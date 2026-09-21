"""Provider interface + shared helpers for the market-data layer.

Each provider implements whichever of these it supports and returns None for
anything it can't serve (unsupported, no key, symbol not covered, over quota,
HTTP error) — the dispatcher then falls back to the next provider.

Return shapes (plain dicts so callers stay simple):
- quote:  {symbol, name, price, sma50, sma200, year_high, year_low, source}
- weekly_series: [ {date, high, low, close}, ... ]  (oldest -> newest)
- analyst: {symbol, strong_buy, buy, hold, sell, strong_sell, consensus,
            target_high, target_low, target_consensus, target_median, source}
"""
from typing import Any, List, Optional, Dict
import httpx

TIMEOUT = 20.0


class Provider:
    name = "base"

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or ""

    async def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        return None

    async def get_weekly_series(self, symbol: str) -> Optional[List[Dict[str, float]]]:
        return None

    async def get_analyst(self, symbol: str) -> Optional[Dict[str, Any]]:
        return None


async def http_json(url: str, params: dict) -> Any:
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        return resp.json()


def consensus_label(sb: int, b: int, h: int, s: int, ss: int) -> str:
    total = sb + b + h + s + ss
    if total == 0:
        return "N/A"
    score = (2 * sb + b - s - 2 * ss) / total   # StrongBuy=2 .. StrongSell=-2
    if score >= 1.5:
        return "Strong Buy"
    if score >= 0.5:
        return "Buy"
    if score > -0.5:
        return "Hold"
    if score > -1.5:
        return "Sell"
    return "Strong Sell"
