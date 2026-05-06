import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import TimeSeriesSplit

from config import MIN_CORRELATION, PREDICTION_DAYS


def predict_price(target: str, returns: pd.DataFrame, corr_matrix: pd.DataFrame,
                  lookahead: int = None) -> tuple:
    """Predict future return of `target` using correlated tickers as features.

    Both direct (positive r) and inverse (negative r) correlators are used as
    predictors. RandomForestRegressor captures non-linear relationships and is
    scale-invariant so no StandardScaler is needed.

    Returns:
        (predicted_return, r2_score, top_predictors, corr_signs, y_actual, y_predicted)
        corr_signs    : dict mapping predictor ticker → raw Pearson r (float).
        y_actual      : np.ndarray of actual cumulative returns used for training.
        y_predicted   : np.ndarray of in-sample model predictions (same length).
        All arrays are None on early-exit paths.
    """
    if lookahead is None:
        lookahead = PREDICTION_DAYS

    predictors = [t for t in returns.columns if t != target]
    if target not in corr_matrix.columns:
        return None, 0.0, [], {}, None, None

    corrs = corr_matrix[target][predictors].abs()  # Looks for positive and inverse correlations
    top_pred = corrs[corrs >= MIN_CORRELATION].sort_values(ascending=False)

    if len(top_pred) < 2:
        return None, 0.0, [], {}, None, None

    pred_cols = top_pred.index.tolist()
    X = returns[pred_cols].values
    y_raw = returns[target].values

    n_samples = len(X) - lookahead
    if n_samples < 20:
        return None, 0.0, [], {}, None, None

    X_train = X[:n_samples]
    y_train = np.array([
        y_raw[i:i + lookahead].sum()   # cumulative return over N days
        for i in range(n_samples)
    ])

    tscv = TimeSeriesSplit(n_splits=3)
    r2_scores = []
    for train_idx, val_idx in tscv.split(X_train):
        if len(train_idx) < 10:
            continue
        m = RandomForestRegressor(
            n_estimators=100, max_depth=4, min_samples_leaf=10,
            random_state=42, n_jobs=-1
        )
        m.fit(X_train[train_idx], y_train[train_idx])
        r2_scores.append(m.score(X_train[val_idx], y_train[val_idx]))

    r2 = float(np.mean(r2_scores)) if r2_scores else 0.0

    model = RandomForestRegressor(
        n_estimators=200, max_depth=4, min_samples_leaf=10,
        random_state=42, n_jobs=-1
    )
    model.fit(X_train, y_train)

    y_predicted  = model.predict(X_train)
    pred_return  = float(model.predict(X[-1:].reshape(1, -1))[0])

    top5       = pred_cols[:5]  # Hardcoded. Top 5 most correlated tickers for target
    corr_signs = {col: float(corr_matrix[target][col]) for col in top5}

    return pred_return, r2, top5, corr_signs, y_train, y_predicted
