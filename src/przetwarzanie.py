"""Czyszczenie i integracja danych (etap 3 projektu).

Wszystkie zbiory są sprowadzane do wspólnego klucza: początek godziny w czasie UTC.
Praca w UTC eliminuje problem dób 23- i 25-godzinnych przy zmianie czasu.
Dane 15-minutowe są agregowane do godzin średnią (moc w MW, cena w PLN/MWh).

Wynik zapisywany jest w bazie danych (data/kse.db, schemat: sql/schemat.sql):
    dim_kalendarz, dim_godzina, dim_czas, dim_zrodlo, dim_lokalizacja – wymiary,
    fakt_kse_godzinowy   – jeden wiersz = jedna godzina,
    fakt_miks            – generacja wg typu źródła (format długi),
    fakt_pogoda_stacje   – pomiary pogodowe z poszczególnych miast,
    jakosc_danych        – raport kompletności danych.
"""
import holidays
import numpy as np
import pandas as pd

from src import baza_danych
from src.konfiguracja import (DANE_SUROWE, DATA_DO, DATA_OD, LOKALIZACJE, REFORMA_RB,
                              STREFA_LOKALNA)

# Słownik typów źródeł wytwarzania (kody PsrType ENTSO-E).
# grupa – agregacja źródeł prezentowana na wykresach miksu (8 grup).
ZRODLA = pd.DataFrame([
    ("B05", "Węgiel kamienny", "konwencjonalne", "Węgiel kamienny"),
    ("B02", "Węgiel brunatny", "konwencjonalne", "Węgiel brunatny"),
    ("B04", "Gaz ziemny", "konwencjonalne", "Gaz ziemny"),
    ("B03", "Gaz koksowniczy", "konwencjonalne", "Pozostałe"),
    ("B06", "Olej opałowy", "konwencjonalne", "Pozostałe"),
    ("B20", "Pozostałe", "konwencjonalne", "Pozostałe"),
    ("B17", "Odpady", "konwencjonalne", "Pozostałe"),
    ("B10", "Elektrownie szczytowo-pompowe", "magazynowanie", "Woda i magazyny"),
    ("B19", "Wiatr na lądzie", "OZE", "Wiatr"),
    ("B18", "Wiatr na morzu", "OZE", "Wiatr"),
    ("B16", "Fotowoltaika", "OZE", "Fotowoltaika"),
    ("B01", "Biomasa", "OZE", "Biomasa"),
    ("B11", "Elektrownie wodne przepływowe", "OZE", "Woda i magazyny"),
    ("B12", "Elektrownie wodne zbiornikowe", "OZE", "Woda i magazyny"),
    ("B15", "Inne OZE", "OZE", "Pozostałe"),
], columns=["kod_zrodla", "nazwa_zrodla", "kategoria", "grupa"])


def _zakres_godzin():
    """Pełna siatka godzin UTC odpowiadająca okresowi analizy w czasie lokalnym."""
    start = pd.Timestamp(DATA_OD, tz=STREFA_LOKALNA).tz_convert("UTC")
    stop = (pd.Timestamp(DATA_DO, tz=STREFA_LOKALNA) + pd.Timedelta(days=1)).tz_convert("UTC")
    return pd.date_range(start, stop, freq="h", inclusive="left", name="czas_utc")


def _liczba(seria):
    """Zamiana zapisu '15 231,5' na liczbę zmiennoprzecinkową."""
    return pd.to_numeric(
        seria.astype(str).str.replace("\xa0", "").str.replace(" ", "").str.replace(",", "."),
        errors="coerce")


def _czas_z_doby_handlowej(tabela, kolumna_daty):
    """Zamienia datę i kolejną godzinę doby handlowej (1–24, w dobach zmiany czasu
    23 lub 25) na początek godziny w UTC. Kolejny wiersz danej doby = kolejna
    godzina od północy czasu lokalnego, co poprawnie obsługuje zmianę czasu."""
    data = pd.to_datetime(tabela[kolumna_daty])
    polnoc_utc = data.dt.tz_localize(STREFA_LOKALNA).dt.tz_convert("UTC")
    numer_w_dobie = tabela.groupby(kolumna_daty).cumcount()
    return polnoc_utc + pd.to_timedelta(numer_w_dobie, unit="h")


# ---------------------------------------------------------------------------
# Z1. PSE
# ---------------------------------------------------------------------------
def _wczytaj_archiwum(raport):
    pliki = sorted((DANE_SUROWE / "pse_archiwum" / raport).glob("*.csv"))
    czesci = [pd.read_csv(p, sep=";", dtype=str) for p in pliki]
    tabela = pd.concat(czesci, ignore_index=True)
    kolumna_daty = tabela.columns[0]                      # "Data" lub "Doba"
    tabela = tabela.dropna(subset=[kolumna_daty]).drop_duplicates()
    tabela["czas_utc"] = _czas_z_doby_handlowej(tabela, kolumna_daty)
    return tabela


def _wczytaj_api(endpoint):
    pliki = sorted((DANE_SUROWE / "pse_api" / endpoint).glob("*.csv"))
    tabela = pd.concat([pd.read_csv(p) for p in pliki], ignore_index=True)
    # dtime_utc oznacza koniec okresu 15-minutowego – przesuwamy na początek okresu
    koniec = pd.to_datetime(tabela["dtime_utc"]).dt.tz_localize("UTC")
    tabela["czas_utc"] = (koniec - pd.Timedelta(minutes=15)).dt.floor("h")
    return tabela


def przygotuj_pse():
    """Zapotrzebowanie, prognoza PSE i generacja wiatr/PV jako szereg godzinowy."""
    # Archiwum (do 13.06.2024) – dane godzinowe
    wyk = _wczytaj_archiwum("PL_WYK_KSE")
    wyk["zapotrzebowanie_mw"] = _liczba(wyk["Krajowe zapotrzebowanie na moc"])

    oze = _wczytaj_archiwum("PL_GEN_WIATR")
    oze["generacja_wiatr_mw"] = _liczba(oze["Generacja źródeł wiatrowych"])
    oze["generacja_pv_mw"] = _liczba(oze["Generacja źródeł fotowoltaicznych"])

    plan = _wczytaj_archiwum("PL_PD_GO_BILANS")
    plan["prognoza_sieci_pse_mw"] = _liczba(plan["Prognozowane zapotrzebowanie sieci"])

    # Archiwalna „prognoza zapotrzebowania sieci” obejmuje inny zakres niż krajowe
    # zapotrzebowanie na moc (jest systematycznie niższa o ok. 2,3 GW), dlatego nie jest
    # porównywalna z prognozą publikowaną od 14.06.2024. Zachowujemy ją w osobnej
    # kolumnie, a prognoza PSE (prognoza_pse_mw) przed tą datą pozostaje pusta.
    archiwum = (wyk.set_index("czas_utc")[["zapotrzebowanie_mw"]]
                .join(oze.set_index("czas_utc")[["generacja_wiatr_mw", "generacja_pv_mw"]])
                .join(plan.set_index("czas_utc")[["prognoza_sieci_pse_mw"]]))

    # API (od 14.06.2024) – dane 15-minutowe uśredniane do godzin
    obciazenie = (_wczytaj_api("kse-load")
                  .groupby("czas_utc")[["load_actual", "load_fcst"]].mean()
                  .rename(columns={"load_actual": "zapotrzebowanie_mw", "load_fcst": "prognoza_pse_mw"}))
    wielkosci = (_wczytaj_api("his-wlk-cal")
                 .groupby("czas_utc")[["wi", "pv"]].mean()
                 .rename(columns={"wi": "generacja_wiatr_mw", "pv": "generacja_pv_mw"}))
    api = obciazenie.join(wielkosci)

    granica = pd.Timestamp(REFORMA_RB, tz=STREFA_LOKALNA).tz_convert("UTC")
    pse = pd.concat([archiwum[archiwum.index < granica], api[api.index >= granica]])
    return pse[~pse.index.duplicated()].sort_index()


# ---------------------------------------------------------------------------
# Z2. Miks energetyczny
# ---------------------------------------------------------------------------
def przygotuj_miks():
    """Generacja wg typu źródła – średnia godzinowa, format długi."""
    katalog = DANE_SUROWE / "miks"
    zrodlo = "entsoe" if any((katalog / "entsoe").glob("*.csv")) else "energy_charts"
    pliki = sorted((katalog / zrodlo).glob("*.csv"))
    miks = pd.concat([pd.read_csv(p) for p in pliki], ignore_index=True)
    miks["czas_utc"] = pd.to_datetime(miks["czas_utc"], utc=True).dt.floor("h")
    miks = (miks.groupby(["czas_utc", "kod_zrodla"], as_index=False)["generacja_mw"].mean())
    # typy źródeł, które w Polsce nie występują (same zera lub braki), są pomijane
    aktywne = miks.groupby("kod_zrodla")["generacja_mw"].sum()
    miks = miks[miks["kod_zrodla"].isin(aktywne[aktywne > 0].index)]
    return miks


# ---------------------------------------------------------------------------
# Z3. Ceny energii
# ---------------------------------------------------------------------------
def przygotuj_ceny():
    """Cena RDN w PLN/MWh: PSE (SDAC, PLN) od 14.06.2024, wcześniej EUR × kurs NBP."""
    sdac = _wczytaj_api("csdac-pln").groupby("czas_utc")["csdac_pln"].mean()

    eur = pd.read_csv(DANE_SUROWE / "ceny" / "ceny_dnia_nastepnego_eur.csv")
    eur["czas_utc"] = pd.to_datetime(eur["czas_utc"], utc=True).dt.floor("h")
    eur = eur.groupby("czas_utc")["cena_eur_mwh"].mean().reset_index()

    kursy = pd.read_csv(DANE_SUROWE / "ceny" / "kurs_eur_nbp.csv", parse_dates=["data"])
    eur["data"] = eur["czas_utc"].dt.tz_convert(STREFA_LOKALNA).dt.tz_localize(None).dt.normalize()
    # kurs z dnia notowania lub ostatni opublikowany wcześniej (weekendy, święta)
    eur = pd.merge_asof(eur.sort_values("data"), kursy.sort_values("data"), on="data")
    # pierwsze dni okresu (1–2.01.2022) poprzedzają pierwsze notowanie – kurs z najbliższego notowania
    eur["kurs_eur_pln"] = eur["kurs_eur_pln"].bfill()
    eur["cena_pln_mwh"] = eur["cena_eur_mwh"] * eur["kurs_eur_pln"]
    eur = eur.set_index("czas_utc")["cena_pln_mwh"].sort_index()

    granica = pd.Timestamp(REFORMA_RB, tz=STREFA_LOKALNA).tz_convert("UTC")
    ceny = pd.concat([eur[eur.index < granica], sdac[sdac.index >= granica]])
    return ceny[~ceny.index.duplicated()].rename("cena_pln_mwh").to_frame()


# ---------------------------------------------------------------------------
# Z4. Pogoda
# ---------------------------------------------------------------------------
def przygotuj_pogode():
    """Zwraca (pomiary dla stacji w formacie długim, średnie ważone dla Polski)."""
    czesci = []
    for miejsce in LOKALIZACJE:
        tabela = pd.read_csv(DANE_SUROWE / "pogoda" / f"{miejsce['id']}.csv")
        tabela["czas_utc"] = pd.to_datetime(tabela["time"]).dt.tz_localize("UTC")
        tabela["id_stacji"] = miejsce["id"]
        czesci.append(tabela.drop(columns="time"))
    stacje = pd.concat(czesci, ignore_index=True).rename(columns={
        "temperature_2m": "temperatura_c", "wind_speed_100m": "wiatr_100m_ms",
        "shortwave_radiation": "promieniowanie_wm2", "cloud_cover": "zachmurzenie_proc"})

    wagi = pd.DataFrame(LOKALIZACJE).set_index("id")
    stacje["w_lud"] = stacje["id_stacji"].map(wagi["waga_ludnosc"])
    stacje["w_wiatr"] = stacje["id_stacji"].map(wagi["waga_wiatr"])

    # średnia ważona: suma(wartość × waga) / suma(wag) dla każdej godziny
    stacje["t_x_w"] = stacje["temperatura_c"] * stacje["w_lud"]
    stacje["v_x_w"] = stacje["wiatr_100m_ms"] * stacje["w_wiatr"]
    g = stacje.groupby("czas_utc")
    polska = pd.DataFrame({
        "temperatura_c": g["t_x_w"].sum() / g["w_lud"].sum(),
        "wiatr_100m_ms": g["v_x_w"].sum() / g["w_wiatr"].sum(),
        "promieniowanie_wm2": g["promieniowanie_wm2"].mean(),
        "zachmurzenie_proc": g["zachmurzenie_proc"].mean(),
    })
    stacje = stacje.drop(columns=["w_lud", "w_wiatr", "t_x_w", "v_x_w"])
    return stacje, polska


# ---------------------------------------------------------------------------
# Z5. Kalendarz
# ---------------------------------------------------------------------------
def dodaj_kalendarz(tabela):
    """Zmienne kalendarzowe liczone według czasu lokalnego."""
    lokalny = tabela.index.tz_convert(STREFA_LOKALNA)
    swieta = holidays.Poland(years=range(lokalny.year.min(), lokalny.year.max() + 2))

    tabela["czas_lokalny"] = lokalny.tz_localize(None)
    tabela["data"] = tabela["czas_lokalny"].dt.normalize()
    tabela["godzina"] = lokalny.hour
    tabela["dzien_tygodnia"] = lokalny.dayofweek          # 0 = poniedziałek
    tabela["miesiac"] = lokalny.month
    tabela["rok"] = lokalny.year
    tabela["swieto"] = tabela["data"].dt.date.map(lambda d: d in swieta).astype(int)
    tabela["weekend"] = (tabela["dzien_tygodnia"] >= 5).astype(int)

    # dzień pomostowy: dzień roboczy między świętem a weekendem (np. piątek po czwartkowym święcie)
    dni = pd.DataFrame({"data": pd.date_range(tabela["data"].min(), tabela["data"].max())})
    dni["wolny"] = (dni["data"].dt.dayofweek >= 5) | dni["data"].dt.date.map(lambda d: d in swieta)
    dni["pomostowy"] = (~dni["wolny"] & dni["wolny"].shift(1, fill_value=False)
                        & dni["wolny"].shift(-1, fill_value=False))
    tabela["dzien_pomostowy"] = tabela["data"].map(dni.set_index("data")["pomostowy"]).astype(int)

    tabela["typ_dnia"] = np.select(
        [tabela["swieto"] == 1, tabela["weekend"] == 1, tabela["dzien_pomostowy"] == 1],
        ["święto", "weekend", "pomostowy"], default="roboczy")
    tabela["sezon"] = tabela["miesiac"].map({12: "zima", 1: "zima", 2: "zima", 3: "wiosna", 4: "wiosna",
                                              5: "wiosna", 6: "lato", 7: "lato", 8: "lato",
                                              9: "jesień", 10: "jesień", 11: "jesień"})
    return tabela


# ---------------------------------------------------------------------------
# Integracja
# ---------------------------------------------------------------------------
def raport_jakosci(przed, po):
    """Liczba braków w każdej kolumnie przed i po uzupełnieniu krótkich luk."""
    return pd.DataFrame({
        "liczba_godzin": len(przed),
        "braki_przed": przed.isna().sum(),
        "braki_po": po.isna().sum(),
    }).assign(kompletnosc_proc=lambda t: (100 * (1 - t["braki_po"] / t["liczba_godzin"])).round(3))


def zbuduj_zbior():
    print("Przetwarzanie PSE...")
    pse = przygotuj_pse()
    print("Przetwarzanie miksu...")
    miks = przygotuj_miks()
    print("Przetwarzanie cen...")
    ceny = przygotuj_ceny()
    print("Przetwarzanie pogody...")
    stacje, pogoda = przygotuj_pogode()

    # udziały w miksie (format szeroki tylko dla wybranych agregatów)
    miks_kat = miks.merge(ZRODLA, on="kod_zrodla", how="left")
    produkcja = miks_kat[miks_kat["kategoria"] != "magazynowanie"]
    suma = produkcja.groupby("czas_utc")["generacja_mw"].sum()
    oze = produkcja[produkcja["kategoria"] == "OZE"].groupby("czas_utc")["generacja_mw"].sum()
    wegiel = produkcja[produkcja["kod_zrodla"].isin(["B02", "B05"])].groupby("czas_utc")["generacja_mw"].sum()
    udzialy = pd.DataFrame({
        "generacja_calkowita_mw": suma,
        "udzial_oze_proc": 100 * oze / suma,
        "udzial_wegla_proc": 100 * wegiel / suma,
    })

    zbior = (pd.DataFrame(index=_zakres_godzin())
             .join(pse).join(ceny).join(pogoda).join(udzialy))

    przed = zbior.copy()
    # krótkie luki (do 3 godzin) uzupełniane interpolacją liniową
    kolumny = zbior.columns
    zbior[kolumny] = zbior[kolumny].interpolate(limit=3, limit_area="inside")
    jakosc = raport_jakosci(przed, zbior)

    zbior["zapotrzebowanie_netto_mw"] = (zbior["zapotrzebowanie_mw"]
                                         - zbior["generacja_wiatr_mw"] - zbior["generacja_pv_mw"])
    zbior = dodaj_kalendarz(zbior)

    print(jakosc)
    zapisz_do_bazy(zbior, miks, stacje, jakosc)
    return zbior


# ---------------------------------------------------------------------------
# Zapis do bazy danych
# ---------------------------------------------------------------------------
MIESIACE = ["styczeń", "luty", "marzec", "kwiecień", "maj", "czerwiec", "lipiec",
            "sierpień", "wrzesień", "październik", "listopad", "grudzień"]
DNI = ["poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela"]
KOLUMNY_KALENDARZA = ["czas_lokalny", "data", "godzina", "dzien_tygodnia", "miesiac", "rok", "swieto",
                      "weekend", "dzien_pomostowy", "typ_dnia", "sezon"]


def pora_dnia(godzina):
    if 6 <= godzina <= 9:
        return "szczyt poranny"
    if 10 <= godzina <= 15:
        return "południe"
    if 16 <= godzina <= 21:
        return "szczyt wieczorny"
    return "noc"


def tabela_kalendarza(zbior):
    """Wymiar kalendarza: jeden wiersz = jedna doba okresu analizy."""
    kalendarz = (zbior.groupby("data")[["rok", "miesiac", "dzien_tygodnia", "swieto", "weekend",
                                        "dzien_pomostowy", "typ_dnia", "sezon"]].first().reset_index())
    swieta = holidays.Poland(years=range(kalendarz["rok"].min(), kalendarz["rok"].max() + 1), language="pl")
    kalendarz["kwartal"] = "Q" + kalendarz["data"].dt.quarter.astype(str)
    kalendarz["miesiac_nazwa"] = kalendarz["miesiac"].map(lambda m: MIESIACE[m - 1])
    kalendarz["rok_miesiac"] = kalendarz["data"].dt.strftime("%Y-%m")
    kalendarz["poczatek_miesiaca"] = kalendarz["data"].dt.to_period("M").dt.start_time.dt.strftime("%Y-%m-%d")
    kalendarz["dzien_tygodnia_nazwa"] = kalendarz["dzien_tygodnia"].map(lambda d: DNI[d])
    kalendarz["nazwa_swieta"] = kalendarz["data"].dt.date.map(lambda d: swieta.get(d))
    return kalendarz


def zapisz_do_bazy(zbior, miks, stacje, jakosc):
    """Tworzy bazę danych od nowa i zapisuje wymiary oraz fakty. Miks i pogoda
    ograniczane są do godzin okresu analizy (klucz obcy do dim_czas); w miksie
    (format długi) brak pomiaru oznacza brak wiersza."""
    miks = miks.dropna(subset=["generacja_mw"])
    baza_danych.utworz_baze()
    baza_danych.zapisz("dim_kalendarz", tabela_kalendarza(zbior))
    godziny = pd.DataFrame({"godzina": range(24)})
    godziny["przedzial"] = godziny["godzina"].map(lambda g: f"{g:02d}:00–{(g + 1) % 24:02d}:00")
    godziny["pora_dnia"] = godziny["godzina"].map(pora_dnia)
    baza_danych.zapisz("dim_godzina", godziny)
    baza_danych.zapisz("dim_czas", zbior[["czas_lokalny", "data", "godzina"]].reset_index())
    baza_danych.zapisz("dim_zrodlo", ZRODLA)
    baza_danych.zapisz("dim_lokalizacja", pd.DataFrame(LOKALIZACJE).rename(columns={
        "id": "id_stacji", "nazwa": "miasto", "lat": "szerokosc", "lon": "dlugosc",
        "waga_ludnosc": "ludnosc_wojewodztwa_mln", "waga_wiatr": "udzial_mocy_wiatrowej"}))

    baza_danych.zapisz("fakt_kse_godzinowy", zbior.drop(columns=KOLUMNY_KALENDARZA).reset_index())
    baza_danych.zapisz("fakt_miks", miks[miks["czas_utc"].isin(zbior.index)])
    baza_danych.zapisz("fakt_pogoda_stacje", stacje[stacje["czas_utc"].isin(zbior.index)])
    baza_danych.zapisz("jakosc_danych", jakosc.rename_axis("zmienna").reset_index())


if __name__ == "__main__":
    zbuduj_zbior()
