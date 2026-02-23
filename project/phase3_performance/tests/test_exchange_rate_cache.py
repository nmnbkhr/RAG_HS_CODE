"""
Phase 3: Performance - Exchange Rate Cache Tests

Comprehensive tests for SQLite-based exchange rate caching.
"""

import pytest
import os
import time
import tempfile
from exchange_rate_cache import (
    ExchangeRateCache, CachedRate, get_cached_exchange_rate
)


@pytest.fixture
def temp_db():
    """Create a temporary database file."""
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def cache(temp_db):
    """Create a cache instance with temp database."""
    return ExchangeRateCache(db_path=temp_db, ttl=3600)


class TestCachedRate:
    """Tests for CachedRate dataclass"""

    def test_create_cached_rate(self):
        now = time.time()
        rate = CachedRate(
            currency="USD",
            tt_buying=278.50,
            tt_selling=280.50,
            source="NBP",
            fetched_at=now,
            expires_at=now + 3600
        )
        assert rate.currency == "USD"
        assert rate.tt_buying == 278.50
        assert rate.tt_selling == 280.50

    def test_is_expired_false(self):
        now = time.time()
        rate = CachedRate("USD", 278.50, 280.50, "NBP", now, now + 3600)
        assert not rate.is_expired

    def test_is_expired_true(self):
        now = time.time()
        rate = CachedRate("USD", 278.50, 280.50, "NBP", now - 7200, now - 3600)
        assert rate.is_expired

    def test_age_seconds(self):
        now = time.time()
        rate = CachedRate("USD", 278.50, 280.50, "NBP", now - 100, now + 3500)
        assert rate.age_seconds >= 100

    def test_age_display_seconds(self):
        now = time.time()
        rate = CachedRate("USD", 278.50, 280.50, "NBP", now - 30, now + 3570)
        assert "s ago" in rate.age_display

    def test_age_display_minutes(self):
        now = time.time()
        rate = CachedRate("USD", 278.50, 280.50, "NBP", now - 300, now + 3300)
        assert "m ago" in rate.age_display

    def test_age_display_hours(self):
        now = time.time()
        rate = CachedRate("USD", 278.50, 280.50, "NBP", now - 7200, now - 3600)
        assert "h ago" in rate.age_display


class TestExchangeRateCache:
    """Tests for ExchangeRateCache class"""

    def test_init(self, cache):
        assert cache.ttl == 3600
        assert cache.db_path is not None

    def test_put_and_get(self, cache):
        cache.put("USD", 278.50, 280.50, "NBP")
        cached = cache.get("USD")

        assert cached is not None
        assert cached.currency == "USD"
        assert cached.tt_buying == 278.50
        assert cached.tt_selling == 280.50
        assert cached.source == "NBP"

    def test_get_nonexistent(self, cache):
        cached = cache.get("EUR")
        assert cached is None

    def test_get_expired(self, temp_db):
        cache = ExchangeRateCache(db_path=temp_db, ttl=1)
        cache.put("USD", 278.50, 280.50, "NBP")
        time.sleep(1.1)

        cached = cache.get("USD")
        assert cached is None

    def test_get_or_fallback_returns_expired(self, temp_db):
        cache = ExchangeRateCache(db_path=temp_db, ttl=1)
        cache.put("USD", 278.50, 280.50, "NBP")
        time.sleep(1.1)

        # get() returns None for expired
        assert cache.get("USD") is None

        # get_or_fallback() returns expired rate
        fallback = cache.get_or_fallback("USD")
        assert fallback is not None
        assert fallback.tt_buying == 278.50
        assert fallback.is_expired

    def test_get_or_fallback_nonexistent(self, cache):
        fallback = cache.get_or_fallback("GBP")
        assert fallback is None

    def test_case_insensitive(self, cache):
        cache.put("usd", 278.50, 280.50, "NBP")
        cached = cache.get("USD")
        assert cached is not None
        assert cached.currency == "USD"

    def test_put_overwrites(self, cache):
        cache.put("USD", 278.50, 280.50, "NBP")
        cache.put("USD", 282.00, 284.00, "NBP Updated")

        cached = cache.get("USD")
        assert cached.tt_buying == 282.00
        assert cached.tt_selling == 284.00

    def test_invalidate(self, cache):
        cache.put("USD", 278.50, 280.50, "NBP")
        result = cache.invalidate("USD")

        assert result is True
        assert cache.get("USD") is None

    def test_invalidate_nonexistent(self, cache):
        result = cache.invalidate("GBP")
        assert result is False

    def test_invalidate_all(self, cache):
        cache.put("USD", 278.50, 280.50, "NBP")
        cache.put("EUR", 300.00, 302.00, "NBP")
        cache.put("GBP", 350.00, 352.00, "NBP")

        count = cache.invalidate_all()
        assert count == 3
        assert cache.get("USD") is None
        assert cache.get("EUR") is None

    def test_get_all(self, cache):
        cache.put("USD", 278.50, 280.50, "NBP")
        cache.put("EUR", 300.00, 302.00, "NBP")

        all_rates = cache.get_all()
        assert len(all_rates) == 2
        currencies = [r.currency for r in all_rates]
        assert "EUR" in currencies
        assert "USD" in currencies

    def test_needs_refresh_no_cache(self, cache):
        assert cache.needs_refresh("USD") is True

    def test_needs_refresh_fresh(self, cache):
        cache.put("USD", 278.50, 280.50, "NBP")
        assert cache.needs_refresh("USD") is False

    def test_needs_refresh_threshold(self, temp_db):
        cache = ExchangeRateCache(db_path=temp_db, ttl=10)
        cache.put("USD", 278.50, 280.50, "NBP")

        # At threshold 0.0, should always refresh
        assert cache.needs_refresh("USD", threshold=0.0) is True

    def test_stats_initial(self, cache):
        stats = cache.stats
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["total_requests"] == 0

    def test_stats_after_operations(self, cache):
        cache.put("USD", 278.50, 280.50, "NBP")
        cache.get("USD")  # hit
        cache.get("EUR")  # miss

        stats = cache.stats
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["updates"] == 1
        assert stats["hit_rate_pct"] == 50.0

    def test_reset_stats(self, cache):
        cache.put("USD", 278.50, 280.50, "NBP")
        cache.get("USD")
        cache.reset_stats()

        stats = cache.stats
        assert stats["hits"] == 0
        assert stats["misses"] == 0

    def test_multiple_currencies(self, cache):
        currencies = {
            "USD": (278.50, 280.50),
            "EUR": (300.00, 302.00),
            "GBP": (350.00, 352.00),
            "AED": (75.00, 77.00),
            "SAR": (74.00, 76.00)
        }

        for curr, (buy, sell) in currencies.items():
            cache.put(curr, buy, sell, "NBP")

        for curr, (buy, sell) in currencies.items():
            cached = cache.get(curr)
            assert cached is not None
            assert cached.tt_buying == buy
            assert cached.tt_selling == sell


class TestGetCachedExchangeRate:
    """Tests for get_cached_exchange_rate convenience function"""

    def test_pkr_returns_immediately(self, temp_db):
        rate, source = get_cached_exchange_rate("PKR", db_path=temp_db)
        assert rate == 1.0
        assert "PKR" in source

    def test_cached_hit_import(self, temp_db):
        cache = ExchangeRateCache(db_path=temp_db)
        cache.put("USD", 278.50, 280.50, "NBP")

        rate, source = get_cached_exchange_rate(
            "USD", "import", cache=cache
        )
        assert rate == 280.50  # TT Selling for imports
        assert "Cached" in source

    def test_cached_hit_export(self, temp_db):
        cache = ExchangeRateCache(db_path=temp_db)
        cache.put("USD", 278.50, 280.50, "NBP")

        rate, source = get_cached_exchange_rate(
            "USD", "export", cache=cache
        )
        assert rate == 278.50  # TT Buying for exports
        assert "Cached" in source

    def test_fetch_on_cache_miss(self, temp_db):
        def mock_fetch():
            return {"tt_buying": 279.00, "tt_selling": 281.00}

        rate, source = get_cached_exchange_rate(
            "USD", "import",
            fetch_fn=mock_fetch,
            db_path=temp_db
        )
        assert rate == 281.00
        assert "Live" in source

    def test_fallback_on_fetch_failure(self, temp_db):
        cache = ExchangeRateCache(db_path=temp_db, ttl=1)
        cache.put("USD", 278.50, 280.50, "NBP")
        time.sleep(1.1)

        def failing_fetch():
            raise Exception("Network error")

        rate, source = get_cached_exchange_rate(
            "USD", "import",
            fetch_fn=failing_fetch,
            cache=cache
        )
        assert rate == 280.50
        assert "stale" in source

    def test_hardcoded_fallback_usd(self, temp_db):
        def failing_fetch():
            raise Exception("Network error")

        rate, source = get_cached_exchange_rate(
            "USD", "import",
            fetch_fn=failing_fetch,
            db_path=temp_db
        )
        assert rate == 280.50
        assert "Estimated" in source

    def test_hardcoded_fallback_usd_export(self, temp_db):
        def failing_fetch():
            raise Exception("Network error")

        rate, source = get_cached_exchange_rate(
            "USD", "export",
            fetch_fn=failing_fetch,
            db_path=temp_db
        )
        assert rate == 278.50

    def test_unknown_currency_fallback(self, temp_db):
        rate, source = get_cached_exchange_rate(
            "XYZ", "import",
            db_path=temp_db
        )
        assert rate == 1.0
        assert "Default" in source

    def test_fetch_caches_result(self, temp_db):
        cache = ExchangeRateCache(db_path=temp_db)

        def mock_fetch():
            return {"tt_buying": 279.00, "tt_selling": 281.00}

        # First call fetches
        get_cached_exchange_rate("USD", "import", fetch_fn=mock_fetch, cache=cache)

        # Second call should hit cache
        rate, source = get_cached_exchange_rate("USD", "import", cache=cache)
        assert rate == 281.00
        assert "Cached" in source


class TestCachePersistence:
    """Tests for cache persistence across instances"""

    def test_persists_across_instances(self, temp_db):
        cache1 = ExchangeRateCache(db_path=temp_db)
        cache1.put("USD", 278.50, 280.50, "NBP")

        # Create new instance with same DB
        cache2 = ExchangeRateCache(db_path=temp_db)
        cached = cache2.get("USD")

        assert cached is not None
        assert cached.tt_buying == 278.50
