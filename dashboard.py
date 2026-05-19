"""
SP500 Correlation Bot — Dashboard
Run with:  streamlit run dashboard.py --server.headless true
"""
import base64
import json
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import streamlit.components.v1 as _stc

from config import OUTPUTS_DIR, TOP_N_HIGHLIGHT
from reporting.html_builders import (
    _build_echarts_html, _build_table_html, _vol_norm,
    _SIGNALS_DESC, _FUND_DESC, _CACHE_SUBDIR, _CHART_START_DATE,
)

# ── Page config (must be first Streamlit call) ────────────────────────────────
st.set_page_config(
    page_title='SP500 Bot Dashboard',
    page_icon='📈',
    layout='wide',
)

# ── Mobile detection via JS → ?m=1 query param ───────────────────────────────
# Runs once on first load: if viewport ≤ 768 px, reloads with ?m=1 so Python
# can serve lighter charts and slimmer tables for the rest of the session.
_stc.html("""
<script>
(function(){
  try {
    var w = window.parent ? window.parent.innerWidth : window.innerWidth;
    if (w && w <= 768) {
      var u = new URL(window.parent.location.href);
      if (u.searchParams.get('m') !== '1') {
        u.searchParams.set('m', '1');
        window.parent.location.replace(u.toString());
      }
    }
  } catch(e) {}
})();
</script>
""", height=0)

is_mobile = st.query_params.get("m") == "1"

# ── Responsive CSS ────────────────────────────────────────────────────────────
st.markdown("""
<style>
@media (max-width: 768px) {
    /* Tighten container padding */
    .main .block-container {
        padding-left: 0.6rem !important;
        padding-right: 0.6rem !important;
        padding-top: 0.75rem !important;
        max-width: 100% !important;
    }
    /* Smaller page title */
    h1 { font-size: 1.25rem !important; line-height: 1.35 !important; }
    h2 { font-size: 1rem !important; }
    p  { font-size: 0.85rem !important; }
    /* Scrollable tab bar — no wrap, no overflow clip */
    [data-testid="stTabs"] > div:first-child {
        overflow-x: auto !important;
        -webkit-overflow-scrolling: touch !important;
        scrollbar-width: none !important;
    }
    [data-testid="stTabs"] > div:first-child::-webkit-scrollbar { display: none; }
    /* Compact tab labels */
    button[data-baseweb="tab"] {
        font-size: 0.6rem !important;
        padding: 0.3rem 0.35rem !important;
        white-space: nowrap !important;
        min-width: 0 !important;
    }
    /* Metric cards — 2-up layout */
    [data-testid="column"] { min-width: 0 !important; }
    [data-testid="stMetric"] { padding: 0.35rem 0.4rem !important; }
    [data-testid="stMetric"] label {
        font-size: 0.65rem !important;
        line-height: 1.2 !important;
    }
    [data-testid="stMetricValue"] { font-size: 1.05rem !important; }
    /* Dividers */
    hr { margin: 0.4rem 0 !important; }
}
</style>
""", unsafe_allow_html=True)

# ── Chart heights ─────────────────────────────────────────────────────────────
_CHART_H        = 400 if is_mobile else 880   # ECharts inner height
_CHART_IFRAME_H = _CHART_H + 55               # iframe wrapper height


def _html_iframe(html: str, height: int, scrolling: bool = False) -> None:
    b64 = base64.b64encode(html.encode()).decode()
    st.iframe(src=f"data:text/html;base64,{b64}", height=height)


def _render_cached(run_dir, name: str, height: int) -> bool:
    """Render pre-built HTML from cache. Returns True on cache hit."""
    cp = run_dir / _CACHE_SUBDIR / f'{name}.html'
    if cp.exists():
        _html_iframe(cp.read_text(encoding='utf-8'), height=height)
        return True
    return False


@st.cache_data
def _load_csv(path, **kwargs):
    return pd.read_csv(path, **kwargs)


# ── Page header ───────────────────────────────────────────────────────────────
st.title('📈 SP500 Correlation Bot')
if not is_mobile:
    st.markdown(
        """
        Correlation-based trading signal system for the full **S&P 500** universe.
        Daily returns are computed for all ~500 companies and Pearson correlations identified.
        A **Random Forest** regression model predicts each stock's 7-day return using its
        top correlated peers as features. Signals are classified as **BUY** (predicted return > 1 %),
        **SELL** (< −10 %) or **HOLD**, enriched with fundamental data, and displayed here
        alongside interactive price, volume and market-cap time series.
        """,
        unsafe_allow_html=False,
    )

# ── Always use the latest completed run ───────────────────────────────────────
run_dirs = sorted(
    [d for d in OUTPUTS_DIR.iterdir() if d.is_dir() and not d.name.startswith('.')],
    reverse=True,
)

if not run_dirs:
    st.warning('No runs found in outputs/. Run the bot first.')
    st.stop()

run_dir  = run_dirs[0]
corr_dir = run_dir / 'Correlation_method'


# ── Helpers ───────────────────────────────────────────────────────────────────

def _dual_scroll_table(df: pd.DataFrame, row_styles: dict = None, height: int = 520,
                        link_cols: dict = None, cell_hrefs: dict = None,
                        col_descriptions: dict = None):
    html = _build_table_html(df, row_styles, height, link_cols, cell_hrefs, col_descriptions)
    _html_iframe(html, height=height + 30, scrolling=False)


def _chart_title(title: str, tooltip: str):
    tip_json = json.dumps(tooltip)
    html = f"""<!DOCTYPE html><html><head><style>
body{{margin:0;padding:0;font-family:"Source Sans Pro",sans-serif;}}
.ttl{{font-size:1.05rem;font-weight:600;color:#0f0f0f;cursor:default;
      display:inline-block;padding:2px 0 3px;
      border-bottom:2px dashed #bbb;line-height:1.3;}}
</style></head><body>
<div class="ttl" id="ttl">{title}</div>
<script>
var pdoc = window.parent.document;
var tip = pdoc.getElementById('__chart_tip__');
if (!tip) {{
  tip = pdoc.createElement('div');
  tip.id = '__chart_tip__';
  tip.style.cssText = 'position:fixed;background:#222;color:#f5f5f5;padding:9px 13px;' +
    'border-radius:6px;font-size:13px;max-width:360px;line-height:1.5;z-index:99999;' +
    'pointer-events:none;display:none;white-space:normal;' +
    'box-shadow:0 2px 8px rgba(0,0,0,0.4);';
  pdoc.body.appendChild(tip);
}}
var el = document.getElementById('ttl');
var msg = {tip_json};
var timer = null;
el.addEventListener('mouseenter', function() {{
  timer = setTimeout(function() {{
    tip.textContent = msg;
    tip.style.display = 'block';
  }}, 2000);
}});
el.addEventListener('mousemove', function(e) {{
  var fr = window.frameElement ? window.frameElement.getBoundingClientRect() : {{left:0,top:0}};
  tip.style.left = (fr.left + e.clientX + 16) + 'px';
  tip.style.top  = (fr.top  + e.clientY - 10) + 'px';
}});
el.addEventListener('mouseleave', function() {{
  clearTimeout(timer);
  tip.style.display = 'none';
}});
</script>
</body></html>"""
    _html_iframe(html, height=38, scrolling=False)


def _echarts_dual_chart(df_all, top_t, nm, norm_fn, abs_fn,
                        title, y1_label, y2_label, height=None,
                        start_date=_CHART_START_DATE, top_t_bottom=None,
                        fit_to_highlights=True):
    h = height if height is not None else _CHART_H
    html = _build_echarts_html(df_all, top_t, nm, norm_fn, abs_fn,
                               title, y1_label, y2_label, h,
                               start_date, top_t_bottom, fit_to_highlights)
    _html_iframe(html, height=h + 55, scrolling=False)


def _cached_chart(name: str, fallback_fn, *args, **kwargs):
    """Load mobile or desktop cache; fall back to live render on miss."""
    cache_name = f'{name}_mobile' if is_mobile else name
    if not _render_cached(run_dir, cache_name, _CHART_IFRAME_H):
        fallback_fn(*args, **kwargs)


# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_signals, tab_fund, tab_mcap, tab_prices, tab_volume, tab_returns, tab_corr = st.tabs([
    '📋 Signals',
    '🏦 Fundamentals',
    '📊 Mkt Cap',
    '📈 Prices',
    '📦 Volume',
    '💹 Returns',
    '🔗 Correlation',
])


# ── Tab 1: Signals ────────────────────────────────────────────────────────────
with tab_signals:
    signals_path = run_dir / 'signals.csv'
    if not signals_path.exists():
        st.info('signals.csv not found for this run.')
    else:
        df = _load_csv(str(signals_path))

        buys  = (df['signal'] == 'BUY').sum()
        sells = (df['signal'] == 'SELL').sum()
        holds = (df['signal'] == 'HOLD').sum()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric('Tickers' if is_mobile else 'Total tickers', len(df))
        c2.metric('BUY',  buys)
        c3.metric('SELL', sells)
        c4.metric('HOLD', holds)
        st.divider()

        table_cache = 'signals_table_mobile' if is_mobile else 'signals_table'
        table_h     = 360 if is_mobile else 500
        if not _render_cached(run_dir, table_cache, table_h + 30):
            top_return_tickers = set(
                df.dropna(subset=['predicted_return'])
                  .nlargest(TOP_N_HIGHLIGHT, 'predicted_return')['ticker']
            )
            SIG_STYLE = {
                'BUY':  'background-color:#d4edda;color:#155724',
                'SELL': 'background-color:#f8d7da;color:#721c24',
                'HOLD': 'background-color:#fff3cd;color:#856404',
            }
            TOP_RETURN_STYLE = 'background-color:#cce5ff;color:#004085;font-weight:bold'
            row_styles = {}
            for i, row in df.iterrows():
                sig  = SIG_STYLE.get(row.get('signal', ''), '')
                tick = row.get('ticker', '')
                if tick in top_return_tickers and not sig:
                    row_styles[i] = TOP_RETURN_STYLE
                elif sig:
                    row_styles[i] = sig

            df_reset = df.reset_index(drop=True)
            if is_mobile:
                from reporting.precompute import _MOBILE_SIG_COLS
                df_reset = df_reset[[c for c in _MOBILE_SIG_COLS if c in df_reset.columns]]
            else:
                cell_hrefs = {}
                if corr_dir.exists():
                    for i, row in df_reset.iterrows():
                        plot = corr_dir / f'analysis_{row["ticker"]}.png'
                        if plot.exists():
                            b64 = base64.b64encode(plot.read_bytes()).decode()
                            cell_hrefs[('signal', i)] = f'data:image/png;base64,{b64}'

            _dual_scroll_table(
                df_reset, row_styles, height=table_h,
                link_cols={'ticker': 'https://finance.yahoo.com/quote/{value}'},
                cell_hrefs=(cell_hrefs if not is_mobile else None),
                col_descriptions=_SIGNALS_DESC,
            )

        st.caption(
            '🔵 Top predicted  🟢 BUY  🔴 SELL  🟡 HOLD'
            if is_mobile else
            f'🔵 Top {TOP_N_HIGHLIGHT} highest predicted return  '
            '🟢 BUY  🔴 SELL  🟡 HOLD  '
            '(underlined signal = click to view prediction chart)'
        )


# ── Tab 2: Fundamentals ───────────────────────────────────────────────────────
with tab_fund:
    path = run_dir / 'fundamentals.csv'
    if not path.exists():
        st.info('fundamentals.csv not found for this run.')
    else:
        df = _load_csv(str(path), index_col=0)

        c1, c2, c3 = st.columns(3)
        c1.metric('Companies', len(df))
        if 'likelihood_pct' in df.columns:
            c2.metric('Avg score', f"{df['likelihood_pct'].mean():.1f}%")
            c3.metric('Top score', f"{df['likelihood_pct'].max():.1f}%")
        st.divider()

        table_cache = 'fund_table_mobile' if is_mobile else 'fund_table'
        table_h     = 360 if is_mobile else 540
        if not _render_cached(run_dir, table_cache, table_h + 30):
            row_styles = {}
            if 'likelihood_pct' in df.columns:
                for i, val in enumerate(df['likelihood_pct']):
                    try:
                        v = float(val)
                        if v >= 70:
                            row_styles[i] = 'background-color:#d4edda;color:#155724'
                        elif v >= 50:
                            row_styles[i] = 'background-color:#fff3cd;color:#856404'
                        else:
                            row_styles[i] = 'background-color:#f8d7da;color:#721c24'
                    except Exception:
                        pass
            df_fund = df.reset_index()
            if is_mobile:
                from reporting.precompute import _MOBILE_FUND_COLS
                df_fund = df_fund[[c for c in _MOBILE_FUND_COLS if c in df_fund.columns]]
            _dual_scroll_table(df_fund, row_styles, height=table_h,
                               link_cols={'ticker': 'https://finance.yahoo.com/quote/{value}'},
                               col_descriptions=_FUND_DESC)

        st.caption('🟢 ≥70%  🟡 ≥50%  🔴 <50%  likelihood of price increase in 12 months')


# ── Tab 3: Market Cap ─────────────────────────────────────────────────────────
with tab_mcap:
    signals_path = run_dir / 'signals.csv'
    if not signals_path.exists():
        st.info('signals.csv not found for this run.')
    else:
        sdf = _load_csv(str(signals_path))
        if {'ticker', 'company_name', 'current_price', 'market_cap_B', 'sector'}.issubset(sdf.columns):
            sdf = sdf.dropna(subset=['market_cap_B']).sort_values('market_cap_B', ascending=False)
            top    = sdf.head(TOP_N_HIGHLIGHT)
            bottom = sdf.tail(TOP_N_HIGHLIGHT)

            bar_h = 420 if is_mobile else 750
            fig = make_subplots(
                rows=2, cols=1, shared_xaxes=False, vertical_spacing=0.12,
                subplot_titles=[
                    f'Close Price ($) — top {TOP_N_HIGHLIGHT} vs bottom {TOP_N_HIGHLIGHT}',
                    f'Market Cap ($B) — top {TOP_N_HIGHLIGHT} vs bottom {TOP_N_HIGHLIGHT}',
                ],
            )
            hover_price = ('<b>%{customdata[0]}</b><br>Sector: %{customdata[1]}<br>'
                           'Price: $%{y:,.2f}<br>Cap: $%{customdata[2]:.1f}B<extra></extra>')
            hover_cap   = ('<b>%{customdata[0]}</b><br>Sector: %{customdata[1]}<br>'
                           'Cap: $%{y:.1f}B<br>Price: $%{customdata[2]:,.2f}<extra></extra>')

            for grp, colour, name in [(top,    'mediumseagreen', f'Top {TOP_N_HIGHLIGHT}'),
                                      (bottom, 'tomato',         f'Bottom {TOP_N_HIGHLIGHT}')]:
                fig.add_trace(go.Bar(
                    x=grp['ticker'], y=grp['current_price'], name=name,
                    marker_color=colour,
                    customdata=grp[['company_name', 'sector', 'market_cap_B']].values,
                    hovertemplate=hover_price,
                ), row=1, col=1)
                fig.add_trace(go.Bar(
                    x=grp['ticker'], y=grp['market_cap_B'], name=name,
                    marker_color=colour, showlegend=False,
                    customdata=grp[['company_name', 'sector', 'current_price']].values,
                    hovertemplate=hover_cap,
                ), row=2, col=1)

            fig.update_layout(
                height=bar_h,
                title=f'Top vs Bottom {TOP_N_HIGHLIGHT} S&P 500 Companies',
                barmode='group',
                legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
                margin=dict(l=40, r=10, t=60, b=40) if is_mobile else {},
            )
            fig.update_yaxes(title_text='Price ($)',       row=1, col=1)
            fig.update_yaxes(title_text='Market Cap ($B)', row=2, col=1)
            _chart_title('Market Cap Bars — hover bars for details',
                'Bar chart comparing the last closing price (top) and current market capitalisation in $B (bottom) '
                f'for the top {TOP_N_HIGHLIGHT} and bottom {TOP_N_HIGHLIGHT} S&P 500 companies by market cap. '
                'Hover any bar to see company name, sector, price and cap. Green = top companies, red = bottom.')
            st.plotly_chart(fig, width='stretch')

            # Time series charts — desktop only (too complex for small screens)
            if not is_mobile:
                prices_path = run_dir / 'prices.csv'
                if prices_path.exists():
                    prices_df = _load_csv(str(prices_path), index_col=0, parse_dates=True)
                    nm = dict(zip(sdf['ticker'], sdf['company_name']))

                    mcap_series = {}
                    for _, r in sdf.iterrows():
                        t = r['ticker']
                        if t in prices_df.columns and r['current_price'] > 0:
                            shares = r['market_cap_B'] / r['current_price']
                            mcap_series[t] = prices_df[t] * shares
                    mcap_df = pd.DataFrame(mcap_series)

                    if not mcap_df.empty:
                        by_abs  = [t for t in sdf['ticker'] if t in mcap_df.columns][:TOP_N_HIGHLIGHT]
                        _mcap_f = mcap_df.loc[mcap_df.index >= pd.Timestamp(_CHART_START_DATE)]
                        by_norm = (_mcap_f.iloc[-1] / _mcap_f.iloc[0]).sort_values(ascending=False).index.tolist()[:TOP_N_HIGHLIGHT]

                        st.divider()
                        _chart_title(f'Market Cap Time Series — Top {TOP_N_HIGHLIGHT} by Current Market Cap',
                            f'Estimated historical market capitalisation for the {TOP_N_HIGHLIGHT} largest S&P 500 companies today. '
                            'Approximated as: price × (current_market_cap / current_price). '
                            'Top subplot: normalised to base=100 at the first data point (relative growth). '
                            'Bottom subplot: absolute market cap in $B. Gray lines = all other S&P 500 companies.')
                        if not _render_cached(run_dir, 'mcap_series_abs', 935):
                            _echarts_dual_chart(
                                mcap_df, by_abs, nm,
                                norm_fn=lambda s: s / s.iloc[0] * 100,
                                abs_fn=lambda s: s,
                                title=f'Top {TOP_N_HIGHLIGHT} by Current Market Cap',
                                y1_label='Normalized (base=100)', y2_label='Market Cap ($B)',
                            )
                        st.divider()
                        _chart_title(f'Market Cap Time Series — Top {TOP_N_HIGHLIGHT} by Normalized Cap Growth',
                            f'Same data as above, but highlights the {TOP_N_HIGHLIGHT} companies with the highest '
                            f'market cap growth since {_CHART_START_DATE}. '
                            'Top subplot: normalised growth. Bottom subplot: absolute cap in $B.')
                        if not _render_cached(run_dir, 'mcap_series_norm', 935):
                            _echarts_dual_chart(
                                mcap_df, by_norm, nm,
                                norm_fn=lambda s: s / s.iloc[0] * 100,
                                abs_fn=lambda s: s,
                                title=f'Top {TOP_N_HIGHLIGHT} by Normalized Cap Growth',
                                y1_label='Normalized (base=100)', y2_label='Market Cap ($B)',
                            )
        else:
            st.info('Required columns missing in signals.csv.')


# ── Tab 4: Price Series ───────────────────────────────────────────────────────
with tab_prices:
    signals_path = run_dir / 'signals.csv'
    prices_path  = run_dir / 'prices.csv'
    if prices_path.exists() and signals_path.exists():
        prices_df = _load_csv(str(prices_path), index_col=0, parse_dates=True)
        sdf_full  = _load_csv(str(signals_path))
        nm        = dict(zip(sdf_full['ticker'], sdf_full.get('company_name', sdf_full['ticker'])))

        mcap_col = 'market_cap_B' if 'market_cap_B' in sdf_full.columns else None
        by_mcap  = (sdf_full.dropna(subset=[mcap_col])
                             .sort_values(mcap_col, ascending=False)['ticker'].tolist()
                    if mcap_col else list(prices_df.columns))
        by_price = prices_df.iloc[-1].sort_values(ascending=False).index.tolist()
        _pf = prices_df.loc[prices_df.index >= pd.Timestamp(_CHART_START_DATE)]
        by_norm_price = (_pf.iloc[-1] / _pf.iloc[0]).sort_values(ascending=False).index.tolist() if not _pf.empty else by_price
        by_norm = (prices_df.iloc[-1] / prices_df.iloc[0]).sort_values(ascending=False).index.tolist()

        _chart_args = dict(norm_fn=lambda s: s / s.iloc[0] * 100, abs_fn=lambda s: s,
                           y1_label='Normalized (base=100)', y2_label='Close price ($)')

        if is_mobile:
            # Mobile: 2 charts only
            _price_charts_mobile = [
                ('price_by_mcap_mobile',       by_mcap,
                 f'Prices — Top {TOP_N_HIGHLIGHT} by Market Cap',
                 f'Top {TOP_N_HIGHLIGHT} largest S&P 500 companies by market cap. '
                 'Normalized to base=100 (top) and absolute price in $ (bottom).'),
                ('price_by_norm_price_mobile', by_norm_price,
                 f'Prices — Top {TOP_N_HIGHLIGHT} Best Performers',
                 f'Best-performing stocks since {_CHART_START_DATE}. '
                 'Normalized to base=100 (top) and absolute price in $ (bottom).'),
            ]
            for cname, ordering, title, tip in _price_charts_mobile:
                top_t = [t for t in ordering if t in prices_df.columns][:TOP_N_HIGHLIGHT]
                _chart_title(title, tip)
                if not _render_cached(run_dir, cname, _CHART_IFRAME_H):
                    _echarts_dual_chart(prices_df, top_t, nm, title=title, **_chart_args)
                st.divider()
        else:
            # Desktop: 4 charts
            _price_charts = [
                ('price_by_mcap',       by_mcap,
                 f'Price Series — Top {TOP_N_HIGHLIGHT} by Market Cap',
                 f'Highlights the {TOP_N_HIGHLIGHT} largest S&P 500 companies by current market cap. '
                 f'Top subplot: price normalised to base=100 at {_CHART_START_DATE} (shows relative growth). '
                 'Bottom subplot: absolute closing price in $. Gray lines = all other companies.'),
                ('price_by_price',      by_price,
                 f'Price Series — Top {TOP_N_HIGHLIGHT} by Stock Price',
                 f'Highlights the {TOP_N_HIGHLIGHT} companies with the highest absolute closing price today. '
                 'Note: high share price does not imply a large company. Top: normalised. Bottom: absolute $ price.'),
                ('price_by_norm_price', by_norm_price,
                 f'Price Series — Top {TOP_N_HIGHLIGHT} by Normalized Stock Price',
                 f'Highlights the {TOP_N_HIGHLIGHT} best-performing stocks since {_CHART_START_DATE}. '
                 'Top: normalised. Bottom: absolute price.'),
                ('price_by_norm',       by_norm,
                 f'Price Series — Top {TOP_N_HIGHLIGHT} by Normalized Return (full history)',
                 f'Highlights the {TOP_N_HIGHLIGHT} best-performing stocks from their first data point. '
                 'Top: normalised. Bottom: absolute price.'),
            ]
            for cname, ordering, title, tip in _price_charts:
                top_t = [t for t in ordering if t in prices_df.columns][:TOP_N_HIGHLIGHT]
                _chart_title(title, tip)
                if not _render_cached(run_dir, cname, 935):
                    _echarts_dual_chart(prices_df, top_t, nm, title=title, **_chart_args)
                st.divider()
    else:
        st.info('prices.csv not found — re-run the bot to enable interactive charts.')


# ── Tab 5: Volume ─────────────────────────────────────────────────────────────
with tab_volume:
    volume_path = run_dir / 'volume.csv'
    if not volume_path.exists():
        st.info('volume.csv not found — re-run the bot to enable this tab.')
    else:
        vol_df  = _load_csv(str(volume_path), index_col=0, parse_dates=True)
        sdf_vol = _load_csv(str(run_dir / 'signals.csv')) if (run_dir / 'signals.csv').exists() else None
        nm_vol  = (dict(zip(sdf_vol['ticker'], sdf_vol['company_name']))
                   if sdf_vol is not None and 'company_name' in sdf_vol.columns else {})

        by_abs_v   = vol_df.mean().sort_values(ascending=False).index.tolist()[:TOP_N_HIGHLIGHT]
        _norm_last = {t: _vol_norm(vol_df[t]).iloc[-1] for t in vol_df.columns}
        by_norm_v  = sorted(_norm_last, key=lambda t: _norm_last[t] if pd.notna(_norm_last[t]) else 0,
                            reverse=True)[:TOP_N_HIGHLIGHT]

        _chart_title(f'Volume — Top {TOP_N_HIGHLIGHT} by Average Volume',
            f'Highlights the {TOP_N_HIGHLIGHT} most actively traded S&P 500 stocks by average daily volume. '
            'Top subplot: volume normalised to base=100 (relative trend). '
            'Bottom subplot: absolute daily trading volume in shares.')
        _cached_chart('volume_abs', _echarts_dual_chart,
            vol_df, by_abs_v, nm_vol,
            norm_fn=_vol_norm, abs_fn=lambda s: s,
            title=f'Top {TOP_N_HIGHLIGHT} by Average Volume',
            y1_label='Normalized (base=100)', y2_label='Volume (shares)')

        if not is_mobile:
            st.divider()
            _chart_title(f'Volume — Top {TOP_N_HIGHLIGHT} by Normalized Volume Growth',
                f'Highlights the {TOP_N_HIGHLIGHT} stocks with the most volume growth relative to their own history. '
                'Top subplot: normalised volume. Bottom: absolute shares traded.')
            if not _render_cached(run_dir, 'volume_norm', 935):
                _echarts_dual_chart(
                    vol_df, by_norm_v, nm_vol,
                    norm_fn=_vol_norm, abs_fn=lambda s: s,
                    title=f'Top {TOP_N_HIGHLIGHT} by Normalized Volume Growth',
                    y1_label='Normalized (base=100)', y2_label='Volume (shares)',
                )


# ── Tab 6: Cumulative Returns ─────────────────────────────────────────────────
with tab_returns:
    prices_path_r = run_dir / 'prices.csv'
    if not prices_path_r.exists():
        st.info('prices.csv not found — re-run the bot to enable this tab.')
    else:
        ret_prices = _load_csv(str(prices_path_r), index_col=0, parse_dates=True)
        sdf_r = _load_csv(str(run_dir / 'signals.csv')) if (run_dir / 'signals.csv').exists() else None
        nm_r  = (dict(zip(sdf_r['ticker'], sdf_r['company_name']))
                 if sdf_r is not None and 'company_name' in sdf_r.columns else {})

        _ret_f  = ret_prices.loc[ret_prices.index >= pd.Timestamp(_CHART_START_DATE)]
        top_t_r = ((_ret_f.iloc[-1] / _ret_f.iloc[0] - 1) * 100).sort_values(ascending=False).index.tolist()[:TOP_N_HIGHLIGHT]

        _chart_title(f'Cumulative Returns — Top {TOP_N_HIGHLIGHT} best performers',
            f'Highlights the {TOP_N_HIGHLIGHT} stocks with the highest cumulative return since {_CHART_START_DATE}. '
            'Top subplot: cumulative % return. '
            'Bottom subplot: dollar return per share. '
            'Gray lines = all other S&P 500 companies.')
        _cached_chart('returns', _echarts_dual_chart,
            ret_prices, top_t_r, nm_r,
            norm_fn=lambda s: (s / s.iloc[0] - 1) * 100,
            abs_fn=lambda s: s - s.iloc[0],
            title=f'Cumulative Returns — Top {TOP_N_HIGHLIGHT} best performers highlighted',
            y1_label='Cum. return (%)', y2_label='$ return/share')


# ── Tab 7: Correlation Analysis ───────────────────────────────────────────────
with tab_corr:
    if not corr_dir.exists():
        st.info('No Correlation_method/ plots found for this run.')
    else:
        matrix_path = corr_dir / 'correlation_matrix.png'
        if matrix_path.exists():
            _chart_title('Correlation Matrix',
                f'Pearson correlation matrix for the top {TOP_N_HIGHLIGHT} S&P 500 companies by market cap. '
                'Red = strong inverse correlation. Green = strong direct correlation. '
                'Values close to 0 indicate little or no linear relationship.')
            st.image(str(matrix_path), width='stretch')
            st.divider()
        else:
            st.info('No plots found in Correlation_method/ for this run.')

        # Interactive chart — desktop only (multiselect unusable on mobile)
        if not is_mobile:
            prices_path_c  = run_dir / 'prices.csv'
            signals_path_c = run_dir / 'signals.csv'
            if prices_path_c.exists() and signals_path_c.exists():
                prices_c = _load_csv(str(prices_path_c), index_col=0, parse_dates=True)
                sdf_c    = _load_csv(str(signals_path_c))
                nm_c     = (dict(zip(sdf_c['ticker'], sdf_c['company_name']))
                            if 'company_name' in sdf_c.columns else {})

                mcap_col_c = 'market_cap_B' if 'market_cap_B' in sdf_c.columns else None
                if mcap_col_c:
                    corr_tickers = (sdf_c.dropna(subset=[mcap_col_c])
                                         .sort_values(mcap_col_c, ascending=False)['ticker']
                                         .head(TOP_N_HIGHLIGHT).tolist())
                else:
                    corr_tickers = list(prices_c.columns)[:TOP_N_HIGHLIGHT]
                corr_tickers = [t for t in corr_tickers if t in prices_c.columns]

                opt_map = {f"{nm_c.get(t, t)} ({t})": t for t in corr_tickers}
                selected_labels = st.multiselect(
                    'Select companies to plot',
                    options=list(opt_map.keys()),
                    default=list(opt_map.keys())[:5],
                )
                selected_t = [opt_map[lbl] for lbl in selected_labels]

                if selected_t:
                    _chart_title('Price Series — Selected Companies',
                        'Interactive price chart for the companies chosen above. '
                        'Top subplot: price normalised to base=100. '
                        'Bottom subplot: absolute closing price in $.')
                    _echarts_dual_chart(
                        prices_c[selected_t], selected_t, nm_c,
                        norm_fn=lambda s: s / s.iloc[0] * 100,
                        abs_fn=lambda s: s,
                        title='Price Series — Selected Companies',
                        y1_label='Normalized (base=100)',
                        y2_label='Close price ($)',
                    )
                else:
                    st.info('Select at least one company above to display the chart.')
        else:
            st.caption('Open on desktop to use the interactive correlation chart.')

# ── Footer ────────────────────────────────────────────────────────────────────
try:
    from datetime import datetime as _dt
    _run_ts = _dt.strptime(run_dir.name, '%Y-%m-%d_%H-%M').strftime('%Y-%m-%d %H:%M UTC')
except Exception:
    _run_ts = run_dir.name

st.divider()
st.markdown(
    f"<div style='text-align:center;color:#666;font-size:0.8rem;padding:0.4rem 0 1rem;'>"
    f"🕐 Last bot run: <strong style='color:#aaa;'>{_run_ts}</strong>"
    f"</div>",
    unsafe_allow_html=True,
)
