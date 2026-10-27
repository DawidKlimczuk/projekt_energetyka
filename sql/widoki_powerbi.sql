-- =============================================================================
-- Widoki raportowe dla Power BI (prefiks pbi_).
--
-- Każdy widok odpowiada jednej tabeli modelu danych Power BI (schemat gwiazdy).
-- Fakty otrzymują datę i godzinę czasu lokalnego (klucze do Dim_Kalendarz i Dim_Godzina),
-- nazwy kolumn są dostosowane do prezentacji w raporcie.
-- =============================================================================
DROP VIEW IF EXISTS pbi_dim_kalendarz;
DROP VIEW IF EXISTS pbi_dim_godzina;
DROP VIEW IF EXISTS pbi_dim_zrodlo;
DROP VIEW IF EXISTS pbi_dim_lokalizacja;
DROP VIEW IF EXISTS pbi_fakt_kse_godzinowy;
DROP VIEW IF EXISTS pbi_fakt_miks;
DROP VIEW IF EXISTS pbi_fakt_pogoda_stacje;
DROP VIEW IF EXISTS pbi_fakt_prognoza;
DROP VIEW IF EXISTS pbi_fakt_symulacja;
DROP VIEW IF EXISTS pbi_klastry_zapotrzebowanie_doby;
DROP VIEW IF EXISTS pbi_klastry_zapotrzebowanie_profile;
DROP VIEW IF EXISTS pbi_klastry_ceny_doby;
DROP VIEW IF EXISTS pbi_klastry_ceny_profile;
DROP VIEW IF EXISTS pbi_waznosc_cech;
DROP VIEW IF EXISTS pbi_metryki_modeli;

-- -----------------------------------------------------------------------------
-- Wymiary
-- -----------------------------------------------------------------------------
CREATE VIEW pbi_dim_kalendarz AS
SELECT data AS Data, rok AS Rok, kwartal AS Kwartal, miesiac AS MiesiacNr, miesiac_nazwa AS Miesiac,
       rok_miesiac AS RokMiesiac, poczatek_miesiaca AS PoczatekMiesiaca,
       dzien_tygodnia + 1 AS DzienTygodniaNr, dzien_tygodnia_nazwa AS DzienTygodnia,
       sezon AS Sezon, typ_dnia AS TypDnia, nazwa_swieta AS NazwaSwieta
FROM dim_kalendarz;

CREATE VIEW pbi_dim_godzina AS
SELECT godzina AS Godzina, przedzial AS Przedzial, pora_dnia AS PoraDnia
FROM dim_godzina;

CREATE VIEW pbi_dim_zrodlo AS
SELECT kod_zrodla AS KodZrodla, nazwa_zrodla AS NazwaZrodla, kategoria AS Kategoria, grupa AS Grupa
FROM dim_zrodlo;

CREATE VIEW pbi_dim_lokalizacja AS
SELECT id_stacji AS IdStacji, miasto AS Miasto, wojewodztwo AS Wojewodztwo,
       szerokosc AS Szerokosc, dlugosc AS Dlugosc,
       ludnosc_wojewodztwa_mln AS LudnoscWojewodztwa_mln, udzial_mocy_wiatrowej AS UdzialMocyWiatrowej
FROM dim_lokalizacja;

-- -----------------------------------------------------------------------------
-- Fakty
-- -----------------------------------------------------------------------------
CREATE VIEW pbi_fakt_kse_godzinowy AS
SELECT c.czas_lokalny AS CzasLokalny, c.data AS Data, c.godzina AS Godzina,
       f.zapotrzebowanie_mw AS Zapotrzebowanie_MW, f.prognoza_pse_mw AS Prognoza_PSE_MW,
       f.generacja_wiatr_mw AS Generacja_Wiatr_MW, f.generacja_pv_mw AS Generacja_PV_MW,
       f.zapotrzebowanie_netto_mw AS Zapotrzebowanie_Netto_MW, f.generacja_calkowita_mw AS Generacja_Calkowita_MW,
       f.udzial_oze_proc AS Udzial_OZE_proc, f.udzial_wegla_proc AS Udzial_Wegla_proc,
       f.cena_pln_mwh AS Cena_PLN_MWh, f.temperatura_c AS Temperatura_C, f.wiatr_100m_ms AS Wiatr_100m_ms,
       f.promieniowanie_wm2 AS Promieniowanie_Wm2, f.zachmurzenie_proc AS Zachmurzenie_proc
FROM fakt_kse_godzinowy AS f
JOIN dim_czas AS c ON c.czas_utc = f.czas_utc;

CREATE VIEW pbi_fakt_miks AS
SELECT c.data AS Data, c.godzina AS Godzina, m.kod_zrodla AS KodZrodla, m.generacja_mw AS Generacja_MW
FROM fakt_miks AS m
JOIN dim_czas AS c ON c.czas_utc = m.czas_utc;

CREATE VIEW pbi_fakt_pogoda_stacje AS
SELECT c.data AS Data, c.godzina AS Godzina, p.id_stacji AS IdStacji,
       p.temperatura_c AS Temperatura_C, p.wiatr_100m_ms AS Wiatr_100m_ms,
       p.promieniowanie_wm2 AS Promieniowanie_Wm2, p.zachmurzenie_proc AS Zachmurzenie_proc
FROM fakt_pogoda_stacje AS p
JOIN dim_czas AS c ON c.czas_utc = p.czas_utc;

-- prognozy z formatu długiego przekształcone do kolumn (agregacja warunkowa)
CREATE VIEW pbi_fakt_prognoza AS
SELECT c.czas_lokalny AS CzasLokalny, c.data AS Data, c.godzina AS Godzina,
       f.zapotrzebowanie_mw AS Rzeczywiste_MW,
       MAX(CASE WHEN p.model = 'Prognoza PSE' THEN p.prognoza_mw END) AS Prognoza_PSE_MW,
       MAX(CASE WHEN p.model = 'Prognoza naiwna (tydzień wcześniej)' THEN p.prognoza_mw END) AS Prognoza_Naiwna_MW,
       MAX(CASE WHEN p.model = (SELECT model FROM v_najlepszy_model) THEN p.prognoza_mw END) AS Prognoza_Model_MW
FROM prognozy_test AS p
JOIN fakt_kse_godzinowy AS f ON f.czas_utc = p.czas_utc
JOIN dim_czas AS c ON c.czas_utc = p.czas_utc
GROUP BY p.czas_utc, c.czas_lokalny, c.data, c.godzina, f.zapotrzebowanie_mw;

CREATE VIEW pbi_fakt_symulacja AS
SELECT c.data AS Data, c.godzina AS Godzina, s.zmiana_c AS Zmiana_C, s.prognoza_mw AS Prognoza_MW
FROM symulacja_temperatury AS s
JOIN dim_czas AS c ON c.czas_utc = s.czas_utc;

-- -----------------------------------------------------------------------------
-- Wyniki analiz
-- -----------------------------------------------------------------------------
CREATE VIEW pbi_klastry_zapotrzebowanie_doby AS
SELECT data AS Data, klaster AS Klaster, nazwa_klastra AS NazwaKlastra
FROM v_klastry_doby WHERE zmienna = 'zapotrzebowanie';

CREATE VIEW pbi_klastry_zapotrzebowanie_profile AS
SELECT klaster AS Klaster, godzina AS Godzina, wartosc AS Wartosc, nazwa_klastra AS NazwaKlastra
FROM v_klastry_profile WHERE zmienna = 'zapotrzebowanie';

CREATE VIEW pbi_klastry_ceny_doby AS
SELECT data AS Data, klaster AS Klaster, nazwa_klastra AS NazwaKlastra
FROM v_klastry_doby WHERE zmienna = 'ceny';

CREATE VIEW pbi_klastry_ceny_profile AS
SELECT klaster AS Klaster, godzina AS Godzina, wartosc AS Wartosc, nazwa_klastra AS NazwaKlastra
FROM v_klastry_profile WHERE zmienna = 'ceny';

CREATE VIEW pbi_waznosc_cech AS
SELECT cecha AS Cecha, nazwa AS NazwaCechy, wzrost_mae_mw AS WzrostMAE_MW, odchylenie AS Odchylenie
FROM waznosc_cech;

CREATE VIEW pbi_metryki_modeli AS
SELECT model AS Model, mape_proc AS MAPE_proc, mae_mw AS MAE_MW, rmse_mw AS RMSE_MW
FROM metryki_modeli;
