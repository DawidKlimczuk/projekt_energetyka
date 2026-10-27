"""Wspólne ustawienia projektu: ścieżki, zakres dat, lokalizacje pomiarów pogodowych."""
import os
from pathlib import Path

KATALOG_PROJEKTU = Path(__file__).resolve().parents[1]
DANE_SUROWE = KATALOG_PROJEKTU / "data" / "raw"
MODELE = KATALOG_PROJEKTU / "models"
KATALOG_SQL = KATALOG_PROJEKTU / "sql"

# Baza danych SQLite – docelowe miejsce przechowywania danych przetworzonych i wyników analiz
BAZA_DANYCH = KATALOG_PROJEKTU / "data" / "kse.db"

for _katalog in (DANE_SUROWE, MODELE):
    _katalog.mkdir(parents=True, exist_ok=True)

# Okres analizy (daty w czasie lokalnym, włącznie)
DATA_OD = "2022-01-01"
DATA_DO = "2026-09-30"

# Rok, od którego zaczyna się zbiór testowy modelu prognostycznego
POCZATEK_TESTU = "2026-01-01"

# Dzień wprowadzenia 15-minutowego rynku bilansującego – od tej daty PSE
# publikuje dane w nowym API (raporty.pse.pl), wcześniejsze dane pochodzą
# z archiwalnego eksportu CSV na pse.pl
REFORMA_RB = "2024-06-14"

STREFA_LOKALNA = "Europe/Warsaw"

# Lokalizacje pomiarów pogodowych.
# waga_ludnosc – liczba ludności województwa [mln] (GUS, 2024, wartości zaokrąglone),
#                używana do ważenia temperatury (zapotrzebowanie zależy od liczby odbiorców),
# waga_wiatr   – szacunkowy udział województwa w mocy zainstalowanej farm wiatrowych,
#                używany do ważenia prędkości wiatru.
LOKALIZACJE = [
    {"id": "WAW", "nazwa": "Warszawa", "wojewodztwo": "mazowieckie", "lat": 52.23, "lon": 21.01, "waga_ludnosc": 5.51, "waga_wiatr": 0.06},
    {"id": "KRK", "nazwa": "Kraków", "wojewodztwo": "małopolskie", "lat": 50.06, "lon": 19.94, "waga_ludnosc": 3.43, "waga_wiatr": 0.01},
    {"id": "WRO", "nazwa": "Wrocław", "wojewodztwo": "dolnośląskie", "lat": 51.11, "lon": 17.04, "waga_ludnosc": 2.88, "waga_wiatr": 0.05},
    {"id": "POZ", "nazwa": "Poznań", "wojewodztwo": "wielkopolskie", "lat": 52.41, "lon": 16.93, "waga_ludnosc": 3.49, "waga_wiatr": 0.17},
    {"id": "GDN", "nazwa": "Gdańsk", "wojewodztwo": "pomorskie", "lat": 54.35, "lon": 18.65, "waga_ludnosc": 2.36, "waga_wiatr": 0.14},
    {"id": "SZZ", "nazwa": "Szczecin", "wojewodztwo": "zachodniopomorskie", "lat": 53.43, "lon": 14.55, "waga_ludnosc": 1.65, "waga_wiatr": 0.25},
    {"id": "LDZ", "nazwa": "Łódź", "wojewodztwo": "łódzkie", "lat": 51.76, "lon": 19.46, "waga_ludnosc": 2.38, "waga_wiatr": 0.10},
    {"id": "KTW", "nazwa": "Katowice", "wojewodztwo": "śląskie", "lat": 50.26, "lon": 19.02, "waga_ludnosc": 4.35, "waga_wiatr": 0.01},
    {"id": "BIA", "nazwa": "Białystok", "wojewodztwo": "podlaskie", "lat": 53.13, "lon": 23.16, "waga_ludnosc": 1.15, "waga_wiatr": 0.12},
    {"id": "RZE", "nazwa": "Rzeszów", "wojewodztwo": "podkarpackie", "lat": 50.04, "lon": 22.00, "waga_ludnosc": 2.08, "waga_wiatr": 0.09},
]

# Token do API ENTSO-E – odczytywany ze zmiennej środowiskowej lub pliku .env
def token_entsoe():
    token = os.environ.get("ENTSOE_TOKEN")
    plik_env = KATALOG_PROJEKTU / ".env"
    if not token and plik_env.exists():
        for linia in plik_env.read_text(encoding="utf-8").splitlines():
            if linia.strip().startswith("ENTSOE_TOKEN="):
                token = linia.split("=", 1)[1].strip()
    return token or None
