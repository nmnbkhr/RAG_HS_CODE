"""
RAG_HS_CODE - HS Code Favorites Manager
Phase 4: Features

Persistent storage for frequently used HS codes with notes and tags.
"""

import sqlite3
import time
import json
import re
import threading
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field


@dataclass
class Favorite:
    """A bookmarked HS code"""
    id: int
    hs_code: str
    description: str
    notes: str = ""
    tags: List[str] = field(default_factory=list)
    customs_duty_rate: Optional[float] = None
    sales_tax_rate: Optional[float] = None
    income_tax_rate: Optional[float] = None
    unit_of_measure: str = "kg"
    created_at: str = ""
    updated_at: str = ""
    use_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "hs_code": self.hs_code,
            "description": self.description,
            "notes": self.notes,
            "tags": self.tags,
            "rates": {
                "customs_duty": self.customs_duty_rate,
                "sales_tax": self.sales_tax_rate,
                "income_tax": self.income_tax_rate
            },
            "unit_of_measure": self.unit_of_measure,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "use_count": self.use_count
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Favorite':
        rates = data.get("rates", {})
        return cls(
            id=data.get("id", 0),
            hs_code=data.get("hs_code", ""),
            description=data.get("description", ""),
            notes=data.get("notes", ""),
            tags=data.get("tags", []),
            customs_duty_rate=rates.get("customs_duty"),
            sales_tax_rate=rates.get("sales_tax"),
            income_tax_rate=rates.get("income_tax"),
            unit_of_measure=data.get("unit_of_measure", "kg"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            use_count=data.get("use_count", 0)
        )


class FavoritesManager:
    """
    SQLite-backed persistent storage for HS code favorites.

    Features:
    - Add/remove/update favorites
    - Search by code, description, tags, notes
    - Track usage count
    - Import/export as JSON
    - Maximum 500 entries
    - Thread-safe operations
    """

    MAX_FAVORITES = 500
    DB_FILENAME = "favorites.db"

    def __init__(self, db_path: Optional[str] = None,
                 max_favorites: int = MAX_FAVORITES):
        self.db_path = db_path or self.DB_FILENAME
        self.max_favorites = max_favorites
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS favorites (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        hs_code TEXT NOT NULL,
                        description TEXT NOT NULL DEFAULT '',
                        notes TEXT DEFAULT '',
                        tags TEXT DEFAULT '[]',
                        customs_duty_rate REAL,
                        sales_tax_rate REAL,
                        income_tax_rate REAL,
                        unit_of_measure TEXT DEFAULT 'kg',
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        use_count INTEGER DEFAULT 0,
                        UNIQUE(hs_code)
                    )
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_fav_hs ON favorites(hs_code)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_fav_use ON favorites(use_count DESC)
                """)
                conn.commit()
            finally:
                conn.close()

    def add(
        self,
        hs_code: str,
        description: str = "",
        notes: str = "",
        tags: Optional[List[str]] = None,
        customs_duty_rate: Optional[float] = None,
        sales_tax_rate: Optional[float] = None,
        income_tax_rate: Optional[float] = None,
        unit_of_measure: str = "kg"
    ) -> Optional[Favorite]:
        """
        Add an HS code to favorites.

        Args:
            hs_code: HS code (will be normalized)
            description: Item description
            notes: User notes
            tags: List of tag strings
            customs_duty_rate: Known CD rate
            sales_tax_rate: Known ST rate
            income_tax_rate: Known IT rate
            unit_of_measure: Unit

        Returns:
            Created Favorite, or None if at capacity
        """
        hs_code = self._normalize_code(hs_code)
        now = datetime.now().isoformat()
        tags = tags or []

        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                # Check capacity
                cursor = conn.execute("SELECT COUNT(*) FROM favorites")
                count = cursor.fetchone()[0]

                # Check if already exists (update instead)
                existing = conn.execute(
                    "SELECT id FROM favorites WHERE hs_code = ?",
                    (hs_code,)
                ).fetchone()

                if existing:
                    # Update existing
                    conn.execute(
                        "UPDATE favorites SET description=?, notes=?, tags=?, "
                        "customs_duty_rate=?, sales_tax_rate=?, income_tax_rate=?, "
                        "unit_of_measure=?, updated_at=? WHERE hs_code=?",
                        (description, notes, json.dumps(tags),
                         customs_duty_rate, sales_tax_rate, income_tax_rate,
                         unit_of_measure, now, hs_code)
                    )
                    conn.commit()
                    fav_id = existing[0]
                elif count >= self.max_favorites:
                    return None  # At capacity
                else:
                    cursor = conn.execute(
                        "INSERT INTO favorites "
                        "(hs_code, description, notes, tags, customs_duty_rate, "
                        "sales_tax_rate, income_tax_rate, unit_of_measure, "
                        "created_at, updated_at, use_count) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)",
                        (hs_code, description, notes, json.dumps(tags),
                         customs_duty_rate, sales_tax_rate, income_tax_rate,
                         unit_of_measure, now, now)
                    )
                    conn.commit()
                    fav_id = cursor.lastrowid

                return Favorite(
                    id=fav_id,
                    hs_code=hs_code,
                    description=description,
                    notes=notes,
                    tags=tags,
                    customs_duty_rate=customs_duty_rate,
                    sales_tax_rate=sales_tax_rate,
                    income_tax_rate=income_tax_rate,
                    unit_of_measure=unit_of_measure,
                    created_at=now,
                    updated_at=now,
                    use_count=0
                )
            finally:
                conn.close()

    def get(self, hs_code: str) -> Optional[Favorite]:
        """Get a favorite by HS code."""
        hs_code = self._normalize_code(hs_code)

        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.execute(
                    "SELECT * FROM favorites WHERE hs_code = ?",
                    (hs_code,)
                )
                row = cursor.fetchone()
                return self._row_to_favorite(row) if row else None
            finally:
                conn.close()

    def get_by_id(self, fav_id: int) -> Optional[Favorite]:
        """Get a favorite by ID."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.execute(
                    "SELECT * FROM favorites WHERE id = ?",
                    (fav_id,)
                )
                row = cursor.fetchone()
                return self._row_to_favorite(row) if row else None
            finally:
                conn.close()

    def remove(self, hs_code: str) -> bool:
        """Remove a favorite by HS code."""
        hs_code = self._normalize_code(hs_code)

        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.execute(
                    "DELETE FROM favorites WHERE hs_code = ?",
                    (hs_code,)
                )
                conn.commit()
                return cursor.rowcount > 0
            finally:
                conn.close()

    def get_all(self, order_by: str = "use_count") -> List[Favorite]:
        """
        Get all favorites.

        Args:
            order_by: Sort field ('use_count', 'created_at', 'hs_code')
        """
        valid_orders = {
            "use_count": "use_count DESC",
            "created_at": "created_at DESC",
            "hs_code": "hs_code ASC",
            "updated_at": "updated_at DESC"
        }
        order_clause = valid_orders.get(order_by, "use_count DESC")

        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.execute(
                    f"SELECT * FROM favorites ORDER BY {order_clause}"
                )
                return [self._row_to_favorite(row) for row in cursor.fetchall()]
            finally:
                conn.close()

    def search(self, query: str, limit: int = 50) -> List[Favorite]:
        """
        Search favorites by HS code, description, notes, or tags.

        Args:
            query: Search string
            limit: Max results

        Returns:
            Matching favorites
        """
        query_lower = f"%{query.lower()}%"

        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.execute(
                    "SELECT * FROM favorites WHERE "
                    "LOWER(hs_code) LIKE ? OR LOWER(description) LIKE ? "
                    "OR LOWER(notes) LIKE ? OR LOWER(tags) LIKE ? "
                    "ORDER BY use_count DESC LIMIT ?",
                    (query_lower, query_lower, query_lower, query_lower, limit)
                )
                return [self._row_to_favorite(row) for row in cursor.fetchall()]
            finally:
                conn.close()

    def get_by_tag(self, tag: str) -> List[Favorite]:
        """Get favorites with a specific tag."""
        tag_pattern = f'%"{tag}"%'

        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.execute(
                    "SELECT * FROM favorites WHERE tags LIKE ? ORDER BY use_count DESC",
                    (tag_pattern,)
                )
                return [self._row_to_favorite(row) for row in cursor.fetchall()]
            finally:
                conn.close()

    def record_use(self, hs_code: str) -> bool:
        """Increment use count for a favorite."""
        hs_code = self._normalize_code(hs_code)

        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.execute(
                    "UPDATE favorites SET use_count = use_count + 1, "
                    "updated_at = ? WHERE hs_code = ?",
                    (datetime.now().isoformat(), hs_code)
                )
                conn.commit()
                return cursor.rowcount > 0
            finally:
                conn.close()

    def is_favorite(self, hs_code: str) -> bool:
        """Check if an HS code is in favorites."""
        hs_code = self._normalize_code(hs_code)

        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM favorites WHERE hs_code = ?",
                    (hs_code,)
                )
                return cursor.fetchone()[0] > 0
            finally:
                conn.close()

    def count(self) -> int:
        """Get total number of favorites."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.execute("SELECT COUNT(*) FROM favorites")
                return cursor.fetchone()[0]
            finally:
                conn.close()

    def clear(self) -> int:
        """Remove all favorites."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.execute("DELETE FROM favorites")
                conn.commit()
                return cursor.rowcount
            finally:
                conn.close()

    def get_most_used(self, limit: int = 10) -> List[Favorite]:
        """Get most frequently used favorites."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.execute(
                    "SELECT * FROM favorites WHERE use_count > 0 "
                    "ORDER BY use_count DESC LIMIT ?",
                    (limit,)
                )
                return [self._row_to_favorite(row) for row in cursor.fetchall()]
            finally:
                conn.close()

    def export_json(self) -> str:
        """Export all favorites as JSON string."""
        favorites = self.get_all(order_by="hs_code")
        data = {
            "version": "1.0",
            "exported_at": datetime.now().isoformat(),
            "count": len(favorites),
            "favorites": [f.to_dict() for f in favorites]
        }
        return json.dumps(data, indent=2)

    def import_json(self, json_str: str) -> Tuple[int, int]:
        """
        Import favorites from JSON string.

        Args:
            json_str: JSON string with favorites data

        Returns:
            Tuple of (imported_count, skipped_count)
        """
        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            return 0, 0

        favorites_data = data.get("favorites", [])
        imported = 0
        skipped = 0

        for fav_data in favorites_data:
            rates = fav_data.get("rates", {})
            result = self.add(
                hs_code=fav_data.get("hs_code", ""),
                description=fav_data.get("description", ""),
                notes=fav_data.get("notes", ""),
                tags=fav_data.get("tags", []),
                customs_duty_rate=rates.get("customs_duty"),
                sales_tax_rate=rates.get("sales_tax"),
                income_tax_rate=rates.get("income_tax"),
                unit_of_measure=fav_data.get("unit_of_measure", "kg")
            )
            if result:
                imported += 1
            else:
                skipped += 1

        return imported, skipped

    def get_all_tags(self) -> List[str]:
        """Get all unique tags across all favorites."""
        favorites = self.get_all()
        all_tags = set()
        for fav in favorites:
            all_tags.update(fav.tags)
        return sorted(all_tags)

    def _row_to_favorite(self, row) -> Favorite:
        """Convert a database row to a Favorite object."""
        tags_str = row[4] or "[]"
        try:
            tags = json.loads(tags_str)
        except json.JSONDecodeError:
            tags = []

        return Favorite(
            id=row[0],
            hs_code=row[1],
            description=row[2],
            notes=row[3] or "",
            tags=tags,
            customs_duty_rate=row[5],
            sales_tax_rate=row[6],
            income_tax_rate=row[7],
            unit_of_measure=row[8] or "kg",
            created_at=row[9],
            updated_at=row[10],
            use_count=row[11] or 0
        )

    @staticmethod
    def _normalize_code(hs_code: str) -> str:
        """Normalize HS code for consistent storage."""
        hs_code = hs_code.strip()
        digits = re.sub(r'\D', '', hs_code)
        if len(digits) >= 8:
            return f"{digits[:4]}.{digits[4:8]}"
        elif len(digits) >= 4:
            return f"{digits[:4]}.{digits[4:].ljust(4, '0')}"
        return hs_code
