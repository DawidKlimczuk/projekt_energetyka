from pathlib import Path

import streamlit as st

from src.konfiguracja import KATALOG_PROJEKTU
from wspolne import naglowek, wniosek

KATALOG_RAPORTU = KATALOG_PROJEKTU / "docs"
KATALOG_NOTEBOOKOW = KATALOG_PROJEKTU / "notebooks"
# notebooki wyeksportowane do HTML (z kodem i wynikami): jupyter nbconvert --to html --template lab
KATALOG_HTML = Path(__file__).resolve().parents[1] / "notebooki"

NOTEBOOKI = [
    ("01_pobranie_danych", "01. Pobranie danych",
     "Etap 2 – pobranie danych z pięciu źródeł, zakres czasowy i charakterystyka danych surowych."),
    ("02_czyszczenie_i_laczenie", "02. Czyszczenie i łączenie",
     "Etap 3 – ujednolicenie stref czasowych i rozdzielczości, łączenie źródeł, jakość danych, baza SQL."),
    ("03_analiza_eksploracyjna", "03. Analiza eksploracyjna",
     "Pytania P1–P3: zapotrzebowanie a temperatura i kalendarz, OZE w miksie, OZE a cena energii; "
     "weryfikacja hipotez H1–H4."),
    ("04_model_prognozy", "04. Model prognozy",
     "Pytanie P4: inżynieria cech, walidacja krzyżowa, porównanie modeli z prognozą PSE, ważność cech, "
     "symulacja what-if; hipoteza H5."),
    ("05_klasteryzacja_profili", "05. Klasteryzacja profili",
     "Pytanie P5: dobór liczby klastrów, typowe profile dobowe zapotrzebowania i cen (K-means)."),
]


@st.cache_data
def wczytaj(sciezka):
    return Path(sciezka).read_bytes()


naglowek("Dokumentacja", "Raport końcowy i notebooki",
         "Raport końcowy projektu oraz notebooki Jupyter dokumentujące kolejne etapy pracy – z kodem i wynikami.")

wniosek("Wszystkie liczby w raporcie i notebookach pochodzą z tej samej bazy danych i tych samych funkcji "
        "Pythona (moduły <b>src/</b>), z których korzysta aplikacja – wyniki są więc identyczne we wszystkich "
        "miejscach. Notebook 04 uczy modele od nowa i sprawdza zgodność wyników z bazą danych.")

st.subheader("Raport końcowy")
raport_pdf = KATALOG_RAPORTU / "raport_koncowy.pdf"
lewa, prawa, _ = st.columns([1, 1, 3])
with lewa:
    st.download_button("Pobierz PDF", wczytaj(raport_pdf), "raport_koncowy.pdf", "application/pdf",
                       icon=":material/picture_as_pdf:", width="stretch")
with prawa:
    st.download_button("Pobierz DOCX", wczytaj(KATALOG_RAPORTU / "raport_koncowy.docx"), "raport_koncowy.docx",
                       "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                       icon=":material/description:", width="stretch")
st.pdf(wczytaj(raport_pdf), height=900)

st.subheader("Notebooki")
st.caption("Notebooki wykonano w całości – poniżej przedstawiono ich zawartość wraz z wynikami. "
           "Pliki .ipynb można pobrać i uruchomić ponownie w katalogu notebooks/ repozytorium projektu.")
zakladki = st.tabs([tytul for _, tytul, _ in NOTEBOOKI])
for zakladka, (plik, tytul, opis) in zip(zakladki, NOTEBOOKI):
    with zakladka:
        opis_kol, pobierz_kol = st.columns([4, 1], vertical_alignment="center")
        opis_kol.caption(opis)
        pobierz_kol.download_button("Pobierz .ipynb", wczytaj(KATALOG_NOTEBOOKOW / f"{plik}.ipynb"),
                                    f"{plik}.ipynb", "application/x-ipynb+json",
                                    icon=":material/download:", key=plik, width="stretch")
        st.iframe(KATALOG_HTML / f"{plik}.html", height=900)
