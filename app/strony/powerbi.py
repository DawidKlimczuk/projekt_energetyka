import io
import json
import zipfile
from pathlib import Path

import pandas as pd
import streamlit as st

from src.konfiguracja import KATALOG_PROJEKTU
from wspolne import naglowek, wniosek

KATALOG_ZRZUTOW = Path(__file__).resolve().parents[1] / "raport_powerbi"
KATALOG_PBI = KATALOG_PROJEKTU / "powerbi"

STRONY = [
    ("Przegląd KSE", "Struktura wytwarzania w grupach paliw, udział OZE w kolejnych latach i kluczowe wskaźniki "
                     "systemu. Fragmentatory roku, sezonu i typu dnia filtrują wszystkie wizualizacje strony."),
    ("Pogoda a system", "Zależność zapotrzebowania od temperatury z podziałem na typy dni oraz mapa ciepła "
                        "zapotrzebowania według godziny i dnia tygodnia (P1); zależność generacji wiatrowej od "
                        "prędkości wiatru – krzywa mocy oraz przyrost mocy zainstalowanej w kolejnych latach (P2)."),
    ("Rynek energii", "Średnia cena RDN według godziny i miesiąca – widoczne niskie ceny w południe w miesiącach "
                      "wiosenno-letnich i wieczorne szczyty cenowe latem; zależność ceny od udziału OZE (P3)."),
    ("Prognoza", "Porównanie modelu uczenia maszynowego z prognozą PSE na zbiorze testowym (P4). Parametr what-if "
                 "pozwala zmienić temperaturę o −10…+10°C – na zrzucie wybrano −5°C."),
    ("Profile dobowe", "Typowe dobowe przebiegi zapotrzebowania i cen wyznaczone metodą K-means (P5) oraz zestawienie "
                       "błędów wszystkich modeli prognostycznych."),
]


@st.cache_data
def model_danych():
    """Tabele, relacje i miary DAX odczytane z definicji modelu Power BI (model.bim)."""
    model = json.loads((KATALOG_PBI / "KSE.SemanticModel" / "model.bim").read_text(encoding="utf-8"))["model"]
    tabele, miary = [], []
    for tabela in model["tables"]:
        zrodlo = " ".join(tabela["partitions"][0]["source"]["expression"])
        widok = zrodlo.split("FROM ")[1].split('"')[0] if "FROM " in zrodlo else "parametr what-if"
        tabele.append((tabela["name"], widok, len(tabela["columns"]), len(tabela.get("measures", []))))
        for miara in tabela.get("measures", []):
            wyrazenie = miara["expression"]
            miary.append((miara["name"], tabela["name"],
                          "\n".join(wyrazenie) if isinstance(wyrazenie, list) else wyrazenie))
    relacje = [(f'{r["fromTable"]}[{r["fromColumn"]}]', f'{r["toTable"]}[{r["toColumn"]}]')
               for r in model["relationships"]]
    return (pd.DataFrame(tabele, columns=["Tabela w modelu", "Widok w bazie danych", "Kolumny", "Miary"]),
            pd.DataFrame(relacje, columns=["Tabela faktów (wiele)", "Wymiar (jeden)"]),
            pd.DataFrame(miary, columns=["Miara", "Tabela", "Wyrażenie DAX"]))


@st.cache_data
def projekt_zip():
    """Archiwum ZIP z projektem Power BI (bez plików lokalnych .pbi)."""
    bufor = io.BytesIO()
    with zipfile.ZipFile(bufor, "w", zipfile.ZIP_DEFLATED) as archiwum:
        for plik in KATALOG_PBI.rglob("*"):
            if plik.is_file() and ".pbi" not in plik.relative_to(KATALOG_PBI).parts:
                archiwum.write(plik, Path("powerbi") / plik.relative_to(KATALOG_PBI))
    return bufor.getvalue()


naglowek("Raport Power BI", "Raport Power BI",
         "Interaktywny raport przygotowany w Power BI Desktop na podstawie tej samej bazy danych, "
         "z której korzysta aplikacja.")

wniosek("Raport odczytuje dane z bazy SQLite projektu przez sterownik ODBC – każda tabela modelu pochodzi "
        "z widoku raportowego <b>pbi_*</b> (schemat gwiazdy: 5 tabel faktów, 4 wymiary, tabele wyników analiz). "
        "Poniżej przedstawiono wszystkie strony raportu oraz definicję modelu danych.")

zakladki = st.tabs([nazwa for nazwa, _ in STRONY])
for nr, (zakladka, (nazwa, opis)) in enumerate(zip(zakladki, STRONY), start=1):
    with zakladka:
        st.caption(opis)
        st.image(str(KATALOG_ZRZUTOW / f"strona_{nr}.png"), width="stretch")

st.subheader("Model danych")
tabele, relacje, miary = model_danych()
lewa, prawa = st.columns([3, 2], gap="large")
with lewa:
    st.markdown(f"**Tabele ({len(tabele)})**")
    st.dataframe(tabele, hide_index=True, width="stretch")
with prawa:
    st.markdown(f"**Relacje ({len(relacje)})** – kierunek filtrowania: wymiar → fakt")
    st.dataframe(relacje, hide_index=True, width="stretch")

st.markdown(f"**Miary DAX ({len(miary)})**")
for tabela, grupa in miary.groupby("Tabela", sort=False):
    with st.expander(f"{tabela} – {len(grupa)} miar"):
        for _, miara in grupa.iterrows():
            st.markdown(f"`{miara['Miara']}`")
            st.code(miara["Wyrażenie DAX"], language=None)

st.subheader("Pobierz projekt")
st.download_button("Projekt Power BI (ZIP)", projekt_zip(), "projekt_powerbi_KSE.zip", "application/zip")
st.caption("Otwarcie projektu wymaga Power BI Desktop, sterownika „SQLite3 ODBC Driver” oraz pliku bazy danych "
           "data/kse.db – instrukcja w pliku README.md repozytorium.")
