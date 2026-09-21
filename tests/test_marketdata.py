"""Dispatcher logic tests: fallback order, TTL caching, all-None, consensus.

Providers are faked so nothing hits the network. We drive market_data._dispatch
through the public get_quote/get_analyst by passing an explicit registry.
"""
import asyncio

from app import market_data
from app.providers.base import Provider, consensus_label


class FakeProvider(Provider):
    """Records how many times each capability was called; returns a preset
    value (None to simulate 'can't serve this symbol')."""

    def __init__(self, name, quote=None, analyst=None, series=None):
        super().__init__(api_key="x")
        self.name = name
        self._quote, self._analyst, self._series = quote, analyst, series
        self.calls = {"get_quote": 0, "get_analyst": 0, "get_weekly_series": 0}

    async def get_quote(self, symbol):
        self.calls["get_quote"] += 1
        return self._quote

    async def get_analyst(self, symbol):
        self.calls["get_analyst"] += 1
        return self._analyst

    async def get_weekly_series(self, symbol):
        self.calls["get_weekly_series"] += 1
        return self._series


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def setup_function(_):
    market_data.clear_cache()


def test_fallback_skips_none_and_returns_first_hit():
    a = FakeProvider("a", quote=None)                      # can't serve
    b = FakeProvider("b", quote={"price": 42, "source": "b"})
    c = FakeProvider("c", quote={"price": 99, "source": "c"})
    reg = {"a": a, "b": b, "c": c}
    # override the configured order for this call
    market_data.settings.quote_providers = "a,b,c"
    out = run(market_data.get_quote("XYZ", registry=reg))
    assert out["source"] == "b"
    assert a.calls["get_quote"] == 1        # tried first
    assert b.calls["get_quote"] == 1        # answered
    assert c.calls["get_quote"] == 0        # never reached


def test_all_none_returns_none():
    a = FakeProvider("a", quote=None)
    b = FakeProvider("b", quote=None)
    reg = {"a": a, "b": b}
    market_data.settings.quote_providers = "a,b"
    assert run(market_data.get_quote("XYZ", registry=reg)) is None


def test_unknown_names_in_order_are_ignored():
    b = FakeProvider("b", quote={"price": 1, "source": "b"})
    reg = {"b": b}
    market_data.settings.quote_providers = "ghost,b,alsoghost"
    out = run(market_data.get_quote("XYZ", registry=reg))
    assert out["source"] == "b"


def test_cache_prevents_second_provider_call():
    market_data.clear_cache()
    b = FakeProvider("b", quote={"price": 5, "source": "b"})
    reg = {"b": b}
    market_data.settings.quote_providers = "b"
    market_data.settings.cache_ttl_quote = 300
    run(market_data.get_quote("AAA", registry=reg))
    run(market_data.get_quote("AAA", registry=reg))   # served from cache
    assert b.calls["get_quote"] == 1


def test_cache_is_per_symbol():
    b = FakeProvider("b", quote={"price": 5, "source": "b"})
    reg = {"b": b}
    market_data.settings.quote_providers = "b"
    market_data.settings.cache_ttl_quote = 300
    run(market_data.get_quote("AAA", registry=reg))
    run(market_data.get_quote("BBB", registry=reg))
    assert b.calls["get_quote"] == 2


def test_ttl_zero_disables_caching():
    b = FakeProvider("b", quote={"price": 5, "source": "b"})
    reg = {"b": b}
    market_data.settings.quote_providers = "b"
    market_data.settings.cache_ttl_quote = 0
    run(market_data.get_quote("AAA", registry=reg))
    run(market_data.get_quote("AAA", registry=reg))
    assert b.calls["get_quote"] == 2


def test_provider_exception_is_swallowed_and_falls_through():
    class Boom(FakeProvider):
        async def get_quote(self, symbol):
            self.calls["get_quote"] += 1
            raise RuntimeError("402 or network")
    a = Boom("a")
    b = FakeProvider("b", quote={"price": 7, "source": "b"})
    reg = {"a": a, "b": b}
    market_data.settings.quote_providers = "a,b"
    out = run(market_data.get_quote("XYZ", registry=reg))
    assert out["source"] == "b"
    assert a.calls["get_quote"] == 1


def test_analyst_dispatch_uses_analyst_order():
    a = FakeProvider("a", analyst=None)
    b = FakeProvider("b", analyst={"consensus": "Buy", "source": "b"})
    reg = {"a": a, "b": b}
    market_data.settings.analyst_providers = "a,b"
    out = run(market_data.get_analyst("XYZ", registry=reg))
    assert out["consensus"] == "Buy"


def test_consensus_label_boundaries():
    assert consensus_label(0, 0, 0, 0, 0) == "N/A"
    assert consensus_label(10, 0, 0, 0, 0) == "Strong Buy"   # score 2.0
    assert consensus_label(0, 10, 0, 0, 0) == "Buy"          # score 1.0
    assert consensus_label(0, 0, 10, 0, 0) == "Hold"         # score 0.0
    assert consensus_label(0, 0, 0, 10, 0) == "Sell"         # score -1.0
    assert consensus_label(0, 0, 0, 0, 10) == "Strong Sell"  # score -2.0
