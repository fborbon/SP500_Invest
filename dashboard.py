"""
SP500 Correlation Bot — Dashboard
Run with:  streamlit run dashboard.py
"""
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st
from pathlib import Path

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

        styled = df.style.map(_colour_signal, subset=['signal'])
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

        styled = df.style.map(_colour_likelihood, subset=['likelihood_pct']) \
                         if 'likelihood_pct' in df.columns else df.style
        st.dataframe(styled, use_container_width=True, height=600)


# ── Tab 3: Price Series & Market Cap ─────────────────────────────────────────
with tab_prices:
    gen_dir = run_dir / 'General'

    # ── Interactive market cap bar chart (Plotly) ─────────────────────────────
    signals_path = run_dir / 'signals.csv'
    if signals_path.exists():
        sdf = pd.read_csv(signals_path)
        if {'ticker', 'company_name', 'current_price', 'market_cap_B', 'sector'}.issubset(sdf.columns):
            sdf = sdf.dropna(subset=['market_cap_B']).sort_values('market_cap_B', ascending=False)
            top    = sdf.head(TOP_N_HIGHLIGHT)
            bottom = sdf.tail(TOP_N_HIGHLIGHT)

            fig = make_subplots(
                rows=2, cols=1,
                shared_xaxes=False,
                vertical_spacing=0.12,
                subplot_titles=[
                    f'Last Close Price ($) — top {TOP_N_HIGHLIGHT} vs bottom {TOP_N_HIGHLIGHT}',
                    f'Market Capitalization ($B) — top {TOP_N_HIGHLIGHT} vs bottom {TOP_N_HIGHLIGHT}',
                ],
            )

            hover_top = (
                '<b>%{customdata[0]}</b><br>'
                'Sector: %{customdata[1]}<br>'
                'Price: $%{y:,.2f}<br>'
                'Market Cap: $%{customdata[2]:.1f}B'
                '<extra></extra>'
            )
            hover_bottom = (
                '<b>%{customdata[0]}</b><br>'
                'Sector: %{customdata[1]}<br>'
                'Cap: $%{y:.1f}B<br>'
                'Price: $%{customdata[2]:,.2f}'
                '<extra></extra>'
            )

            for grp, colour, name in [(top, 'mediumseagreen', f'Top {TOP_N_HIGHLIGHT}'),
                                      (bottom, 'tomato',         f'Bottom {TOP_N_HIGHLIGHT}')]:
                cd_price = grp[['company_name', 'sector', 'market_cap_B']].values
                cd_cap   = grp[['company_name', 'sector', 'current_price']].values

                fig.add_trace(go.Bar(
                    x=grp['ticker'], y=grp['current_price'],
                    name=name, marker_color=colour,
                    customdata=cd_price, hovertemplate=hover_top,
                ), row=1, col=1)

                fig.add_trace(go.Bar(
                    x=grp['ticker'], y=grp['market_cap_B'],
                    name=name, marker_color=colour, showlegend=False,
                    customdata=cd_cap, hovertemplate=hover_bottom,
                ), row=2, col=1)

            fig.update_layout(
                height=750,
                title=f'Top vs Bottom {TOP_N_HIGHLIGHT} S&P 500 Companies',
                barmode='group',
                legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1),
            )
            fig.update_yaxes(title_text='Price ($)',    row=1, col=1)
            fig.update_yaxes(title_text='Market Cap ($B)', row=2, col=1)

            st.subheader('Market Cap Bars (interactive)')
            st.plotly_chart(fig, use_container_width=True)
            st.divider()

    # ── Static price series PNGs ──────────────────────────────────────────────
    if not gen_dir.exists():
        st.info('No General/ plots found for this run.')
    else:
        plots = sorted(p for p in gen_dir.glob('*.png') if 'price_series' in p.name)
        if not plots:
            st.info('No price series plots found for this run.')
        for plot in plots:
            title = (plot.stem
                     .replace('price_series_', 'Price Series — ')
                     .replace('-', ' ')
                     .replace('_', ' ')
                     .title())
            st.subheader(title)
            st.image(str(plot), use_container_width=True)
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
            st.image(str(matrix_path), use_container_width=True)
            st.divider()

        # Per-ticker analysis charts — two per row
        analysis_plots = sorted(corr_dir.glob('analysis_*.png'))
        if analysis_plots:
            st.subheader(f'Per-Ticker Prediction Analysis ({len(analysis_plots)} charts)')
            for i in range(0, len(analysis_plots), 2):
                cols = st.columns(2)
                for j, plot in enumerate(analysis_plots[i:i+2]):
                    ticker = plot.stem.replace('analysis_', '')
                    cols[j].image(str(plot), caption=ticker, use_container_width=True)
        elif not matrix_path.exists():
            st.info('No plots found in Correlation_method/ for this run.')
