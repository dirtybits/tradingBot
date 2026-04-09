from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncIterator, Iterable

import websockets


WS_URL = "wss://advanced-trade-ws.coinbase.com"


class CoinbaseWebsocketError(Exception):
    """Raised when the websocket feed cannot deliver the expected data."""


def _normalize_products(
    product_ids: Iterable[str],
    quote: str = "USD",
) -> list[str]:
    normalized = []
    for product_id in product_ids:
        normalized.append(product_id if "-" in product_id else f"{product_id}-{quote}")
    return normalized


def extract_ticker_updates(message: dict[str, Any]) -> list[dict[str, str]]:
    """Extract ticker rows from an Advanced Trade websocket message."""
    if message.get("channel") != "ticker":
        return []

    updates: list[dict[str, str]] = []
    for event in message.get("events", []):
        for ticker in event.get("tickers", []):
            updates.append(
                {
                    "product_id": ticker["product_id"],
                    "price": ticker["price"],
                    "time": message.get("timestamp", ""),
                }
            )
    return updates


async def stream_ticker_messages(
    product_ids: Iterable[str],
    *,
    timeout_seconds: float = 15.0,
) -> AsyncIterator[dict[str, Any]]:
    """Yield ticker updates from the Advanced Trade websocket feed."""
    subscribed_products = _normalize_products(product_ids)
    subscription = {
        "type": "subscribe",
        "channel": "ticker",
        "product_ids": subscribed_products,
    }
    heartbeat_subscription = {
        "type": "subscribe",
        "channel": "heartbeats",
    }

    async with websockets.connect(
        WS_URL,
        open_timeout=timeout_seconds,
        close_timeout=5,
        ping_interval=20,
        ping_timeout=20,
    ) as websocket:
        await websocket.send(json.dumps(subscription))
        await websocket.send(json.dumps(heartbeat_subscription))
        while True:
            try:
                raw_message = await asyncio.wait_for(
                    websocket.recv(),
                    timeout=timeout_seconds,
                )
                message = json.loads(raw_message)
            except json.JSONDecodeError as exc:
                raise CoinbaseWebsocketError(
                    "Received invalid JSON from Advanced Trade websocket."
                ) from exc
            if message.get("type") == "error":
                raise CoinbaseWebsocketError(
                    message.get("message", "Coinbase websocket returned an error.")
                )
            for update in extract_ticker_updates(message):
                yield update


async def collect_latest_prices(
    product_ids: Iterable[str],
    *,
    timeout_seconds: float = 15.0,
) -> dict[str, float | str]:
    """Collect one fresh ticker price per requested product."""
    subscribed_products = _normalize_products(product_ids)
    remaining_products = set(subscribed_products)
    latest_prices: dict[str, float | str] = {}
    last_time = None

    try:
        deadline = asyncio.get_running_loop().time() + timeout_seconds
        async for message in stream_ticker_messages(
            subscribed_products,
            timeout_seconds=timeout_seconds,
        ):
            product_id = message["product_id"]
            latest_prices[product_id] = float(message["price"])
            last_time = message.get("time", last_time) or last_time
            remaining_products.discard(product_id)
            if not remaining_products:
                break
            if asyncio.get_running_loop().time() >= deadline:
                raise TimeoutError
    except TimeoutError as exc:
        missing_products = ", ".join(sorted(remaining_products))
        raise CoinbaseWebsocketError(
            f"Timed out waiting for ticker updates: {missing_products}"
        ) from exc

    if last_time is not None:
        latest_prices["time"] = last_time
    return latest_prices

