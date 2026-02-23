"""
Phase 7: Live Data Integration - API Health Dashboard Tests
"""

import os
import time
import pytest
from api_health import APIHealthDashboard, APIHealthRecord


class TestAPIHealthRecord:
    """Tests for APIHealthRecord dataclass"""

    def test_create(self):
        record = APIHealthRecord(
            source="NBP", timestamp=time.time(),
            response_time_ms=250.0, status_code=200,
            success=True
        )
        assert record.source == "NBP"
        assert record.success is True

    def test_create_with_error(self):
        record = APIHealthRecord(
            source="WEBOC", timestamp=time.time(),
            response_time_ms=5000.0, status_code=500,
            success=False, error_message="Timeout"
        )
        assert record.success is False
        assert record.error_message == "Timeout"


class TestAPIHealthDashboard:
    """Tests for APIHealthDashboard"""

    def test_init_creates_db(self, tmp_db_dir):
        db_path = os.path.join(tmp_db_dir, "health.db")
        dashboard = APIHealthDashboard(db_path=db_path)
        assert os.path.exists(db_path)

    def test_record_and_retrieve(self, tmp_db_dir):
        db_path = os.path.join(tmp_db_dir, "health.db")
        dashboard = APIHealthDashboard(db_path=db_path)
        dashboard.record("NBP", 250.0, True, 200)
        health = dashboard.get_health("NBP")
        assert health["total_checks"] == 1
        assert health["uptime_pct"] == 100.0

    def test_record_failure(self, tmp_db_dir):
        db_path = os.path.join(tmp_db_dir, "health.db")
        dashboard = APIHealthDashboard(db_path=db_path)
        dashboard.record("WEBOC", 5000.0, False, 500, error="Timeout")
        health = dashboard.get_health("WEBOC")
        assert health["total_checks"] == 1
        assert health["uptime_pct"] == 0.0
        assert health["last_error"] == "Timeout"

    def test_uptime_calculation(self, tmp_db_dir):
        db_path = os.path.join(tmp_db_dir, "health.db")
        dashboard = APIHealthDashboard(db_path=db_path)
        for _ in range(8):
            dashboard.record("NBP", 200.0, True, 200)
        for _ in range(2):
            dashboard.record("NBP", 5000.0, False, 500)
        health = dashboard.get_health("NBP")
        assert health["uptime_pct"] == 80.0
        assert health["total_checks"] == 10

    def test_avg_response_time(self, tmp_db_dir):
        db_path = os.path.join(tmp_db_dir, "health.db")
        dashboard = APIHealthDashboard(db_path=db_path)
        dashboard.record("SBP", 100.0, True)
        dashboard.record("SBP", 200.0, True)
        dashboard.record("SBP", 300.0, True)
        health = dashboard.get_health("SBP")
        assert health["avg_response_ms"] == 200.0

    def test_status_online(self, tmp_db_dir):
        db_path = os.path.join(tmp_db_dir, "health.db")
        dashboard = APIHealthDashboard(db_path=db_path)
        for _ in range(5):
            dashboard.record("TIPP", 300.0, True, 200)
        health = dashboard.get_health("TIPP")
        assert health["status"] == "online"

    def test_status_offline(self, tmp_db_dir):
        db_path = os.path.join(tmp_db_dir, "health.db")
        dashboard = APIHealthDashboard(db_path=db_path)
        for _ in range(5):
            dashboard.record("WEBOC", 0.0, False, 0, error="Down")
        health = dashboard.get_health("WEBOC")
        assert health["status"] == "offline"

    def test_status_degraded(self, tmp_db_dir):
        db_path = os.path.join(tmp_db_dir, "health.db")
        dashboard = APIHealthDashboard(db_path=db_path)
        dashboard.record("NBP", 300.0, True, 200)
        dashboard.record("NBP", 0.0, False, 0)
        dashboard.record("NBP", 300.0, True, 200)
        dashboard.record("NBP", 0.0, False, 0)
        dashboard.record("NBP", 300.0, True, 200)
        health = dashboard.get_health("NBP")
        assert health["status"] == "degraded"

    def test_status_unknown_no_records(self, tmp_db_dir):
        db_path = os.path.join(tmp_db_dir, "health.db")
        dashboard = APIHealthDashboard(db_path=db_path)
        health = dashboard.get_health("TIPP")
        assert health["status"] == "unknown"
        assert health["total_checks"] == 0

    def test_get_all_health(self, tmp_db_dir):
        db_path = os.path.join(tmp_db_dir, "health.db")
        dashboard = APIHealthDashboard(db_path=db_path)
        dashboard.record("NBP", 200.0, True)
        dashboard.record("SBP", 300.0, True)
        all_health = dashboard.get_all_health()
        assert len(all_health) == len(dashboard.KNOWN_SOURCES)
        assert "NBP" in all_health
        assert "SBP" in all_health

    def test_get_history(self, tmp_db_dir):
        db_path = os.path.join(tmp_db_dir, "health.db")
        dashboard = APIHealthDashboard(db_path=db_path)
        dashboard.record("TIPP", 100.0, True)
        dashboard.record("TIPP", 200.0, True)
        dashboard.record("TIPP", 300.0, False, 500)
        history = dashboard.get_history("TIPP")
        assert len(history) == 3
        assert all(isinstance(r, APIHealthRecord) for r in history)
        # Newest first
        assert history[0].response_time_ms == 300.0

    def test_cleanup_old(self, tmp_db_dir):
        db_path = os.path.join(tmp_db_dir, "health.db")
        dashboard = APIHealthDashboard(db_path=db_path, retention_days=1)
        dashboard.record("NBP", 200.0, True)
        # With 1-day retention, cleanup should not remove fresh records
        deleted = dashboard.cleanup_old(days=1)
        assert deleted == 0
        # Verify record still exists
        health = dashboard.get_health("NBP")
        assert health["total_checks"] == 1

    def test_get_record_count(self, tmp_db_dir):
        db_path = os.path.join(tmp_db_dir, "health.db")
        dashboard = APIHealthDashboard(db_path=db_path)
        assert dashboard.get_record_count() == 0
        dashboard.record("NBP", 200.0, True)
        dashboard.record("SBP", 300.0, True)
        assert dashboard.get_record_count() == 2
        assert dashboard.get_record_count("NBP") == 1

    def test_format_age(self):
        now = time.time()
        assert "s ago" in APIHealthDashboard._format_age(now - 30)
        assert "m ago" in APIHealthDashboard._format_age(now - 300)
        assert "h ago" in APIHealthDashboard._format_age(now - 7200)
        assert "d ago" in APIHealthDashboard._format_age(now - 172800)

    def test_error_rate(self, tmp_db_dir):
        db_path = os.path.join(tmp_db_dir, "health.db")
        dashboard = APIHealthDashboard(db_path=db_path)
        for _ in range(7):
            dashboard.record("WEBOC", 200.0, True)
        for _ in range(3):
            dashboard.record("WEBOC", 0.0, False, 500)
        health = dashboard.get_health("WEBOC")
        assert health["error_rate"] == 30.0

    def test_known_sources(self):
        assert "NBP" in APIHealthDashboard.KNOWN_SOURCES
        assert "SBP" in APIHealthDashboard.KNOWN_SOURCES
        assert "WEBOC" in APIHealthDashboard.KNOWN_SOURCES
        assert "TIPP" in APIHealthDashboard.KNOWN_SOURCES
        assert "OpenAI" in APIHealthDashboard.KNOWN_SOURCES
