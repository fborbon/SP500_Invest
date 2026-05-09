import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots

from config import OUTPUTS_DIR, TOP_N_HIGHLIGHT

COLORS = [
    '#1f77b4','#ff7f0e','#2ca02c','#d62728','#9467bd',
    '#8c564b','#e377c2','#7f7f7f','#bcbd22','#17becf',
    '#aec7e8','#ffbb78','#98df8a','#ff9896','#c5b0d5',
    '#c49c94','#f7b6d2','#dbdb8d','#9edae5','#ad494a',
]

_EXPORT = dict(width=1800, height=1200, scale=2)

# Max data points per trace for PNG export — prevents kaleido timeout on long histories
_MAX_BG_PTS = 200   # background (gray) traces
_MAX_FG_PTS = 800   # foreground (colored) traces


def _step(n: int, max_pts: int) -> int:
    """Downsample step so that n points become at most max_pts."""
    return max(1, n // max_pts)


def _save(fig, path):
    pio.write_image(fig, str(path), **_EXPORT)
    print(f"  Saved: {path}")


def _dt(index):
    """Convert DatetimeIndex to ISO date strings — kaleido/orjson cannot serialize Timestamps."""
    try:
        return index.strftime('%Y-%m-%d').tolist()
    except AttributeError:
        return list(index)


def plot_correlation_matrix(corr_matrix, save_path=None):
    if save_path is None:
        save_path = OUTPUTS_DIR / 'correlation_matrix.png'

    n = len(corr_matrix)
    vals = corr_matrix.values
    labels = corr_matrix.columns.tolist()

    text = [[f'{vals[i,j]:.2f}' for j in range(n)] for i in range(n)]

    fig = go.Figure(go.Heatmap(
        z=vals, x=labels, y=labels,
        text=text, texttemplate='%{text}', textfont=dict(size=7),
        colorscale='RdYlGn', zmin=-1, zmax=1,
        colorbar=dict(title='Pearson r'),
    ))
    fig.update_layout(
        title=f'Correlation Matrix — Top {n} S&P 500 companies by market cap',
        height=900, width=1000,
        xaxis=dict(tickangle=45, tickfont=dict(size=9)),
        yaxis=dict(autorange='reversed', tickfont=dict(size=9)),
        margin=dict(l=80, r=40, t=60, b=120),
    )
    _save(fig, save_path)


def plot_price_series(prices_df, tickers_ordered, top_n=TOP_N_HIGHLIGHT, label='market cap',
                      save_path=None):
    if save_path is None:
        save_path = OUTPUTS_DIR / 'price_series_market-cap.png'

    top_t = [t for t in tickers_ordered if t in prices_df.columns][:top_n]

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.06,
                        subplot_titles=['Normalized price (base = 100)', 'Close price ($)'])

    n      = len(prices_df)
    bg_s   = _step(n, _MAX_BG_PTS)
    fg_s   = _step(n, _MAX_FG_PTS)

    x_bg_n, y_bg_n, x_bg_a, y_bg_a = [], [], [], []
    for t in prices_df.columns:
        if t not in top_t:
            nv = prices_df[t] / prices_df[t].iloc[0] * 100
            x_bg_n.extend(_dt(prices_df.index[::bg_s]) + [None]); y_bg_n.extend(list(nv.iloc[::bg_s]) + [None])
            x_bg_a.extend(_dt(prices_df.index[::bg_s]) + [None]); y_bg_a.extend(list(prices_df[t].iloc[::bg_s]) + [None])
    if x_bg_n:
        for rn, xb, yb in [(1, x_bg_n, y_bg_n), (2, x_bg_a, y_bg_a)]:
            fig.add_trace(go.Scatter(x=xb, y=yb, mode='lines',
                                     line=dict(color='lightgray', width=0.5),
                                     showlegend=False, hoverinfo='skip'), row=rn, col=1)

    for i, t in enumerate(top_t):
        nv    = prices_df[t] / prices_df[t].iloc[0] * 100
        color = COLORS[i % len(COLORS)]
        fig.add_trace(go.Scatter(x=_dt(prices_df.index[::fg_s]), y=nv.iloc[::fg_s], mode='lines', name=t,
                                  line=dict(color=color, width=1.5)), row=1, col=1)
        fig.add_trace(go.Scatter(x=_dt(prices_df.index[::fg_s]), y=prices_df[t].iloc[::fg_s], mode='lines', name=t,
                                  line=dict(color=color, width=1.5),
                                  showlegend=False), row=2, col=1)

    fig.update_layout(
        title=f'S&P 500 Price Series — Top {len(top_t)} by {label} highlighted',
        height=1000, legend=dict(orientation='h', y=1.02, x=1, xanchor='right'),
    )
    fig.update_yaxes(title_text='Normalized (base=100)', row=1, col=1)
    fig.update_yaxes(title_text='Close price ($)',        row=2, col=1)
    fig.update_xaxes(title_text='Date',                   row=2, col=1)
    _save(fig, save_path)


def plot_market_cap_bars(prices_df, tickers_ordered, market_caps=None,
                         top_n=TOP_N_HIGHLIGHT, save_path=None):
    if save_path is None:
        save_path = OUTPUTS_DIR / 'market_cap_bars.png'

    available = [t for t in tickers_ordered if t in prices_df.columns]
    top        = available[:top_n]
    bottom     = available[-top_n:] if len(available) >= top_n * 2 else available[top_n:]

    fig = make_subplots(rows=2, cols=1, vertical_spacing=0.12,
                        subplot_titles=['Last Close Price ($)', 'Market Capitalization ($B)'])

    for grp, color, name in [(top, 'mediumseagreen', f'Top {len(top)}'),
                              (bottom, 'tomato', f'Bottom {len(bottom)}')]:
        prices = [prices_df[t].iloc[-1] for t in grp]
        fig.add_trace(go.Bar(x=grp, y=prices, name=name, marker_color=color), row=1, col=1)
        if market_caps:
            caps = [market_caps.get(t, 0) / 1e9 for t in grp]
            fig.add_trace(go.Bar(x=grp, y=caps, name=name, marker_color=color,
                                  showlegend=False), row=2, col=1)

    fig.update_layout(
        title=f'Top {len(top)} vs Bottom {len(bottom)} S&P 500 Companies',
        height=900, barmode='group',
        legend=dict(orientation='h', y=1.02, x=1, xanchor='right'),
    )
    fig.update_yaxes(title_text='Price ($)',       row=1, col=1)
    fig.update_yaxes(title_text='Market Cap ($B)', row=2, col=1)
    _save(fig, save_path)


def plot_market_cap_series(prices_df, market_caps: dict, top_n=TOP_N_HIGHLIGHT,
                           save_path_abs=None, save_path_norm=None):
    if save_path_abs  is None: save_path_abs  = OUTPUTS_DIR / 'market_cap_series_absolute.png'
    if save_path_norm is None: save_path_norm = OUTPUTS_DIR / 'market_cap_series_normalized.png'

    mcap_series = {}
    for t in prices_df.columns:
        cap_usd = market_caps.get(t, 0)
        price   = prices_df[t].iloc[-1]
        if cap_usd > 0 and price > 0:
            mcap_series[t] = prices_df[t] * (cap_usd / price) / 1e9
    if not mcap_series:
        print("  ✗ No market cap data for time series.")
        return
    mcap_df = pd.DataFrame(mcap_series)

    by_abs  = sorted(mcap_series, key=lambda t: market_caps.get(t, 0), reverse=True)
    by_norm = (mcap_df.iloc[-1] / mcap_df.iloc[0]).sort_values(ascending=False).index.tolist()

    def _plot(ordered, save_path, label):
        top_t  = ordered[:top_n]
        nm     = len(mcap_df)
        bg_s   = _step(nm, _MAX_BG_PTS)
        fg_s   = _step(nm, _MAX_FG_PTS)
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.06,
                            subplot_titles=['Normalized market cap (base = 100)', 'Market cap ($B)'])
        x_bg_n, y_bg_n, x_bg_a, y_bg_a = [], [], [], []
        for t in mcap_df.columns:
            if t not in top_t:
                nv = mcap_df[t] / mcap_df[t].iloc[0] * 100
                x_bg_n.extend(_dt(mcap_df.index[::bg_s]) + [None]); y_bg_n.extend(list(nv.iloc[::bg_s]) + [None])
                x_bg_a.extend(_dt(mcap_df.index[::bg_s]) + [None]); y_bg_a.extend(list(mcap_df[t].iloc[::bg_s]) + [None])
        if x_bg_n:
            for rn, xb, yb in [(1, x_bg_n, y_bg_n), (2, x_bg_a, y_bg_a)]:
                fig.add_trace(go.Scatter(x=xb, y=yb, mode='lines',
                                         line=dict(color='lightgray', width=0.5),
                                         showlegend=False, hoverinfo='skip'), row=rn, col=1)
        for i, t in enumerate(top_t):
            nv    = mcap_df[t] / mcap_df[t].iloc[0] * 100
            color = COLORS[i % len(COLORS)]
            fig.add_trace(go.Scatter(x=_dt(mcap_df.index[::fg_s]), y=nv.iloc[::fg_s], mode='lines', name=t,
                                      line=dict(color=color, width=1.5)), row=1, col=1)
            fig.add_trace(go.Scatter(x=_dt(mcap_df.index[::fg_s]), y=mcap_df[t].iloc[::fg_s], mode='lines', name=t,
                                      line=dict(color=color, width=1.5),
                                      showlegend=False), row=2, col=1)
        fig.update_layout(
            title=f'Market Cap Time Series — Top {top_n} by {label}',
            height=1000, legend=dict(orientation='h', y=1.02, x=1, xanchor='right'),
        )
        fig.update_yaxes(title_text='Normalized (base=100)', row=1, col=1)
        fig.update_yaxes(title_text='Market Cap ($B)',        row=2, col=1)
        fig.update_xaxes(title_text='Date',                   row=2, col=1)
        _save(fig, save_path)

    _plot(by_abs,  save_path_abs,  'current market cap')
    _plot(by_norm, save_path_norm, 'normalized cap growth')


def plot_volume_series(volume_df, top_n=TOP_N_HIGHLIGHT,
                       save_path_abs=None, save_path_norm=None):
    if save_path_abs  is None: save_path_abs  = OUTPUTS_DIR / 'volume_series_absolute.png'
    if save_path_norm is None: save_path_norm = OUTPUTS_DIR / 'volume_series_normalized.png'

    by_abs  = volume_df.mean().sort_values(ascending=False).index.tolist()
    by_norm = (volume_df.iloc[-1] / volume_df.iloc[0]).sort_values(ascending=False).index.tolist()

    def _plot(ordered, save_path, label):
        top_t  = [t for t in ordered if t in volume_df.columns][:top_n]
        nv_len = len(volume_df)
        bg_s   = _step(nv_len, _MAX_BG_PTS)
        fg_s   = _step(nv_len, _MAX_FG_PTS)
        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.06,
                            subplot_titles=['Normalized volume (base = 100)', 'Volume (shares)'])
        x_bg_n, y_bg_n, x_bg_a, y_bg_a = [], [], [], []
        for t in volume_df.columns:
            if t not in top_t:
                first = volume_df[t].replace(0, float('nan')).first_valid_index()
                nv = volume_df[t] / volume_df[t][first] * 100 if first else volume_df[t] * 0
                x_bg_n.extend(_dt(volume_df.index[::bg_s]) + [None]); y_bg_n.extend(list(nv.iloc[::bg_s]) + [None])
                x_bg_a.extend(_dt(volume_df.index[::bg_s]) + [None]); y_bg_a.extend(list(volume_df[t].iloc[::bg_s]) + [None])
        if x_bg_n:
            for rn, xb, yb in [(1, x_bg_n, y_bg_n), (2, x_bg_a, y_bg_a)]:
                fig.add_trace(go.Scatter(x=xb, y=yb, mode='lines',
                                         line=dict(color='lightgray', width=0.5),
                                         showlegend=False, hoverinfo='skip'), row=rn, col=1)
        for i, t in enumerate(top_t):
            first = volume_df[t].replace(0, float('nan')).first_valid_index()
            nv    = volume_df[t] / volume_df[t][first] * 100 if first else volume_df[t] * 0
            color = COLORS[i % len(COLORS)]
            fig.add_trace(go.Scatter(x=_dt(volume_df.index[::fg_s]), y=nv.iloc[::fg_s], mode='lines', name=t,
                                      line=dict(color=color, width=1.5)), row=1, col=1)
            fig.add_trace(go.Scatter(x=_dt(volume_df.index[::fg_s]), y=volume_df[t].iloc[::fg_s], mode='lines', name=t,
                                      line=dict(color=color, width=1.5),
                                      showlegend=False), row=2, col=1)
        fig.update_layout(
            title=f'Volume Time Series — Top {top_n} by {label}',
            height=1000, legend=dict(orientation='h', y=1.02, x=1, xanchor='right'),
        )
        fig.update_yaxes(title_text='Normalized (base=100)', row=1, col=1)
        fig.update_yaxes(title_text='Volume (shares)',        row=2, col=1)
        fig.update_xaxes(title_text='Date',                   row=2, col=1)
        _save(fig, save_path)

    _plot(by_abs,  save_path_abs,  'average volume')
    _plot(by_norm, save_path_norm, 'normalized volume growth')


def plot_cumulative_returns(prices_df, top_n=TOP_N_HIGHLIGHT, save_path=None):
    if save_path is None:
        save_path = OUTPUTS_DIR / 'cumulative_returns.png'

    cum_pct = (prices_df / prices_df.iloc[0] - 1) * 100
    cum_usd = prices_df - prices_df.iloc[0]
    top_t   = cum_pct.iloc[-1].sort_values(ascending=False).index.tolist()[:top_n]

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.06,
                        subplot_titles=['Cumulative return (%)', 'Dollar return ($ per share)'])

    n    = len(prices_df)
    bg_s = _step(n, _MAX_BG_PTS)
    fg_s = _step(n, _MAX_FG_PTS)

    x_bg_p, y_bg_p, x_bg_u, y_bg_u = [], [], [], []
    for t in prices_df.columns:
        if t not in top_t:
            x_bg_p.extend(_dt(cum_pct.index[::bg_s]) + [None]); y_bg_p.extend(list(cum_pct[t].iloc[::bg_s]) + [None])
            x_bg_u.extend(_dt(cum_usd.index[::bg_s]) + [None]); y_bg_u.extend(list(cum_usd[t].iloc[::bg_s]) + [None])
    if x_bg_p:
        for rn, xb, yb in [(1, x_bg_p, y_bg_p), (2, x_bg_u, y_bg_u)]:
            fig.add_trace(go.Scatter(x=xb, y=yb, mode='lines',
                                     line=dict(color='lightgray', width=0.5),
                                     showlegend=False, hoverinfo='skip'), row=rn, col=1)

    for i, t in enumerate(top_t):
        color = COLORS[i % len(COLORS)]
        fig.add_trace(go.Scatter(x=_dt(cum_pct.index[::fg_s]), y=cum_pct[t].iloc[::fg_s], mode='lines', name=t,
                                  line=dict(color=color, width=1.5)), row=1, col=1)
        fig.add_trace(go.Scatter(x=_dt(cum_usd.index[::fg_s]), y=cum_usd[t].iloc[::fg_s], mode='lines', name=t,
                                  line=dict(color=color, width=1.5),
                                  showlegend=False), row=2, col=1)

    for rn in [1, 2]:
        fig.add_hline(y=0, line_dash='dash', line_color='grey', line_width=1, row=rn, col=1)
    fig.update_layout(
        title=f'Cumulative Returns — Top {top_n} best performers highlighted',
        height=1000, legend=dict(orientation='h', y=1.02, x=1, xanchor='right'),
    )
    fig.update_yaxes(title_text='Cumulative return (%)',   row=1, col=1)
    fig.update_yaxes(title_text='Dollar return ($/share)', row=2, col=1)
    fig.update_xaxes(title_text='Date',                    row=2, col=1)
    _save(fig, save_path)


def plot_prediction_analysis(target: str, returns, prices_df,
                              top5: list, corr_signs: dict,
                              y_actual: np.ndarray, y_predicted: np.ndarray,
                              save_path=None):
    if save_path is None:
        save_path = OUTPUTS_DIR / f'analysis_{target}.png'

    r2 = float(np.corrcoef(y_actual, y_predicted)[0, 1] ** 2)

    fig = make_subplots(rows=1, cols=2,
                        subplot_titles=['Actual vs Predicted (in-sample)',
                                        'Price series — target and predictors'])

    # ── Left: scatter actual vs predicted ────────────────────────────────────
    fig.add_trace(go.Scatter(
        x=y_actual * 100, y=y_predicted * 100, mode='markers',
        marker=dict(color='steelblue', size=5, opacity=0.4),
        name='Observations',
    ), row=1, col=1)

    lim = max(abs(y_actual).max(), abs(y_predicted).max()) * 100 * 1.15
    fig.add_trace(go.Scatter(
        x=[-lim, lim], y=[-lim, lim], mode='lines',
        line=dict(color='black', dash='dash', width=1), name='Perfect prediction',
    ), row=1, col=1)

    m, b = np.polyfit(y_actual * 100, y_predicted * 100, 1)
    x_line = np.linspace(y_actual.min() * 100, y_actual.max() * 100, 100)
    fig.add_trace(go.Scatter(
        x=x_line, y=m * x_line + b, mode='lines',
        line=dict(color='crimson', width=2), name=f'Trend  R²={r2:.3f}',
    ), row=1, col=1)

    fig.add_hline(y=0, line_dash='dot', line_color='grey', line_width=0.8, row=1, col=1)
    fig.add_vline(x=0, line_dash='dot', line_color='grey', line_width=0.8, row=1, col=1)

    # ── Right: normalized price time series ──────────────────────────────────
    plot_tickers = [t for t in top5 if t in prices_df.columns]

    # Trim to target's first valid date so the x-axis has no empty space on the left
    if target in prices_df.columns:
        first_valid = prices_df[target].first_valid_index()
        if first_valid is not None:
            prices_df = prices_df.loc[first_valid:]

    n_right = len(prices_df)
    fg_s    = _step(n_right, _MAX_FG_PTS)

    def normalize(series):
        first = series.first_valid_index()
        return series / series[first] * 100 if first is not None else series

    if target in prices_df.columns:
        fig.add_trace(go.Scatter(
            x=_dt(prices_df.index[::fg_s]), y=normalize(prices_df[target]).iloc[::fg_s], mode='lines',
            name=f'{target} (target)', line=dict(color='black', width=2.5),
        ), row=1, col=2)

    for i, ticker in enumerate(plot_tickers):
        r         = corr_signs.get(ticker, 0)
        direction = '↑' if r > 0 else '↓'
        dash      = 'solid' if r > 0 else 'dash'
        fig.add_trace(go.Scatter(
            x=_dt(prices_df.index[::fg_s]), y=normalize(prices_df[ticker]).iloc[::fg_s], mode='lines',
            name=f'{direction} {ticker}  r={r:+.2f}',
            line=dict(color=COLORS[i % len(COLORS)], dash=dash, width=1.4),
        ), row=1, col=2)

    fig.update_layout(
        title=f'{target} — Prediction Analysis (Random Forest)',
        height=600, width=1400,
        legend=dict(orientation='v', x=1.01, y=1),
    )
    fig.update_xaxes(title_text='Actual cumulative return (%)',  row=1, col=1)
    fig.update_yaxes(title_text='Predicted return (%)',          row=1, col=1)
    fig.update_xaxes(title_text='Date',                          row=1, col=2)
    fig.update_yaxes(title_text='Normalized price (base=100)',   row=1, col=2)
    _save(fig, save_path)
