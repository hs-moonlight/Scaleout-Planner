"""Market-data clients.

Weekly OHLC series from Alpha Vantage (ONE call -> ATR + 40-week SMA computed
locally in indicators.py, so /suggest makes a single AV call and avoids the
free-tier burst throttle). Quote + analyst from FMP's current "stable" API.
All calls are best-effort: raise MarketDataError or return empty so /suggest
degrades gracefully.

NOTE: FMP retired the legacy /api/v3 endpoints for new keys (they 403); this
client uses https://financialmodelingprep.com/stable.
"""
from typing import Any, Dict, List
import httpx

from .config import settings

FMP_BASE = "https://financialmodelingprep.com/stable"
AV_BASE = "https://www.alphavantage.co/query"
_TIMEOUT = 20.0


class MarketDataError(Exception):
    pass


async def _get_json(client: httpx.AsyncClient, url: str, params: dict) -> Any:
    resp = await client.get(url, params=params, timeout=_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


async def get_quote(symbol: str) -> Dict[str, Any]:
    """Current price plus FMP's 50- and 200-day averages (200-day ~ 40-week SMA)."""
    if not settings.fmp_api_key:
        raise MarketDataError("FMP_API_KEY is not set")
    async with httpx.AsyncClient() as client:
        data = await _get_json(client, f"{FMP_BASE}/quote",
                               {"symbol": symbol, "apikey": settings.fmp_api_key})
    if not data:
        raise MarketDataError(f"No quote returned for {symbol}")
    q = data[0] if isinstance(data, list) else data
    return {
        "symbol": q.get("symbol"),
        "name": q.get("name"),
        "price": q.get("price"),
        "sma50": q.get("priceAvg50"),
        "sma200": q.get("priceAvg200"),
        "year_high": q.get("yearHigh"),
        "year_low": q.get("yearLow"),
    }


async def get_analyst(symbol: str) -> Dict[str, Any]:
    """Buy/Hold/Sell counts + consensus and price-target consensus (FMP stable)."""
    if not settings.fmp_api_key:
        raise MarketDataError("FMP_API_KEY is not set")
    key = settings.fmp_api_key
    async with httpx.AsyncClient() as client:
        grades = await _get_json(client, f"{FMP_BASE}/grades-consensus",
                                 {"symbol": symbol, "apikey": key})
        try:
            target = await _get_json(client, f"{FMP_BASE}/price-target-consensus",
                                     {"symbol": symbol, "apikey": key})
        except Exception:
            target = None

    g = grades[0] if isinstance(grades, list) and grades else (grades if isinstance(grades, dict) else {})
    sb = g.get("strongBuy", 0) or 0
    b = g.get("buy", 0) or 0
    h = g.get("hold", 0) or 0
    s = g.get("sell", 0) or 0
    ss = g.get("strongSell", 0) or 0
    consensus = g.get("consensus") or _consensus_label(sb, b, h, s, ss)

    tgt = {}
    if target:
        t = target[0] if isinstance(target, list) and target else target
        if isinstance(t, dict):
            tgt = {
                "target_high": t.get("targetHigh"),
                "target_low": t.get("targetLow"),
                "target_consensus": t.get("targetConsensus"),
                "target_median": t.get("targetMedian"),
            }

    return {
        "symbol": symbol,
        "strong_buy": sb, "buy": b, "hold": h, "sell": s, "strong_sell": ss,
        "consensus": consensus,
        **tgt,
    }


def _consensus_label(sb, b, h, s, ss) -> str:
    total = sb + b + h + s + ss
    if total == 0:
        return "N/A"
    score = (2 * sb + b - s - 2 * ss) / total   # StrongBuy=2..StrongSell=-2
    if score >= 1.5:
        return "Strong Buy"
    if score >= 0.5:
        return "Buy"
    if score > -0.5:
        return "Hold"
    if score > -1.5:
        return "Sell"
    return "Strong Sell"


async def get_weekly_series(symbol: str) -> List[Dict[str, float]]:
    """ONE Alpha Vantage call -> weekly OHLC bars, oldest to newest.

    Returns [] on any failure or rate-limit (caller falls back). ATR and the
    40-week SMA are computed from this single series in indicators.py.
    """
    if not settings.alpha_vantage_api_key:
        return []
    params = {"function": "TIME_SERIES_WEEKLY", "symbol": symbol,
              "apikey": settings.alpha_vantage_api_key}
    try:
        async with httpx.AsyncClient() as client:
            data = await _get_json(client, AV_BASE, params)
        ts = data.get("Weekly Time Series") or {}
        bars: List[Dict[str, float]] = []
        for d in sorted(ts.keys()):
            row = ts[d]
            bars.append({
                "date": d,
                "high": float(row["2. high"]),
                "low": float(row["3. low"]),
                "close": float(row["4. close"]),
            })
        return bars
    except Exception:
        return []
