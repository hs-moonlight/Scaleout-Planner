"""Core scale-out strategy math. Pure Python, no external dependencies.

Strategy: from an investment amount, entry price and stop-loss %, size the
position, place two R-multiple targets (default 1:1 and 2:1), sell half at
Target 1 and the rest at Target 2, and move the stop to breakeven after T1.
"""
from dataclasses import dataclass, asdict
import math


@dataclass
class TargetLeg:
    ratio: float          # reward-to-risk multiple (e.g. 1.0, 2.0)
    price: float          # target price
    gain_pct: float       # % gain from entry to this target
    shares: int           # shares sold at this target
    profit: float         # dollar profit realized on this leg
    r_multiple: float     # reward in R on this leg (== ratio)


@dataclass
class PlanResult:
    symbol: str
    investment: float
    entry: float
    stop_pct: float
    shares: int
    capital_deployed: float
    leftover_cash: float
    risk_per_share: float     # 1R per share
    stop_price: float
    total_risk: float         # max loss if stopped out (= 1.00R)
    breakeven_stop: float     # where the stop moves after Target 1
    t1: TargetLeg
    t2: TargetLeg
    total_profit: float       # realized if both targets fill
    blended_r: float
    gain_pct: float           # total_profit as % of capital deployed


def compute_plan(investment: float, entry: float, stop_pct: float,
                 symbol: str = "", t1_r: float = 1.0, t2_r: float = 2.0,
                 t1_sell_pct: float = 50.0) -> PlanResult:
    """Build the scale-out plan. `stop_pct` and `t1_sell_pct` are percents (6 == 6%)."""
    if entry <= 0:
        raise ValueError("entry price must be greater than 0")
    if investment < 0:
        raise ValueError("investment must be >= 0")

    s = stop_pct / 100.0
    shares = math.floor(investment / entry)          # round down; never exceed budget
    deployed = shares * entry
    leftover = investment - deployed

    risk_ps = entry * s                              # 1R per share
    stop_price = entry - risk_ps
    total_risk = risk_ps * shares

    t1_price = entry + t1_r * risk_ps
    t2_price = entry + t2_r * risk_ps
    t1_shares = round(shares * (t1_sell_pct / 100.0))
    t2_shares = max(0, shares - t1_shares)           # remainder sold at T2

    t1_profit = (t1_price - entry) * t1_shares
    t2_profit = (t2_price - entry) * t2_shares
    total_profit = t1_profit + t2_profit
    blended_r = (total_profit / total_risk) if total_risk > 0 else 0.0
    gain_pct = (total_profit / deployed * 100.0) if deployed > 0 else 0.0

    t1 = TargetLeg(t1_r, t1_price, t1_r * stop_pct, t1_shares, t1_profit, t1_r)
    t2 = TargetLeg(t2_r, t2_price, t2_r * stop_pct, t2_shares, t2_profit, t2_r)

    return PlanResult(
        symbol=symbol, investment=investment, entry=entry, stop_pct=stop_pct,
        shares=shares, capital_deployed=deployed, leftover_cash=leftover,
        risk_per_share=risk_ps, stop_price=stop_price, total_risk=total_risk,
        breakeven_stop=entry, t1=t1, t2=t2, total_profit=total_profit,
        blended_r=blended_r, gain_pct=gain_pct,
    )


@dataclass
class RealizedResult:
    realized_pnl: float
    r_multiple: float
    gain_pct: float
    open_shares: int
    status: str               # planned | t1_filled | closed | stopped


def compute_realized(entry: float, shares: int, stop_pct: float,
                     t1_filled: bool = False, t1_price: float = None, t1_shares: int = None,
                     t2_filled: bool = False, t2_price: float = None, t2_shares: int = None,
                     stopped: bool = False, stop_price: float = None, stop_shares: int = None
                     ) -> RealizedResult:
    """Realized performance from the actual fills recorded on a trade."""
    risk_ps = entry * (stop_pct / 100.0)
    total_risk = risk_ps * shares
    realized = 0.0
    sold = 0
    if t1_filled and t1_price and t1_shares:
        realized += (t1_price - entry) * t1_shares
        sold += t1_shares
    if t2_filled and t2_price and t2_shares:
        realized += (t2_price - entry) * t2_shares
        sold += t2_shares
    if stopped and stop_price and stop_shares:
        realized += (stop_price - entry) * stop_shares
        sold += stop_shares
    open_shares = max(0, shares - sold)
    r_mult = (realized / total_risk) if total_risk > 0 else 0.0
    gain = (realized / (entry * shares) * 100.0) if entry * shares > 0 else 0.0

    if stopped and open_shares == 0:
        status = "stopped"
    elif sold > 0 and open_shares == 0:
        status = "closed"
    elif t1_filled:
        status = "t1_filled"
    else:
        status = "planned"
    return RealizedResult(realized, r_mult, gain, open_shares, status)


def plan_to_dict(res: PlanResult) -> dict:
    return asdict(res)


def realized_to_dict(res: RealizedResult) -> dict:
    return asdict(res)
