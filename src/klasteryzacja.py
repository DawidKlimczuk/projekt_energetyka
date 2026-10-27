"""Klasteryzacja dobowych profili zapotrzebowania i cen (pytanie P5).

Każda doba opisana jest wektorem 24 wartości (godziny czasu lokalnego).
Profile są normalizowane, aby grupować doby według kształtu przebiegu,
a nie według poziomu:
    * zapotrzebowanie – podzielone przez średnią dobową,
    * cena – standaryzacja w obrębie doby (odjęcie średniej, podzielenie przez
      odchylenie standardowe), ponieważ ceny mogą być ujemne.
Liczba klastrów: współczynnik sylwetki maleje wraz z k i jest najwyższy dla k = 2,
jednak taki podział rozdziela wyłącznie dni robocze i wolne, co jest znane z góry.
Przyjęto k = 4 – sylwetka jest praktycznie równa wartości dla k = 3, a klastry
są lepiej interpretowalne (np. oddzielenie sobót od niedziel i świąt).
"""
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

from src import baza_danych


def profile_dobowe(zbior, kolumna):
    """Tabela doba × godzina (0–23). Doby 23-godzinne uzupełniane interpolacją,
    w dobach 25-godzinnych powtórzona godzina jest uśredniana."""
    tabela = zbior.pivot_table(index="data", columns="godzina", values=kolumna, aggfunc="mean")
    tabela = tabela.interpolate(axis=1, limit_direction="both")
    return tabela.dropna()


def dobierz_k(macierz, zakres=range(2, 9)):
    wyniki = []
    for k in zakres:
        etykiety = KMeans(n_clusters=k, n_init=10, random_state=42).fit_predict(macierz)
        wyniki.append({"k": k, "sylwetka": silhouette_score(macierz, etykiety, sample_size=1500, random_state=42)})
    return pd.DataFrame(wyniki)


KOLEJNOSC_SEZONOW = ["zima", "wiosna", "lato", "jesień"]


def opisz_klaster(doby_klastra):
    """Nazwa klastra na podstawie udziału typów dni i sezonów wśród jego dób."""
    wolne = doby_klastra["typ_dnia"].isin(["weekend", "święto"]).mean()
    soboty = (doby_klastra["dzien_tygodnia"] == 5).mean()
    if wolne > 0.6:
        typ = "soboty" if soboty > 0.6 else ("niedziele i święta" if soboty < 0.25 else "dni wolne")
    elif wolne > 0.3:
        typ = "dni robocze i wolne"
    else:
        poniedzialki = (doby_klastra["dzien_tygodnia"] == 0).mean()
        if poniedzialki > 0.6:
            typ = "poniedziałki"
        elif poniedzialki < 0.1 and doby_klastra["dzien_tygodnia"].between(1, 4).mean() > 0.85:
            typ = "wtorki–piątki"
        else:
            typ = "dni robocze"

    udzialy = doby_klastra["sezon"].value_counts(normalize=True)
    if udzialy.iloc[0] >= 0.6:
        sezon = udzialy.index[0]
    elif udzialy.iloc[:2].sum() >= 0.7:
        sezon = "–".join(sorted(udzialy.index[:2], key=KOLEJNOSC_SEZONOW.index))
    else:
        return typ
    return f"{typ} · {sezon}"


def klasteryzuj(zbior, kolumna, normalizacja, k=4):
    profile = profile_dobowe(zbior, kolumna)
    if normalizacja == "srednia":
        macierz = profile.div(profile.mean(axis=1), axis=0)
    else:
        macierz = profile.sub(profile.mean(axis=1), axis=0).div(profile.std(axis=1) + 1e-9, axis=0)

    sylwetki = dobierz_k(macierz.values)
    model = KMeans(n_clusters=k, n_init=20, random_state=42).fit(macierz.values)

    doby = pd.DataFrame({"data": profile.index, "klaster": model.labels_})
    info = zbior.groupby("data").agg(typ_dnia=("typ_dnia", "first"), sezon=("sezon", "first"),
                                     dzien_tygodnia=("dzien_tygodnia", "first"), poziom=(kolumna, "mean"))
    doby = doby.merge(info, left_on="data", right_index=True)

    opis = doby.groupby("klaster").agg(
        liczba_dob=("data", "size"),
        sredni_poziom=("poziom", "mean"),
        udzial_dni_wolnych=("typ_dnia", lambda s: s.isin(["weekend", "święto"]).mean()),
    )
    opis["nazwa"] = [opisz_klaster(doby[doby["klaster"] == k]) for k in opis.index]
    # gdy dwa klastry mają tę samą nazwę, rozróżnia je poziom średni
    for nazwa, grupa in opis.groupby("nazwa"):
        if len(grupa) > 1:
            for i, k in enumerate(grupa.sort_values("sredni_poziom").index):
                opis.loc[k, "nazwa"] = f"{nazwa} ({'niższy' if i == 0 else 'wyższy'} poziom)"
    doby["nazwa_klastra"] = doby["klaster"].map(opis["nazwa"])

    # profil przeciętny każdego klastra w jednostkach oryginalnych
    srodki = profile.groupby(doby.set_index("data")["klaster"]).mean()
    srodki = srodki.reset_index().melt(id_vars="klaster", var_name="godzina", value_name="wartosc")
    srodki["nazwa_klastra"] = srodki["klaster"].map(opis["nazwa"])
    return doby, opis, srodki, sylwetki


def wykonaj():
    zbior = baza_danych.wczytaj_zbior()
    wyniki = {}
    for nazwa, kolumna, normalizacja in (("zapotrzebowanie", "zapotrzebowanie_mw", "srednia"),
                                         ("ceny", "cena_pln_mwh", "standaryzacja")):
        doby, opis, srodki, sylwetki = klasteryzuj(zbior, kolumna, normalizacja)
        print(f"{nazwa}: k = {len(opis)}")
        print(opis)
        wyniki[nazwa] = (doby, opis, srodki, sylwetki)

    # zapis do bazy: wyniki obu analiz w jednej tabeli, rozróżnione kolumną „zmienna”
    def polacz(numer, kolumny):
        return pd.concat([w[numer].reset_index()[kolumny].assign(zmienna=n) for n, w in wyniki.items()])

    baza_danych.wyczysc("klastry_doby", "klastry_profile")  # tabele zależne od klastry_opis
    baza_danych.zapisz("klastry_opis", polacz(1, ["klaster", "nazwa", "liczba_dob", "sredni_poziom",
                                                  "udzial_dni_wolnych"]))
    baza_danych.zapisz("klastry_doby", polacz(0, ["data", "klaster", "poziom"]))
    baza_danych.zapisz("klastry_profile", polacz(2, ["klaster", "godzina", "wartosc"]))
    baza_danych.zapisz("klastry_sylwetka", polacz(3, ["k", "sylwetka"]))
    return wyniki


if __name__ == "__main__":
    wykonaj()
