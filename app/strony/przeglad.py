import plotly.graph_objects as go
import streamlit as st

from wspolne import (KOLORY_MIKSU, filtr_okresu, kafle, liczba, miks_grupy, naglowek, wniosek, wykres, zbior)

naglowek("Analiza danych", "Przegląd Krajowego Systemu Elektroenergetycznego",
         "Zapotrzebowanie, struktura wytwarzania i udział odnawialnych źródeł energii w wybranym okresie.")

dane = filtr_okresu(zbior(), "przeglad")
if dane.empty:
    st.warning("Brak danych dla wybranych filtrów.")
    st.stop()

miks = miks_grupy()
miks = miks[miks["czas_utc"].isin(dane.index)]

kafle([
    ("Średnie zapotrzebowanie", f"{liczba(dane['zapotrzebowanie_mw'].mean())} MW",
     f"maksimum {liczba(dane['zapotrzebowanie_mw'].max())} MW"),
    ("Udział OZE w generacji", f"{liczba(dane['udzial_oze_proc'].mean(), 1)}%",
     f"najwyższy godzinowy {liczba(dane['udzial_oze_proc'].max(), 0)}%"),
    ("Udział węgla w generacji", f"{liczba(dane['udzial_wegla_proc'].mean(), 1)}%", "kamienny i brunatny"),
    ("Średnia cena RDN", f"{liczba(dane['cena_pln_mwh'].mean())} PLN/MWh", "fixing dla obszaru PL"),
    ("Godziny z ceną ujemną", liczba((dane["cena_pln_mwh"] < 0).sum()), "w wybranym okresie"),
])

st.write("")
st.subheader("Struktura wytwarzania energii elektrycznej")
krok = st.segmented_control("Agregacja", ["tydzień", "miesiąc"], default="miesiąc", key="przeglad_krok")
regula = {"tydzień": "W-MON", "miesiąc": "MS"}[krok or "miesiąc"]

szereg = (miks.set_index("czas_lokalny").groupby("grupa")["generacja_mw"].resample(regula).mean()
          .reset_index())
fig = go.Figure()
for grupa, kolor in KOLORY_MIKSU.items():
    czesc = szereg[szereg["grupa"] == grupa]
    if czesc.empty:
        continue
    fig.add_scatter(x=czesc["czas_lokalny"], y=czesc["generacja_mw"], name=grupa, stackgroup="miks",
                    mode="lines", line=dict(width=0.5, color=kolor), fillcolor=kolor,
                    hovertemplate=f"{grupa}: %{{y:,.0f}} MW<extra></extra>")
fig.update_layout(yaxis_title="średnia moc [MW]", hovermode="x unified")
wykres(fig, 440)

lewa, prawa = st.columns(2, gap="large")
with lewa:
    st.subheader("Udział grup źródeł w kolejnych latach")
    roczny = miks.assign(rok=miks["czas_lokalny"].dt.year).groupby(["rok", "grupa"])["generacja_mw"].sum()
    roczny = (roczny / roczny.groupby("rok").transform("sum") * 100).reset_index()
    fig = go.Figure()
    for grupa, kolor in KOLORY_MIKSU.items():
        czesc = roczny[roczny["grupa"] == grupa]
        fig.add_bar(x=czesc["rok"].astype(str), y=czesc["generacja_mw"], name=grupa, marker_color=kolor,
                    marker_line=dict(color="#fcfcfb", width=1),
                    hovertemplate=f"{grupa}: %{{y:.1f}}%<extra></extra>")
    fig.update_layout(barmode="stack", yaxis_title="udział w generacji [%]", hovermode="x unified",
                      bargap=0.35)
    wykres(fig, 420)

with prawa:
    st.subheader("Przeciętny profil dobowy wytwarzania")
    miks["godzina"] = miks["czas_lokalny"].dt.hour
    profil = miks.groupby(["godzina", "grupa"])["generacja_mw"].mean().reset_index()
    fig = go.Figure()
    for grupa, kolor in KOLORY_MIKSU.items():
        czesc = profil[profil["grupa"] == grupa]
        fig.add_scatter(x=czesc["godzina"], y=czesc["generacja_mw"], name=grupa, stackgroup="profil",
                        mode="lines", line=dict(width=0.5, color=kolor), fillcolor=kolor,
                        hovertemplate=f"{grupa}: %{{y:,.0f}} MW<extra></extra>")
    zap = dane.groupby("godzina")["zapotrzebowanie_mw"].mean()
    fig.add_scatter(x=zap.index, y=zap.values, name="Zapotrzebowanie", mode="lines",
                    line=dict(color="#16232B", width=2), hovertemplate="Zapotrzebowanie: %{y:,.0f} MW<extra></extra>")
    fig.update_layout(xaxis_title="godzina doby", yaxis_title="średnia moc [MW]", xaxis_dtick=2)
    wykres(fig, 420)

poludnie = dane[dane["godzina"].between(11, 14)]
nadwyzka = (poludnie["generacja_calkowita_mw"] > poludnie["zapotrzebowanie_mw"]).mean() * 100
wniosek(f"W godzinach 11–15 fotowoltaika dostarcza w wybranym okresie średnio "
        f"<b>{liczba(poludnie['generacja_pv_mw'].mean())} MW</b>. W <b>{liczba(nadwyzka, 0)}%</b> tych godzin "
        "generacja krajowa przewyższała zapotrzebowanie – różnica odpowiada saldu wymiany międzysystemowej "
        "(eksport energii).")
