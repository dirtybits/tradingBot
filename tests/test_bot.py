from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from bot import main


class BotCliTests(unittest.TestCase):
    def test_live_buy_requires_confirm_flag(self) -> None:
        stderr = io.StringIO()
        with patch.object(
            sys,
            "argv",
            ["bot.py", "live-buy", "BTC-USD", "--funds", "10"],
        ):
            with redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as exc:
                    main()

        self.assertEqual(exc.exception.code, 1)
        self.assertIn("--confirm-live", stderr.getvalue())

    @patch("bot.CoinbaseAdvancedTradeClient.from_env")
    def test_live_buy_prints_fill_summary_and_json(self, from_env) -> None:
        client = from_env.return_value
        client.place_market_order.return_value = {
            "success": True,
            "success_response": {
                "order_id": "order-123",
                "product_id": "BTC-USD",
            },
            "order": {
                "filled_size": "0.001",
                "average_filled_price": "65000.12",
            },
        }
        stdout = io.StringIO()
        stderr = io.StringIO()

        with patch.object(
            sys,
            "argv",
            ["bot.py", "live-buy", "BTC-USD", "--funds", "10", "--confirm-live"],
        ):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = main()

        self.assertEqual(result, 0)
        self.assertIn(
            "Bought 0.001 BTC at 65000.12 USD per BTC.",
            stderr.getvalue(),
        )
        self.assertEqual(
            json.loads(stdout.getvalue()),
            client.place_market_order.return_value,
        )

    @patch("bot.CoinbaseAdvancedTradeClient.from_env")
    def test_live_buy_reports_pending_fill_when_details_missing(self, from_env) -> None:
        client = from_env.return_value
        client.place_market_order.return_value = {
            "success": True,
            "success_response": {
                "order_id": "order-123",
                "product_id": "BTC-USD",
            },
            "order": {
                "status": "PENDING",
            },
        }
        stdout = io.StringIO()
        stderr = io.StringIO()

        with patch.object(
            sys,
            "argv",
            ["bot.py", "live-buy", "BTC-USD", "--funds", "10", "--confirm-live"],
        ):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                result = main()

        self.assertEqual(result, 0)
        self.assertIn(
            "Submitted BTC-USD buy order; fill details are not available yet.",
            stderr.getvalue(),
        )
        self.assertEqual(
            json.loads(stdout.getvalue()),
            client.place_market_order.return_value,
        )


if __name__ == "__main__":
    unittest.main()
