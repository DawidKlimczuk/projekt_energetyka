"""Model prognozy zapotrzebowania na moc w KSE na dobę naprzód (pytanie P4).

Założenia:
    * zmienna objaśniana: średnie godzinowe zapotrzebowanie na moc [MW],
    * prognoza sporządzana jest w dobie D-1 na dobę D. PSE publikuje rzeczywiste
      zapotrzebowanie z jednodniowym opóźnieniem (ok. godz. 3:00 następnej doby),
      więc w chwili sporządzania prognozy znane są pełne dane tylko do doby D-2.
      Z tego powodu najkrótsze opóźnienie zapotrzebowania wynosi 48 h – dzięki
      temu model nie korzysta z informacji niedostępnych w praktyce,
    * dane pogodowe traktowane są jako prognoza pogody – w danych historycznych
      użyto wartości rzeczywistych (reanaliza ERA5), co jest uproszczeniem,
    * walidacja chronologiczna (TimeSeriesSplit), zbiór testowy: rok 2026.
"""
import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.inspection import permutation_importance
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src import baza_danych
from src.konfiguracja import MODELE, POCZATEK_TESTU

CEL = "zapotrzebowanie_mw"

CECHY_KALENDARZOWE = ["godzina", "dzien_tygodnia", "miesiac", "swieto", "dzien_pomostowy"]
CECHY_POGODOWE = ["temperatura_c", "hdd", "cdd", "temperatura_srednia_24h",
                  "promieniowanie_wm2", "zachmurzenie_proc"]
CECHY_OPOZNIONE = ["zapotrzebowanie_lag_48h", "zapotrzebowanie_lag_168h",
                   "zapotrzebowanie_srednia_7d_ta_godzina"]
CECHY = CECHY_KALENDARZOWE + CECHY_POGODOWE + CECHY_OPOZNIONE

NAZWY_CECH = {
    "godzina": "Godzina doby",
    "dzien_tygodnia": "Dzień tygodnia",
    "miesiac": "Miesiąc",
    "swieto": "Święto",
    "dzien_pomostowy": "Dzień pomostowy",
    "temperatura_c": "Temperatura",
    "hdd": "Stopnie grzania (HDD)",
    "cdd": "Stopnie chłodzenia (CDD)",
    "temperatura_srednia_24h": "Średnia temperatura z 24 h",
    "promieniowanie_wm2": "Promieniowanie słoneczne",
    "zachmurzenie_proc": "Zachmurzenie",
    "zapotrzebowanie_lag_48h": "Zapotrzebowanie sprzed 48 h",
    "zapotrzebowanie_lag_168h": "Zapotrzebowanie sprzed 7 dni",
    "zapotrzebowanie_srednia_7d_ta_godzina": "Średnie zapotrzebowanie o tej godzinie (7 dni)",
}


def dodaj_cechy(zbior):
    """Inżynieria cech. Wymaga ciągłego indeksu godzinowego (czas UTC)."""
    dane = zbior.copy()
    # stopniogodziny grzania i chłodzenia (progi 18°C i 22°C)
    dane["hdd"] = (18 - dane["temperatura_c"]).clip(lower=0)
    dane["cdd"] = (dane["temperatura_c"] - 22).clip(lower=0)
    dane["temperatura_srednia_24h"] = dane["temperatura_c"].rolling(24, min_periods=12).mean()

    zap = dane[CEL]
    dane["zapotrzebowanie_lag_48h"] = zap.shift(48)
    dane["zapotrzebowanie_lag_168h"] = zap.shift(168)
    # średnia z tej samej godziny w 7 znanych dobach (opóźnienia 48, 72, ..., 192 h)
    dane["zapotrzebowanie_srednia_7d_ta_godzina"] = np.mean(
        [zap.shift(24 * k) for k in range(2, 9)], axis=0)
    return dane


def modele():
    """Słownik porównywanych modeli (prognoza naiwna liczona osobno)."""
    kategorie = ["godzina", "dzien_tygodnia", "miesiac"]
    liczbowe = [c for c in CECHY if c not in kategorie]
    przygotowanie_liniowe = ColumnTransformer([
        ("kategorie", OneHotEncoder(handle_unknown="ignore"), kategorie),
        ("liczby", StandardScaler(), liczbowe),
    ])
    return {
        "Regresja liniowa": make_pipeline(przygotowanie_liniowe, Ridge(alpha=1.0)),
        "Random Forest": RandomForestRegressor(n_estimators=200, min_samples_leaf=3,
                                               max_features=0.5, n_jobs=-1, random_state=42),
        "HistGradientBoosting": HistGradientBoostingRegressor(
            max_iter=600, learning_rate=0.05, max_leaf_nodes=63,
            categorical_features=[CECHY.index("dzien_tygodnia")], random_state=42),
    }


def miary(rzeczywiste, prognoza):
    rzeczywiste, prognoza = np.asarray(rzeczywiste), np.asarray(prognoza)
    return {
        "mape_proc": 100 * np.mean(np.abs((rzeczywiste - prognoza) / rzeczywiste)),
        "mae_mw": mean_absolute_error(rzeczywiste, prognoza),
        "rmse_mw": np.sqrt(mean_squared_error(rzeczywiste, prognoza)),
    }


def walidacja_krzyzowa(uczacy, n_podzialow=5):
    """Walidacja chronologiczna na zbiorze uczącym – każdy fold to kolejny okres."""
    wyniki = []
    podzial = TimeSeriesSplit(n_splits=n_podzialow, test_size=24 * 90)
    for nr, (idx_ucz, idx_wal) in enumerate(podzial.split(uczacy), start=1):
        ucz, wal = uczacy.iloc[idx_ucz], uczacy.iloc[idx_wal]
        okres = f"{wal.index[0]:%Y-%m-%d} – {wal.index[-1]:%Y-%m-%d}"
        wyniki.append({"fold": nr, "okres_walidacji": okres, "model": "Prognoza naiwna (tydzień wcześniej)",
                       **miary(wal[CEL], wal["zapotrzebowanie_lag_168h"])})
        for nazwa, model in modele().items():
            model.fit(ucz[CECHY], ucz[CEL])
            wyniki.append({"fold": nr, "okres_walidacji": okres, "model": nazwa,
                           **miary(wal[CEL], model.predict(wal[CECHY]))})
        print(f"  fold {nr}: {okres}")
    return pd.DataFrame(wyniki)


def trenuj_i_ocen():
    zbior = baza_danych.wczytaj_zbior()
    dane = dodaj_cechy(zbior).dropna(subset=CECHY + [CEL])

    uczacy = dane[dane["czas_lokalny"] < POCZATEK_TESTU]
    testowy = dane[(dane["czas_lokalny"] >= POCZATEK_TESTU) & dane["prognoza_pse_mw"].notna()]
    print(f"Zbiór uczący: {len(uczacy)} godzin, testowy: {len(testowy)} godzin")

    print("Walidacja krzyżowa (TimeSeriesSplit)...")
    cv = walidacja_krzyzowa(uczacy)

    print("Uczenie na pełnym zbiorze uczącym i ocena na roku 2026...")
    prognozy = testowy[["czas_lokalny", CEL, "prognoza_pse_mw", "temperatura_c", "typ_dnia"]].copy()
    prognozy["Prognoza naiwna (tydzień wcześniej)"] = testowy["zapotrzebowanie_lag_168h"]
    wytrenowane = {}
    for nazwa, model in modele().items():
        model.fit(uczacy[CECHY], uczacy[CEL])
        prognozy[nazwa] = model.predict(testowy[CECHY])
        wytrenowane[nazwa] = model

    porownanie = ["Prognoza naiwna (tydzień wcześniej)", *modele(), "prognoza_pse_mw"]
    metryki = pd.DataFrame({nazwa: miary(prognozy[CEL], prognozy[nazwa]) for nazwa in porownanie}).T
    metryki = metryki.rename(index={"prognoza_pse_mw": "Prognoza PSE"}).sort_values("mape_proc")
    print(metryki.round(2))

    najlepszy = metryki.drop(index=["Prognoza PSE", "Prognoza naiwna (tydzień wcześniej)"]).index[0]
    print(f"Ważność cech (permutacyjna) dla modelu: {najlepszy}")
    probka = testowy.sample(min(3000, len(testowy)), random_state=42)
    waznosc = permutation_importance(wytrenowane[najlepszy], probka[CECHY], probka[CEL],
                                     scoring="neg_mean_absolute_error", n_repeats=5,
                                     random_state=42, n_jobs=-1)
    waznosc = pd.DataFrame({
        "cecha": CECHY,
        "nazwa": [NAZWY_CECH[c] for c in CECHY],
        "wzrost_mae_mw": waznosc.importances_mean,
        "odchylenie": waznosc.importances_std,
    }).sort_values("wzrost_mae_mw", ascending=False)

    # prognozy zapisywane w formacie długim: jeden wiersz = godzina × model
    prognozy = (prognozy[porownanie].rename(columns={"prognoza_pse_mw": "Prognoza PSE"})
                .rename_axis(columns="model").stack().rename("prognoza_mw").reset_index())

    print("Zapis wyników do bazy danych...")
    baza_danych.zapisz("metryki_modeli", metryki.rename_axis("model").reset_index())
    baza_danych.zapisz("prognozy_test", prognozy)
    baza_danych.zapisz("walidacja_krzyzowa", cv)
    baza_danych.zapisz("waznosc_cech", waznosc)

    # model produkcyjny – uczony na wszystkich dostępnych danych, używany w aplikacji
    produkcyjny = modele()[najlepszy].fit(dane[CECHY], dane[CEL])
    joblib.dump({"model": produkcyjny, "nazwa": najlepszy, "cechy": CECHY},
                MODELE / "model_prognozy.joblib")
    print(f"Zapisano model produkcyjny ({najlepszy})")
    baza_danych.zapisz("symulacja_temperatury", symulacja_temperatury(produkcyjny, zbior))
    return metryki


def symulacja_temperatury(model, zbior, zmiany=range(-10, 11)):
    """Prognozy modelu produkcyjnego dla godzin zbioru testowego przy temperaturze
    zmienionej o kolejne wartości [°C]. W Power BI wybór zmiany odbywa się parametrem what-if."""
    dane = dodaj_cechy(zbior)
    dane = dane[dane["czas_lokalny"] >= POCZATEK_TESTU].dropna(subset=CECHY)
    czesci = []
    for zmiana in zmiany:
        wariant = dane[CECHY].copy()
        wariant["temperatura_c"] += zmiana
        wariant["temperatura_srednia_24h"] += zmiana
        wariant["hdd"] = (18 - wariant["temperatura_c"]).clip(lower=0)
        wariant["cdd"] = (wariant["temperatura_c"] - 22).clip(lower=0)
        czesci.append(pd.DataFrame({"zmiana_c": zmiana, "prognoza_mw": model.predict(wariant)}, index=dane.index))
    return pd.concat(czesci).reset_index()


if __name__ == "__main__":
    trenuj_i_ocen()
