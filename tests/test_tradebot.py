from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from unittest.mock import patch

from tradebot import main


class BotCliTests(unittest.TestCase):
    def test_live_buy_requires_yes_flag(self) -> None:
        """bot buy --live without --yes must exit 1 and mention --yes."""
        stderr = io.StringIO()
        with patch.object(sys, "argv", ["tradebot", "buy", "BTC-USD", "--funds", "10", "--live"]):
            with redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as exc:
                    main()

        self.assertEqual(exc.exception.code, 1)
        self.assertIn("--yes", stderr.getvalue())

    def test_live_sell_requires_yes_flag(self) -> None:
        """bot sell --live without --yes must exit 1 and mention --yes."""
        stderr = io.StringIO()
        with patch.object(sys, "argv", ["tradebot", "sell", "BTC-USD", "--size", "0.001", "--live"]):
            with redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as exc:
                    main()

        self.assertEqual(exc.exception.code, 1)
        self.assertIn("--yes", stderr.getvalue())

    def test_buy_requires_funds(self) -> None:
        """bot buy without --funds must exit non-zero."""
        with patch.object(sys, "argv", ["tradebot", "buy", "BTC-USD"]):
            with self.assertRaises(SystemExit) as exc:
                main()
        self.assertNotEqual(exc.exception.code, 0)

    def test_sell_requires_size(self) -> None:
        """bot sell without --size must exit non-zero."""
        with patch.object(sys, "argv", ["tradebot", "sell", "BTC-USD"]):
            with self.assertRaises(SystemExit) as exc:
                main()
        self.assertNotEqual(exc.exception.code, 0)


    @patch("tradebot.CoinbaseAdvancedTradeClient.from_env")
    def test_live_buy_prints_fill_summary(self, from_env) -> None:
        """A filled live buy prints a human-readable summary to stderr."""
        from_env.return_value.place_market_order.return_value = {
            "success": True,
            "success_response": {"order_id": "order-123", "product_id": "BTC-USD"},
            "order": {"filled_size": "0.001", "average_filled_price": "65000.12", "side": "BUY"},
        }
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(sys, "argv", ["tradebot", "buy", "BTC-USD", "--funds", "10", "--live", "--yes"]):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                rc = main()

        self.assertEqual(rc, 0)
        self.assertIn("Bought 0.001 BTC at 65000.12 USD per BTC.", stderr.getvalue())
        self.assertEqual(json.loads(stdout.getvalue())["success"], True)

    @patch("tradebot.CoinbaseAdvancedTradeClient.from_env")
    def test_live_buy_reports_pending_when_fill_missing(self, from_env) -> None:
        """A pending live buy prints a fallback message to stderr."""
        from_env.return_value.place_market_order.return_value = {
            "success": True,
            "success_response": {"order_id": "order-123", "product_id": "BTC-USD"},
            "order": {"status": "PENDING", "side": "BUY"},
        }
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(sys, "argv", ["tradebot", "buy", "BTC-USD", "--funds", "10", "--live", "--yes"]):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                rc = main()

        self.assertEqual(rc, 0)
        self.assertIn("Submitted BTC-USD buy order; fill details are not available yet.", stderr.getvalue())

    @patch("tradebot.CoinbaseAdvancedTradeClient.from_env")
    def test_live_sell_prints_fill_summary(self, from_env) -> None:
        """A filled live sell prints a human-readable summary to stderr."""
        from_env.return_value.place_market_order.return_value = {
            "success": True,
            "success_response": {"order_id": "order-456", "product_id": "BTC-USD"},
            "order": {"filled_size": "0.001", "average_filled_price": "65000.12", "side": "SELL"},
        }
        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(sys, "argv", ["tradebot", "sell", "BTC-USD", "--size", "0.001", "--live", "--yes"]):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                rc = main()

        self.assertEqual(rc, 0)
        self.assertIn("Sold 0.001 BTC at 65000.12 USD per BTC.", stderr.getvalue())


class LimitOrderCliTests(unittest.TestCase):
    def test_limit_buy_requires_yes_flag(self) -> None:
        stderr = io.StringIO()
        with patch.object(
            sys, "argv",
            ["tradebot", "limit-buy", "BTC-USD", "--funds", "10", "--live"],
        ):
            with redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as exc:
                    main()

        self.assertEqual(exc.exception.code, 1)
        self.assertIn("--yes", stderr.getvalue())

    def test_limit_sell_requires_yes_flag(self) -> None:
        stderr = io.StringIO()
        with patch.object(
            sys, "argv",
            ["tradebot", "limit-sell", "BTC-USD", "--size", "0.001", "--live"],
        ):
            with redirect_stderr(stderr):
                with self.assertRaises(SystemExit) as exc:
                    main()

        self.assertEqual(exc.exception.code, 1)
        self.assertIn("--yes", stderr.getvalue())

    @patch("tradebot.CoinbaseAdvancedTradeClient.from_env")
    def test_limit_buy_paper_mode_includes_reference_price(self, from_env) -> None:
        """Paper limit-buy adds reference_price to the JSON output."""
        from_env.return_value.check_prices.return_value = {"BTC": 95000.0}
        from_env.return_value.place_limit_order.return_value = {
            "dry_run": True,
            "payload": {
                "side": "BUY",
                "order_configuration": {
                    "limit_limit_gtc": {
                        "limit_price": "94715.00",
                        "base_size": "0.00105584",
                        "post_only": False,
                    }
                },
            },
        }

        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(
            sys, "argv",
            ["tradebot", "limit-buy", "BTC-USD", "--funds", "100"],
        ):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                rc = main()

        self.assertEqual(rc, 0)
        output = json.loads(stdout.getvalue())
        self.assertTrue(output["dry_run"])
        self.assertEqual(output["reference_price"], 95000.0)

    @patch("tradebot.CoinbaseAdvancedTradeClient.from_env")
    def test_live_limit_buy_prints_open_status(self, from_env) -> None:
        """A live limit buy that lands as OPEN prints a waiting message."""
        from_env.return_value.check_prices.return_value = {"BTC": 95000.0}
        from_env.return_value.place_limit_order.return_value = {
            "success": True,
            "success_response": {"order_id": "limit-1", "product_id": "BTC-USD"},
            "order": {
                "status": "OPEN",
                "side": "BUY",
                "product_id": "BTC-USD",
                "order_type": "LIMIT",
                "order_configuration": {
                    "limit_limit_gtc": {
                        "limit_price": "94715.00",
                        "post_only": True,
                    }
                },
            },
        }

        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(
            sys, "argv",
            ["tradebot", "limit-buy", "BTC-USD", "--funds", "100", "--post-only", "--live", "--yes"],
        ):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                rc = main()

        self.assertEqual(rc, 0)
        err = stderr.getvalue()
        self.assertIn("94715.00", err)
        self.assertIn("post-only", err)
        self.assertIn("Waiting to fill", err)

    @patch("tradebot.CoinbaseAdvancedTradeClient.from_env")
    def test_limit_sell_paper_mode_includes_reference_price(self, from_env) -> None:
        """Paper limit-sell adds reference_price to the JSON output."""
        from_env.return_value.check_prices.return_value = {"BTC": 95000.0}
        from_env.return_value.place_limit_order.return_value = {
            "dry_run": True,
            "payload": {
                "side": "SELL",
                "order_configuration": {
                    "limit_limit_gtc": {
                        "limit_price": "95285.00",
                        "base_size": "0.00100000",
                        "post_only": False,
                    }
                },
            },
        }

        stdout, stderr = io.StringIO(), io.StringIO()
        with patch.object(
            sys, "argv",
            ["tradebot", "limit-sell", "BTC-USD", "--size", "0.001"],
        ):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                rc = main()

        self.assertEqual(rc, 0)
        output = json.loads(stdout.getvalue())
        self.assertTrue(output["dry_run"])
        self.assertEqual(output["reference_price"], 95000.0)


if __name__ == "__main__":
    unittest.main()
