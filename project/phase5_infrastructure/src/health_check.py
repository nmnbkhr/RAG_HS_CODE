"""
RAG_HS_CODE - Health Check & Monitoring
Phase 5: Infrastructure

System health checks for dependencies, services, and environment.
"""

import os
import sys
import socket
import importlib
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class CheckResult:
    """Result of a single health check."""
    name: str
    status: str  # "ok", "warn", "fail"
    message: str
    details: Optional[Dict[str, Any]] = None
    duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "name": self.name,
            "status": self.status,
            "message": self.message,
            "duration_ms": round(self.duration_ms, 1),
        }
        if self.details:
            d["details"] = self.details
        return d


@dataclass
class HealthReport:
    """Aggregate health check report."""
    checks: List[CheckResult] = field(default_factory=list)
    timestamp: str = ""
    hostname: str = ""
    python_version: str = ""

    @property
    def overall_status(self) -> str:
        if any(c.status == "fail" for c in self.checks):
            return "unhealthy"
        if any(c.status == "warn" for c in self.checks):
            return "degraded"
        return "healthy"

    @property
    def ok_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "ok")

    @property
    def warn_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "warn")

    @property
    def fail_count(self) -> int:
        return sum(1 for c in self.checks if c.status == "fail")

    @property
    def total_checks(self) -> int:
        return len(self.checks)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_status": self.overall_status,
            "timestamp": self.timestamp,
            "hostname": self.hostname,
            "python_version": self.python_version,
            "summary": {
                "ok": self.ok_count,
                "warn": self.warn_count,
                "fail": self.fail_count,
                "total": self.total_checks,
            },
            "checks": [c.to_dict() for c in self.checks],
        }

    def summary_text(self) -> str:
        lines = []
        lines.append(f"Health Check: {self.overall_status.upper()}")
        lines.append(f"  OK: {self.ok_count}  Warn: {self.warn_count}  Fail: {self.fail_count}")
        for c in self.checks:
            icon = {"ok": "+", "warn": "!", "fail": "X"}[c.status]
            lines.append(f"  [{icon}] {c.name}: {c.message}")
        return "\n".join(lines)


# Required Python packages for the application
REQUIRED_PACKAGES = [
    ("streamlit", "streamlit"),
    ("langchain", "langchain"),
    ("langchain_openai", "langchain-openai"),
    ("langchain_community", "langchain-community"),
    ("openai", "openai"),
    ("faiss", "faiss-cpu"),
    ("pypdf", "pypdf"),
    ("dotenv", "python-dotenv"),
    ("requests", "requests"),
    ("bs4", "beautifulsoup4"),
    ("lxml", "lxml"),
]

OPTIONAL_PACKAGES = [
    ("reportlab", "reportlab"),
    ("openpyxl", "openpyxl"),
    ("pytest", "pytest"),
]


def check_python_packages(
    required: Optional[List[tuple]] = None,
    optional: Optional[List[tuple]] = None,
) -> List[CheckResult]:
    """
    Check that required Python packages are importable.

    Args:
        required: List of (import_name, pip_name) tuples
        optional: List of (import_name, pip_name) tuples

    Returns:
        List of CheckResult objects
    """
    results = []
    if required is None:
        required = REQUIRED_PACKAGES
    if optional is None:
        optional = OPTIONAL_PACKAGES

    for import_name, pip_name in required:
        start = time.time()
        try:
            mod = importlib.import_module(import_name)
            version = getattr(mod, "__version__", "unknown")
            results.append(CheckResult(
                name=f"pkg:{pip_name}",
                status="ok",
                message=f"v{version}",
                duration_ms=(time.time() - start) * 1000,
            ))
        except ImportError:
            results.append(CheckResult(
                name=f"pkg:{pip_name}",
                status="fail",
                message=f"Not installed (pip install {pip_name})",
                duration_ms=(time.time() - start) * 1000,
            ))

    for import_name, pip_name in optional:
        start = time.time()
        try:
            mod = importlib.import_module(import_name)
            version = getattr(mod, "__version__", "unknown")
            results.append(CheckResult(
                name=f"pkg:{pip_name}",
                status="ok",
                message=f"v{version} (optional)",
                duration_ms=(time.time() - start) * 1000,
            ))
        except ImportError:
            results.append(CheckResult(
                name=f"pkg:{pip_name}",
                status="warn",
                message=f"Not installed (optional: pip install {pip_name})",
                duration_ms=(time.time() - start) * 1000,
            ))

    return results


def check_service_reachable(
    host: str,
    port: int = 443,
    timeout: float = 5.0,
    name: Optional[str] = None,
) -> CheckResult:
    """
    Check if an external service is reachable via TCP.

    Args:
        host: Hostname to connect to
        port: Port number
        timeout: Connection timeout in seconds
        name: Display name for the check

    Returns:
        CheckResult
    """
    display_name = name or f"svc:{host}"
    start = time.time()
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        sock.close()
        return CheckResult(
            name=display_name,
            status="ok",
            message=f"Reachable ({host}:{port})",
            duration_ms=(time.time() - start) * 1000,
        )
    except (socket.timeout, socket.error) as e:
        return CheckResult(
            name=display_name,
            status="warn",
            message=f"Unreachable: {e}",
            duration_ms=(time.time() - start) * 1000,
        )


def check_external_services() -> List[CheckResult]:
    """Check connectivity to all external services."""
    services = [
        ("api.openai.com", 443, "svc:OpenAI API"),
        ("www.weboc.gov.pk", 443, "svc:WEBOC"),
        ("www.nbp.com.pk", 443, "svc:NBP Rates"),
    ]
    results = []
    for host, port, name in services:
        results.append(check_service_reachable(host, port, name=name))
    return results


def check_filesystem(project_root: Optional[str] = None) -> List[CheckResult]:
    """
    Check that required files and directories exist.

    Args:
        project_root: Root directory of the project

    Returns:
        List of CheckResult objects
    """
    if project_root is None:
        project_root = str(Path(__file__).resolve().parent.parent.parent.parent)

    root = Path(project_root)
    results = []

    # Critical files
    critical = [
        (root / ".env", "file:.env"),
        (root / "appuiux.py", "file:appuiux.py"),
    ]

    for path, name in critical:
        if path.exists():
            size = path.stat().st_size
            results.append(CheckResult(
                name=name,
                status="ok",
                message=f"Found ({size} bytes)",
            ))
        else:
            results.append(CheckResult(
                name=name,
                status="fail",
                message="Missing",
            ))

    # FAISS index (may be on external drive)
    faiss_path = os.getenv("FAISS_INDEX_PATH", "/mnt/e/rag_hs_codedata/faiss_index")
    faiss_dir = Path(faiss_path)
    if faiss_dir.exists():
        files = list(faiss_dir.glob("*"))
        results.append(CheckResult(
            name="file:faiss_index",
            status="ok",
            message=f"Found ({len(files)} files in {faiss_path})",
        ))
    else:
        results.append(CheckResult(
            name="file:faiss_index",
            status="warn",
            message=f"Not found at {faiss_path} (needed for RAG queries)",
        ))

    # Project phases
    for i in range(1, 6):
        phase_dir = root / "project" / f"phase{i}_{'security_validation' if i == 1 else 'ux_enhancements' if i == 2 else 'performance' if i == 3 else 'features' if i == 4 else 'infrastructure'}"
        name = f"dir:phase{i}"
        if phase_dir.exists():
            results.append(CheckResult(name=name, status="ok", message="Present"))
        else:
            results.append(CheckResult(name=name, status="warn", message="Missing"))

    return results


def check_conda_env() -> CheckResult:
    """Check if running in the correct conda environment."""
    conda_env = os.environ.get("CONDA_DEFAULT_ENV", "")
    if conda_env == "rag_hs_code":
        return CheckResult(
            name="env:conda",
            status="ok",
            message="rag_hs_code (correct)",
        )
    elif conda_env:
        return CheckResult(
            name="env:conda",
            status="warn",
            message=f"Active: {conda_env} (expected: rag_hs_code)",
        )
    else:
        return CheckResult(
            name="env:conda",
            status="warn",
            message="No conda environment active",
        )


def check_env_vars() -> List[CheckResult]:
    """Check required environment variables."""
    results = []

    key = os.getenv("OPENAI_API_KEY", "").strip()
    if key:
        masked = key[:4] + "****" + key[-4:] if len(key) > 8 else "****"
        results.append(CheckResult(
            name="env:OPENAI_API_KEY",
            status="ok",
            message=f"Set ({masked})",
        ))
    else:
        results.append(CheckResult(
            name="env:OPENAI_API_KEY",
            status="fail",
            message="Not set (required for RAG queries)",
        ))

    return results


def run_health_check(
    project_root: Optional[str] = None,
    include_services: bool = True,
    include_packages: bool = True,
) -> HealthReport:
    """
    Run all health checks and produce a report.

    Args:
        project_root: Root directory of the project
        include_services: Check external service connectivity
        include_packages: Check Python package availability

    Returns:
        HealthReport with all check results
    """
    checks = []

    # Conda environment
    checks.append(check_conda_env())

    # Environment variables
    checks.extend(check_env_vars())

    # Filesystem
    checks.extend(check_filesystem(project_root))

    # Python packages
    if include_packages:
        checks.extend(check_python_packages())

    # External services
    if include_services:
        checks.extend(check_external_services())

    return HealthReport(
        checks=checks,
        timestamp=datetime.now().isoformat(),
        hostname=socket.gethostname(),
        python_version=sys.version.split()[0],
    )
