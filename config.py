import datetime
from pathlib import Path

BASE_DIR    = Path(__file__).parent
OUTPUTS_DIR = BASE_DIR / 'outputs'
OUTPUTS_DIR.mkdir(exist_ok=True)

def create_run_dirs() -> tuple:
    """Create a timestamped output folder tree for a single bot run.

    Returns (run_dir, general_dir, correlation_dir).
    Folder name format: 'YYYY-MM-DD_HH-MM'
    """
    ts      = datetime.datetime.now().strftime('%Y-%m-%d_%H-%M')
    run_dir = OUTPUTS_DIR / ts
    gen_dir  = run_dir / 'General'
    corr_dir = run_dir / 'Correlation_method'
    run_dir.mkdir(exist_ok=True)
    gen_dir.mkdir(exist_ok=True)
    corr_dir.mkdir(exist_ok=True)
    print(f"  Run outputs → {run_dir}")
    return run_dir, gen_dir, corr_dir

# Interactive Brokers connection
IB_HOST   = '127.0.0.1'
IB_PORT   = 7497           # 7497 = paper trading | 7496 = live
CLIENT_ID = 1
ACCOUNT   = ''             # Empty → use default account

# Used as fallback when Wikipedia is unreachable, and for demo mode
FALLBACK_TICKERS = [
    'AAPL', 'MSFT', 'NVDA', 'AMZN', 'GOOGL',
    'META', 'LLY',  'TSLA', 'JPM',  'V',
    'UNH',  'XOM',  'JNJ',  'WMT',  'MA',
    'PG',   'HD',   'AVGO', 'COST', 'NFLX'
]

# Number of top companies highlighted in price series and bar charts
TOP_N_HIGHLIGHT  = 15

# Model parameters
HISTORY_DAYS     = 800     # Days of history for correlation calculation
PREDICTION_DAYS  = 7       # Prediction horizon (days)
MIN_CORRELATION  = 0.50    # Minimum correlation to use as predictor
MIN_R2           = 0.01    # Minimum R² to trust the signal. =0.40
BUY_THRESHOLD    = 0.01    # Predicted return > X% → BUY
SELL_THRESHOLD   = -0.10   # Predicted return < -X% → SELL
ORDER_QUANTITY        = 10       # Shares per order (paper trading)
MAX_POSITION_PCT      = 0.10     # Maximum % of portfolio per position
FALLBACK_PORTFOLIO    = 1_000.0  # Used when IB does not return NetLiquidation
