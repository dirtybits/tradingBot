from __future__ import annotations

from statistics import mean
from typing import Literal, Sequence


Signal = Literal["buy", "sell", "hold"]


def _validate_prices(prices: Sequence[float], minimum_length: int) -> None:
    if len(prices) < minimum_length:
        raise ValueError(
            f"Need at least {minimum_length} prices, received {len(prices)}."
        )


def simple_moving_average(prices: Sequence[float], window: int) -> float:
    """Return the latest simple moving average."""
    if window <= 0:
        raise ValueError("window must be positive")
    _validate_prices(prices, window)
    return mean(prices[-window:])


def latest_relative_strength_index(
    prices: Sequence[float],
    period: int = 14,
) -> float:
    """Calculate a basic RSI value from the latest `period` price changes."""
    if period <= 0:
        raise ValueError("period must be positive")
    _validate_prices(prices, period + 1)

    gains = []
    losses = []
    for previous_price, current_price in zip(prices[-(period + 1) : -1], prices[-period:]):
        change = current_price - previous_price
        gains.append(max(change, 0))
        losses.append(abs(min(change, 0)))

    average_gain = mean(gains)
    average_loss = mean(losses)
    if average_gain == 0 and average_loss == 0:
        return 50.0
    if average_loss == 0:
        return 100.0
    if average_gain == 0:
        return 0.0
    relative_strength = average_gain / average_loss
    return 100 - (100 / (1 + relative_strength))


def moving_average_crossover_signal(
    prices: Sequence[float],
    short_window: int = 5,
    long_window: int = 20,
) -> Signal:
    """Generate a signal from the latest short/long moving averages."""
    if short_window >= long_window:
        raise ValueError("short_window must be smaller than long_window")

    short_average = simple_moving_average(prices, short_window)
    long_average = simple_moving_average(prices, long_window)
    if short_average > long_average:
        return "buy"
    if short_average < long_average:
        return "sell"
    return "hold"


def rsi_signal(
    prices: Sequence[float],
    *,
    period: int = 14,
    oversold: float = 30,
    overbought: float = 70,
) -> Signal:
    """Generate a signal from the latest RSI reading."""
    rsi_value = latest_relative_strength_index(prices, period=period)
    if rsi_value <= oversold:
        return "buy"
    if rsi_value >= overbought:
        return "sell"
    return "hold"