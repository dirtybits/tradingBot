from __future__ import annotations

import argparse
import asyncio
import json
import sys

from cbpro import CoinbaseAdvancedTradeClient, CoinbaseBotError, parse_positive_decimal
from webfeed import CoinbaseWebsocketError, collect_latest_prices


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Coinbase Advanced Trade bot")
    subparsers = parser.add_subparsers(dest="command", required=True)

    price_parser = subparsers.add_parser("price", help="Fetch current prices")
    price_parser.add_argument("symbols", nargs="+", help="Symbols such as BTC ETH")
    price_parser.add_argument("--quote", default="USD", help="Quote currency")

    balances_parser = subparsers.add_parser("balances", help="List account balances")
    balances_parser.add_argument(
        "--all",
        action="store_true",
        help="Include zero-balance accounts",
    )

    paper_buy_parser = subparsers.add_parser(
        "paper-buy",
        help="Build a market-buy order without sending it",
    )
    paper_buy_parser.add_argument("product_id", help="Product such as BTC-USD")
    paper_buy_parser.add_argument(
        "--funds",
        required=True,
        type=parse_positive_decimal,
        help="Quote funds to spend",
    )

    live_buy_parser = subparsers.add_parser(
        "live-buy",
        help="Submit a live market-buy order",
    )
    live_buy_parser.add_argument("product_id", help="Product such as BTC-USD")
    live_buy_parser.add_argument(
        "--funds",
        required=True,
        type=parse_positive_decimal,
        help="Quote funds to spend",
    )
    live_buy_parser.add_argument(
        "--confirm-live",
        action="store_true",
        help="Required to submit a live order",
    )

    feed_parser = subparsers.add_parser(
        "feed",
        help="Collect one ticker update per product from the websocket feed",
    )
    feed_parser.add_argument("product_ids", nargs="+", help="Products such as BTC-USD")

    return parser


def print_live_buy_summary(result: object) -> None:
    if not isinstance(result, dict):
        return

    order = result.get("order")
    if not isinstance(order, dict):
        return

    filled_size = order.get("filled_size")
    average_price = order.get("average_filled_price")
    success_response = result.get("success_response")
    response_product_id = (
        success_response.get("product_id")
        if isinstance(success_response, dict)
        else None
    )
    product_id = order.get("product_id") or response_product_id or "order"
    status = order.get("status")
    base_currency, _, quote_currency = str(product_id).partition("-")

    if filled_size and average_price:
        print(
            f"Bought {filled_size} {base_currency} at {average_price} {quote_currency} per {base_currency}.",
            file=sys.stderr,
        )
        return

    if status:
        print(
            f"Submitted {product_id} buy order; fill details are not available yet.",
            file=sys.stderr,
        )


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
        elif args.command == "paper-buy":
            client = CoinbaseAdvancedTradeClient.from_env(live_mode=False)
            result = client.place_market_order(args.product_id, funds=args.funds)
        elif args.command == "live-buy":
            if not args.confirm_live:
                parser.exit(
                    status=1,
                    message="Refusing to place a live order without --confirm-live\n",
                )
            client = CoinbaseAdvancedTradeClient.from_env(live_mode=True)
            result = client.place_market_order(args.product_id, funds=args.funds)
            print_live_buy_summary(result)
        else:
            result = asyncio.run(collect_latest_prices(args.product_ids))
    except (CoinbaseBotError, CoinbaseWebsocketError) as exc:
        parser.exit(status=1, message=f"{exc}\n")
    except Exception as exc:
        parser.exit(status=1, message=f"{exc}\n")

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
