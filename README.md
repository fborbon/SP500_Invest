# SP500 Correlation Bot

Algorithmic trading bot for Interactive Brokers that predicts short-term price movements using Pearson correlations across the full S&P 500 universe (~500 tickers). Both direct and inverse correlations are used as predictors with a Random Forest model.

## Requirements

```bash
pip install ib_insync pandas numpy scikit-learn matplotlib requests nest_asyncio
```

- Interactive Brokers TWS or IB Gateway running locally
- Port `7497` for paper trading (recommended for testing)
- Port `7496` for live trading (use with caution)

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

Or use `Main.ipynb` in Jupyter by setting the `mode` variable in the second cell.

## File Structure

```
V3/
├── config.py               # All constants + OUTPUTS_DIR path
├── main.py                 # run_bot() + CLI entry point (full S&P 500)
├── demo.py                 # run_demo() — synthetic data, no IB connection needed
│
├── broker/
│   ├── __init__.py
│   ├── connection.py       # connect_ib(), get_contract(), nest_asyncio fix
│   ├── data.py             # fetch_prices(); auto-converts days→years for IB API
│   └── orders.py           # execute_order(), close_position(), calculate_position_size()
│
├── analysis/
│   ├── __init__.py
│   ├── universe.py         # get_sp500_tickers() — fetches ~500 tickers from Wikipedia
│   ├── correlations.py     # compute_correlations(), get_top_correlated_pairs(),
│   │                       # get_top_inverse_pairs()
│   ├── model.py            # predict_price() — RandomForestRegressor + TimeSeriesSplit;
│   │                       # returns corr_signs, y_actual, y_predicted
│   └── signals.py          # generate_signals() — BUY/SELL/HOLD with
│                           # direct_top5_predictors / inverse_top5_predictors
│
├── reporting/
│   ├── __init__.py
│   ├── charts.py           # plot_correlation_matrix();
│   │                       # plot_prediction_analysis() — dual subplot per ticker
│   └── report.py           # print_report() — direct (↑↑) and inverse (↑↓) pair
│                           # sections; save_signals_csv()
│
├── outputs/                # Generated files (PNG, CSV) — git-ignored contents
│   ├── correlation_matrix.png
│   ├── signals.csv
│   ├── analysis_{TICKER}.png   # one per top-5 signal
│   ├── demo_correlation_matrix.png
│   └── demo_signals.csv
│
├── sp500_bot_function_diagram.png   # Architecture diagram
└── Main.ipynb                       # Jupyter entry point
```

## Key Configuration (`config.py`)

| Variable | Default | Description |
|---|---|---|
| `IB_HOST` | `127.0.0.1` | TWS / IB Gateway host |
| `IB_PORT` | `7497` | 7497 = paper, 7496 = live |
| `HISTORY_DAYS` | `800` | Trading days of history (>365 auto-converts to years for IB) |
| `PREDICTION_DAYS` | `7` | Forecast horizon (days) |
| `MIN_CORRELATION` | `0.50` | Minimum absolute Pearson r to use a predictor (direct or inverse) |
| `MIN_R2` | `0.25` | Minimum R² to trust a signal |
| `BUY_THRESHOLD` | `0.02` | Predicted return > 2% → BUY |
| `SELL_THRESHOLD` | `-0.02` | Predicted return < −2% → SELL |
| `MAX_POSITION_PCT` | `0.05` | Max 5% of portfolio per position |
| `FALLBACK_TICKERS` | top 20 | Used when Wikipedia is unreachable or in demo mode |

## Prediction Model

`predict_price()` uses a **RandomForestRegressor** (200 trees, `max_depth=4`, `min_samples_leaf=10`) validated with `TimeSeriesSplit`. No feature scaling is needed since trees are scale-invariant. The model returns `y_actual` and `y_predicted` arrays so the scatter plot can be built without re-running the model.

## Inverse Correlation Logic

Stocks with absolute Pearson r ≥ 0.50 relative to the target are included as predictors regardless of sign. The Random Forest assigns the correct weight to each — inverse correlators (r < 0) contribute negatively to the prediction. The report labels them as **↓ inverso** and lists the most negatively correlated pairs under **↑↓ TOP 5 PARES CORRELACIÓN INVERSA**.

## Output Plots (`save_plots=True`)

**`correlation_matrix.png`** — full S&P 500 heatmap.

**`analysis_{TICKER}.png`** — generated for the top 5 signals by predicted return:
- **Left** — scatter of actual vs predicted cumulative returns with R² trend line.
- **Right** — normalized price time series (base = 100) of the target + its top 5 correlated tickers. Direct correlators drawn as solid lines, inverse correlators as dashed lines.
