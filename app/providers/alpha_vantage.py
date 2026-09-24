"""Alpha Vantage provider: latest price (GLOBAL_QUOTE, incl. day change) +
weekly OHLC series.

The weekly series uses TIME_SERIES_WEEKLY_ADJUSTED (free tier) and returns
SPLIT/DIVIDEND-ADJUSTED bars: each bar's high/low/close are scaled by that
bar's adjustment factor (adjusted_close / close). This keeps the 40-week SMA
and ATR correct across stock splits — the unadjusted series mixes pre- and
post-split price levels and yields a wildly wrong SMA (e.g. CRWD's 4:1 split
on 2026-07-02 inflated the raw 40-week SMA to ~$407 vs the true ~$151). Falls
back to the unadjusted series if the adjusted endpoint returns nothing.

Broad symbol coverage but a small daily quota (~25/day free); GLOBAL_QUOTE
price reflects the last close, not a live intraday tick. No analyst data.
"""
from typing import Any, Dict, List, Optional
from .base import Provider, http_json

AV = "https://www.alphavantage.co/query"


def _f(x) -> Optional[float]:
    try:
        return float(str(x).replace("%", "").strip())
    except (TypeError, ValueError):
        return None


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
                    "change": _f(gq.get("09. change")),
                    "change_pct": _f(gq.get("10. change percent")),
                    "sma50": None, "sma200": None, "year_high": None, "year_low": None,
                    "source": self.name}
        except Exception:
            return None

    async def get_weekly_series(self, symbol: str) -> Optional[List[Dict[str, float]]]:
        if not self.api_key:
            return None
        # Preferred: split/dividend-adjusted weekly bars (correct across splits).
        try:
            data = await http_json(AV, {"function": "TIME_SERIES_WEEKLY_ADJUSTED",
                                        "symbol": symbol, "apikey": self.api_key})
            ts = data.get("Weekly Adjusted Time Series") or {}
            if ts:
                bars = []
                for d, v in sorted(ts.items()):
                    close = float(v["4. close"])
                    adj = float(v["5. adjusted close"])
                    factor = (adj / close) if close else 1.0
                    bars.append({"date": d,
                                 "high": float(v["2. high"]) * factor,
                                 "low": float(v["3. low"]) * factor,
                                 "close": adj})
                if bars:
                    return bars
        except Exception:
            pass
        # Fallback: unadjusted weekly (no split handling, but better than nothing).
        try:
            data = await http_json(AV, {"function": "TIME_SERIES_WEEKLY",
                                        "symbol": symbol, "apikey": self.api_key})
            ts = data.get("Weekly Time Series") or {}
            if not ts:
                return None
            return [{"date": d, "high": float(v["2. high"]), "low": float(v["3. low"]),
                     "close": float(v["4. close"])} for d, v in sorted(ts.items())] or None
        except Exception:
            return None
