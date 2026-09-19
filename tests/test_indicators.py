"""Deterministic, hand-verified tests for the local indicator math."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app import indicators


def test_sma_basic():
    assert indicators.sma([1, 2, 3, 4, 5], 3) == 4.0        # (3+4+5)/3
    assert indicators.sma([9, 10, 11, 12], 2) == 11.5
    assert indicators.sma([9, 10, 11], 2) == 10.5           # previous-week window
    assert indicators.sma([1, 2], 5) is None                # not enough data


def test_atr_wilder_hand_computed():
    # highs/lows/closes chosen so ATR(period=2) works out to exactly 2.5:
    #   TRs (from bar 1) = [2, 2, 3]; seed=mean(2,2)=2; then (2*1+3)/2=2.5
    highs = [10, 11, 12, 13]
    lows = [8, 9, 10, 10]
    closes = [9, 10, 11, 12]
    assert round(indicators.atr_wilder(highs, lows, closes, 2), 6) == 2.5
    assert indicators.atr_wilder([1], [1], [1], 14) is None  # not enough data


def test_trend_direction():
    closes = [9, 10, 11, 12]
    now = indicators.sma(closes, 2)            # 11.5
    prev = indicators.sma(closes[:-1], 2)      # 10.5
    assert now > prev                          # rising


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\nAll {len(fns)} indicator tests passed.")
