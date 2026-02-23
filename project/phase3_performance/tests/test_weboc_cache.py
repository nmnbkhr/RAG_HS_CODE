"""
Phase 3: Performance - WEBOC Cache Tests

Comprehensive tests for WEBOC duty data caching.
"""

import pytest
import os
import time
import tempfile
from weboc_cache import WEBOCCache, CachedDutyData


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
    return WEBOCCache(db_path=temp_db, ttl=3600)


SAMPLE_DUTY_DATA = {
    "customs_duty": 20.0,
    "sales_tax": 18.0,
    "income_tax": 5.5,
    "additional_duty": 0.0,
    "regulatory_duty": 0.0,
    "description": "Fresh apples",
    "unit_of_measure": "kg"
}

VEHICLE_DUTY_DATA = {
    "customs_duty": 50.0,
    "sales_tax": 18.0,
    "income_tax": 6.0,
    "additional_duty": 7.0,
    "regulatory_duty": 15.0,
    "description": "Motor vehicles for transport of persons",
    "unit_of_measure": "units"
}


class TestCachedDutyData:
    """Tests for CachedDutyData dataclass"""

    def test_create(self):
        now = time.time()
        data = CachedDutyData(
            hs_code="0808.1000",
            customs_duty=20.0,
            sales_tax=18.0,
            income_tax=5.5,
            additional_duty=0.0,
            regulatory_duty=0.0,
            federal_excise_duty=0.0,
            description="Fresh apples",
            unit_of_measure="kg",
            source="WEBOC",
            fetched_at=now,
            expires_at=now + 86400
        )
        assert data.hs_code == "0808.1000"
        assert data.customs_duty == 20.0

    def test_is_expired(self):
        now = time.time()
        data = CachedDutyData(
            "0808.1000", 20.0, 18.0, 5.5, 0.0, 0.0, 0.0,
            "Apples", "kg", "WEBOC", now - 100000, now - 50000
        )
        assert data.is_expired

    def test_not_expired(self):
        now = time.time()
        data = CachedDutyData(
            "0808.1000", 20.0, 18.0, 5.5, 0.0, 0.0, 0.0,
            "Apples", "kg", "WEBOC", now, now + 86400
        )
        assert not data.is_expired

    def test_to_dict(self):
        now = time.time()
        data = CachedDutyData(
            "0808.1000", 20.0, 18.0, 5.5, 0.0, 0.0, 0.0,
            "Fresh apples", "kg", "WEBOC", now, now + 86400
        )
        d = data.to_dict()
        assert d["hs_code"] == "0808.1000"
        assert d["status"] == "success"
        assert d["customs_duty"] == 20.0
        assert d["cached"] is True

    def test_age_display(self):
        now = time.time()
        data = CachedDutyData(
            "0808.1000", 20.0, 18.0, 5.5, 0.0, 0.0, 0.0,
            "Apples", "kg", "WEBOC", now - 30, now + 86370
        )
        assert "s ago" in data.age_display


class TestWEBOCCache:
    """Tests for WEBOCCache class"""

    def test_init(self, cache):
        assert cache.ttl == 3600
        assert cache.max_entries == 10000

    def test_put_and_get(self, cache):
        cache.put("0808.1000", SAMPLE_DUTY_DATA)
        cached = cache.get("0808.1000")

        assert cached is not None
        assert cached.hs_code == "0808.1000"
        assert cached.customs_duty == 20.0
        assert cached.sales_tax == 18.0
        assert cached.income_tax == 5.5
        assert cached.description == "Fresh apples"
        assert cached.unit_of_measure == "kg"

    def test_get_nonexistent(self, cache):
        assert cache.get("9999.9999") is None

    def test_get_expired(self, temp_db):
        cache = WEBOCCache(db_path=temp_db, ttl=1)
        cache.put("0808.1000", SAMPLE_DUTY_DATA)
        time.sleep(1.1)

        assert cache.get("0808.1000") is None

    def test_get_or_fallback_expired(self, temp_db):
        cache = WEBOCCache(db_path=temp_db, ttl=1)
        cache.put("0808.1000", SAMPLE_DUTY_DATA)
        time.sleep(1.1)

        fallback = cache.get_or_fallback("0808.1000")
        assert fallback is not None
        assert fallback.customs_duty == 20.0
        assert fallback.is_expired

    def test_get_or_fallback_nonexistent(self, cache):
        assert cache.get_or_fallback("9999.9999") is None

    def test_hs_code_normalization(self, cache):
        cache.put("08081000", SAMPLE_DUTY_DATA)
        cached = cache.get("0808.1000")
        assert cached is not None

    def test_put_overwrites(self, cache):
        cache.put("0808.1000", SAMPLE_DUTY_DATA)
        updated = {**SAMPLE_DUTY_DATA, "customs_duty": 25.0}
        cache.put("0808.1000", updated)

        cached = cache.get("0808.1000")
        assert cached.customs_duty == 25.0

    def test_invalidate(self, cache):
        cache.put("0808.1000", SAMPLE_DUTY_DATA)
        result = cache.invalidate("0808.1000")
        assert result is True
        assert cache.get("0808.1000") is None

    def test_invalidate_nonexistent(self, cache):
        assert cache.invalidate("9999.9999") is False

    def test_invalidate_all(self, cache):
        cache.put("0808.1000", SAMPLE_DUTY_DATA)
        cache.put("8703.2300", VEHICLE_DUTY_DATA)

        count = cache.invalidate_all()
        assert count == 2
        assert cache.count() == 0

    def test_cleanup_expired(self, temp_db):
        cache = WEBOCCache(db_path=temp_db, ttl=1)
        cache.put("0808.1000", SAMPLE_DUTY_DATA)
        cache.put("8703.2300", VEHICLE_DUTY_DATA)
        time.sleep(1.1)

        removed = cache.cleanup_expired()
        assert removed == 2
        assert cache.count() == 0

    def test_count(self, cache):
        assert cache.count() == 0
        cache.put("0808.1000", SAMPLE_DUTY_DATA)
        assert cache.count() == 1
        cache.put("8703.2300", VEHICLE_DUTY_DATA)
        assert cache.count() == 2

    def test_search_by_hs_code(self, cache):
        cache.put("0808.1000", SAMPLE_DUTY_DATA)
        cache.put("0808.2000", {**SAMPLE_DUTY_DATA, "description": "Pears"})
        cache.put("8703.2300", VEHICLE_DUTY_DATA)

        results = cache.search("0808")
        assert len(results) == 2

    def test_search_by_description(self, cache):
        cache.put("0808.1000", SAMPLE_DUTY_DATA)
        cache.put("8703.2300", VEHICLE_DUTY_DATA)

        results = cache.search("apples")
        assert len(results) == 1
        assert results[0].hs_code == "0808.1000"

    def test_search_no_results(self, cache):
        cache.put("0808.1000", SAMPLE_DUTY_DATA)
        results = cache.search("electronics")
        assert len(results) == 0

    def test_stats(self, cache):
        cache.put("0808.1000", SAMPLE_DUTY_DATA)
        cache.get("0808.1000")  # hit
        cache.get("9999.9999")  # miss

        stats = cache.stats
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["updates"] == 1
        assert stats["hit_rate_pct"] == 50.0
        assert stats["entries"] == 1

    def test_reset_stats(self, cache):
        cache.put("0808.1000", SAMPLE_DUTY_DATA)
        cache.get("0808.1000")
        cache.reset_stats()

        stats = cache.stats
        assert stats["hits"] == 0

    def test_multiple_duties(self, cache):
        """Test caching items with all duty types"""
        cache.put("8703.2300", VEHICLE_DUTY_DATA)
        cached = cache.get("8703.2300")

        assert cached.customs_duty == 50.0
        assert cached.additional_duty == 7.0
        assert cached.regulatory_duty == 15.0

    def test_none_duty_values(self, cache):
        """Test handling of None duty values"""
        data = {
            "customs_duty": None,
            "sales_tax": None,
            "income_tax": None,
            "additional_duty": None,
            "regulatory_duty": None,
            "description": "Unknown item",
            "unit_of_measure": "units"
        }
        cache.put("9999.0000", data)
        cached = cache.get("9999.0000")

        assert cached is not None
        assert cached.customs_duty is None

    def test_lru_eviction(self, temp_db):
        """Test LRU eviction when cache is full"""
        cache = WEBOCCache(db_path=temp_db, ttl=3600, max_entries=10)

        for i in range(15):
            hs = f"{i:04d}.0000"
            cache.put(hs, {**SAMPLE_DUTY_DATA, "description": f"Item {i}"})

        # Should have evicted some entries
        assert cache.count() <= 15


class TestCachePersistence:
    """Tests for cache persistence across instances"""

    def test_persists_across_instances(self, temp_db):
        cache1 = WEBOCCache(db_path=temp_db)
        cache1.put("0808.1000", SAMPLE_DUTY_DATA)

        cache2 = WEBOCCache(db_path=temp_db)
        cached = cache2.get("0808.1000")

        assert cached is not None
        assert cached.customs_duty == 20.0


class TestEdgeCases:
    """Edge case tests"""

    def test_long_description(self, cache):
        data = {**SAMPLE_DUTY_DATA, "description": "A" * 1000}
        cache.put("0808.1000", data)
        cached = cache.get("0808.1000")
        assert len(cached.description) == 1000

    def test_special_characters_in_description(self, cache):
        data = {**SAMPLE_DUTY_DATA, "description": "Items (Grade A) - 'Premium' & Fresh <100kg>"}
        cache.put("0808.1000", data)
        cached = cache.get("0808.1000")
        assert "Grade A" in cached.description

    def test_zero_duty_rates(self, cache):
        data = {
            "customs_duty": 0.0,
            "sales_tax": 0.0,
            "income_tax": 0.0,
            "additional_duty": 0.0,
            "regulatory_duty": 0.0,
            "description": "Exempt item",
            "unit_of_measure": "units"
        }
        cache.put("0808.1000", data)
        cached = cache.get("0808.1000")
        assert cached.customs_duty == 0.0
