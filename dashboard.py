"""
SP500 Correlation Bot — Dashboard
Run with:  streamlit run dashboard.py --server.headless true
"""
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import streamlit.components.v1 as components

from config import OUTPUTS_DIR, TOP_N_HIGHLIGHT

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title='SP500 Bot Dashboard',
    page_icon='📈',
    layout='wide',
)

st.title('📈 SP500 Correlation Bot — Dashboard')

# ── Run selector (sidebar) ────────────────────────────────────────────────────
run_dirs = sorted(
    [d for d in OUTPUTS_DIR.iterdir() if d.is_dir() and not d.name.startswith('.')],
    reverse=True,
)

if not run_dirs:
    st.warning('No runs found in outputs/. Run the bot first.')
    st.stop()

selected = st.sidebar.selectbox('Select run', [d.name for d in run_dirs], index=0)
run_dir  = OUTPUTS_DIR / selected
st.sidebar.caption(f'📁 {run_dir}')

corr_dir = run_dir / 'Correlation_method'

# ── Helpers ───────────────────────────────────────────────────────────────────

def _dual_scroll_table(df: pd.DataFrame, row_styles: dict = None, height: int = 520,
                        link_cols: dict = None):
    """Render a DataFrame as HTML with a synchronised scrollbar on top AND bottom.

    link_cols: maps column name → URL template with {value} placeholder.
               e.g. {'ticker': 'https://finance.yahoo.com/quote/{value}'}
    """
    rows_html = []
    for idx, row in df.iterrows():
        style = row_styles.get(idx, '') if row_styles else ''
        cells = []
        for col, v in zip(df.columns, row):
            if link_cols and col in link_cols:
                url = link_cols[col].format(value=v)
                cell = (f'<td style="padding:4px 10px;border:1px solid #eee;white-space:nowrap;">'
                        f'<a href="{url}" target="_blank" '
                        f'style="color:inherit;text-decoration:underline;">{v}</a></td>')
            else:
                cell = f'<td style="padding:4px 10px;border:1px solid #eee;white-space:nowrap;">{v}</td>'
            cells.append(cell)
        rows_html.append(f'<tr style="{style}">{"".join(cells)}</tr>')

    headers = ''.join(
        f'<th style="padding:6px 10px;border:1px solid #ddd;background:#f5f5f5;'
        f'white-space:nowrap;position:sticky;top:0;z-index:1;">{c}</th>'
        for c in df.columns
    )

    table_html = (
        f'<table style="border-collapse:collapse;font-size:12px;font-family:sans-serif;">'
        f'<thead><tr>{headers}</tr></thead>'
        f'<tbody>{"".join(rows_html)}</tbody>'
        f'</table>'
    )

    full_html = f"""
    <html><head><style>
      body{{margin:0;}}
      #top-bar{{overflow-x:scroll;overflow-y:hidden;height:18px;border-bottom:1px solid #ccc;}}
      #top-inner{{height:1px;}}
      #main{{overflow:auto;max-height:{height}px;}}
    </style></head><body>
      <div id="top-bar"><div id="top-inner"></div></div>
      <div id="main">{table_html}</div>
      <script>
        const m=document.getElementById('main');
        const t=document.getElementById('top-bar');
        const ti=document.getElementById('top-inner');
        function sync(){{ti.style.width=m.scrollWidth+'px';}}
        sync(); setTimeout(sync,300); setTimeout(sync,1000);
        t.addEventListener('scroll',()=>m.scrollLeft=t.scrollLeft);
        m.addEventListener('scroll',()=>t.scrollLeft=m.scrollLeft);
      </script>
    </body></html>
    """
    components.html(full_html, height=height + 30, scrolling=False)


def _show_analysis_charts(tickers_df: pd.DataFrame, name_map: dict):
    """Show expanders with analysis PNG for each ticker in tickers_df."""
    if not corr_dir.exists():
        return
    for _, row in tickers_df.iterrows():
        ticker  = row['ticker']
        plot    = corr_dir / f'analysis_{ticker}.png'
        if not plot.exists():
            continue
        company = name_map.get(ticker, ticker)
        signal  = row.get('signal', '')
        icon    = '🟢' if signal == 'BUY' else '🔴' if signal == 'SELL' else '📈'
        ret_str = (f"  ret={row['predicted_return']:+.1f}%"
                   if pd.notna(row.get('predicted_return')) else '')
        with st.expander(f"{icon} {ticker} — {company}{ret_str}"):
            st.image(str(plot), use_container_width=True)


# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_signals, tab_fund, tab_prices, tab_corr = st.tabs([
    '📋 Signals',
    '🏦 Fundamentals',
    '📊 Price Series & Market Cap',
    '🔗 Correlation Analysis',
])


# ── Tab 1: Signals ────────────────────────────────────────────────────────────
with tab_signals:
    signals_path = run_dir / 'signals.csv'
    if not signals_path.exists():
        st.info('signals.csv not found for this run.')
    else:
        df = pd.read_csv(signals_path)
        name_map = dict(zip(df['ticker'], df.get('company_name', df['ticker'])))

        buys  = (df['signal'] == 'BUY').sum()
        sells = (df['signal'] == 'SELL').sum()
        holds = (df['signal'] == 'HOLD').sum()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric('Total tickers', len(df))
        c2.metric('BUY',  buys)
        c3.metric('SELL', sells)
        c4.metric('HOLD', holds)
        st.divider()

        # Identify special tickers
        top_return_tickers = set(
            df.dropna(subset=['predicted_return'])
              .nlargest(TOP_N_HIGHLIGHT, 'predicted_return')['ticker']
        )
        buysell_tickers = set(df[df['signal'].isin(['BUY', 'SELL'])]['ticker'])

        # Build per-row styles
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

        _dual_scroll_table(df.reset_index(drop=True), row_styles, height=500,
                           link_cols={'ticker': 'https://finance.yahoo.com/quote/{value}'})
        st.caption(
            f'🔵 Top {TOP_N_HIGHLIGHT} highest predicted return  '
            '🟢 BUY  🔴 SELL  🟡 HOLD'
        )
        st.divider()

        # Analysis chart expanders for BUY/SELL + top return tickers
        special_df = (
            pd.concat([
                df[df['signal'].isin(['BUY', 'SELL'])],
                df[df['ticker'].isin(top_return_tickers)],
            ])
            .drop_duplicates(subset=['ticker'])
            .sort_values('predicted_return', ascending=False, na_position='last')
        )

        if not special_df.empty and corr_dir.exists():
            available = [t for t in special_df['ticker']
                         if (corr_dir / f'analysis_{t}.png').exists()]
            if available:
                st.subheader(f'📊 Prediction Analysis Charts ({len(available)} tickers)')
                _show_analysis_charts(
                    special_df[special_df['ticker'].isin(available)], name_map
                )


# ── Tab 2: Fundamentals ───────────────────────────────────────────────────────
with tab_fund:
    path = run_dir / 'fundamentals.csv'
    if not path.exists():
        st.info('fundamentals.csv not found for this run.')
    else:
        df = pd.read_csv(path, index_col=0)

        c1, c2, c3 = st.columns(3)
        c1.metric('Companies analysed', len(df))
        if 'likelihood_pct' in df.columns:
            c2.metric('Avg likelihood', f"{df['likelihood_pct'].mean():.1f}%")
            c3.metric('Top score',      f"{df['likelihood_pct'].max():.1f}%")
        st.divider()

        # Per-row styles based on likelihood_pct
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

        _dual_scroll_table(df.reset_index(), row_styles, height=540,
                           link_cols={'ticker': 'https://finance.yahoo.com/quote/{value}'})
        st.caption('🟢 ≥70%  🟡 ≥50%  🔴 <50%  likelihood of price increase in 12 months')


# ── Tab 3: Price Series & Market Cap ─────────────────────────────────────────
with tab_prices:
    gen_dir      = run_dir / 'General'
    signals_path = run_dir / 'signals.csv'

    # ── Interactive market cap bars ───────────────────────────────────────────
    if signals_path.exists():
        sdf = pd.read_csv(signals_path)
        if {'ticker', 'company_name', 'current_price', 'market_cap_B', 'sector'}.issubset(sdf.columns):
            sdf = sdf.dropna(subset=['market_cap_B']).sort_values('market_cap_B', ascending=False)
            top    = sdf.head(TOP_N_HIGHLIGHT)
            bottom = sdf.tail(TOP_N_HIGHLIGHT)

            fig = make_subplots(
                rows=2, cols=1, shared_xaxes=False, vertical_spacing=0.12,
                subplot_titles=[
                    f'Last Close Price ($) — top {TOP_N_HIGHLIGHT} vs bottom {TOP_N_HIGHLIGHT}',
                    f'Market Capitalization ($B) — top {TOP_N_HIGHLIGHT} vs bottom {TOP_N_HIGHLIGHT}',
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
                height=750,
                title=f'Top vs Bottom {TOP_N_HIGHLIGHT} S&P 500 Companies',
                barmode='group',
                legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
            )
            fig.update_yaxes(title_text='Price ($)',       row=1, col=1)
            fig.update_yaxes(title_text='Market Cap ($B)', row=2, col=1)
            st.subheader('Market Cap Bars (interactive — hover for company name)')
            st.plotly_chart(fig, use_container_width=True)
            st.divider()

    # ── Interactive price series ──────────────────────────────────────────────
    prices_path = run_dir / 'prices.csv'
    if prices_path.exists() and signals_path.exists():
        prices_df = pd.read_csv(prices_path, index_col=0, parse_dates=True)
        sdf_full  = pd.read_csv(signals_path)
        nm        = dict(zip(sdf_full['ticker'], sdf_full.get('company_name', sdf_full['ticker'])))

        COLORS = ['#1f77b4','#ff7f0e','#2ca02c','#d62728','#9467bd',
                  '#8c564b','#e377c2','#7f7f7f','#bcbd22','#17becf',
                  '#aec7e8','#ffbb78','#98df8a','#ff9896','#c5b0d5']

        def _series_chart(ordered, title, normalize=False):
            top_t = [t for t in ordered if t in prices_df.columns][:TOP_N_HIGHLIGHT]
            fig   = go.Figure()
            x_bg, y_bg = [], []
            for t in prices_df.columns:
                if t not in top_t:
                    v = prices_df[t] / prices_df[t].iloc[0] * 100 if normalize else prices_df[t]
                    x_bg.extend(list(prices_df.index) + [None])
                    y_bg.extend(list(v) + [None])
            if x_bg:
                fig.add_trace(go.Scatter(x=x_bg, y=y_bg, mode='lines',
                                         line=dict(color='lightgray', width=0.5),
                                         showlegend=False, hoverinfo='skip'))
            for i, t in enumerate(top_t):
                company = nm.get(t, t)
                v       = prices_df[t] / prices_df[t].iloc[0] * 100 if normalize else prices_df[t]
                fig.add_trace(go.Scatter(
                    x=prices_df.index, y=v, mode='lines', name=t,
                    line=dict(color=COLORS[i % len(COLORS)], width=1.8),
                    hovertemplate=(f'<b>{company}</b> ({t})<br>'
                                   f'%{{x|%Y-%m-%d}}<br>'
                                   f'{"Norm." if normalize else "Price ($)"}: %{{y:,.2f}}'
                                   '<extra></extra>'),
                ))
            fig.update_layout(
                title=title, height=480,
                xaxis_title='Date',
                yaxis_title='Normalized price (base=100)' if normalize else 'Close price ($)',
                hovermode='x unified',
                legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
            )
            return fig

        mcap_col = 'market_cap_B' if 'market_cap_B' in sdf_full.columns else None
        by_mcap  = (sdf_full.dropna(subset=[mcap_col])
                             .sort_values(mcap_col, ascending=False)['ticker'].tolist()
                    if mcap_col else list(prices_df.columns))
        by_price = prices_df.iloc[-1].sort_values(ascending=False).index.tolist()
        by_norm  = (prices_df.iloc[-1] / prices_df.iloc[0]).sort_values(ascending=False).index.tolist()

        for ordering, title, norm in [
            (by_mcap,  f'Price Series — Top {TOP_N_HIGHLIGHT} by Market Cap',       False),
            (by_price, f'Price Series — Top {TOP_N_HIGHLIGHT} by Stock Price',       False),
            (by_norm,  f'Price Series — Top {TOP_N_HIGHLIGHT} by Normalized Return', True),
        ]:
            st.subheader(title)
            st.plotly_chart(_series_chart(ordering, title, norm), use_container_width=True)
            st.divider()
    else:
        st.info('prices.csv not found — re-run the bot to enable interactive charts.')


# ── Tab 4: Correlation Analysis ───────────────────────────────────────────────
with tab_corr:
    if not corr_dir.exists():
        st.info('No Correlation_method/ plots found for this run.')
    else:
        matrix_path = corr_dir / 'correlation_matrix.png'
        if matrix_path.exists():
            st.subheader('Correlation Matrix')
            st.image(str(matrix_path), use_container_width=True)
            st.divider()

        if not matrix_path.exists():
            st.info('No plots found in Correlation_method/ for this run.')
