from pathlib import Path

BASE_DIR    = Path(__file__).parent
OUTPUTS_DIR      = BASE_DIR / 'outputs'
GENERAL_DIR      = OUTPUTS_DIR / 'General'
CORRELATION_DIR  = OUTPUTS_DIR / 'Correlation_method'
OUTPUTS_DIR.mkdir(exist_ok=True)
GENERAL_DIR.mkdir(exist_ok=True)
CORRELATION_DIR.mkdir(exist_ok=True)

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
