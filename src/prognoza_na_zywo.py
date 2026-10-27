"""Prognoza zapotrzebowania na kolejną dobę na podstawie bieżących danych.

Dane wejściowe:
    * rzeczywiste zapotrzebowanie i prognoza PSE z ostatnich dni (API PSE),
    * prognoza pogody dla 10 lokalizacji (Open-Meteo Forecast API).
Wynik: prognoza modelu dla doby jutrzejszej oraz – dla porównania – prognozy
modelu z ostatnich dni, dla których znane jest już zapotrzebowanie rzeczywiste.
"""
from datetime import date, timedelta

import joblib
import pandas as pd
import requests

from src.konfiguracja import LOKALIZACJE, MODELE, STREFA_LOKALNA
from src.model import dodaj_cechy
from src.przetwarzanie import dodaj_kalendarz

DNI_HISTORII = 14


def _zapotrzebowanie_pse(od, do):
    url = "https://api.raporty.pse.pl/api/kse-load"
    params = {"$filter": f"business_date ge '{od}' and business_date le '{do}'", "$first": 50000}
    wiersze = []
    while url:
        dane = requests.get(url, params=params, timeout=60).json()
        wiersze.extend(dane["value"])
        url, params = dane.get("nextLink"), None
    tabela = pd.DataFrame(wiersze)
    koniec = pd.to_datetime(tabela["dtime_utc"]).dt.tz_localize("UTC")
    tabela["czas_utc"] = (koniec - pd.Timedelta(minutes=15)).dt.floor("h")
    return (tabela.groupby("czas_utc")[["load_actual", "load_fcst"]].mean()
            .rename(columns={"load_actual": "zapotrzebowanie_mw", "load_fcst": "prognoza_pse_mw"}))


def _prognoza_pogody():
    """Godzinowa prognoza (oraz dane z ostatnich dni) uśredniona dla Polski."""
    odp = requests.get("https://api.open-meteo.com/v1/forecast", params={
        "latitude": ",".join(str(m["lat"]) for m in LOKALIZACJE),
        "longitude": ",".join(str(m["lon"]) for m in LOKALIZACJE),
        "hourly": "temperature_2m,shortwave_radiation,cloud_cover,wind_speed_100m",
        "wind_speed_unit": "ms", "timezone": "GMT",
        "past_days": DNI_HISTORII + 2, "forecast_days": 3,
    }, timeout=60).json()
    czesci = []
    for miejsce, dane in zip(LOKALIZACJE, odp):
        tabela = pd.DataFrame(dane["hourly"])
        tabela["czas_utc"] = pd.to_datetime(tabela["time"]).dt.tz_localize("UTC")
        tabela["waga"] = miejsce["waga_ludnosc"]
        czesci.append(tabela)
    pogoda = pd.concat(czesci)
    pogoda["t_x_w"] = pogoda["temperature_2m"] * pogoda["waga"]
    g = pogoda.groupby("czas_utc")
    return pd.DataFrame({
        "temperatura_c": g["t_x_w"].sum() / g["waga"].sum(),
        "promieniowanie_wm2": g["shortwave_radiation"].mean(),
        "zachmurzenie_proc": g["cloud_cover"].mean(),
        "wiatr_100m_ms": g["wind_speed_100m"].mean(),
    })


def prognozuj(dzien=None):
    """Zwraca (tabela godzinowa z prognozami, nazwa modelu, doba prognozy)."""
    pakiet = joblib.load(MODELE / "model_prognozy.joblib")
    model, cechy = pakiet["model"], pakiet["cechy"]

    dzien = dzien or date.today() + timedelta(days=1)
    od = dzien - timedelta(days=DNI_HISTORII + 9)

    pse = _zapotrzebowanie_pse(od, dzien)
    pogoda = _prognoza_pogody()

    start = pd.Timestamp(od, tz=STREFA_LOKALNA).tz_convert("UTC")
    stop = pd.Timestamp(dzien + timedelta(days=1), tz=STREFA_LOKALNA).tz_convert("UTC")
    siatka = pd.date_range(start, stop, freq="h", inclusive="left", name="czas_utc")
    dane = pd.DataFrame(index=siatka).join(pse).join(pogoda)
    dane = dodaj_kalendarz(dane)
    dane = dodaj_cechy(dane)

    do_prognozy = dane.dropna(subset=cechy)
    dane.loc[do_prognozy.index, "prognoza_model_mw"] = model.predict(do_prognozy[cechy])

    wynik = dane[dane["czas_lokalny"] >= pd.Timestamp(dzien - timedelta(days=DNI_HISTORII))]
    return wynik[["czas_lokalny", "zapotrzebowanie_mw", "prognoza_pse_mw", "prognoza_model_mw",
                  "temperatura_c", "promieniowanie_wm2", "typ_dnia"]], pakiet["nazwa"], dzien
