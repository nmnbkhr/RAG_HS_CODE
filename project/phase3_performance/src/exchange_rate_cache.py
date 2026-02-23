"""
RAG_HS_CODE - Exchange Rate Cache Module
Phase 3: Performance & Caching

SQLite-based caching for exchange rates with TTL and fallback support.
"""

import sqlite3
import time
import json
import os
import threading
from datetime import datetime
from typing import Dict, Optional, Tuple, Any
from dataclasses import dataclass, asdict


@dataclass
class CachedRate:
    """Cached exchange rate entry"""
    currency: str
    tt_buying: float
    tt_selling: float
    source: str
    fetched_at: float  # Unix timestamp
    expires_at: float  # Unix timestamp

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    @property
    def age_seconds(self) -> float:
        return time.time() - self.fetched_at

    @property
    def age_display(self) -> str:
        age = self.age_seconds
        if age < 60:
            return f"{age:.0f}s ago"
        elif age < 3600:
            return f"{age / 60:.0f}m ago"
        else:
            return f"{age / 3600:.1f}h ago"


class ExchangeRateCache:
    """
    SQLite-based exchange rate cache with TTL.

    Features:
    - Persistent cache across app restarts
    - Configurable TTL (default 4 hours)
    - Thread-safe operations
    - Fallback to last known rate on fetch failure
    - Cache statistics
    """

    DEFAULT_TTL = 4 * 3600  # 4 hours in seconds
    DB_FILENAME = "exchange_rate_cache.db"

    def __init__(self, db_path: Optional[str] = None, ttl: int = DEFAULT_TTL):
        """
        Initialize exchange rate cache.

        Args:
            db_path: Path to SQLite database. Defaults to current directory.
            ttl: Time-to-live in seconds for cached rates.
        """
        self.ttl = ttl
        self.db_path = db_path or self.DB_FILENAME
        self._lock = threading.Lock()
        self._stats = {"hits": 0, "misses": 0, "updates": 0, "fallbacks": 0}
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database and create table if needed."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS exchange_rates (
                        currency TEXT PRIMARY KEY,
                        tt_buying REAL NOT NULL,
                        tt_selling REAL NOT NULL,
                        source TEXT NOT NULL,
                        fetched_at REAL NOT NULL,
                        expires_at REAL NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS cache_stats (
                        key TEXT PRIMARY KEY,
                        value INTEGER DEFAULT 0
                    )
                """)
                conn.commit()
            finally:
                conn.close()

    def get(self, currency: str) -> Optional[CachedRate]:
        """
        Get cached exchange rate for currency.

        Args:
            currency: Currency code (e.g., 'USD')

        Returns:
            CachedRate if found and not expired, None otherwise
        """
        currency = currency.upper()

        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.execute(
                    "SELECT currency, tt_buying, tt_selling, source, fetched_at, expires_at "
                    "FROM exchange_rates WHERE currency = ?",
                    (currency,)
                )
                row = cursor.fetchone()

                if row is None:
                    self._stats["misses"] += 1
                    return None

                cached = CachedRate(
                    currency=row[0],
                    tt_buying=row[1],
                    tt_selling=row[2],
                    source=row[3],
                    fetched_at=row[4],
                    expires_at=row[5]
                )

                if cached.is_expired:
                    self._stats["misses"] += 1
                    return None

                self._stats["hits"] += 1
                return cached
            finally:
                conn.close()

    def get_or_fallback(self, currency: str) -> Optional[CachedRate]:
        """
        Get cached rate, or return expired rate as fallback.

        Returns the cached rate even if expired (for offline/fallback use).
        The caller should check is_expired to determine freshness.

        Args:
            currency: Currency code

        Returns:
            CachedRate if any exists (may be expired), None if never cached
        """
        currency = currency.upper()

        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.execute(
                    "SELECT currency, tt_buying, tt_selling, source, fetched_at, expires_at "
                    "FROM exchange_rates WHERE currency = ?",
                    (currency,)
                )
                row = cursor.fetchone()

                if row is None:
                    return None

                cached = CachedRate(
                    currency=row[0],
                    tt_buying=row[1],
                    tt_selling=row[2],
                    source=row[3],
                    fetched_at=row[4],
                    expires_at=row[5]
                )

                if cached.is_expired:
                    self._stats["fallbacks"] += 1
                else:
                    self._stats["hits"] += 1

                return cached
            finally:
                conn.close()

    def put(self, currency: str, tt_buying: float, tt_selling: float,
            source: str = "NBP") -> CachedRate:
        """
        Store exchange rate in cache.

        Args:
            currency: Currency code
            tt_buying: TT Buying rate (export)
            tt_selling: TT Selling rate (import)
            source: Rate source description

        Returns:
            The created CachedRate entry
        """
        currency = currency.upper()
        now = time.time()
        expires = now + self.ttl

        cached = CachedRate(
            currency=currency,
            tt_buying=tt_buying,
            tt_selling=tt_selling,
            source=source,
            fetched_at=now,
            expires_at=expires
        )

        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO exchange_rates "
                    "(currency, tt_buying, tt_selling, source, fetched_at, expires_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (currency, tt_buying, tt_selling, source, now, expires,
                     datetime.now().isoformat())
                )
                conn.commit()
                self._stats["updates"] += 1
            finally:
                conn.close()

        return cached

    def invalidate(self, currency: str) -> bool:
        """
        Remove a currency from cache.

        Args:
            currency: Currency code to invalidate

        Returns:
            True if entry was removed, False if not found
        """
        currency = currency.upper()

        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.execute(
                    "DELETE FROM exchange_rates WHERE currency = ?",
                    (currency,)
                )
                conn.commit()
                return cursor.rowcount > 0
            finally:
                conn.close()

    def invalidate_all(self) -> int:
        """
        Clear all cached rates.

        Returns:
            Number of entries removed
        """
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.execute("DELETE FROM exchange_rates")
                conn.commit()
                return cursor.rowcount
            finally:
                conn.close()

    def get_all(self) -> list:
        """Get all cached rates (including expired)."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.execute(
                    "SELECT currency, tt_buying, tt_selling, source, fetched_at, expires_at "
                    "FROM exchange_rates ORDER BY currency"
                )
                results = []
                for row in cursor.fetchall():
                    results.append(CachedRate(
                        currency=row[0],
                        tt_buying=row[1],
                        tt_selling=row[2],
                        source=row[3],
                        fetched_at=row[4],
                        expires_at=row[5]
                    ))
                return results
            finally:
                conn.close()

    def needs_refresh(self, currency: str, threshold: float = 0.75) -> bool:
        """
        Check if a cached rate should be proactively refreshed.

        Returns True if the rate is past the threshold percentage of its TTL.
        Useful for background refresh before expiry.

        Args:
            currency: Currency code
            threshold: Fraction of TTL after which refresh is recommended (0.0-1.0)

        Returns:
            True if refresh recommended
        """
        cached = self.get_or_fallback(currency.upper())
        if cached is None:
            return True

        age = cached.age_seconds
        return age > (self.ttl * threshold)

    @property
    def stats(self) -> Dict[str, int]:
        """Get cache statistics."""
        total = self._stats["hits"] + self._stats["misses"]
        hit_rate = (self._stats["hits"] / total * 100) if total > 0 else 0.0

        return {
            **self._stats,
            "total_requests": total,
            "hit_rate_pct": round(hit_rate, 1)
        }

    def reset_stats(self):
        """Reset cache statistics."""
        self._stats = {"hits": 0, "misses": 0, "updates": 0, "fallbacks": 0}

    def close(self):
        """Clean up resources."""
        pass  # SQLite connections are opened/closed per operation

    def __del__(self):
        self.close()


def get_cached_exchange_rate(
    currency: str,
    transaction_type: str = "import",
    fetch_fn=None,
    cache: Optional[ExchangeRateCache] = None,
    db_path: Optional[str] = None
) -> Tuple[float, str]:
    """
    Get exchange rate with caching.

    This is the main entry point that replaces direct API calls.
    It checks the cache first, then falls back to fetching.

    Args:
        currency: Currency code (e.g., 'USD')
        transaction_type: 'import' (TT Selling) or 'export' (TT Buying)
        fetch_fn: Function to fetch fresh rates. Should return dict with
                  'tt_buying' and 'tt_selling' keys.
        cache: Optional ExchangeRateCache instance
        db_path: Optional database path

    Returns:
        Tuple of (rate, source_description)
    """
    currency = currency.upper()

    if currency == "PKR":
        return 1.0, "PKR (no conversion)"

    if cache is None:
        cache = ExchangeRateCache(db_path=db_path)

    # Try cache first
    cached = cache.get(currency)
    if cached is not None:
        rate = cached.tt_buying if transaction_type == "export" else cached.tt_selling
        rate_type = "TT Buying" if transaction_type == "export" else "TT Selling"
        return rate, f"{cached.source} {rate_type} (Cached {cached.age_display})"

    # Cache miss - fetch fresh rates
    if fetch_fn is not None:
        try:
            rates = fetch_fn()
            if rates and (rates.get("tt_buying") or rates.get("tt_selling")):
                tt_buying = rates.get("tt_buying", 0)
                tt_selling = rates.get("tt_selling", 0)

                # Fill in missing rate from the other
                if not tt_selling and tt_buying:
                    tt_selling = tt_buying + 2.0
                if not tt_buying and tt_selling:
                    tt_buying = tt_selling - 2.0

                cache.put(currency, tt_buying, tt_selling, "NBP")

                rate = tt_buying if transaction_type == "export" else tt_selling
                rate_type = "TT Buying" if transaction_type == "export" else "TT Selling"
                return rate, f"NBP {rate_type} (Live)"
        except Exception:
            pass

    # Fetch failed - try fallback (expired cache)
    fallback = cache.get_or_fallback(currency)
    if fallback is not None:
        rate = fallback.tt_buying if transaction_type == "export" else fallback.tt_selling
        rate_type = "TT Buying" if transaction_type == "export" else "TT Selling"
        return rate, f"{fallback.source} {rate_type} (Cached - stale {fallback.age_display})"

    # No cache at all - return hardcoded fallback
    if currency == "USD":
        rate = 278.50 if transaction_type == "export" else 280.50
        rate_type = "TT Buying" if transaction_type == "export" else "TT Selling"
        return rate, f"Estimated {rate_type} (No cache)"

    return 1.0, "Default (unknown currency)"
