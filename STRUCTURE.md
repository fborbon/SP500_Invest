# SP500 Correlation Bot — File Structure

```
V3/
├── config.py               # All constants + OUTPUTS_DIR path
├── main.py                 # run_bot() + CLI entry point (full S&P 500)
├── demo.py                 # run_demo() — synthetic data, no IB connection needed
│
├── broker/
│   ├── __init__.py
│   ├── connection.py       # connect_ib(), get_contract(), nest_asyncio fix
│   ├── data.py             # fetch_prices()
│   └── orders.py           # execute_order(), close_position(), calculate_position_size()
│
├── analysis/
│   ├── __init__.py
│   ├── universe.py         # get_sp500_tickers() — fetches ~500 tickers from Wikipedia
│   ├── correlations.py     # compute_correlations(), get_top_correlated_pairs(),
│   │                       # get_top_inverse_pairs()
│   ├── model.py            # predict_price() — LinearRegression + TimeSeriesSplit,
│   │                       # returns corr_signs (direct vs inverse predictors)
│   └── signals.py          # generate_signals() — BUY/SELL/HOLD with direct &
│                           # inverse predictor breakdown
│
├── reporting/
│   ├── __init__.py
│   ├── charts.py           # plot_correlation_matrix()
│   └── report.py           # print_report() — direct (↑↑) and inverse (↑↓) pair
│                           # sections; save_signals_csv()
│
├── outputs/                # Generated files (PNG, CSV) — git-ignored contents
│   ├── correlation_matrix.png
│   ├── signals.csv
│   ├── demo_correlation_matrix.png
│   └── demo_signals.csv
│
├── sp500_bot_function_diagram.png   # Architecture diagram
└── Main.ipynb                       # Jupyter entry point
```

## Usage

```bash
# Demo mode — no IB required, synthetic data with inverse correlations
python main.py demo

# Generate signals only (requires IB Gateway on port 7497)
python main.py signals

# Paper trading — executes orders on simulated account
python main.py paper

# Live trading — real money, requires manual confirmation
python main.py live
```

## Key configuration (`config.py`)

| Variable | Default | Description |
|---|---|---|
| `IB_HOST` | `127.0.0.1` | TWS / IB Gateway host |
| `IB_PORT` | `7497` | 7497 = paper, 7496 = live |
| `HISTORY_DAYS` | `90` | Days of price history |
| `PREDICTION_DAYS` | `7` | Forecast horizon |
| `MIN_CORRELATION` | `0.50` | Minimum absolute Pearson r to use a predictor (direct or inverse) |
| `MIN_R2` | `0.40` | Minimum R² to trust a signal |
| `BUY_THRESHOLD` | `0.02` | Predicted return > 2% → BUY |
| `SELL_THRESHOLD` | `-0.02` | Predicted return < −2% → SELL |
| `MAX_POSITION_PCT` | `0.05` | Max 5% of portfolio per position |
| `FALLBACK_TICKERS` | top 20 | Used when Wikipedia is unreachable or in demo mode |

## Inverse correlation logic

Stocks with a Pearson r ≤ −0.50 relative to the target are included as predictors
with their natural negative sign. `LinearRegression` assigns them a negative
coefficient, so when an inverse predictor rises the model predicts the target falls
(and vice versa). The report labels these predictors with **↓ inverso** and lists
the most negatively correlated pairs under **↑↓ TOP 5 PARES CORRELACIÓN INVERSA**.
