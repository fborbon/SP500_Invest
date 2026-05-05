import math
import time

import pandas as pd
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
    """Download historical close prices for each ticker.

    Returns a DataFrame with dates as index and tickers as columns.
    """
    if duration is None:
        duration = _build_duration(HISTORY_DAYS)

    prices = {}
    print(f"\nDescargando histórico ({duration}, barras {bar_size})...")

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
                print(f"  ✗ {ticker}: sin datos")
                continue
            df = util.df(bars)[['date', 'close']].set_index('date')
            prices[ticker] = df['close']
            print(f"  ✓ {ticker}: {len(df)} barras — último cierre ${df['close'].iloc[-1]:.2f}")
            time.sleep(0.2)   # avoid API throttling
        except Exception as e:
            print(f"  ✗ {ticker}: {e}")

    prices_df = pd.DataFrame(prices).tail(HISTORY_DAYS)
    prices_df.dropna(axis=1, how='all', inplace=True)
    print(f"\n  Total tickers con datos: {len(prices_df.columns)}/{len(tickers)}")
    return prices_df
