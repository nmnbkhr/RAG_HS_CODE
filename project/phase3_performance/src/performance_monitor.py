"""
RAG_HS_CODE - Performance Monitor Module
Phase 3: Performance & Caching

Tracks response times and provides statistics for all operations.
"""

import time
import threading
import statistics
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict
from contextlib import contextmanager


@dataclass
class TimingRecord:
    """A single timing measurement"""
    operation: str
    duration_ms: float
    timestamp: float
    success: bool = True
    metadata: Optional[Dict[str, Any]] = None


class PerformanceMonitor:
    """
    Tracks response times and provides statistics.

    Features:
    - Track timing for named operations
    - Context manager for easy timing
    - Statistics: avg, p50, p95, p99, min, max
    - Slow query detection and logging
    - Per-operation breakdowns
    - Rolling window (last N records per operation)
    """

    SLOW_THRESHOLD_MS = 2000  # 2 seconds
    MAX_RECORDS_PER_OP = 1000

    def __init__(self, slow_threshold_ms: float = SLOW_THRESHOLD_MS,
                 max_records: int = MAX_RECORDS_PER_OP):
        self.slow_threshold_ms = slow_threshold_ms
        self.max_records = max_records
        self._records: Dict[str, List[TimingRecord]] = defaultdict(list)
        self._slow_queries: List[TimingRecord] = []
        self._lock = threading.Lock()

    @contextmanager
    def track(self, operation: str, metadata: Optional[Dict[str, Any]] = None):
        """
        Context manager to track operation timing.

        Usage:
            with monitor.track("weboc_search", {"hs_code": "0808.1000"}):
                result = scraper.search_hs_code("0808.1000")

        Args:
            operation: Name of the operation being tracked
            metadata: Optional metadata about the operation
        """
        start = time.time()
        success = True
        try:
            yield
        except Exception:
            success = False
            raise
        finally:
            duration_ms = (time.time() - start) * 1000
            self.record(operation, duration_ms, success, metadata)

    def record(self, operation: str, duration_ms: float,
               success: bool = True, metadata: Optional[Dict[str, Any]] = None):
        """
        Record a timing measurement.

        Args:
            operation: Name of the operation
            duration_ms: Duration in milliseconds
            success: Whether the operation succeeded
            metadata: Optional metadata
        """
        record = TimingRecord(
            operation=operation,
            duration_ms=duration_ms,
            timestamp=time.time(),
            success=success,
            metadata=metadata
        )

        with self._lock:
            records = self._records[operation]
            records.append(record)

            # Rolling window - keep last N records
            if len(records) > self.max_records:
                self._records[operation] = records[-self.max_records:]

            # Track slow queries
            if duration_ms > self.slow_threshold_ms:
                self._slow_queries.append(record)
                if len(self._slow_queries) > 100:
                    self._slow_queries = self._slow_queries[-100:]

    def get_stats(self, operation: str) -> Dict[str, Any]:
        """
        Get statistics for a specific operation.

        Args:
            operation: Name of the operation

        Returns:
            Dictionary with timing statistics
        """
        with self._lock:
            records = self._records.get(operation, [])

        if not records:
            return {
                "operation": operation,
                "count": 0,
                "avg_ms": 0,
                "min_ms": 0,
                "max_ms": 0,
                "p50_ms": 0,
                "p95_ms": 0,
                "p99_ms": 0,
                "success_rate": 0,
                "slow_count": 0
            }

        durations = [r.duration_ms for r in records]
        successful = [r for r in records if r.success]
        slow = [r for r in records if r.duration_ms > self.slow_threshold_ms]

        sorted_durations = sorted(durations)
        n = len(sorted_durations)

        return {
            "operation": operation,
            "count": n,
            "avg_ms": round(statistics.mean(durations), 2),
            "min_ms": round(min(durations), 2),
            "max_ms": round(max(durations), 2),
            "p50_ms": round(sorted_durations[n // 2], 2),
            "p95_ms": round(sorted_durations[int(n * 0.95)], 2) if n >= 20 else round(max(durations), 2),
            "p99_ms": round(sorted_durations[int(n * 0.99)], 2) if n >= 100 else round(max(durations), 2),
            "success_rate": round(len(successful) / n * 100, 1),
            "slow_count": len(slow)
        }

    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all operations."""
        with self._lock:
            operations = list(self._records.keys())

        return {op: self.get_stats(op) for op in operations}

    def get_slow_queries(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get most recent slow queries."""
        with self._lock:
            slow = self._slow_queries[-limit:]

        return [
            {
                "operation": r.operation,
                "duration_ms": round(r.duration_ms, 2),
                "timestamp": r.timestamp,
                "success": r.success,
                "metadata": r.metadata
            }
            for r in reversed(slow)
        ]

    def get_summary(self) -> Dict[str, Any]:
        """
        Get overall performance summary.

        Returns:
            Dictionary with summary statistics for Streamlit display
        """
        all_stats = self.get_all_stats()

        total_requests = sum(s["count"] for s in all_stats.values())
        total_slow = sum(s["slow_count"] for s in all_stats.values())

        all_durations = []
        with self._lock:
            for records in self._records.values():
                all_durations.extend(r.duration_ms for r in records)

        avg_response = round(statistics.mean(all_durations), 2) if all_durations else 0

        return {
            "total_requests": total_requests,
            "total_slow": total_slow,
            "avg_response_ms": avg_response,
            "operations": all_stats,
            "slow_pct": round(total_slow / total_requests * 100, 1) if total_requests > 0 else 0
        }

    def reset(self, operation: Optional[str] = None):
        """
        Reset timing records.

        Args:
            operation: If specified, only reset this operation.
                      If None, reset all records.
        """
        with self._lock:
            if operation:
                self._records.pop(operation, None)
            else:
                self._records.clear()
                self._slow_queries.clear()

    @property
    def operations(self) -> List[str]:
        """List all tracked operations."""
        with self._lock:
            return list(self._records.keys())


# Global monitor instance
_global_monitor: Optional[PerformanceMonitor] = None


def get_monitor() -> PerformanceMonitor:
    """Get or create the global performance monitor."""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = PerformanceMonitor()
    return _global_monitor
