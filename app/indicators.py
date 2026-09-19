"""Technical indicators computed locally from a weekly price series.

Standard formulas so results match data providers:
- SMA: simple mean of the last N closes.
- ATR: Wilder's Average True Range (the method Alpha Vantage / most charting
  tools use), seeded with the simple average of the first N true ranges.
"""
from typing import List, Optional


def sma(closes: List[float], period: int) -> Optional[float]:
    """Simple moving average of the last `period` closes; None if not enough data."""
    if period <= 0 or len(closes) < period:
        return None
    return sum(closes[-period:]) / period


def true_ranges(highs: List[float], lows: List[float], closes: List[float]) -> List[float]:
    """True range for each bar after the first (needs the prior close)."""
    trs = []
    for i in range(1, len(closes)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        trs.append(tr)
    return trs


def atr_wilder(highs: List[float], lows: List[float], closes: List[float],
               period: int = 14) -> Optional[float]:
    """Wilder's ATR over the whole series; None if not enough data.

    Seed = simple average of the first `period` true ranges, then
    ATR_t = (ATR_{t-1} * (period-1) + TR_t) / period.
    """
    if period <= 0 or len(closes) < period + 1:
        return None
    trs = true_ranges(highs, lows, closes)
    if len(trs) < period:
        return None
    atr = sum(trs[:period]) / period
    for tr in trs[period:]:
        atr = (atr * (period - 1) + tr) / period
    return atr
