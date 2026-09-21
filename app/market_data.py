"""Provider-agnostic market-data dispatcher.

Providers (app/providers/) each implement whatever they can and return None for
anything they can't serve. This module builds a registry from settings, then for
each capability (quote / weekly_series / analyst) tries providers in a
configurable order and returns the first non-None result. Results are cached in
memory with a per-capability TTL to stretch free-tier quotas.

Why: no single free provider covers every symbol or has a generous quota. FMP's
free plan gates many symbols (HTTP 402); Alpha Vantage covers them but has a
tiny daily cap and no analyst data; Finnhub covers analyst recommendations
broadly. Ordering + fallback gets the best of each at $0.

Default order (config.py / .env):
  quote:   fmp -> alpha_vantage -> finnhub   (FMP-gated symbols fall back to AV)
  analyst: fmp -> finnhub
  series:  alpha_vantage                      (only AV gives the weekly OHLC we need)
"""
import time
from typing import Any, Dict, List, Optional

from .config import settings
from .providers.alpha_vantage import AlphaVantage
from .providers.fmp import FMP_
from .providers.finnhub import Finnhub

# Re-exported for callers/tests that want the labeller.
from .providers.base import consensus_label  # noqa: F401


class MarketDataError(Exception):
    """Raised by callers (e.g. main.py) when every provider returns nothing."""


def build_registry() -> Dict[str, Any]:
    """Instantiate every known provider with its key. A provider with no key
    still lives in the registry but returns None (so config-driven order stays
    simple); the dispatcher just falls through to the next one."""
    return {
        "alpha_vantage": AlphaVantage(settings.alpha_vantage_api_key),
        "fmp": FMP_(settings.fmp_api_key),
        "finnhub": Finnhub(settings.finnhub_api_key),
    }


_REGISTRY: Dict[str, Any] = build_registry()

# key -> (expires_at_epoch, value). Only truthy results are cached.
_CACHE: Dict[tuple, tuple] = {}


def clear_cache() -> None:
    _CACHE.clear()


def reload_registry() -> None:
    """Rebuild providers from current settings (used by tests / key rotation)."""
    global _REGISTRY
    _REGISTRY = build_registry()


def _order(csv: str, registry: Dict[str, Any]) -> List[str]:
    """Comma-separated provider names -> those actually present in the registry,
    order preserved, blanks and unknown names dropped."""
    return [n.strip() for n in (csv or "").split(",")
            if n.strip() in registry]


async def _dispatch(capability: str, method: str, symbol: str, csv_order: str,
                    ttl: int, registry: Optional[Dict[str, Any]] = None) -> Optional[Any]:
    registry = registry if registry is not None else _REGISTRY
    sym = symbol.upper()
    ck = (capability, sym)
    hit = _CACHE.get(ck)
    if hit and hit[0] > time.time():
        return hit[1]

    for name in _order(csv_order, registry):
        provider = registry[name]
        try:
            result = await getattr(provider, method)(sym)
        except Exception:
            result = None
        if result:
            if ttl > 0:
                _CACHE[ck] = (time.time() + ttl, result)
            return result
    return None


async def get_quote(symbol: str, registry: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    return await _dispatch("quote", "get_quote", symbol,
                           settings.quote_providers, settings.cache_ttl_quote, registry)


async def get_analyst(symbol: str, registry: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    return await _dispatch("analyst", "get_analyst", symbol,
                           settings.analyst_providers, settings.cache_ttl_analyst, registry)


async def get_weekly_series(symbol: str, registry: Optional[Dict[str, Any]] = None) -> Optional[List[Dict[str, float]]]:
    return await _dispatch("series", "get_weekly_series", symbol,
                           settings.series_providers, settings.cache_ttl_series, registry)
