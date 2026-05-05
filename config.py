from pathlib import Path

BASE_DIR    = Path(__file__).parent
OUTPUTS_DIR = BASE_DIR / 'outputs'
OUTPUTS_DIR.mkdir(exist_ok=True)

# Interactive Brokers connection
IB_HOST   = '127.0.0.1'
IB_PORT   = 7497           # 7497 = paper trading | 7496 = live
CLIENT_ID = 1
ACCOUNT   = ''             # Empty → use default account

TOP20_TICKERS = [
    'AAPL', 'MSFT', 'NVDA', 'AMZN', 'GOOGL',
    'META', 'LLY',  'TSLA', 'JPM',  'V',
    'UNH',  'XOM',  'JNJ',  'WMT',  'MA',
    'PG',   'HD',   'AVGO', 'COST', 'NFLX'
]

# Model parameters
HISTORY_DAYS     = 90      # Days of history for correlation calculation
PREDICTION_DAYS  = 7       # Prediction horizon (days)
MIN_CORRELATION  = 0.50    # Minimum correlation to use as predictor
MIN_R2           = 0.40    # Minimum R² to trust the signal
BUY_THRESHOLD    = 0.02    # Predicted return > 2% → BUY
SELL_THRESHOLD   = -0.02   # Predicted return < -2% → SELL
ORDER_QUANTITY   = 10      # Shares per order (paper trading)
MAX_POSITION_PCT = 0.05    # Maximum 5% of portfolio per position
