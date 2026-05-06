import warnings
warnings.filterwarnings('ignore')

from config import MIN_R2, OUTPUTS_DIR
from broker.connection import connect_ib
from broker.data import fetch_prices, fetch_prices_free
from broker.orders import calculate_position_size, execute_order, get_portfolio_value
from analysis.universe import fetch_market_caps, get_sp500_tickers
from analysis.correlations import compute_correlations, get_top_correlated_pairs, get_top_inverse_pairs
from analysis.model import predict_price
from analysis.signals import generate_signals
from reporting.charts import (plot_correlation_matrix, plot_market_cap_bars,
                               plot_prediction_analysis, plot_price_series)
from reporting.report import print_report, save_signals_csv


def run_bot(execute_trades: bool = False, save_plots: bool = True,
            n_tickers: int = None):
    """Full pipeline: connect → download → correlate → predict → signal → (trade).

    Args:
        execute_trades: If True, places real orders in IB. Use with caution.
        save_plots:     If True, saves heatmap + price series + per-signal analysis PNGs.
        n_tickers:      Number of top S&P 500 companies by market cap to use.
                        None = full universe (~503 tickers).
    """
    print("\nFetching S&P 500 universe...")
    tickers = get_sp500_tickers(n=n_tickers)

    prices_df = fetch_prices_free(tickers)
    if prices_df.empty or len(prices_df.columns) < 5:
        print("✗ Insufficient data. Aborting.")
        return

    market_caps = fetch_market_caps(list(prices_df.columns))

    print("\nCalculating correlations...")
    corr_matrix, returns = compute_correlations(prices_df)
    top_pairs     = get_top_correlated_pairs(corr_matrix, top_n=10)
    inverse_pairs = get_top_inverse_pairs(corr_matrix, top_n=10)

    signals_df = generate_signals(prices_df, returns, corr_matrix)
    print_report(signals_df, top_pairs, inverse_pairs)
    save_signals_csv(signals_df)

    if save_plots:
        plot_correlation_matrix(corr_matrix)

        # All tickers in gray, top 15 most valuable in color
        plot_price_series(prices_df, tickers, top_n=15)

        # Top 15 vs bottom 15 — stock price (top) and market cap (bottom)
        plot_market_cap_bars(prices_df, tickers, market_caps=market_caps, top_n=15)

        # Dual-subplot analysis for top 5 signals by predicted return
        top_signals = signals_df.head(5)
        if not top_signals.empty:
            print("\nGenerating analysis charts...")
        for _, row in top_signals.iterrows():
            ticker = row['ticker']
            pred_ret, r2, top5, corr_signs, y_actual, y_pred = predict_price(
                ticker, returns, corr_matrix
            )
            if y_actual is not None:
                plot_prediction_analysis(
                    ticker, returns, prices_df, top5, corr_signs,
                    y_actual, y_pred,
                    save_path=OUTPUTS_DIR / f'analysis_{ticker}.png'
                )

    if execute_trades:
        ib = connect_ib()
        try:
            portfolio_value = get_portfolio_value(ib)
            print(f"\nPlacing orders (portfolio: ${portfolio_value:,.0f})...")
            actionable = signals_df[signals_df['signal'].isin(['BUY', 'SELL'])]
            for _, row in actionable.iterrows():
                if row['model_r2'] < MIN_R2:
                    continue
                strength = min(1.0, row['model_r2'])
                qty = calculate_position_size(portfolio_value, row['current_price'], strength)
                execute_order(ib, row['ticker'], row['signal'], qty)
        finally:
            ib.disconnect()
            print("\n✓ Disconnected from Interactive Brokers.")
    else:
        print("\n  ℹ Simulation mode — no orders placed.")
        print("    To execute on paper trading: run_bot(execute_trades=True)")


if __name__ == '__main__':
    import sys
    from demo import run_demo
    import config

    mode   = sys.argv[1] if len(sys.argv) > 1 else 'demo'
    _n_arg = sys.argv[2] if len(sys.argv) > 2 else None
    n      = (_n_arg if _n_arg == 'FALLBACK_TICKERS'
               else int(_n_arg) if _n_arg is not None
               else None)

    if mode == 'demo':
        run_demo()

    elif mode == 'paper':
        run_bot(execute_trades=True, n_tickers=n)

    elif mode == 'live':
        confirm = input("Confirm execution on LIVE account? (type YES): ")
        if confirm.strip() == 'YES':
            config.IB_PORT = 7496   # override before connect_ib() reads it
            run_bot(execute_trades=True, n_tickers=n)
        else:
            print("Cancelled.")

    elif mode == 'signals':
        run_bot(execute_trades=False, n_tickers=n)

    else:
        print("Usage: python main.py [demo|paper|live|signals] [n_tickers]")
