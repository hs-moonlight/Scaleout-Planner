"""Pydantic request models and the SQLModel Trade table."""
from typing import Optional
from datetime import datetime
from pydantic import BaseModel
from sqlmodel import SQLModel, Field


class PlanInput(BaseModel):
    """Input to the /plan calculator."""
    symbol: str = ""
    investment: float
    entry: float
    stop_pct: float = 6.0
    t1_r: float = 1.0
    t2_r: float = 2.0
    t1_sell_pct: float = 50.0


class Trade(SQLModel, table=True):
    """A saved trade: the plan plus the actual fills, for updates and lookbacks.

    `user_id` is a stable INTERNAL id (default "local" in Step 2). Step 3 maps it
    to the auth provider's subject claim, so the identity provider can change
    without touching trade rows (the provider-agnostic guardrail).
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: str = Field(default="local", index=True)
    name: str = ""
    symbol: str = ""

    # --- plan ---
    investment: float
    entry: float
    stop_pct: float = 6.0
    t1_r: float = 1.0
    t2_r: float = 2.0
    t1_sell_pct: float = 50.0
    order_type: str = "market"        # market | limit
    limit_offset: float = 0.0

    # --- actual fills ---
    actual_entry: Optional[float] = None
    actual_shares: Optional[int] = None
    t1_filled: bool = False
    t1_fill_price: Optional[float] = None
    t1_fill_shares: Optional[int] = None
    t2_filled: bool = False
    t2_fill_price: Optional[float] = None
    t2_fill_shares: Optional[int] = None
    stopped_out: bool = False
    stop_fill_price: Optional[float] = None
    stop_fill_shares: Optional[int] = None

    status: str = "planned"           # planned | t1_filled | closed | stopped
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class TradeCreate(BaseModel):
    name: str = ""
    symbol: str = ""
    investment: float
    entry: float
    stop_pct: float = 6.0
    t1_r: float = 1.0
    t2_r: float = 2.0
    t1_sell_pct: float = 50.0
    order_type: str = "market"
    limit_offset: float = 0.0


class TradeUpdate(BaseModel):
    """All optional: send only the fields being changed (e.g. recording fills)."""
    name: Optional[str] = None
    symbol: Optional[str] = None
    investment: Optional[float] = None
    entry: Optional[float] = None
    stop_pct: Optional[float] = None
    t1_r: Optional[float] = None
    t2_r: Optional[float] = None
    t1_sell_pct: Optional[float] = None
    order_type: Optional[str] = None
    limit_offset: Optional[float] = None
    actual_entry: Optional[float] = None
    actual_shares: Optional[int] = None
    t1_filled: Optional[bool] = None
    t1_fill_price: Optional[float] = None
    t1_fill_shares: Optional[int] = None
    t2_filled: Optional[bool] = None
    t2_fill_price: Optional[float] = None
    t2_fill_shares: Optional[int] = None
    stopped_out: Optional[bool] = None
    stop_fill_price: Optional[float] = None
    stop_fill_shares: Optional[int] = None
    status: Optional[str] = None
