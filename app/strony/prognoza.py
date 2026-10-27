import joblib
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.konfiguracja import MODELE
from src.model import CECHY, dodaj_cechy
from wspolne import (AKCENT, KOLORY_SERII, NAZWY_MIAR, NIEBIESKI, POMARANCZOWY, TUSZ_WYCISZONY, kafle, liczba,
                     metryki_modeli, naglowek, prognozy_test, wniosek, wykres, zapytanie, zbior)

naglowek("Prognozowanie · pytanie P4", "Model prognozy zapotrzebowania",
         "Prognoza godzinowego zapotrzebowania na moc na dobę naprzód. Ocena na danych z 2026 r., "
         "które nie były wykorzystywane do uczenia modelu.")

metryki = metryki_modeli()
prognozy = prognozy_test()
waznosc = zapytanie("SELECT * FROM waznosc_cech ORDER BY wzrost_mae_mw DESC")
cv = zapytanie("SELECT * FROM walidacja_krzyzowa")
nazwa_modelu = metryki.drop(index=["Prognoza PSE", "Prognoza naiwna (tydzień wcześniej)"])["mape_proc"].idxmin()

m_model, m_pse = metryki.loc[nazwa_modelu], metryki.loc["Prognoza PSE"]
m_naiwna = metryki.loc["Prognoza naiwna (tydzień wcześniej)"]
kafle([
    (f"MAPE – {nazwa_modelu}", f"{liczba(m_model['mape_proc'], 2)}%", f"MAE {liczba(m_model['mae_mw'])} MW"),
    ("MAPE – prognoza PSE", f"{liczba(m_pse['mape_proc'], 2)}%", f"MAE {liczba(m_pse['mae_mw'])} MW"),
    ("MAPE – prognoza naiwna", f"{liczba(m_naiwna['mape_proc'], 2)}%", "wartość sprzed tygodnia"),
    ("Poprawa względem naiwnej", f"{liczba(100 * (1 - m_model['mape_proc'] / m_naiwna['mape_proc']), 0)}%",
     "redukcja błędu MAPE"),
    ("Godziny testowe", liczba(len(prognozy)), "01.01.2026 – 30.09.2026"),
])

zakl_wyniki, zakl_przebieg, zakl_cechy, zakl_symulacja = st.tabs(
    ["Porównanie modeli", "Przebieg prognoz", "Ważność cech", "Symulacja what-if"])

# ---------------------------------------------------------------------------
with zakl_wyniki:
    st.subheader("Miary błędu na zbiorze testowym")
    st.dataframe(metryki.rename(columns=NAZWY_MIAR).style.format(lambda v: liczba(v, 2), subset=["MAPE [%]"])
                 .format(lambda v: liczba(v), subset=["MAE [MW]", "RMSE [MW]"]), width="stretch")
    lewa, prawa = st.columns([2, 3], gap="large")
    with lewa:
        st.subheader("MAPE modeli")
        kolory = [POMARANCZOWY if m == "Prognoza PSE" else (NIEBIESKI if m == nazwa_modelu else TUSZ_WYCISZONY)
                  for m in metryki.index]
        fig = go.Figure(go.Bar(x=metryki["mape_proc"], y=metryki.index, orientation="h", marker_color=kolory,
                               text=[f"{liczba(v, 2)}%" for v in metryki["mape_proc"]], textposition="outside",
                               cliponaxis=False, hovertemplate="%{y}: %{x:.2f}%<extra></extra>"))
        fig.update_layout(xaxis=dict(title="MAPE [%]", range=[0, metryki["mape_proc"].max() * 1.2]),
                          yaxis=dict(autorange="reversed"), hovermode="closest", bargap=0.35)
        wykres(fig, 640)
    with prawa:
        st.subheader("Błąd w zależności od godziny doby")
        p = prognozy.copy()
        p["godzina"] = p["czas_lokalny"].dt.hour
        fig = go.Figure()
        for kolumna, nazwa in ((nazwa_modelu, "Model ML"), ("Prognoza PSE", "Prognoza PSE")):
            ape = (100 * (p[kolumna] - p["rzeczywiste_mw"]).abs() / p["rzeczywiste_mw"]).groupby(p["godzina"]).mean()
            fig.add_scatter(x=ape.index, y=ape.values, mode="lines+markers", name=nazwa,
                            line=dict(color=KOLORY_SERII[nazwa], width=2), marker_size=6,
                            hovertemplate=f"{nazwa}: %{{y:.2f}}%<extra></extra>")
        fig.update_layout(xaxis_title="godzina doby", yaxis_title="MAPE [%]", xaxis_dtick=2)
        wykres(fig, 300)

        st.subheader("Błąd w kolejnych miesiącach 2026 r.")
        p["miesiac"] = p["czas_lokalny"].dt.to_period("M").dt.to_timestamp()
        fig = go.Figure()
        for kolumna, nazwa in ((nazwa_modelu, "Model ML"), ("Prognoza PSE", "Prognoza PSE")):
            ape = (100 * (p[kolumna] - p["rzeczywiste_mw"]).abs() / p["rzeczywiste_mw"]).groupby(p["miesiac"]).mean()
            fig.add_bar(x=ape.index, y=ape.values, name=nazwa, marker_color=KOLORY_SERII[nazwa],
                        hovertemplate=f"{nazwa}: %{{y:.2f}}%<extra></extra>")
        fig.update_layout(yaxis_title="MAPE [%]", barmode="group", xaxis_tickformat="%m.%Y", bargap=0.3)
        wykres(fig, 300)

    st.subheader("Walidacja krzyżowa (TimeSeriesSplit, 5 okresów po 90 dni w latach 2024–2025)")
    tabela_cv = cv.pivot_table(index="model", columns="okres_walidacji", values="mape_proc")
    tabela_cv["średnia"] = tabela_cv.mean(axis=1)
    st.dataframe(tabela_cv.sort_values("średnia").style.format(lambda v: liczba(v, 2)), width="stretch")
    st.caption("Wartości MAPE [%]. Każdy model uczony jest wyłącznie na danych sprzed okresu walidacji, "
               "co odwzorowuje rzeczywiste warunki prognozowania.")

# ---------------------------------------------------------------------------
with zakl_przebieg:
    dni = prognozy["czas_lokalny"].dt.date
    od, do = st.slider("Zakres dat", min_value=dni.min(), max_value=dni.max(),
                       value=(pd.Timestamp("2026-01-12").date(), pd.Timestamp("2026-01-25").date()),
                       format="DD.MM.YYYY", key="prognoza_zakres")
    okno = prognozy[(dni >= od) & (dni <= do)]
    fig = go.Figure()
    for kolumna, nazwa, szer in (("rzeczywiste_mw", "Rzeczywiste", 2.5), ("Prognoza PSE", "Prognoza PSE", 2),
                                 (nazwa_modelu, "Model ML", 2)):
        fig.add_scatter(x=okno["czas_lokalny"], y=okno[kolumna], mode="lines", name=nazwa,
                        line=dict(color=KOLORY_SERII[nazwa], width=szer),
                        hovertemplate=f"{nazwa}: %{{y:,.0f}} MW<extra></extra>")
    fig.update_layout(yaxis_title="zapotrzebowanie [MW]", xaxis_tickformat="%d.%m\n%H:%M")
    wykres(fig, 460)
    if len(okno):
        mape_m = 100 * ((okno[nazwa_modelu] - okno["rzeczywiste_mw"]).abs() / okno["rzeczywiste_mw"]).mean()
        mape_p = 100 * ((okno["Prognoza PSE"] - okno["rzeczywiste_mw"]).abs() / okno["rzeczywiste_mw"]).mean()
        st.caption(f"W wybranym okresie: MAPE modelu {liczba(mape_m, 2)}%, MAPE prognozy PSE {liczba(mape_p, 2)}%.")

    st.subheader("Rozkład błędów prognozy")
    fig = go.Figure()
    for kolumna, nazwa in ((nazwa_modelu, "Model ML"), ("Prognoza PSE", "Prognoza PSE")):
        fig.add_histogram(x=prognozy[kolumna] - prognozy["rzeczywiste_mw"], name=nazwa, nbinsx=80, opacity=0.6,
                          marker_color=KOLORY_SERII[nazwa])
    fig.update_layout(barmode="overlay", xaxis_title="błąd prognozy (prognoza − rzeczywiste) [MW]",
                      yaxis_title="liczba godzin", hovermode="closest")
    wykres(fig, 340)

# ---------------------------------------------------------------------------
with zakl_cechy:
    st.subheader(f"Ważność cech – {nazwa_modelu}")
    w = waznosc.sort_values("wzrost_mae_mw")
    fig = go.Figure(go.Bar(x=w["wzrost_mae_mw"], y=w["nazwa"], orientation="h", marker_color=AKCENT,
                           error_x=dict(type="data", array=w["odchylenie"], color=TUSZ_WYCISZONY, thickness=1),
                           hovertemplate="%{y}: +%{x:,.0f} MW<extra></extra>"))
    fig.update_layout(xaxis_title="wzrost MAE po losowym przemieszaniu cechy [MW]", hovermode="closest")
    wykres(fig, 480)
    wniosek("Ważność permutacyjna mierzy, o ile wzrasta błąd modelu, gdy wartości danej cechy zostaną losowo "
            "przemieszane. Największe znaczenie mają <b>cechy kalendarzowe</b> (dzień tygodnia, godzina) "
            "oraz <b>zapotrzebowanie z poprzednich dni</b>; spośród zmiennych pogodowych najważniejsza jest "
            "temperatura, a promieniowanie słoneczne odzwierciedla wpływ fotowoltaiki prosumenckiej, "
            "która obniża zapotrzebowanie widoczne w sieci.")

# ---------------------------------------------------------------------------
with zakl_symulacja:
    st.subheader("Wpływ zmiany temperatury na zapotrzebowanie")
    st.caption("Model produkcyjny oblicza prognozę dla wybranej doby przy temperaturze zmienionej o zadaną "
               "wartość względem rzeczywistej (pozostałe cechy bez zmian).")


    @st.cache_resource
    def model_produkcyjny():
        return joblib.load(MODELE / "model_prognozy.joblib")["model"]


    @st.cache_data
    def dane_z_cechami():
        return dodaj_cechy(zbior())

    k1, k2 = st.columns([1, 2])
    doba = k1.date_input("Doba", value=pd.Timestamp("2026-02-10").date(),
                         min_value=pd.Timestamp("2022-01-15").date(), max_value=pd.Timestamp("2026-09-30").date(),
                         format="DD.MM.YYYY")
    zmiana = k2.slider("Zmiana temperatury [°C]", -10.0, 10.0, -5.0, 0.5)

    dane = dane_z_cechami()
    dzien = dane[dane["data"] == pd.Timestamp(doba)].copy()
    zmieniony = dzien.copy()
    zmieniony["temperatura_c"] += zmiana
    zmieniony["temperatura_srednia_24h"] += zmiana
    zmieniony["hdd"] = (18 - zmieniony["temperatura_c"]).clip(lower=0)
    zmieniony["cdd"] = (zmieniony["temperatura_c"] - 22).clip(lower=0)
    model = model_produkcyjny()
    bazowa = model.predict(dzien[CECHY])
    symulacja = model.predict(zmieniony[CECHY])

    fig = go.Figure()
    fig.add_scatter(x=dzien["godzina"], y=dzien["zapotrzebowanie_mw"], name="Rzeczywiste", mode="lines",
                    line=dict(color=KOLORY_SERII["Rzeczywiste"], width=2.5))
    fig.add_scatter(x=dzien["godzina"], y=bazowa, name="Model – temperatura rzeczywista", mode="lines",
                    line=dict(color=NIEBIESKI, width=2))
    fig.add_scatter(x=dzien["godzina"], y=symulacja, name=f"Model – temperatura {zmiana:+.1f}°C", mode="lines",
                    line=dict(color=POMARANCZOWY, width=2))
    fig.update_layout(xaxis_title="godzina doby", yaxis_title="zapotrzebowanie [MW]", xaxis_dtick=2)
    wykres(fig, 400)
    roznica_energii = (symulacja - bazowa).sum()
    kafle([
        ("Średnia temperatura doby", f"{liczba(dzien['temperatura_c'].mean(), 1)}°C",
         f"w symulacji {liczba(dzien['temperatura_c'].mean() + zmiana, 1)}°C"),
        ("Zmiana zużycia energii w dobie", f"{'+' if roznica_energii >= 0 else '−'}{liczba(abs(roznica_energii))} MWh",
         f"{liczba(100 * roznica_energii / bazowa.sum(), 2)}% względem prognozy bazowej"),
        ("Zmiana szczytu", f"{liczba(symulacja.max() - bazowa.max())} MW",
         f"szczyt w symulacji: {liczba(symulacja.max())} MW"),
    ])
    st.caption("Symulacja ma charakter poglądowy: modele drzewiaste nie ekstrapolują poza zakres temperatur "
               "obserwowanych w danych uczących.")
