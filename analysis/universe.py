from io import StringIO

import pandas as pd
import requests

from config import FALLBACK_TICKERS

_HEADERS = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36'}


def get_sp500_tickers() -> list:
    """Fetch the current S&P 500 constituent tickers from Wikipedia.

    Falls back to FALLBACK_TICKERS if the request fails.
    Ticker dots are kept as-is (e.g. BRK.B) — get_contract() handles the IB format.
    """
    try:
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        resp = requests.get(url, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        table = pd.read_html(StringIO(resp.text), attrs={'id': 'constituents'})[0]
        tickers = table['Symbol'].tolist()
        print(f"  ✓ S&P 500: {len(tickers)} tickers obtenidos de Wikipedia")
        return tickers
    except Exception as e:
        print(f"  ✗ No se pudo obtener la lista S&P 500 ({e}).")
        print(f"    Usando lista de respaldo ({len(FALLBACK_TICKERS)} tickers).")
        return FALLBACK_TICKERS
