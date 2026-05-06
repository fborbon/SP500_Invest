# SP500 Correlation Bot — File Structure

```
V3/
├── config.py               # All constants + OUTPUTS_DIR path
├── main.py                 # run_bot(n_tickers) + CLI entry point
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
│   ├── universe.py         # get_sp500_tickers(n) — top N by market cap via
│   │                       # slickcharts.com; falls back to Wikipedia, then top-20
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

## Usage

```bash
# Demo mode — no IB required
python main.py demo

# Top N companies by market cap (N is optional; omit for full S&P 500)
python main.py signals 50
python main.py paper 100
python main.py live 50
python main.py paper          # full ~503 tickers
```

**Jupyter:** set `n_tickers` and `mode` in the run cell of `Main.ipynb`.

## Key configuration (`config.py`)

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
| `FALLBACK_TICKERS` | top 20 | Used when all online sources fail |

## Selecting companies (`analysis/universe.py`)

`get_sp500_tickers(n)` fetches the **N most valuable** S&P 500 companies at runtime:

| Source | Order | Used when |
|---|---|---|
| slickcharts.com | By S&P 500 weight ≈ market cap ✓ | Primary |
| Wikipedia | Alphabetical ⚠ | slickcharts unreachable |
| `FALLBACK_TICKERS` | Hardcoded top-20 | Both sources fail |

## Prediction model (`analysis/model.py`)

**RandomForestRegressor** (200 trees, `max_depth=4`, `min_samples_leaf=10`) validated with `TimeSeriesSplit`. No feature scaling needed. Returns `y_actual` and `y_predicted` for the scatter plot without re-running the model.

## Inverse correlation logic

Stocks with absolute Pearson r ≥ 0.50 are included as predictors regardless of sign. The Random Forest assigns the correct weight — inverse correlators (r < 0) contribute negatively. Report labels: **↓ inverso** / **↑↓ TOP 5 PARES CORRELACIÓN INVERSA**.

## Output plots (`save_plots=True`)

**`correlation_matrix.png`** — heatmap of all analyzed tickers.

**`analysis_{TICKER}.png`** — top 5 signals by predicted return:
- **Left** — scatter: actual vs predicted cumulative returns + R² trend line.
- **Right** — normalized time series (base = 100): target + top 5 predictors. Direct = solid, inverse = dashed.
