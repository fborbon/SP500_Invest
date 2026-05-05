import pandas as pd


def compute_correlations(prices_df: pd.DataFrame):
    """Compute Pearson correlation matrix on daily returns.

    Returns (corr_matrix, returns_df).
    """
    returns = prices_df.pct_change().dropna()
    corr_matrix = returns.corr(method='pearson')
    return corr_matrix, returns


def get_top_correlated_pairs(corr_matrix: pd.DataFrame, top_n: int = 10) -> list:
    """Return the N pairs with the highest absolute correlation."""
    tickers = corr_matrix.columns.tolist()
    pairs = []
    for i in range(len(tickers)):
        for j in range(i + 1, len(tickers)):
            a, b = tickers[i], tickers[j]
            pairs.append((a, b, round(corr_matrix.loc[a, b], 4)))
    pairs.sort(key=lambda x: abs(x[2]), reverse=True)
    return pairs[:top_n]
