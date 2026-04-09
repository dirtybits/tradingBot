from __future__ import annotations

import io
import sys
import unittest
from contextlib import redirect_stderr
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


if __name__ == "__main__":
    unittest.main()
