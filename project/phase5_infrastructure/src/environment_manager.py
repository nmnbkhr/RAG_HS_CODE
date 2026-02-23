"""
RAG_HS_CODE - Environment Manager
Phase 5: Infrastructure

Manages conda environment validation, package checks, and setup generation.
"""

import os
import sys
import re
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime


# Minimum required packages with version constraints
REQUIRED_PACKAGES = {
    "streamlit": "1.28.0",
    "langchain": "0.1.0",
    "langchain-community": "0.0.10",
    "langchain-openai": "0.0.5",
    "langchain-core": "0.1.0",
    "langchain-text-splitters": "0.0.1",
    "openai": "1.0.0",
    "faiss-cpu": "1.7.4",
    "pypdf": "3.17.0",
    "python-dotenv": "1.0.0",
    "requests": "2.31.0",
    "beautifulsoup4": "4.12.0",
    "lxml": "4.9.0",
}

DEV_PACKAGES = {
    "pytest": "7.0.0",
    "pytest-cov": "4.0.0",
    "reportlab": "4.0.0",
    "openpyxl": "3.1.0",
}

TARGET_CONDA_ENV = "rag_hs_code"
TARGET_PYTHON = "3.11"


@dataclass
class PackageStatus:
    """Status of a single package."""
    name: str
    required_version: str
    installed_version: Optional[str] = None
    is_installed: bool = False
    version_ok: bool = False
    is_dev: bool = False

    @property
    def status(self) -> str:
        if not self.is_installed:
            return "missing"
        if not self.version_ok:
            return "outdated"
        return "ok"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "required": self.required_version,
            "installed": self.installed_version or "not installed",
            "status": self.status,
            "dev": self.is_dev,
        }


@dataclass
class EnvironmentStatus:
    """Overall environment validation status."""
    conda_env_name: str
    conda_env_active: bool
    python_version: str
    python_version_ok: bool
    packages: List[PackageStatus] = field(default_factory=list)
    timestamp: str = ""

    @property
    def all_ok(self) -> bool:
        required = [p for p in self.packages if not p.is_dev]
        return (
            self.conda_env_active
            and self.python_version_ok
            and all(p.status == "ok" for p in required)
        )

    @property
    def missing_count(self) -> int:
        return sum(1 for p in self.packages if p.status == "missing")

    @property
    def outdated_count(self) -> int:
        return sum(1 for p in self.packages if p.status == "outdated")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conda_env": self.conda_env_name,
            "conda_active": self.conda_env_active,
            "python_version": self.python_version,
            "python_ok": self.python_version_ok,
            "all_ok": self.all_ok,
            "missing": self.missing_count,
            "outdated": self.outdated_count,
            "packages": [p.to_dict() for p in self.packages],
            "timestamp": self.timestamp,
        }

    def summary_text(self) -> str:
        lines = []
        status = "OK" if self.all_ok else "ISSUES FOUND"
        lines.append(f"Environment: {status}")
        lines.append(f"  Conda: {self.conda_env_name} (active: {self.conda_env_active})")
        lines.append(f"  Python: {self.python_version} (required: {TARGET_PYTHON})")

        if self.missing_count > 0:
            missing = [p.name for p in self.packages if p.status == "missing"]
            lines.append(f"  Missing ({self.missing_count}): {', '.join(missing)}")

        if self.outdated_count > 0:
            outdated = [f"{p.name} ({p.installed_version})" for p in self.packages if p.status == "outdated"]
            lines.append(f"  Outdated ({self.outdated_count}): {', '.join(outdated)}")

        return "\n".join(lines)


def _parse_version(version_str: str) -> Tuple[int, ...]:
    """Parse a version string into a comparable tuple."""
    try:
        parts = re.findall(r'\d+', version_str.split("+")[0].split("rc")[0].split("a")[0].split("b")[0])
        if not parts:
            return (0, 0, 0)
        return tuple(int(p) for p in parts[:3])
    except (ValueError, IndexError):
        return (0, 0, 0)


def _version_gte(installed: str, required: str) -> bool:
    """Check if installed version >= required version."""
    return _parse_version(installed) >= _parse_version(required)


def check_package(
    pip_name: str,
    min_version: str,
    is_dev: bool = False,
) -> PackageStatus:
    """
    Check if a package is installed and meets version requirements.

    Args:
        pip_name: Package name as used by pip
        min_version: Minimum required version
        is_dev: Whether this is a development-only package

    Returns:
        PackageStatus with check results
    """
    status = PackageStatus(
        name=pip_name,
        required_version=min_version,
        is_dev=is_dev,
    )

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "show", pip_name],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            for line in result.stdout.split("\n"):
                if line.startswith("Version:"):
                    version = line.split(":", 1)[1].strip()
                    status.installed_version = version
                    status.is_installed = True
                    status.version_ok = _version_gte(version, min_version)
                    break
    except (subprocess.TimeoutExpired, Exception):
        pass

    return status


def validate_environment() -> EnvironmentStatus:
    """
    Validate the current environment against requirements.

    Returns:
        EnvironmentStatus with full validation results
    """
    # Conda environment
    conda_env = os.environ.get("CONDA_DEFAULT_ENV", "")
    conda_active = conda_env == TARGET_CONDA_ENV

    # Python version
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}"
    py_ok = _version_gte(py_version, TARGET_PYTHON)

    # Check packages
    packages = []
    for name, version in REQUIRED_PACKAGES.items():
        packages.append(check_package(name, version, is_dev=False))

    for name, version in DEV_PACKAGES.items():
        packages.append(check_package(name, version, is_dev=True))

    return EnvironmentStatus(
        conda_env_name=conda_env or "(none)",
        conda_env_active=conda_active,
        python_version=py_version,
        python_version_ok=py_ok,
        packages=packages,
        timestamp=datetime.now().isoformat(),
    )


def generate_environment_yml(
    include_dev: bool = True,
    output_path: Optional[str] = None,
) -> str:
    """
    Generate an environment.yml from current requirements.

    Args:
        include_dev: Include development packages
        output_path: Path to write file (None = return string only)

    Returns:
        YAML string
    """
    lines = [
        f"name: {TARGET_CONDA_ENV}",
        "channels:",
        "  - conda-forge",
        "  - defaults",
        "dependencies:",
        f"  - python={TARGET_PYTHON}",
        "  - pip",
        "  - pip:",
    ]

    for name, version in sorted(REQUIRED_PACKAGES.items()):
        lines.append(f"      - {name}>={version}")

    if include_dev:
        lines.append("      # Development dependencies")
        for name, version in sorted(DEV_PACKAGES.items()):
            lines.append(f"      - {name}>={version}")

    content = "\n".join(lines) + "\n"

    if output_path:
        Path(output_path).write_text(content)

    return content


def generate_requirements_txt(
    include_dev: bool = True,
    output_path: Optional[str] = None,
) -> str:
    """
    Generate a requirements.txt from current requirements.

    Args:
        include_dev: Include development packages
        output_path: Path to write file (None = return string only)

    Returns:
        Requirements text
    """
    lines = ["# RAG_HS_CODE - Python Requirements", ""]

    lines.append("# Core dependencies")
    for name, version in sorted(REQUIRED_PACKAGES.items()):
        lines.append(f"{name}>={version}")

    if include_dev:
        lines.append("")
        lines.append("# Development dependencies")
        for name, version in sorted(DEV_PACKAGES.items()):
            lines.append(f"{name}>={version}")

    content = "\n".join(lines) + "\n"

    if output_path:
        Path(output_path).write_text(content)

    return content


def get_install_commands(status: EnvironmentStatus) -> List[str]:
    """
    Generate pip install commands to fix missing/outdated packages.

    Args:
        status: EnvironmentStatus from validate_environment()

    Returns:
        List of pip install commands
    """
    commands = []

    missing = [p for p in status.packages if p.status == "missing" and not p.is_dev]
    if missing:
        pkgs = " ".join(f"{p.name}>={p.required_version}" for p in missing)
        commands.append(f"pip install {pkgs}")

    outdated = [p for p in status.packages if p.status == "outdated" and not p.is_dev]
    if outdated:
        pkgs = " ".join(f"{p.name}>={p.required_version}" for p in outdated)
        commands.append(f"pip install --upgrade {pkgs}")

    dev_missing = [p for p in status.packages if p.status in ("missing", "outdated") and p.is_dev]
    if dev_missing:
        pkgs = " ".join(f"{p.name}>={p.required_version}" for p in dev_missing)
        commands.append(f"pip install {pkgs}  # dev dependencies")

    return commands
