# Pogoda, OZE i cena prądu – analiza i prognoza zapotrzebowania KSE

**Aplikacja online: https://kse-pogoda-oze.streamlit.app/**

W aplikacji dostępne są wszystkie elementy projektu: analizy, model prognostyczny, raport Power BI,
raport końcowy oraz notebooki 01–05 z kodem i wynikami (strona „Raport końcowy i notebooki”).

Projekt z przedmiotu *Metody analizy, przetwarzania i wizualizacji danych* (WSB).
Zespół: Dawid Klimczuk (195810), Maria Gosa (159835), Wiktoria Dębińska (159859).

Projekt integruje dane z czterech niezależnych instytucji (PSE, ENTSO-E, Rynek Dnia Następnego,
Open-Meteo/ERA5) oraz kalendarz świąt, analizuje wpływ pogody na zapotrzebowanie, miks energetyczny
i ceny energii w Polsce w latach 2022–2026, a także prognozuje zapotrzebowanie Krajowego Systemu
Elektroenergetycznego na dobę naprzód i porównuje wynik z oficjalną prognozą PSE.
Dane przetworzone i wyniki analiz przechowywane są w relacyjnej bazie danych SQLite, z której
korzystają zarówno aplikacja analityczna, jak i raport Power BI.

## Najważniejsze wyniki

| Miara (zbiór testowy 01.01–30.09.2026) | MAPE | MAE |
|---|---|---|
| Prognoza PSE | 2,49% | 449 MW |
| **Model HistGradientBoosting** | **2,88%** | 524 MW |
| Random Forest | 3,13% | 570 MW |
| Regresja liniowa (Ridge) | 4,04% | 701 MW |
| Prognoza naiwna (tydzień wcześniej) | 5,72% | 1 048 MW |

Wszystkie hipotezy badawcze H1–H5 z koncepcji projektu zostały potwierdzone – szczegóły na stronie
startowej aplikacji oraz w raporcie końcowym (`docs/raport_koncowy.pdf`). Kolejne etapy analizy
z kodem i wynikami opisano w notebookach `notebooks/01–05`.

## Uruchomienie aplikacji

**Windows – jedno kliknięcie:** dwukrotne kliknięcie pliku `Uruchom aplikację.bat`.
Przy pierwszym uruchomieniu skrypt tworzy środowisko Pythona i instaluje biblioteki (kilka minut),
kolejne uruchomienia trwają kilka sekund. Aplikacja otwiera się w przeglądarce; zamknięcie okna
konsoli kończy jej działanie. Wymagany jest Python 3.12 lub nowszy.

Ręcznie:
```
pip install -r app/requirements.txt
streamlit run app/app.py
```

## Baza danych

Plik `data/kse.db` (SQLite) – struktura zdefiniowana w skryptach SQL:

* `sql/schemat.sql` – tabele w schemacie gwiazdy z kluczami głównymi, obcymi i ograniczeniami `CHECK`:
  * wymiary: `dim_kalendarz`, `dim_godzina`, `dim_czas`, `dim_zrodlo`, `dim_lokalizacja`,
  * fakty: `fakt_kse_godzinowy`, `fakt_miks`, `fakt_pogoda_stacje`,
  * wyniki analiz: `prognozy_test`, `metryki_modeli`, `walidacja_krzyzowa`, `waznosc_cech`,
    `symulacja_temperatury`, `klastry_*`, `jakosc_danych`,
  * widoki analityczne `v_*` wykorzystywane przez aplikację (np. `v_kse_godzinowy`, `v_najlepszy_model`);
* `sql/widoki_powerbi.sql` – widoki raportowe `pbi_*` odczytywane przez Power BI.

Bazę można przeglądać dowolnym narzędziem obsługującym SQLite (np. DB Browser for SQLite, DBeaver).
Lista tabel z liczbą wierszy znajduje się również na stronie „Dane i metodyka” aplikacji.

## Raport Power BI

1. Jednorazowo: instalacja sterownika ODBC dla SQLite – plik `sqliteodbc_w64.exe` ze strony
   http://www.ch-werner.de/sqliteodbc/ (wersja 64-bitowa, zgodna z Power BI Desktop).
2. Otworzyć `powerbi/KSE.pbip` w Power BI Desktop i kliknąć **Odśwież**. Przy pierwszym połączeniu
   wybrać uwierzytelnianie **Domyślne lub niestandardowe** → *Połącz*.
3. Po przeniesieniu projektu na inny komputer należy ponownie uruchomić `python -m src.projekt_powerbi`
   (aktualizuje ścieżkę do bazy w parametrze `PlikBazy`).

## Odtworzenie danych od podstaw

```
pip install -r requirements.txt
python run_pipeline.py
```
Pobieranie trwa ok. 30–60 min (archiwum PSE udostępnia dane w porcjach po 31 dni; ponowne
uruchomienie pomija pobrane pliki). Jeżeli dane surowe są już w `data/raw`:
`python run_pipeline.py --bez-pobierania` (ok. 5 min).

Opcjonalnie: token API ENTSO-E zapisany w pliku `.env` (`ENTSOE_TOKEN=...`) powoduje pobieranie
miksu energetycznego i cen bezpośrednio z ENTSO-E zamiast z kopii danych energy-charts.info.

## Struktura projektu

```
projekt_energetyka/
├── Uruchom aplikację.bat    – uruchomienie aplikacji jednym kliknięciem (Windows)
├── data/
│   ├── kse.db               – baza danych SQLite (dane przetworzone i wyniki analiz)
│   └── raw/                 – dane surowe pobrane ze źródeł (bez modyfikacji)
├── sql/
│   ├── schemat.sql          – tabele, klucze, ograniczenia i widoki analityczne
│   └── widoki_powerbi.sql   – widoki raportowe dla Power BI
├── src/
│   ├── konfiguracja.py      – ścieżki, okres analizy, lokalizacje pogodowe
│   ├── pobieranie.py        – etap 2: pobieranie danych ze wszystkich źródeł
│   ├── przetwarzanie.py     – etap 3: czyszczenie, UTC, agregacja, łączenie, kalendarz, zapis do bazy
│   ├── baza_danych.py       – tworzenie bazy, zapis i odczyt danych (SQL)
│   ├── analiza.py           – pytania P1–P3, weryfikacja hipotez H1–H5
│   ├── model.py             – pytanie P4: model prognostyczny, symulacja what-if
│   ├── klasteryzacja.py     – pytanie P5: profile dobowe (K-means)
│   ├── prognoza_na_zywo.py  – prognoza na kolejną dobę z bieżących danych
│   └── projekt_powerbi.py   – generator projektu Power BI (.pbip)
├── app/                     – aplikacja analityczna (Streamlit); app/notebooki – notebooki w HTML
├── powerbi/                 – projekt raportu Power BI (KSE.pbip)
├── notebooks/               – notebooki 01–05 z opisem kolejnych etapów
├── docs/                    – raport końcowy (PDF, DOCX)
├── models/                  – zapisany model produkcyjny
├── run_pipeline.py          – uruchomienie wszystkich etapów
└── requirements.txt         – pełne środowisko projektu (app/requirements.txt – tylko aplikacja)
```

## Źródła danych

| Nr | Źródło | Zakres |
|---|---|---|
| Z1 | PSE S.A. – archiwum raportów (pse.pl) oraz API raporty.pse.pl | zapotrzebowanie, prognoza PSE, generacja wiatr/PV |
| Z2 | ENTSO-E Transparency Platform (kopia: energy-charts.info) | generacja według typu paliwa |
| Z3 | Rynek Dnia Następnego – fixing SDAC dla PL (PSE, ENTSO-E), kursy NBP | ceny energii [PLN/MWh] |
| Z4 | Open-Meteo Historical Weather API (reanaliza ERA5) | pogoda dla 10 lokalizacji |
| Z5 | biblioteka `holidays` | dni ustawowo wolne od pracy |
