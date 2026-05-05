import pandas as pd


def compute_correlations(prices_df: pd.DataFrame):
    """Compute Pearson correlation matrix on daily returns.

    Returns (corr_matrix, returns_df).
    """
    returns = prices_df.pct_change().dropna()
    corr_matrix = returns.corr(method='pearson')
    return corr_matrix, returns


def get_top_correlated_pairs(corr_matrix: pd.DataFrame, top_n: int = 10) -> list:
    """Return the N pairs with the highest absolute correlation (direct or inverse)."""
    tickers = corr_matrix.columns.tolist()
    pairs = []
    for i in range(len(tickers)):
        for j in range(i + 1, len(tickers)):
            a, b = tickers[i], tickers[j]
            pairs.append((a, b, round(corr_matrix.loc[a, b], 4)))
    pairs.sort(key=lambda x: abs(x[2]), reverse=True)
    return pairs[:top_n]


def get_top_inverse_pairs(corr_matrix: pd.DataFrame, top_n: int = 10) -> list:
    """Return the N pairs with the most negative (inverse) correlation."""
    tickers = corr_matrix.columns.tolist()
    pairs = []
    for i in range(len(tickers)):
        for j in range(i + 1, len(tickers)):
            a, b = tickers[i], tickers[j]
            r = corr_matrix.loc[a, b]
            if r < 0:
                pairs.append((a, b, round(r, 4)))
    pairs.sort(key=lambda x: x[2])   # most negative first
    return pairs[:top_n]
