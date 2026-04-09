from __future__ import annotations

import argparse
import asyncio
import json
import sys
import textwrap
from typing import Any

from cbpro import CoinbaseAdvancedTradeClient, CoinbaseBotError, parse_positive_decimal
from webfeed import CoinbaseWebsocketError, collect_latest_prices


# ---------------------------------------------------------------------------
# Help epilogs — real invocations make pattern-matching easy for agents
# ---------------------------------------------------------------------------

_PRICE_EPILOG = textwrap.dedent("""\
    Examples:
      tradebot price BTC
      tradebot price BTC ETH SOL
      tradebot price BTC ETH --quote EUR
""")

_BALANCES_EPILOG = textwrap.dedent("""\
    Examples:
      tradebot balances
      tradebot balances --all
""")

_BUY_EPILOG = textwrap.dedent("""\
    Paper mode (default) builds the order payload without sending it.
    Pass --live --yes to submit a real market order.

    Examples:
      tradebot buy BTC-USD --funds 100
      tradebot buy ETH-USD --funds 50 --live --yes
""")

_SELL_EPILOG = textwrap.dedent("""\
    Paper mode (default) builds the order payload without sending it.
    Pass --live --yes to submit a real market order.

    Examples:
      tradebot sell BTC-USD --size 0.001
      tradebot sell ETH-USD --size 0.01 --live --yes
""")

_FEED_EPILOG = textwrap.dedent("""\
    Examples:
      tradebot feed BTC-USD
      tradebot feed BTC-USD ETH-USD SOL-USD
""")

_SIGNAL_EPILOG = textwrap.dedent("""\
    Fetches recent candles from the REST API and computes a buy/sell/hold signal.
    Strategies:
      crossover  Moving-average crossover (short MA vs long MA)
      rsi        Relative Strength Index

    Examples:
      tradebot signal BTC-USD
      tradebot signal BTC-USD --strategy rsi
      tradebot signal ETH-USD --strategy crossover --short-window 5 --long-window 20
      tradebot signal BTC-USD --strategy rsi --candles 50 --period 14 --oversold 30 --overbought 70
      tradebot signal BTC-USD --granularity FIFTEEN_MINUTE --candles 100
""")


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tradebot",
        description="Coinbase Advanced Trade CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # price -------------------------------------------------------------------
    price_parser = subparsers.add_parser(
        "price",
        help="Fetch current prices for one or more symbols",
        epilog=_PRICE_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    price_parser.add_argument("symbols", nargs="+", help="Base symbols such as BTC ETH")
    price_parser.add_argument("--quote", default="USD", help="Quote currency (default: USD)")

    # balances ----------------------------------------------------------------
    balances_parser = subparsers.add_parser(
        "balances",
        help="List account balances (requires credentials)",
        epilog=_BALANCES_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    balances_parser.add_argument(
        "--all",
        action="store_true",
        help="Include zero-balance accounts",
    )

    # buy ---------------------------------------------------------------------
    buy_parser = subparsers.add_parser(
        "buy",
        help="Place a market buy order — paper mode by default",
        epilog=_BUY_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    buy_parser.add_argument("product_id", help="Product such as BTC-USD")
    buy_parser.add_argument(
        "--funds",
        required=True,
        type=parse_positive_decimal,
        help="Quote funds to spend (e.g. 100 for $100)",
    )
    buy_parser.add_argument(
        "--live",
        action="store_true",
        help="Submit a real order — requires --yes",
    )
    buy_parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm live order submission",
    )

    # sell --------------------------------------------------------------------
    sell_parser = subparsers.add_parser(
        "sell",
        help="Place a market sell order — paper mode by default",
        epilog=_SELL_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sell_parser.add_argument("product_id", help="Product such as BTC-USD")
    sell_parser.add_argument(
        "--size",
        required=True,
        type=parse_positive_decimal,
        help="Base asset amount to sell (e.g. 0.001 for 0.001 BTC)",
    )
    sell_parser.add_argument(
        "--live",
        action="store_true",
        help="Submit a real order — requires --yes",
    )
    sell_parser.add_argument(
        "--yes",
        action="store_true",
        help="Confirm live order submission",
    )

    # feed --------------------------------------------------------------------
    feed_parser = subparsers.add_parser(
        "feed",
        help="Collect one websocket ticker update per product",
        epilog=_FEED_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    feed_parser.add_argument("product_ids", nargs="+", help="Products such as BTC-USD ETH-USD")

    # signal ------------------------------------------------------------------
    signal_parser = subparsers.add_parser(
        "signal",
        help="Compute a buy/sell/hold signal from recent candles",
        epilog=_SIGNAL_EPILOG,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    signal_parser.add_argument("product_id", help="Product such as BTC-USD")
    signal_parser.add_argument(
        "--strategy",
        choices=["crossover", "rsi"],
        default="crossover",
        help="Strategy: crossover or rsi (default: crossover)",
    )
    signal_parser.add_argument(
        "--candles",
        type=int,
        default=50,
        metavar="N",
        help="Number of candles to fetch (default: 50, max: 350)",
    )
    signal_parser.add_argument(
        "--granularity",
        default="ONE_HOUR",
        choices=[
            "ONE_MINUTE", "FIVE_MINUTE", "FIFTEEN_MINUTE", "THIRTY_MINUTE",
            "ONE_HOUR", "TWO_HOUR", "SIX_HOUR", "ONE_DAY",
        ],
        help="Candle granularity (default: ONE_HOUR)",
    )
    signal_parser.add_argument(
        "--short-window",
        type=int,
        default=5,
        metavar="N",
        help="Short MA window for crossover strategy (default: 5)",
    )
    signal_parser.add_argument(
        "--long-window",
        type=int,
        default=20,
        metavar="N",
        help="Long MA window for crossover strategy (default: 20)",
    )
    signal_parser.add_argument(
        "--period",
        type=int,
        default=14,
        metavar="N",
        help="RSI lookback period (default: 14)",
    )
    signal_parser.add_argument(
        "--oversold",
        type=float,
        default=30.0,
        metavar="THRESHOLD",
        help="RSI oversold threshold → buy signal (default: 30)",
    )
    signal_parser.add_argument(
        "--overbought",
        type=float,
        default=70.0,
        metavar="THRESHOLD",
        help="RSI overbought threshold → sell signal (default: 70)",
    )

    return parser


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _check_live_confirmation(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
) -> None:
    """Exit with an actionable error if --live is set without --yes."""
    if not args.live or args.yes:
        return
    if args.command == "buy":
        example = f"tradebot buy {args.product_id} --funds {args.funds} --live --yes"
    else:
        example = f"tradebot sell {args.product_id} --size {args.size} --live --yes"
    parser.exit(
        status=1,
        message=(
            f"Error: --live requires --yes to prevent accidental order submission.\n"
            f"  {example}\n"
        ),
    )


def _compute_signal(args: argparse.Namespace, prices: list[float]) -> dict[str, Any]:
    from strategies import (
        latest_relative_strength_index,
        moving_average_crossover_signal,
        rsi_signal,
        simple_moving_average,
    )

    result: dict[str, Any] = {
        "product_id": args.product_id,
        "strategy": args.strategy,
        "candles_fetched": len(prices),
        "granularity": args.granularity,
    }

    if args.strategy == "crossover":
        result["signal"] = moving_average_crossover_signal(
            prices, short_window=args.short_window, long_window=args.long_window
        )
        result["short_ma"] = round(simple_moving_average(prices, args.short_window), 8)
        result["long_ma"] = round(simple_moving_average(prices, args.long_window), 8)
        result["short_window"] = args.short_window
        result["long_window"] = args.long_window
    else:  # rsi
        result["signal"] = rsi_signal(
            prices, period=args.period, oversold=args.oversold, overbought=args.overbought
        )
        result["rsi"] = round(latest_relative_strength_index(prices, period=args.period), 2)
        result["period"] = args.period
        result["oversold"] = args.oversold
        result["overbought"] = args.overbought

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    try:
        if args.command == "price":
            client = CoinbaseAdvancedTradeClient.from_env(live_mode=False)
            result = client.check_prices(args.symbols, quote=args.quote)

        elif args.command == "balances":
            client = CoinbaseAdvancedTradeClient.from_env(live_mode=True)
            result = client.get_balances(non_zero_only=not args.all)

        elif args.command == "buy":
            _check_live_confirmation(parser, args)
            client = CoinbaseAdvancedTradeClient.from_env(live_mode=args.live and args.yes)
            result = client.place_market_order(args.product_id, funds=args.funds)

        elif args.command == "sell":
            _check_live_confirmation(parser, args)
            client = CoinbaseAdvancedTradeClient.from_env(live_mode=args.live and args.yes)
            result = client.place_market_order(
                args.product_id, base_size=args.size, side="SELL"
            )

        elif args.command == "feed":
            result = asyncio.run(collect_latest_prices(args.product_ids))

        else:  # signal
            client = CoinbaseAdvancedTradeClient.from_env(live_mode=False)
            candles = client.get_candles(
                args.product_id,
                granularity=args.granularity,
                limit=args.candles,
            )
            if not candles:
                print(
                    f"Error: No candle data returned for {args.product_id}",
                    file=sys.stderr,
                )
                return 1
            prices = [float(c["close"]) for c in candles]
            result = _compute_signal(args, prices)

    except (CoinbaseBotError, CoinbaseWebsocketError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
