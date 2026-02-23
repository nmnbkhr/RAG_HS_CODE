"""
Phase 5: Infrastructure - Health Check Tests

Tests for system health checks and monitoring.
"""

import pytest
import os
import socket
from pathlib import Path
from unittest.mock import patch, MagicMock
from health_check import (
    CheckResult, HealthReport,
    check_python_packages, check_service_reachable,
    check_external_services, check_filesystem,
    check_conda_env, check_env_vars, run_health_check,
    REQUIRED_PACKAGES, OPTIONAL_PACKAGES,
)

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)


class TestCheckResult:
    """Tests for CheckResult dataclass"""

    def test_create_ok(self):
        r = CheckResult(name="test", status="ok", message="All good")
        assert r.status == "ok"

    def test_create_fail(self):
        r = CheckResult(name="test", status="fail", message="Missing")
        assert r.status == "fail"

    def test_to_dict(self):
        r = CheckResult(name="test", status="ok", message="v1.0", duration_ms=5.5)
        d = r.to_dict()
        assert d["name"] == "test"
        assert d["status"] == "ok"
        assert d["duration_ms"] == 5.5

    def test_to_dict_with_details(self):
        r = CheckResult(
            name="test", status="ok", message="v1.0",
            details={"extra": "info"},
        )
        d = r.to_dict()
        assert d["details"]["extra"] == "info"

    def test_to_dict_without_details(self):
        r = CheckResult(name="test", status="ok", message="v1.0")
        d = r.to_dict()
        assert "details" not in d


class TestHealthReport:
    """Tests for HealthReport aggregate"""

    def test_healthy(self):
        report = HealthReport(checks=[
            CheckResult(name="a", status="ok", message="ok"),
            CheckResult(name="b", status="ok", message="ok"),
        ])
        assert report.overall_status == "healthy"
        assert report.ok_count == 2

    def test_degraded(self):
        report = HealthReport(checks=[
            CheckResult(name="a", status="ok", message="ok"),
            CheckResult(name="b", status="warn", message="warning"),
        ])
        assert report.overall_status == "degraded"
        assert report.warn_count == 1

    def test_unhealthy(self):
        report = HealthReport(checks=[
            CheckResult(name="a", status="ok", message="ok"),
            CheckResult(name="b", status="fail", message="failed"),
        ])
        assert report.overall_status == "unhealthy"
        assert report.fail_count == 1

    def test_total_checks(self):
        report = HealthReport(checks=[
            CheckResult(name="a", status="ok", message="ok"),
            CheckResult(name="b", status="warn", message="w"),
            CheckResult(name="c", status="fail", message="f"),
        ])
        assert report.total_checks == 3

    def test_to_dict(self):
        report = HealthReport(
            checks=[CheckResult(name="a", status="ok", message="ok")],
            timestamp="2026-01-01",
            hostname="test",
            python_version="3.11",
        )
        d = report.to_dict()
        assert d["overall_status"] == "healthy"
        assert d["summary"]["ok"] == 1
        assert d["summary"]["total"] == 1
        assert len(d["checks"]) == 1

    def test_summary_text(self):
        report = HealthReport(checks=[
            CheckResult(name="a", status="ok", message="good"),
            CheckResult(name="b", status="fail", message="bad"),
        ])
        text = report.summary_text()
        assert "UNHEALTHY" in text
        assert "[+] a" in text
        assert "[X] b" in text


class TestCheckPythonPackages:
    """Tests for package checking"""

    def test_check_stdlib(self):
        """Check that stdlib packages are importable."""
        results = check_python_packages(
            required=[("os", "os"), ("sys", "sys")],
            optional=[],
        )
        assert len(results) == 2
        assert all(r.status == "ok" for r in results)

    def test_check_missing_package(self):
        results = check_python_packages(
            required=[("nonexistent_pkg_xyz", "nonexistent-pkg-xyz")],
            optional=[],
        )
        assert len(results) == 1
        assert results[0].status == "fail"

    def test_check_optional_missing(self):
        results = check_python_packages(
            required=[],
            optional=[("nonexistent_pkg_xyz", "nonexistent-pkg-xyz")],
        )
        assert len(results) == 1
        assert results[0].status == "warn"

    def test_duration_tracked(self):
        results = check_python_packages(
            required=[("os", "os")],
            optional=[],
        )
        assert results[0].duration_ms >= 0


class TestCheckServiceReachable:
    """Tests for service connectivity checks"""

    @patch("health_check.socket.create_connection")
    def test_reachable(self, mock_conn):
        mock_sock = MagicMock()
        mock_conn.return_value = mock_sock
        result = check_service_reachable("example.com", 443, name="test")
        assert result.status == "ok"
        mock_sock.close.assert_called_once()

    @patch("health_check.socket.create_connection")
    def test_unreachable(self, mock_conn):
        mock_conn.side_effect = socket.timeout("timed out")
        result = check_service_reachable("example.com", 443, name="test")
        assert result.status == "warn"

    @patch("health_check.socket.create_connection")
    def test_connection_error(self, mock_conn):
        mock_conn.side_effect = socket.error("connection refused")
        result = check_service_reachable("example.com", 443, name="test")
        assert result.status == "warn"

    def test_default_name(self):
        with patch("health_check.socket.create_connection") as mock:
            mock.return_value = MagicMock()
            result = check_service_reachable("example.com", 443)
            assert "example.com" in result.name


class TestCheckFilesystem:
    """Tests for filesystem checks"""

    def test_checks_env_file(self):
        results = check_filesystem(PROJECT_ROOT)
        names = [r.name for r in results]
        assert "file:.env" in names

    def test_checks_main_app(self):
        results = check_filesystem(PROJECT_ROOT)
        names = [r.name for r in results]
        assert "file:appuiux.py" in names

    def test_checks_faiss_index(self):
        results = check_filesystem(PROJECT_ROOT)
        names = [r.name for r in results]
        assert "file:faiss_index" in names

    def test_checks_phases(self):
        results = check_filesystem(PROJECT_ROOT)
        names = [r.name for r in results]
        assert "dir:phase1" in names
        assert "dir:phase4" in names

    def test_appuiux_exists(self):
        results = check_filesystem(PROJECT_ROOT)
        app_check = next(r for r in results if r.name == "file:appuiux.py")
        assert app_check.status == "ok"


class TestCheckCondaEnv:
    """Tests for conda environment check"""

    @patch.dict(os.environ, {"CONDA_DEFAULT_ENV": "rag_hs_code"})
    def test_correct_env(self):
        result = check_conda_env()
        assert result.status == "ok"

    @patch.dict(os.environ, {"CONDA_DEFAULT_ENV": "other_env"})
    def test_wrong_env(self):
        result = check_conda_env()
        assert result.status == "warn"
        assert "other_env" in result.message

    @patch.dict(os.environ, {}, clear=True)
    def test_no_env(self):
        result = check_conda_env()
        assert result.status == "warn"


class TestCheckEnvVars:
    """Tests for environment variable checks"""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "sk-test1234567890"})
    def test_key_set(self):
        results = check_env_vars()
        key_check = next(r for r in results if "OPENAI_API_KEY" in r.name)
        assert key_check.status == "ok"
        assert "****" in key_check.message  # Masked

    @patch.dict(os.environ, {"OPENAI_API_KEY": ""})
    def test_key_empty(self):
        results = check_env_vars()
        key_check = next(r for r in results if "OPENAI_API_KEY" in r.name)
        assert key_check.status == "fail"

    @patch.dict(os.environ, {}, clear=True)
    def test_key_missing(self):
        results = check_env_vars()
        key_check = next(r for r in results if "OPENAI_API_KEY" in r.name)
        assert key_check.status == "fail"


class TestRunHealthCheck:
    """Tests for full health check"""

    def test_returns_report(self):
        report = run_health_check(
            project_root=PROJECT_ROOT,
            include_services=False,
            include_packages=False,
        )
        assert isinstance(report, HealthReport)
        assert report.total_checks > 0

    def test_has_timestamp(self):
        report = run_health_check(
            project_root=PROJECT_ROOT,
            include_services=False,
            include_packages=False,
        )
        assert report.timestamp != ""

    def test_has_hostname(self):
        report = run_health_check(
            project_root=PROJECT_ROOT,
            include_services=False,
            include_packages=False,
        )
        assert report.hostname != ""

    def test_has_python_version(self):
        report = run_health_check(
            project_root=PROJECT_ROOT,
            include_services=False,
            include_packages=False,
        )
        assert "3." in report.python_version

    def test_with_packages(self):
        report = run_health_check(
            project_root=PROJECT_ROOT,
            include_services=False,
            include_packages=True,
        )
        names = [c.name for c in report.checks]
        assert any("pkg:" in n for n in names)
