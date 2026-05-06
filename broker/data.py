import math
import time

import pandas as pd
import yfinance as yf
from ib_insync import IB, util

from config import HISTORY_DAYS
from broker.connection import get_contract


def _build_duration(trading_days: int) -> str:
    """Convert a number of trading days to an IB durationStr.

    IB requires years (Y) for requests longer than 365 days.
    1 year ≈ 252 trading days.
    """
    total = trading_days + 10   # small buffer for holidays
    if total > 365:
        return f'{math.ceil(total / 252)} Y'
    return f'{total} D'


def fetch_prices(ib: IB, tickers: list, duration: str = None,
                 bar_size: str = '1 day') -> pd.DataFrame:
    """Download historical close prices via Interactive Brokers.

    Requires an active IB TWS / Gateway connection.
    Returns a DataFrame with dates as index and tickers as columns.
    """
    if duration is None:
        duration = _build_duration(HISTORY_DAYS)

    prices = {}
    print(f"\nDownloading historical data ({duration}, bar size {bar_size})...")

    for ticker in tickers:
        try:
            contract = get_contract(ticker)
            bars = ib.reqHistoricalData(
                contract,
                endDateTime='',
                durationStr=duration,
                barSizeSetting=bar_size,
                whatToShow='ADJUSTED_LAST',
                useRTH=True,
                keepUpToDate=False,
            )
            if not bars:
                print(f"  ✗ {ticker}: no data")
                continue
            df = util.df(bars)[['date', 'close']].set_index('date')
            prices[ticker] = df['close']
            print(f"  ✓ {ticker}: {len(df)} bars — last close ${df['close'].iloc[-1]:.2f}")
            time.sleep(0.2)   # avoid API throttling
        except Exception as e:
            print(f"  ✗ {ticker}: {e}")

    prices_df = pd.DataFrame(prices).tail(HISTORY_DAYS)
    prices_df.dropna(axis=1, how='all', inplace=True)
    print(f"\n  Tickers with data: {len(prices_df.columns)}/{len(tickers)}")
    return prices_df


def fetch_prices_free(tickers: list) -> pd.DataFrame:
    """Download historical close prices via Yahoo Finance (yfinance) — no IB needed.

    All tickers are fetched in a single batch request. Dot notation is converted
    to Yahoo Finance format (e.g. BRK.B → BRK-B) automatically.
    Data is 15-min delayed for the latest bar; all historical bars are accurate.

    Returns a DataFrame with dates as index and original ticker names as columns.
    """
    yf_tickers  = [t.replace('.', '-') for t in tickers]
    ticker_map  = dict(zip(yf_tickers, tickers))   # yf name → original name

    # HISTORY_DAYS are trading days; yfinance period uses calendar days
    calendar_days = math.ceil(HISTORY_DAYS * 365 / 252) + 10
    period = f'{calendar_days}d'

    print(f"\nDownloading historical data via yfinance ({HISTORY_DAYS} trading days)...")
    raw = yf.download(
        yf_tickers,
        period=period,
        interval='1d',
        auto_adjust=True,
        progress=False,
        threads=True,
    )

    # yf.download returns MultiIndex columns when >1 ticker; single ticker is flat
    if isinstance(raw.columns, pd.MultiIndex):
        prices = raw['Close'].rename(columns=ticker_map)
    else:
        prices = raw[['Close']].rename(columns={'Close': tickers[0]})

    prices.index = pd.to_datetime(prices.index).tz_localize(None)
    prices = prices.tail(HISTORY_DAYS)
    prices.dropna(axis=1, how='all', inplace=True)

    fetched = len(prices.columns)
    print(f"  Tickers with data: {fetched}/{len(tickers)}")
    for ticker in prices.columns:
        print(f"  ✓ {ticker}: {prices[ticker].count()} bars"
              f" — last close ${prices[ticker].dropna().iloc[-1]:.2f}")
    return prices
