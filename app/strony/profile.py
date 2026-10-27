import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from wspolne import (DNI, MORSKI, NIEBIESKI, POMARANCZOWY, ZOLTY, liczba, naglowek, wniosek, wykres,
                     zapytanie)

# cztery klastry – pierwsze cztery sloty palety kategorycznej
KOLORY_KLASTROW = [NIEBIESKI, POMARANCZOWY, MORSKI, ZOLTY]

naglowek("Analiza danych · pytanie P5", "Typowe profile dobowe",
         "Klasteryzacja metodą k-średnich (K-means) dobowych przebiegów zapotrzebowania i cen "
         "(każda doba = wektor 24 wartości).")

wybor = st.segmented_control("Profile", ["zapotrzebowanie", "ceny"], default="zapotrzebowanie",
                             format_func=lambda k: {"zapotrzebowanie": "Zapotrzebowanie na moc",
                                                    "ceny": "Ceny energii"}[k], key="profile_wybor")
wybor = wybor or "zapotrzebowanie"
jednostka = "MW" if wybor == "zapotrzebowanie" else "PLN/MWh"

doby = zapytanie("SELECT * FROM v_klastry_doby WHERE zmienna = ? ORDER BY data", (wybor,))
opis = zapytanie("SELECT * FROM klastry_opis WHERE zmienna = ? ORDER BY klaster", (wybor,)).set_index("klaster")
profile = zapytanie("SELECT * FROM klastry_profile WHERE zmienna = ? ORDER BY klaster, godzina", (wybor,))
sylwetki = zapytanie("SELECT * FROM klastry_sylwetka WHERE zmienna = ? ORDER BY k", (wybor,))
kolor = {k: KOLORY_KLASTROW[i % 4] for i, k in enumerate(opis.index)}

lewa, prawa = st.columns([1, 1], gap="large")
with lewa:
    st.subheader("Profile przeciętne klastrów")
    fig = go.Figure()
    for k, wiersz in opis.iterrows():
        czesc = profile[profile["klaster"] == k]
        fig.add_scatter(x=czesc["godzina"], y=czesc["wartosc"], mode="lines", name=wiersz["nazwa"],
                        line=dict(color=kolor[k], width=2.5),
                        hovertemplate=f"{wiersz['nazwa']}: %{{y:,.0f}} {jednostka}<extra></extra>")
    fig.update_layout(xaxis_title="godzina doby", yaxis_title=f"średnia wartość [{jednostka}]", xaxis_dtick=2)
    wykres(fig, 430)

with prawa:
    st.subheader("Charakterystyka klastrów")
    sklad = pd.crosstab(doby["klaster"], doby["typ_dnia"], normalize="index").mul(100)
    tabela = pd.DataFrame({
        "Klaster": opis["nazwa"],
        "Liczba dób": opis["liczba_dob"],
        f"Średni poziom [{jednostka}]": opis["sredni_poziom"].map(liczba),
        "Dni wolne [%]": (100 * opis["udzial_dni_wolnych"]).map(liczba),
    })
    st.dataframe(tabela, hide_index=True, width="stretch")
    sezony = pd.crosstab(doby["klaster"].map(opis["nazwa"]), doby["sezon"], normalize="index").mul(100).round(0)
    st.markdown("**Udział sezonów w klastrach [%]**")
    st.dataframe(sezony[[s for s in ["zima", "wiosna", "lato", "jesień"] if s in sezony]],
                 width="stretch")

st.subheader("Kalendarz przynależności dób do klastrów")
rok = st.segmented_control("Rok", sorted(doby["data"].dt.year.unique()), default=2025, key="profile_rok") or 2025
rok_doby = doby[doby["data"].dt.year == rok].copy()
rok_doby["tydzien"] = rok_doby["data"].dt.isocalendar().week.astype(int)
# dni z przełomu roku należące do tygodnia ISO sąsiedniego roku
rok_doby.loc[(rok_doby["data"].dt.month == 1) & (rok_doby["tydzien"] > 50), "tydzien"] = 0
rok_doby.loc[(rok_doby["data"].dt.month == 12) & (rok_doby["tydzien"] == 1), "tydzien"] = 53
rok_doby["dzien"] = rok_doby["data"].dt.dayofweek
rok_doby["opis"] = rok_doby["data"].dt.strftime("%d.%m.%Y") + "<br>" + rok_doby["klaster"].map(opis["nazwa"])
siatka = rok_doby.pivot(index="dzien", columns="tydzien", values="klaster")
opisy = rok_doby.pivot(index="dzien", columns="tydzien", values="opis").fillna("")

# dyskretna skala kolorów: każdy numer klastra ma stały kolor
n = len(opis)
skala = []
for i, k in enumerate(opis.index):
    skala += [[i / n, kolor[k]], [(i + 1) / n, kolor[k]]]
fig = go.Figure(go.Heatmap(
    z=siatka.values, x=siatka.columns, y=[DNI[d] for d in siatka.index], colorscale=skala,
    zmin=-0.5, zmax=n - 0.5, showscale=False, xgap=2, ygap=2,
    text=opisy.values, hovertemplate="%{text}<extra></extra>"))
fig.update_layout(yaxis=dict(autorange="reversed"), xaxis_title="tydzień roku", hovermode="closest")
wykres(fig, 300)
st.markdown(" · ".join(f'<span style="color:{kolor[k]}">■</span> {w["nazwa"]}' for k, w in opis.iterrows()),
            unsafe_allow_html=True)

st.subheader("Dobór liczby klastrów")
fig = go.Figure(go.Scatter(x=sylwetki["k"], y=sylwetki["sylwetka"], mode="lines+markers",
                           line=dict(color=NIEBIESKI, width=2), marker_size=8,
                           hovertemplate="k = %{x}: %{y:.3f}<extra></extra>"))
fig.add_vline(x=len(opis), line=dict(color="#898781", width=1))
fig.update_layout(xaxis_title="liczba klastrów k", yaxis_title="współczynnik sylwetki", hovermode="closest")
wykres(fig, 300)

if wybor == "zapotrzebowanie":
    wniosek("Klasteryzacja samodzielnie, bez informacji o kalendarzu, rozdzieliła doby na <b>wtorki–piątki, "
            "poniedziałki, soboty oraz niedziele i święta</b>. Poniedziałki tworzą odrębny klaster, ponieważ "
            "noc poprzedzona weekendem ma wyraźnie niższe zapotrzebowanie, a amplituda dobowa jest największa.")
else:
    wniosek("Profile cen różnicują się przede wszystkim sezonowo: zimą dominuje szczyt poranny i wieczorny, "
            "natomiast wiosną i latem w godzinach południowych występuje głęboki spadek cen związany "
            "z generacją fotowoltaiczną.")
st.caption(f"Współczynnik sylwetki dla przyjętego k = {len(opis)}: "
           f"{liczba(sylwetki.set_index('k').loc[len(opis), 'sylwetka'], 3)}. Uzasadnienie wyboru k – "
           "zob. zakładka „Dane i metodyka”.")
