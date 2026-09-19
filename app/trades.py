"""CRUD for saved trades, plus a realized-performance view and simple stats."""
from datetime import datetime
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from .database import get_session
from .models import Trade, TradeCreate, TradeUpdate
from . import scaleout

router = APIRouter(prefix="/trades", tags=["trades"])

# Step 2: single local user. Step 3 replaces this with the authenticated user's
# internal id derived from the token's subject claim.
CURRENT_USER = "local"


@router.post("", response_model=Trade)
def create_trade(payload: TradeCreate, session: Session = Depends(get_session)) -> Trade:
    trade = Trade(user_id=CURRENT_USER, **payload.model_dump())
    session.add(trade)
    session.commit()
    session.refresh(trade)
    return trade


@router.get("", response_model=List[Trade])
def list_trades(session: Session = Depends(get_session)) -> List[Trade]:
    stmt = select(Trade).where(Trade.user_id == CURRENT_USER).order_by(Trade.updated_at.desc())
    return list(session.exec(stmt).all())


@router.get("/stats")
def trade_stats(session: Session = Depends(get_session)) -> dict:
    """Foundation for the Step 4 journal: win rate + total realized R on closed trades."""
    stmt = select(Trade).where(Trade.user_id == CURRENT_USER)
    trades = list(session.exec(stmt).all())
    closed = [t for t in trades if t.status in ("closed", "stopped")]
    total_r = 0.0
    wins = 0
    for t in closed:
        r = _realized(t)
        total_r += r.r_multiple
        if r.realized_pnl > 0:
            wins += 1
    n = len(closed)
    return {
        "trades_total": len(trades),
        "trades_closed": n,
        "win_rate": (wins / n) if n else 0.0,
        "total_realized_r": total_r,
        "avg_realized_r": (total_r / n) if n else 0.0,
    }


@router.get("/{trade_id}", response_model=Trade)
def get_trade(trade_id: int, session: Session = Depends(get_session)) -> Trade:
    trade = _owned(session, trade_id)
    return trade


@router.get("/{trade_id}/realized")
def get_realized(trade_id: int, session: Session = Depends(get_session)) -> dict:
    """Realized P&L / R / % from the actual fills recorded on this trade."""
    t = _owned(session, trade_id)
    return scaleout.realized_to_dict(_realized(t))


@router.put("/{trade_id}", response_model=Trade)
def update_trade(trade_id: int, payload: TradeUpdate, session: Session = Depends(get_session)) -> Trade:
    trade = _owned(session, trade_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(trade, key, value)
    # Recompute status from the (possibly updated) fills unless caller set it.
    if "status" not in payload.model_dump(exclude_unset=True):
        trade.status = _realized(trade).status
    trade.updated_at = datetime.utcnow()
    session.add(trade)
    session.commit()
    session.refresh(trade)
    return trade


@router.delete("/{trade_id}")
def delete_trade(trade_id: int, session: Session = Depends(get_session)) -> dict:
    trade = _owned(session, trade_id)
    session.delete(trade)
    session.commit()
    return {"ok": True, "deleted": trade_id}


def _owned(session: Session, trade_id: int) -> Trade:
    trade = session.get(Trade, trade_id)
    if not trade or trade.user_id != CURRENT_USER:
        raise HTTPException(status_code=404, detail="Trade not found")
    return trade


def _realized(t: Trade) -> "scaleout.RealizedResult":
    entry = t.actual_entry if t.actual_entry else t.entry
    shares = t.actual_shares if t.actual_shares is not None else 0
    return scaleout.compute_realized(
        entry=entry, shares=shares, stop_pct=t.stop_pct,
        t1_filled=t.t1_filled, t1_price=t.t1_fill_price, t1_shares=t.t1_fill_shares,
        t2_filled=t.t2_filled, t2_price=t.t2_fill_price, t2_shares=t.t2_fill_shares,
        stopped=t.stopped_out, stop_price=t.stop_fill_price, stop_shares=t.stop_fill_shares,
    )
