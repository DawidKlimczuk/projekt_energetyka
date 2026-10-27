import plotly.graph_objects as go
import streamlit as st

from src.analiza import (efekt_kalendarza, korelacje_pogoda_oze, krzywa_mocy, krzywa_temperaturowa,
                         mapa_godzina_dzien)
from wspolne import (AKCENT, DNI, NIEBIESKI, POMARANCZOWY, SKALA_SEKWENCYJNA, TUSZ_WYCISZONY,
                     filtr_okresu, liczba, lokalizacje, naglowek, pogoda_stacje, wniosek, wykres, zbior)

# kolory kolejnych lat – skala porządkowa jednej barwy (od jasnego do ciemnego)
KOLORY_LAT = {2022: "#86b6ef", 2023: "#5598e7", 2024: "#2a78d6", 2025: "#1c5cab", 2026: "#0d366b"}

naglowek("Analiza danych · pytania P1 i P2", "Pogoda a system elektroenergetyczny",
         "Wpływ temperatury i kalendarza na zapotrzebowanie oraz zależność generacji z wiatru i słońca od pogody.")

dane = filtr_okresu(zbior(), "pogoda")
if dane.empty:
    st.warning("Brak danych dla wybranych filtrów.")
    st.stop()

zakladka_t, zakladka_oze, zakladka_mapa = st.tabs(
    ["Temperatura i kalendarz (P1)", "Wiatr i słońce (P2)", "Mapa warunków pogodowych"])

# ---------------------------------------------------------------------------
with zakladka_t:
    robocze, dopasowanie, t_min = krzywa_temperaturowa(dane)
    lewa, prawa = st.columns([3, 2], gap="large")
    with lewa:
        st.subheader("Zapotrzebowanie a temperatura (dni robocze)")
        fig = go.Figure()
        fig.add_scatter(x=robocze["temperatura_c"], y=robocze["zapotrzebowanie_mw"], mode="markers",
                        name="doba robocza", marker=dict(color=NIEBIESKI, size=6, opacity=0.35),
                        customdata=robocze.index.strftime("%d.%m.%Y"),
                        hovertemplate="%{customdata}<br>%{x:.1f}°C · %{y:,.0f} MW<extra></extra>")
        fig.add_scatter(x=dopasowanie["temperatura_c"], y=dopasowanie["zapotrzebowanie_mw"], mode="lines",
                        name="dopasowanie wielomianowe", line=dict(color=POMARANCZOWY, width=2.5),
                        hoverinfo="skip")
        fig.add_vline(x=t_min, line=dict(color=TUSZ_WYCISZONY, width=1))
        fig.add_annotation(x=t_min, y=1, yref="paper", text=f"minimum: {liczba(t_min, 1)}°C",
                           showarrow=False, yanchor="bottom", font_color="#52514e")
        fig.update_layout(xaxis_title="średnia temperatura doby [°C]", yaxis_title="średnie zapotrzebowanie [MW]",
                          hovermode="closest")
        wykres(fig, 430)
    with prawa:
        st.subheader("Efekt kalendarza")
        kal = efekt_kalendarza(dane).drop(index="roboczy", errors="ignore").reset_index()
        kal["spadek"] = -kal["zmiana_vs_roboczy_proc"]
        fig = go.Figure(go.Bar(
            x=kal["spadek"], y=kal["typ_dnia"], orientation="h", marker_color=AKCENT,
            text=[f"−{liczba(v, 1)}%" for v in kal["spadek"]], textposition="outside", cliponaxis=False,
            hovertemplate="%{y}: zapotrzebowanie niższe o %{x:.1f}% niż w dzień roboczy<extra></extra>"))
        fig.update_layout(xaxis=dict(title="spadek zapotrzebowania względem dnia roboczego [%]",
                                     range=[0, kal["spadek"].max() * 1.25]),
                          yaxis=dict(autorange="reversed"), hovermode="closest", bargap=0.45)
        wykres(fig, 430)

    st.subheader("Przeciętne zapotrzebowanie: godzina doby × dzień tygodnia")
    mapa = mapa_godzina_dzien(dane)
    fig = go.Figure(go.Heatmap(z=mapa.values, x=[DNI[d] for d in mapa.columns], y=mapa.index,
                               colorscale=SKALA_SEKWENCYJNA, colorbar=dict(title="MW"), xgap=2, ygap=2,
                               hovertemplate="%{x}, godz. %{y}:00<br>%{z:,.0f} MW<extra></extra>"))
    fig.update_layout(yaxis=dict(autorange="reversed", dtick=2, title="godzina"), hovermode="closest")
    wykres(fig, 480)
    wniosek(f"Zapotrzebowanie ma kształt litery „U” względem temperatury z minimum przy około "
            f"<b>{liczba(t_min, 1)}°C</b>. Poniżej tej temperatury rośnie wskutek ogrzewania, powyżej – wskutek "
            "chłodzenia, przy czym efekt mrozu jest znacznie silniejszy niż efekt upałów.")

# ---------------------------------------------------------------------------
with zakladka_oze:
    lewa, prawa = st.columns(2, gap="large")
    for kolumna_ui, x, y, szer, tytul, os_x in (
            (lewa, "wiatr_100m_ms", "generacja_wiatr_mw", 1, "Empiryczna krzywa mocy farm wiatrowych",
             "prędkość wiatru na wys. 100 m [m/s]"),
            (prawa, "promieniowanie_wm2", "generacja_pv_mw", 50, "Generacja PV a promieniowanie słoneczne",
             "promieniowanie krótkofalowe [W/m²]")):
        with kolumna_ui:
            st.subheader(tytul)
            krzywa = krzywa_mocy(dane, x, y, szer)
            fig = go.Figure()
            for rok, czesc in krzywa.groupby("rok"):
                fig.add_scatter(x=czesc["przedzial"], y=czesc["srednia"], mode="lines+markers", name=str(rok),
                                line=dict(color=KOLORY_LAT.get(rok, NIEBIESKI), width=2), marker_size=5,
                                hovertemplate=f"{rok}: %{{y:,.0f}} MW<extra></extra>")
            fig.update_layout(xaxis_title=os_x, yaxis_title="średnia generacja [MW]")
            wykres(fig, 400)

    roczne = dane.groupby("rok")[["generacja_wiatr_mw", "generacja_pv_mw"]].max()
    wniosek("Krzywe przesuwają się w górę z roku na rok – przy tych samych warunkach pogodowych produkcja jest "
            "wyższa, co odzwierciedla przyrost mocy zainstalowanej. Maksymalna godzinowa generacja PV wzrosła "
            f"z <b>{liczba(roczne['generacja_pv_mw'].iloc[0])} MW</b> ({roczne.index[0]}) do "
            f"<b>{liczba(roczne['generacja_pv_mw'].iloc[-1])} MW</b> ({roczne.index[-1]}).")

    st.subheader("Siła zależności")
    korelacje = korelacje_pogoda_oze(dane)
    st.dataframe(korelacje.rename(columns={"zaleznosc": "Zależność", "pearson": "r Pearsona",
                                           "spearman": "ρ Spearmana", "n": "Liczba godzin"}),
                 hide_index=True, width="stretch",
                 column_config={"r Pearsona": st.column_config.NumberColumn(format="%.3f"),
                                "ρ Spearmana": st.column_config.NumberColumn(format="%.3f")})
    st.caption("Zależność generacji wiatrowej od prędkości wiatru jest nieliniowa (krzywa mocy turbiny ma "
               "kształt litery S), dlatego współczynnik Spearmana lepiej opisuje jej siłę.")

# ---------------------------------------------------------------------------
with zakladka_mapa:
    stacje = pogoda_stacje()
    stacje = stacje[stacje["czas_utc"].isin(dane.index)]
    zmienne = {"temperatura_c": ("Temperatura", "°C"), "wiatr_100m_ms": ("Prędkość wiatru (100 m)", "m/s"),
               "promieniowanie_wm2": ("Promieniowanie słoneczne", "W/m²"), "zachmurzenie_proc": ("Zachmurzenie", "%")}
    wybor = st.segmented_control("Zmienna", list(zmienne), default="temperatura_c",
                                 format_func=lambda k: zmienne[k][0], key="mapa_zmienna") or "temperatura_c"
    nazwa, jednostka = zmienne[wybor]
    srednie = stacje.groupby("id_stacji")[wybor].mean().rename("wartosc")
    punkty = lokalizacje().merge(srednie, left_on="id", right_index=True)

    fig = go.Figure(go.Scattermap(
        lat=punkty["lat"], lon=punkty["lon"], mode="markers+text",
        marker=dict(size=26, color=punkty["wartosc"], colorscale=SKALA_SEKWENCYJNA, showscale=True,
                    colorbar=dict(title=jednostka)),
        text=[f"{n}<br>{liczba(v, 1)}" for n, v in zip(punkty["nazwa"], punkty["wartosc"])],
        textposition="top center", textfont=dict(size=12, color="#16232B"),
        hovertemplate="%{customdata}<extra></extra>",
        customdata=[f"{n} ({w})<br>{nazwa}: {liczba(v, 1)} {jednostka}"
                    for n, w, v in zip(punkty["nazwa"], punkty["wojewodztwo"], punkty["wartosc"])]))
    fig.update_layout(map=dict(style="carto-positron", center=dict(lat=52.0, lon=19.3), zoom=5.1),
                      margin=dict(l=0, r=0, t=0, b=0))
    wykres(fig, 560)
    st.caption(f"Średnia wartość zmiennej „{nazwa}” w wybranym okresie dla 10 lokalizacji (Open-Meteo, reanaliza ERA5). "
               "Wartości ogólnopolskie w analizie to średnie ważone: temperatura – liczbą ludności województwa, "
               "prędkość wiatru – szacunkowym rozmieszczeniem farm wiatrowych.")
