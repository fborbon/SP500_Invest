"""Pure-Python HTML builders for the SP500 dashboard — no Streamlit dependency."""
import json
import math

import pandas as pd

from config import TOP_N_HIGHLIGHT

_BG_STEP          = 5
_BG_TARGET_PTS    = 200
_CHART_START_DATE = '2005-01-01'
_CACHE_SUBDIR     = 'dashboard_cache'
_ECHARTS_CDN      = 'https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js'
_COLORS = ['#1f77b4','#ff7f0e','#2ca02c','#d62728','#9467bd',
           '#8c564b','#e377c2','#7f7f7f','#bcbd22','#17becf',
           '#aec7e8','#ffbb78','#98df8a','#ff9896','#c5b0d5']


def _y_bounds(tickers, fn, df, margin=0.05):
    vals = []
    for t in tickers:
        if t not in df.columns:
            continue
        try:
            s = fn(df[t]).replace([float('inf'), float('-inf')], float('nan')).dropna()
            vals.extend(s.tolist())
        except Exception:
            pass
    if not vals:
        return {}
    lo, hi = min(vals), max(vals)
    pad = (hi - lo) * margin if hi != lo else abs(hi) * margin or 1
    return {'min': round(lo - pad, 4), 'max': round(hi + pad, 4)}


def _vol_norm(s):
    first = s.replace(0, float('nan')).first_valid_index()
    return s / s[first] * 100 if first is not None else s * 0


def _build_table_html(df, row_styles=None, height=520, link_cols=None,
                      cell_hrefs=None, col_descriptions=None):
    """Build the dual-scrollbar table HTML string. No Streamlit calls."""
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

    desc = col_descriptions or {}
    headers = ''.join(
        f'<th style="padding:6px 10px;border:1px solid #ddd;background:#f5f5f5;'
        f'white-space:nowrap;position:sticky;top:0;z-index:1;'
        f'{"border-bottom:2px dashed #aaa;" if c in desc else ""}"'
        f'{f" data-tip=\"{desc[c]}\"" if c in desc else ""}>{c}</th>'
        for c in df.columns
    )

    table_html = (
        f'<table style="border-collapse:collapse;font-size:12px;font-family:sans-serif;">'
        f'<thead><tr>{headers}</tr></thead>'
        f'<tbody>{"".join(rows_html)}</tbody>'
        f'</table>'
    )

    return f"""
    <html><head><style>
      body{{margin:0;}}
      #top-bar{{overflow-x:scroll;overflow-y:hidden;height:18px;border-bottom:1px solid #ccc;}}
      #top-inner{{height:1px;}}
      #main{{overflow:auto;max-height:{height}px;}}
      #tip{{position:fixed;background:#333;color:#fff;padding:6px 10px;border-radius:5px;
            font-size:12px;max-width:260px;line-height:1.4;z-index:9999;
            pointer-events:none;display:none;white-space:normal;}}
    </style></head><body>
      <div id="tip"></div>
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

        const tip=document.getElementById('tip');
        let tipTimer=null;
        document.querySelectorAll('th[data-tip]').forEach(th=>{{
          th.addEventListener('mouseenter',e=>{{
            tipTimer=setTimeout(()=>{{
              tip.textContent=th.getAttribute('data-tip');
              tip.style.display='block';
            }},2000);
          }});
          th.addEventListener('mousemove',e=>{{
            tip.style.left=(e.clientX+14)+'px';
            tip.style.top=(e.clientY+14)+'px';
          }});
          th.addEventListener('mouseleave',()=>{{
            clearTimeout(tipTimer);
            tip.style.display='none';
          }});
        }});

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


def _build_echarts_html(df_all, top_t, nm, norm_fn, abs_fn,
                        title, y1_label, y2_label, height=880,
                        start_date=_CHART_START_DATE, top_t_bottom=None,
                        fit_to_highlights=True):
    """Build the dual-subplot ECharts HTML string. No Streamlit calls."""
    if start_date:
        df_all = df_all.loc[df_all.index >= pd.Timestamp(start_date)]

    if top_t_bottom is None:
        top_t_bottom = top_t

    def _clean(v):
        try:
            f = float(v)
            return None if (math.isnan(f) or math.isinf(f)) else round(f, 4)
        except Exception:
            return None

    top_set_n = set(top_t)
    dates     = df_all.index.strftime('%Y-%m-%d').tolist()

    bg_step  = max(_BG_STEP, len(dates) // _BG_TARGET_PTS)
    dates_bg = dates[::bg_step]

    series = []

    bg_n, bg_a = [], []
    for t in df_all.columns:
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

    for i, t in enumerate(top_t):
        if t not in df_all.columns:
            continue
        color = _COLORS[i % len(_COLORS)]
        try:
            nv = norm_fn(df_all[t])
            norm_data = [[dates[j], _clean(nv.iloc[j])] for j in range(len(dates))]
        except Exception:
            continue
        series.append({
            'name': t, 'type': 'line', 'xAxisIndex': 0, 'yAxisIndex': 0,
            'data': norm_data, 'symbol': 'none',
            'lineStyle': {'color': color, 'width': 1.8},
            'itemStyle': {'color': color},
        })

    for i, t in enumerate(top_t_bottom):
        if t not in df_all.columns:
            continue
        color = _COLORS[i % len(_COLORS)]
        try:
            av = abs_fn(df_all[t])
            abs_data = [[dates[j], _clean(av.iloc[j])] for j in range(len(dates))]
        except Exception:
            continue
        in_legend = t in top_set_n
        series.append({
            'name': t, 'type': 'line', 'xAxisIndex': 1, 'yAxisIndex': 1,
            'data': abs_data, 'symbol': 'none',
            'lineStyle': {'color': color, 'width': 1.8},
            'itemStyle': {'color': color},
            'legendHoverLink': not in_legend,
        })

    option = {
        'animation': False,
        'backgroundColor': '#fff',
        'title': {'text': title, 'textStyle': {'fontSize': 12, 'fontWeight': 'bold'}, 'top': 2},
        'legend': {
            'type': 'scroll', 'top': 28,
            'data': [{'name': t, 'icon': 'circle'}
                     for t in dict.fromkeys(list(top_t) + list(top_t_bottom))
                     if t in df_all.columns],
            'itemWidth': 10, 'itemHeight': 10,
            'textStyle': {'fontSize': 10},
        },
        'axisPointer': {'link': [{'xAxisIndex': 'all'}]},
        'dataZoom': [
            {
                'type': 'slider', 'xAxisIndex': [0, 1],
                'filterMode': 'filter',
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
            {**{'type': 'value', 'gridIndex': 0, 'name': y1_label, 'scale': True,
                'nameTextStyle': {'fontSize': 9}, 'axisLabel': {'fontSize': 9},
                'splitLine': {'lineStyle': {'opacity': 0.3}}},
             **(_y_bounds(top_t, norm_fn, df_all) if fit_to_highlights else {})},
            {**{'type': 'value', 'gridIndex': 1, 'name': y2_label, 'scale': True,
                'nameTextStyle': {'fontSize': 9}, 'axisLabel': {'fontSize': 9},
                'splitLine': {'lineStyle': {'opacity': 0.3}}},
             **(_y_bounds(top_t_bottom, abs_fn, df_all) if fit_to_highlights else {})},
        ],
        'series': series,
    }

    opt_json = json.dumps(option)
    nm_json  = json.dumps({t: nm.get(t, t)
                           for t in dict.fromkeys(list(top_t) + list(top_t_bottom))})

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
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


_SIGNALS_DESC = {
    'ticker':                  'Stock ticker symbol (e.g. AAPL). Click to open Yahoo Finance.',
    'company_name':            'Full legal name of the company.',
    'sector':                  'GICS sector classification (e.g. Technology, Energy).',
    'founded':                 'Year the company was founded.',
    'market_cap_B':            'Current market capitalisation in billions USD.',
    'current_price':           'Last available closing price (USD).',
    'target_price_7d':         'Model-predicted price 7 trading days from now.',
    'predicted_return':        'Expected % return over the next 7 days according to the model.',
    'model_r2':                'R² of the regression model. Higher = more reliable signal. Values below 0.01 are flagged LOW_CONFIDENCE.',
    'direct_top5_predictors':  'Top 5 tickers most positively correlated with this stock, used as predictors.',
    'inverse_top5_predictors': 'Top 5 tickers most negatively correlated with this stock, used as predictors.',
    'signal':                  'Trading signal. BUY: predicted return > 1%. SELL: predicted return < -10%. HOLD: otherwise. Click to view prediction chart.',
}

_FUND_DESC = {
    'ticker':           'Stock ticker symbol. Click to open Yahoo Finance.',
    'company_name':     'Full legal name of the company.',
    'sector':           'GICS sector classification.',
    'market_cap_B':     'Market capitalisation in billions USD.',
    'revenue_growth':   'Year-over-year revenue growth rate (%).',
    'gross_margin':     'Gross profit as % of revenue. Measures production efficiency.',
    'operating_margin': 'Operating income as % of revenue. Measures operational efficiency.',
    'net_margin':       'Net income as % of revenue. Bottom-line profitability.',
    'free_cash_flow':   'Operating cash flow minus capital expenditure (USD). Measures cash generation.',
    'current_ratio':    'Current assets / current liabilities. >1 means the company can cover short-term obligations.',
    'debt_to_equity':   'Total debt / shareholders equity. Higher = more leveraged.',
    'pe_ratio':         'Price-to-Earnings ratio: stock price / EPS. Lower may indicate undervaluation.',
    'peg_ratio':        'PE ratio / earnings growth rate. Accounts for growth; <1 often considered attractive.',
    'ps_ratio':         'Price-to-Sales ratio: market cap / revenue.',
    'pb_ratio':         'Price-to-Book ratio: stock price / book value per share.',
    'ev_ebitda':        'Enterprise Value / EBITDA. Common valuation multiple; lower = cheaper relative to earnings.',
    'eps':              'Earnings Per Share: net income / shares outstanding.',
    'earnings_growth':  'Year-over-year earnings growth rate (%).',
    'likelihood_pct':   'Composite fundamental score: estimated probability (%) of price increase over the next 12 months. ≥70% green, ≥50% yellow, <50% red.',
}
