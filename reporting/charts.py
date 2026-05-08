import numpy as np
import matplotlib.pyplot as plt

from config import OUTPUTS_DIR, TOP_N_HIGHLIGHT


def plot_correlation_matrix(corr_matrix, save_path=None):
    """Save the correlation matrix as a heatmap PNG."""
    if save_path is None:
        save_path = OUTPUTS_DIR / 'correlation_matrix.png'

    fig, ax = plt.subplots(figsize=(14, 12))
    n = len(corr_matrix)
    im = ax.imshow(corr_matrix.values, cmap='RdYlGn', vmin=-1, vmax=1, aspect='auto')
    plt.colorbar(im, ax=ax, label='Pearson Correlation')

    ax.set_xticks(range(n))
    ax.set_yticks(range(n))
    ax.set_xticklabels(corr_matrix.columns, rotation=45, ha='right', fontsize=9)
    ax.set_yticklabels(corr_matrix.columns, fontsize=9)

    for i in range(n):
        for j in range(n):
            val = corr_matrix.values[i, j]
            color = 'black' if 0.3 < abs(val) < 0.8 else 'white'
            ax.text(j, i, f'{val:.2f}', ha='center', va='center', fontsize=7, color=color)

    ax.set_title(f'Correlation Matrix — Top {n} S&P 500 companies by market cap',
                 fontsize=14, pad=16)
    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Correlation matrix saved to: {save_path}")


def plot_price_series(prices_df, tickers_ordered, top_n=TOP_N_HIGHLIGHT, label='market cap',
                      save_path=None):
    """Two-subplot price time series for all tickers in prices_df.

    Top subplot    — normalized prices (base = 100).
    Bottom subplot — absolute close prices ($).

    Top N tickers (ordered by tickers_ordered) drawn in distinct colors with
    labels; all others as thin light-gray lines without labels.
    Both subplots share the same X axis and color coding.

    Args:
        label: describes how tickers_ordered is ranked (used in the plot title).
               e.g. 'market cap' or 'stock price'.
    """
    if save_path is None:
        save_path = OUTPUTS_DIR / 'price_series_market-cap.png'

    top_tickers = [t for t in tickers_ordered if t in prices_df.columns][:top_n]
    colors = plt.cm.tab20.colors

    fig, (ax_norm, ax_abs) = plt.subplots(2, 1, figsize=(18, 14), sharex=True,
                                           gridspec_kw={'hspace': 0.06})
    fig.suptitle(f'S&P 500 Price Series — Top {len(top_tickers)} by {label} highlighted',
                 fontsize=13, fontweight='bold')

    def normalize(series):
        return series / series.iloc[0] * 100

    for ax, use_norm in [(ax_norm, True), (ax_abs, False)]:
        # Background — all non-top tickers in gray
        for ticker in prices_df.columns:
            if ticker not in top_tickers:
                data = normalize(prices_df[ticker]) if use_norm else prices_df[ticker]
                ax.plot(prices_df.index, data,
                        color='lightgray', linewidth=0.6, alpha=0.6, zorder=1)

        # Foreground — top N tickers in color with labels
        for idx, ticker in enumerate(top_tickers):
            data = normalize(prices_df[ticker]) if use_norm else prices_df[ticker]
            ax.plot(prices_df.index, data,
                    color=colors[idx % 20], linewidth=1.6, alpha=0.9,
                    label=ticker, zorder=2)

        ax.grid(True, alpha=0.2)
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

    ax_norm.set_ylabel('Normalized price (base = 100)')
    ax_norm.set_title('Normalized prices')
    ax_norm.legend(fontsize=8, loc='upper left', ncol=3, framealpha=0.8)

    ax_abs.set_ylabel('Close price ($)')
    ax_abs.set_title('Absolute prices')
    ax_abs.legend(fontsize=8, loc='upper left', ncol=3, framealpha=0.8)
    ax_abs.set_xlabel('Date')
    ax_abs.tick_params(axis='x', rotation=30)

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Price series saved to: {save_path}")


def plot_market_cap_bars(prices_df, tickers_ordered, market_caps=None,
                         top_n=TOP_N_HIGHLIGHT, save_path=None):
    """Two-subplot bar chart for top N and bottom N companies (by market cap order).

    Top subplot    — last closing stock price ($).
    Bottom subplot — market capitalization ($B), requires market_caps dict.
                     If market_caps is None the bottom subplot is skipped.

    Both subplots share the same X axis (same companies, same order).
    Top N shown in green, bottom N in coral, with a gap between groups.
    """
    if save_path is None:
        save_path = OUTPUTS_DIR / 'market_cap_bars.png'

    available     = [t for t in tickers_ordered if t in prices_df.columns]
    top           = available[:top_n]
    bottom        = available[-top_n:] if len(available) >= top_n * 2 else available[top_n:]
    labels        = top + bottom
    n_bars        = len(labels)

    gap      = 2
    x_top    = list(range(len(top)))
    x_bottom = [x + len(top) + gap for x in range(len(bottom))]
    x_all    = x_top + x_bottom

    top_prices    = [prices_df[t].iloc[-1] for t in top]
    bottom_prices = [prices_df[t].iloc[-1] for t in bottom]

    n_rows  = 2 if market_caps else 1
    fig_h   = 7 * n_rows
    fig_w   = max(16, n_bars * 0.85)
    fig, axes = plt.subplots(n_rows, 1, figsize=(fig_w, fig_h),
                             sharex=True,
                             gridspec_kw={'hspace': 0.08})
    ax_price = axes[0] if n_rows == 2 else axes
    fig.suptitle(f'Top {len(top)} vs Bottom {len(bottom)} S&P 500 Companies',
                 fontsize=13, fontweight='bold', y=1.01)

    # ── Top subplot: last close price ────────────────────────
    def _bar_labels(ax, bars, fmt):
        for bar in bars:
            ax.text(bar.get_x() + bar.get_width() / 2,
                    bar.get_height() * 1.01,
                    fmt(bar.get_height()),
                    ha='center', va='bottom', fontsize=7, rotation=45)

    bt = ax_price.bar(x_top,    top_prices,    color='mediumseagreen', alpha=0.85,
                      edgecolor='white', linewidth=0.5,
                      label=f'Top {len(top)} (most valuable)')
    bb = ax_price.bar(x_bottom, bottom_prices, color='tomato',         alpha=0.85,
                      edgecolor='white', linewidth=0.5,
                      label=f'Bottom {len(bottom)} (least valuable)')
    _bar_labels(ax_price, bt + bb, lambda v: f'${v:,.0f}')
    ax_price.set_ylabel('Last Close Price ($)')
    ax_price.set_title('Stock Price')
    ax_price.legend(fontsize=8)
    ax_price.grid(axis='y', alpha=0.25)
    ax_price.spines['top'].set_visible(False)
    ax_price.spines['right'].set_visible(False)

    # ── Bottom subplot: market capitalisation ─────────────────
    if market_caps:
        ax_mcap = axes[1]
        top_caps    = [market_caps.get(t, 0) / 1e9 for t in top]
        bottom_caps = [market_caps.get(t, 0) / 1e9 for t in bottom]

        bt2 = ax_mcap.bar(x_top,    top_caps,    color='mediumseagreen', alpha=0.85,
                          edgecolor='white', linewidth=0.5)
        bb2 = ax_mcap.bar(x_bottom, bottom_caps, color='tomato',         alpha=0.85,
                          edgecolor='white', linewidth=0.5)
        _bar_labels(ax_mcap, bt2 + bb2,
                    lambda v: f'${v/1e3:.1f}T' if v >= 1000 else f'${v:.0f}B')
        ax_mcap.set_ylabel('Market Cap ($B)')
        ax_mcap.set_title('Market Capitalization')
        ax_mcap.set_xticks(x_all)
        ax_mcap.set_xticklabels(labels, rotation=45, ha='right', fontsize=9)
        ax_mcap.grid(axis='y', alpha=0.25)
        ax_mcap.spines['top'].set_visible(False)
        ax_mcap.spines['right'].set_visible(False)
    else:
        ax_price.set_xticks(x_all)
        ax_price.set_xticklabels(labels, rotation=45, ha='right', fontsize=9)

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Market cap bars saved to: {save_path}")


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
                  alpha=0.35, s=18, color='steelblue', label='Observations')

    lim = max(abs(y_actual).max(), abs(y_predicted).max()) * 100 * 1.15
    ax_sc.plot([-lim, lim], [-lim, lim], 'k--', linewidth=1, alpha=0.4,
               label='Perfect prediction')

    m, b = np.polyfit(y_actual * 100, y_predicted * 100, 1)
    x_line = np.linspace(y_actual.min() * 100, y_actual.max() * 100, 100)
    ax_sc.plot(x_line, m * x_line + b, color='crimson', linewidth=1.8,
               label=f'Trend  R²={r2:.3f}')

    ax_sc.axhline(0, color='grey', linewidth=0.5, alpha=0.6)
    ax_sc.axvline(0, color='grey', linewidth=0.5, alpha=0.6)
    ax_sc.set_aspect('equal', adjustable='box')
    ax_sc.set_xlabel('Actual cumulative return (%)')
    ax_sc.set_ylabel('Predicted return (%)')
    ax_sc.set_title('Actual vs Predicted (in-sample)')
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
                   label=f'{target} (target)')

    for idx, ticker in enumerate(plot_tickers):
        r = corr_signs.get(ticker, 0)
        linestyle = '-' if r > 0 else '--'
        direction = '↑' if r > 0 else '↓'
        ax_ts.plot(prices_df.index, normalize(prices_df[ticker]),
                   color=colors[idx % 10], linestyle=linestyle,
                   linewidth=1.4, alpha=0.85,
                   label=f'{direction} {ticker}  r={r:+.2f}')

    ax_ts.set_xlabel('Date')
    ax_ts.set_ylabel('Normalized price (base = 100)')
    ax_ts.set_title('Price series — target and predictors')
    ax_ts.legend(fontsize=8, loc='upper left')
    ax_ts.grid(True, alpha=0.25)
    ax_ts.tick_params(axis='x', rotation=30)

    plt.tight_layout()
    plt.savefig(save_path, dpi=150, bbox_inches='tight')
    plt.close()
    print(f"  Analysis saved to: {save_path}")
