"""FMP provider: full quote (price + day change + 50/200-day MAs + 52wk range)
and analyst data (consensus + price targets). Free plan restricts symbol
coverage and has a daily cap — both surface as HTTP 402, which we swallow and
return None so the dispatcher falls back.
"""
from typing import Any, Dict, Optional
from .base import Provider, http_json, consensus_label

FMP = "https://financialmodelingprep.com/stable"


class FMP_(Provider):
    name = "fmp"

    async def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            return None
        try:
            data = await http_json(f"{FMP}/quote", {"symbol": symbol, "apikey": self.api_key})
        except Exception:
            return None
        q = data[0] if isinstance(data, list) and data else (data if isinstance(data, dict) else None)
        if not q or q.get("price") is None:
            return None
        change_pct = q.get("changePercentage")
        if change_pct is None:
            change_pct = q.get("changesPercentage")   # legacy field name
        return {"symbol": q.get("symbol"), "name": q.get("name"), "price": q.get("price"),
                "change": q.get("change"), "change_pct": change_pct,
                "sma50": q.get("priceAvg50"), "sma200": q.get("priceAvg200"),
                "year_high": q.get("yearHigh"), "year_low": q.get("yearLow"),
                "source": self.name}

    async def get_analyst(self, symbol: str) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            return None
        try:
            grades = await http_json(f"{FMP}/grades-consensus", {"symbol": symbol, "apikey": self.api_key})
        except Exception:
            return None
        g = grades[0] if isinstance(grades, list) and grades else (grades if isinstance(grades, dict) else {})
        if not g:
            return None
        sb = g.get("strongBuy", 0) or 0
        b = g.get("buy", 0) or 0
        h = g.get("hold", 0) or 0
        s = g.get("sell", 0) or 0
        ss = g.get("strongSell", 0) or 0
        out = {"symbol": symbol, "strong_buy": sb, "buy": b, "hold": h, "sell": s,
               "strong_sell": ss, "consensus": g.get("consensus") or consensus_label(sb, b, h, s, ss),
               "target_high": None, "target_low": None, "target_consensus": None,
               "target_median": None, "source": self.name}
        try:
            t = await http_json(f"{FMP}/price-target-consensus", {"symbol": symbol, "apikey": self.api_key})
            tt = t[0] if isinstance(t, list) and t else (t if isinstance(t, dict) else {})
            if tt:
                out.update(target_high=tt.get("targetHigh"), target_low=tt.get("targetLow"),
                           target_consensus=tt.get("targetConsensus"), target_median=tt.get("targetMedian"))
        except Exception:
            pass
        return out
