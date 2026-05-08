from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import yfinance as yf


# ── Scoring weights (must sum to 100) ────────────────────────────────────────
_WEIGHTS = {
    'revenue_growth':   15,   # growing top line
    'gross_margin':     10,   # pricing power / business quality
    'operating_margin': 10,   # operational efficiency
    'fcf':              10,   # real cash generation
    'current_ratio':    10,   # short-term solvency
    'debt_to_equity':   10,   # financial leverage risk
    'pe_ratio':         10,   # valuation vs earnings
    'peg_ratio':        10,   # valuation vs growth
    'earnings_growth':  10,   # profit momentum
    'pb_ratio':          5,   # valuation vs book value
}   # total = 100


def fetch_fundamentals(tickers: list) -> pd.DataFrame:
    """Fetch fundamental metrics for each ticker via yfinance.info.

    Uses 10 parallel threads with 2 retries each.
    Returns a DataFrame indexed by ticker with raw metric columns.
    """
    def _get_info(ticker):
        yf_ticker = ticker.replace('.', '-')
        for _ in range(2):
            try:
                info = yf.Ticker(yf_ticker).info
                return {
                    'ticker':           ticker,
                    'company_name':     info.get('longName'),
                    'sector':           info.get('sector'),
                    'revenue_growth':   info.get('revenueGrowth'),
                    'gross_margin':     info.get('grossMargins'),
                    'operating_margin': info.get('operatingMargins'),
                    'net_margin':       info.get('profitMargins'),
                    'free_cash_flow':   info.get('freeCashflow'),
                    'current_ratio':    info.get('currentRatio'),
                    'debt_to_equity':   info.get('debtToEquity'),   # yfinance: % (150 = 1.5×)
                    'pe_ratio':         info.get('trailingPE'),
                    'peg_ratio':        info.get('pegRatio'),
                    'ps_ratio':         info.get('priceToSalesTrailing12Months'),
                    'pb_ratio':         info.get('priceToBook'),
                    'ev_ebitda':        info.get('enterpriseToEbitda'),
                    'eps':              info.get('trailingEps'),
                    'earnings_growth':  info.get('earningsGrowth'),
                    'market_cap_B':     round(info.get('marketCap', 0) / 1e9, 1) or None,
                }
            except Exception:
                pass
        return {'ticker': ticker}

    print(f"\nFetching fundamentals for {len(tickers)} tickers via yfinance"
          f" (may take a few minutes)...")
    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(_get_info, tickers))

    df = pd.DataFrame(results).set_index('ticker')
    ok = df.drop(columns=['company_name', 'sector', 'market_cap_B'],
                 errors='ignore').notna().any(axis=1).sum()
    print(f"  ✓ Fundamentals retrieved: {ok}/{len(tickers)}")
    return df


def score_fundamentals(df: pd.DataFrame) -> pd.DataFrame:
    """Score each company on 10 fundamental criteria and compute likelihood_pct.

    Each criterion is scored 0–(weight) and summed to a 0–100 likelihood
    that the stock price will increase over the next 12 months.

    Returns a copy of df with a 'likelihood_pct' column, sorted descending.
    """
    out = df.copy()

    def _score(series, thresholds):
        """thresholds: [(upper_bound, score), ...] evaluated top-down."""
        def _apply(x):
            if pd.isna(x):
                return thresholds[-1][1] // 2   # neutral if missing
            for bound, pts in thresholds:
                if bound is None or x <= bound:
                    return pts
            return thresholds[-1][1]
        return series.apply(_apply)

    w = _WEIGHTS

    # Revenue growth — higher is better
    out['s_revenue_growth'] = _score(df['revenue_growth'], [
        (0.00, 0), (0.05, round(w['revenue_growth'] * 0.33)),
        (0.10, round(w['revenue_growth'] * 0.60)),
        (0.20, round(w['revenue_growth'] * 0.80)),
        (None, w['revenue_growth']),
    ])

    # Gross margin — higher = stronger moat
    out['s_gross_margin'] = _score(df['gross_margin'], [
        (0.10, 0), (0.25, round(w['gross_margin'] * 0.40)),
        (0.40, round(w['gross_margin'] * 0.70)),
        (0.60, round(w['gross_margin'] * 0.85)),
        (None, w['gross_margin']),
    ])

    # Operating margin — higher = more efficient
    out['s_operating_margin'] = _score(df['operating_margin'], [
        (0.00, 0), (0.05, round(w['operating_margin'] * 0.40)),
        (0.15, round(w['operating_margin'] * 0.70)),
        (None, w['operating_margin']),
    ])

    # Free cash flow — positive is essential
    out['s_fcf'] = df['free_cash_flow'].apply(
        lambda x: w['fcf'] if pd.notna(x) and x > 0 else
                  round(w['fcf'] * 0.5) if pd.isna(x) else 0
    )

    # Current ratio — above 1.5 is healthy (yfinance raw value)
    out['s_current_ratio'] = _score(df['current_ratio'], [
        (0.80, 0), (1.00, round(w['current_ratio'] * 0.40)),
        (1.50, round(w['current_ratio'] * 0.70)),
        (2.00, round(w['current_ratio'] * 0.85)),
        (None, w['current_ratio']),
    ])

    # Debt-to-equity (yfinance reports as %, so 150 = 1.5×) — lower is safer
    out['s_debt_to_equity'] = _score(df['debt_to_equity'], [
        (50,  w['debt_to_equity']),
        (100, round(w['debt_to_equity'] * 0.70)),
        (200, round(w['debt_to_equity'] * 0.40)),
        (None, 0),
    ])

    # P/E — moderate is best; very high or negative is risky
    def _pe_score(x):
        if pd.isna(x) or x <= 0:
            return round(w['pe_ratio'] * 0.5)
        if x < 12:   return w['pe_ratio']           # deep value
        if x < 20:   return round(w['pe_ratio'] * 0.85)
        if x < 30:   return round(w['pe_ratio'] * 0.65)
        if x < 50:   return round(w['pe_ratio'] * 0.40)
        return round(w['pe_ratio'] * 0.15)           # very expensive
    out['s_pe_ratio'] = df['pe_ratio'].apply(_pe_score)

    # PEG — below 1 = undervalued relative to growth
    out['s_peg_ratio'] = _score(df['peg_ratio'], [
        (0, round(w['peg_ratio'] * 0.5)),   # negative PEG ambiguous
        (1, w['peg_ratio']),
        (1.5, round(w['peg_ratio'] * 0.70)),
        (2, round(w['peg_ratio'] * 0.40)),
        (None, 0),
    ])

    # Earnings growth — momentum matters
    out['s_earnings_growth'] = _score(df['earnings_growth'], [
        (0.00, 0), (0.05, round(w['earnings_growth'] * 0.40)),
        (0.15, round(w['earnings_growth'] * 0.70)),
        (0.25, round(w['earnings_growth'] * 0.85)),
        (None, w['earnings_growth']),
    ])

    # P/B — below 1 = trading below book (value signal)
    out['s_pb_ratio'] = _score(df['pb_ratio'], [
        (0, round(w['pb_ratio'] * 0.5)),
        (1, w['pb_ratio']),
        (3, round(w['pb_ratio'] * 0.60)),
        (6, round(w['pb_ratio'] * 0.20)),
        (None, 0),
    ])

    score_cols = [c for c in out.columns if c.startswith('s_')]
    out['likelihood_pct'] = out[score_cols].sum(axis=1).clip(0, 100).round(1)

    # Build clean display table
    display_cols = [
        'company_name', 'sector', 'market_cap_B',
        'revenue_growth', 'gross_margin', 'operating_margin', 'net_margin',
        'free_cash_flow', 'current_ratio', 'debt_to_equity',
        'pe_ratio', 'peg_ratio', 'ps_ratio', 'pb_ratio', 'ev_ebitda',
        'eps', 'earnings_growth',
        'likelihood_pct',
    ]
    cols = [c for c in display_cols if c in out.columns]
    return out[cols].sort_values('likelihood_pct', ascending=False)


def save_fundamentals_csv(df: pd.DataFrame, path) -> None:
    """Format percentages and save the fundamentals table to CSV."""
    out = df.copy()
    pct_cols = ['revenue_growth', 'gross_margin', 'operating_margin',
                'net_margin', 'earnings_growth']
    for col in pct_cols:
        if col in out.columns:
            out[col] = out[col].apply(
                lambda x: f'{x*100:.1f}%' if pd.notna(x) else 'N/A'
            )
    if 'free_cash_flow' in out.columns:
        out['free_cash_flow'] = out['free_cash_flow'].apply(
            lambda x: f'${x/1e9:.2f}B' if pd.notna(x) else 'N/A'
        )
    out.to_csv(path)
    print(f"  Fundamentals saved to: {path}")
