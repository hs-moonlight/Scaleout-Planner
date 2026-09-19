"""Fair-entry zone from technical signals (Step 2).

Builds a suggested entry *zone* (not a single price) from a trend anchor
(40-week / ~200-day SMA), a faster average (50-day / 10-week), the weekly ATR
volatility buffer, and flags — including the key check of whether the stop is
tighter than one ATR of normal noise. Not a hard buy signal; the user still
enters their real fill.
"""
from dataclasses import dataclass, asdict, field
from typing import Optional, List


@dataclass
class FairEntry:
    symbol: str
    price: float
    trend_anchor: float          # 40-week / ~200-day SMA
    fast_ma: Optional[float]     # 50-day / 10-week SMA
    atr_weekly: Optional[float]
    zone_low: float
    zone_high: float
    ideal_entry: float
    trend_rising: Optional[bool]
    extended_above_zone: bool
    stop_pct: float
    stop_distance: float
    stop_inside_atr: Optional[bool]
    notes: List[str] = field(default_factory=list)


def build_fair_entry(symbol: str, price: float, trend_anchor: float,
                     fast_ma: Optional[float], atr_weekly: Optional[float],
                     stop_pct: float, trend_anchor_prev: Optional[float] = None) -> FairEntry:
    # The pullback band runs between the faster MA and the trend anchor.
    highs = [v for v in (trend_anchor, fast_ma) if v]
    zone_low = min(highs) if highs else trend_anchor
    zone_high = max(highs) if highs else trend_anchor
    ideal_entry = zone_low + 0.5 * (zone_high - zone_low)

    trend_rising = None
    if trend_anchor_prev is not None:
        trend_rising = trend_anchor > trend_anchor_prev

    extended = price > zone_high
    stop_distance = price * (stop_pct / 100.0)
    stop_inside_atr = (stop_distance < atr_weekly) if atr_weekly else None

    notes: List[str] = []
    if extended:
        notes.append(
            f"Price {price:.2f} is above the fair-entry zone "
            f"({zone_low:.2f}-{zone_high:.2f}); consider waiting for a pullback."
        )
    else:
        notes.append(
            f"Price {price:.2f} is within/below the fair-entry zone "
            f"({zone_low:.2f}-{zone_high:.2f})."
        )
    if stop_inside_atr:
        notes.append(
            f"A {stop_pct:.1f}% stop (${stop_distance:.2f}) is tighter than one weekly "
            f"ATR (${atr_weekly:.2f}) - prone to noise stop-outs; consider a wider stop "
            f"or waiting for lower volatility."
        )
    if trend_rising is False:
        notes.append("40-week trend is not rising - caution for a long position.")

    return FairEntry(
        symbol=symbol, price=price, trend_anchor=trend_anchor, fast_ma=fast_ma,
        atr_weekly=atr_weekly, zone_low=zone_low, zone_high=zone_high,
        ideal_entry=ideal_entry, trend_rising=trend_rising,
        extended_above_zone=extended, stop_pct=stop_pct, stop_distance=stop_distance,
        stop_inside_atr=stop_inside_atr, notes=notes,
    )


def fair_entry_to_dict(fe: FairEntry) -> dict:
    return asdict(fe)
