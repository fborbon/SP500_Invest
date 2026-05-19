"""Pre-compute and cache all dashboard HTML artifacts during the daily run."""
import base64
from pathlib import Path

import pandas as pd

from config import TOP_N_HIGHLIGHT
from reporting.html_builders import (
    _build_echarts_html, _build_table_html, _vol_norm,
    _SIGNALS_DESC, _FUND_DESC, _CACHE_SUBDIR, _CHART_START_DATE,
)


def precompute_dashboard_cache(run_dir: Path) -> None:
    """Pre-build all chart and table HTML files into run_dir/dashboard_cache/.

    The dashboard loads these files directly instead of recomputing on every
    page visit, eliminating the heavy data-processing work at render time.
    The interactive correlation chart (user-driven multiselect) is excluded.
    """
    cache_dir = run_dir / _CACHE_SUBDIR
    cache_dir.mkdir(exist_ok=True)

    def _save(name: str, html: str) -> None:
        (cache_dir / f'{name}.html').write_text(html, encoding='utf-8')
        print(f'    cached {name}.html')

    signals_path = run_dir / 'signals.csv'
    prices_path  = run_dir / 'prices.csv'
    volume_path  = run_dir / 'volume.csv'
    fund_path    = run_dir / 'fundamentals.csv'
    corr_dir     = run_dir / 'Correlation_method'

    sdf       = pd.read_csv(signals_path)                                    if signals_path.exists() else None
    prices_df = pd.read_csv(prices_path, index_col=0, parse_dates=True)     if prices_path.exists() else None
    vol_df    = pd.read_csv(volume_path,  index_col=0, parse_dates=True)    if volume_path.exists() else None
    fund_df   = pd.read_csv(fund_path, index_col=0)                         if fund_path.exists() else None

    nm = (dict(zip(sdf['ticker'], sdf['company_name']))
          if sdf is not None and 'company_name' in sdf.columns else {})

    # ── Signals table ─────────────────────────────────────────────────────────
    if sdf is not None:
        top_return_tickers = set(
            sdf.dropna(subset=['predicted_return'])
               .nlargest(TOP_N_HIGHLIGHT, 'predicted_return')['ticker']
        )
        _SIG = {
            'BUY':  'background-color:#d4edda;color:#155724',
            'SELL': 'background-color:#f8d7da;color:#721c24',
            'HOLD': 'background-color:#fff3cd;color:#856404',
        }
        _TOP = 'background-color:#cce5ff;color:#004085;font-weight:bold'
        row_styles = {}
        for i, row in sdf.iterrows():
            sig  = _SIG.get(row.get('signal', ''), '')
            tick = row.get('ticker', '')
            if tick in top_return_tickers and not sig:
                row_styles[i] = _TOP
            elif sig:
                row_styles[i] = sig

        df_reset   = sdf.reset_index(drop=True)
        cell_hrefs = {}
        if corr_dir.exists():
            for i, row in df_reset.iterrows():
                plot = corr_dir / f'analysis_{row["ticker"]}.png'
                if plot.exists():
                    b64 = base64.b64encode(plot.read_bytes()).decode()
                    cell_hrefs[('signal', i)] = f'data:image/png;base64,{b64}'

        _save('signals_table', _build_table_html(
            df_reset, row_styles, height=500,
            link_cols={'ticker': 'https://finance.yahoo.com/quote/{value}'},
            cell_hrefs=cell_hrefs,
            col_descriptions=_SIGNALS_DESC,
        ))

    # ── Fundamentals table ────────────────────────────────────────────────────
    if fund_df is not None:
        row_styles = {}
        if 'likelihood_pct' in fund_df.columns:
            for i, val in enumerate(fund_df['likelihood_pct']):
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
        _save('fund_table', _build_table_html(
            fund_df.reset_index(), row_styles, height=540,
            link_cols={'ticker': 'https://finance.yahoo.com/quote/{value}'},
            col_descriptions=_FUND_DESC,
        ))

    # ── ECharts: Market Cap time series ───────────────────────────────────────
    if prices_df is not None and sdf is not None:
        if {'ticker', 'current_price', 'market_cap_B'}.issubset(sdf.columns):
            mcap_series = {}
            for _, r in sdf.iterrows():
                t = r['ticker']
                if t in prices_df.columns and r['current_price'] > 0:
                    mcap_series[t] = prices_df[t] * (r['market_cap_B'] / r['current_price'])
            mcap_df = pd.DataFrame(mcap_series)

            if not mcap_df.empty:
                by_abs  = [t for t in sdf['ticker'] if t in mcap_df.columns][:TOP_N_HIGHLIGHT]
                _mf     = mcap_df.loc[mcap_df.index >= pd.Timestamp(_CHART_START_DATE)]
                by_norm_m = ((_mf.iloc[-1] / _mf.iloc[0])
                             .sort_values(ascending=False).index.tolist()[:TOP_N_HIGHLIGHT])

                _save('mcap_series_abs', _build_echarts_html(
                    mcap_df, by_abs, nm,
                    norm_fn=lambda s: s / s.iloc[0] * 100, abs_fn=lambda s: s,
                    title=f'Top {TOP_N_HIGHLIGHT} by Current Market Cap',
                    y1_label='Normalized (base=100)', y2_label='Market Cap ($B)',
                ))
                _save('mcap_series_norm', _build_echarts_html(
                    mcap_df, by_norm_m, nm,
                    norm_fn=lambda s: s / s.iloc[0] * 100, abs_fn=lambda s: s,
                    title=f'Top {TOP_N_HIGHLIGHT} by Normalized Cap Growth',
                    y1_label='Normalized (base=100)', y2_label='Market Cap ($B)',
                ))

        # ── ECharts: Price Series ──────────────────────────────────────────────
        by_mcap  = [t for t in sdf['ticker'] if t in prices_df.columns][:TOP_N_HIGHLIGHT]
        by_price = prices_df.iloc[-1].sort_values(ascending=False).index.tolist()
        _pf      = prices_df.loc[prices_df.index >= pd.Timestamp(_CHART_START_DATE)]
        by_norm_price = ((_pf.iloc[-1] / _pf.iloc[0]).sort_values(ascending=False).index.tolist()
                         if not _pf.empty else by_price)
        by_norm  = (prices_df.iloc[-1] / prices_df.iloc[0]).sort_values(ascending=False).index.tolist()

        _pkw = dict(norm_fn=lambda s: s / s.iloc[0] * 100, abs_fn=lambda s: s,
                    y1_label='Normalized (base=100)', y2_label='Close price ($)')
        for cname, ordering, title in [
            ('price_by_mcap',       by_mcap,       f'Price Series — Top {TOP_N_HIGHLIGHT} by Market Cap'),
            ('price_by_price',      by_price,      f'Price Series — Top {TOP_N_HIGHLIGHT} by Stock Price'),
            ('price_by_norm_price', by_norm_price, f'Price Series — Top {TOP_N_HIGHLIGHT} by Normalized Stock Price'),
            ('price_by_norm',       by_norm,       f'Price Series — Top {TOP_N_HIGHLIGHT} by Normalized Return (full history)'),
        ]:
            top_t = [t for t in ordering if t in prices_df.columns][:TOP_N_HIGHLIGHT]
            _save(cname, _build_echarts_html(prices_df, top_t, nm, title=title, **_pkw))

    # ── ECharts: Volume ───────────────────────────────────────────────────────
    if vol_df is not None:
        by_abs_v   = vol_df.mean().sort_values(ascending=False).index.tolist()[:TOP_N_HIGHLIGHT]
        _norm_last = {t: _vol_norm(vol_df[t]).iloc[-1] for t in vol_df.columns}
        by_norm_v  = sorted(_norm_last,
                            key=lambda t: _norm_last[t] if pd.notna(_norm_last[t]) else 0,
                            reverse=True)[:TOP_N_HIGHLIGHT]

        _save('volume_abs', _build_echarts_html(
            vol_df, by_abs_v, nm,
            norm_fn=_vol_norm, abs_fn=lambda s: s,
            title=f'Top {TOP_N_HIGHLIGHT} by Average Volume',
            y1_label='Normalized (base=100)', y2_label='Volume (shares)',
        ))
        _save('volume_norm', _build_echarts_html(
            vol_df, by_norm_v, nm,
            norm_fn=_vol_norm, abs_fn=lambda s: s,
            title=f'Top {TOP_N_HIGHLIGHT} by Normalized Volume Growth',
            y1_label='Normalized (base=100)', y2_label='Volume (shares)',
        ))

    # ── ECharts: Cumulative Returns ───────────────────────────────────────────
    if prices_df is not None:
        _rf     = prices_df.loc[prices_df.index >= pd.Timestamp(_CHART_START_DATE)]
        top_t_r = (((_rf.iloc[-1] / _rf.iloc[0] - 1) * 100)
                   .sort_values(ascending=False).index.tolist()[:TOP_N_HIGHLIGHT])
        _save('returns', _build_echarts_html(
            prices_df, top_t_r, nm,
            norm_fn=lambda s: (s / s.iloc[0] - 1) * 100,
            abs_fn=lambda s: s - s.iloc[0],
            title=f'Cumulative Returns — Top {TOP_N_HIGHLIGHT} best performers highlighted',
            y1_label='Cum. return (%)', y2_label='$ return/share',
        ))

    print(f'  Dashboard cache ready → {cache_dir}')
