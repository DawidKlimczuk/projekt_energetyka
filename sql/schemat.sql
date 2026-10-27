-- =============================================================================
-- Baza danych projektu „Pogoda, OZE i cena prądu” (SQLite)
--
-- Model danych: schemat gwiazdy.
--   * wymiary (dim_*)  – kalendarz, godzina doby, czas, źródło wytwarzania, lokalizacja,
--   * fakty (fakt_*)   – pomiary godzinowe KSE, miks wytwarzania, pogoda w lokalizacjach,
--   * wyniki analiz    – prognozy, metryki modeli, ważność cech, klasteryzacja, symulacja.
-- Wspólny klucz czasu: czas_utc = początek godziny w UTC (tekst „RRRR-MM-DD GG:MM:SS”).
-- Czas lokalny i data kalendarzowa przypisane są do czasu UTC w tabeli dim_czas.
--
-- Skrypt tworzy bazę od nowa (usuwa istniejące obiekty).
-- =============================================================================
PRAGMA foreign_keys = OFF;

DROP VIEW IF EXISTS v_kse_godzinowy;
DROP VIEW IF EXISTS v_miks_grupy;
DROP VIEW IF EXISTS v_prognozy_test;
DROP VIEW IF EXISTS v_najlepszy_model;
DROP VIEW IF EXISTS v_klastry_doby;
DROP VIEW IF EXISTS v_klastry_profile;

DROP TABLE IF EXISTS symulacja_temperatury;
DROP TABLE IF EXISTS prognozy_test;
DROP TABLE IF EXISTS metryki_modeli;
DROP TABLE IF EXISTS walidacja_krzyzowa;
DROP TABLE IF EXISTS waznosc_cech;
DROP TABLE IF EXISTS klastry_doby;
DROP TABLE IF EXISTS klastry_profile;
DROP TABLE IF EXISTS klastry_opis;
DROP TABLE IF EXISTS klastry_sylwetka;
DROP TABLE IF EXISTS jakosc_danych;
DROP TABLE IF EXISTS fakt_pogoda_stacje;
DROP TABLE IF EXISTS fakt_miks;
DROP TABLE IF EXISTS fakt_kse_godzinowy;
DROP TABLE IF EXISTS dim_czas;
DROP TABLE IF EXISTS dim_lokalizacja;
DROP TABLE IF EXISTS dim_zrodlo;
DROP TABLE IF EXISTS dim_godzina;
DROP TABLE IF EXISTS dim_kalendarz;

PRAGMA foreign_keys = ON;

-- -----------------------------------------------------------------------------
-- Wymiary
-- -----------------------------------------------------------------------------
CREATE TABLE dim_kalendarz (
    data                  TEXT PRIMARY KEY,           -- RRRR-MM-DD
    rok                   INTEGER NOT NULL,
    kwartal               TEXT NOT NULL,              -- Q1–Q4
    miesiac               INTEGER NOT NULL,           -- 1–12
    miesiac_nazwa         TEXT NOT NULL,
    rok_miesiac           TEXT NOT NULL,              -- RRRR-MM
    poczatek_miesiaca     TEXT NOT NULL,              -- pierwszy dzień miesiąca (oś czasu w raportach)
    dzien_tygodnia        INTEGER NOT NULL,           -- 0 = poniedziałek … 6 = niedziela
    dzien_tygodnia_nazwa  TEXT NOT NULL,
    swieto                INTEGER NOT NULL CHECK (swieto IN (0, 1)),
    weekend               INTEGER NOT NULL CHECK (weekend IN (0, 1)),
    dzien_pomostowy       INTEGER NOT NULL CHECK (dzien_pomostowy IN (0, 1)),
    typ_dnia              TEXT NOT NULL CHECK (typ_dnia IN ('roboczy', 'weekend', 'święto', 'pomostowy')),
    sezon                 TEXT NOT NULL CHECK (sezon IN ('zima', 'wiosna', 'lato', 'jesień')),
    nazwa_swieta          TEXT
);

CREATE TABLE dim_godzina (
    godzina    INTEGER PRIMARY KEY CHECK (godzina BETWEEN 0 AND 23),
    przedzial  TEXT NOT NULL,                         -- np. 07:00–08:00
    pora_dnia  TEXT NOT NULL
);

CREATE TABLE dim_czas (
    czas_utc     TEXT PRIMARY KEY,
    czas_lokalny TEXT NOT NULL,                       -- czas polski (CET/CEST)
    data         TEXT NOT NULL REFERENCES dim_kalendarz (data),
    godzina      INTEGER NOT NULL REFERENCES dim_godzina (godzina)
);
CREATE INDEX ix_dim_czas_data ON dim_czas (data);

CREATE TABLE dim_zrodlo (
    kod_zrodla    TEXT PRIMARY KEY,                   -- kod typu wytwarzania ENTSO-E (B01–B20)
    nazwa_zrodla  TEXT NOT NULL,
    kategoria     TEXT NOT NULL CHECK (kategoria IN ('OZE', 'konwencjonalne', 'magazynowanie')),
    grupa         TEXT NOT NULL                       -- grupa paliw prezentowana na wykresach
);

CREATE TABLE dim_lokalizacja (
    id_stacji                TEXT PRIMARY KEY,
    miasto                   TEXT NOT NULL,
    wojewodztwo              TEXT NOT NULL,
    szerokosc                REAL NOT NULL,
    dlugosc                  REAL NOT NULL,
    ludnosc_wojewodztwa_mln  REAL NOT NULL,           -- waga temperatury
    udzial_mocy_wiatrowej    REAL NOT NULL            -- waga prędkości wiatru
);

-- -----------------------------------------------------------------------------
-- Fakty
-- -----------------------------------------------------------------------------
CREATE TABLE fakt_kse_godzinowy (
    czas_utc                  TEXT PRIMARY KEY REFERENCES dim_czas (czas_utc),
    zapotrzebowanie_mw        REAL,
    generacja_wiatr_mw        REAL,
    generacja_pv_mw           REAL,
    prognoza_sieci_pse_mw     REAL,                   -- archiwalny plan dobowy PSE (do 13.06.2024)
    prognoza_pse_mw           REAL,                   -- prognoza zapotrzebowania PSE (od 14.06.2024)
    cena_pln_mwh              REAL,
    temperatura_c             REAL,                   -- średnia ważona liczbą ludności
    wiatr_100m_ms             REAL,                   -- średnia ważona mocą farm wiatrowych
    promieniowanie_wm2        REAL,
    zachmurzenie_proc         REAL,
    generacja_calkowita_mw    REAL,
    udzial_oze_proc           REAL,
    udzial_wegla_proc         REAL,
    zapotrzebowanie_netto_mw  REAL                    -- zapotrzebowanie − wiatr − PV
);

CREATE TABLE fakt_miks (
    czas_utc      TEXT NOT NULL REFERENCES dim_czas (czas_utc),
    kod_zrodla    TEXT NOT NULL REFERENCES dim_zrodlo (kod_zrodla),
    generacja_mw  REAL NOT NULL,
    PRIMARY KEY (czas_utc, kod_zrodla)
) WITHOUT ROWID;

CREATE TABLE fakt_pogoda_stacje (
    czas_utc            TEXT NOT NULL REFERENCES dim_czas (czas_utc),
    id_stacji           TEXT NOT NULL REFERENCES dim_lokalizacja (id_stacji),
    temperatura_c       REAL,
    wiatr_100m_ms       REAL,
    promieniowanie_wm2  REAL,
    zachmurzenie_proc   REAL,
    PRIMARY KEY (czas_utc, id_stacji)
) WITHOUT ROWID;

CREATE TABLE jakosc_danych (
    zmienna           TEXT PRIMARY KEY,
    liczba_godzin     INTEGER NOT NULL,
    braki_przed       INTEGER NOT NULL,               -- przed uzupełnieniem krótkich luk
    braki_po          INTEGER NOT NULL,
    kompletnosc_proc  REAL NOT NULL
);

-- -----------------------------------------------------------------------------
-- Wyniki modelu prognostycznego (P4)
-- -----------------------------------------------------------------------------
CREATE TABLE metryki_modeli (
    model      TEXT PRIMARY KEY,
    mape_proc  REAL NOT NULL,
    mae_mw     REAL NOT NULL,
    rmse_mw    REAL NOT NULL
);

-- prognozy na zbiorze testowym w formacie długim: jeden wiersz = godzina × model
CREATE TABLE prognozy_test (
    czas_utc     TEXT NOT NULL REFERENCES fakt_kse_godzinowy (czas_utc),
    model        TEXT NOT NULL REFERENCES metryki_modeli (model),
    prognoza_mw  REAL NOT NULL,
    PRIMARY KEY (czas_utc, model)
) WITHOUT ROWID;

CREATE TABLE walidacja_krzyzowa (
    fold             INTEGER NOT NULL,
    okres_walidacji  TEXT NOT NULL,
    model            TEXT NOT NULL,
    mape_proc        REAL NOT NULL,
    mae_mw           REAL NOT NULL,
    rmse_mw          REAL NOT NULL,
    PRIMARY KEY (fold, model)
);

CREATE TABLE waznosc_cech (
    cecha          TEXT PRIMARY KEY,
    nazwa          TEXT NOT NULL,
    wzrost_mae_mw  REAL NOT NULL,                     -- ważność permutacyjna
    odchylenie     REAL NOT NULL
);

-- prognozy modelu produkcyjnego przy temperaturze zmienionej o zmiana_c [°C]
CREATE TABLE symulacja_temperatury (
    czas_utc     TEXT NOT NULL REFERENCES dim_czas (czas_utc),
    zmiana_c     INTEGER NOT NULL CHECK (zmiana_c BETWEEN -10 AND 10),
    prognoza_mw  REAL NOT NULL,
    PRIMARY KEY (czas_utc, zmiana_c)
) WITHOUT ROWID;

-- -----------------------------------------------------------------------------
-- Wyniki klasteryzacji profili dobowych (P5); zmienna = 'zapotrzebowanie' lub 'ceny'
-- -----------------------------------------------------------------------------
CREATE TABLE klastry_opis (
    zmienna             TEXT NOT NULL,
    klaster             INTEGER NOT NULL,
    nazwa               TEXT NOT NULL,
    liczba_dob          INTEGER NOT NULL,
    sredni_poziom       REAL NOT NULL,
    udzial_dni_wolnych  REAL NOT NULL,
    PRIMARY KEY (zmienna, klaster)
);

CREATE TABLE klastry_doby (
    zmienna  TEXT NOT NULL,
    data     TEXT NOT NULL REFERENCES dim_kalendarz (data),
    klaster  INTEGER NOT NULL,
    poziom   REAL NOT NULL,                           -- średnia wartość w dobie
    PRIMARY KEY (zmienna, data),
    FOREIGN KEY (zmienna, klaster) REFERENCES klastry_opis (zmienna, klaster)
);

CREATE TABLE klastry_profile (
    zmienna  TEXT NOT NULL,
    klaster  INTEGER NOT NULL,
    godzina  INTEGER NOT NULL REFERENCES dim_godzina (godzina),
    wartosc  REAL NOT NULL,
    PRIMARY KEY (zmienna, klaster, godzina),
    FOREIGN KEY (zmienna, klaster) REFERENCES klastry_opis (zmienna, klaster)
);

CREATE TABLE klastry_sylwetka (
    zmienna   TEXT NOT NULL,
    k         INTEGER NOT NULL,
    sylwetka  REAL NOT NULL,
    PRIMARY KEY (zmienna, k)
);

-- -----------------------------------------------------------------------------
-- Widoki analityczne (wykorzystywane przez aplikację)
-- -----------------------------------------------------------------------------

-- zintegrowany zbiór godzinowy: pomiary + czas lokalny + zmienne kalendarzowe
CREATE VIEW v_kse_godzinowy AS
SELECT f.czas_utc,
       f.zapotrzebowanie_mw, f.generacja_wiatr_mw, f.generacja_pv_mw, f.prognoza_sieci_pse_mw,
       f.prognoza_pse_mw, f.cena_pln_mwh, f.temperatura_c, f.wiatr_100m_ms, f.promieniowanie_wm2,
       f.zachmurzenie_proc, f.generacja_calkowita_mw, f.udzial_oze_proc, f.udzial_wegla_proc,
       f.zapotrzebowanie_netto_mw,
       c.czas_lokalny, c.data, c.godzina,
       k.dzien_tygodnia, k.miesiac, k.rok, k.swieto, k.weekend, k.dzien_pomostowy, k.typ_dnia, k.sezon
FROM fakt_kse_godzinowy AS f
JOIN dim_czas AS c ON c.czas_utc = f.czas_utc
JOIN dim_kalendarz AS k ON k.data = c.data;

-- generacja zsumowana w grupach paliw
CREATE VIEW v_miks_grupy AS
SELECT m.czas_utc, c.czas_lokalny, z.grupa, SUM(m.generacja_mw) AS generacja_mw
FROM fakt_miks AS m
JOIN dim_zrodlo AS z ON z.kod_zrodla = m.kod_zrodla
JOIN dim_czas AS c ON c.czas_utc = m.czas_utc
GROUP BY m.czas_utc, c.czas_lokalny, z.grupa;

-- model uczenia maszynowego o najniższym MAPE (bez prognozy PSE i prognozy naiwnej)
CREATE VIEW v_najlepszy_model AS
SELECT model
FROM metryki_modeli
WHERE model NOT IN ('Prognoza PSE', 'Prognoza naiwna (tydzień wcześniej)')
ORDER BY mape_proc
LIMIT 1;

CREATE VIEW v_prognozy_test AS
SELECT p.czas_utc, c.czas_lokalny, f.zapotrzebowanie_mw AS rzeczywiste_mw, p.model, p.prognoza_mw
FROM prognozy_test AS p
JOIN fakt_kse_godzinowy AS f ON f.czas_utc = p.czas_utc
JOIN dim_czas AS c ON c.czas_utc = p.czas_utc;

CREATE VIEW v_klastry_doby AS
SELECT d.zmienna, d.data, d.klaster, o.nazwa AS nazwa_klastra, d.poziom,
       k.typ_dnia, k.sezon, k.dzien_tygodnia
FROM klastry_doby AS d
JOIN klastry_opis AS o ON o.zmienna = d.zmienna AND o.klaster = d.klaster
JOIN dim_kalendarz AS k ON k.data = d.data;

CREATE VIEW v_klastry_profile AS
SELECT p.zmienna, p.klaster, o.nazwa AS nazwa_klastra, p.godzina, p.wartosc
FROM klastry_profile AS p
JOIN klastry_opis AS o ON o.zmienna = p.zmienna AND o.klaster = p.klaster;
