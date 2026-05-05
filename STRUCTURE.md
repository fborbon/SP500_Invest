# SP500 Correlation Bot — File Structure

```
V3/
├── config.py               # All constants + OUTPUTS_DIR path
├── main.py                 # run_bot() + CLI entry point
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
│   ├── correlations.py     # compute_correlations(), get_top_correlated_pairs()
│   ├── model.py            # predict_price() — LinearRegression + TimeSeriesSplit
│   └── signals.py          # generate_signals()
│
├── reporting/
│   ├── __init__.py
│   ├── charts.py           # plot_correlation_matrix()
│   └── report.py           # print_report(), save_signals_csv()
│
├── outputs/                # Generated files (PNG, CSV) — git-ignored contents
│   ├── correlation_matrix.png
│   ├── signals.csv
│   ├── demo_correlation_matrix.png
│   └── demo_signals.csv
│
└── Main.ipynb              # Jupyter entry point
```

## Usage

```bash
# Demo mode — no IB required
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
| `MIN_CORRELATION` | `0.50` | Minimum Pearson r to use a predictor |
| `MIN_R2` | `0.40` | Minimum R² to trust a signal |
| `BUY_THRESHOLD` | `0.02` | Predicted return > 2% → BUY |
| `SELL_THRESHOLD` | `-0.02` | Predicted return < −2% → SELL |
| `MAX_POSITION_PCT` | `0.05` | Max 5% of portfolio per position |
