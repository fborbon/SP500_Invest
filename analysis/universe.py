from io import StringIO

import pandas as pd
import requests

from config import FALLBACK_TICKERS

_HEADERS = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36'}


def get_sp500_tickers(n: int = None) -> list:
    """Return S&P 500 tickers sorted by market cap (index weight).

    Args:
        n: Number of top companies by market cap to return.
           None = all constituents (~503).

    Sources tried in order:
      1. slickcharts.com  — already ranked by S&P 500 weight (≈ market cap).
      2. Wikipedia        — fallback, alphabetical order (warns user).
      3. FALLBACK_TICKERS — hardcoded top-20 when both sources fail.
    """
    tickers = _fetch_sorted_tickers()

    total = len(tickers)
    if n is not None:
        tickers = tickers[:n]
        print(f"  → Seleccionados top {n} de {total} por capitalización de mercado")
    else:
        print(f"  → Usando los {total} tickers del S&P 500")

    return tickers


def _fetch_sorted_tickers() -> list:
    # ── 1. slickcharts — sorted by portfolio weight (≈ market cap) ──
    try:
        resp = requests.get('https://slickcharts.com/sp500', headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        table = pd.read_html(StringIO(resp.text))[0]
        tickers = table['Symbol'].str.strip().tolist()
        print(f"  ✓ {len(tickers)} tickers obtenidos de slickcharts (orden por capitalización)")
        return tickers
    except Exception as e:
        print(f"  ✗ slickcharts no disponible ({e}), intentando Wikipedia...")

    # ── 2. Wikipedia — alphabetical, not sorted by market cap ────────
    try:
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        resp = requests.get(url, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        table = pd.read_html(StringIO(resp.text), attrs={'id': 'constituents'})[0]
        tickers = table['Symbol'].tolist()
        print(f"  ✓ {len(tickers)} tickers obtenidos de Wikipedia")
        print("  ⚠ Wikipedia no ordena por capitalización — el parámetro n no garantiza las N mayores.")
        return tickers
    except Exception as e:
        print(f"  ✗ Wikipedia no disponible ({e}). Usando lista de respaldo.")
        return list(FALLBACK_TICKERS)
