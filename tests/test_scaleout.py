"""Unit tests for the pure scale-out math (no external dependencies).

Runnable two ways:
  pytest
  python3 tests/test_scaleout.py    # stdlib-only fallback
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import scaleout


def test_worked_example():
    """$18,000 at $180 entry, 6% stop -> the canonical plan."""
    r = scaleout.compute_plan(investment=18000, entry=180, stop_pct=6)
    assert r.shares == 100
    assert round(r.stop_price, 2) == 169.20
    assert round(r.risk_per_share, 2) == 10.80
    assert round(r.total_risk, 2) == 1080.00
    assert round(r.t1.price, 2) == 190.80
    assert round(r.t2.price, 2) == 201.60
    assert r.t1.shares == 50 and r.t2.shares == 50
    assert round(r.t1.profit, 2) == 540.00
    assert round(r.t2.profit, 2) == 1080.00
    assert round(r.total_profit, 2) == 1620.00
    assert round(r.blended_r, 2) == 1.50
    assert round(r.gain_pct, 1) == 9.0
    assert r.breakeven_stop == 180


def test_round_down_shares_and_leftover():
    r = scaleout.compute_plan(investment=1000, entry=180, stop_pct=6)
    assert r.shares == 5                       # floor(1000/180)
    assert round(r.capital_deployed, 2) == 900.00
    assert round(r.leftover_cash, 2) == 100.00


def test_odd_shares_split():
    r = scaleout.compute_plan(investment=180 * 55, entry=180, stop_pct=6)
    assert r.shares == 55
    assert r.t1.shares == 28 and r.t2.shares == 27   # T1 sells the larger half


def test_custom_ratios():
    r = scaleout.compute_plan(investment=10000, entry=100, stop_pct=5, t1_r=1.5, t2_r=3)
    assert round(r.t1.price, 2) == 107.50            # 100 + 1.5 * (100*0.05)
    assert round(r.t2.price, 2) == 115.00            # 100 + 3 * 5


def test_realized_partial_then_breakeven():
    """T1 filled, rest stopped at breakeven -> only the T1 gain is realized."""
    rr = scaleout.compute_realized(
        entry=180, shares=100, stop_pct=6,
        t1_filled=True, t1_price=190.80, t1_shares=50,
        stopped=True, stop_price=180, stop_shares=50,
    )
    assert round(rr.realized_pnl, 2) == 540.00
    assert rr.open_shares == 0
    assert rr.status == "stopped"


def test_invalid_entry():
    try:
        scaleout.compute_plan(investment=1000, entry=0, stop_pct=6)
    except ValueError:
        return
    raise AssertionError("expected ValueError for entry <= 0")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for fn in fns:
        fn()
        print(f"ok  {fn.__name__}")
    print(f"\nAll {len(fns)} tests passed.")
