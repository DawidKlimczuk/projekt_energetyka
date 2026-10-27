"""Obsługa bazy danych projektu (SQLite, plik data/kse.db).

Struktura bazy opisana jest w plikach SQL:
    sql/schemat.sql         – tabele wymiarów, faktów i wyników analiz, klucze, widoki analityczne,
    sql/widoki_powerbi.sql  – widoki raportowe (prefiks pbi_) odczytywane przez Power BI.

Etapy przetwarzania zapisują wyniki funkcją zapisz(), a model, klasteryzacja
i aplikacja odczytują dane funkcją wczytaj() (dowolne zapytanie SQL).
Daty i czasy przechowywane są jako tekst w formacie ISO 8601, ponieważ SQLite
nie posiada osobnego typu daty.
"""
import sqlite3

import pandas as pd

from src.konfiguracja import BAZA_DANYCH, KATALOG_SQL

SKRYPTY = ["schemat.sql", "widoki_powerbi.sql"]


def polacz():
    polaczenie = sqlite3.connect(BAZA_DANYCH)
    polaczenie.execute("PRAGMA foreign_keys = ON")
    return polaczenie


def utworz_baze():
    """Tworzy wszystkie tabele i widoki od nowa (istniejące dane są usuwane)."""
    polaczenie = polacz()
    try:
        for skrypt in SKRYPTY:
            polaczenie.executescript((KATALOG_SQL / skrypt).read_text(encoding="utf-8"))
    finally:
        polaczenie.close()
    print(f"Utworzono bazę danych: {BAZA_DANYCH}")


def _do_zapisu(tabela):
    """Zamienia kolumny dat i czasu na tekst ISO 8601 (czas ze strefą – w UTC)."""
    tabela = tabela.copy()
    for kolumna in tabela.columns:
        seria = tabela[kolumna]
        if isinstance(seria.dtype, pd.DatetimeTZDtype):
            tabela[kolumna] = seria.dt.tz_convert("UTC").dt.strftime("%Y-%m-%d %H:%M:%S")
        elif pd.api.types.is_datetime64_any_dtype(seria):
            format_ = "%Y-%m-%d" if kolumna == "data" else "%Y-%m-%d %H:%M:%S"
            tabela[kolumna] = seria.dt.strftime(format_)
    return tabela


def wyczysc(*nazwy):
    """Usuwa zawartość podanych tabel (w podanej kolejności)."""
    polaczenie = polacz()
    try:
        with polaczenie:
            for nazwa in nazwy:
                polaczenie.execute(f"DELETE FROM {nazwa}")
    finally:
        polaczenie.close()


def zapisz(nazwa, tabela):
    """Zastępuje zawartość tabeli `nazwa` (tabela musi być zdefiniowana w schemacie).
    Operacja wykonywana jest w jednej transakcji – przy błędzie (np. naruszeniu
    klucza obcego) zawartość tabeli pozostaje bez zmian."""
    polaczenie = polacz()
    try:
        with polaczenie:
            polaczenie.execute(f"DELETE FROM {nazwa}")
            _do_zapisu(tabela).to_sql(nazwa, polaczenie, if_exists="append", index=False, chunksize=50_000)
    finally:
        polaczenie.close()
    print(f"  {nazwa}: {len(tabela)} wierszy")


def wczytaj(zapytanie, parametry=()):
    """Wynik zapytania SQL jako DataFrame. Kolumny czas_utc, czas_lokalny i data
    zamieniane są na typ datetime (czas_utc – ze strefą UTC)."""
    polaczenie = polacz()
    try:
        tabela = pd.read_sql_query(zapytanie, polaczenie, params=parametry)
    finally:
        polaczenie.close()
    if "czas_utc" in tabela:
        tabela["czas_utc"] = pd.to_datetime(tabela["czas_utc"], utc=True)
    for kolumna in ("czas_lokalny", "data"):
        if kolumna in tabela:
            tabela[kolumna] = pd.to_datetime(tabela[kolumna])
    return tabela


def wczytaj_zbior():
    """Zintegrowany zbiór godzinowy (widok v_kse_godzinowy) z indeksem czas_utc."""
    return wczytaj("SELECT * FROM v_kse_godzinowy ORDER BY czas_utc").set_index("czas_utc")


def wczytaj_prognozy():
    """Prognozy na zbiorze testowym w formacie szerokim: kolumna = model."""
    dlugie = wczytaj("SELECT * FROM v_prognozy_test")
    szerokie = dlugie.pivot(index=["czas_utc", "czas_lokalny", "rzeczywiste_mw"], columns="model",
                            values="prognoza_mw")
    return szerokie.reset_index().set_index("czas_utc").rename_axis(columns=None)
