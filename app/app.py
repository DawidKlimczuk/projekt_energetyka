"""Aplikacja analityczna projektu. Uruchomienie z katalogu projektu:

    streamlit run app/app.py
"""
import streamlit as st

from wspolne import konfiguruj_aplikacje

konfiguruj_aplikacje()

nawigacja = st.navigation({
    "Projekt": [
        st.Page("strony/start.py", title="Start", icon=":material/home:", default=True),
    ],
    "Analiza danych": [
        st.Page("strony/przeglad.py", title="Przegląd KSE", icon=":material/bolt:"),
        st.Page("strony/pogoda.py", title="Pogoda a system (P1, P2)", icon=":material/partly_cloudy_day:"),
        st.Page("strony/rynek.py", title="Rynek energii (P3)", icon=":material/payments:"),
        st.Page("strony/profile.py", title="Profile dobowe (P5)", icon=":material/stacked_line_chart:"),
    ],
    "Prognozowanie": [
        st.Page("strony/prognoza.py", title="Model prognostyczny (P4)", icon=":material/model_training:"),
        st.Page("strony/jutro.py", title="Prognoza na jutro", icon=":material/online_prediction:"),
    ],
    "Raport": [
        st.Page("strony/powerbi.py", title="Raport Power BI", icon=":material/bar_chart:"),
    ],
    "Dokumentacja": [
        st.Page("strony/metodyka.py", title="Dane i metodyka", icon=":material/dataset:"),
        st.Page("strony/dokumenty.py", title="Raport końcowy i notebooki", icon=":material/menu_book:"),
    ],
})
nawigacja.run()
