"""
SP500 Correlation Bot — Dashboard
Run with:  streamlit run dashboard.py --server.headless true
"""
import base64
import json
import math
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
import streamlit.components.v1 as components

from config import OUTPUTS_DIR, TOP_N_HIGHLIGHT

@st.cache_data
def _load_csv(path, **kwargs):
    return pd.read_csv(path, **kwargs)

# Minimum downsample step for background traces; actual step is computed adaptively
_BG_STEP = 5
# Max background tickers per chart and target points per background trace
_MAX_BG_TICKERS = 100
_BG_TARGET_PTS  = 200
# Default start date for all time series charts (slices data before building JSON)
_CHART_START_DATE = '2005-01-01'

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


_ECHARTS_CDN = 'https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js'
_COLORS = ['#1f77b4','#ff7f0e','#2ca02c','#d62728','#9467bd',
           '#8c564b','#e377c2','#7f7f7f','#bcbd22','#17becf',
           '#aec7e8','#ffbb78','#98df8a','#ff9896','#c5b0d5']


def _echarts_dual_chart(df_all, top_t, nm, norm_fn, abs_fn,
                        title, y1_label, y2_label, height=880,
                        start_date=_CHART_START_DATE):
    """Two-subplot ECharts time series with native y-axis auto-scaling on x-zoom.

    dataZoom filterMode='filter' makes ECharts automatically rescale both
    y-axes whenever the x range changes — no JavaScript callbacks needed.
    """
    if start_date:
        df_all = df_all.loc[df_all.index >= pd.Timestamp(start_date)]

    def _clean(v):
        try:
            f = float(v)
            return None if (math.isnan(f) or math.isinf(f)) else round(f, 4)
        except Exception:
            return None

    top_set = set(top_t)
    dates    = df_all.index.strftime('%Y-%m-%d').tolist()

    # Adaptive step: target ≤ _BG_TARGET_PTS points per background trace
    bg_step  = max(_BG_STEP, len(dates) // _BG_TARGET_PTS)
    dates_bg = dates[::bg_step]

    series = []

    # ── Background gray traces (downsampled, not in legend) ──────────────────
    bg_tickers = [t for t in df_all.columns if t not in top_set][:_MAX_BG_TICKERS]
    bg_n, bg_a = [], []
    for t in bg_tickers:
        try:
            nv = norm_fn(df_all[t]).iloc[::bg_step]
            av = abs_fn(df_all[t]).iloc[::bg_step]
            for i in range(len(dates_bg)):
                bg_n.append([dates_bg[i], _clean(nv.iloc[i])])
                bg_a.append([dates_bg[i], _clean(av.iloc[i])])
            bg_n.append(None)
            bg_a.append(None)
        except Exception:
            pass

    if bg_n:
        for subplot, data in [(0, bg_n), (1, bg_a)]:
            series.append({
                'name': '__bg__', 'type': 'line',
                'xAxisIndex': subplot, 'yAxisIndex': subplot,
                'data': data, 'symbol': 'none', 'silent': True,
                'lineStyle': {'color': '#ddd', 'width': 0.5},
                'large': True, 'largeThreshold': 200,
            })

    # ── Highlighted top-N traces (same name links both subplots in legend) ───
    for i, t in enumerate(top_t):
        if t not in df_all.columns:
            continue
        color = _COLORS[i % len(_COLORS)]
        try:
            nv = norm_fn(df_all[t])
            av = abs_fn(df_all[t])
            norm_data = [[dates[j], _clean(nv.iloc[j])] for j in range(len(dates))]
            abs_data  = [[dates[j], _clean(av.iloc[j])]  for j in range(len(dates))]
        except Exception:
            continue
        series.append({
            'name': t, 'type': 'line', 'xAxisIndex': 0, 'yAxisIndex': 0,
            'data': norm_data, 'symbol': 'none',
            'lineStyle': {'color': color, 'width': 1.8},
            'itemStyle': {'color': color},
        })
        series.append({
            'name': t, 'type': 'line', 'xAxisIndex': 1, 'yAxisIndex': 1,
            'data': abs_data, 'symbol': 'none',
            'lineStyle': {'color': color, 'width': 1.8},
            'itemStyle': {'color': color},
        })

    option = {
        'animation': False,
        'backgroundColor': '#fff',
        'title': {'text': title, 'textStyle': {'fontSize': 12, 'fontWeight': 'bold'}, 'top': 2},
        'legend': {
            'type': 'scroll', 'top': 28,
            'data': [{'name': t, 'icon': 'circle'} for t in top_t if t in df_all.columns],
            'itemWidth': 10, 'itemHeight': 10,
            'textStyle': {'fontSize': 10},
        },
        'axisPointer': {'link': [{'xAxisIndex': 'all'}]},
        'dataZoom': [
            {
                'type': 'slider', 'xAxisIndex': [0, 1],
                'filterMode': 'filter',   # ← auto-scales y on x zoom
                'bottom': 5, 'height': 22, 'labelFormatter': '',
            },
            {'type': 'inside', 'xAxisIndex': [0, 1], 'filterMode': 'filter'},
        ],
        'grid': [
            {'top': '18%', 'bottom': '52%', 'left': '9%', 'right': '3%'},
            {'top': '55%', 'bottom': '12%', 'left': '9%', 'right': '3%'},
        ],
        'xAxis': [
            {'type': 'time', 'gridIndex': 0,
             'axisLabel': {'show': False}, 'splitLine': {'show': False}},
            {'type': 'time', 'gridIndex': 1,
             'axisLabel': {'formatter': '{yyyy}-{MM}', 'fontSize': 9}},
        ],
        'yAxis': [
            {'type': 'value', 'gridIndex': 0, 'name': y1_label, 'scale': True,
             'nameTextStyle': {'fontSize': 9}, 'axisLabel': {'fontSize': 9},
             'splitLine': {'lineStyle': {'opacity': 0.3}}},
            {'type': 'value', 'gridIndex': 1, 'name': y2_label, 'scale': True,
             'nameTextStyle': {'fontSize': 9}, 'axisLabel': {'fontSize': 9},
             'splitLine': {'lineStyle': {'opacity': 0.3}}},
        ],
        'series': series,
    }

    opt_json  = json.dumps(option)
    nm_json   = json.dumps({t: nm.get(t, t) for t in top_t})

    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<script src="{_ECHARTS_CDN}"></script>
<style>
body{{margin:0;padding:0;background:#fff;font-family:sans-serif;}}
#btns{{padding:4px 8px;}}
#btns button{{margin:2px;padding:3px 8px;cursor:pointer;border:1px solid #ccc;
  border-radius:3px;background:#f5f5f5;font-size:11px;}}
#btns button:hover{{background:#dce8f5;}}
</style></head>
<body>
<div id="btns"></div>
<div id="chart" style="width:100%;height:{height}px;"></div>
<script>
var chart = echarts.init(document.getElementById('chart'),null,{{renderer:'canvas'}});
var nm = {nm_json};
var opt = {opt_json};

// Tooltip: show company name + ticker + value for hovered series only
// Track mouse Y so formatter can find the nearest series
var _mouseY = 0;
chart.getZr().on('mousemove', function(e){{ _mouseY = e.offsetY; }});

opt.tooltip = {{
  trigger: 'axis',
  axisPointer: {{ type: 'cross', link: [{{xAxisIndex: 'all'}}] }},
  confine: true,
  formatter: function(params) {{
    if(!params || params.length === 0) return '';
    var best = null, bestDist = Infinity;
    params.forEach(function(p) {{
      if(p.seriesName.startsWith('__bg')) return;
      if(!p.data || p.data[1] === null || p.data[1] === undefined) return;
      try {{
        var opt2 = chart.getOption();
        var yIdx = (opt2.series[p.seriesIndex] || {{}}).yAxisIndex || 0;
        var pixY = chart.convertToPixel({{yAxisIndex: yIdx}}, parseFloat(p.data[1]));
        var dist = Math.abs(pixY - _mouseY);
        if(dist < bestDist) {{ bestDist = dist; best = p; }}
      }} catch(e) {{}}
    }});
    if(!best) return '';
    var company = nm[best.seriesName] || best.seriesName;
    return best.data[0] + '<br/>' + best.marker +
           ' <b>' + company + '</b> (' + best.seriesName + '): ' +
           parseFloat(best.data[1]).toFixed(2);
  }}
}};

chart.setOption(opt);
window.addEventListener('resize', function(){{ chart.resize(); }});

// Period selector buttons
var periods = [
  {{l:'1M',m:1}},{{l:'3M',m:3}},{{l:'6M',m:6}},
  {{l:'YTD',ytd:true}},{{l:'1Y',m:12}},{{l:'All',all:true}}
];
var btnsDiv = document.getElementById('btns');
periods.forEach(function(p){{
  var btn = document.createElement('button');
  btn.innerText = p.l;
  btn.onclick = function(){{
    var now = new Date();
    if(p.all){{
      chart.dispatchAction({{type:'dataZoom',dataZoomIndex:0,start:0,end:100}});
    }} else if(p.ytd){{
      var s = new Date(now.getFullYear(),0,1);
      chart.dispatchAction({{type:'dataZoom',dataZoomIndex:0,
        startValue:s.getTime(),endValue:now.getTime()}});
    }} else {{
      var s = new Date(now); s.setMonth(s.getMonth()-p.m);
      chart.dispatchAction({{type:'dataZoom',dataZoomIndex:0,
        startValue:s.getTime(),endValue:now.getTime()}});
    }}
  }};
  btnsDiv.appendChild(btn);
}});
</script>
</body></html>"""

    components.html(html, height=height + 55, scrolling=False)


# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_signals, tab_fund, tab_mcap, tab_prices, tab_volume, tab_returns, tab_corr = st.tabs([
    '📋 Signals',
    '🏦 Fundamentals',
    '📊 Market Cap',
    '📈 Price Series',
    '📦 Volume',
    '💹 Cumulative Returns',
    '🔗 Correlation Analysis',
])


# ── Tab 1: Signals ────────────────────────────────────────────────────────────
with tab_signals:
    signals_path = run_dir / 'signals.csv'
    if not signals_path.exists():
        st.info('signals.csv not found for this run.')
    else:
        df = _load_csv(str(signals_path))
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
        df = _load_csv(str(path), index_col=0)

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
        sdf = _load_csv(str(signals_path))
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
                prices_df = _load_csv(str(prices_path), index_col=0, parse_dates=True)
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
                    by_abs  = [t for t in sdf['ticker'] if t in mcap_df.columns][:TOP_N_HIGHLIGHT]
                    by_norm = (mcap_df.iloc[-1] / mcap_df.iloc[0]).sort_values(ascending=False).index.tolist()[:TOP_N_HIGHLIGHT]

                    st.divider()
                    st.subheader(f'Market Cap Time Series — Top {TOP_N_HIGHLIGHT} by Current Market Cap')
                    _echarts_dual_chart(
                        mcap_df, by_abs, nm,
                        norm_fn=lambda s: s / s.iloc[0] * 100,
                        abs_fn=lambda s: s,
                        title=f'Top {TOP_N_HIGHLIGHT} by Current Market Cap',
                        y1_label='Normalized (base=100)', y2_label='Market Cap ($B)',
                    )
                    st.divider()
                    st.subheader(f'Market Cap Time Series — Top {TOP_N_HIGHLIGHT} by Normalized Cap Growth')
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
        by_norm  = (prices_df.iloc[-1] / prices_df.iloc[0]).sort_values(ascending=False).index.tolist()

        for ordering, title in [
            (by_mcap,  f'Price Series — Top {TOP_N_HIGHLIGHT} by Market Cap'),
            (by_price, f'Price Series — Top {TOP_N_HIGHLIGHT} by Stock Price'),
            (by_norm,  f'Price Series — Top {TOP_N_HIGHLIGHT} by Normalized Return'),
        ]:
            top_t = [t for t in ordering if t in prices_df.columns][:TOP_N_HIGHLIGHT]
            _echarts_dual_chart(
                prices_df, top_t, nm,
                norm_fn=lambda s: s / s.iloc[0] * 100,
                abs_fn=lambda s: s,
                title=title,
                y1_label='Normalized (base=100)',
                y2_label='Close price ($)',
            )
            st.divider()
    else:
        st.info('prices.csv not found — re-run the bot to enable interactive charts.')


# ── Tab 5: Volume ─────────────────────────────────────────────────────────────
with tab_volume:
    volume_path = run_dir / 'volume.csv'
    if not volume_path.exists():
        st.info('volume.csv not found — re-run the bot to enable this tab.')
    else:
        vol_df = _load_csv(str(volume_path), index_col=0, parse_dates=True)
        sdf_vol = _load_csv(str(run_dir / "signals.csv")) if (run_dir / 'signals.csv').exists() else None
        nm_vol  = dict(zip(sdf_vol['ticker'], sdf_vol['company_name'])) if sdf_vol is not None and 'company_name' in sdf_vol.columns else {}

        def _vol_norm(s):
            first = s.replace(0, float('nan')).first_valid_index()
            return s / s[first] * 100 if first is not None else s * 0

        by_abs_v  = vol_df.mean().sort_values(ascending=False).index.tolist()[:TOP_N_HIGHLIGHT]
        by_norm_v = (vol_df.iloc[-1] / vol_df.iloc[0]).sort_values(ascending=False).index.tolist()[:TOP_N_HIGHLIGHT]

        st.subheader(f'Volume Time Series — Top {TOP_N_HIGHLIGHT} by Average Volume')
        _echarts_dual_chart(
            vol_df, by_abs_v, nm_vol,
            norm_fn=_vol_norm, abs_fn=lambda s: s,
            title=f'Top {TOP_N_HIGHLIGHT} by Average Volume',
            y1_label='Normalized (base=100)', y2_label='Volume (shares)',
        )
        st.divider()
        st.subheader(f'Volume Time Series — Top {TOP_N_HIGHLIGHT} by Normalized Volume Growth')
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
        sdf_r = _load_csv(str(run_dir / "signals.csv")) if (run_dir / 'signals.csv').exists() else None
        nm_r  = dict(zip(sdf_r['ticker'], sdf_r['company_name'])) if sdf_r is not None and 'company_name' in sdf_r.columns else {}

        top_t_r = ((ret_prices.iloc[-1] / ret_prices.iloc[0] - 1) * 100).sort_values(ascending=False).index.tolist()[:TOP_N_HIGHLIGHT]

        _echarts_dual_chart(
            ret_prices, top_t_r, nm_r,
            norm_fn=lambda s: (s / s.iloc[0] - 1) * 100,
            abs_fn=lambda s: s - s.iloc[0],
            title=f'Cumulative Returns — Top {TOP_N_HIGHLIGHT} best performers highlighted',
            y1_label='Cum. return (%)', y2_label='$ return/share',
        )


# ── Tab 7: Correlation Analysis ───────────────────────────────────────────────
with tab_corr:
    if not corr_dir.exists():
        st.info('No Correlation_method/ plots found for this run.')
    else:
        matrix_path = corr_dir / 'correlation_matrix.png'
        if matrix_path.exists():
            st.subheader('Correlation Matrix')
            st.image(str(matrix_path), use_container_width=True)
            st.divider()
        else:
            st.info('No plots found in Correlation_method/ for this run.')

        # ── Interactive price series for correlation matrix companies ──────────
        prices_path_c  = run_dir / 'prices.csv'
        signals_path_c = run_dir / 'signals.csv'
        if prices_path_c.exists() and signals_path_c.exists():
            prices_c = _load_csv(str(prices_path_c), index_col=0, parse_dates=True)
            sdf_c    = _load_csv(str(signals_path_c))
            nm_c     = (dict(zip(sdf_c['ticker'], sdf_c['company_name']))
                        if 'company_name' in sdf_c.columns else {})

            # Same tickers as the correlation heatmap (top N by market cap)
            mcap_col_c = 'market_cap_B' if 'market_cap_B' in sdf_c.columns else None
            if mcap_col_c:
                corr_tickers = (sdf_c.dropna(subset=[mcap_col_c])
                                     .sort_values(mcap_col_c, ascending=False)['ticker']
                                     .head(TOP_N_HIGHLIGHT).tolist())
            else:
                corr_tickers = list(prices_c.columns)[:TOP_N_HIGHLIGHT]
            corr_tickers = [t for t in corr_tickers if t in prices_c.columns]

            # Multiselect: display as "Company Name (TICKER)", default = first 5
            opt_map = {f"{nm_c.get(t, t)} ({t})": t for t in corr_tickers}
            selected_labels = st.multiselect(
                'Select companies to plot',
                options=list(opt_map.keys()),
                default=list(opt_map.keys())[:5],
            )
            selected_t = [opt_map[lbl] for lbl in selected_labels]

            if selected_t:
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
