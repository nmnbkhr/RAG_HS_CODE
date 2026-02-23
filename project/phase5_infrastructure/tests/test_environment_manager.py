"""
Phase 5: Infrastructure - Environment Manager Tests

Tests for conda environment validation and setup generation.
"""

import pytest
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from environment_manager import (
    PackageStatus, EnvironmentStatus,
    REQUIRED_PACKAGES, DEV_PACKAGES, TARGET_CONDA_ENV, TARGET_PYTHON,
    _parse_version, _version_gte,
    check_package, validate_environment,
    generate_environment_yml, generate_requirements_txt,
    get_install_commands,
)


class TestVersionParsing:
    """Tests for version parsing utilities"""

    def test_simple_version(self):
        assert _parse_version("1.2.3") == (1, 2, 3)

    def test_two_part_version(self):
        assert _parse_version("3.11") == (3, 11)

    def test_version_with_suffix(self):
        assert _parse_version("1.2.3rc1") == (1, 2, 3)

    def test_version_with_alpha(self):
        assert _parse_version("1.2.3a1") == (1, 2, 3)

    def test_version_with_build(self):
        assert _parse_version("1.2.3+local") == (1, 2, 3)

    def test_empty_version(self):
        assert _parse_version("") == (0, 0, 0)

    def test_gte_equal(self):
        assert _version_gte("1.2.3", "1.2.3") is True

    def test_gte_greater(self):
        assert _version_gte("2.0.0", "1.2.3") is True

    def test_gte_less(self):
        assert _version_gte("1.2.2", "1.2.3") is False

    def test_gte_major_version(self):
        assert _version_gte("2.0.0", "1.99.99") is True

    def test_gte_minor_version(self):
        assert _version_gte("1.3.0", "1.2.99") is True


class TestPackageStatus:
    """Tests for PackageStatus dataclass"""

    def test_missing(self):
        p = PackageStatus(name="test", required_version="1.0.0")
        assert p.status == "missing"

    def test_installed_ok(self):
        p = PackageStatus(
            name="test", required_version="1.0.0",
            installed_version="1.2.0", is_installed=True, version_ok=True,
        )
        assert p.status == "ok"

    def test_outdated(self):
        p = PackageStatus(
            name="test", required_version="2.0.0",
            installed_version="1.5.0", is_installed=True, version_ok=False,
        )
        assert p.status == "outdated"

    def test_to_dict(self):
        p = PackageStatus(
            name="test", required_version="1.0.0",
            installed_version="1.2.0", is_installed=True, version_ok=True,
        )
        d = p.to_dict()
        assert d["name"] == "test"
        assert d["status"] == "ok"
        assert d["installed"] == "1.2.0"

    def test_to_dict_missing(self):
        p = PackageStatus(name="test", required_version="1.0.0")
        d = p.to_dict()
        assert d["installed"] == "not installed"


class TestEnvironmentStatus:
    """Tests for EnvironmentStatus aggregate"""

    def test_all_ok(self):
        status = EnvironmentStatus(
            conda_env_name="rag_hs_code",
            conda_env_active=True,
            python_version="3.11",
            python_version_ok=True,
            packages=[
                PackageStatus(
                    name="p1", required_version="1.0",
                    is_installed=True, version_ok=True, is_dev=False,
                ),
            ],
        )
        assert status.all_ok is True

    def test_missing_package(self):
        status = EnvironmentStatus(
            conda_env_name="rag_hs_code",
            conda_env_active=True,
            python_version="3.11",
            python_version_ok=True,
            packages=[
                PackageStatus(name="p1", required_version="1.0", is_dev=False),
            ],
        )
        assert status.all_ok is False
        assert status.missing_count == 1

    def test_wrong_conda_env(self):
        status = EnvironmentStatus(
            conda_env_name="other",
            conda_env_active=False,
            python_version="3.11",
            python_version_ok=True,
        )
        assert status.all_ok is False

    def test_dev_missing_doesnt_affect_all_ok(self):
        status = EnvironmentStatus(
            conda_env_name="rag_hs_code",
            conda_env_active=True,
            python_version="3.11",
            python_version_ok=True,
            packages=[
                PackageStatus(
                    name="p1", required_version="1.0",
                    is_installed=True, version_ok=True, is_dev=False,
                ),
                PackageStatus(name="dev-pkg", required_version="1.0", is_dev=True),
            ],
        )
        assert status.all_ok is True  # Dev missing doesn't count

    def test_to_dict(self):
        status = EnvironmentStatus(
            conda_env_name="rag_hs_code",
            conda_env_active=True,
            python_version="3.11",
            python_version_ok=True,
        )
        d = status.to_dict()
        assert d["conda_env"] == "rag_hs_code"
        assert d["all_ok"] is True

    def test_summary_text(self):
        status = EnvironmentStatus(
            conda_env_name="rag_hs_code",
            conda_env_active=True,
            python_version="3.11",
            python_version_ok=True,
        )
        text = status.summary_text()
        assert "OK" in text
        assert "rag_hs_code" in text


class TestCheckPackage:
    """Tests for individual package checks"""

    def test_check_pip(self):
        """pip is always available in a Python environment."""
        result = check_package("pip", "1.0.0")
        assert result.is_installed is True
        assert result.version_ok is True

    def test_check_nonexistent(self):
        result = check_package("nonexistent-pkg-xyz-123", "1.0.0")
        assert result.is_installed is False
        assert result.status == "missing"


class TestGenerateEnvironmentYml:
    """Tests for environment.yml generation"""

    def test_generates_yaml(self):
        yml = generate_environment_yml()
        assert f"name: {TARGET_CONDA_ENV}" in yml
        assert "conda-forge" in yml
        assert f"python={TARGET_PYTHON}" in yml

    def test_includes_required_packages(self):
        yml = generate_environment_yml()
        for pkg in REQUIRED_PACKAGES:
            assert pkg in yml

    def test_includes_dev_packages(self):
        yml = generate_environment_yml(include_dev=True)
        for pkg in DEV_PACKAGES:
            assert pkg in yml

    def test_excludes_dev(self):
        yml = generate_environment_yml(include_dev=False)
        for pkg in DEV_PACKAGES:
            assert pkg not in yml

    def test_writes_to_file(self):
        with tempfile.NamedTemporaryFile(suffix=".yml", delete=False) as f:
            path = f.name

        try:
            generate_environment_yml(output_path=path)
            content = Path(path).read_text()
            assert TARGET_CONDA_ENV in content
        finally:
            os.unlink(path)


class TestGenerateRequirementsTxt:
    """Tests for requirements.txt generation"""

    def test_generates_text(self):
        txt = generate_requirements_txt()
        assert "RAG_HS_CODE" in txt

    def test_includes_required(self):
        txt = generate_requirements_txt()
        for pkg in REQUIRED_PACKAGES:
            assert pkg in txt

    def test_includes_dev(self):
        txt = generate_requirements_txt(include_dev=True)
        for pkg in DEV_PACKAGES:
            assert pkg in txt

    def test_excludes_dev(self):
        txt = generate_requirements_txt(include_dev=False)
        for pkg in DEV_PACKAGES:
            assert pkg not in txt

    def test_writes_to_file(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            path = f.name

        try:
            generate_requirements_txt(output_path=path)
            content = Path(path).read_text()
            assert "streamlit" in content
        finally:
            os.unlink(path)


class TestGetInstallCommands:
    """Tests for install command generation"""

    def test_no_issues(self):
        status = EnvironmentStatus(
            conda_env_name="rag_hs_code",
            conda_env_active=True,
            python_version="3.11",
            python_version_ok=True,
            packages=[
                PackageStatus(
                    name="p1", required_version="1.0",
                    is_installed=True, version_ok=True, is_dev=False,
                ),
            ],
        )
        commands = get_install_commands(status)
        assert len(commands) == 0

    def test_missing_package(self):
        status = EnvironmentStatus(
            conda_env_name="rag_hs_code",
            conda_env_active=True,
            python_version="3.11",
            python_version_ok=True,
            packages=[
                PackageStatus(name="missing-pkg", required_version="1.0", is_dev=False),
            ],
        )
        commands = get_install_commands(status)
        assert len(commands) == 1
        assert "pip install" in commands[0]
        assert "missing-pkg" in commands[0]

    def test_outdated_package(self):
        status = EnvironmentStatus(
            conda_env_name="rag_hs_code",
            conda_env_active=True,
            python_version="3.11",
            python_version_ok=True,
            packages=[
                PackageStatus(
                    name="old-pkg", required_version="2.0",
                    installed_version="1.0", is_installed=True,
                    version_ok=False, is_dev=False,
                ),
            ],
        )
        commands = get_install_commands(status)
        assert any("--upgrade" in c for c in commands)

    def test_dev_separate(self):
        status = EnvironmentStatus(
            conda_env_name="rag_hs_code",
            conda_env_active=True,
            python_version="3.11",
            python_version_ok=True,
            packages=[
                PackageStatus(name="dev-pkg", required_version="1.0", is_dev=True),
            ],
        )
        commands = get_install_commands(status)
        assert any("dev" in c for c in commands)


class TestConstants:
    """Tests for module constants"""

    def test_required_packages_nonempty(self):
        assert len(REQUIRED_PACKAGES) > 10

    def test_dev_packages_nonempty(self):
        assert len(DEV_PACKAGES) >= 3

    def test_target_env(self):
        assert TARGET_CONDA_ENV == "rag_hs_code"

    def test_target_python(self):
        assert TARGET_PYTHON == "3.11"
