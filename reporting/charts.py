import numpy as np
import matplotlib.pyplot as plt

from config import OUTPUTS_DIR


def plot_correlation_matrix(corr_matrix, save_path=None):
    """Save the correlation matrix as a heatmap PNG."""
    if save_path is None:
        save_path = OUTPUTS_DIR / 'correlation_matrix.png'

    fig, ax = plt.subplots(figsize=(14, 12))
    n = len(corr_matrix)
    im = ax.imshow(corr_matrix.values, cmap='RdYlGn', vmin=-1, vmax=1, aspect='auto')
    plt.colorbar(im, ax=ax, label='Correlación de Pearson')

    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(corr_matrix.columns, rotation=45, ha='right', fontsize=9)
    ax.set_yticklabels(corr_matrix.columns, fontsize=9)

    for i in range(n):
        for j in range(n):
            val = corr_matrix.values[i, j]
            color = 'black' if 0.3 < abs(val) < 0.8 else 'white'
            ax.text(j, i, f'{val:.2f}', ha='center', va='center', fontsize=7, color=color)

    ax.set_title('Matriz de Correlación — S&P 500', fontsize=14, pad=16)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Matriz guardada en: {save_path}")


def plot_prediction_analysis(target: str, returns, prices_df,
                              top5: list, corr_signs: dict,
                              y_actual: np.ndarray, y_predicted: np.ndarray,
                              save_path=None):
    """Dual subplot for a single ticker:
      Left  — scatter of actual cumulative returns (X) vs model predictions (Y).
      Right — normalized price time series of target + top 5 correlated tickers.
              Direct correlators (r > 0) drawn as solid lines,
              inverse correlators (r < 0) drawn as dashed lines.
    """
    if save_path is None:
        save_path = OUTPUTS_DIR / f'analysis_{target}.png'

    fig, (ax_sc, ax_ts) = plt.subplots(1, 2, figsize=(16, 6))
    fig.suptitle(f'{target} — Prediction Analysis (Random Forest)',
                 fontsize=14, fontweight='bold')

    # ── Left: actual vs predicted scatter ────────────────────
    r2 = float(np.corrcoef(y_actual, y_predicted)[0, 1] ** 2)

    ax_sc.scatter(y_actual * 100, y_predicted * 100,
                  alpha=0.35, s=18, color='steelblue', label='Observaciones')

    lim = max(abs(y_actual).max(), abs(y_predicted).max()) * 100 * 1.15
    ax_sc.plot([-lim, lim], [-lim, lim], 'k--', linewidth=1, alpha=0.4,
               label='Predicción perfecta')

    m, b = np.polyfit(y_actual * 100, y_predicted * 100, 1)
    x_line = np.linspace(y_actual.min() * 100, y_actual.max() * 100, 100)
    ax_sc.plot(x_line, m * x_line + b, color='crimson', linewidth=1.8,
               label=f'Tendencia  R²={r2:.3f}')

    ax_sc.axhline(0, color='grey', linewidth=0.5, alpha=0.6)
    ax_sc.axvline(0, color='grey', linewidth=0.5, alpha=0.6)
    ax_sc.set_aspect('equal', adjustable='box')
    ax_sc.set_xlabel('Retorno real acumulado (%)')
    ax_sc.set_ylabel('Retorno predicho (%)')
    ax_sc.set_title('Real vs Predicho (in-sample)')
    ax_sc.legend(fontsize=8)
    ax_sc.grid(True, alpha=0.25)

    # ── Right: normalized price time series ──────────────────
    colors = plt.cm.tab10.colors
    plot_tickers = [t for t in top5 if t in prices_df.columns]

    def normalize(series):
        return series / series.iloc[0] * 100

    if target in prices_df.columns:
        ax_ts.plot(prices_df.index, normalize(prices_df[target]),
                   color='black', linewidth=2.5, zorder=5,
                   label=f'{target} (objetivo)')

    for idx, ticker in enumerate(plot_tickers):
        r = corr_signs.get(ticker, 0)
        linestyle = '-' if r > 0 else '--'
        direction = '↑' if r > 0 else '↓'
        ax_ts.plot(prices_df.index, normalize(prices_df[ticker]),
                   color=colors[idx % 10], linestyle=linestyle,
                   linewidth=1.4, alpha=0.85,
                   label=f'{direction} {ticker}  r={r:+.2f}')

    ax_ts.set_xlabel('Fecha')
    ax_ts.set_ylabel('Precio normalizado (base = 100)')
    ax_ts.set_title('Serie de tiempo — objetivo y predictores')
    ax_ts.legend(fontsize=8, loc='upper left')
    ax_ts.grid(True, alpha=0.25)
    ax_ts.tick_params(axis='x', rotation=30)

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Análisis guardado en: {save_path}")
