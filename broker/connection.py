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
    print(f"Conectando a IB en {IB_HOST}:{IB_PORT}...")
    try:
        ib.connect(IB_HOST, IB_PORT, clientId=CLIENT_ID)
        print(f"✓ Conectado. Cuenta: {ib.managedAccounts()}")
        return ib
    except Exception as e:
        print(f"✗ Error de conexión: {e}")
        print("  Asegúrate de que TWS o IB Gateway esté abierto y configurado.")
        raise


def get_contract(ticker: str) -> Stock:
    """Create a stock contract for the given ticker (handles BRK.B → 'BRK B')."""
    return Stock(ticker.replace('.', ' '), 'SMART', 'USD')
