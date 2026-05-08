"""
SP500 Correlation Bot — Dashboard
Run with:  streamlit run dashboard.py
"""
import pandas as pd
import streamlit as st
from pathlib import Path

from config import OUTPUTS_DIR

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

selected = st.sidebar.selectbox(
    'Select run',
    [d.name for d in run_dirs],
    index=0,
)
run_dir = OUTPUTS_DIR / selected
st.sidebar.caption(f'📁 {run_dir}')

# ── Tabs ──────────────────────────────────────────────────────────────────────
tab_signals, tab_fund, tab_prices, tab_corr = st.tabs([
    '📋 Signals',
    '🏦 Fundamentals',
    '📊 Price Series & Market Cap',
    '🔗 Correlation Analysis',
])


# ── Tab 1: Signals ────────────────────────────────────────────────────────────
with tab_signals:
    path = run_dir / 'signals.csv'
    if not path.exists():
        st.info('signals.csv not found for this run.')
    else:
        df = pd.read_csv(path)

        # Summary metrics
        buys  = (df['signal'] == 'BUY').sum()
        sells = (df['signal'] == 'SELL').sum()
        holds = (df['signal'] == 'HOLD').sum()
        c1, c2, c3, c4 = st.columns(4)
        c1.metric('Total tickers', len(df))
        c2.metric('BUY', buys,  delta=None)
        c3.metric('SELL', sells, delta=None)
        c4.metric('HOLD', holds, delta=None)

        st.divider()

        # Colour rows by signal
        def _colour_signal(val):
            colours = {
                'BUY':  'background-color: #d4edda; color: #155724',
                'SELL': 'background-color: #f8d7da; color: #721c24',
                'HOLD': 'background-color: #fff3cd; color: #856404',
            }
            return colours.get(val, '')

        styled = df.style.applymap(_colour_signal, subset=['signal'])
        st.dataframe(styled, use_container_width=True, height=600)


# ── Tab 2: Fundamentals ───────────────────────────────────────────────────────
with tab_fund:
    path = run_dir / 'fundamentals.csv'
    if not path.exists():
        st.info('fundamentals.csv not found for this run.')
    else:
        df = pd.read_csv(path, index_col=0)

        # Summary metrics
        c1, c2, c3 = st.columns(3)
        c1.metric('Companies analysed', len(df))
        if 'likelihood_pct' in df.columns:
            c2.metric('Avg likelihood', f"{df['likelihood_pct'].mean():.1f}%")
            c3.metric('Top score', f"{df['likelihood_pct'].max():.1f}%")

        st.divider()

        # Colour likelihood_pct column
        def _colour_likelihood(val):
            try:
                v = float(val)
                if v >= 70: return 'background-color: #d4edda; color: #155724'
                if v >= 50: return 'background-color: #fff3cd; color: #856404'
                return 'background-color: #f8d7da; color: #721c24'
            except Exception:
                return ''

        styled = df.style.applymap(_colour_likelihood, subset=['likelihood_pct']) \
                         if 'likelihood_pct' in df.columns else df.style
        st.dataframe(styled, use_container_width=True, height=600)


# ── Tab 3: Price Series & Market Cap ─────────────────────────────────────────
with tab_prices:
    gen_dir = run_dir / 'General'
    if not gen_dir.exists():
        st.info('No General/ plots found for this run.')
    else:
        plots = sorted(gen_dir.glob('*.png'))
        if not plots:
            st.info('No PNG files in General/ for this run.')
        for plot in plots:
            title = (plot.stem
                     .replace('price_series_', 'Price Series — ')
                     .replace('market_cap_bars', 'Market Cap Bars')
                     .replace('-', ' ')
                     .replace('_', ' ')
                     .title())
            st.subheader(title)
            st.image(str(plot), use_column_width=True)
            st.divider()


# ── Tab 4: Correlation Analysis ───────────────────────────────────────────────
with tab_corr:
    corr_dir = run_dir / 'Correlation_method'
    if not corr_dir.exists():
        st.info('No Correlation_method/ plots found for this run.')
    else:
        # Correlation matrix
        matrix_path = corr_dir / 'correlation_matrix.png'
        if matrix_path.exists():
            st.subheader('Correlation Matrix')
            st.image(str(matrix_path), use_column_width=True)
            st.divider()

        # Per-ticker analysis charts — two per row
        analysis_plots = sorted(corr_dir.glob('analysis_*.png'))
        if analysis_plots:
            st.subheader(f'Per-Ticker Prediction Analysis ({len(analysis_plots)} charts)')
            for i in range(0, len(analysis_plots), 2):
                cols = st.columns(2)
                for j, plot in enumerate(analysis_plots[i:i+2]):
                    ticker = plot.stem.replace('analysis_', '')
                    cols[j].image(str(plot), caption=ticker, use_column_width=True)
        elif not matrix_path.exists():
            st.info('No plots found in Correlation_method/ for this run.')
