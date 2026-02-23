"""
Phase 3: Performance - Performance Monitor Tests

Comprehensive tests for response time tracking and statistics.
"""

import pytest
import time
from performance_monitor import PerformanceMonitor, TimingRecord, get_monitor


class TestTimingRecord:
    """Tests for TimingRecord dataclass"""

    def test_create(self):
        record = TimingRecord(
            operation="weboc_search",
            duration_ms=150.5,
            timestamp=time.time(),
            success=True
        )
        assert record.operation == "weboc_search"
        assert record.duration_ms == 150.5
        assert record.success is True

    def test_with_metadata(self):
        record = TimingRecord(
            operation="weboc_search",
            duration_ms=150.5,
            timestamp=time.time(),
            metadata={"hs_code": "0808.1000"}
        )
        assert record.metadata["hs_code"] == "0808.1000"

    def test_failed_record(self):
        record = TimingRecord(
            operation="nbp_fetch",
            duration_ms=5000.0,
            timestamp=time.time(),
            success=False
        )
        assert record.success is False


class TestPerformanceMonitor:
    """Tests for PerformanceMonitor class"""

    def test_init(self):
        monitor = PerformanceMonitor()
        assert monitor.slow_threshold_ms == 2000
        assert len(monitor.operations) == 0

    def test_custom_threshold(self):
        monitor = PerformanceMonitor(slow_threshold_ms=1000)
        assert monitor.slow_threshold_ms == 1000

    def test_record(self):
        monitor = PerformanceMonitor()
        monitor.record("weboc_search", 150.0)

        stats = monitor.get_stats("weboc_search")
        assert stats["count"] == 1
        assert stats["avg_ms"] == 150.0

    def test_record_multiple(self):
        monitor = PerformanceMonitor()
        monitor.record("weboc_search", 100.0)
        monitor.record("weboc_search", 200.0)
        monitor.record("weboc_search", 300.0)

        stats = monitor.get_stats("weboc_search")
        assert stats["count"] == 3
        assert stats["avg_ms"] == 200.0
        assert stats["min_ms"] == 100.0
        assert stats["max_ms"] == 300.0

    def test_track_context_manager(self):
        monitor = PerformanceMonitor()

        with monitor.track("test_op"):
            time.sleep(0.05)

        stats = monitor.get_stats("test_op")
        assert stats["count"] == 1
        assert stats["avg_ms"] >= 40  # At least 40ms (sleep 50ms with tolerance)

    def test_track_with_exception(self):
        monitor = PerformanceMonitor()

        with pytest.raises(ValueError):
            with monitor.track("failing_op"):
                raise ValueError("test error")

        stats = monitor.get_stats("failing_op")
        assert stats["count"] == 1
        assert stats["success_rate"] == 0.0

    def test_track_with_metadata(self):
        monitor = PerformanceMonitor()

        with monitor.track("weboc_search", {"hs_code": "0808.1000"}):
            pass

        stats = monitor.get_stats("weboc_search")
        assert stats["count"] == 1

    def test_get_stats_empty(self):
        monitor = PerformanceMonitor()
        stats = monitor.get_stats("nonexistent")

        assert stats["count"] == 0
        assert stats["avg_ms"] == 0

    def test_percentiles(self):
        monitor = PerformanceMonitor()

        # Record 100 values from 1 to 100
        for i in range(1, 101):
            monitor.record("op", float(i))

        stats = monitor.get_stats("op")
        assert stats["count"] == 100
        assert stats["p50_ms"] == 51.0  # Median (0-indexed: sorted[50] = 51)
        assert stats["p95_ms"] == 96.0  # sorted[95] = 96
        assert stats["p99_ms"] == 100.0  # sorted[99] = 100

    def test_success_rate(self):
        monitor = PerformanceMonitor()
        monitor.record("op", 100.0, success=True)
        monitor.record("op", 200.0, success=True)
        monitor.record("op", 5000.0, success=False)

        stats = monitor.get_stats("op")
        assert stats["success_rate"] == pytest.approx(66.7, abs=0.1)

    def test_slow_query_detection(self):
        monitor = PerformanceMonitor(slow_threshold_ms=100)
        monitor.record("op", 50.0)   # Fast
        monitor.record("op", 200.0)  # Slow
        monitor.record("op", 300.0)  # Slow

        stats = monitor.get_stats("op")
        assert stats["slow_count"] == 2

    def test_get_slow_queries(self):
        monitor = PerformanceMonitor(slow_threshold_ms=100)
        monitor.record("op1", 50.0)
        monitor.record("op2", 200.0, metadata={"query": "test"})

        slow = monitor.get_slow_queries()
        assert len(slow) == 1
        assert slow[0]["operation"] == "op2"
        assert slow[0]["duration_ms"] == 200.0

    def test_get_all_stats(self):
        monitor = PerformanceMonitor()
        monitor.record("op1", 100.0)
        monitor.record("op2", 200.0)

        all_stats = monitor.get_all_stats()
        assert "op1" in all_stats
        assert "op2" in all_stats

    def test_get_summary(self):
        monitor = PerformanceMonitor()
        monitor.record("op1", 100.0)
        monitor.record("op2", 200.0)

        summary = monitor.get_summary()
        assert summary["total_requests"] == 2
        assert summary["avg_response_ms"] == 150.0

    def test_reset_specific_operation(self):
        monitor = PerformanceMonitor()
        monitor.record("op1", 100.0)
        monitor.record("op2", 200.0)

        monitor.reset("op1")

        assert monitor.get_stats("op1")["count"] == 0
        assert monitor.get_stats("op2")["count"] == 1

    def test_reset_all(self):
        monitor = PerformanceMonitor()
        monitor.record("op1", 100.0)
        monitor.record("op2", 200.0)

        monitor.reset()

        assert len(monitor.operations) == 0

    def test_operations_list(self):
        monitor = PerformanceMonitor()
        monitor.record("op1", 100.0)
        monitor.record("op2", 200.0)
        monitor.record("op3", 300.0)

        ops = monitor.operations
        assert len(ops) == 3
        assert "op1" in ops
        assert "op2" in ops
        assert "op3" in ops

    def test_rolling_window(self):
        monitor = PerformanceMonitor(max_records=10)

        for i in range(20):
            monitor.record("op", float(i))

        stats = monitor.get_stats("op")
        assert stats["count"] == 10  # Only last 10 kept


class TestGetMonitor:
    """Tests for global monitor"""

    def test_get_monitor_returns_instance(self):
        monitor = get_monitor()
        assert isinstance(monitor, PerformanceMonitor)

    def test_get_monitor_singleton(self):
        m1 = get_monitor()
        m2 = get_monitor()
        assert m1 is m2
