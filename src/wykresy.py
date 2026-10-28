"""Wspólny styl wykresów matplotlib i tabel pandas wykorzystywanych w notebookach.

Kolory odpowiadają palecie aplikacji analitycznej (app/wspolne.py), dzięki czemu
wykresy w notebookach, aplikacji i raporcie końcowym są spójne.
"""
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import FuncFormatter

TUSZ = "#16232B"
TUSZ_DRUGORZEDNY = "#52514e"
TUSZ_WYCISZONY = "#898781"
SIATKA = "#e1e0d9"
OS = "#c3c2b7"

NIEBIESKI, POMARANCZOWY, MORSKI, ZOLTY = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
MAGENTA, ZIELONY, FIOLET, CZERWONY = "#e87ba4", "#008300", "#6250d6", "#e34948"
PALETA = [NIEBIESKI, POMARANCZOWY, MORSKI, ZOLTY, MAGENTA, ZIELONY, FIOLET, CZERWONY]

KOLORY_MIKSU = {
    "Węgiel kamienny": CZERWONY,
    "Węgiel brunatny": FIOLET,
    "Biomasa": ZIELONY,
    "Pozostałe": MAGENTA,
    "Fotowoltaika": ZOLTY,
    "Woda i magazyny": MORSKI,
    "Gaz ziemny": POMARANCZOWY,
    "Wiatr": NIEBIESKI,
}

# skale barw map ciepła: sekwencyjna (wartości dodatnie) i rozbieżna (wokół zera)
SKALA_SEKWENCYJNA = "Blues"
SKALA_ROZBIEZNA = "RdBu_r"

DNI = ["pon", "wt", "śr", "czw", "pt", "sob", "nd"]
MIESIACE = ["sty", "lut", "mar", "kwi", "maj", "cze", "lip", "sie", "wrz", "paź", "lis", "gru"]


def ustaw_styl():
    """Styl wykresów matplotlib oraz zapis liczb w tabelach pandas (format polski)."""
    pd.set_option("display.float_format", lambda x: _liczba(x, 2))
    pd.set_option("display.max_columns", 30)
    plt.rcParams.update({
        "figure.figsize": (11, 4.5),
        "figure.dpi": 110,
        "font.size": 10,
        "axes.edgecolor": OS,
        "axes.labelcolor": TUSZ_DRUGORZEDNY,
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
        "axes.titlecolor": TUSZ,
        "axes.titlelocation": "left",
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.prop_cycle": plt.cycler(color=PALETA),
        "grid.color": SIATKA,
        "grid.linewidth": 0.7,
        "xtick.color": TUSZ_DRUGORZEDNY,
        "ytick.color": TUSZ_DRUGORZEDNY,
        "legend.frameon": False,
        "axes.formatter.use_locale": False,
    })


def _liczba(x, miejsca=0):
    return f"{x:,.{miejsca}f}".replace(",", " ").replace(".", ",")


def format_polski(ax, os_="y", miejsca=0):
    """Etykiety osi w zapisie polskim (spacja jako separator tysięcy, przecinek dziesiętny)."""
    formatter = FuncFormatter(lambda x, _: _liczba(x, miejsca))
    (ax.yaxis if os_ == "y" else ax.xaxis).set_major_formatter(formatter)
