"""Pobieranie danych źródłowych (etap 2 projektu).

Każde źródło zapisywane jest do katalogu data/raw w postaci niezmienionej
(z dokładnością do formatu CSV). Pliki pobrane wcześniej nie są pobierane
ponownie, dzięki czemu przerwane pobieranie można bezpiecznie wznowić.

Źródła:
    Z1  PSE – zapotrzebowanie, prognoza zapotrzebowania, generacja wiatr/PV
        * do 13.06.2024: archiwalny eksport CSV ze strony pse.pl
        * od 14.06.2024: API raporty.pse.pl (dane 15-minutowe)
    Z2  ENTSO-E – generacja według typu paliwa (miks energetyczny)
        * API ENTSO-E (wymaga tokenu), a bez tokenu – kopia danych ENTSO-E
          udostępniana przez energy-charts.info (Fraunhofer ISE)
    Z3  Ceny Rynku Dnia Następnego (fixing SDAC dla obszaru PL)
        * od 14.06.2024: cena SDAC w PLN publikowana przez PSE
        * wcześniej: cena dnia następnego ENTSO-E [EUR/MWh] przeliczona
          po średnim kursie NBP
    Z4  Open-Meteo – godzinowe dane pogodowe (reanaliza ERA5) dla 10 miast
    Z5  Kalendarz świąt – generowany w module przetwarzanie.py
"""
import time
from datetime import date, timedelta

import pandas as pd
import requests

from src.konfiguracja import (DANE_SUROWE, DATA_DO, DATA_OD, LOKALIZACJE,
                              REFORMA_RB, token_entsoe)

sesja = requests.Session()
sesja.headers["User-Agent"] = "Projekt studencki WSB - analiza KSE"


def _pobierz(url, params=None, proby=5, timeout=120):
    """Zapytanie GET z ponawianiem w razie błędu sieci lub limitu serwera."""
    for proba in range(1, proby + 1):
        try:
            odp = sesja.get(url, params=params, timeout=timeout)
            if odp.status_code == 200:
                return odp
            print(f"  kod {odp.status_code}, próba {proba}/{proby}")
        except requests.RequestException as blad:
            print(f"  błąd sieci ({type(blad).__name__}), próba {proba}/{proby}")
        time.sleep(10 * proba)
    raise RuntimeError(f"Nie udało się pobrać: {url}")


def _okresy(od, do, dni):
    """Dzieli zakres dat na kolejne okresy o długości co najwyżej `dni` dni."""
    poczatek = date.fromisoformat(od)
    koniec = date.fromisoformat(do)
    while poczatek <= koniec:
        kres = min(poczatek + timedelta(days=dni - 1), koniec)
        yield poczatek, kres
        poczatek = kres + timedelta(days=1)


def _miesiace(od, do):
    """Zwraca kolejne miesiące kalendarzowe (pierwszy i ostatni dzień) z zakresu."""
    pierwszy_miesiac = pd.Timestamp(od).to_period("M").start_time
    for miesiac in pd.date_range(pierwszy_miesiac, do, freq="MS"):
        poczatek = max(miesiac, pd.Timestamp(od))
        koniec = min(miesiac + pd.offsets.MonthEnd(0), pd.Timestamp(do))
        yield poczatek.date(), koniec.date()


# ---------------------------------------------------------------------------
# Z1. PSE – archiwalny eksport CSV (do 13.06.2024)
# ---------------------------------------------------------------------------
RAPORTY_PSE_ARCHIWUM = {
    "PL_WYK_KSE": "zapotrzebowanie rzeczywiste",
    "PL_GEN_WIATR": "generacja wiatr i fotowoltaika",
    "PL_PD_GO_BILANS": "plan dobowy – prognoza zapotrzebowania",
}


def pobierz_pse_archiwum(raport, od=DATA_OD, do=None, dni_na_zapytanie=31):
    """Pobiera raport z archiwum pse.pl w porcjach (serwer ogranicza długość okresu)."""
    do = do or (date.fromisoformat(REFORMA_RB) - timedelta(days=1)).isoformat()
    katalog = DANE_SUROWE / "pse_archiwum" / raport
    katalog.mkdir(parents=True, exist_ok=True)

    for poczatek, koniec in _okresy(od, do, dni_na_zapytanie):
        plik = katalog / f"{poczatek:%Y%m%d}_{koniec:%Y%m%d}.csv"
        if plik.exists():
            continue
        url = (f"https://www.pse.pl/getcsv/-/export/csv/{raport}"
               f"/data_od/{poczatek:%Y%m%d}/data_do/{koniec:%Y%m%d}")
        for proba in range(1, 7):
            tekst = _pobierz(url).content.decode("cp1250")
            if not tekst.lstrip().startswith("<"):
                break
            # Odpowiedź HTML oznacza przekroczenie limitu – odczekanie i ponowienie
            print(f"  {raport} {poczatek}: limit serwera, oczekiwanie...")
            time.sleep(60 * proba)
        else:
            raise RuntimeError(f"Serwer PSE odrzuca zapytania dla {raport} {poczatek}")
        plik.write_text(tekst, encoding="utf-8")
        print(f"  {raport}: {poczatek} – {koniec}")
        time.sleep(1)


# ---------------------------------------------------------------------------
# Z1/Z3. PSE – API raporty.pse.pl (od 14.06.2024)
# ---------------------------------------------------------------------------
ENDPOINTY_PSE_API = {
    "kse-load": "zapotrzebowanie rzeczywiste i prognoza PSE",
    "his-wlk-cal": "wielkości podstawowe KSE (w tym generacja wiatr i PV)",
    "csdac-pln": "cena SDAC (Rynek Dnia Następnego) w PLN",
}


def pobierz_pse_api(endpoint, od=REFORMA_RB, do=DATA_DO):
    """Pobiera dane z API PSE miesiącami, z obsługą stronicowania (nextLink)."""
    katalog = DANE_SUROWE / "pse_api" / endpoint
    katalog.mkdir(parents=True, exist_ok=True)

    for poczatek, koniec in _miesiace(od, do):
        plik = katalog / f"{poczatek:%Y%m}.csv"
        if plik.exists():
            continue
        url = f"https://api.raporty.pse.pl/api/{endpoint}"
        params = {
            "$filter": f"business_date ge '{poczatek}' and business_date le '{koniec}'",
            "$first": 50000,
        }
        wiersze = []
        while url:
            dane = _pobierz(url, params).json()
            wiersze.extend(dane["value"])
            url, params = dane.get("nextLink"), None
        pd.DataFrame(wiersze).to_csv(plik, index=False)
        print(f"  {endpoint}: {poczatek:%Y-%m} ({len(wiersze)} wierszy)")


# ---------------------------------------------------------------------------
# Z2. Miks energetyczny – ENTSO-E (token) lub energy-charts.info
# ---------------------------------------------------------------------------
# Nazwy typów źródeł w energy-charts -> kody PsrType ENTSO-E
ENERGY_CHARTS_NA_KOD = {
    "Biomass": "B01",
    "Fossil brown coal / lignite": "B02",
    "Fossil coal-derived gas": "B03",
    "Fossil gas": "B04",
    "Fossil hard coal": "B05",
    "Fossil oil": "B06",
    "Hydro pumped storage": "B10",
    "Hydro Run-of-River": "B11",
    "Hydro water reservoir": "B12",
    "Others": "B20",
    "Other renewables": "B15",
    "Solar": "B16",
    "Waste": "B17",
    "Wind offshore": "B18",
    "Wind onshore": "B19",
}


def _miks_energy_charts(poczatek, koniec):
    odp = _pobierz("https://api.energy-charts.info/public_power", {
        "country": "pl", "start": f"{poczatek}T00:00+01:00",
        "end": f"{koniec + timedelta(days=1)}T00:00+01:00",
    })
    dane = odp.json()
    czas = pd.to_datetime(dane["unix_seconds"], unit="s", utc=True)
    tabela = pd.DataFrame({"czas_utc": czas})
    for typ in dane["production_types"]:
        kod = ENERGY_CHARTS_NA_KOD.get(typ["name"])
        if kod:
            tabela[kod] = typ["data"]
    return tabela.melt(id_vars="czas_utc", var_name="kod_zrodla", value_name="generacja_mw")


def _miks_entsoe(poczatek, koniec, token):
    from entsoe import EntsoePandasClient

    klient = EntsoePandasClient(api_key=token)
    start = pd.Timestamp(poczatek, tz="Europe/Warsaw")
    stop = pd.Timestamp(koniec + timedelta(days=1), tz="Europe/Warsaw")
    tabela = klient.query_generation("PL", start=start, end=stop, psr_type=None)
    # Kolumny w postaci (typ, "Actual Aggregated") – zostawiamy tylko generację
    if isinstance(tabela.columns, pd.MultiIndex):
        tabela = tabela.xs("Actual Aggregated", axis=1, level=1)
    nazwa_na_kod = {nazwa: kod for kod, nazwa in _nazwy_entsoe().items()}
    tabela = tabela.rename(columns=nazwa_na_kod)
    tabela.index = tabela.index.tz_convert("UTC")
    tabela = tabela.rename_axis("czas_utc").reset_index()
    return tabela.melt(id_vars="czas_utc", var_name="kod_zrodla", value_name="generacja_mw")


def _nazwy_entsoe():
    from entsoe.mappings import PSRTYPE_MAPPINGS
    return PSRTYPE_MAPPINGS


def pobierz_miks(od=DATA_OD, do=DATA_DO):
    """Generacja według typu paliwa dla Polski, zapisywana miesiącami."""
    token = token_entsoe()
    zrodlo = "entsoe" if token else "energy_charts"
    katalog = DANE_SUROWE / "miks" / zrodlo
    katalog.mkdir(parents=True, exist_ok=True)
    print(f"  źródło miksu: {'API ENTSO-E' if token else 'energy-charts.info (dane ENTSO-E)'}")

    for poczatek, koniec in _miesiace(od, do):
        plik = katalog / f"{poczatek:%Y%m}.csv"
        if plik.exists():
            continue
        if token:
            tabela = _miks_entsoe(poczatek, koniec, token)
        else:
            tabela = _miks_energy_charts(poczatek, koniec)
        tabela.to_csv(plik, index=False)
        print(f"  miks: {poczatek:%Y-%m} ({len(tabela)} wierszy)")
        time.sleep(1)


# ---------------------------------------------------------------------------
# Z3. Ceny dnia następnego przed 14.06.2024 (EUR) oraz kursy NBP
# ---------------------------------------------------------------------------
def pobierz_ceny_eur(od=DATA_OD, do=REFORMA_RB):
    """Cena dnia następnego dla obszaru PL [EUR/MWh], dane ENTSO-E."""
    token = token_entsoe()
    plik = DANE_SUROWE / "ceny" / "ceny_dnia_nastepnego_eur.csv"
    plik.parent.mkdir(parents=True, exist_ok=True)
    if plik.exists():
        return

    czesci = []
    for poczatek, koniec in _okresy(od, do, 92):
        if token:
            from entsoe import EntsoePandasClient
            seria = EntsoePandasClient(api_key=token).query_day_ahead_prices(
                "PL", start=pd.Timestamp(poczatek, tz="Europe/Warsaw"),
                end=pd.Timestamp(koniec + timedelta(days=1), tz="Europe/Warsaw"))
            czesc = seria.tz_convert("UTC").rename("cena_eur_mwh").rename_axis("czas_utc").reset_index()
        else:
            dane = _pobierz("https://api.energy-charts.info/price", {
                "bzn": "PL", "start": f"{poczatek}T00:00+01:00",
                "end": f"{koniec + timedelta(days=1)}T00:00+01:00",
            }).json()
            czesc = pd.DataFrame({
                "czas_utc": pd.to_datetime(dane["unix_seconds"], unit="s", utc=True),
                "cena_eur_mwh": dane["price"],
            })
        czesci.append(czesc)
        print(f"  ceny EUR: {poczatek} – {koniec}")
    pd.concat(czesci).drop_duplicates("czas_utc").to_csv(plik, index=False)


def pobierz_kursy_nbp(od=DATA_OD, do=DATA_DO):
    """Średnie kursy EUR/PLN z tabeli A NBP (API przyjmuje maks. 93 dni)."""
    plik = DANE_SUROWE / "ceny" / "kurs_eur_nbp.csv"
    plik.parent.mkdir(parents=True, exist_ok=True)
    if plik.exists():
        return
    kursy = []
    for poczatek, koniec in _okresy(od, do, 90):
        url = f"https://api.nbp.pl/api/exchangerates/rates/a/eur/{poczatek}/{koniec}/?format=json"
        kursy.extend(_pobierz(url).json()["rates"])
    tabela = pd.DataFrame(kursy).rename(columns={"effectiveDate": "data", "mid": "kurs_eur_pln"})
    tabela[["data", "kurs_eur_pln"]].to_csv(plik, index=False)
    print(f"  kursy NBP: {len(tabela)} notowań")


# ---------------------------------------------------------------------------
# Z4. Pogoda – Open-Meteo Historical Weather API (reanaliza ERA5)
# ---------------------------------------------------------------------------
ZMIENNE_POGODOWE = ["temperature_2m", "wind_speed_100m", "shortwave_radiation", "cloud_cover"]


def pobierz_pogode(od="2021-12-31", do=DATA_DO):
    """Dane godzinowe (czas UTC) dla każdej lokalizacji z pliku konfiguracji.
    Pobieranie zaczyna się dzień wcześniej, ponieważ północ 1.01.2022 czasu
    lokalnego to godzina 23:00 dnia poprzedniego w UTC."""
    katalog = DANE_SUROWE / "pogoda"
    katalog.mkdir(parents=True, exist_ok=True)

    for miejsce in LOKALIZACJE:
        plik = katalog / f"{miejsce['id']}.csv"
        if plik.exists():
            continue
        dane = _pobierz("https://archive-api.open-meteo.com/v1/archive", {
            "latitude": miejsce["lat"], "longitude": miejsce["lon"],
            "start_date": od, "end_date": do,
            "hourly": ",".join(ZMIENNE_POGODOWE),
            "wind_speed_unit": "ms", "timezone": "GMT",
        }).json()
        tabela = pd.DataFrame(dane["hourly"])
        tabela.to_csv(plik, index=False)
        print(f"  pogoda: {miejsce['nazwa']} ({len(tabela)} godzin)")
        time.sleep(2)


def pobierz_wszystko():
    print("Z4 – pogoda (Open-Meteo)")
    pobierz_pogode()
    print("Z2 – miks energetyczny")
    pobierz_miks()
    print("Z3 – ceny")
    pobierz_pse_api("csdac-pln")
    pobierz_ceny_eur()
    pobierz_kursy_nbp()
    print("Z1 – PSE, API (od 14.06.2024)")
    for endpoint in ("kse-load", "his-wlk-cal"):
        pobierz_pse_api(endpoint)
    print("Z1 – PSE, archiwum CSV (do 13.06.2024)")
    for raport in RAPORTY_PSE_ARCHIWUM:
        pobierz_pse_archiwum(raport)


if __name__ == "__main__":
    pobierz_wszystko()
