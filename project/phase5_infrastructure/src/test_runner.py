"""
RAG_HS_CODE - Unified Test Runner
Phase 5: Infrastructure

Runs all phase tests from a single entry point with coverage and reporting.
"""

import os
import sys
import time
import subprocess
import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

PHASES = {
    "phase1": {
        "name": "Phase 1 - Security & Validation",
        "path": "project/phase1_security_validation",
        "test_dir": "tests",
    },
    "phase2": {
        "name": "Phase 2 - UX Enhancements",
        "path": "project/phase2_ux_enhancements",
        "test_dir": "tests",
    },
    "phase3": {
        "name": "Phase 3 - Performance & Caching",
        "path": "project/phase3_performance",
        "test_dir": "tests",
    },
    "phase4": {
        "name": "Phase 4 - Features",
        "path": "project/phase4_features",
        "test_dir": "tests",
    },
    "phase5": {
        "name": "Phase 5 - Infrastructure",
        "path": "project/phase5_infrastructure",
        "test_dir": "tests",
    },
}


@dataclass
class PhaseResult:
    """Result of running tests for a single phase."""
    phase_id: str
    phase_name: str
    passed: int = 0
    failed: int = 0
    errors: int = 0
    skipped: int = 0
    duration_seconds: float = 0.0
    returncode: int = 0
    output: str = ""

    @property
    def total(self) -> int:
        return self.passed + self.failed + self.errors + self.skipped

    @property
    def success(self) -> bool:
        return self.returncode == 0 and self.failed == 0 and self.errors == 0

    @property
    def success_rate(self) -> float:
        if self.total == 0:
            return 0.0
        return (self.passed / self.total) * 100

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase_id": self.phase_id,
            "phase_name": self.phase_name,
            "passed": self.passed,
            "failed": self.failed,
            "errors": self.errors,
            "skipped": self.skipped,
            "total": self.total,
            "success": self.success,
            "success_rate": round(self.success_rate, 1),
            "duration_seconds": round(self.duration_seconds, 2),
        }


@dataclass
class TestRunResult:
    """Aggregate result of running all phase tests."""
    phase_results: List[PhaseResult] = field(default_factory=list)
    total_duration: float = 0.0
    timestamp: str = ""

    @property
    def total_passed(self) -> int:
        return sum(r.passed for r in self.phase_results)

    @property
    def total_failed(self) -> int:
        return sum(r.failed for r in self.phase_results)

    @property
    def total_errors(self) -> int:
        return sum(r.errors for r in self.phase_results)

    @property
    def total_tests(self) -> int:
        return sum(r.total for r in self.phase_results)

    @property
    def all_passed(self) -> bool:
        return all(r.success for r in self.phase_results)

    @property
    def phases_passed(self) -> int:
        return sum(1 for r in self.phase_results if r.success)

    @property
    def phases_total(self) -> int:
        return len(self.phase_results)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "all_passed": self.all_passed,
            "total_tests": self.total_tests,
            "total_passed": self.total_passed,
            "total_failed": self.total_failed,
            "total_errors": self.total_errors,
            "phases_passed": self.phases_passed,
            "phases_total": self.phases_total,
            "total_duration": round(self.total_duration, 2),
            "phases": [r.to_dict() for r in self.phase_results],
        }

    def summary_text(self) -> str:
        lines = []
        lines.append("=" * 70)
        lines.append("RAG_HS_CODE - Unified Test Results")
        lines.append("=" * 70)

        for r in self.phase_results:
            status = "PASS" if r.success else "FAIL"
            lines.append(
                f"  [{status}] {r.phase_name:<40} "
                f"{r.passed:>4} passed / {r.total:>4} total  ({r.duration_seconds:.1f}s)"
            )

        lines.append("-" * 70)
        status = "ALL PASSED" if self.all_passed else "FAILURES DETECTED"
        lines.append(
            f"  [{status}] Total: {self.total_passed} passed, "
            f"{self.total_failed} failed, {self.total_errors} errors "
            f"/ {self.total_tests} tests ({self.total_duration:.1f}s)"
        )
        lines.append("=" * 70)
        return "\n".join(lines)


def _parse_pytest_output(output: str) -> Dict[str, int]:
    """Parse pytest summary line for counts."""
    counts = {"passed": 0, "failed": 0, "errors": 0, "skipped": 0}

    # Map pytest output terms to our keys (handle singular/plural)
    term_map = {
        "passed": "passed",
        "failed": "failed",
        "error": "errors",
        "skipped": "skipped",
    }

    import re
    for line in output.split("\n"):
        line = line.strip()
        if "passed" in line or "failed" in line or "error" in line or "skipped" in line:
            for term, key in term_map.items():
                match = re.search(rf"(\d+)\s+{term}", line)
                if match:
                    counts[key] = int(match.group(1))

    return counts


def run_phase_tests(
    phase_id: str,
    project_root: Optional[Path] = None,
    verbose: bool = False,
    junit_xml: bool = False,
    extra_args: Optional[List[str]] = None,
) -> PhaseResult:
    """
    Run tests for a single phase.

    Args:
        phase_id: Phase identifier (e.g. "phase1")
        project_root: Root directory of the project
        verbose: Enable verbose pytest output
        junit_xml: Generate JUnit XML report
        extra_args: Additional pytest arguments

    Returns:
        PhaseResult with test outcome
    """
    if project_root is None:
        project_root = PROJECT_ROOT

    if phase_id not in PHASES:
        return PhaseResult(
            phase_id=phase_id,
            phase_name=f"Unknown: {phase_id}",
            returncode=1,
            output=f"Unknown phase: {phase_id}",
        )

    phase = PHASES[phase_id]
    phase_dir = project_root / phase["path"]
    test_dir = phase_dir / phase["test_dir"]

    if not test_dir.exists():
        return PhaseResult(
            phase_id=phase_id,
            phase_name=phase["name"],
            returncode=1,
            output=f"Test directory not found: {test_dir}",
        )

    cmd = [sys.executable, "-m", "pytest", str(test_dir)]

    if verbose:
        cmd.append("-v")

    cmd.append("--tb=short")

    if junit_xml:
        xml_path = phase_dir / f"test-results-{phase_id}.xml"
        cmd.extend(["--junitxml", str(xml_path)])

    if extra_args:
        cmd.extend(extra_args)

    start = time.time()
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=str(phase_dir),
            timeout=300,
        )
        duration = time.time() - start
        output = result.stdout + result.stderr
        counts = _parse_pytest_output(output)

        return PhaseResult(
            phase_id=phase_id,
            phase_name=phase["name"],
            passed=counts["passed"],
            failed=counts["failed"],
            errors=counts["errors"],
            skipped=counts["skipped"],
            duration_seconds=duration,
            returncode=result.returncode,
            output=output,
        )
    except subprocess.TimeoutExpired:
        return PhaseResult(
            phase_id=phase_id,
            phase_name=phase["name"],
            returncode=1,
            duration_seconds=300.0,
            output="Test execution timed out (300s)",
        )
    except Exception as e:
        return PhaseResult(
            phase_id=phase_id,
            phase_name=phase["name"],
            returncode=1,
            duration_seconds=time.time() - start,
            output=f"Error running tests: {e}",
        )


def run_all_tests(
    project_root: Optional[Path] = None,
    phases: Optional[List[str]] = None,
    verbose: bool = False,
    junit_xml: bool = False,
    extra_args: Optional[List[str]] = None,
) -> TestRunResult:
    """
    Run tests for all phases (or specified phases).

    Args:
        project_root: Root directory of the project
        phases: List of phase IDs to run (None = all)
        verbose: Enable verbose output
        junit_xml: Generate JUnit XML reports
        extra_args: Additional pytest arguments

    Returns:
        TestRunResult with aggregate outcomes
    """
    from datetime import datetime

    if project_root is None:
        project_root = PROJECT_ROOT

    phase_ids = phases or list(PHASES.keys())
    results = []
    total_start = time.time()

    for pid in phase_ids:
        result = run_phase_tests(
            pid,
            project_root=project_root,
            verbose=verbose,
            junit_xml=junit_xml,
            extra_args=extra_args,
        )
        results.append(result)

    return TestRunResult(
        phase_results=results,
        total_duration=time.time() - total_start,
        timestamp=datetime.now().isoformat(),
    )


def get_available_phases(project_root: Optional[Path] = None) -> List[Dict[str, str]]:
    """Get list of phases that have test directories."""
    if project_root is None:
        project_root = PROJECT_ROOT

    available = []
    for pid, phase in PHASES.items():
        phase_dir = project_root / phase["path"] / phase["test_dir"]
        available.append({
            "id": pid,
            "name": phase["name"],
            "path": phase["path"],
            "exists": phase_dir.exists(),
        })
    return available
