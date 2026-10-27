import pandas as pd
import streamlit as st

from wspolne import naglowek, zapytanie, zbior

GRUPY_OBIEKTOW = [
    ("Wymiary", "dim_%", "table"),
    ("Fakty", "fakt_%", "table"),
    ("Wyniki analiz", "%", "table"),
    ("Widoki analityczne (aplikacja)", "v_%", "view"),
    ("Widoki raportowe (Power BI)", "pbi_%", "view"),
]


def obiekty_bazy():
    """Tabele i widoki bazy danych z liczbą wierszy (odczyt z katalogu systemowego sqlite_master)."""
    obiekty = zapytanie("SELECT name AS nazwa, type AS typ FROM sqlite_master "
                        "WHERE type IN ('table', 'view') ORDER BY name")
    wiersze, przypisane = [], set()
    for grupa, wzorzec, typ in GRUPY_OBIEKTOW:
        prefiks = wzorzec.rstrip("%")
        for nazwa in obiekty.loc[obiekty["typ"] == typ, "nazwa"]:
            if nazwa in przypisane or not nazwa.startswith(prefiks):
                continue
            przypisane.add(nazwa)
            liczba_wierszy = zapytanie(f"SELECT COUNT(*) AS n FROM {nazwa}")["n"].iloc[0]
            wiersze.append((grupa, nazwa, liczba_wierszy))
    return pd.DataFrame(wiersze, columns=["Grupa", "Tabela / widok", "Liczba wierszy"])

naglowek("Dokumentacja", "Dane i metodyka",
         "Pochodzenie danych, sposób ich integracji, ocena jakości oraz założenia i ograniczenia analizy.")

st.subheader("Źródła danych")
st.table(pd.DataFrame([
    ("Z1", "PSE S.A. – archiwum raportów (pse.pl)", "CSV", "01.01.2022 – 13.06.2024",
     "zapotrzebowanie na moc, generacja wiatrowa i fotowoltaiczna (dane godzinowe)"),
    ("Z1", "PSE S.A. – API raporty.pse.pl", "API (JSON)", "14.06.2024 – 30.09.2026",
     "zapotrzebowanie, prognoza PSE, generacja wiatr/PV (dane 15-minutowe)"),
    ("Z2", "ENTSO-E Transparency Platform (kopia: energy-charts.info, Fraunhofer ISE)", "API (JSON)",
     "01.01.2022 – 30.09.2026", "generacja według typu paliwa – miks energetyczny"),
    ("Z3", "Rynek Dnia Następnego – fixing SDAC dla obszaru PL (PSE; wcześniej ENTSO-E)", "API (JSON)",
     "01.01.2022 – 30.09.2026", "godzinowe ceny energii; ceny w EUR przeliczone po kursie średnim NBP"),
    ("Z3", "Narodowy Bank Polski – tabela A", "API (JSON)", "01.01.2022 – 30.09.2026", "średni kurs EUR/PLN"),
    ("Z4", "Open-Meteo Historical Weather API (reanaliza ERA5)", "API (JSON)", "01.01.2022 – 30.09.2026",
     "temperatura, wiatr na 100 m, promieniowanie, zachmurzenie – 10 lokalizacji"),
    ("Z5", "Biblioteka holidays (Python)", "generowane", "—", "dni ustawowo wolne od pracy w Polsce"),
], columns=["Nr", "Źródło", "Format", "Okres", "Zawartość"]).set_index("Nr"))

st.subheader("Integracja danych")
st.markdown("""
- **Wspólny klucz:** początek godziny w czasie UTC. Praca w UTC eliminuje duplikaty i luki w dobach
  23- i 25-godzinnych (zmiana czasu). W raportach prezentowany jest czas lokalny.
- **Doba handlowa PSE (godziny 1–24):** kolejny wiersz doby traktowany jest jako kolejna godzina od północy
  czasu lokalnego, co poprawnie obsługuje doby o zmiennej długości.
- **Rozdzielczość:** dane 15-minutowe (PSE od 14.06.2024, ceny od 01.10.2025) agregowane do godzin średnią.
- **Pogoda:** wartość ogólnopolska jako średnia ważona – temperatura liczbą ludności województw,
  prędkość wiatru szacunkowym rozmieszczeniem mocy farm wiatrowych; promieniowanie i zachmurzenie – średnia prosta.
- **Braki danych:** luki do 3 godzin uzupełniane interpolacją liniową; dłuższe pozostawiane jako braki.
""")

st.subheader("Baza danych")
st.markdown("""
Dane przetworzone oraz wyniki analiz przechowywane są w relacyjnej bazie danych **SQLite** (plik `data/kse.db`).
Struktura bazy zdefiniowana jest w skrypcie `sql/schemat.sql` i odpowiada **schematowi gwiazdy**:
tabele faktów (pomiary godzinowe KSE, miks wytwarzania, pogoda w lokalizacjach) połączone kluczami obcymi
z wymiarami czasu, kalendarza, godziny doby, źródła wytwarzania i lokalizacji. Wspólnym kluczem czasu jest
początek godziny w UTC; tabela `dim_czas` przypisuje mu czas lokalny i datę kalendarzową.

- **Integralność danych** zapewniają klucze główne, klucze obce i ograniczenia `CHECK` (np. dopuszczalne
  typy dni i sezony) – zapis niespójnych danych kończy się błędem i wycofaniem transakcji.
- **Widoki analityczne** (`v_*`) łączą tabele na potrzeby aplikacji, np. `v_kse_godzinowy` odtwarza
  zintegrowany zbiór godzinowy, a `v_najlepszy_model` wybiera model o najniższym błędzie MAPE.
- **Widoki raportowe** (`pbi_*`, plik `sql/widoki_powerbi.sql`) stanowią warstwę prezentacji dla raportu
  Power BI, który odczytuje dane z bazy przez sterownik ODBC.
""")
st.dataframe(obiekty_bazy(), hide_index=True, width="stretch",
             column_config={"Liczba wierszy": st.column_config.NumberColumn(format="localized")})

st.subheader("Ocena jakości danych")
jakosc = zapytanie("SELECT * FROM jakosc_danych")
st.dataframe(jakosc.rename(columns={"zmienna": "Zmienna", "liczba_godzin": "Liczba godzin",
                                    "braki_przed": "Braki przed uzupełnieniem", "braki_po": "Braki po uzupełnieniu",
                                    "kompletnosc_proc": "Kompletność [%]"}),
             hide_index=True, width="stretch")
st.markdown("""
**Prognoza PSE przed 14.06.2024.** Archiwalny raport planu dobowego zawiera „prognozowane zapotrzebowanie sieci”,
które jest systematycznie niższe od krajowego zapotrzebowania na moc o ok. 2,3 GW (inny zakres bilansowy).
Wielkość ta nie jest porównywalna z prognozą publikowaną w nowym API, dlatego porównanie z prognozą PSE
wykonano wyłącznie na danych od 14.06.2024 – w szczególności na zbiorze testowym (2026 r.).
""")

st.subheader("Model prognostyczny – założenia")
st.markdown("""
- **Zmienna objaśniana:** średnie godzinowe zapotrzebowanie na moc w KSE [MW].
- **Horyzont:** doba naprzód. PSE publikuje zapotrzebowanie rzeczywiste z ok. jednodniowym opóźnieniem,
  więc w dniu D-1 znane są pełne dane do doby D-2. Najkrótsze opóźnienie zmiennej objaśnianej wynosi
  zatem **48 h** (w koncepcji zakładano 24 h – zmiana zapobiega wykorzystaniu informacji niedostępnej w praktyce).
- **Cechy:** godzina, dzień tygodnia, miesiąc, święto, dzień pomostowy, temperatura, stopniogodziny grzania
  (próg 18°C) i chłodzenia (22°C), średnia temperatura z 24 h, promieniowanie, zachmurzenie, zapotrzebowanie
  sprzed 48 h i 7 dni, średnia z tej samej godziny w 7 znanych dobach.
- **Modele:** prognoza naiwna (wartość sprzed tygodnia), regresja grzbietowa z kodowaniem one-hot,
  Random Forest, HistGradientBoosting.
- **Walidacja:** TimeSeriesSplit (5 okresów po 90 dni), bez losowego mieszania obserwacji; zbiór testowy:
  01.01–30.09.2026.
- **Miary:** MAPE, MAE, RMSE; ważność cech metodą permutacyjną.
""")

st.subheader("Ograniczenia")
st.markdown("""
- W danych historycznych użyto **rzeczywistych** wartości pogodowych (reanaliza) zamiast prognoz pogody
  dostępnych w dniu D-1 – zbiór testowy jest więc pod tym względem korzystniejszy dla modelu. W prognozie
  na żywo wykorzystywana jest rzeczywista prognoza pogody.
- Miks energetyczny pochodzi z kopii danych ENTSO-E udostępnianej przez energy-charts.info; po uzyskaniu
  tokenu API ENTSO-E dane mogą zostać pobrane bezpośrednio, bez zmian w dalszej części przetwarzania.
- Wagi rozmieszczenia farm wiatrowych mają charakter szacunkowy.
- **Klasteryzacja:** współczynnik sylwetki jest najwyższy dla k = 2, jednak taki podział oddziela wyłącznie
  dni robocze od wolnych. Przyjęto k = 4 (sylwetka praktycznie równa wartości dla k = 3) ze względu na
  lepszą interpretowalność klastrów.
""")

st.subheader("Pobierz dane")
k1, k2, k3 = st.columns(3)
dane = zbior()
k1.download_button("Zbiór godzinowy (CSV)", dane.to_csv().encode("utf-8"), "kse_godzinowy.csv", "text/csv",
                   width="stretch")
for kolumna, (etykieta, tabela) in zip((k2, k3), (("Metryki modeli (CSV)", "metryki_modeli"),
                                                    ("Ważność cech (CSV)", "waznosc_cech"))):
    tresc = zapytanie(f"SELECT * FROM {tabela}").to_csv(index=False).encode("utf-8")
    kolumna.download_button(etykieta, tresc, f"{tabela}.csv", "text/csv", width="stretch")
