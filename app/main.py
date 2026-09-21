"""Scale-Out Planner API (Step 2).

Endpoints:
  GET  /health              - liveness
  POST /plan                - scale-out math (no network)
  GET  /quote/{symbol}      - live price (+ 50/200-day averages if available)
  GET  /analyst/{symbol}    - analyst consensus + price targets
  GET  /suggest/{symbol}    - fair-entry zone + flags + analyst overlay
  /trades ...               - save / update / review trades (SQLite)

Market data comes through app/market_data.py, a provider-agnostic dispatcher
that tries providers (FMP / Alpha Vantage / Finnhub) in a configurable order
with fallback and in-memory caching, so a symbol one provider gates still
resolves via another.
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
        q = await market_data.get_quote(symbol.upper())
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"quote lookup error: {e}")
    if not q:
        raise HTTPException(
            status_code=404,
            detail=f"No quote for {symbol.upper()} from any configured provider.",
        )
    return q


@app.get("/analyst/{symbol}")
async def analyst(symbol: str) -> dict:
    try:
        a = await market_data.get_analyst(symbol.upper())
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"analyst lookup error: {e}")
    if not a:
        raise HTTPException(
            status_code=404,
            detail=f"No analyst data for {symbol.upper()} from any configured provider.",
        )
    return a


@app.get("/suggest/{symbol}")
async def suggest(symbol: str, stop_pct: float | None = None, debug: bool = False) -> dict:
    symbol = symbol.upper()
    stop_pct = stop_pct if stop_pct is not None else settings.default_stop_pct

    q = await market_data.get_quote(symbol)              # may be None
    series = await market_data.get_weekly_series(symbol)  # may be None

    # From the weekly OHLC series (one provider call): 40-week SMA anchor,
    # its prior-week value (trend direction), a fast MA (~10 weeks ~ 50 days),
    # and 14-week ATR.
    atr = sma40 = sma40_prev = sma_fast = None
    if series:
        closes = [b["close"] for b in series]
        highs = [b["high"] for b in series]
        lows = [b["low"] for b in series]
        sma40 = indicators.sma(closes, 40)
        sma40_prev = indicators.sma(closes[:-1], 40)
        sma_fast = indicators.sma(closes, 10)   # ~50 trading days
        atr = indicators.atr_wilder(highs, lows, closes, 14)

    # Price: prefer the live quote, fall back to the latest weekly close.
    price = (q or {}).get("price")
    if price is None and series:
        price = series[-1]["close"]
    if price is None:
        raise HTTPException(
            status_code=404,
            detail=f"No price for {symbol} from any configured provider "
                   f"(check the symbol, or set more provider keys).",
        )

    anchor = sma40 if sma40 else (q or {}).get("sma200")
    if anchor is None:
        raise HTTPException(
            status_code=502,
            detail="No trend anchor available: need either an Alpha Vantage "
                   "weekly series (40-week SMA) or a provider 200-day SMA.",
        )
    fast_ma = sma_fast if sma_fast else (q or {}).get("sma50")

    fe = build_fair_entry(
        symbol=symbol, price=price, trend_anchor=anchor,
        fast_ma=fast_ma, atr_weekly=atr, stop_pct=stop_pct,
        trend_anchor_prev=sma40_prev,
    )
    out = fair_entry_to_dict(fe)
    out["price_source"] = (q or {}).get("source") if q and q.get("price") is not None \
        else ("weekly_series_close" if series else None)
    out["trend_anchor_source"] = "weekly_40wk_sma" if sma40 else "quote_200day_fallback"
    out["fast_ma_source"] = "weekly_10wk_sma" if sma_fast else \
        ("quote_50day" if fast_ma is not None else None)

    if debug:
        out["_debug"] = {
            "quote_source": (q or {}).get("source"),
            "quote": q,
            "weekly_bars": len(series) if series else 0,
            "last5_weekly_closes": [{"date": b["date"], "close": b["close"]}
                                    for b in series[-5:]] if series else [],
            "sma40_now": sma40,
            "sma40_prev_week": sma40_prev,
            "sma_fast_10wk": sma_fast,
            "atr14_weekly": atr,
        }

    out["analyst"] = await market_data.get_analyst(symbol)  # best-effort, may be None
    return out
