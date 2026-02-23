"""
RAG_HS_CODE - API Health Dashboard
Phase 7: Live Data Integration

Tracks external API availability, response times, error rates,
and trends over time. Powers a health dashboard in the UI.

SQLite-backed with a rolling 7-day window.
"""

import sqlite3
import time
import threading
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime


@dataclass
class APIHealthRecord:
    """A single health check record"""
    source: str
    timestamp: float
    response_time_ms: float
    status_code: int
    success: bool
    error_message: str = ""


class APIHealthDashboard:
    """
    Tracks and reports on external API health.

    Features:
    - Record API call outcomes (success/failure, response time, status code)
    - Calculate uptime percentage per source
    - Average response time with percentiles
    - Error rate tracking
    - Rolling 7-day data retention
    - Thread-safe SQLite storage
    """

    DEFAULT_RETENTION_DAYS = 7
    DB_FILENAME = "api_health.db"
    KNOWN_SOURCES = ["NBP", "SBP", "WEBOC", "TIPP", "OpenAI"]

    def __init__(self, db_path: Optional[str] = None,
                 retention_days: int = DEFAULT_RETENTION_DAYS):
        self.db_path = db_path or self.DB_FILENAME
        self.retention_days = retention_days
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS health_records (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        source TEXT NOT NULL,
                        timestamp REAL NOT NULL,
                        response_time_ms REAL NOT NULL,
                        status_code INTEGER NOT NULL,
                        success INTEGER NOT NULL,
                        error_message TEXT DEFAULT ''
                    )
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_source_time
                    ON health_records(source, timestamp)
                """)
                conn.commit()
            finally:
                conn.close()

    def record(self, source: str, response_time_ms: float,
               success: bool, status_code: int = 200,
               error: str = ""):
        """
        Record an API call outcome.

        Args:
            source: API source name (e.g., "NBP", "WEBOC")
            response_time_ms: Response time in milliseconds
            success: Whether the call succeeded
            status_code: HTTP status code
            error: Error message if failed
        """
        now = time.time()
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute(
                    "INSERT INTO health_records "
                    "(source, timestamp, response_time_ms, status_code, success, error_message) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (source, now, response_time_ms, status_code,
                     1 if success else 0, error)
                )
                conn.commit()
            finally:
                conn.close()

    def get_health(self, source: str, hours: int = 24) -> Dict[str, Any]:
        """
        Get health summary for a specific source.

        Args:
            source: API source name
            hours: Time window in hours (default 24h)

        Returns:
            Dict with uptime_pct, avg_response_ms, error_rate, last_check, status, total_checks
        """
        cutoff = time.time() - (hours * 3600)

        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.execute(
                    "SELECT response_time_ms, success, timestamp, error_message "
                    "FROM health_records "
                    "WHERE source = ? AND timestamp > ? "
                    "ORDER BY timestamp DESC",
                    (source, cutoff)
                )
                rows = cursor.fetchall()

                if not rows:
                    return {
                        "source": source,
                        "status": "unknown",
                        "uptime_pct": 0.0,
                        "avg_response_ms": 0.0,
                        "error_rate": 0.0,
                        "last_check": None,
                        "last_error": "",
                        "total_checks": 0,
                    }

                total = len(rows)
                successes = sum(1 for r in rows if r[1])
                response_times = [r[0] for r in rows if r[1]]
                avg_ms = sum(response_times) / len(response_times) if response_times else 0.0
                uptime = (successes / total * 100) if total > 0 else 0.0
                error_rate = ((total - successes) / total * 100) if total > 0 else 0.0

                last_timestamp = rows[0][2]
                last_error = ""
                for r in rows:
                    if not r[1] and r[3]:
                        last_error = r[3]
                        break

                # Determine status from recent checks
                recent = rows[:5] if len(rows) >= 5 else rows
                recent_successes = sum(1 for r in recent if r[1])

                if recent_successes == len(recent):
                    status = "online"
                elif recent_successes == 0:
                    status = "offline"
                elif avg_ms > 2000:
                    status = "slow"
                else:
                    status = "degraded"

                return {
                    "source": source,
                    "status": status,
                    "uptime_pct": round(uptime, 1),
                    "avg_response_ms": round(avg_ms, 1),
                    "error_rate": round(error_rate, 1),
                    "last_check": last_timestamp,
                    "last_check_display": self._format_age(last_timestamp),
                    "last_error": last_error,
                    "total_checks": total,
                }
            finally:
                conn.close()

    def get_all_health(self, hours: int = 24) -> Dict[str, Dict[str, Any]]:
        """Get health summary for all known sources."""
        return {source: self.get_health(source, hours) for source in self.KNOWN_SOURCES}

    def get_history(self, source: str, hours: int = 24) -> List[APIHealthRecord]:
        """
        Get time series health records for a source.

        Args:
            source: API source name
            hours: Time window

        Returns:
            List of APIHealthRecord objects (newest first)
        """
        cutoff = time.time() - (hours * 3600)

        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.execute(
                    "SELECT source, timestamp, response_time_ms, status_code, "
                    "success, error_message "
                    "FROM health_records "
                    "WHERE source = ? AND timestamp > ? "
                    "ORDER BY timestamp DESC",
                    (source, cutoff)
                )

                return [
                    APIHealthRecord(
                        source=row[0],
                        timestamp=row[1],
                        response_time_ms=row[2],
                        status_code=row[3],
                        success=bool(row[4]),
                        error_message=row[5] or ""
                    )
                    for row in cursor.fetchall()
                ]
            finally:
                conn.close()

    def cleanup_old(self, days: Optional[int] = None) -> int:
        """
        Remove records older than N days.

        Args:
            days: Days to retain (default: self.retention_days)

        Returns:
            Number of records deleted
        """
        days = days or self.retention_days
        cutoff = time.time() - (days * 86400)

        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.execute(
                    "DELETE FROM health_records WHERE timestamp < ?",
                    (cutoff,)
                )
                conn.commit()
                return cursor.rowcount
            finally:
                conn.close()

    def get_record_count(self, source: Optional[str] = None) -> int:
        """Get total number of health records."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                if source:
                    cursor = conn.execute(
                        "SELECT COUNT(*) FROM health_records WHERE source = ?",
                        (source,)
                    )
                else:
                    cursor = conn.execute("SELECT COUNT(*) FROM health_records")
                return cursor.fetchone()[0]
            finally:
                conn.close()

    @staticmethod
    def _format_age(timestamp: float) -> str:
        """Format a timestamp as relative age string."""
        age = time.time() - timestamp
        if age < 60:
            return f"{age:.0f}s ago"
        elif age < 3600:
            return f"{age / 60:.0f}m ago"
        elif age < 86400:
            return f"{age / 3600:.1f}h ago"
        else:
            return f"{age / 86400:.1f}d ago"
