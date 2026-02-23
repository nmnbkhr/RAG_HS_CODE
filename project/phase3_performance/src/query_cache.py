"""
RAG_HS_CODE - RAG Query Cache Module
Phase 3: Performance & Caching

In-memory + SQLite caching for RAG query results with TTL.
"""

import sqlite3
import time
import hashlib
import re
import json
import threading
from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class CachedQuery:
    """Cached RAG query result"""
    query_hash: str
    original_query: str
    normalized_query: str
    result: str
    fetched_at: float
    expires_at: float

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    @property
    def age_seconds(self) -> float:
        return time.time() - self.fetched_at


class QueryCache:
    """
    Cache for RAG query results.

    Features:
    - Query normalization for deduplication
    - SQLite persistence
    - TTL-based expiration (12 hours default)
    - Max 1,000 entries with LRU eviction
    - In-memory hot cache for fastest access
    """

    DEFAULT_TTL = 12 * 3600  # 12 hours
    MAX_ENTRIES = 1000
    HOT_CACHE_SIZE = 100
    DB_FILENAME = "query_cache.db"

    def __init__(self, db_path: Optional[str] = None, ttl: int = DEFAULT_TTL,
                 max_entries: int = MAX_ENTRIES):
        self.ttl = ttl
        self.max_entries = max_entries
        self.db_path = db_path or self.DB_FILENAME
        self._lock = threading.Lock()
        self._hot_cache: Dict[str, CachedQuery] = {}
        self._stats = {"hits": 0, "misses": 0, "hot_hits": 0, "updates": 0}
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS query_cache (
                        query_hash TEXT PRIMARY KEY,
                        original_query TEXT NOT NULL,
                        normalized_query TEXT NOT NULL,
                        result TEXT NOT NULL,
                        fetched_at REAL NOT NULL,
                        expires_at REAL NOT NULL,
                        last_accessed REAL NOT NULL,
                        access_count INTEGER DEFAULT 1
                    )
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_query_expires
                    ON query_cache(expires_at)
                """)
                conn.commit()
            finally:
                conn.close()

    @staticmethod
    def normalize_query(query: str) -> str:
        """
        Normalize a query string for deduplication.

        Handles:
        - Case normalization
        - Whitespace normalization
        - HS code format normalization
        - Common synonym replacement
        """
        q = query.lower().strip()
        q = re.sub(r'\s+', ' ', q)

        # Normalize HS code references
        q = re.sub(r'hs\s*code\s*', 'hs code ', q)
        q = re.sub(r'pct\s*code\s*', 'hs code ', q)

        # Normalize HS code format within query
        def normalize_hs(match):
            digits = re.sub(r'\D', '', match.group(0))
            if len(digits) >= 8:
                return f"{digits[:4]}.{digits[4:8]}"
            return match.group(0)

        q = re.sub(r'\d{4}\.?\d{2,4}', normalize_hs, q)

        return q

    @staticmethod
    def hash_query(normalized_query: str) -> str:
        """Create a hash of the normalized query."""
        return hashlib.sha256(normalized_query.encode()).hexdigest()[:16]

    def get(self, query: str) -> Optional[str]:
        """
        Get cached result for a query.

        Args:
            query: The RAG query string

        Returns:
            Cached result string if found and not expired, None otherwise
        """
        normalized = self.normalize_query(query)
        query_hash = self.hash_query(normalized)

        # Check hot cache first
        if query_hash in self._hot_cache:
            cached = self._hot_cache[query_hash]
            if not cached.is_expired:
                self._stats["hot_hits"] += 1
                self._stats["hits"] += 1
                return cached.result
            else:
                del self._hot_cache[query_hash]

        # Check SQLite cache
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.execute(
                    "SELECT query_hash, original_query, normalized_query, result, "
                    "fetched_at, expires_at "
                    "FROM query_cache WHERE query_hash = ?",
                    (query_hash,)
                )
                row = cursor.fetchone()

                if row is None:
                    self._stats["misses"] += 1
                    return None

                cached = CachedQuery(
                    query_hash=row[0],
                    original_query=row[1],
                    normalized_query=row[2],
                    result=row[3],
                    fetched_at=row[4],
                    expires_at=row[5]
                )

                if cached.is_expired:
                    self._stats["misses"] += 1
                    return None

                # Update access time and count
                conn.execute(
                    "UPDATE query_cache SET last_accessed = ?, access_count = access_count + 1 "
                    "WHERE query_hash = ?",
                    (time.time(), query_hash)
                )
                conn.commit()

                # Promote to hot cache
                self._promote_to_hot_cache(cached)

                self._stats["hits"] += 1
                return cached.result
            finally:
                conn.close()

    def put(self, query: str, result: str) -> CachedQuery:
        """
        Store a query result in cache.

        Args:
            query: The original query string
            result: The RAG result to cache

        Returns:
            The created CachedQuery entry
        """
        normalized = self.normalize_query(query)
        query_hash = self.hash_query(normalized)
        now = time.time()
        expires = now + self.ttl

        cached = CachedQuery(
            query_hash=query_hash,
            original_query=query,
            normalized_query=normalized,
            result=result,
            fetched_at=now,
            expires_at=expires
        )

        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                # Evict if at capacity
                self._evict_if_needed(conn)

                conn.execute(
                    "INSERT OR REPLACE INTO query_cache "
                    "(query_hash, original_query, normalized_query, result, "
                    "fetched_at, expires_at, last_accessed, access_count) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, 1)",
                    (query_hash, query, normalized, result, now, expires, now)
                )
                conn.commit()
                self._stats["updates"] += 1
            finally:
                conn.close()

        # Add to hot cache
        self._promote_to_hot_cache(cached)

        return cached

    def _promote_to_hot_cache(self, cached: CachedQuery):
        """Add entry to hot cache, evicting oldest if full."""
        if len(self._hot_cache) >= self.HOT_CACHE_SIZE:
            # Remove oldest entry
            oldest_key = min(self._hot_cache,
                           key=lambda k: self._hot_cache[k].fetched_at)
            del self._hot_cache[oldest_key]

        self._hot_cache[cached.query_hash] = cached

    def _evict_if_needed(self, conn: sqlite3.Connection):
        """Evict oldest entries if cache exceeds max size."""
        cursor = conn.execute("SELECT COUNT(*) FROM query_cache")
        count = cursor.fetchone()[0]

        if count >= self.max_entries:
            to_remove = max(1, self.max_entries // 10)
            conn.execute(
                "DELETE FROM query_cache WHERE query_hash IN ("
                "  SELECT query_hash FROM query_cache ORDER BY last_accessed ASC LIMIT ?"
                ")",
                (to_remove,)
            )

    def invalidate_all(self) -> int:
        """Clear all cached queries."""
        self._hot_cache.clear()
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.execute("DELETE FROM query_cache")
                conn.commit()
                return cursor.rowcount
            finally:
                conn.close()

    def cleanup_expired(self) -> int:
        """Remove all expired entries."""
        # Clean hot cache
        expired_keys = [k for k, v in self._hot_cache.items() if v.is_expired]
        for k in expired_keys:
            del self._hot_cache[k]

        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.execute(
                    "DELETE FROM query_cache WHERE expires_at < ?",
                    (time.time(),)
                )
                conn.commit()
                return cursor.rowcount + len(expired_keys)
            finally:
                conn.close()

    def count(self) -> int:
        """Get number of cached entries."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.execute("SELECT COUNT(*) FROM query_cache")
                return cursor.fetchone()[0]
            finally:
                conn.close()

    @property
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = (self._stats["hits"] / total * 100) if total > 0 else 0.0

        return {
            **self._stats,
            "total_requests": total,
            "hit_rate_pct": round(hit_rate, 1),
            "entries": self.count(),
            "hot_cache_size": len(self._hot_cache)
        }

    def reset_stats(self):
        """Reset cache statistics."""
        self._stats = {"hits": 0, "misses": 0, "hot_hits": 0, "updates": 0}
