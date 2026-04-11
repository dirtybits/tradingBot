from __future__ import annotations

from datetime import date as _Date
from decimal import Decimal
from typing import Any

from mcp.server.fastmcp import FastMCP

from cbpro import CoinbaseAdvancedTradeClient
from dca import execute_dca, load_dca_config
from strategies import (
    latest_relative_strength_index,
    moving_average_crossover_signal,
    rsi_signal,
    simple_moving_average,
    trend_rsi_signal,
)

mcp = FastMCP(
    "tradebot",
    instructions=(
        "Coinbase Advanced Trade tools for the local tradebot installation. "
        "All order tools default to paper mode (live=False) and will NOT submit real orders "
        "unless live=True is explicitly passed. Always confirm with the user before passing live=True."
    ),
)


@mcp.tool()
def get_price(symbols: list[str], quote: str = "USD") -> dict[str, Any]:
    """Get current market prices for one or more base symbols.

    Returns a dict mapping each symbol to its latest trade price, plus a 'time' key.
    Example: get_price(["BTC", "ETH"]) -> {"BTC": 82000.0, "ETH": 1900.0, "time": "..."}
    """
    client = CoinbaseAdvancedTradeClient.from_env(live_mode=False)
    return client.check_prices(symbols, quote=quote)


@mcp.tool()
def get_balances(include_zero: bool = False) -> list[dict[str, Any]]:
    """Get Coinbase account balances. Requires CB_API_KEY and CB_API_SECRET.

    Set include_zero=True to see all accounts including zero-balance ones.
    """
    client = CoinbaseAdvancedTradeClient.from_env(live_mode=True)
    return client.get_balances(non_zero_only=not include_zero)


@mcp.tool()
def get_signal(
    product_id: str,
    strategy: str = "crossover",
    candles: int = 50,
    granularity: str = "ONE_HOUR",
    short_window: int = 5,
    long_window: int = 20,
    period: int = 14,
    oversold: float = 30.0,
    overbought: float = 70.0,
    trend_window: int = 20,
) -> dict[str, Any]:
    """Compute a buy/sell/hold signal from recent candles.

    strategy: "crossover" | "rsi" | "trend-rsi"
    granularity: ONE_MINUTE | FIVE_MINUTE | FIFTEEN_MINUTE | THIRTY_MINUTE |
                 ONE_HOUR | TWO_HOUR | SIX_HOUR | ONE_DAY
    candles: number of candles to fetch (max 350). For trend-rsi, candles must exceed trend_window.
    """
    client = CoinbaseAdvancedTradeClient.from_env(live_mode=False)
    candle_data = client.get_candles(product_id, granularity=granularity, limit=candles)
    if not candle_data:
        return {"error": f"No candle data returned for {product_id}"}

    prices = [float(c["close"]) for c in candle_data]
    result: dict[str, Any] = {
        "product_id": product_id,
        "strategy": strategy,
        "candles_fetched": len(prices),
        "granularity": granularity,
    }

    if strategy == "crossover":
        result["signal"] = moving_average_crossover_signal(
            prices, short_window=short_window, long_window=long_window
        )
        result["short_ma"] = round(simple_moving_average(prices, short_window), 8)
        result["long_ma"] = round(simple_moving_average(prices, long_window), 8)
        result["short_window"] = short_window
        result["long_window"] = long_window
    elif strategy == "rsi":
        result["signal"] = rsi_signal(
            prices, period=period, oversold=oversold, overbought=overbought
        )
        result["rsi"] = round(latest_relative_strength_index(prices, period=period), 2)
        result["period"] = period
        result["oversold"] = oversold
        result["overbought"] = overbought
    else:  # trend-rsi
        result["signal"] = trend_rsi_signal(
            prices,
            period=period,
            oversold=oversold,
            overbought=overbought,
            trend_window=trend_window,
        )
        result["rsi"] = round(latest_relative_strength_index(prices, period=period), 2)
        result["trend_ma"] = round(simple_moving_average(prices, trend_window), 8)
        result["price"] = prices[-1]
        result["period"] = period
        result["oversold"] = oversold
        result["overbought"] = overbought
        result["trend_window"] = trend_window

    return result


@mcp.tool()
def place_market_buy(
    product_id: str,
    funds: float,
    live: bool = False,
) -> dict[str, Any]:
    """Place a market buy order. Paper mode by default — pass live=True to submit a real order.

    product_id: e.g. "BTC-USD"
    funds: quote-currency amount to spend (e.g. 100.0 for $100)
    live: set True only after explicit user confirmation
    """
    client = CoinbaseAdvancedTradeClient.from_env(live_mode=live)
    return client.place_market_order(product_id, funds=Decimal(str(funds)))


@mcp.tool()
def place_market_sell(
    product_id: str,
    size: float,
    live: bool = False,
) -> dict[str, Any]:
    """Place a market sell order. Paper mode by default — pass live=True to submit a real order.

    product_id: e.g. "BTC-USD"
    size: base-asset amount to sell (e.g. 0.001 for 0.001 BTC)
    live: set True only after explicit user confirmation
    """
    client = CoinbaseAdvancedTradeClient.from_env(live_mode=live)
    return client.place_market_order(product_id, base_size=Decimal(str(size)), side="SELL")


@mcp.tool()
def place_limit_buy(
    product_id: str,
    funds: float,
    discount_pct: float = 0.3,
    post_only: bool = False,
    live: bool = False,
) -> dict[str, Any]:
    """Place a GTC limit buy below the current market price (targets maker fee).

    product_id: e.g. "BTC-USD"
    funds: quote-currency amount to spend
    discount_pct: percent below market to place the limit (default 0.3%)
    post_only: if True, cancel instead of crossing as taker (guarantees maker fee)
    live: set True only after explicit user confirmation
    """
    client = CoinbaseAdvancedTradeClient.from_env(live_mode=live)
    symbol, _, quote_currency = product_id.partition("-")
    prices = client.check_prices([symbol], quote=quote_currency or "USD")
    ref_price = prices.get(symbol)
    if ref_price is None:
        return {"error": f"Could not fetch price for {product_id}"}
    return client.place_limit_order(
        product_id,
        side="BUY",
        quote_amount=Decimal(str(funds)),
        reference_price=ref_price,
        price_factor=Decimal(str(discount_pct)) / Decimal("100"),
        post_only=post_only,
    )


@mcp.tool()
def place_limit_sell(
    product_id: str,
    size: float,
    premium_pct: float = 0.3,
    post_only: bool = False,
    live: bool = False,
) -> dict[str, Any]:
    """Place a GTC limit sell above the current market price (targets maker fee).

    product_id: e.g. "BTC-USD"
    size: base-asset amount to sell
    premium_pct: percent above market to place the limit (default 0.3%)
    post_only: if True, cancel instead of crossing as taker (guarantees maker fee)
    live: set True only after explicit user confirmation
    """
    client = CoinbaseAdvancedTradeClient.from_env(live_mode=live)
    symbol, _, quote_currency = product_id.partition("-")
    prices = client.check_prices([symbol], quote=quote_currency or "USD")
    ref_price = prices.get(symbol)
    if ref_price is None:
        return {"error": f"Could not fetch price for {product_id}"}
    return client.place_limit_order(
        product_id,
        side="SELL",
        base_size=Decimal(str(size)),
        reference_price=ref_price,
        price_factor=Decimal(str(premium_pct)) / Decimal("100"),
        post_only=post_only,
    )


@mcp.tool()
def get_open_orders(product_id: str | None = None) -> list[dict[str, Any]]:
    """List open orders. Optionally filter by product_id (e.g. "BTC-USD").

    Requires CB_API_KEY and CB_API_SECRET.
    """
    client = CoinbaseAdvancedTradeClient.from_env(live_mode=True)
    return client.get_open_orders(product_id=product_id)


@mcp.tool()
def run_dca(
    config_path: str,
    live: bool = False,
    run_date: str | None = None,
) -> dict[str, Any]:
    """Run config-driven daily DCA limit buys from a YAML/JSON/TOML config file.

    Paper mode by default — pass live=True to submit real orders.
    run_date: override the execution date in YYYY-MM-DD format (useful for backfills/testing).

    If the config includes signal_strategy (crossover/rsi/trend-rsi), each asset is only
    bought when its signal is 'buy' — others are recorded as 'skipped_signal' in results.

    Repeated same-day live runs skip assets already submitted (SQLite ledger deduplication).
    """
    config = load_dca_config(config_path)
    parsed_date = _Date.fromisoformat(run_date) if run_date else None
    client = CoinbaseAdvancedTradeClient.from_env(live_mode=live)
    return execute_dca(client, config, live_mode=live, run_date=parsed_date)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
