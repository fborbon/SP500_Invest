# SP500 Correlation Bot

Algorithmic trading bot for Interactive Brokers that predicts short-term price movements using Pearson correlations across the full S&P 500 universe. Both direct and inverse correlations are used as predictors with a Random Forest model. The number of companies analyzed is configurable at runtime, always selecting the **N most valuable** by market cap.

## Requirements

```bash
pip install ib_insync pandas numpy scikit-learn matplotlib requests yfinance nest_asyncio
```

- Interactive Brokers TWS or IB Gateway running locally (only needed to place orders)
- Port `7497` for paper trading (recommended for testing)
- Port `7496` for live trading (use with caution)

> **Price data** is fetched from Yahoo Finance via `yfinance` (free, no IB needed).
> IB is only connected when `execute_trades=True` to place the actual orders.

## Usage

```bash
# Demo mode — no IB required, synthetic data with inverse correlations
python main.py demo

# Top 50 companies by market cap, signals only
python main.py signals 50

# Top 100 companies, paper trading
python main.py paper 100

# Full S&P 500 (~503 tickers), paper trading
python main.py paper

# Live trading — real money, requires manual confirmation
python main.py live 50
```

Or use `Main.ipynb` in Jupyter — set `n_tickers` and `mode` in the run cell.

## File Structure

```
V3/
├── config.py               # All constants + OUTPUTS_DIR path
├── main.py                 # run_bot(n_tickers) + CLI entry point
├── demo.py                 # run_demo() — synthetic data, no IB connection needed
│
├── broker/
│   ├── __init__.py
│   ├── connection.py       # connect_ib(), get_contract(), nest_asyncio fix
│   ├── data.py             # fetch_prices() via IB; fetch_prices_free() via yfinance
│   └── orders.py           # execute_order(), close_position(), calculate_position_size()
│
├── analysis/
│   ├── __init__.py
│   ├── universe.py         # get_sp500_tickers(n) → (tickers, caps); fetch_market_caps();
│   │                       # fetch_company_metadata() — name, sector, founded, cap ($B)
│   ├── correlations.py     # compute_correlations(), get_top_correlated_pairs(),
│   │                       # get_top_inverse_pairs()
│   ├── model.py            # predict_price() — RandomForestRegressor + TimeSeriesSplit;
│   │                       # returns corr_signs, y_actual, y_predicted
│   └── signals.py          # generate_signals() — BUY/SELL/HOLD with
│                           # direct_top5_predictors / inverse_top5_predictors
│
├── reporting/
│   ├── __init__.py
│   ├── charts.py           # plot_correlation_matrix(); plot_price_series();
│   │                       # plot_market_cap_bars(); plot_prediction_analysis()
│   └── report.py           # print_report() — direct (↑↑) and inverse (↑↓) pair
│                           # sections; save_signals_csv()
│
├── outputs/                # Generated files (PNG, CSV) — git-ignored contents
│   ├── General/
│   │   ├── price_series_market-cap.png
│   │   ├── price_series_stock-price-absolute.png
│   │   ├── price_series_normalized-return.png
│   │   └── market_cap_bars.png
│   ├── Correlation_method/
│   │   ├── correlation_matrix.png
│   │   └── analysis_{TICKER}.png   # one per top-5 signal
│   ├── signals.csv
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
| `MIN_R2` | `0.01` | Minimum R² to trust a signal |
| `BUY_THRESHOLD` | `0.01` | Predicted return > 1% → BUY |
| `SELL_THRESHOLD` | `-0.10` | Predicted return < −10% → SELL |
| `MAX_POSITION_PCT` | `0.10` | Max 10% of portfolio per position |
| `FALLBACK_PORTFOLIO` | `1000.0` | Portfolio value used when IB does not return NetLiquidation |
| `FALLBACK_TICKERS` | top 20 | Used when all online sources fail |

## Selecting Companies

`get_sp500_tickers(n)` fetches the **N most valuable** S&P 500 companies at runtime:

| Source | Order | Used when |
|---|---|---|
| Wikipedia + yfinance sort | By actual market cap ✓ | Always (when `n` is specified) |
| Wikipedia only | Alphabetical | `n=None` (full universe) |
| `FALLBACK_TICKERS` | Hardcoded top-20 | Wikipedia unavailable, or `n_tickers='FALLBACK_TICKERS'` |

When `n` is specified, all ~503 Wikipedia tickers are fetched then sorted by real yfinance market caps (~30s) before slicing to top N. Plots also re-sort by market cap so `price_series.png` and `market_cap_bars.png` always show the correct companies.

`n_tickers` accepts three types:
- **`int`** — top N companies by market cap (e.g. `50`)
- **`None`** — full S&P 500 (~503 tickers)
- **`'FALLBACK_TICKERS'`** — hardcoded top-20 list, no web request

## Position Sizing

The spend per order is calculated in `broker/orders.py`:

```
portfolio_value  ×  MAX_POSITION_PCT  ×  signal_strength
```

- `MAX_POSITION_PCT = 0.10` → max 10% of portfolio per position
- `signal_strength = min(1.0, model_r2)` → scales down if R² < 1.0

Example — $100,000 portfolio, buying a $300 stock with R²=0.6:
```
max_value = 100,000 × 0.05 × 0.6 = $3,000
quantity  = int(3,000 / 300)      = 10 shares
```

To change the spend amount, adjust `MAX_POSITION_PCT` or `FALLBACK_PORTFOLIO` in `config.py`.

## Prediction Model

`predict_price()` uses a **RandomForestRegressor** (200 trees, `max_depth=4`, `min_samples_leaf=10`) validated with `TimeSeriesSplit`. No feature scaling needed — trees are scale-invariant. Returns `y_actual` and `y_predicted` arrays for the scatter plot.

## Inverse Correlation Logic

Stocks with absolute Pearson r ≥ 0.50 relative to the target are included as predictors regardless of sign. The Random Forest assigns the correct weight to each — inverse correlators (r < 0) contribute negatively to the prediction. The report labels them **↓ inverso** and lists the most negatively correlated pairs under **↑↓ TOP 5 PARES CORRELACIÓN INVERSA**.

## Output Plots (`save_plots=True`)

**`Correlation_method/correlation_matrix.png`** — Pearson correlation heatmap for all analyzed tickers.

**`Correlation_method/analysis_{TICKER}.png`** — generated for the top 5 signals by predicted return:
- **Left** — scatter of actual vs predicted cumulative returns (1:1 aspect ratio) with R² trend line.
- **Right** — normalized price time series of the target + its top 5 correlated tickers.

**`General/price_series_market-cap.png`** — Two-subplot price time series. Top 15 by market cap in distinct colors; all others in light gray.
- **Top subplot** — normalized prices (base = 100).
- **Bottom subplot** — absolute close prices ($).

**`General/price_series_stock-price-absolute.png`** — Same layout but top 15 highlighted by highest last close stock price ($).

**`General/price_series_normalized-return.png`** — Same layout but top 15 highlighted by highest normalized return (best performers: largest % gain from the start of the history window).

**`General/market_cap_bars.png`** — Two-subplot bar chart for top 15 and bottom 15 companies by market cap.
- **Top subplot** — last closing stock price ($).
- **Bottom subplot** — market capitalization ($B / $T) from yfinance.

**`analysis_{TICKER}.png`** — generated for the top 5 signals by predicted return:
- **Left** — scatter of actual vs predicted cumulative returns (1:1 aspect ratio) with R² trend line.
- **Right** — normalized price time series of the target + its top 5 correlated tickers. Direct correlators as solid lines, inverse correlators as dashed lines.
