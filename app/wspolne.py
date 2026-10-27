"""Elementy wspólne aplikacji: wczytywanie danych, kolory, szablon wykresów."""
import sys
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import baza_danych  # noqa: E402
from src.konfiguracja import LOKALIZACJE  # noqa: E402

# ---------------------------------------------------------------------------
# Kolory
# ---------------------------------------------------------------------------
TUSZ = "#16232B"
TUSZ_DRUGORZEDNY = "#52514e"
TUSZ_WYCISZONY = "#898781"
SIATKA = "#e1e0d9"
OS = "#c3c2b7"
POWIERZCHNIA = "#fcfcfb"
AKCENT = "#0B4F6C"

NIEBIESKI, POMARANCZOWY, MORSKI, ZOLTY = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
MAGENTA, ZIELONY, FIOLET, CZERWONY = "#e87ba4", "#008300", "#6250d6", "#e34948"

KOLORY_SERII = {
    "Rzeczywiste": TUSZ,
    "Model ML": NIEBIESKI,
    "Prognoza PSE": POMARANCZOWY,
    "Prognoza naiwna": TUSZ_WYCISZONY,
}

# Kolory grup miksu (przypisanie źródeł do grup: tabela dim_zrodlo w bazie danych).
# Kolejność = kolejność warstw (od dołu) i kolejność slotów palety, która gwarantuje
# rozróżnialność sąsiednich warstw także przy zaburzeniach widzenia barw.
KOLORY_MIKSU = {
    "Węgiel kamienny": CZERWONY,
    "Węgiel brunatny": FIOLET,
    "Biomasa": ZIELONY,
    "Pozostałe": MAGENTA,
    "Fotowoltaika": ZOLTY,
    "Woda i magazyny": MORSKI,
    "Gaz ziemny": POMARANCZOWY,
    "Wiatr": NIEBIESKI,
}

SKALA_SEKWENCYJNA = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
SKALA_ROZBIEZNA = [[0, "#184f95"], [0.25, "#6da7ec"], [0.5, "#f0efec"], [0.75, "#f08a7e"], [1, "#b8302f"]]

DNI = ["pon", "wt", "śr", "czw", "pt", "sob", "nd"]
MIESIACE = ["sty", "lut", "mar", "kwi", "maj", "cze", "lip", "sie", "wrz", "paź", "lis", "gru"]

# ---------------------------------------------------------------------------
# Szablon wykresów Plotly
# ---------------------------------------------------------------------------
pio.templates["kse"] = go.layout.Template(layout=dict(
    font=dict(family="Source Sans 3, Segoe UI, system-ui, sans-serif", size=13, color=TUSZ),
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor=POWIERZCHNIA,
    colorway=[NIEBIESKI, POMARANCZOWY, MORSKI, ZOLTY, MAGENTA, ZIELONY, FIOLET, CZERWONY],
    xaxis=dict(gridcolor=SIATKA, linecolor=OS, zerolinecolor=OS, tickcolor=OS,
               title_font_color=TUSZ_DRUGORZEDNY, tickfont_color=TUSZ_DRUGORZEDNY),
    yaxis=dict(gridcolor=SIATKA, linecolor=OS, zerolinecolor=OS, tickcolor=OS,
               title_font_color=TUSZ_DRUGORZEDNY, tickfont_color=TUSZ_DRUGORZEDNY),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0,
                font_color=TUSZ_DRUGORZEDNY, bgcolor="rgba(0,0,0,0)"),
    margin=dict(l=10, r=10, t=40, b=10),
    hoverlabel=dict(bgcolor="white", bordercolor=SIATKA, font_color=TUSZ),
    hovermode="x unified",
    separators=", ",
))
pio.templates.default = "kse"

KONFIG_WYKRESU = {"displaylogo": False, "locale": "pl",
                  "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"]}


def wykres(fig, wysokosc=420):
    fig.update_layout(height=wysokosc)
    st.plotly_chart(fig, width="stretch", config=KONFIG_WYKRESU)


# ---------------------------------------------------------------------------
# Wygląd strony
# ---------------------------------------------------------------------------
CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Archivo:wght@600;800&family=Source+Sans+3:wght@400;600&display=swap');
html, body, [class*="css"], .stMarkdown, .stText { font-family: "Source Sans 3", "Segoe UI", sans-serif; }
h1, h2, h3 { font-family: "Archivo", "Segoe UI", sans-serif !important; letter-spacing: -0.01em; color: #16232B; }
h1 { font-weight: 800 !important; }
.block-container { padding-top: 3.2rem; max-width: 1280px; }
.naglowek-strony { border-left: 5px solid #0B4F6C; padding: 0.2rem 0 0.2rem 1rem; margin-bottom: 1.2rem; }
.naglowek-strony .nadtytul { text-transform: uppercase; letter-spacing: 0.08em; font-size: 0.78rem;
    color: #0B4F6C; font-weight: 600; }
.naglowek-strony h1 { margin: 0.1rem 0 0.2rem 0; padding: 0; font-size: 2.1rem; }
.naglowek-strony p { color: #56666F; margin: 0; font-size: 1.05rem; }
.kafel { background: #FFFFFF; border: 1px solid #D5DEE3; border-radius: 10px; padding: 0.85rem 1rem;
    min-height: 124px; }
.kafel .etykieta { color: #56666F; font-size: 0.85rem; }
.kafel .wartosc { font-family: "Archivo", sans-serif; font-weight: 800; font-size: 1.55rem; color: #16232B;
    line-height: 1.25; white-space: nowrap; }
.kafel .jednostka { font-size: 0.95rem; font-weight: 600; color: #56666F; margin-left: 0.15rem; }
.kafel .opis { color: #56666F; font-size: 0.82rem; }
.wniosek { background: #E3EEF3; border-radius: 10px; padding: 0.85rem 1.1rem; margin: 0.4rem 0 1rem 0;
    color: #16232B; }
.wniosek b { color: #0B4F6C; }
.hipoteza { background: #FFFFFF; border: 1px solid #D5DEE3; border-radius: 10px; padding: 0.9rem 1.1rem;
    margin-bottom: 0.7rem; }
.hipoteza .status { font-weight: 600; font-size: 0.85rem; }
.potwierdzona { color: #006300; }
.czesciowo { color: #B86E00; }
.odrzucona { color: #d03b3b; }
div[data-testid="stMetricValue"] { font-family: "Archivo", sans-serif; }
</style>
"""


def konfiguruj_aplikacje():
    st.set_page_config(page_title="Pogoda, OZE i cena prądu", page_icon="⚡", layout="wide")
    st.markdown(CSS, unsafe_allow_html=True)
    with st.sidebar:
        st.markdown("**Pogoda, OZE i cena prądu**  \nAnaliza i prognoza zapotrzebowania KSE")
        st.caption("Metody analizy, przetwarzania i wizualizacji danych · WSB")
        st.caption("Dawid Klimczuk · Maria Gosa · Wiktoria Dębińska")


def naglowek(nadtytul, tytul, opis=""):
    st.markdown(f'<div class="naglowek-strony"><div class="nadtytul">{nadtytul}</div>'
                f'<h1>{tytul}</h1><p>{opis}</p></div>', unsafe_allow_html=True)


def kafle(elementy):
    """elementy: lista krotek (etykieta, wartość, opis). Jednostka po ostatniej spacji
    w wartości (np. „532 PLN/MWh”) wyświetlana jest mniejszą czcionką."""
    kolumny = st.columns(len(elementy))
    for kolumna, (etykieta, wartosc, opis) in zip(kolumny, elementy):
        liczba_tekst, _, jednostka = str(wartosc).rpartition(" ")
        if liczba_tekst and any(z.isalpha() for z in jednostka):
            wartosc = f'{liczba_tekst}<span class="jednostka">{jednostka}</span>'
        kolumna.markdown(f'<div class="kafel"><div class="etykieta">{etykieta}</div>'
                         f'<div class="wartosc">{wartosc}</div><div class="opis">{opis}</div></div>',
                         unsafe_allow_html=True)


def wniosek(tekst):
    st.markdown(f'<div class="wniosek">{tekst}</div>', unsafe_allow_html=True)


def liczba(x, miejsca=0):
    """Format liczby z polskim separatorem tysięcy i przecinkiem dziesiętnym."""
    tekst = f"{x:,.{miejsca}f}"
    return tekst.replace(",", " ").replace(".", ",")


# ---------------------------------------------------------------------------
# Dane – odczyt z bazy SQLite (data/kse.db), wyniki zapamiętywane w pamięci podręcznej
# ---------------------------------------------------------------------------
NAZWY_MIAR = {"mape_proc": "MAPE [%]", "mae_mw": "MAE [MW]", "rmse_mw": "RMSE [MW]"}


@st.cache_data(show_spinner="Wczytywanie danych...")
def zbior():
    """Zintegrowany zbiór godzinowy (widok v_kse_godzinowy)."""
    return baza_danych.wczytaj_zbior()


@st.cache_data(show_spinner="Wczytywanie miksu...")
def miks_grupy():
    """Generacja w grupach paliw (widok v_miks_grupy), format długi."""
    return baza_danych.wczytaj("SELECT * FROM v_miks_grupy")


@st.cache_data
def pogoda_stacje():
    return baza_danych.wczytaj("SELECT * FROM fakt_pogoda_stacje")


@st.cache_data
def prognozy_test():
    """Prognozy na zbiorze testowym – kolumna dla każdego modelu."""
    return baza_danych.wczytaj_prognozy()


@st.cache_data
def zapytanie(sql, parametry=()):
    """Wynik dowolnego zapytania SQL do bazy projektu."""
    return baza_danych.wczytaj(sql, parametry)


def metryki_modeli():
    return zapytanie("SELECT * FROM metryki_modeli ORDER BY mape_proc").set_index("model")


def lokalizacje():
    return pd.DataFrame(LOKALIZACJE)


def filtr_okresu(dane, klucz="okres"):
    """Filtr lat, sezonu i typu dnia w jednym wierszu nad wykresami."""
    k1, k2, k3 = st.columns([2, 1, 1])
    lata = sorted(dane["rok"].unique())
    wybrane_lata = k1.segmented_control("Rok", lata, default=lata, selection_mode="multi", key=f"{klucz}_rok")
    sezon = k2.selectbox("Sezon", ["wszystkie", "zima", "wiosna", "lato", "jesień"], key=f"{klucz}_sezon")
    typ = k3.selectbox("Typ dnia", ["wszystkie", "roboczy", "weekend", "święto", "pomostowy"], key=f"{klucz}_typ")
    maska = dane["rok"].isin(wybrane_lata or lata)
    if sezon != "wszystkie":
        maska &= dane["sezon"] == sezon
    if typ != "wszystkie":
        maska &= dane["typ_dnia"] == typ
    return dane[maska]
