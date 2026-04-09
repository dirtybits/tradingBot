from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

from webfeed import (
    CoinbaseWebsocketError,
    collect_latest_prices,
    extract_ticker_updates,
)


class WebFeedTests(unittest.IsolatedAsyncioTestCase):
    def test_extract_ticker_updates_handles_advanced_trade_message(self) -> None:
        updates = extract_ticker_updates(
            {
                "channel": "ticker",
                "timestamp": "2026-01-01T00:00:00Z",
                "events": [
                    {
                        "type": "snapshot",
                        "tickers": [
                            {
                                "product_id": "BTC-USD",
                                "price": "70000.00",
                            }
                        ],
                    }
                ],
            }
        )

        self.assertEqual(
            updates,
            [
                {
                    "product_id": "BTC-USD",
                    "price": "70000.00",
                    "time": "2026-01-01T00:00:00Z",
                }
            ],
        )

    async def test_collect_latest_prices_returns_requested_products(self) -> None:
        async def fake_stream(_product_ids, *, timeout_seconds):
            yield {
                "product_id": "BTC-USD",
                "price": "70000.00",
                "time": "2026-01-01T00:00:00Z",
            }
            yield {
                "product_id": "ETH-USD",
                "price": "2000.00",
                "time": "2026-01-01T00:00:01Z",
            }

        with patch("webfeed.stream_ticker_messages", new=fake_stream):
            result = await collect_latest_prices(["BTC-USD", "ETH-USD"])

        self.assertEqual(result["BTC-USD"], 70000.0)
        self.assertEqual(result["ETH-USD"], 2000.0)

    async def test_collect_latest_prices_times_out_when_product_is_missing(self) -> None:
        async def fake_stream(_product_ids, *, timeout_seconds):
            while True:
                yield {
                    "product_id": "BTC-USD",
                    "price": "70000.00",
                    "time": "2026-01-01T00:00:00Z",
                }
                await asyncio.sleep(0)

        with patch("webfeed.stream_ticker_messages", new=fake_stream):
            with self.assertRaises(CoinbaseWebsocketError):
                await collect_latest_prices(
                    ["BTC-USD", "ETH-USD"],
                    timeout_seconds=0.01,
                )


if __name__ == "__main__":
    unittest.main()
