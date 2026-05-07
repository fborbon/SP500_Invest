from concurrent.futures import ThreadPoolExecutor
from io import StringIO

import pandas as pd
import requests
import yfinance as yf

from config import FALLBACK_TICKERS

# Full browser-like headers to avoid 403 blocks on financial sites
_HEADERS = {
    'User-Agent':                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                                 '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept':                    'text/html,application/xhtml+xml,application/xml;q=0.9,'
                                 'image/avif,image/webp,image/apng,*/*;q=0.8',
    'Accept-Language':           'en-US,en;q=0.9',
    'Accept-Encoding':           'gzip, deflate, br',
    'Connection':                'keep-alive',
    'Upgrade-Insecure-Requests': '1',
    'Cache-Control':             'max-age=0',
}


def get_sp500_tickers(n=None) -> list:
    """Return S&P 500 tickers sorted by market cap (index weight).

    Args:
        n: Controls which tickers are returned:
           - None               → all S&P 500 constituents (~503).
           - int                → top N companies by market cap.
           - 'FALLBACK_TICKERS' → hardcoded top-20 list from config, no web request.

    Sources tried in order (unless n='FALLBACK_TICKERS'):
      1. slickcharts.com     — pre-ranked by S&P 500 weight (≈ market cap).
      2. stockanalysis.com   — ranked by market cap.
      3. Wikipedia           — fallback, alphabetical order (warns user).
      4. FALLBACK_TICKERS    — hardcoded top-20 when all sources fail.
    """
    if n == 'FALLBACK_TICKERS':
        print(f"  → Using FALLBACK_TICKERS ({len(FALLBACK_TICKERS)} hardcoded tickers)")
        return list(FALLBACK_TICKERS)

    tickers = _fetch_sorted_tickers()

    total = len(tickers)
    if n is not None:
        tickers = tickers[:n]
        print(f"  → Selected top {n} of {total} by market cap")
    else:
        print(f"  → Using all {total} S&P 500 tickers")

    return tickers


def fetch_market_caps(tickers: list) -> dict:
    """Fetch market capitalization for each ticker via yfinance (free, no API key).

    Uses 30 parallel threads. Yahoo Finance uses '-' instead of '.' in tickers
    (e.g. BRK-B), so dots are converted automatically.

    Returns dict mapping original ticker → market cap in USD (0 if unavailable).
    """
    def _get_cap(ticker):
        yf_ticker = ticker.replace('.', '-')
        try:
            cap = yf.Ticker(yf_ticker).fast_info['market_cap']
            return ticker, cap if cap else 0
        except Exception:
            return ticker, 0

    print(f"\nFetching market caps for {len(tickers)} tickers via yfinance...")
    with ThreadPoolExecutor(max_workers=30) as executor:
        results = dict(executor.map(_get_cap, tickers))

    fetched = sum(1 for v in results.values() if v > 0)
    print(f"  ✓ Market caps retrieved: {fetched}/{len(tickers)}")
    return results


def _fetch_sorted_tickers() -> list:
    # ── 1. slickcharts — sorted by portfolio weight (≈ market cap) ──────
    try:
        resp = requests.get('https://slickcharts.com/sp500',
                            headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        table = pd.read_html(StringIO(resp.text))[0]
        tickers = table['Symbol'].str.strip().tolist()
        print(f"  ✓ {len(tickers)} tickers fetched from slickcharts (sorted by market cap)")
        return tickers
    except Exception as e:
        print(f"  ✗ slickcharts unavailable ({e}), trying stockanalysis.com...")

    # ── 2. stockanalysis.com — sorted by market cap ───────────────────────
    try:
        resp = requests.get('https://stockanalysis.com/list/sp-500/',
                            headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        table = pd.read_html(StringIO(resp.text))[0]
        # Column is 'Symbol' or 'Ticker' depending on page version
        col = 'Symbol' if 'Symbol' in table.columns else 'Ticker'
        tickers = table[col].str.strip().tolist()
        print(f"  ✓ {len(tickers)} tickers fetched from stockanalysis.com (sorted by market cap)")
        return tickers
    except Exception as e:
        print(f"  ✗ stockanalysis.com unavailable ({e}), trying Wikipedia...")

    # ── 3. Wikipedia — alphabetical, not sorted by market cap ────────────
    try:
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        resp = requests.get(url, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        table = pd.read_html(StringIO(resp.text), attrs={'id': 'constituents'})[0]
        tickers = table['Symbol'].tolist()
        print(f"  ✓ {len(tickers)} tickers fetched from Wikipedia")
        print("  ⚠ Wikipedia is not sorted by market cap — plots will use yfinance caps for ordering.")
        return tickers
    except Exception as e:
        print(f"  ✗ Wikipedia unavailable ({e}). Using fallback list.")
        return list(FALLBACK_TICKERS)
