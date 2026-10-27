from datetime import datetime

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src.prognoza_na_zywo import prognozuj
from wspolne import KOLORY_SERII, kafle, liczba, naglowek, wniosek, wykres


@st.cache_data(ttl=1800, show_spinner="Pobieranie bieżących danych z PSE i prognozy pogody...")
def biezaca_prognoza():
    tabela, nazwa, dzien = prognozuj()
    return tabela, nazwa, dzien, datetime.now()


naglowek("Prognozowanie · dane bieżące", "Prognoza zapotrzebowania na jutro",
         "Model pobiera aktualne dane PSE oraz prognozę pogody Open-Meteo dla 10 lokalizacji i wyznacza "
         "godzinowe zapotrzebowanie na kolejną dobę. Wynik porównywany jest z oficjalną prognozą PSE.")

if st.button("Odśwież dane", icon=":material/refresh:"):
    biezaca_prognoza.clear()

try:
    tabela, nazwa_modelu, dzien, czas_pobrania = biezaca_prognoza()
except Exception as blad:  # brak połączenia lub zmiana API
    st.error(f"Nie udało się pobrać bieżących danych: {blad}")
    st.stop()

jutro = tabela[tabela["czas_lokalny"].dt.date == dzien]
historia = tabela[tabela["czas_lokalny"].dt.date < dzien]
st.caption(f"Doba prognozy: **{dzien:%d.%m.%Y}** · model: {nazwa_modelu} · dane pobrane "
           f"{czas_pobrania:%d.%m.%Y, %H:%M}")

szczyt_m = jutro["prognoza_model_mw"].max()
szczyt_p = jutro["prognoza_pse_mw"].max()
energia_m = jutro["prognoza_model_mw"].sum()
energia_p = jutro["prognoza_pse_mw"].sum()
kafle([
    ("Szczyt – model ML", f"{liczba(szczyt_m)} MW",
     f"godz. {int(jutro.loc[jutro['prognoza_model_mw'].idxmax(), 'czas_lokalny'].hour)}:00"),
    ("Szczyt – prognoza PSE", f"{liczba(szczyt_p)} MW" if pd.notna(szczyt_p) else "brak",
     "publikowana ok. 9:00 dnia poprzedniego"),
    ("Energia w dobie – model", f"{liczba(energia_m / 1000, 1)} GWh",
     f"różnica vs PSE: {liczba(100 * (energia_m / energia_p - 1), 2)}%" if energia_p else ""),
    ("Średnia temperatura (prognoza)", f"{liczba(jutro['temperatura_c'].mean(), 1)}°C",
     f"typ dnia: {jutro['typ_dnia'].iloc[0]}"),
])

st.write("")
st.subheader("Ostatnie dwa tygodnie i prognoza na jutro")
fig = go.Figure()
fig.add_vrect(x0=jutro["czas_lokalny"].min(), x1=jutro["czas_lokalny"].max(), fillcolor="#E3EEF3",
              line_width=0, layer="below")
fig.add_annotation(x=jutro["czas_lokalny"].min(), y=1, yref="paper", text="jutro", showarrow=False,
                   xanchor="left", yanchor="bottom", font_color="#0B4F6C")
for kolumna, nazwa, szer in (("zapotrzebowanie_mw", "Rzeczywiste", 2.5), ("prognoza_pse_mw", "Prognoza PSE", 2),
                             ("prognoza_model_mw", "Model ML", 2)):
    fig.add_scatter(x=tabela["czas_lokalny"], y=tabela[kolumna], mode="lines", name=nazwa,
                    line=dict(color=KOLORY_SERII[nazwa], width=szer),
                    hovertemplate=f"{nazwa}: %{{y:,.0f}} MW<extra></extra>")
fig.update_layout(yaxis_title="zapotrzebowanie [MW]", xaxis_tickformat="%d.%m")
wykres(fig, 460)

lewa, prawa = st.columns([3, 2], gap="large")
with lewa:
    st.subheader("Trafność w ostatnich dniach")
    znane = historia.dropna(subset=["zapotrzebowanie_mw", "prognoza_model_mw", "prognoza_pse_mw"]).copy()
    znane["data"] = znane["czas_lokalny"].dt.date
    fig = go.Figure()
    for kolumna, nazwa in (("prognoza_model_mw", "Model ML"), ("prognoza_pse_mw", "Prognoza PSE")):
        ape = (100 * (znane[kolumna] - znane["zapotrzebowanie_mw"]).abs()
               / znane["zapotrzebowanie_mw"]).groupby(znane["data"]).mean()
        fig.add_bar(x=ape.index, y=ape.values, name=nazwa, marker_color=KOLORY_SERII[nazwa],
                    hovertemplate=f"{nazwa}: %{{y:.2f}}%<extra></extra>")
    fig.update_layout(barmode="group", yaxis_title="MAPE doby [%]", xaxis_tickformat="%d.%m", bargap=0.3)
    wykres(fig, 340)
    if len(znane):
        mape_m = 100 * ((znane["prognoza_model_mw"] - znane["zapotrzebowanie_mw"]).abs() / znane["zapotrzebowanie_mw"]).mean()
        mape_p = 100 * ((znane["prognoza_pse_mw"] - znane["zapotrzebowanie_mw"]).abs() / znane["zapotrzebowanie_mw"]).mean()
        wniosek(f"W ostatnich {znane['data'].nunique()} dobach, dla których znane jest już zapotrzebowanie "
                f"rzeczywiste, MAPE modelu wyniosło <b>{liczba(mape_m, 2)}%</b>, a prognozy PSE "
                f"<b>{liczba(mape_p, 2)}%</b>.")

with prawa:
    st.subheader(f"Prognoza godzinowa na {dzien:%d.%m.%Y}")
    tab = pd.DataFrame({
        "Godzina": jutro["czas_lokalny"].dt.strftime("%H:00"),
        "Model ML [MW]": jutro["prognoza_model_mw"].round(0),
        "PSE [MW]": jutro["prognoza_pse_mw"].round(0),
        "Różnica [MW]": (jutro["prognoza_model_mw"] - jutro["prognoza_pse_mw"]).round(0),
        "Temperatura [°C]": jutro["temperatura_c"].round(1),
    })
    st.dataframe(tab, hide_index=True, width="stretch", height=420)
    st.download_button("Pobierz prognozę (CSV)", tab.to_csv(index=False).encode("utf-8"),
                       file_name=f"prognoza_{dzien:%Y%m%d}.csv", mime="text/csv")

st.caption("Zapotrzebowanie rzeczywiste publikowane jest przez PSE z ok. jednodniowym opóźnieniem, dlatego "
           "model korzysta z opóźnień co najmniej 48-godzinnych. Prognoza pogody pochodzi z modeli numerycznych "
           "Open-Meteo, więc jej błąd przenosi się na prognozę zapotrzebowania.")
