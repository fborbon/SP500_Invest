import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import TimeSeriesSplit
from sklearn.preprocessing import StandardScaler

from config import MIN_CORRELATION, PREDICTION_DAYS


def predict_price(target: str, returns: pd.DataFrame, corr_matrix: pd.DataFrame,
                  lookahead: int = None) -> tuple:
    """Predict future return of `target` using correlated tickers as features.

    Both direct (positive r) and inverse (negative r) correlators are used as
    predictors; LinearRegression assigns the correct sign to each coefficient.

    Returns (predicted_return, r2_score, top_predictors, corr_signs).
      corr_signs: dict mapping predictor ticker → raw Pearson r (float).
                  Positive = moves with target, negative = moves against it.
    """
    if lookahead is None:
        lookahead = PREDICTION_DAYS

    predictors = [t for t in returns.columns if t != target]
    if target not in corr_matrix.columns:
        return None, 0.0, [], {}

    corrs = corr_matrix[target][predictors].abs()
    top_pred = corrs[corrs >= MIN_CORRELATION].sort_values(ascending=False)

    if len(top_pred) < 2:
        return None, 0.0, [], {}

    pred_cols = top_pred.index.tolist()
    X = returns[pred_cols].values
    y_raw = returns[target].values

    n_samples = len(X) - lookahead
    if n_samples < 20:
        return None, 0.0, [], {}

    X_train = X[:n_samples]
    y_train = np.array([
        y_raw[i:i + lookahead].sum()   # cumulative return over N days
        for i in range(n_samples)
    ])

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X_train)

    tscv = TimeSeriesSplit(n_splits=3)
    r2_scores = []
    for train_idx, val_idx in tscv.split(X_scaled):
        if len(train_idx) < 10:
            continue
        m = LinearRegression()
        m.fit(X_scaled[train_idx], y_train[train_idx])
        r2_scores.append(m.score(X_scaled[val_idx], y_train[val_idx]))

    r2 = float(np.mean(r2_scores)) if r2_scores else 0.0

    model = LinearRegression()
    model.fit(X_scaled, y_train)
    pred_return = float(model.predict(scaler.transform(X[-1:]))[0])

    top5 = pred_cols[:5]
    corr_signs = {col: float(corr_matrix[target][col]) for col in top5}

    return pred_return, r2, top5, corr_signs
