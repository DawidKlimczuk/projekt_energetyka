@echo off
chcp 65001 >nul
title Pogoda, OZE i cena prądu – aplikacja
cd /d "%~dp0"

rem Uruchamia aplikację analityczną projektu w przeglądarce.
rem Przy pierwszym uruchomieniu tworzy środowisko wirtualne i instaluje biblioteki. Środowisko
rem zapisywane jest poza folderem projektu (%LOCALAPPDATA%\ProjektKSE), aby nie było
rem synchronizowane przez OneDrive
rem (wymagany Python 3.12 lub nowszy dostępny jako polecenie "python" lub "py").

set VENV=%LOCALAPPDATA%\ProjektKSE\venv
set PYTHON=
where py >nul 2>nul && set PYTHON=py -3
if not defined PYTHON where python >nul 2>nul && set PYTHON=python
if not defined PYTHON (
    echo Nie znaleziono Pythona. Zainstaluj Python 3.12+ ze strony https://www.python.org/downloads/
    echo i zaznacz opcję "Add python.exe to PATH".
    pause
    exit /b 1
)

if not exist "data\kse.db" (
    echo Brak bazy danych data\kse.db. Uruchom najpierw: python run_pipeline.py
    pause
    exit /b 1
)

if not exist "%VENV%\Scripts\python.exe" (
    echo Pierwsze uruchomienie: przygotowanie środowiska i instalacja bibliotek ^(kilka minut^)...
    %PYTHON% -m venv "%VENV%" || goto blad
    "%VENV%\Scripts\python.exe" -m pip install --upgrade pip --quiet
    "%VENV%\Scripts\python.exe" -m pip install -r app\requirements.txt --quiet || goto blad
)

echo Uruchamianie aplikacji – przeglądarka otworzy się automatycznie.
echo Aby zakończyć pracę aplikacji, zamknij to okno.
rem przegladarka otwierana po chwili, gdy serwer juz dziala (tryb headless pomija pytania Streamlit w konsoli)
start "" /min cmd /c "timeout /t 5 /nobreak >nul & start http://localhost:8501"
"%VENV%\Scripts\python.exe" -m streamlit run app\app.py --server.headless true --server.port 8501
exit /b 0

:blad
echo.
echo Wystąpił błąd podczas instalacji bibliotek. Usuń folder %VENV% i spróbuj ponownie.
pause
exit /b 1
