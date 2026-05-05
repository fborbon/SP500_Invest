import warnings
warnings.filterwarnings('ignore')

from config import MIN_R2, OUTPUTS_DIR
from broker.connection import connect_ib
from broker.data import fetch_prices
from broker.orders import calculate_position_size, execute_order, get_portfolio_value
from analysis.universe import get_sp500_tickers
from analysis.correlations import compute_correlations, get_top_correlated_pairs, get_top_inverse_pairs
from analysis.signals import generate_signals
from reporting.charts import plot_correlation_matrix
from reporting.report import print_report, save_signals_csv


def run_bot(execute_trades: bool = False, save_plots: bool = True):
    """Full pipeline: connect → download → correlate → predict → signal → (trade).

    Uses the full S&P 500 universe (~500 tickers). Both direct and inverse
    correlations are used as predictors.

    Args:
        execute_trades: If True, places real orders in IB. Use with caution.
        save_plots:     If True, saves the correlation heatmap as PNG.
    """
    ib = connect_ib()
    try:
        print("\nObteniendo universo S&P 500...")
        tickers = get_sp500_tickers()

        prices_df = fetch_prices(ib, tickers)
        if prices_df.empty or len(prices_df.columns) < 5:
            print("✗ Datos insuficientes. Abortando.")
            return

        print("\nCalculando correlaciones...")
        corr_matrix, returns = compute_correlations(prices_df)
        top_pairs     = get_top_correlated_pairs(corr_matrix, top_n=10)
        inverse_pairs = get_top_inverse_pairs(corr_matrix, top_n=10)

        if save_plots:
            plot_correlation_matrix(corr_matrix)

        signals_df = generate_signals(prices_df, returns, corr_matrix)
        print_report(signals_df, top_pairs, inverse_pairs)
        save_signals_csv(signals_df)

        if execute_trades:
            portfolio_value = get_portfolio_value(ib)
            print(f"\nEjecutando órdenes (portfolio: ${portfolio_value:,.0f})...")
            actionable = signals_df[signals_df['signal'].isin(['BUY', 'SELL'])]
            for _, row in actionable.iterrows():
                if row['model_r2'] < MIN_R2:
                    continue
                strength = min(1.0, row['model_r2'])
                qty = calculate_position_size(portfolio_value, row['current_price'], strength)
                execute_order(ib, row['ticker'], row['signal'], qty)
        else:
            print("\n  ℹ Modo simulación — órdenes no ejecutadas.")
            print("    Para ejecutar en paper trading: run_bot(execute_trades=True)")

    finally:
        ib.disconnect()
        print("\n✓ Desconectado de Interactive Brokers.")


if __name__ == '__main__':
    import sys
    from demo import run_demo
    import config

    mode = sys.argv[1] if len(sys.argv) > 1 else 'demo'

    if mode == 'demo':
        run_demo()

    elif mode == 'paper':
        run_bot(execute_trades=True)

    elif mode == 'live':
        confirm = input("¿Confirmas ejecución en cuenta REAL? (escribe SI): ")
        if confirm.strip() == 'SI':
            config.IB_PORT = 7496   # override before connect_ib() reads it
            run_bot(execute_trades=True)
        else:
            print("Cancelado.")

    elif mode == 'signals':
        run_bot(execute_trades=False)

    else:
        print("Uso: python main.py [demo|paper|live|signals]")
