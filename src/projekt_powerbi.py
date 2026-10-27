"""Generator projektu Power BI (format .pbip) odczytującego dane z bazy SQLite.

Tworzy w katalogu powerbi/:
    KSE.pbip                     – plik projektu (otwierany w Power BI Desktop),
    KSE.SemanticModel/model.bim  – model danych: tabele, relacje (schemat gwiazdy), miary DAX,
    KSE.Report/report.json       – strony raportu z wizualizacjami.

Każda tabela modelu pobierana jest zapytaniem SQL z widoku raportowego bazy
(sql/widoki_powerbi.sql, np. Fakt_Miks ← pbi_fakt_miks) przez sterownik
„SQLite3 ODBC Driver”. Ścieżka do pliku bazy zapisywana jest w parametrze
Power Query „PlikBazy” – po przeniesieniu projektu na inny komputer wystarczy
ponownie uruchomić ten skrypt albo zmienić parametr (Przekształć dane → Parametry).
"""
import json
import shutil
import uuid

from src import baza_danych
from src.konfiguracja import BAZA_DANYCH, KATALOG_PROJEKTU

KATALOG_PBI = KATALOG_PROJEKTU / "powerbi"
NAZWA = "KSE"
STEROWNIK_ODBC = "SQLite3 ODBC Driver"

# Kolory raportu – zgodne z aplikacją
TUSZ, NIEBIESKI, POMARANCZOWY = "#16232B", "#2a78d6", "#eb6834"
KOLORY = [NIEBIESKI, POMARANCZOWY, "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
KOLORY_MIKSU = {
    "Węgiel kamienny": "#e34948", "Węgiel brunatny": "#6250d6", "Biomasa": "#008300", "Pozostałe": "#e87ba4",
    "Fotowoltaika": "#eda100", "Woda i magazyny": "#1baf7a", "Gaz ziemny": "#eb6834", "Wiatr": "#2a78d6",
}

# ---------------------------------------------------------------------------
# Model danych
# ---------------------------------------------------------------------------
# tabela modelu Power BI -> widok bazy danych
TABELE = {
    "Fakt_KSE_Godzinowy": "pbi_fakt_kse_godzinowy",
    "Fakt_Miks": "pbi_fakt_miks",
    "Fakt_Pogoda_Stacje": "pbi_fakt_pogoda_stacje",
    "Fakt_Prognoza": "pbi_fakt_prognoza",
    "Fakt_Symulacja": "pbi_fakt_symulacja",
    "Dim_Kalendarz": "pbi_dim_kalendarz",
    "Dim_Godzina": "pbi_dim_godzina",
    "Dim_Zrodlo": "pbi_dim_zrodlo",
    "Dim_Lokalizacja": "pbi_dim_lokalizacja",
    "Klastry_Zapotrzebowanie_Doby": "pbi_klastry_zapotrzebowanie_doby",
    "Klastry_Zapotrzebowanie_Profile": "pbi_klastry_zapotrzebowanie_profile",
    "Klastry_Ceny_Doby": "pbi_klastry_ceny_doby",
    "Klastry_Ceny_Profile": "pbi_klastry_ceny_profile",
    "Waznosc_Cech": "pbi_waznosc_cech",
    "Metryki_Modeli": "pbi_metryki_modeli",
}

RELACJE = [
    ("Fakt_KSE_Godzinowy", "Data", "Dim_Kalendarz", "Data"),
    ("Fakt_KSE_Godzinowy", "Godzina", "Dim_Godzina", "Godzina"),
    ("Fakt_Miks", "Data", "Dim_Kalendarz", "Data"),
    ("Fakt_Miks", "Godzina", "Dim_Godzina", "Godzina"),
    ("Fakt_Miks", "KodZrodla", "Dim_Zrodlo", "KodZrodla"),
    ("Fakt_Pogoda_Stacje", "Data", "Dim_Kalendarz", "Data"),
    ("Fakt_Pogoda_Stacje", "Godzina", "Dim_Godzina", "Godzina"),
    ("Fakt_Pogoda_Stacje", "IdStacji", "Dim_Lokalizacja", "IdStacji"),
    ("Fakt_Prognoza", "Data", "Dim_Kalendarz", "Data"),
    ("Fakt_Prognoza", "Godzina", "Dim_Godzina", "Godzina"),
    ("Fakt_Symulacja", "Data", "Dim_Kalendarz", "Data"),
    ("Fakt_Symulacja", "Godzina", "Dim_Godzina", "Godzina"),
    ("Klastry_Zapotrzebowanie_Doby", "Data", "Dim_Kalendarz", "Data"),
    ("Klastry_Ceny_Doby", "Data", "Dim_Kalendarz", "Data"),
]

# Miary DAX: tabela -> lista (nazwa, wyrażenie, format)
MIARY = {
    "Fakt_KSE_Godzinowy": [
        ("Średnie zapotrzebowanie (MW)", "AVERAGE(Fakt_KSE_Godzinowy[Zapotrzebowanie_MW])", "#,0"),
        ("Maksymalne zapotrzebowanie (MW)", "MAX(Fakt_KSE_Godzinowy[Zapotrzebowanie_MW])", "#,0"),
        ("Zużycie energii (GWh)", "SUM(Fakt_KSE_Godzinowy[Zapotrzebowanie_MW]) / 1000", "#,0.0"),
        ("Średnia generacja PV (MW)", "AVERAGE(Fakt_KSE_Godzinowy[Generacja_PV_MW])", "#,0"),
        ("Średnia generacja wiatrowa (MW)", "AVERAGE(Fakt_KSE_Godzinowy[Generacja_Wiatr_MW])", "#,0"),
        ("Średnie zapotrzebowanie netto (MW)", "AVERAGE(Fakt_KSE_Godzinowy[Zapotrzebowanie_Netto_MW])", "#,0"),
        ("Średnia cena (PLN/MWh)", "AVERAGE(Fakt_KSE_Godzinowy[Cena_PLN_MWh])", "#,0"),
        ("Minimalna cena (PLN/MWh)", "MIN(Fakt_KSE_Godzinowy[Cena_PLN_MWh])", "#,0"),
        ("Godziny z ceną ujemną",
         "CALCULATE(COUNTROWS(Fakt_KSE_Godzinowy), Fakt_KSE_Godzinowy[Cena_PLN_MWh] < 0) + 0", "#,0"),
        ("Średni udział OZE godzinowy (%)", "AVERAGE(Fakt_KSE_Godzinowy[Udzial_OZE_proc]) / 100", "0.0%"),
        ("Średnia temperatura (°C)", "AVERAGE(Fakt_KSE_Godzinowy[Temperatura_C])", "0.0"),
        ("Średnia prędkość wiatru (m/s)", "AVERAGE(Fakt_KSE_Godzinowy[Wiatr_100m_ms])", "0.0"),
        ("Średnie promieniowanie (W/m²)", "AVERAGE(Fakt_KSE_Godzinowy[Promieniowanie_Wm2])", "#,0"),
        ("Zapotrzebowanie rok do roku (%)",
         "VAR Biezace = [Średnie zapotrzebowanie (MW)]\n"
         "VAR Poprzednie = CALCULATE([Średnie zapotrzebowanie (MW)], SAMEPERIODLASTYEAR(Dim_Kalendarz[Data]))\n"
         "RETURN DIVIDE(Biezace - Poprzednie, Poprzednie)", "+0.0%;-0.0%;0.0%"),
    ],
    "Fakt_Miks": [
        # suma generacji źródeł podzielona przez liczbę godzin – warstwy grup paliw sumują się do mocy całkowitej
        ("Średnia generacja (MW)", "DIVIDE(SUM(Fakt_Miks[Generacja_MW]), COUNTROWS(Fakt_KSE_Godzinowy))", "#,0"),
        ("Produkcja energii (GWh)", "SUM(Fakt_Miks[Generacja_MW]) / 1000", "#,0.0"),
        ("Udział OZE w produkcji (%)",
         "DIVIDE(CALCULATE(SUM(Fakt_Miks[Generacja_MW]), Dim_Zrodlo[Kategoria] = \"OZE\"),\n"
         "       CALCULATE(SUM(Fakt_Miks[Generacja_MW]), Dim_Zrodlo[Kategoria] <> \"magazynowanie\"))", "0.0%"),
        ("Udział w produkcji (%)",
         "DIVIDE(SUM(Fakt_Miks[Generacja_MW]),\n"
         "       CALCULATE(SUM(Fakt_Miks[Generacja_MW]), ALL(Dim_Zrodlo)))", "0.0%"),
    ],
    "Fakt_Pogoda_Stacje": [
        ("Temperatura w stacji (°C)", "AVERAGE(Fakt_Pogoda_Stacje[Temperatura_C])", "0.0"),
        ("Wiatr w stacji (m/s)", "AVERAGE(Fakt_Pogoda_Stacje[Wiatr_100m_ms])", "0.0"),
        ("Promieniowanie w stacji (W/m²)", "AVERAGE(Fakt_Pogoda_Stacje[Promieniowanie_Wm2])", "#,0"),
    ],
    "Fakt_Prognoza": [
        ("Zapotrzebowanie rzeczywiste (MW)", "AVERAGE(Fakt_Prognoza[Rzeczywiste_MW])", "#,0"),
        ("Prognoza modelu (MW)", "AVERAGE(Fakt_Prognoza[Prognoza_Model_MW])", "#,0"),
        ("Prognoza PSE (MW)", "AVERAGE(Fakt_Prognoza[Prognoza_PSE_MW])", "#,0"),
        ("MAPE modelu (%)",
         "AVERAGEX(Fakt_Prognoza, DIVIDE(ABS(Fakt_Prognoza[Prognoza_Model_MW] - Fakt_Prognoza[Rzeczywiste_MW]), "
         "Fakt_Prognoza[Rzeczywiste_MW]))", "0.00%"),
        ("MAPE PSE (%)",
         "AVERAGEX(Fakt_Prognoza, DIVIDE(ABS(Fakt_Prognoza[Prognoza_PSE_MW] - Fakt_Prognoza[Rzeczywiste_MW]), "
         "Fakt_Prognoza[Rzeczywiste_MW]))", "0.00%"),
        ("MAPE prognozy naiwnej (%)",
         "AVERAGEX(Fakt_Prognoza, DIVIDE(ABS(Fakt_Prognoza[Prognoza_Naiwna_MW] - Fakt_Prognoza[Rzeczywiste_MW]), "
         "Fakt_Prognoza[Rzeczywiste_MW]))", "0.00%"),
        ("MAE modelu (MW)",
         "AVERAGEX(Fakt_Prognoza, ABS(Fakt_Prognoza[Prognoza_Model_MW] - Fakt_Prognoza[Rzeczywiste_MW]))", "#,0"),
        ("MAE PSE (MW)",
         "AVERAGEX(Fakt_Prognoza, ABS(Fakt_Prognoza[Prognoza_PSE_MW] - Fakt_Prognoza[Rzeczywiste_MW]))", "#,0"),
    ],
    "Fakt_Symulacja": [
        ("Prognoza bazowa (MW)",
         "CALCULATE(AVERAGE(Fakt_Symulacja[Prognoza_MW]), Fakt_Symulacja[Zmiana_C] = 0)", "#,0"),
        # miara nie może być użyta bezpośrednio w warunku CALCULATE – wartość parametru trafia do zmiennej
        ("Prognoza przy zmianie temperatury (MW)",
         "VAR Zmiana = [Wybrana zmiana temperatury (°C)]\n"
         "RETURN CALCULATE(AVERAGE(Fakt_Symulacja[Prognoza_MW]), Fakt_Symulacja[Zmiana_C] = Zmiana)", "#,0"),
        ("Zmiana zapotrzebowania (%)",
         "DIVIDE([Prognoza przy zmianie temperatury (MW)] - [Prognoza bazowa (MW)], [Prognoza bazowa (MW)])",
         "+0.00%;-0.00%;0.00%"),
    ],
    "Parametr_Temperatura": [
        ("Wybrana zmiana temperatury (°C)", "SELECTEDVALUE(Parametr_Temperatura[Zmiana_C], 0)", "+0;-0;0"),
    ],
    "Klastry_Zapotrzebowanie_Profile": [
        ("Profil zapotrzebowania (MW)", "AVERAGE(Klastry_Zapotrzebowanie_Profile[Wartosc])", "#,0"),
    ],
    "Klastry_Ceny_Profile": [
        ("Profil ceny (PLN/MWh)", "AVERAGE(Klastry_Ceny_Profile[Wartosc])", "#,0"),
    ],
    "Klastry_Zapotrzebowanie_Doby": [
        ("Liczba dób", "COUNTROWS(Klastry_Zapotrzebowanie_Doby)", "#,0"),
    ],
    "Waznosc_Cech": [
        ("Ważność cechy (MW)", "SUM(Waznosc_Cech[WzrostMAE_MW])", "#,0"),
    ],
}

SORTOWANIE = {("Dim_Kalendarz", "Miesiac"): "MiesiacNr", ("Dim_Kalendarz", "DzienTygodnia"): "DzienTygodniaNr"}
KLUCZE = {"Dim_Kalendarz": "Data", "Dim_Godzina": "Godzina", "Dim_Zrodlo": "KodZrodla", "Dim_Lokalizacja": "IdStacji"}
KOLUMNY_DAT = {"Data", "PoczatekMiesiaca"}


def _typ_kolumny(nazwa, seria):
    """Zwraca (typ w modelu, typ w Power Query, format) dla kolumny widoku."""
    if nazwa == "CzasLokalny":
        return "dateTime", "type datetime", "yyyy-mm-dd hh:nn"
    if nazwa in KOLUMNY_DAT:
        return "dateTime", "type date", "yyyy-mm-dd"
    if seria.dtype.kind == "i":
        return "int64", "Int64.Type", "0"
    if seria.dtype.kind == "f":
        return "double", "type number", "#,0.0"
    return "string", "type text", None


def _tabela(nazwa, widok):
    probka = baza_danych.wczytaj(f"SELECT * FROM {widok} LIMIT 5000")
    kolumny, typy_m = [], []
    for kolumna in probka.columns:
        typ, typ_m, format_ = _typ_kolumny(kolumna, probka[kolumna])
        definicja = {"name": kolumna, "dataType": typ, "sourceColumn": kolumna,
                     "summarizeBy": "none" if typ != "double" else "sum"}
        if format_:
            definicja["formatString"] = format_
        if (nazwa, kolumna) in SORTOWANIE:
            definicja["sortByColumn"] = SORTOWANIE[(nazwa, kolumna)]
        if KLUCZE.get(nazwa) == kolumna:
            definicja["isKey"] = True
        if kolumna in ("Szerokosc", "Dlugosc"):
            definicja["dataCategory"] = "Latitude" if kolumna == "Szerokosc" else "Longitude"
            definicja["summarizeBy"] = "none"
        kolumny.append(definicja)
        typy_m.append(f'{{"{kolumna}", {typ_m}}}')

    wyrazenie = [
        "let",
        f'    Zrodlo = Odbc.Query("Driver={{{STEROWNIK_ODBC}}};Database=" & PlikBazy, "SELECT * FROM {widok}"),',
        f'    Typy = Table.TransformColumnTypes(Zrodlo, {{{", ".join(typy_m)}}}, "en-US")',
        "in",
        "    Typy",
    ]
    tabela = {"name": nazwa, "columns": kolumny,
              "partitions": [{"name": nazwa, "mode": "import", "source": {"type": "m", "expression": wyrazenie}}]}
    if nazwa == "Dim_Kalendarz":
        tabela["dataCategory"] = "Time"
    return tabela


def _tabela_parametru():
    """Tabela parametru what-if: zmiana temperatury od −10 do +10°C."""
    wyrazenie = [
        "let",
        '    Zrodlo = Table.FromList({-10..10}, Splitter.SplitByNothing(), {"Zmiana_C"}),',
        '    Typy = Table.TransformColumnTypes(Zrodlo, {{"Zmiana_C", Int64.Type}})',
        "in",
        "    Typy",
    ]
    return {"name": "Parametr_Temperatura",
            "columns": [{"name": "Zmiana_C", "dataType": "int64", "sourceColumn": "Zmiana_C",
                         "summarizeBy": "none", "formatString": "+0;-0;0"}],
            "partitions": [{"name": "Parametr_Temperatura", "mode": "import",
                            "source": {"type": "m", "expression": wyrazenie}}]}


def zbuduj_model():
    tabele = [_tabela(nazwa, widok) for nazwa, widok in TABELE.items()] + [_tabela_parametru()]
    for tabela in tabele:
        tabela["measures"] = [{"name": n, "expression": e.split("\n") if "\n" in e else e, "formatString": f}
                              for n, e, f in MIARY.get(tabela["name"], [])]
        if not tabela["measures"]:
            del tabela["measures"]

    relacje = [{"name": str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{t1}.{k1}")), "fromTable": t1, "fromColumn": k1,
                "toTable": t2, "toColumn": k2} for t1, k1, t2, k2 in RELACJE]

    return {
        "compatibilityLevel": 1567,
        "model": {
            "culture": "pl-PL",
            "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "sourceQueryCulture": "pl-PL",
            "dataAccessOptions": {"legacyRedirects": True, "returnErrorValuesAsNull": True},
            "tables": tabele,
            "relationships": relacje,
            "expressions": [{
                "name": "PlikBazy", "kind": "m",
                "expression": f'"{BAZA_DANYCH}" meta [IsParameterQuery = true, Type = "Text", '
                              'IsParameterQueryRequired = true]',
                "annotations": [{"name": "PBI_ResultType", "value": "Text"}],
            }],
            "annotations": [
                {"name": "PBI_QueryOrder", "value": json.dumps(["PlikBazy", *TABELE, "Parametr_Temperatura"])},
                # bez automatycznych tabel dat – rolę kalendarza pełni Dim_Kalendarz
                {"name": "__PBI_TimeIntelligenceEnabled", "value": "0"},
            ],
        },
    }


# ---------------------------------------------------------------------------
# Raport
# ---------------------------------------------------------------------------
def _literal(wartosc):
    return {"expr": {"Literal": {"Value": wartosc}}}


def _tekst(wartosc):
    return _literal(f"'{wartosc}'")


def _kolor(kolor):
    return {"solid": {"color": _tekst(kolor)}}


class Wizualizacja:
    """Pomocnik budujący kontener wizualizacji w formacie report.json."""

    licznik = 0

    def __init__(self, typ, x, y, szer, wys, tytul=None):
        Wizualizacja.licznik += 1
        self.nazwa = f"w{Wizualizacja.licznik:04d}"
        self.typ, self.pozycja = typ, (x, y, szer, wys)
        self.tytul = tytul
        self.zrodla, self.wybory, self.projekcje = {}, [], {}
        self.obiekty, self.wlasciwosci_kolumn, self.sortowanie = {}, {}, []

    def _alias(self, tabela):
        if tabela not in self.zrodla:
            self.zrodla[tabela] = f"t{len(self.zrodla)}"
        return self.zrodla[tabela]

    def _wyrazenie(self, tabela, nazwa, miara):
        return {"Measure" if miara else "Column": {"Expression": {"SourceRef": {"Source": self._alias(tabela)}},
                                                   "Property": nazwa}}

    def pole(self, rola, tabela, nazwa, miara=False, etykieta=None):
        ref = f"{tabela}.{nazwa}"
        self.wybory.append({**self._wyrazenie(tabela, nazwa, miara), "Name": ref})
        self.projekcje.setdefault(rola, []).append({"queryRef": ref, **({"active": True} if rola == "Category" else {})})
        if etykieta:
            self.wlasciwosci_kolumn[ref] = {"displayName": etykieta}
        return self

    def miara(self, rola, tabela, nazwa, etykieta=None):
        return self.pole(rola, tabela, nazwa, miara=True, etykieta=etykieta)

    def sortuj(self, tabela, nazwa, miara=False, malejaco=True):
        self.sortowanie.append({"Direction": 2 if malejaco else 1,
                                "Expression": self._wyrazenie(tabela, nazwa, miara)})
        return self

    def ustaw(self, obiekt, wlasciwosci, selektor=None):
        wpis = {"properties": wlasciwosci}
        if selektor:
            wpis["selector"] = selektor
        self.obiekty.setdefault(obiekt, []).append(wpis)
        return self

    def kolory_miar(self, tabela, kolory):
        """Stały kolor serii dla kolejnych miar (np. rzeczywiste – grafit, PSE – pomarańcz)."""
        for miara, kolor in kolory.items():
            self.ustaw("dataPoint", {"fill": _kolor(kolor)}, {"metadata": f"{tabela}.{miara}"})
        return self

    def kolory_wartosci(self, tabela, kolumna, kolory):
        """Stały kolor serii dla wartości kolumny legendy (np. grupy paliw)."""
        alias = {"Column": {"Expression": {"SourceRef": {"Entity": tabela}}, "Property": kolumna}}
        for wartosc, kolor in kolory.items():
            self.ustaw("dataPoint", {"fill": _kolor(kolor)}, {"data": [{"scopeId": {"Comparison": {
                "ComparisonKind": 0, "Left": alias, "Right": {"Literal": {"Value": f"'{wartosc}'"}}}}}]})
        return self

    def kontener(self):
        x, y, szer, wys = self.pozycja
        zapytanie = {
            "Version": 2,
            "From": [{"Name": a, "Entity": t, "Type": 0} for t, a in self.zrodla.items()],
            "Select": self.wybory,
        }
        if self.sortowanie:
            zapytanie["OrderBy"] = self.sortowanie
        pojedyncza = {"visualType": self.typ, "projections": self.projekcje, "prototypeQuery": zapytanie,
                      "drillFilterOtherVisuals": True}
        if self.wlasciwosci_kolumn:
            pojedyncza["columnProperties"] = self.wlasciwosci_kolumn
        if self.obiekty:
            pojedyncza["objects"] = self.obiekty
        vc = {}
        if self.tytul:
            vc["title"] = [{"properties": {"show": _literal("true"), "text": _tekst(self.tytul),
                                           "fontColor": _kolor("#16232B"), "fontSize": _literal("11D")}}]
        else:
            vc["title"] = [{"properties": {"show": _literal("false")}}]
        if self.typ != "textbox":
            vc["background"] = [{"properties": {"show": _literal("true"), "color": _kolor("#FFFFFF")}}]
            vc["border"] = [{"properties": {"show": _literal("true"), "color": _kolor("#D5DEE3"),
                                            "radius": _literal("8D")}}]
        pojedyncza["vcObjects"] = vc
        konfiguracja = {"name": self.nazwa,
                        "layouts": [{"id": 0, "position": {"x": x, "y": y, "z": Wizualizacja.licznik,
                                                           "width": szer, "height": wys}}],
                        "singleVisual": pojedyncza}
        return {"x": x, "y": y, "z": Wizualizacja.licznik, "width": szer, "height": wys,
                "config": json.dumps(konfiguracja, ensure_ascii=False), "filters": "[]"}


# --- elementy powtarzalne ---------------------------------------------------
GORA_WYKRESOW = 182        # górna krawędź obszaru wykresów (pod nagłówkiem, filtrami i kartami)
DOL_STRONY = 708


def _naglowek(tekst, podtytul):
    w = Wizualizacja("textbox", 20, 4, 1240, 74)
    w.obiekty = {"general": [{"properties": {"paragraphs": [
        {"textRuns": [{"value": tekst, "textStyle": {"fontWeight": "bold", "fontSize": "20pt",
                                                     "color": "#16232B", "fontFamily": "Segoe UI"}}]},
        {"textRuns": [{"value": podtytul, "textStyle": {"fontSize": "11pt", "color": "#56666F",
                                                        "fontFamily": "Segoe UI"}}]},
    ]}}]}
    return w


def _fragmentator(x, y, szer, tabela, kolumna, etykieta, tryb="Dropdown", wys=88, jeden=False):
    w = Wizualizacja("slicer", x, y, szer, wys).pole("Values", tabela, kolumna, etykieta=etykieta)
    w.ustaw("data", {"mode": _tekst(tryb)})
    w.ustaw("header", {"show": _literal("true"), "fontColor": _kolor("#56666F"), "textSize": _literal("10D")})
    w.ustaw("items", {"textSize": _literal("11D")})
    if jeden:
        w.ustaw("selection", {"singleSelect": _literal("true")})
    return w


def _fragmentatory():
    pola = (("Rok", "Rok"), ("Sezon", "Sezon"), ("TypDnia", "Typ dnia"))
    return [_fragmentator(20 + i * 180, 80, 172, "Dim_Kalendarz", kolumna, etykieta)
            for i, (kolumna, etykieta) in enumerate(pola)]


def _karta(x, y, szer, tabela, miara, etykieta, wys=88):
    """Karta KPI: wartość bez skracania (np. 19 054 zamiast 19 tys.) i etykieta pod spodem."""
    w = Wizualizacja("card", x, y, szer, wys).miara("Values", tabela, miara, etykieta=etykieta)
    w.ustaw("labels", {"fontSize": _literal("22D"), "labelDisplayUnits": _literal("1D"),
                       "color": _kolor("#16232B")})
    w.ustaw("categoryLabels", {"show": _literal("true"), "fontSize": _literal("10D"), "color": _kolor("#56666F")})
    return w


def _karty(elementy, x=560, szer=172):
    return [_karta(x + i * (szer + 8), 80, szer, t, m, e) for i, (t, m, e) in enumerate(elementy)]


def _mapa_ciepla(w, tabela, miara, kolory=("#9ec5f4", "#f0efec", "#f08a7e")):
    """Formatowanie warunkowe tła komórek macierzy (gradient trzech kolorów)."""
    miara_wyr = {"Measure": {"Expression": {"SourceRef": {"Entity": tabela}}, "Property": miara}}
    gradient = {"linearGradient3": {
        "min": {"color": {"Literal": {"Value": f"'{kolory[0]}'"}}},
        "mid": {"color": {"Literal": {"Value": f"'{kolory[1]}'"}}},
        "max": {"color": {"Literal": {"Value": f"'{kolory[2]}'"}}},
        "nullColoringStrategy": {"strategy": {"Literal": {"Value": "'asZero'"}}}}}
    w.ustaw("values", {"backColor": {"solid": {"color": {"expr": {"FillRule": {"Input": miara_wyr,
                                                                              "FillRule": gradient}}}}}},
            {"data": [{"dataViewWildcard": {"matchingOption": 1}}], "metadata": f"{tabela}.{miara}"})
    w.ustaw("subTotals", {"rowSubtotals": _literal("false"), "columnSubtotals": _literal("false")})
    return w


def strony_raportu():
    strony = []
    dol = DOL_STRONY
    g = GORA_WYKRESOW

    # 1. Przegląd KSE ----------------------------------------------------------
    w = [_naglowek("Przegląd Krajowego Systemu Elektroenergetycznego",
                   "Zapotrzebowanie, struktura wytwarzania i udział OZE · dane PSE, ENTSO-E, RDN"),
         *_fragmentatory(),
         *_karty([("Fakt_KSE_Godzinowy", "Średnie zapotrzebowanie (MW)", "Zapotrzebowanie [MW]"),
                  ("Fakt_Miks", "Udział OZE w produkcji (%)", "Udział OZE w produkcji"),
                  ("Fakt_KSE_Godzinowy", "Średnia cena (PLN/MWh)", "Cena RDN [PLN/MWh]"),
                  ("Fakt_KSE_Godzinowy", "Godziny z ceną ujemną", "Godziny z ceną ujemną")])]
    w.append(Wizualizacja("stackedAreaChart", 20, g, 820, dol - g, "Średnia generacja według grup paliw (MW)")
             .pole("Category", "Dim_Kalendarz", "PoczatekMiesiaca", etykieta="Miesiąc")
             .pole("Series", "Dim_Zrodlo", "Grupa", etykieta="Grupa paliw")
             .miara("Y", "Fakt_Miks", "Średnia generacja (MW)")
             .kolory_wartosci("Dim_Zrodlo", "Grupa", KOLORY_MIKSU))
    srodek = g + (dol - g) // 2
    w.append(Wizualizacja("clusteredColumnChart", 850, g, 410, srodek - g - 5, "Udział OZE w produkcji energii")
             .pole("Category", "Dim_Kalendarz", "Rok").miara("Y", "Fakt_Miks", "Udział OZE w produkcji (%)")
             .ustaw("labels", {"show": _literal("true")}))
    w.append(Wizualizacja("clusteredBarChart", 850, srodek + 5, 410, dol - srodek - 5, "Udział grup paliw w produkcji")
             .pole("Category", "Dim_Zrodlo", "Grupa", etykieta="Grupa paliw")
             .miara("Y", "Fakt_Miks", "Udział w produkcji (%)")
             .sortuj("Fakt_Miks", "Udział w produkcji (%)", miara=True)
             .ustaw("labels", {"show": _literal("true")}))
    strony.append(("Przegląd KSE", w))

    # 2. Pogoda a system -------------------------------------------------------
    w = [_naglowek("Pogoda a system elektroenergetyczny",
                   "P1 – zapotrzebowanie a temperatura i kalendarz · P2 – generacja OZE a warunki pogodowe"),
         *_fragmentatory(),
         *_karty([("Fakt_KSE_Godzinowy", "Średnia temperatura (°C)", "Średnia temperatura [°C]"),
                  ("Fakt_KSE_Godzinowy", "Średnia prędkość wiatru (m/s)", "Wiatr na 100 m [m/s]"),
                  ("Fakt_KSE_Godzinowy", "Średnia generacja PV (MW)", "Generacja PV [MW]"),
                  ("Fakt_KSE_Godzinowy", "Średnia generacja wiatrowa (MW)", "Generacja wiatrowa [MW]")])]
    srodek = g + 270
    w.append(Wizualizacja("scatterChart", 20, g, 620, srodek - g - 5, "Zapotrzebowanie a temperatura (średnie dobowe)")
             .pole("Category", "Dim_Kalendarz", "Data").pole("Series", "Dim_Kalendarz", "TypDnia", etykieta="Typ dnia")
             .miara("X", "Fakt_KSE_Godzinowy", "Średnia temperatura (°C)")
             .miara("Y", "Fakt_KSE_Godzinowy", "Średnie zapotrzebowanie (MW)"))
    w.append(_mapa_ciepla(
        Wizualizacja("pivotTable", 650, g, 610, srodek - g - 5, "Średnie zapotrzebowanie (MW): godzina × dzień tygodnia")
        .pole("Rows", "Dim_Godzina", "Godzina").pole("Columns", "Dim_Kalendarz", "DzienTygodnia")
        .miara("Values", "Fakt_KSE_Godzinowy", "Średnie zapotrzebowanie (MW)"),
        "Fakt_KSE_Godzinowy", "Średnie zapotrzebowanie (MW)", ("#F6F8F9", "#9ec5f4", "#3987e5")))
    w.append(Wizualizacja("scatterChart", 20, srodek + 5, 620, dol - srodek - 5,
                          "Generacja wiatrowa a prędkość wiatru (średnie dobowe)")
             .pole("Category", "Dim_Kalendarz", "Data").pole("Series", "Dim_Kalendarz", "Rok")
             .miara("X", "Fakt_KSE_Godzinowy", "Średnia prędkość wiatru (m/s)")
             .miara("Y", "Fakt_KSE_Godzinowy", "Średnia generacja wiatrowa (MW)"))
    w.append(Wizualizacja("tableEx", 650, srodek + 5, 610, dol - srodek - 5, "Warunki pogodowe w lokalizacjach")
             .pole("Values", "Dim_Lokalizacja", "Miasto").pole("Values", "Dim_Lokalizacja", "Wojewodztwo",
                                                               etykieta="Województwo")
             .miara("Values", "Fakt_Pogoda_Stacje", "Temperatura w stacji (°C)", etykieta="Temperatura [°C]")
             .miara("Values", "Fakt_Pogoda_Stacje", "Wiatr w stacji (m/s)", etykieta="Wiatr [m/s]")
             .miara("Values", "Fakt_Pogoda_Stacje", "Promieniowanie w stacji (W/m²)", etykieta="Promieniowanie [W/m²]"))
    strony.append(("Pogoda a system", w))

    # 3. Rynek energii ---------------------------------------------------------
    w = [_naglowek("Rynek energii", "P3 – ceny Rynku Dnia Następnego a generacja z OZE (efekt merit order)"),
         *_fragmentatory(),
         *_karty([("Fakt_KSE_Godzinowy", "Średnia cena (PLN/MWh)", "Cena RDN [PLN/MWh]"),
                  ("Fakt_KSE_Godzinowy", "Minimalna cena (PLN/MWh)", "Cena minimalna [PLN/MWh]"),
                  ("Fakt_KSE_Godzinowy", "Godziny z ceną ujemną", "Godziny z ceną ujemną"),
                  ("Fakt_KSE_Godzinowy", "Średni udział OZE godzinowy (%)", "Średni udział OZE")])]
    srodek = g + 270
    w.append(_mapa_ciepla(
        Wizualizacja("pivotTable", 20, g, 620, dol - g, "Średnia cena (PLN/MWh): godzina × miesiąc")
        .pole("Rows", "Dim_Godzina", "Godzina").pole("Columns", "Dim_Kalendarz", "Miesiac", etykieta="Miesiąc")
        .miara("Values", "Fakt_KSE_Godzinowy", "Średnia cena (PLN/MWh)"),
        "Fakt_KSE_Godzinowy", "Średnia cena (PLN/MWh)"))
    w.append(Wizualizacja("scatterChart", 650, g, 610, srodek - g - 5, "Cena a udział OZE (średnie dobowe)")
             .pole("Category", "Dim_Kalendarz", "Data").pole("Series", "Dim_Kalendarz", "Sezon")
             .miara("X", "Fakt_KSE_Godzinowy", "Średni udział OZE godzinowy (%)")
             .miara("Y", "Fakt_KSE_Godzinowy", "Średnia cena (PLN/MWh)"))
    w.append(Wizualizacja("clusteredColumnChart", 650, srodek + 5, 610, dol - srodek - 5, "Liczba godzin z ceną ujemną")
             .pole("Category", "Dim_Kalendarz", "Rok").miara("Y", "Fakt_KSE_Godzinowy", "Godziny z ceną ujemną")
             .ustaw("labels", {"show": _literal("true")}))
    strony.append(("Rynek energii", w))

    # 4. Prognoza zapotrzebowania ----------------------------------------------
    w = [_naglowek("Prognoza zapotrzebowania",
                   "P4 – model uczenia maszynowego a prognoza PSE · zbiór testowy 01.01–30.09.2026")]
    w += [_karta(20 + i * 188, 80, 180, "Fakt_Prognoza", m, e) for i, (m, e) in enumerate([
        ("MAPE modelu (%)", "MAPE modelu ML"), ("MAPE PSE (%)", "MAPE prognozy PSE"),
        ("MAPE prognozy naiwnej (%)", "MAPE prognozy naiwnej"), ("MAE modelu (MW)", "MAE modelu ML [MW]"),
        ("MAE PSE (MW)", "MAE prognozy PSE [MW]")])]
    w.append(_fragmentator(960, 80, 300, "Dim_Kalendarz", "RokMiesiac", "Miesiąc"))
    srodek = g + 290
    w.append(Wizualizacja("lineChart", 20, g, 820, srodek - g - 5, "Średnie dobowe zapotrzebowanie i prognozy (MW)")
             .pole("Category", "Dim_Kalendarz", "Data")
             .miara("Y", "Fakt_Prognoza", "Zapotrzebowanie rzeczywiste (MW)", etykieta="Rzeczywiste")
             .miara("Y", "Fakt_Prognoza", "Prognoza PSE (MW)", etykieta="Prognoza PSE")
             .miara("Y", "Fakt_Prognoza", "Prognoza modelu (MW)", etykieta="Model ML")
             .kolory_miar("Fakt_Prognoza", {"Zapotrzebowanie rzeczywiste (MW)": TUSZ,
                                            "Prognoza PSE (MW)": POMARANCZOWY, "Prognoza modelu (MW)": NIEBIESKI}))
    w.append(Wizualizacja("clusteredBarChart", 850, g, 410, srodek - g - 5, "Ważność cech modelu (wzrost MAE, MW)")
             .pole("Category", "Waznosc_Cech", "NazwaCechy", etykieta="Cecha")
             .miara("Y", "Waznosc_Cech", "Ważność cechy (MW)")
             .sortuj("Waznosc_Cech", "Ważność cechy (MW)", miara=True)
             .ustaw("categoryAxis", {"maxMarginFactor": _literal("50L")}))
    w.append(Wizualizacja("lineChart", 20, srodek + 5, 560, dol - srodek - 5, "MAPE według godziny doby")
             .pole("Category", "Dim_Godzina", "Godzina")
             .miara("Y", "Fakt_Prognoza", "MAPE modelu (%)", etykieta="Model ML")
             .miara("Y", "Fakt_Prognoza", "MAPE PSE (%)", etykieta="Prognoza PSE")
             .kolory_miar("Fakt_Prognoza", {"MAPE modelu (%)": NIEBIESKI, "MAPE PSE (%)": POMARANCZOWY}))
    w.append(_fragmentator(590, srodek + 5, 250, "Parametr_Temperatura", "Zmiana_C",
                           "Symulacja: zmiana temperatury [°C]", jeden=True))
    w.append(_karta(590, srodek + 103, 250, "Fakt_Symulacja", "Zmiana zapotrzebowania (%)",
                    "Zmiana średniego zapotrzebowania", wys=dol - srodek - 103))
    w.append(Wizualizacja("lineChart", 850, srodek + 5, 410, dol - srodek - 5, "Symulacja what-if: profil dobowy (MW)")
             .pole("Category", "Dim_Godzina", "Godzina")
             .miara("Y", "Fakt_Symulacja", "Prognoza bazowa (MW)", etykieta="Temperatura rzeczywista")
             .miara("Y", "Fakt_Symulacja", "Prognoza przy zmianie temperatury (MW)", etykieta="Po zmianie temperatury")
             .kolory_miar("Fakt_Symulacja", {"Prognoza bazowa (MW)": NIEBIESKI,
                                             "Prognoza przy zmianie temperatury (MW)": POMARANCZOWY}))
    strony.append(("Prognoza", w))

    # 5. Profile dobowe --------------------------------------------------------
    w = [_naglowek("Typowe profile dobowe",
                   "P5 – klasteryzacja K-means dobowych przebiegów zapotrzebowania i cen (k = 4)")]
    srodek = 430
    w.append(Wizualizacja("lineChart", 20, 80, 620, srodek - 85, "Profile zapotrzebowania (MW)")
             .pole("Category", "Klastry_Zapotrzebowanie_Profile", "Godzina")
             .pole("Series", "Klastry_Zapotrzebowanie_Profile", "NazwaKlastra", etykieta="Klaster")
             .miara("Y", "Klastry_Zapotrzebowanie_Profile", "Profil zapotrzebowania (MW)"))
    w.append(Wizualizacja("lineChart", 650, 80, 610, srodek - 85, "Profile cen (PLN/MWh)")
             .pole("Category", "Klastry_Ceny_Profile", "Godzina")
             .pole("Series", "Klastry_Ceny_Profile", "NazwaKlastra", etykieta="Klaster")
             .miara("Y", "Klastry_Ceny_Profile", "Profil ceny (PLN/MWh)"))
    w.append(Wizualizacja("pivotTable", 20, srodek + 5, 620, dol - srodek - 5, "Liczba dób w klastrach zapotrzebowania")
             .pole("Rows", "Klastry_Zapotrzebowanie_Doby", "NazwaKlastra", etykieta="Klaster")
             .pole("Columns", "Dim_Kalendarz", "TypDnia", etykieta="Typ dnia")
             .miara("Values", "Klastry_Zapotrzebowanie_Doby", "Liczba dób"))
    w.append(Wizualizacja("tableEx", 650, srodek + 5, 610, dol - srodek - 5, "Porównanie modeli (zbiór testowy 2026)")
             .pole("Values", "Metryki_Modeli", "Model")
             .pole("Values", "Metryki_Modeli", "MAPE_proc", etykieta="MAPE [%]")
             .pole("Values", "Metryki_Modeli", "MAE_MW", etykieta="MAE [MW]")
             .pole("Values", "Metryki_Modeli", "RMSE_MW", etykieta="RMSE [MW]")
             .sortuj("Metryki_Modeli", "MAPE_proc", malejaco=False))
    strony.append(("Profile dobowe", w))
    return strony


def zbuduj_raport():
    Wizualizacja.licznik = 0
    sekcje = []
    for nr, (nazwa, wizualizacje) in enumerate(strony_raportu()):
        sekcje.append({
            "name": f"strona{nr + 1}", "displayName": nazwa, "displayOption": 1, "width": 1280, "height": 720,
            "ordinal": nr, "config": json.dumps({"objects": {"background": [{"properties": {
                "color": _kolor("#F6F8F9"), "transparency": _literal("0D")}}]}}),
            "filters": "[]", "visualContainers": [w.kontener() for w in wizualizacje],
        })
    konfiguracja = {
        "version": "5.43",
        # motyw własny zarejestrowany w zasobach raportu (RegisteredResources: pakiet typu 1, plik typu 201)
        "themeCollection": {"customTheme": {"name": "KSE.json", "version": "5.43", "type": 1}},
        "activeSectionIndex": 0,
        "defaultDrillFilterOtherVisuals": True,
        "settings": {"useStylableVisualContainerHeader": True, "exportDataMode": 1},
    }
    return {
        "config": json.dumps(konfiguracja),
        "layoutOptimization": 0,
        "resourcePackages": [{"resourcePackage": {
            "name": "RegisteredResources", "type": 1, "disabled": False,
            "items": [{"type": 201, "path": "KSE.json", "name": "KSE.json"}]}}],
        "sections": sekcje,
    }


def motyw():
    return {
        "name": "KSE",
        "dataColors": KOLORY,
        "background": "#FFFFFF", "foreground": "#16232B", "tableAccent": "#0B4F6C",
        "textClasses": {
            "title": {"fontFace": "Segoe UI Semibold", "fontSize": 11, "color": "#16232B"},
            "label": {"fontFace": "Segoe UI", "fontSize": 10, "color": "#52514e"},
            "callout": {"fontFace": "Segoe UI Semibold", "fontSize": 22, "color": "#16232B"},
        },
    }


def _zapisz_json(sciezka, dane):
    sciezka.parent.mkdir(parents=True, exist_ok=True)
    sciezka.write_text(json.dumps(dane, ensure_ascii=False, indent=2), encoding="utf-8")


def generuj():
    _zapisz_json(KATALOG_PBI / f"{NAZWA}.pbip", {
        "version": "1.0",
        "artifacts": [{"report": {"path": f"{NAZWA}.Report"}}],
        "settings": {"enableAutoRecovery": True},
    })
    model = KATALOG_PBI / f"{NAZWA}.SemanticModel"
    _zapisz_json(model / "definition.pbism", {"version": "1.0", "settings": {}})
    _zapisz_json(model / "model.bim", zbuduj_model())

    raport = KATALOG_PBI / f"{NAZWA}.Report"
    # Power BI Desktop przy zapisie może dodać kopię raportu w nowym formacie (folder definition/);
    # źródłem raportu jest report.json, więc kopia jest usuwana, aby nie powodowała konfliktu
    shutil.rmtree(raport / "definition", ignore_errors=True)
    _zapisz_json(raport / "definition.pbir", {
        "version": "1.0", "datasetReference": {"byPath": {"path": f"../{NAZWA}.SemanticModel"}, "byConnection": None}})
    _zapisz_json(raport / "report.json", zbuduj_raport())
    _zapisz_json(raport / "StaticResources" / "RegisteredResources" / "KSE.json", motyw())
    (KATALOG_PBI / ".gitignore").write_text("**/.pbi/localSettings.json\n**/.pbi/cache.abf\n", encoding="utf-8")
    print(f"Projekt Power BI zapisany w: {KATALOG_PBI / (NAZWA + '.pbip')}")


if __name__ == "__main__":
    generuj()
