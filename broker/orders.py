from ib_insync import IB, LimitOrder, MarketOrder, Trade

from config import FALLBACK_PORTFOLIO, MAX_POSITION_PCT
from broker.connection import get_contract


def get_portfolio_value(ib: IB) -> float:
    """Return net liquidation value from IB account summary."""
    for av in ib.accountSummary():
        if av.tag == 'NetLiquidation' and av.currency == 'USD':
            return float(av.value)
    return FALLBACK_PORTFOLIO


def calculate_position_size(portfolio_value: float, price: float,
                             signal_strength: float = 1.0) -> int:
    """Return share count respecting the per-position limit.

    signal_strength (0.0–1.0) scales the position by model confidence.
    """
    max_value = portfolio_value * MAX_POSITION_PCT * signal_strength
    return max(1, int(max_value / price))


def execute_order(ib: IB, ticker: str, action: str, quantity: int,
                  order_type: str = 'MKT') -> Trade:
    """Place a market or limit order on IB."""
    contract = get_contract(ticker)
    ib.qualifyContracts(contract)

    if order_type == 'MKT':
        order = MarketOrder(action, quantity)
    else:
        ticker_data = ib.reqMktData(contract, '', False, False)
        ib.sleep(1)
        limit_price = ticker_data.ask if action == 'BUY' else ticker_data.bid
        order = LimitOrder(action, quantity, round(limit_price, 2))

    trade = ib.placeOrder(contract, order)
    ib.sleep(0.5)
    print(f"  → Orden {action} {quantity}x {ticker}: {trade.orderStatus.status}")
    return trade


def close_position(ib: IB, ticker: str):
    """Close an open position for the given ticker if one exists."""
    positions = {p.contract.symbol: p for p in ib.positions()}
    if ticker in positions:
        pos = positions[ticker]
        action = 'SELL' if pos.position > 0 else 'BUY'
        execute_order(ib, ticker, action, abs(int(pos.position)))
