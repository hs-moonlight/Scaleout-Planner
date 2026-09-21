"""Alpha Vantage provider: current price (GLOBAL_QUOTE) + weekly OHLC series.

Broad symbol coverage (covers many tickers FMP's free plan gates), but a small
daily quota (~25/day free). No analyst data.
"""
from typing import Any, Dict, List, Optional
from .base import Provider, http_json

AV = "https://www.alphavantage.co/query"


class AlphaVantage(Provider):
    name = "alpha_vantage"

    async def get_quote(self, symbol: str) -> Optional[Dict[str, Any]]:
        if not self.api_key:
            return None
        try:
            data = await http_json(AV, {"function": "GLOBAL_QUOTE", "symbol": symbol,
                                        "apikey": self.api_key})
            gq = data.get("Global Quote") or {}
            price = gq.get("05. price")
            if not price:
                return None
            return {"symbol": symbol, "name": None, "price": float(price),
                    "sma50": None, "sma200": None, "year_high": None, "year_low": None,
                    "source": self.name}
        except Exception:
            return None

    async def get_weekly_series(self, symbol: str) -> Optional[List[Dict[str, float]]]:
        if not self.api_key:
            return None
        try:
            data = await http_json(AV, {"function": "TIME_SERIES_WEEKLY", "symbol": symbol,
                                        "apikey": self.api_key})
            ts = data.get("Weekly Time Series") or {}
            if not ts:
                return None
            bars = [{"date": d, "high": float(v["2. high"]), "low": float(v["3. low"]),
                     "close": float(v["4. close"])} for d, v in sorted(ts.items())]
            return bars or None
        except Exception:
            return None
