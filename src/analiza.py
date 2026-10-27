"""Analiza eksploracyjna (pytania P1–P3) i weryfikacja hipotez badawczych.

Funkcje zwracają tabele i liczby, które wykorzystują zarówno notebooki,
jak i aplikacja – dzięki temu wszystkie prezentowane wyniki są spójne.
"""
import numpy as np
import pandas as pd


def _l(x, miejsca=0):
    """Liczba w zapisie polskim: spacja jako separator tysięcy, przecinek dziesiętny."""
    return f"{x:,.{miejsca}f}".replace(",", " ").replace(".", ",")


def dzienne(zbior):
    """Agregaty dobowe: średnie zapotrzebowanie, temperatura, cena, udział OZE."""
    return zbior.groupby("data").agg(
        zapotrzebowanie_mw=("zapotrzebowanie_mw", "mean"),
        temperatura_c=("temperatura_c", "mean"),
        cena_pln_mwh=("cena_pln_mwh", "mean"),
        udzial_oze_proc=("udzial_oze_proc", "mean"),
        typ_dnia=("typ_dnia", "first"),
        sezon=("sezon", "first"),
        rok=("rok", "first"),
    )


# ---------------------------------------------------------------------------
# P1 – zapotrzebowanie a temperatura i kalendarz
# ---------------------------------------------------------------------------
def krzywa_temperaturowa(zbior, stopien=4):
    """Dopasowanie wielomianu do zależności średniego dobowego zapotrzebowania
    od średniej dobowej temperatury (tylko dni robocze, aby wyeliminować wpływ kalendarza).
    Zwraca (doby robocze, siatka temperatur z dopasowaniem, temperatura minimum)."""
    doby = dzienne(zbior)
    robocze = doby[doby["typ_dnia"] == "roboczy"].dropna(subset=["zapotrzebowanie_mw", "temperatura_c"])
    wspolczynniki = np.polyfit(robocze["temperatura_c"], robocze["zapotrzebowanie_mw"], stopien)
    siatka = np.linspace(robocze["temperatura_c"].quantile(0.005), robocze["temperatura_c"].quantile(0.995), 200)
    dopasowanie = pd.DataFrame({"temperatura_c": siatka, "zapotrzebowanie_mw": np.polyval(wspolczynniki, siatka)})
    t_min = dopasowanie.loc[dopasowanie["zapotrzebowanie_mw"].idxmin(), "temperatura_c"]
    return robocze, dopasowanie, float(t_min)


def zapotrzebowanie_wg_temperatury(zbior, szerokosc=2):
    """Średnie zapotrzebowanie w przedziałach temperatury dobowej (dni robocze)."""
    doby = dzienne(zbior)
    robocze = doby[doby["typ_dnia"] == "roboczy"].copy()
    robocze["przedzial"] = (np.floor(robocze["temperatura_c"] / szerokosc) * szerokosc).astype(int)
    return robocze.groupby("przedzial")["zapotrzebowanie_mw"].agg(["mean", "count"]).reset_index()


def mapa_godzina_dzien(zbior, kolumna="zapotrzebowanie_mw"):
    """Średnia wartość w układzie godzina doby × dzień tygodnia."""
    return zbior.pivot_table(index="godzina", columns="dzien_tygodnia", values=kolumna, aggfunc="mean")


def efekt_kalendarza(zbior):
    """Średnie dobowe zapotrzebowanie wg typu dnia i spadek względem dni roboczych [%]."""
    doby = dzienne(zbior)
    srednie = doby.groupby("typ_dnia")["zapotrzebowanie_mw"].mean()
    return pd.DataFrame({
        "srednie_zapotrzebowanie_mw": srednie,
        "zmiana_vs_roboczy_proc": 100 * (srednie / srednie["roboczy"] - 1),
    }).sort_values("srednie_zapotrzebowanie_mw", ascending=False)


# ---------------------------------------------------------------------------
# P2 – OZE w miksie i ich zależność od pogody
# ---------------------------------------------------------------------------
def udzial_oze_roczny(zbior):
    return zbior.groupby("rok").agg(
        udzial_oze_proc=("udzial_oze_proc", "mean"),
        generacja_wiatr_mw=("generacja_wiatr_mw", "mean"),
        generacja_pv_mw=("generacja_pv_mw", "mean"),
        liczba_godzin=("zapotrzebowanie_mw", "count"),
    )


def krzywa_mocy(zbior, kolumna_x, kolumna_y, szerokosc):
    """Empiryczna krzywa: średnia (i kwartyle) zmiennej y w przedziałach zmiennej x."""
    dane = zbior[[kolumna_x, kolumna_y, "rok"]].dropna().copy()
    dane["przedzial"] = np.floor(dane[kolumna_x] / szerokosc) * szerokosc + szerokosc / 2
    return (dane.groupby(["rok", "przedzial"])[kolumna_y]
            .agg(srednia="mean", q25=lambda s: s.quantile(0.25), q75=lambda s: s.quantile(0.75), liczba="count")
            .reset_index().query("liczba >= 20"))


def korelacje_pogoda_oze(zbior):
    """Współczynniki korelacji Pearsona i Spearmana pomiędzy pogodą a generacją OZE."""
    pary = [("wiatr_100m_ms", "generacja_wiatr_mw", "Prędkość wiatru → generacja wiatrowa"),
            ("promieniowanie_wm2", "generacja_pv_mw", "Promieniowanie → generacja PV"),
            ("temperatura_c", "zapotrzebowanie_mw", "Temperatura → zapotrzebowanie"),
            ("udzial_oze_proc", "cena_pln_mwh", "Udział OZE → cena energii")]
    wiersze = []
    for x, y, opis in pary:
        dane = zbior[[x, y]].dropna()
        wiersze.append({"zaleznosc": opis, "pearson": dane[x].corr(dane[y]),
                        "spearman": dane[x].corr(dane[y], method="spearman"), "n": len(dane)})
    return pd.DataFrame(wiersze)


# ---------------------------------------------------------------------------
# P3 – OZE a cena energii
# ---------------------------------------------------------------------------
def cena_wg_udzialu_oze(zbior, szerokosc=10):
    dane = zbior[["udzial_oze_proc", "cena_pln_mwh"]].dropna().copy()
    dane["przedzial"] = (np.floor(dane["udzial_oze_proc"] / szerokosc) * szerokosc).clip(upper=80).astype(int)
    tabela = dane.groupby("przedzial")["cena_pln_mwh"].agg(
        srednia="mean", mediana="median", q10=lambda s: s.quantile(0.1),
        q90=lambda s: s.quantile(0.9), liczba="count", ujemne=lambda s: (s < 0).sum())
    tabela["etykieta"] = [f"{p}–{p + szerokosc}%" if p < 80 else "≥80%" for p in tabela.index]
    return tabela.reset_index()


def ceny_ujemne(zbior):
    """Statystyki godzin z ujemną ceną energii w kolejnych latach."""
    dane = zbior.dropna(subset=["cena_pln_mwh"])
    ujemne = dane[dane["cena_pln_mwh"] < 0]
    roczne = pd.DataFrame({
        "godziny_z_cena_ujemna": ujemne.groupby("rok").size(),
        "minimalna_cena": dane.groupby("rok")["cena_pln_mwh"].min(),
        "srednia_cena": dane.groupby("rok")["cena_pln_mwh"].mean(),
    }).fillna({"godziny_z_cena_ujemna": 0})
    warunki = pd.DataFrame({
        "godziny z ceną ujemną": ujemne[["udzial_oze_proc", "generacja_pv_mw", "generacja_wiatr_mw",
                                         "zapotrzebowanie_mw", "promieniowanie_wm2", "wiatr_100m_ms"]].mean(),
        "pozostałe godziny": dane[dane["cena_pln_mwh"] >= 0][[
            "udzial_oze_proc", "generacja_pv_mw", "generacja_wiatr_mw", "zapotrzebowanie_mw",
            "promieniowanie_wm2", "wiatr_100m_ms"]].mean(),
    })
    typ_dnia = ujemne["typ_dnia"].value_counts(normalize=True).mul(100)
    return roczne, warunki, typ_dnia


def rozpietosc_dobowa_cen(zbior):
    """Dobowa różnica między ceną maksymalną a minimalną – potencjał magazynów energii."""
    doby = zbior.groupby("data")["cena_pln_mwh"].agg(["min", "max"])
    doby["rozpietosc"] = doby["max"] - doby["min"]
    doby["rok"] = pd.to_datetime(doby.index).year
    return doby


# ---------------------------------------------------------------------------
# Weryfikacja hipotez (rozdział 8 koncepcji)
# ---------------------------------------------------------------------------
def weryfikuj_hipotezy(zbior, metryki=None):
    """Zwraca listę słowników: numer, hipoteza, wynik (opis liczbowy), werdykt."""
    hipotezy = []

    # H1 – nieliniowa (U) zależność od temperatury
    robocze, dopasowanie, t_min = krzywa_temperaturowa(zbior)
    zimno = robocze.loc[robocze["temperatura_c"] < 0, "zapotrzebowanie_mw"].mean()
    minimum = robocze.loc[robocze["temperatura_c"].between(t_min - 2, t_min + 2), "zapotrzebowanie_mw"].mean()
    upal = robocze.loc[robocze["temperatura_c"] > 24, "zapotrzebowanie_mw"].mean()
    ksztalt_u = zimno > minimum and upal > minimum
    hipotezy.append({
        "nr": "H1", "hipoteza": "Zapotrzebowanie zależy od temperatury nieliniowo (kształt litery „U”), "
                                "z minimum w przedziale ok. 15–18°C.",
        "wynik": f"Minimum dopasowanej krzywej przypada przy {_l(t_min, 1)}°C. Przy mrozie (< 0°C) zapotrzebowanie "
                 f"jest wyższe o {_l(100 * (zimno / minimum - 1), 1)}%, a w upały (> 24°C) "
                 f"o {_l(100 * (upal / minimum - 1), 1)}% względem minimum.",
        "werdykt": "potwierdzona" if ksztalt_u and 13 <= t_min <= 21 else "częściowo potwierdzona",
    })

    # H2 – sezonowość wielopoziomowa i krzywa kaczki
    kalendarz = efekt_kalendarza(zbior)
    lato = zbior[(zbior["sezon"] == "lato") & (zbior["typ_dnia"] == "roboczy") & (zbior["rok"] >= 2024)]
    profil_netto = lato.groupby("godzina")["zapotrzebowanie_netto_mw"].mean()
    profil = lato.groupby("godzina")["zapotrzebowanie_mw"].mean()
    spadek_poludnie = 100 * (1 - profil_netto.loc[11:14].mean() / profil_netto.loc[[7, 8, 19, 20]].mean())
    weekend = kalendarz.loc["weekend", "zmiana_vs_roboczy_proc"] if "weekend" in kalendarz.index else np.nan
    swieto = kalendarz.loc["święto", "zmiana_vs_roboczy_proc"] if "święto" in kalendarz.index else np.nan
    hipotezy.append({
        "nr": "H2", "hipoteza": "Zapotrzebowanie ma sezonowość dobową, tygodniową i roczną; w południe "
                                "zapotrzebowanie netto spada wskutek generacji PV (krzywa kaczki).",
        "wynik": f"W weekendy zapotrzebowanie jest niższe o {_l(abs(weekend), 1)}%, w święta o {_l(abs(swieto), 1)}% "
                 f"niż w dni robocze. Latem (dni robocze, 2024–2026) zapotrzebowanie netto w godz. 11–15 "
                 f"jest o {spadek_poludnie:.0f}% niższe niż w szczytach porannym i wieczornym, a szczyt "
                 f"zapotrzebowania całkowitego przypada na godz. {int(profil.idxmax())}:00.",
        "werdykt": "potwierdzona" if spadek_poludnie > 10 and weekend < 0 else "częściowo potwierdzona",
    })

    # H3 – efekt merit order i ceny ujemne
    dane = zbior.dropna(subset=["udzial_oze_proc", "cena_pln_mwh"])
    rho = dane["udzial_oze_proc"].corr(dane["cena_pln_mwh"], method="spearman")
    dolny = dane[dane["udzial_oze_proc"] <= dane["udzial_oze_proc"].quantile(0.1)]["cena_pln_mwh"].mean()
    gorny = dane[dane["udzial_oze_proc"] >= dane["udzial_oze_proc"].quantile(0.9)]["cena_pln_mwh"].mean()
    roczne, _, typ_dnia = ceny_ujemne(zbior)
    wolne = typ_dnia.drop("roboczy", errors="ignore").sum()
    hipotezy.append({
        "nr": "H3", "hipoteza": "Wyższa produkcja z OZE obniża cenę energii (efekt merit order); ceny ujemne "
                                "występują głównie w dni wolne przy wysokiej generacji z OZE.",
        "wynik": f"Korelacja rang Spearmana między udziałem OZE a ceną wynosi {_l(rho, 2)}. W 10% godzin z najwyższym "
                 f"udziałem OZE średnia cena to {_l(gorny)} PLN/MWh wobec {_l(dolny)} PLN/MWh w 10% godzin "
                 f"z najniższym udziałem. Godzin z ceną ujemną: {_l(roczne['godziny_z_cena_ujemna'].sum())}, "
                 f"z czego {_l(wolne)}% w weekendy, święta i dni pomostowe.",
        "werdykt": "potwierdzona" if rho < -0.3 and gorny < dolny else "częściowo potwierdzona",
    })

    # H4 – wzrost udziału OZE i sezonowość PV / wiatru
    roczny = udzial_oze_roczny(zbior)
    pelne = roczny[roczny["liczba_godzin"] > 8000]
    pierwszy, ostatni = pelne.index.min(), pelne.index.max()
    sezonowo = zbior.groupby("sezon")[["generacja_pv_mw", "generacja_wiatr_mw"]].mean()
    hipotezy.append({
        "nr": "H4", "hipoteza": "Udział OZE rośnie w kolejnych latach; fotowoltaika dominuje latem, wiatr zimą.",
        "wynik": f"Średni udział OZE w generacji wzrósł z {_l(pelne.loc[pierwszy, 'udzial_oze_proc'], 1)}% "
                 f"({pierwszy}) do {_l(pelne.loc[ostatni, 'udzial_oze_proc'], 1)}% ({ostatni}). Średnia generacja PV "
                 f"latem: {_l(sezonowo.loc['lato', 'generacja_pv_mw'])} MW, zimą: "
                 f"{_l(sezonowo.loc['zima', 'generacja_pv_mw'])} MW; wiatr zimą: "
                 f"{_l(sezonowo.loc['zima', 'generacja_wiatr_mw'])} MW, latem: "
                 f"{_l(sezonowo.loc['lato', 'generacja_wiatr_mw'])} MW.",
        "werdykt": "potwierdzona" if (pelne.loc[ostatni, "udzial_oze_proc"] > pelne.loc[pierwszy, "udzial_oze_proc"]
                                      and sezonowo.loc["lato", "generacja_pv_mw"] > sezonowo.loc["zima", "generacja_pv_mw"]
                                      and sezonowo.loc["zima", "generacja_wiatr_mw"] > sezonowo.loc["lato", "generacja_wiatr_mw"])
                   else "częściowo potwierdzona",
    })

    # H5 – model ML z błędem kilku procent, porównywalny z PSE
    if metryki is not None:
        m = metryki["mape_proc"]
        modele_ml = m.drop(index=["Prognoza PSE", "Prognoza naiwna (tydzień wcześniej)"])
        najlepszy, mape = modele_ml.idxmin(), modele_ml.min()
        roznica = mape - m["Prognoza PSE"]
        hipotezy.append({
            "nr": "H5", "hipoteza": "Model uczenia maszynowego osiągnie MAPE na poziomie kilku procent, "
                                    "porównywalne z prognozą PSE.",
            "wynik": f"Najlepszy model ({najlepszy}) uzyskał na danych z 2026 r. MAPE = {_l(mape, 2)}% wobec "
                     f"{_l(m['Prognoza PSE'], 2)}% dla prognozy PSE i {_l(m['Prognoza naiwna (tydzień wcześniej)'], 2)}% "
                     f"dla prognozy naiwnej (różnica względem PSE: +{_l(roznica, 2)} p.p.).",
            "werdykt": "potwierdzona" if mape < 5 and roznica < 1.5 else "częściowo potwierdzona",
        })
    return hipotezy
