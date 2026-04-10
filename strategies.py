from __future__ import annotations

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
    window_prices = prices[-window:]
    return sum(window_prices) / window


def latest_relative_strength_index(
    prices: Sequence[float],
    period: int = 14,
) -> float:
    """Calculate RSI using Wilder's EMA smoothing over all available prices.

    Seeds the EMA with a simple average of the first ``period`` changes, then
    applies Wilder's smoothed moving average for every subsequent change.  This
    matches the calculation used by most charting platforms and produces values
    that agree with TradingView / standard TA libraries.
    """
    if period <= 0:
        raise ValueError("period must be positive")
    _validate_prices(prices, period + 1)

    changes = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    gains = [max(c, 0.0) for c in changes]
    losses = [abs(min(c, 0.0)) for c in changes]

    # Seed: simple average of the first `period` changes
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    # Wilder's smoothed EMA for all remaining changes
    for i in range(period, len(changes)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period

    if avg_gain == 0 and avg_loss == 0:
        return 50.0
    if avg_loss == 0:
        return 100.0
    if avg_gain == 0:
        return 0.0
    return 100 - (100 / (1 + avg_gain / avg_loss))


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


def trend_rsi_signal(
    prices: Sequence[float],
    *,
    period: int = 14,
    oversold: float = 30,
    overbought: float = 70,
    trend_window: int = 20,
) -> Signal:
    """RSI signal gated by a trend SMA filter.

    Reduces false signals in strongly trending markets by only acting when the
    RSI reading agrees with the prevailing trend:

    - ``buy``  only when RSI <= oversold  AND price is above the trend SMA
    - ``sell`` only when RSI >= overbought AND price is below the trend SMA
    - ``hold`` in all other cases (including RSI extremes that contradict trend)

    ``trend_window`` controls the SMA period.  The ``prices`` slice must contain
    at least ``trend_window`` values, so pass ``--candles`` > ``--trend-window``
    when using this strategy from the CLI.
    """
    rsi_value = latest_relative_strength_index(prices, period=period)
    trend_ma = simple_moving_average(prices, trend_window)
    current_price = prices[-1]

    if rsi_value <= oversold and current_price > trend_ma:
        return "buy"
    if rsi_value >= overbought and current_price < trend_ma:
        return "sell"
    return "hold"