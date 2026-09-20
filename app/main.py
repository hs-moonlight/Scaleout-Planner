"""Scale-Out Planner API (Step 2).

Endpoints:
  GET  /health              - liveness
  POST /plan                - scale-out math (no network)
  GET  /quote/{symbol}      - live price + 50/200-day averages (FMP)
  GET  /analyst/{symbol}    - analyst consensus + price targets (FMP)
  GET  /suggest/{symbol}    - fair-entry zone + flags + analyst overlay
  /trades ...               - save / update / review trades (SQLite)
"""
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .config import settings
from .database import init_db
from .models import PlanInput
from .suggest import build_fair_entry, fair_entry_to_dict
from .trades import router as trades_router
from . import scaleout, market_data, indicators
from .auth import current_user, current_user_name


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="Scale-Out Planner API", version="0.2.0", lifespan=lifespan)

origins = ["*"] if settings.cors_origins.strip() == "*" else \
    [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware, allow_origins=origins, allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

app.include_router(trades_router)

_STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")


@app.get("/", include_in_schema=False)
def index():
    """Serve the single-page front end (same origin as the API)."""
    return FileResponse(os.path.join(_STATIC_DIR, "index.html"))


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/me")
def me(request: Request) -> dict:
    """Who is signed in (from Easy Auth); 'local' when running without auth."""
    return {"user_id": current_user(request), "name": current_user_name(request)}


@app.post("/plan")
def plan(inp: PlanInput) -> dict:
    try:
        res = scaleout.compute_plan(
            investment=inp.investment, entry=inp.entry, stop_pct=inp.stop_pct,
            symbol=inp.symbol, t1_r=inp.t1_r, t2_r=inp.t2_r, t1_sell_pct=inp.t1_sell_pct,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return scaleout.plan_to_dict(res)


@app.get("/quote/{symbol}")
async def quote(symbol: str) -> dict:
    try:
        return await market_data.get_quote(symbol.upper())
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"quote failed: {e}")


@app.get("/analyst/{symbol}")
async def analyst(symbol: str) -> dict:
    try:
        return await market_data.get_analyst(symbol.upper())
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"analyst failed: {e}")


@app.get("/suggest/{symbol}")
async def suggest(symbol: str, stop_pct: float | None = None, debug: bool = False) -> dict:
    symbol = symbol.upper()
    stop_pct = stop_pct if stop_pct is not None else settings.default_stop_pct
    try:
        q = await market_data.get_quote(symbol)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"quote failed: {e}")

    # ONE Alpha Vantage call -> compute 40-week SMA (this week + last) and ATR locally.
    series = await market_data.get_weekly_series(symbol)
    atr = sma40 = sma40_prev = None
    if series:
        closes = [b["close"] for b in series]
        highs = [b["high"] for b in series]
        lows = [b["low"] for b in series]
        sma40 = indicators.sma(closes, 40)
        sma40_prev = indicators.sma(closes[:-1], 40)
        atr = indicators.atr_wilder(highs, lows, closes, 14)

    anchor = sma40 if sma40 else q.get("sma200")
    if anchor is None:
        raise HTTPException(status_code=502, detail="No trend anchor (40-week/200-day SMA) available")

    fe = build_fair_entry(
        symbol=symbol, price=q["price"], trend_anchor=anchor,
        fast_ma=q.get("sma50"), atr_weekly=atr, stop_pct=stop_pct,
        trend_anchor_prev=sma40_prev,
    )
    out = fair_entry_to_dict(fe)
    # Transparency: which source the trend anchor came from this call.
    out["trend_anchor_source"] = "alpha_vantage_40wk_sma" if sma40 else "fmp_200day_fallback"
    if debug:
        last5 = [{"date": b["date"], "close": b["close"]} for b in series[-5:]]
        out["_debug"] = {
            "weekly_bars": len(series),
            "last5_weekly_closes": last5,
            "sma40_now": sma40,
            "sma40_prev_week": sma40_prev,
            "atr14_weekly": atr,
        }
    try:
        out["analyst"] = await market_data.get_analyst(symbol)
    except Exception:
        out["analyst"] = None
    return out
