"""
SP500 Correlation Bot — Dashboard
Run with:  streamlit run dashboard.py --server.headless true
"""
import base64
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
                        link_cols: dict = None, cell_hrefs: dict = None):
    """Render a DataFrame as HTML with a synchronised scrollbar on top AND bottom.

    link_cols:  maps column name → URL template with {value} placeholder (all rows).
                e.g. {'ticker': 'https://finance.yahoo.com/quote/{value}'}
    cell_hrefs: maps (col_name, row_idx) → href for individual cell links.
                e.g. {('signal', 3): 'data:image/png;base64,...'}
    """
    rows_html = []
    for idx, row in df.iterrows():
        style = row_styles.get(idx, '') if row_styles else ''
        cells = []
        for col, v in zip(df.columns, row):
            td = 'padding:4px 10px;border:1px solid #eee;white-space:nowrap;'
            if cell_hrefs and (col, idx) in cell_hrefs:
                href = cell_hrefs[(col, idx)]
                cell = (f'<td style="{td}">'
                        f'<a href="{href}" target="_blank" '
                        f'style="color:inherit;text-decoration:underline;font-weight:bold;">'
                        f'{v}</a></td>')
            elif link_cols and col in link_cols:
                url = link_cols[col].format(value=v)
                cell = (f'<td style="{td}">'
                        f'<a href="{url}" target="_blank" '
                        f'style="color:inherit;text-decoration:underline;">{v}</a></td>')
            else:
                cell = f'<td style="{td}">{v}</td>'
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
        function sync(){{if(m.scrollWidth>0)ti.style.width=m.scrollWidth+'px';}}
        [0,200,500,1000,2000,4000].forEach(d=>setTimeout(sync,d));
        if(window.ResizeObserver){{new ResizeObserver(sync).observe(m);}}
        t.addEventListener('scroll',()=>m.scrollLeft=t.scrollLeft);
        m.addEventListener('scroll',()=>t.scrollLeft=m.scrollLeft);

        // ── Column sorting ──────────────────────────────────────────────────
        const ths=Array.from(document.querySelectorAll('thead th'));
        ths.forEach(th=>{{th.dataset.orig=th.textContent; th.style.cursor='pointer'; th.style.userSelect='none';}});
        let sortCol=-1, sortAsc=true;
        const clean=v=>v.replace(/[^0-9.-]/g,'');
        ths.forEach((th,idx)=>{{
          th.addEventListener('click',()=>{{
            if(sortCol===idx){{sortAsc=!sortAsc;}}else{{sortCol=idx;sortAsc=true;}}
            ths.forEach((h,i)=>{{h.textContent=h.dataset.orig+(i===sortCol?(sortAsc?' ▲':' ▼'):'');}});
            const tbody=m.querySelector('tbody');
            const rows=Array.from(tbody.querySelectorAll('tr'));
            rows.sort((a,b)=>{{
              const av=a.cells[idx].textContent.trim();
              const bv=b.cells[idx].textContent.trim();
              const an=parseFloat(clean(av)), bn=parseFloat(clean(bv));
              const aok=!isNaN(an), bok=!isNaN(bn);
              if(!aok&&bok)return 1; if(aok&&!bok)return -1;
              if(!aok&&!bok)return av.localeCompare(bv);
              return sortAsc?an-bn:bn-an;
            }});
            rows.forEach(r=>tbody.appendChild(r));
            sync();
          }});
        }});
      </script>
    </body></html>
    """
    components.html(full_html, height=height + 30, scrolling=False)



# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_signals, tab_fund, tab_mcap, tab_prices, tab_volume, tab_corr = st.tabs([
    '📋 Signals',
    '🏦 Fundamentals',
    '📊 Market Cap',
    '📈 Price Series',
    '📦 Volume',
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

        # Build per-cell chart links for the signal column
        df_reset = df.reset_index(drop=True)
        cell_hrefs = {}
        if corr_dir.exists():
            for i, row in df_reset.iterrows():
                plot = corr_dir / f'analysis_{row["ticker"]}.png'
                if plot.exists():
                    b64 = base64.b64encode(plot.read_bytes()).decode()
                    cell_hrefs[('signal', i)] = f'data:image/png;base64,{b64}'

        _dual_scroll_table(df_reset, row_styles, height=500,
                           link_cols={'ticker': 'https://finance.yahoo.com/quote/{value}'},
                           cell_hrefs=cell_hrefs)
        st.caption(
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


# ── Tab 3: Market Cap ────────────────────────────────────────────────────────
with tab_mcap:
    signals_path = run_dir / 'signals.csv'
    if not signals_path.exists():
        st.info('signals.csv not found for this run.')
    else:
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

            # ── Market cap time series ────────────────────────────────────────
            prices_path = run_dir / 'prices.csv'
            if prices_path.exists():
                prices_df = pd.read_csv(prices_path, index_col=0, parse_dates=True)
                nm = dict(zip(sdf['ticker'], sdf['company_name']))

                # Approximate historical market cap: price × (current_mcap / current_price)
                mcap_series = {}
                for _, r in sdf.iterrows():
                    t = r['ticker']
                    if t in prices_df.columns and r['current_price'] > 0:
                        shares = r['market_cap_B'] / r['current_price']
                        mcap_series[t] = prices_df[t] * shares
                mcap_df = pd.DataFrame(mcap_series)

                if not mcap_df.empty:
                    COLORS = ['#1f77b4','#ff7f0e','#2ca02c','#d62728','#9467bd',
                              '#8c564b','#e377c2','#7f7f7f','#bcbd22','#17becf',
                              '#aec7e8','#ffbb78','#98df8a','#ff9896','#c5b0d5']

                    def _mcap_chart(top_t, title):
                        fig_ts = make_subplots(
                            rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.06,
                            subplot_titles=['Normalized market cap (base = 100)', 'Market cap ($B)'],
                        )
                        x_bg_n, y_bg_n, x_bg_a, y_bg_a = [], [], [], []
                        for t in mcap_df.columns:
                            if t not in top_t:
                                nv = mcap_df[t] / mcap_df[t].iloc[0] * 100
                                x_bg_n.extend(list(mcap_df.index) + [None]); y_bg_n.extend(list(nv) + [None])
                                x_bg_a.extend(list(mcap_df.index) + [None]); y_bg_a.extend(list(mcap_df[t]) + [None])
                        if x_bg_n:
                            for rn, xb, yb in [(1, x_bg_n, y_bg_n), (2, x_bg_a, y_bg_a)]:
                                fig_ts.add_trace(go.Scatter(x=xb, y=yb, mode='lines',
                                                             line=dict(color='lightgray', width=0.5),
                                                             showlegend=False, hoverinfo='skip'),
                                                 row=rn, col=1)
                        for i, t in enumerate(top_t):
                            company = nm.get(t, t)
                            nv      = mcap_df[t] / mcap_df[t].iloc[0] * 100
                            color   = COLORS[i % len(COLORS)]
                            fig_ts.add_trace(go.Scatter(
                                x=mcap_df.index, y=nv, mode='lines', name=t,
                                line=dict(color=color, width=1.8),
                                hovertemplate=(f'<b>{company}</b> ({t})<br>'
                                               '%{x|%Y-%m-%d}<br>Norm.: %{y:,.2f}<extra></extra>'),
                            ), row=1, col=1)
                            fig_ts.add_trace(go.Scatter(
                                x=mcap_df.index, y=mcap_df[t], mode='lines', name=t,
                                line=dict(color=color, width=1.8), showlegend=False,
                                hovertemplate=(f'<b>{company}</b> ({t})<br>'
                                               '%{x|%Y-%m-%d}<br>Cap ($B): %{y:,.1f}<extra></extra>'),
                            ), row=2, col=1)
                        fig_ts.update_layout(
                            title=title, height=860, hovermode='closest',
                            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
                        )
                        fig_ts.update_yaxes(title_text='Normalized (base=100)', row=1, col=1)
                        fig_ts.update_yaxes(title_text='Market Cap ($B)',        row=2, col=1)
                        fig_ts.update_xaxes(title_text='Date',                   row=2, col=1)
                        fig_ts.update_xaxes(
                            rangeselector=dict(buttons=[
                                dict(count=1,  label='1M',  step='month', stepmode='backward'),
                                dict(count=3,  label='3M',  step='month', stepmode='backward'),
                                dict(count=6,  label='6M',  step='month', stepmode='backward'),
                                dict(count=1,  label='YTD', step='year',  stepmode='todate'),
                                dict(count=1,  label='1Y',  step='year',  stepmode='backward'),
                                dict(step='all', label='All'),
                            ]),
                            row=1, col=1,
                        )
                        return fig_ts

                    # Chart 1 — top by current (absolute) market cap
                    by_abs  = [t for t in sdf['ticker'] if t in mcap_df.columns][:TOP_N_HIGHLIGHT]
                    # Chart 2 — top by normalized market cap growth (latest / earliest)
                    by_norm = (mcap_df.iloc[-1] / mcap_df.iloc[0]).sort_values(ascending=False).index.tolist()
                    by_norm = by_norm[:TOP_N_HIGHLIGHT]

                    st.divider()
                    st.subheader(f'Market Cap Time Series — Top {TOP_N_HIGHLIGHT} by Current Market Cap')
                    with st.spinner('Rendering chart...'):
                        st.plotly_chart(_mcap_chart(by_abs,  f'Top {TOP_N_HIGHLIGHT} by Current Market Cap'),  use_container_width=True)
                    st.divider()
                    st.subheader(f'Market Cap Time Series — Top {TOP_N_HIGHLIGHT} by Normalized Cap Growth')
                    with st.spinner('Rendering chart...'):
                        st.plotly_chart(_mcap_chart(by_norm, f'Top {TOP_N_HIGHLIGHT} by Normalized Cap Growth'), use_container_width=True)
        else:
            st.info('Required columns missing in signals.csv.')


# ── Tab 4: Price Series ───────────────────────────────────────────────────────
with tab_prices:
    signals_path = run_dir / 'signals.csv'
    prices_path  = run_dir / 'prices.csv'
    if prices_path.exists() and signals_path.exists():
        prices_df = pd.read_csv(prices_path, index_col=0, parse_dates=True)
        sdf_full  = pd.read_csv(signals_path)
        nm        = dict(zip(sdf_full['ticker'], sdf_full.get('company_name', sdf_full['ticker'])))

        COLORS = ['#1f77b4','#ff7f0e','#2ca02c','#d62728','#9467bd',
                  '#8c564b','#e377c2','#7f7f7f','#bcbd22','#17becf',
                  '#aec7e8','#ffbb78','#98df8a','#ff9896','#c5b0d5']

        def _series_chart(ordered, title):
            top_t = [t for t in ordered if t in prices_df.columns][:TOP_N_HIGHLIGHT]
            fig   = make_subplots(rows=2, cols=1, shared_xaxes=True,
                                  vertical_spacing=0.06,
                                  subplot_titles=['Normalized price (base = 100)', 'Close price ($)'])

            x_bg_n, y_bg_n, x_bg_a, y_bg_a = [], [], [], []
            for t in prices_df.columns:
                if t not in top_t:
                    norm_v = prices_df[t] / prices_df[t].iloc[0] * 100
                    x_bg_n.extend(list(prices_df.index) + [None])
                    y_bg_n.extend(list(norm_v) + [None])
                    x_bg_a.extend(list(prices_df.index) + [None])
                    y_bg_a.extend(list(prices_df[t]) + [None])
            if x_bg_n:
                for row, xb, yb in [(1, x_bg_n, y_bg_n), (2, x_bg_a, y_bg_a)]:
                    fig.add_trace(go.Scatter(x=xb, y=yb, mode='lines',
                                             line=dict(color='lightgray', width=0.5),
                                             showlegend=False, hoverinfo='skip'),
                                  row=row, col=1)

            for i, t in enumerate(top_t):
                company = nm.get(t, t)
                norm_v  = prices_df[t] / prices_df[t].iloc[0] * 100
                color   = COLORS[i % len(COLORS)]
                fig.add_trace(go.Scatter(
                    x=prices_df.index, y=norm_v, mode='lines', name=t,
                    line=dict(color=color, width=1.8),
                    hovertemplate=(f'<b>{company}</b> ({t})<br>'
                                   '%{x|%Y-%m-%d}<br>Norm.: %{y:,.2f}<extra></extra>'),
                ), row=1, col=1)
                fig.add_trace(go.Scatter(
                    x=prices_df.index, y=prices_df[t], mode='lines', name=t,
                    line=dict(color=color, width=1.8), showlegend=False,
                    hovertemplate=(f'<b>{company}</b> ({t})<br>'
                                   '%{x|%Y-%m-%d}<br>Price ($): %{y:,.2f}<extra></extra>'),
                ), row=2, col=1)

            fig.update_layout(
                title=title, height=860,
                hovermode='closest',
                legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
            )
            fig.update_yaxes(title_text='Normalized (base=100)', row=1, col=1)
            fig.update_yaxes(title_text='Close price ($)',        row=2, col=1)
            fig.update_xaxes(title_text='Date',                   row=2, col=1)
            fig.update_xaxes(
                rangeselector=dict(buttons=[
                    dict(count=1,  label='1M',  step='month', stepmode='backward'),
                    dict(count=3,  label='3M',  step='month', stepmode='backward'),
                    dict(count=6,  label='6M',  step='month', stepmode='backward'),
                    dict(count=1,  label='YTD', step='year',  stepmode='todate'),
                    dict(count=1,  label='1Y',  step='year',  stepmode='backward'),
                    dict(step='all', label='All'),
                ]),
                row=1, col=1,
            )
            return fig

        mcap_col = 'market_cap_B' if 'market_cap_B' in sdf_full.columns else None
        by_mcap  = (sdf_full.dropna(subset=[mcap_col])
                             .sort_values(mcap_col, ascending=False)['ticker'].tolist()
                    if mcap_col else list(prices_df.columns))
        by_price = prices_df.iloc[-1].sort_values(ascending=False).index.tolist()
        by_norm  = (prices_df.iloc[-1] / prices_df.iloc[0]).sort_values(ascending=False).index.tolist()

        for ordering, title in [
            (by_mcap,  f'Price Series — Top {TOP_N_HIGHLIGHT} by Market Cap'),
            (by_price, f'Price Series — Top {TOP_N_HIGHLIGHT} by Stock Price'),
            (by_norm,  f'Price Series — Top {TOP_N_HIGHLIGHT} by Normalized Return'),
        ]:
            st.subheader(title)
            st.plotly_chart(_series_chart(ordering, title), use_container_width=True)
            st.divider()
    else:
        st.info('prices.csv not found — re-run the bot to enable interactive charts.')


# ── Tab 5: Volume ─────────────────────────────────────────────────────────────
with tab_volume:
    volume_path = run_dir / 'volume.csv'
    if not volume_path.exists():
        st.info('volume.csv not found — re-run the bot to enable this tab.')
    else:
        vol_df = pd.read_csv(volume_path, index_col=0, parse_dates=True)
        sdf_vol = pd.read_csv(run_dir / 'signals.csv') if (run_dir / 'signals.csv').exists() else None
        nm_vol  = dict(zip(sdf_vol['ticker'], sdf_vol['company_name'])) if sdf_vol is not None and 'company_name' in sdf_vol.columns else {}

        COLORS_V = ['#1f77b4','#ff7f0e','#2ca02c','#d62728','#9467bd',
                    '#8c564b','#e377c2','#7f7f7f','#bcbd22','#17becf',
                    '#aec7e8','#ffbb78','#98df8a','#ff9896','#c5b0d5']

        def _volume_chart(top_t, title):
            fig_v = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.06,
                                  subplot_titles=['Normalized volume (base = 100)', 'Volume (shares)'])
            x_bg_n, y_bg_n, x_bg_a, y_bg_a = [], [], [], []
            for t in vol_df.columns:
                if t not in top_t:
                    first = vol_df[t].replace(0, float('nan')).first_valid_index()
                    nv = vol_df[t] / vol_df[t][first] * 100 if first else vol_df[t] * 0
                    x_bg_n.extend(list(vol_df.index) + [None]); y_bg_n.extend(list(nv) + [None])
                    x_bg_a.extend(list(vol_df.index) + [None]); y_bg_a.extend(list(vol_df[t]) + [None])
            if x_bg_n:
                for rn, xb, yb in [(1, x_bg_n, y_bg_n), (2, x_bg_a, y_bg_a)]:
                    fig_v.add_trace(go.Scatter(x=xb, y=yb, mode='lines',
                                               line=dict(color='lightgray', width=0.5),
                                               showlegend=False, hoverinfo='skip'), row=rn, col=1)
            for i, t in enumerate(top_t):
                company = nm_vol.get(t, t)
                first   = vol_df[t].replace(0, float('nan')).first_valid_index()
                nv      = vol_df[t] / vol_df[t][first] * 100 if first else vol_df[t] * 0
                color   = COLORS_V[i % len(COLORS_V)]
                fig_v.add_trace(go.Scatter(
                    x=vol_df.index, y=nv, mode='lines', name=t,
                    line=dict(color=color, width=1.8),
                    hovertemplate=(f'<b>{company}</b> ({t})<br>'
                                   '%{x|%Y-%m-%d}<br>Norm.: %{y:,.2f}<extra></extra>'),
                ), row=1, col=1)
                fig_v.add_trace(go.Scatter(
                    x=vol_df.index, y=vol_df[t], mode='lines', name=t,
                    line=dict(color=color, width=1.8), showlegend=False,
                    hovertemplate=(f'<b>{company}</b> ({t})<br>'
                                   '%{x|%Y-%m-%d}<br>Volume: %{y:,.0f}<extra></extra>'),
                ), row=2, col=1)
            fig_v.update_layout(title=title, height=860, hovermode='closest',
                                legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1))
            fig_v.update_yaxes(title_text='Normalized (base=100)', row=1, col=1)
            fig_v.update_yaxes(title_text='Volume (shares)',        row=2, col=1)
            fig_v.update_xaxes(title_text='Date',                   row=2, col=1)
            fig_v.update_xaxes(rangeselector=dict(buttons=[
                dict(count=1,  label='1M',  step='month', stepmode='backward'),
                dict(count=3,  label='3M',  step='month', stepmode='backward'),
                dict(count=6,  label='6M',  step='month', stepmode='backward'),
                dict(count=1,  label='YTD', step='year',  stepmode='todate'),
                dict(count=1,  label='1Y',  step='year',  stepmode='backward'),
                dict(step='all', label='All'),
            ]), row=1, col=1)
            return fig_v

        by_abs_v  = vol_df.mean().sort_values(ascending=False).index.tolist()[:TOP_N_HIGHLIGHT]
        by_norm_v = (vol_df.iloc[-1] / vol_df.iloc[0]).sort_values(ascending=False).index.tolist()[:TOP_N_HIGHLIGHT]

        st.subheader(f'Volume Time Series — Top {TOP_N_HIGHLIGHT} by Average Volume')
        with st.spinner('Rendering chart...'):
            st.plotly_chart(_volume_chart(by_abs_v,  f'Top {TOP_N_HIGHLIGHT} by Average Volume'),  use_container_width=True)
        st.divider()
        st.subheader(f'Volume Time Series — Top {TOP_N_HIGHLIGHT} by Normalized Volume Growth')
        with st.spinner('Rendering chart...'):
            st.plotly_chart(_volume_chart(by_norm_v, f'Top {TOP_N_HIGHLIGHT} by Normalized Volume Growth'), use_container_width=True)


# ── Tab 6: Correlation Analysis ───────────────────────────────────────────────
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
