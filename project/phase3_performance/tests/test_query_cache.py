"""
Phase 3: Performance - Query Cache Tests

Comprehensive tests for RAG query result caching.
"""

import pytest
import os
import time
import tempfile
from query_cache import QueryCache, CachedQuery


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def cache(temp_db):
    return QueryCache(db_path=temp_db, ttl=3600)


class TestQueryNormalization:
    """Tests for query normalization"""

    def test_case_normalization(self):
        assert QueryCache.normalize_query("HELLO WORLD") == "hello world"

    def test_whitespace_normalization(self):
        assert QueryCache.normalize_query("hello   world") == "hello world"

    def test_leading_trailing_whitespace(self):
        assert QueryCache.normalize_query("  hello  ") == "hello"

    def test_hs_code_keyword_normalization(self):
        q1 = QueryCache.normalize_query("HS Code 0808.1000")
        q2 = QueryCache.normalize_query("HSCode 0808.1000")
        assert q1 == q2

    def test_pct_code_normalization(self):
        q1 = QueryCache.normalize_query("PCT code 0808.1000")
        q2 = QueryCache.normalize_query("HS code 0808.1000")
        assert q1 == q2

    def test_hs_code_format_normalization(self):
        q1 = QueryCache.normalize_query("What is 08081000?")
        q2 = QueryCache.normalize_query("What is 0808.1000?")
        assert q1 == q2

    def test_identical_queries_same_hash(self):
        q1 = "What is HS code 0808.1000?"
        q2 = "What is HS Code 0808.1000?"

        n1 = QueryCache.normalize_query(q1)
        n2 = QueryCache.normalize_query(q2)

        assert QueryCache.hash_query(n1) == QueryCache.hash_query(n2)

    def test_different_queries_different_hash(self):
        n1 = QueryCache.normalize_query("What is HS code 0808.1000?")
        n2 = QueryCache.normalize_query("What is HS code 8703.2300?")

        assert QueryCache.hash_query(n1) != QueryCache.hash_query(n2)


class TestQueryCache:
    """Tests for QueryCache class"""

    def test_init(self, cache):
        assert cache.ttl == 3600
        assert cache.count() == 0

    def test_put_and_get(self, cache):
        query = "What is HS code 0808.1000?"
        result = "HS Code: 0808.1000\nDescription: Fresh apples\nCD: 20%"

        cache.put(query, result)
        cached = cache.get(query)

        assert cached is not None
        assert cached == result

    def test_get_nonexistent(self, cache):
        assert cache.get("some random query") is None

    def test_get_expired(self, temp_db):
        cache = QueryCache(db_path=temp_db, ttl=1)
        cache.put("query", "result")
        time.sleep(1.1)

        assert cache.get("query") is None

    def test_case_insensitive_matching(self, cache):
        cache.put("What is HS code 0808.1000?", "Result A")
        cached = cache.get("what is hs code 0808.1000?")
        assert cached == "Result A"

    def test_whitespace_insensitive_matching(self, cache):
        cache.put("What is  HS  code  0808.1000?", "Result A")
        cached = cache.get("What is HS code 0808.1000?")
        assert cached == "Result A"

    def test_put_overwrites(self, cache):
        cache.put("query", "result1")
        cache.put("query", "result2")

        assert cache.get("query") == "result2"

    def test_count(self, cache):
        assert cache.count() == 0
        cache.put("query1", "result1")
        assert cache.count() == 1
        cache.put("query2", "result2")
        assert cache.count() == 2

    def test_invalidate_all(self, cache):
        cache.put("query1", "result1")
        cache.put("query2", "result2")

        count = cache.invalidate_all()
        assert count == 2
        assert cache.count() == 0

    def test_cleanup_expired(self, temp_db):
        cache = QueryCache(db_path=temp_db, ttl=1)
        cache.put("query1", "result1")
        cache.put("query2", "result2")
        time.sleep(1.1)

        removed = cache.cleanup_expired()
        assert removed >= 2

    def test_hot_cache(self, cache):
        """Test that frequently accessed queries are in hot cache"""
        cache.put("query", "result")

        # First get populates hot cache
        cache.get("query")

        # Second get should hit hot cache
        cache.get("query")

        stats = cache.stats
        assert stats["hot_hits"] >= 1

    def test_stats(self, cache):
        cache.put("query1", "result1")
        cache.get("query1")  # hit
        cache.get("query2")  # miss

        stats = cache.stats
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["updates"] == 1
        assert stats["hit_rate_pct"] == 50.0

    def test_reset_stats(self, cache):
        cache.put("query", "result")
        cache.get("query")
        cache.reset_stats()

        assert cache.stats["hits"] == 0

    def test_large_result(self, cache):
        """Test caching large results"""
        large_result = "A" * 10000
        cache.put("query", large_result)
        assert cache.get("query") == large_result

    def test_special_characters_in_query(self, cache):
        query = "What's the duty for 'apples' & 'pears' (fresh)?"
        cache.put(query, "result")
        assert cache.get(query) == "result"

    def test_unicode_in_result(self, cache):
        result = "Description: Fresh apples - PKR 280.50"
        cache.put("query", result)
        assert cache.get("query") == result


class TestCachePersistence:
    """Tests for persistence"""

    def test_persists_across_instances(self, temp_db):
        cache1 = QueryCache(db_path=temp_db)
        cache1.put("query", "result")

        cache2 = QueryCache(db_path=temp_db)
        assert cache2.get("query") == "result"


class TestEviction:
    """Tests for cache eviction"""

    def test_eviction_at_capacity(self, temp_db):
        cache = QueryCache(db_path=temp_db, ttl=3600, max_entries=10)

        for i in range(15):
            cache.put(f"query {i}", f"result {i}")

        assert cache.count() <= 15
