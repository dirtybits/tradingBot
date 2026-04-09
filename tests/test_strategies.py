from __future__ import annotations

import unittest

from strategies import moving_average_crossover_signal, rsi_signal


class StrategyTests(unittest.TestCase):
    def test_moving_average_crossover_signal_buy(self) -> None:
        prices = [100, 101, 102, 103, 104, 105, 106, 107]

        signal = moving_average_crossover_signal(
            prices,
            short_window=3,
            long_window=5,
        )

        self.assertEqual(signal, "buy")

    def test_rsi_signal_sell(self) -> None:
        prices = [100, 102, 104, 106, 108, 110, 112, 114, 116, 118, 120, 122, 124, 126, 128]

        signal = rsi_signal(prices, period=14)

        self.assertEqual(signal, "sell")

    def test_rsi_signal_hold_for_flat_prices(self) -> None:
        prices = [100] * 15

        signal = rsi_signal(prices, period=14)

        self.assertEqual(signal, "hold")


if __name__ == "__main__":
    unittest.main()
