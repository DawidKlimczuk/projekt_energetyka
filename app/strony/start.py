import plotly.graph_objects as go
import streamlit as st

from src.analiza import weryfikuj_hipotezy
from wspolne import (AKCENT, NIEBIESKI, kafle, liczba, metryki_modeli, naglowek, wykres, zbior)


@st.cache_data(show_spinner="Weryfikacja hipotez...")
def hipotezy():
    return weryfikuj_hipotezy(zbior(), metryki_modeli())


dane = zbior()
metryki = metryki_modeli()
najlepszy = metryki.drop(index=["Prognoza PSE", "Prognoza naiwna (tydzień wcześniej)"])["mape_proc"].idxmin()

naglowek("Metody analizy, przetwarzania i wizualizacji danych · WSB",
         "Pogoda, OZE i cena prądu",
         "Analiza wpływu warunków pogodowych na miks energetyczny, zapotrzebowanie i ceny energii elektrycznej "
         "w Polsce oraz prognoza zapotrzebowania KSE z wykorzystaniem uczenia maszynowego.")

kafle([
    ("Obserwacje godzinowe", liczba(len(dane)), "01.01.2022 – 30.09.2026"),
    ("Źródła danych", "5", "PSE · ENTSO-E · RDN · Open-Meteo · kalendarz"),
    ("Udział OZE w generacji", f"{liczba(dane['udzial_oze_proc'].mean(), 1)}%", "średnia z całego okresu"),
    ("MAPE modelu ML (2026)", f"{liczba(metryki.loc[najlepszy, 'mape_proc'], 2)}%", najlepszy),
    ("MAPE prognozy PSE (2026)", f"{liczba(metryki.loc['Prognoza PSE', 'mape_proc'], 2)}%", "oficjalna prognoza operatora"),
])

st.write("")
lewa, prawa = st.columns([3, 2], gap="large")

with lewa:
    st.subheader("Weryfikacja hipotez badawczych")
    st.caption("Wyniki obliczane bezpośrednio z danych przy każdym uruchomieniu aplikacji.")
    klasy = {"potwierdzona": "potwierdzona", "częściowo potwierdzona": "czesciowo", "odrzucona": "odrzucona"}
    ikony = {"potwierdzona": "✔", "częściowo potwierdzona": "◐", "odrzucona": "✖"}
    for h in hipotezy():
        st.markdown(
            f'<div class="hipoteza"><b>{h["nr"]}.</b> {h["hipoteza"]}<br>'
            f'<span class="status {klasy[h["werdykt"]]}">{ikony[h["werdykt"]]} Hipoteza {h["werdykt"]}</span>'
            f'<div style="color:#56666F;margin-top:0.3rem">{h["wynik"]}</div></div>',
            unsafe_allow_html=True)

with prawa:
    st.subheader("Transformacja miksu")
    miesieczne = dane.set_index("czas_lokalny")["udzial_oze_proc"].resample("MS").mean()
    fig = go.Figure()
    fig.add_scatter(x=miesieczne.index, y=miesieczne.values, mode="lines", name="Udział OZE (średnia miesięczna)",
                    line=dict(color=NIEBIESKI, width=2),
                    hovertemplate="%{x|%m.%Y}: %{y:.1f}%<extra></extra>")
    fig.update_layout(yaxis_title="udział OZE w generacji [%]", showlegend=False, hovermode="closest",
                      title=dict(text="Miesięczny udział OZE w generacji energii", font_size=14))
    wykres(fig, 300)

    st.subheader("Przepływ danych")
    etapy = [
        ("1. Pobranie", "API PSE, archiwum CSV PSE, energy-charts / ENTSO-E, NBP, Open-Meteo"),
        ("2. Integracja", "UTC, agregacja 15 min → 1 h, średnie ważone pogody, kalendarz świąt"),
        ("3. Analiza", "statystyki, korelacje, krzywe mocy, klasteryzacja K-means"),
        ("4. Modelowanie", "Ridge, Random Forest, HistGradientBoosting, walidacja chronologiczna"),
        ("5. Prezentacja", "aplikacja Streamlit oraz raport Power BI (schemat gwiazdy)"),
    ]
    for tytul, opis in etapy:
        st.markdown(f'<div style="border-left:3px solid {AKCENT};padding:0.15rem 0 0.15rem 0.8rem;'
                    f'margin-bottom:0.5rem"><b>{tytul}</b><br><span style="color:#56666F">{opis}</span></div>',
                    unsafe_allow_html=True)
