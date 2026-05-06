import datetime

import pandas as pd

from config import OUTPUTS_DIR


def print_report(signals_df: pd.DataFrame, top_pairs: list,
                 inverse_pairs: list = None):
    """Print a human-readable summary of signals, direct pairs, and inverse pairs."""
    now = datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
    print("\n" + "═" * 62)
    print(f"  SP500 CORRELATION BOT — Informe {now}")
    print("═" * 62)

    buys  = signals_df[signals_df['signal'] == 'BUY']
    sells = signals_df[signals_df['signal'] == 'SELL']
    holds = signals_df[signals_df['signal'] == 'HOLD']

    print(f"\n  SEÑALES: {len(buys)} BUY · {len(holds)} HOLD · {len(sells)} SELL\n")

    print("  ── COMPRAS ──────────────────────────────────────────")
    for _, r in buys.iterrows():
        print(f"  ▲ {r['ticker']:<6} ${r['current_price']:.2f} → ${r['target_price_7d']:.2f}  "
              f"(+{r['predicted_return']:.1f}%)  R²={r['model_r2']:.2f}")
        if r['direct_top5_predictors']:
            print(f"      ↑ directo:   {r['direct_top5_predictors']}")
        if r['inverse_top5_predictors']:
            print(f"      ↓ inverso:   {r['inverse_top5_predictors']}")

    if not sells.empty:
        print("\n  ── VENTAS ───────────────────────────────────────────")
        for _, r in sells.iterrows():
            print(f"  ▼ {r['ticker']:<6} ${r['current_price']:.2f} → ${r['target_price_7d']:.2f}  "
                  f"({r['predicted_return']:.1f}%)  R²={r['model_r2']:.2f}")
            if r['direct_top5_predictors']:
                print(f"      ↑ directo:   {r['direct_top5_predictors']}")
            if r['inverse_top5_predictors']:
                print(f"      ↓ inverso:   {r['inverse_top5_predictors']}")

    print("\n  ── TOP 5 PARES CORRELACIÓN DIRECTA ─────────────────")
    for a, b, r in top_pairs[:5]:
        if r > 0:
            bar = '█' * int(abs(r) * 20)
            print(f"  {a:<6} ↑↑ {b:<6}  r={r:+.3f}  {bar}")

    if inverse_pairs:
        print("\n  ── TOP 5 PARES CORRELACIÓN INVERSA ─────────────────")
        for a, b, r in inverse_pairs[:5]:
            bar = '█' * int(abs(r) * 20)
            print(f"  {a:<6} ↑↓ {b:<6}  r={r:+.3f}  {bar}")

    print("\n" + "═" * 62)


def save_signals_csv(signals_df: pd.DataFrame, path=None):
    """Save signals to CSV in the outputs directory."""
    if path is None:
        path = OUTPUTS_DIR / 'signals.csv'
    signals_df.to_csv(path, index=False)
    print(f"  Señales guardadas en: {path}")
