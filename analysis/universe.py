from concurrent.futures import ThreadPoolExecutor
from io import StringIO

import pandas as pd
import requests
import yfinance as yf

from config import FALLBACK_TICKERS

_HEADERS = {'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36'}


def get_sp500_tickers(n=None) -> list:
    """Return S&P 500 tickers, optionally filtered to the top N by market cap.

    Args:
        n: Controls which tickers are returned:
           - None               → all S&P 500 constituents (~503).
           - int                → top N companies by market cap.
           - 'FALLBACK_TICKERS' → hardcoded top-20 list, no web request.

    Strategy:
      1. Wikipedia → full list of S&P 500 tickers.
      2. If n is specified, yfinance fetches market caps for all tickers and
         sorts them so the true top N by market cap are returned (~30s extra).
    """
    if n == 'FALLBACK_TICKERS':
        print(f"  → Using FALLBACK_TICKERS ({len(FALLBACK_TICKERS)} hardcoded tickers)")
        return list(FALLBACK_TICKERS)

    all_tickers = _fetch_wikipedia()

    if n is None:
        print(f"  → Using all {len(all_tickers)} S&P 500 tickers")
        return all_tickers

    print(f"  Sorting {len(all_tickers)} tickers by market cap via yfinance"
          f" to select top {n} (this takes ~30s)...")
    caps = _fetch_caps_parallel(all_tickers)
    all_tickers.sort(key=lambda t: caps.get(t, 0), reverse=True)
    print(f"  → Selected top {n} of {len(all_tickers)} by market cap")
    return all_tickers[:n]


def fetch_market_caps(tickers: list) -> dict:
    """Fetch market capitalization for each ticker via yfinance (free, no API key).

    Uses 30 parallel threads. Dot notation is converted to Yahoo Finance format
    automatically (e.g. BRK.B → BRK-B).

    Returns dict mapping original ticker → market cap in USD (0 if unavailable).
    """
    print(f"\nFetching market caps for {len(tickers)} tickers via yfinance...")
    caps = _fetch_caps_parallel(tickers)
    fetched = sum(1 for v in caps.values() if v > 0)
    print(f"  ✓ Market caps retrieved: {fetched}/{len(tickers)}")
    return caps


# ── Internal helpers ──────────────────────────────────────────────────────────

def _fetch_caps_parallel(tickers: list) -> dict:
    def _get_cap(ticker):
        try:
            cap = yf.Ticker(ticker.replace('.', '-')).fast_info['market_cap']
            return ticker, cap if cap else 0
        except Exception:
            return ticker, 0

    with ThreadPoolExecutor(max_workers=30) as executor:
        return dict(executor.map(_get_cap, tickers))


def _fetch_wikipedia() -> list:
    try:
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        resp = requests.get(url, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        table = pd.read_html(StringIO(resp.text), attrs={'id': 'constituents'})[0]
        tickers = table['Symbol'].tolist()
        print(f"  ✓ {len(tickers)} tickers fetched from Wikipedia")
        return tickers
    except Exception as e:
        print(f"  ✗ Wikipedia unavailable ({e}). Using fallback list.")
        return list(FALLBACK_TICKERS)
