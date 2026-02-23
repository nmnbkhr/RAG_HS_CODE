"""
RAG_HS_CODE - WEBOC Duty Data Cache Module
Phase 3: Performance & Caching

SQLite-based caching for WEBOC duty lookups with TTL.
"""

import sqlite3
import time
import json
import threading
from datetime import datetime
from typing import Dict, Optional, List, Any
from dataclasses import dataclass


@dataclass
class CachedDutyData:
    """Cached WEBOC duty data entry"""
    hs_code: str
    customs_duty: Optional[float]
    sales_tax: Optional[float]
    income_tax: Optional[float]
    additional_duty: Optional[float]
    regulatory_duty: Optional[float]
    federal_excise_duty: Optional[float]
    description: Optional[str]
    unit_of_measure: str
    source: str
    fetched_at: float
    expires_at: float

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

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary matching WEBOC scraper output format."""
        return {
            "hs_code": self.hs_code,
            "status": "success",
            "customs_duty": self.customs_duty,
            "sales_tax": self.sales_tax,
            "income_tax": self.income_tax,
            "additional_duty": self.additional_duty,
            "regulatory_duty": self.regulatory_duty,
            "federal_excise_duty": self.federal_excise_duty,
            "description": self.description,
            "unit_of_measure": self.unit_of_measure,
            "source": self.source,
            "cached": True,
            "cache_age": self.age_display
        }


class WEBOCCache:
    """
    SQLite-based cache for WEBOC duty data.

    Features:
    - Cache duty lookups by HS code
    - 24-hour TTL (duty rates change rarely)
    - Max 10,000 entries with LRU eviction
    - Thread-safe operations
    - Full duty data storage (CD, ST, IT, AD, RD, FED, description, UOM)
    """

    DEFAULT_TTL = 24 * 3600  # 24 hours
    MAX_ENTRIES = 10000
    DB_FILENAME = "weboc_cache.db"

    def __init__(self, db_path: Optional[str] = None, ttl: int = DEFAULT_TTL,
                 max_entries: int = MAX_ENTRIES):
        self.ttl = ttl
        self.max_entries = max_entries
        self.db_path = db_path or self.DB_FILENAME
        self._lock = threading.Lock()
        self._stats = {"hits": 0, "misses": 0, "updates": 0, "evictions": 0}
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS duty_data (
                        hs_code TEXT PRIMARY KEY,
                        customs_duty REAL,
                        sales_tax REAL,
                        income_tax REAL,
                        additional_duty REAL,
                        regulatory_duty REAL,
                        description TEXT,
                        unit_of_measure TEXT DEFAULT 'units',
                        source TEXT DEFAULT 'WEBOC',
                        fetched_at REAL NOT NULL,
                        expires_at REAL NOT NULL,
                        last_accessed REAL NOT NULL
                    )
                """)
                # Migration: add federal_excise_duty column if missing
                try:
                    conn.execute("ALTER TABLE duty_data ADD COLUMN federal_excise_duty REAL")
                except sqlite3.OperationalError:
                    pass  # Column already exists
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_expires ON duty_data(expires_at)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_accessed ON duty_data(last_accessed)
                """)
                conn.commit()
            finally:
                conn.close()

    def get(self, hs_code: str) -> Optional[CachedDutyData]:
        """
        Get cached duty data for HS code.

        Args:
            hs_code: HS code (e.g., '0808.1000')

        Returns:
            CachedDutyData if found and not expired, None otherwise
        """
        hs_code = self._normalize_code(hs_code)

        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.execute(
                    "SELECT hs_code, customs_duty, sales_tax, income_tax, "
                    "additional_duty, regulatory_duty, federal_excise_duty, "
                    "description, unit_of_measure, "
                    "source, fetched_at, expires_at "
                    "FROM duty_data WHERE hs_code = ?",
                    (hs_code,)
                )
                row = cursor.fetchone()

                if row is None:
                    self._stats["misses"] += 1
                    return None

                cached = CachedDutyData(
                    hs_code=row[0],
                    customs_duty=row[1],
                    sales_tax=row[2],
                    income_tax=row[3],
                    additional_duty=row[4],
                    regulatory_duty=row[5],
                    federal_excise_duty=row[6],
                    description=row[7],
                    unit_of_measure=row[8] or "units",
                    source=row[9] or "WEBOC",
                    fetched_at=row[10],
                    expires_at=row[11]
                )

                if cached.is_expired:
                    self._stats["misses"] += 1
                    return None

                # Update last accessed time
                conn.execute(
                    "UPDATE duty_data SET last_accessed = ? WHERE hs_code = ?",
                    (time.time(), hs_code)
                )
                conn.commit()

                self._stats["hits"] += 1
                return cached
            finally:
                conn.close()

    def get_or_fallback(self, hs_code: str) -> Optional[CachedDutyData]:
        """
        Get cached data, returning expired data as fallback.

        Args:
            hs_code: HS code

        Returns:
            CachedDutyData if any exists (may be expired), None if never cached
        """
        hs_code = self._normalize_code(hs_code)

        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.execute(
                    "SELECT hs_code, customs_duty, sales_tax, income_tax, "
                    "additional_duty, regulatory_duty, federal_excise_duty, "
                    "description, unit_of_measure, "
                    "source, fetched_at, expires_at "
                    "FROM duty_data WHERE hs_code = ?",
                    (hs_code,)
                )
                row = cursor.fetchone()

                if row is None:
                    return None

                return CachedDutyData(
                    hs_code=row[0],
                    customs_duty=row[1],
                    sales_tax=row[2],
                    income_tax=row[3],
                    additional_duty=row[4],
                    regulatory_duty=row[5],
                    federal_excise_duty=row[6],
                    description=row[7],
                    unit_of_measure=row[8] or "units",
                    source=row[9] or "WEBOC",
                    fetched_at=row[10],
                    expires_at=row[11]
                )
            finally:
                conn.close()

    def put(self, hs_code: str, duty_data: Dict[str, Any],
            source: str = "WEBOC") -> CachedDutyData:
        """
        Store duty data in cache.

        Args:
            hs_code: HS code
            duty_data: Dictionary with duty rates and metadata
            source: Data source name

        Returns:
            The created CachedDutyData entry
        """
        hs_code = self._normalize_code(hs_code)
        now = time.time()
        expires = now + self.ttl

        cached = CachedDutyData(
            hs_code=hs_code,
            customs_duty=duty_data.get("customs_duty"),
            sales_tax=duty_data.get("sales_tax"),
            income_tax=duty_data.get("income_tax"),
            additional_duty=duty_data.get("additional_duty"),
            regulatory_duty=duty_data.get("regulatory_duty"),
            federal_excise_duty=duty_data.get("federal_excise_duty"),
            description=duty_data.get("description"),
            unit_of_measure=duty_data.get("unit_of_measure", "units"),
            source=source,
            fetched_at=now,
            expires_at=expires
        )

        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                # Evict if at capacity
                self._evict_if_needed(conn)

                conn.execute(
                    "INSERT OR REPLACE INTO duty_data "
                    "(hs_code, customs_duty, sales_tax, income_tax, additional_duty, "
                    "regulatory_duty, federal_excise_duty, description, unit_of_measure, "
                    "source, fetched_at, expires_at, last_accessed) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (hs_code, cached.customs_duty, cached.sales_tax,
                     cached.income_tax, cached.additional_duty,
                     cached.regulatory_duty, cached.federal_excise_duty,
                     cached.description,
                     cached.unit_of_measure, source, now, expires, now)
                )
                conn.commit()
                self._stats["updates"] += 1
            finally:
                conn.close()

        return cached

    def _evict_if_needed(self, conn: sqlite3.Connection):
        """Evict oldest entries if cache exceeds max size."""
        cursor = conn.execute("SELECT COUNT(*) FROM duty_data")
        count = cursor.fetchone()[0]

        if count >= self.max_entries:
            # Remove 10% of oldest entries (LRU)
            to_remove = max(1, self.max_entries // 10)
            conn.execute(
                "DELETE FROM duty_data WHERE hs_code IN ("
                "  SELECT hs_code FROM duty_data ORDER BY last_accessed ASC LIMIT ?"
                ")",
                (to_remove,)
            )
            self._stats["evictions"] += to_remove

    def invalidate(self, hs_code: str) -> bool:
        """Remove a specific HS code from cache."""
        hs_code = self._normalize_code(hs_code)

        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.execute(
                    "DELETE FROM duty_data WHERE hs_code = ?",
                    (hs_code,)
                )
                conn.commit()
                return cursor.rowcount > 0
            finally:
                conn.close()

    def invalidate_all(self) -> int:
        """Clear all cached duty data."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.execute("DELETE FROM duty_data")
                conn.commit()
                return cursor.rowcount
            finally:
                conn.close()

    def cleanup_expired(self) -> int:
        """Remove all expired entries."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.execute(
                    "DELETE FROM duty_data WHERE expires_at < ?",
                    (time.time(),)
                )
                conn.commit()
                return cursor.rowcount
            finally:
                conn.close()

    def search(self, query: str, limit: int = 50) -> List[CachedDutyData]:
        """
        Search cached duty data by HS code prefix or description.

        Args:
            query: Search query (HS code prefix or description keyword)
            limit: Max results to return

        Returns:
            List of matching CachedDutyData entries
        """
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.execute(
                    "SELECT hs_code, customs_duty, sales_tax, income_tax, "
                    "additional_duty, regulatory_duty, federal_excise_duty, "
                    "description, unit_of_measure, "
                    "source, fetched_at, expires_at "
                    "FROM duty_data "
                    "WHERE hs_code LIKE ? OR description LIKE ? "
                    "ORDER BY last_accessed DESC LIMIT ?",
                    (f"{query}%", f"%{query}%", limit)
                )

                results = []
                for row in cursor.fetchall():
                    results.append(CachedDutyData(
                        hs_code=row[0],
                        customs_duty=row[1],
                        sales_tax=row[2],
                        income_tax=row[3],
                        additional_duty=row[4],
                        regulatory_duty=row[5],
                        federal_excise_duty=row[6],
                        description=row[7],
                        unit_of_measure=row[8] or "units",
                        source=row[9] or "WEBOC",
                        fetched_at=row[10],
                        expires_at=row[11]
                    ))
                return results
            finally:
                conn.close()

    def count(self) -> int:
        """Get number of cached entries."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.execute("SELECT COUNT(*) FROM duty_data")
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
            "entries": self.count()
        }

    def reset_stats(self):
        """Reset cache statistics."""
        self._stats = {"hits": 0, "misses": 0, "updates": 0, "evictions": 0}

    @staticmethod
    def _normalize_code(hs_code: str) -> str:
        """Normalize HS code for consistent cache keys."""
        import re
        hs_code = hs_code.strip()
        digits = re.sub(r'\D', '', hs_code)
        if len(digits) >= 8:
            return f"{digits[:4]}.{digits[4:8]}"
        elif len(digits) >= 4:
            return f"{digits[:4]}.{digits[4:].ljust(4, '0')}"
        return hs_code
