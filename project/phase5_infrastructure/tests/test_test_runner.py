"""
Phase 5: Infrastructure - Test Runner Tests

Tests for the unified test runner across all phases.
"""

import pytest
import os
from pathlib import Path
from test_runner import (
    PhaseResult, TestRunResult, PHASES,
    _parse_pytest_output, run_phase_tests, run_all_tests,
    get_available_phases,
)


# Use project root from environment or detect
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


class TestPhaseResult:
    """Tests for PhaseResult dataclass"""

    def test_create(self):
        r = PhaseResult(phase_id="phase1", phase_name="Test Phase")
        assert r.phase_id == "phase1"
        assert r.total == 0

    def test_total(self):
        r = PhaseResult(
            phase_id="p1", phase_name="P1",
            passed=10, failed=2, errors=1, skipped=3,
        )
        assert r.total == 16

    def test_success_true(self):
        r = PhaseResult(phase_id="p1", phase_name="P1", passed=10, returncode=0)
        assert r.success is True

    def test_success_false_failures(self):
        r = PhaseResult(phase_id="p1", phase_name="P1", passed=8, failed=2, returncode=1)
        assert r.success is False

    def test_success_false_errors(self):
        r = PhaseResult(phase_id="p1", phase_name="P1", passed=8, errors=1, returncode=1)
        assert r.success is False

    def test_success_rate(self):
        r = PhaseResult(phase_id="p1", phase_name="P1", passed=9, failed=1)
        assert r.success_rate == 90.0

    def test_success_rate_empty(self):
        r = PhaseResult(phase_id="p1", phase_name="P1")
        assert r.success_rate == 0.0

    def test_to_dict(self):
        r = PhaseResult(
            phase_id="p1", phase_name="P1",
            passed=10, failed=0, duration_seconds=1.5,
        )
        d = r.to_dict()
        assert d["phase_id"] == "p1"
        assert d["passed"] == 10
        assert d["success"] is True
        assert d["success_rate"] == 100.0
        assert d["duration_seconds"] == 1.5


class TestTestRunResult:
    """Tests for TestRunResult aggregate"""

    def test_empty(self):
        r = TestRunResult()
        assert r.total_tests == 0
        assert r.all_passed is True  # vacuously true

    def test_aggregate(self):
        r = TestRunResult(phase_results=[
            PhaseResult(phase_id="p1", phase_name="P1", passed=50, returncode=0),
            PhaseResult(phase_id="p2", phase_name="P2", passed=30, returncode=0),
        ])
        assert r.total_passed == 80
        assert r.total_tests == 80
        assert r.all_passed is True
        assert r.phases_passed == 2

    def test_aggregate_with_failure(self):
        r = TestRunResult(phase_results=[
            PhaseResult(phase_id="p1", phase_name="P1", passed=50, returncode=0),
            PhaseResult(phase_id="p2", phase_name="P2", passed=28, failed=2, returncode=1),
        ])
        assert r.total_passed == 78
        assert r.total_failed == 2
        assert r.all_passed is False
        assert r.phases_passed == 1

    def test_to_dict(self):
        r = TestRunResult(
            phase_results=[
                PhaseResult(phase_id="p1", phase_name="P1", passed=10, returncode=0),
            ],
            timestamp="2026-01-01T00:00:00",
        )
        d = r.to_dict()
        assert d["all_passed"] is True
        assert d["total_tests"] == 10
        assert len(d["phases"]) == 1

    def test_summary_text(self):
        r = TestRunResult(
            phase_results=[
                PhaseResult(
                    phase_id="p1", phase_name="Phase 1",
                    passed=119, duration_seconds=0.1, returncode=0,
                ),
            ],
            total_duration=0.1,
        )
        text = r.summary_text()
        assert "Phase 1" in text
        assert "119" in text
        assert "ALL PASSED" in text

    def test_summary_text_failure(self):
        r = TestRunResult(
            phase_results=[
                PhaseResult(
                    phase_id="p1", phase_name="Phase 1",
                    passed=118, failed=1, duration_seconds=0.1, returncode=1,
                ),
            ],
        )
        text = r.summary_text()
        assert "FAIL" in text


class TestParsePytestOutput:
    """Tests for pytest output parsing"""

    def test_all_passed(self):
        output = "============================= 119 passed in 0.09s =============================="
        counts = _parse_pytest_output(output)
        assert counts["passed"] == 119
        assert counts["failed"] == 0

    def test_mixed_results(self):
        output = "=============== 5 failed, 114 passed, 1 skipped in 2.3s ==============="
        counts = _parse_pytest_output(output)
        assert counts["passed"] == 114
        assert counts["failed"] == 5
        assert counts["skipped"] == 1

    def test_errors(self):
        output = "=============== 1 error in 0.5s ==============="
        counts = _parse_pytest_output(output)
        assert counts["errors"] == 1

    def test_empty_output(self):
        counts = _parse_pytest_output("")
        assert counts["passed"] == 0


class TestRunPhaseTests:
    """Tests for running individual phase tests"""

    def test_unknown_phase(self):
        result = run_phase_tests("nonexistent")
        assert result.success is False
        assert "Unknown" in result.output

    def test_phase1_exists(self):
        phases = get_available_phases(PROJECT_ROOT)
        phase1 = next((p for p in phases if p["id"] == "phase1"), None)
        assert phase1 is not None
        assert phase1["exists"] is True

    def test_run_phase1(self):
        """Integration test: actually run Phase 1 tests"""
        result = run_phase_tests("phase1", project_root=PROJECT_ROOT)
        assert result.passed > 0
        assert result.success is True

    def test_missing_test_dir(self, tmp_path):
        result = run_phase_tests("phase1", project_root=tmp_path)
        assert result.success is False
        assert "not found" in result.output


class TestGetAvailablePhases:
    """Tests for phase discovery"""

    def test_returns_list(self):
        phases = get_available_phases(PROJECT_ROOT)
        assert isinstance(phases, list)
        assert len(phases) == len(PHASES)

    def test_phase_structure(self):
        phases = get_available_phases(PROJECT_ROOT)
        for p in phases:
            assert "id" in p
            assert "name" in p
            assert "exists" in p

    def test_known_phases_exist(self):
        phases = get_available_phases(PROJECT_ROOT)
        existing = [p for p in phases if p["exists"]]
        assert len(existing) >= 4  # At least phases 1-4


class TestPhasesConfig:
    """Tests for PHASES configuration"""

    def test_all_phases_defined(self):
        assert "phase1" in PHASES
        assert "phase2" in PHASES
        assert "phase3" in PHASES
        assert "phase4" in PHASES
        assert "phase5" in PHASES

    def test_phase_has_required_keys(self):
        for pid, phase in PHASES.items():
            assert "name" in phase
            assert "path" in phase
            assert "test_dir" in phase
