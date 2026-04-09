from __future__ import annotations

import io
import sys
import unittest
from contextlib import redirect_stderr
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


if __name__ == "__main__":
    unittest.main()
