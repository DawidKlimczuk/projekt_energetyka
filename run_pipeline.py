"""Uruchamia cały proces przetwarzania danych po kolei.

    python run_pipeline.py            – wszystkie etapy
    python run_pipeline.py --bez-pobierania   – pomija pobieranie (dane już w data/raw)
"""
import sys
import time

from src import klasteryzacja, model, pobieranie, projekt_powerbi, przetwarzanie

ETAPY = [
    ("Pobieranie danych", pobieranie.pobierz_wszystko),
    ("Czyszczenie, integracja i zapis do bazy danych", przetwarzanie.zbuduj_zbior),
    ("Model prognostyczny", model.trenuj_i_ocen),
    ("Klasteryzacja profili dobowych", klasteryzacja.wykonaj),
    ("Generowanie projektu Power BI", projekt_powerbi.generuj),
]

if __name__ == "__main__":
    pomin_pobieranie = "--bez-pobierania" in sys.argv
    for nr, (nazwa, funkcja) in enumerate(ETAPY, start=1):
        if pomin_pobieranie and funkcja is pobieranie.pobierz_wszystko:
            continue
        print(f"\n=== Etap {nr}/{len(ETAPY)}: {nazwa} ===")
        start = time.time()
        funkcja()
        print(f"--- zakończono w {time.time() - start:.0f} s")
