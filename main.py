import warnings
warnings.filterwarnings('ignore')

from config import MIN_R2, OUTPUTS_DIR, TOP_N_HIGHLIGHT, create_run_dirs
from broker.connection import connect_ib
from broker.data import fetch_prices, fetch_prices_free
from broker.orders import calculate_position_size, execute_order, get_portfolio_value
from analysis.universe import fetch_company_metadata, get_sp500_tickers
from analysis.fundamentals import fetch_fundamentals, score_fundamentals, save_fundamentals_csv
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
    run_dir, gen_dir, corr_dir = create_run_dirs()

    print("\nFetching S&P 500 universe...")
    tickers, market_caps = get_sp500_tickers(n=n_tickers)

    prices_df = fetch_prices_free(tickers)
    if prices_df.empty or len(prices_df.columns) < 5:
        print("✗ Insufficient data. Aborting.")
        return

    print("\nCalculating correlations...")
    corr_matrix, returns = compute_correlations(prices_df)
    top_pairs     = get_top_correlated_pairs(corr_matrix, top_n=10)
    inverse_pairs = get_top_inverse_pairs(corr_matrix, top_n=10)

    signals_df = generate_signals(prices_df, returns, corr_matrix)

    # Enrich signals with company name, sector, founded year, market cap (B)
    company_meta = fetch_company_metadata(list(prices_df.columns), market_caps)
    signals_df = signals_df.merge(
        company_meta.reset_index().rename(columns={'index': 'ticker'}),
        on='ticker', how='left'
    )
    # Reorder columns so metadata appears right after ticker
    meta_cols = ['company_name', 'sector', 'founded', 'market_cap_B']
    other_cols = [c for c in signals_df.columns if c not in ['ticker'] + meta_cols]
    signals_df = signals_df[['ticker'] + meta_cols + other_cols]

    print_report(signals_df, top_pairs, inverse_pairs)
    save_signals_csv(signals_df, run_dir / 'signals.csv')

    # Fundamental analysis table
    fund_raw = fetch_fundamentals(list(prices_df.columns))
    fund_df  = score_fundamentals(fund_raw)
    save_fundamentals_csv(fund_df, run_dir / 'fundamentals.csv')

    if save_plots:
        # Slice to top N by market cap for a legible heatmap
        top_t = [t for t in tickers if t in corr_matrix.columns][:TOP_N_HIGHLIGHT]
        plot_correlation_matrix(corr_matrix.loc[top_t, top_t],
                                save_path=corr_dir / 'correlation_matrix.png')

        # General/ — price series highlighted by market cap
        plot_price_series(prices_df, tickers, top_n=TOP_N_HIGHLIGHT, label='market cap',
                          save_path=gen_dir / 'price_series_market-cap.png')

        # General/ — price series highlighted by highest absolute stock price
        tickers_by_price = sorted(
            prices_df.columns.tolist(),
            key=lambda t: prices_df[t].iloc[-1],
            reverse=True
        )
        plot_price_series(prices_df, tickers_by_price, top_n=TOP_N_HIGHLIGHT, label='stock price',
                          save_path=gen_dir / 'price_series_stock-price-absolute.png')

        # General/ — price series highlighted by highest normalized return (best performers)
        tickers_by_norm = sorted(
            prices_df.columns.tolist(),
            key=lambda t: prices_df[t].iloc[-1] / prices_df[t].iloc[0],
            reverse=True
        )
        plot_price_series(prices_df, tickers_by_norm, top_n=TOP_N_HIGHLIGHT, label='normalized return',
                          save_path=gen_dir / 'price_series_normalized-return.png')

        # General/ — bar chart: top 15 vs bottom 15 by market cap
        plot_market_cap_bars(prices_df, tickers, market_caps=market_caps, top_n=TOP_N_HIGHLIGHT,
                             save_path=gen_dir / 'market_cap_bars.png')

        # Correlation_method/ — per-ticker prediction analysis
        top_signals_n = 15
        top_signals = signals_df.head(top_signals_n)
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
                    save_path=corr_dir / f'analysis_{ticker}.png'
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
