try:
    import nest_asyncio
    nest_asyncio.apply()
except ImportError:
    import subprocess, sys as _sys
    subprocess.check_call([_sys.executable, '-m', 'pip', 'install', 'nest_asyncio', '-q'])
    import nest_asyncio
    nest_asyncio.apply()

from ib_insync import IB, Stock
from config import IB_HOST, IB_PORT, CLIENT_ID


def connect_ib() -> IB:
    """Connect to Interactive Brokers TWS or IB Gateway."""
    ib = IB()
    print(f"Connecting to IB at {IB_HOST}:{IB_PORT}...")
    try:
        ib.connect(IB_HOST, IB_PORT, clientId=CLIENT_ID)
        print(f"✓ Connected. Account: {ib.managedAccounts()}")
        return ib
    except Exception as e:
        print(f"✗ Connection error: {e}")
        print("  Make sure TWS or IB Gateway is open and configured.")
        raise


def get_contract(ticker: str) -> Stock:
    """Create a stock contract for the given ticker (handles BRK.B → 'BRK B')."""
    return Stock(ticker.replace('.', ' '), 'SMART', 'USD')
