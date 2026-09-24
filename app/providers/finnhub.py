"""Finnhub provider: real-time price + day change (/quote) and analyst
recommendation trends (/stock/recommendation -> buy/hold/sell counts). Broad
free coverage and real-time US quotes; price targets are premium (not fetched).
No 50/200-day MAs or 52wk range.
"""
from typing import Any, Dict, Optional
from .base import Provider, http_json, consensus_label

FH = "https://finnhub.io/api/v1"


class Finnhub(Provider):
    name = "finnhub"

    async def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            return None
        try:
            data = await http_json(f"{FH}/quote", {"symbol": symbol, "token": self.api_key})
        except Exception:
            return None
        price = data.get("c") if isinstance(data, dict) else None
        if not price:   # c == 0 means "no data for symbol"
            return None
        return {"symbol": symbol, "name": None, "price": float(price),
                "change": data.get("d"), "change_pct": data.get("dp"),
                "sma50": None, "sma200": None,
                "year_high": None, "year_low": None,   # /quote h,l are the day range, not 52wk
                "source": self.name}

    async def get_analyst(self, symbol: str) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            return None
        try:
            data = await http_json(f"{FH}/stock/recommendation", {"symbol": symbol, "token": self.api_key})
        except Exception:
            return None
        if not isinstance(data, list) or not data:
            return None
        r = data[0]   # most recent period
        sb = r.get("strongBuy", 0) or 0
        b = r.get("buy", 0) or 0
        h = r.get("hold", 0) or 0
        s = r.get("sell", 0) or 0
        ss = r.get("strongSell", 0) or 0
        if (sb + b + h + s + ss) == 0:
            return None
        return {"symbol": symbol, "strong_buy": sb, "buy": b, "hold": h, "sell": s,
                "strong_sell": ss, "consensus": consensus_label(sb, b, h, s, ss),
                "target_high": None, "target_low": None, "target_consensus": None,
                "target_median": None, "source": self.name}
