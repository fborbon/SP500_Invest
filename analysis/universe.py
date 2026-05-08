from concurrent.futures import ThreadPoolExecutor
from io import StringIO
import re
import time

import pandas as pd
import requests
import yfinance as yf

import datetime
import json

from config import CACHE_DIR, FALLBACK_TICKERS, EXCLUDED_TICKERS, MCAP_CACHE_MAX_AGE_HOURS

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
        all_tickers = list(FALLBACK_TICKERS)
    else:
        all_tickers = _fetch_wikipedia()

    all_tickers = [t for t in all_tickers if t not in EXCLUDED_TICKERS]
        
    print(f"  Sorting {len(all_tickers)} tickers by market cap...")
    caps = fetch_market_caps_cached(all_tickers)
    caps = dict(sorted(caps.items(), key=lambda item: item[1], reverse=True))
    all_tickers = sorted(all_tickers, key=lambda t: caps.get(t, 0), reverse=True)

    if n is None:
        print(f"  → Using all {len(all_tickers)} S&P 500 tickers")
    elif isinstance(n, int):
        print(f"  → Selected top {n} of {len(all_tickers)} by market cap")
        all_tickers = all_tickers[:n]
        caps = dict(list(caps.items())[:n])
        
    return all_tickers, caps


def fetch_company_metadata(tickers: list, market_caps: dict) -> pd.DataFrame:
    """Fetch company name, sector, and founding year from Wikipedia S&P 500 table.

    Combines with market_caps to add a market_cap_B column.
    Returns a DataFrame indexed by ticker with columns:
      company_name, sector, founded, market_cap_B
    Missing tickers get NaN for metadata fields but keep their market cap.
    """
    try:
        url = 'https://en.wikipedia.org/wiki/List_of_S%26P_500_companies'
        resp = requests.get(url, headers=_HEADERS, timeout=15)
        resp.raise_for_status()
        table = pd.read_html(StringIO(resp.text), attrs={'id': 'constituents'})[0]

        meta = table[['Symbol', 'Security', 'GICS Sector', 'Founded']].copy()
        meta.columns = ['ticker', 'company_name', 'sector', 'founded']
        meta['ticker'] = meta['ticker'].str.strip()

        # Extract 4-digit founding year from strings like "1976", "1885 (reincorporated 2000)"
        meta['founded'] = meta['founded'].apply(
            lambda v: int(m.group()) if (m := re.search(r'\d{4}', str(v))) else None
        )
        meta = meta.set_index('ticker')

    except Exception as e:
        print(f"  ✗ Could not fetch company metadata ({e}). Fields will be empty.")
        meta = pd.DataFrame(index=tickers, columns=['company_name', 'sector', 'founded'])

    # Add market cap in billions, for all tickers we have prices for
    result = meta.reindex(tickers)
    result['market_cap_B'] = [
        round(market_caps.get(t, 0) / 1e9, 1) if market_caps.get(t, 0) else None
        for t in tickers
    ]
    return result


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


def fetch_market_caps_cached(tickers: list) -> dict:
    """Cached version of fetch_market_caps.

    Reuses a JSON snapshot when it is younger than MCAP_CACHE_MAX_AGE_HOURS.
    Any ticker missing from the cache is fetched individually and added.
    """
    CACHE_DIR.mkdir(exist_ok=True)
    cache_path = CACHE_DIR / 'market_caps_cache.json'

    if cache_path.exists():
        with open(cache_path) as f:
            data = json.load(f)
        ts  = datetime.datetime.fromisoformat(data['timestamp'])
        age = (datetime.datetime.now() - ts).total_seconds() / 3600

        if age < MCAP_CACHE_MAX_AGE_HOURS:
            cached_caps = data['caps']
            missing = [t for t in tickers if t not in cached_caps]
            if not missing:
                print(f"  Using cached market caps (age: {age:.1f}h)")
                return {t: cached_caps.get(t, 0) for t in tickers}
            print(f"  Cache hit ({age:.1f}h old), fetching {len(missing)} missing tickers...")
            fresh = _fetch_caps_parallel(missing)
            cached_caps.update(fresh)
            data['caps'] = cached_caps
            data['timestamp'] = datetime.datetime.now().isoformat()
            with open(cache_path, 'w') as f:
                json.dump(data, f)
            print(f"  ✓ Market caps cache updated ({len(cached_caps)} tickers)")
            return {t: cached_caps.get(t, 0) for t in tickers}

    print(f"  Market caps cache missing or stale — fetching fresh data...")
    caps = fetch_market_caps(tickers)
    with open(cache_path, 'w') as f:
        json.dump({'timestamp': datetime.datetime.now().isoformat(), 'caps': caps}, f)
    print(f"  ✓ Market caps cache saved ({len(caps)} tickers)")
    return caps


# ── Internal helpers ──────────────────────────────────────────────────────────

def _fetch_caps_parallel(tickers: list) -> dict:
    def _get_cap(ticker):
        yf_ticker = ticker.replace('.', '-')
        for attempt in range(3):   # retry up to 3 times on None/error
            try:
                cap = yf.Ticker(yf_ticker).fast_info['market_cap']
                if cap:
                    return ticker, cap
            except Exception:
                pass
            time.sleep(0.5 * (attempt + 1))
        return ticker, 0

    # 10 workers instead of 30 to avoid Yahoo Finance rate-limiting on first call
    with ThreadPoolExecutor(max_workers=10) as executor:
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
