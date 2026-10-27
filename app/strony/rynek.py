import plotly.graph_objects as go
import streamlit as st

from src.analiza import ceny_ujemne, cena_wg_udzialu_oze, rozpietosc_dobowa_cen
from wspolne import (AKCENT, MIESIACE, NIEBIESKI, SKALA_ROZBIEZNA, TUSZ_WYCISZONY, filtr_okresu, kafle,
                     liczba, naglowek, wniosek, wykres, zbior)

naglowek("Analiza danych · pytanie P3", "Rynek energii",
         "Ceny Rynku Dnia Następnego a generacja z OZE: efekt merit order, ceny ujemne i dobowa zmienność cen.")

dane = filtr_okresu(zbior(), "rynek")
if dane.empty:
    st.warning("Brak danych dla wybranych filtrów.")
    st.stop()

doby = rozpietosc_dobowa_cen(dane)
kafle([
    ("Średnia cena", f"{liczba(dane['cena_pln_mwh'].mean())} PLN/MWh", "średnia arytmetyczna godzin"),
    ("Cena minimalna", f"{liczba(dane['cena_pln_mwh'].min())} PLN/MWh",
     dane.loc[dane["cena_pln_mwh"].idxmin(), "czas_lokalny"].strftime("%d.%m.%Y, godz. %H:00")),
    ("Cena maksymalna", f"{liczba(dane['cena_pln_mwh'].max())} PLN/MWh",
     dane.loc[dane["cena_pln_mwh"].idxmax(), "czas_lokalny"].strftime("%d.%m.%Y, godz. %H:00")),
    ("Godziny z ceną ujemną", liczba((dane["cena_pln_mwh"] < 0).sum()),
     f"{liczba(100 * (dane['cena_pln_mwh'] < 0).mean(), 2)}% wszystkich godzin"),
    ("Średnia rozpiętość dobowa", f"{liczba(doby['rozpietosc'].mean())} PLN/MWh", "maksimum − minimum w dobie"),
])

st.write("")
lewa, prawa = st.columns(2, gap="large")
with lewa:
    st.subheader("Cena energii a udział OZE (efekt merit order)")
    tabela = cena_wg_udzialu_oze(dane)
    fig = go.Figure()
    fig.add_bar(x=tabela["etykieta"], y=tabela["srednia"], name="średnia cena", marker_color=AKCENT,
                customdata=tabela[["q10", "q90", "liczba"]],
                hovertemplate="udział OZE %{x}<br>średnia: %{y:,.0f} PLN/MWh<br>"
                              "10.–90. percentyl: %{customdata[0]:,.0f} – %{customdata[1]:,.0f}<br>"
                              "godzin: %{customdata[2]:,}<extra></extra>",
                error_y=dict(type="data", symmetric=False, array=tabela["q90"] - tabela["srednia"],
                             arrayminus=tabela["srednia"] - tabela["q10"], color=TUSZ_WYCISZONY, thickness=1))
    fig.update_layout(xaxis_title="udział OZE w generacji", yaxis_title="cena [PLN/MWh]",
                      hovermode="closest", showlegend=False, bargap=0.3)
    wykres(fig, 420)
    st.caption("Słupki – średnia cena; wąsy – przedział od 10. do 90. percentyla cen w danej grupie godzin.")

with prawa:
    st.subheader("Średnia cena: godzina doby × miesiąc")
    mapa = dane.pivot_table(index="godzina", columns="miesiac", values="cena_pln_mwh", aggfunc="mean")
    srodek = dane["cena_pln_mwh"].mean()
    fig = go.Figure(go.Heatmap(
        z=mapa.values, x=[MIESIACE[m - 1] for m in mapa.columns], y=mapa.index,
        colorscale=SKALA_ROZBIEZNA, zmid=srodek, xgap=2, ygap=2, colorbar=dict(title="PLN/MWh"),
        hovertemplate="%{x}, godz. %{y}:00<br>%{z:,.0f} PLN/MWh<extra></extra>"))
    fig.update_layout(yaxis=dict(autorange="reversed", dtick=2, title="godzina"), hovermode="closest")
    wykres(fig, 420)
    st.caption(f"Skala rozbieżna: kolor neutralny odpowiada średniej cenie w okresie ({liczba(srodek)} PLN/MWh), "
               "niebieski – cenom niższym, czerwony – wyższym.")

st.subheader("Ceny ujemne")
roczne, warunki, typ_dnia = ceny_ujemne(dane)
lewa, prawa = st.columns([2, 3], gap="large")
with lewa:
    fig = go.Figure(go.Bar(x=roczne.index.astype(str), y=roczne["godziny_z_cena_ujemna"], marker_color=NIEBIESKI,
                           text=roczne["godziny_z_cena_ujemna"].astype(int), textposition="outside",
                           hovertemplate="%{x}: %{y} godzin<extra></extra>"))
    fig.update_layout(yaxis_title="liczba godzin z ceną < 0", hovermode="closest", bargap=0.4,
                      title=dict(text="Liczba godzin z ceną ujemną w kolejnych latach", font_size=14))
    wykres(fig, 360)
with prawa:
    if (dane["cena_pln_mwh"] < 0).any():
        porownanie = warunki.copy()
        porownanie.index = ["Udział OZE [%]", "Generacja PV [MW]", "Generacja wiatrowa [MW]",
                            "Zapotrzebowanie [MW]", "Promieniowanie [W/m²]", "Prędkość wiatru [m/s]"]
        st.markdown("**Warunki w godzinach z ceną ujemną (średnie)**")
        st.dataframe(porownanie.style.format(lambda v: liczba(v, 1)), width="stretch")
        udzial_wolnych = typ_dnia.drop("roboczy", errors="ignore").sum()
        wniosek(f"<b>{liczba(udzial_wolnych, 0)}%</b> godzin z ceną ujemną przypada na weekendy, święta i dni "
                "pomostowe. Ceny ujemne pojawiają się przy wysokiej generacji PV i niskim zapotrzebowaniu, "
                "gdy podaż energii przekracza możliwości jej zagospodarowania w systemie.")
    else:
        st.info("W wybranym okresie nie wystąpiły ceny ujemne.")

st.subheader("Dobowa rozpiętość cen – potencjał magazynów energii")
fig = go.Figure()
for rok, czesc in doby.groupby("rok"):
    fig.add_box(y=czesc["rozpietosc"], name=str(rok), marker_color=AKCENT, line_width=1.5,
                boxpoints=False, hovertemplate="%{y:,.0f} PLN/MWh<extra></extra>")
fig.update_layout(yaxis_title="cena maks. − cena min. w dobie [PLN/MWh]", showlegend=False, hovermode="closest")
wykres(fig, 380)
wniosek("Rozpiętość dobowa określa, ile może zarobić magazyn energii ładowany w godzinach najtańszych "
        "i rozładowywany w najdroższych. Jest to jeden z argumentów za inwestycjami w magazyny energii "
        "wskazanych w koncepcji projektu (rozdz. 8).")
