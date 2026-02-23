"""
Phase 5: Infrastructure - CI/CD Configuration Tests

Tests for GitHub Actions workflow generation and validation.
"""

import pytest
import os
import tempfile
from pathlib import Path
from ci_config import (
    CIConfig, generate_workflow, write_workflow,
    validate_workflow, get_branch_protection_rules,
    WORKFLOW_TEMPLATE,
)


class TestCIConfig:
    """Tests for CIConfig dataclass"""

    def test_defaults(self):
        config = CIConfig()
        assert "main" in config.branches
        assert config.runs_on == "ubuntu-latest"
        assert config.python_version == "3.11"
        assert config.conda_env == "rag_hs_code"

    def test_custom(self):
        config = CIConfig(branches=["develop"], runs_on="ubuntu-22.04")
        assert config.branches == ["develop"]
        assert config.runs_on == "ubuntu-22.04"

    def test_to_dict(self):
        config = CIConfig()
        d = config.to_dict()
        assert "branches" in d
        assert "runs_on" in d
        assert "python_version" in d

    def test_phases_list(self):
        config = CIConfig()
        assert len(config.phases) == 5
        assert "phase1" in config.phases


class TestGenerateWorkflow:
    """Tests for workflow generation"""

    def test_generates_yaml(self):
        yaml = generate_workflow()
        assert "name:" in yaml
        assert "on:" in yaml
        assert "jobs:" in yaml

    def test_contains_branches(self):
        config = CIConfig(branches=["main", "develop"])
        yaml = generate_workflow(config)
        assert "main" in yaml
        assert "develop" in yaml

    def test_contains_conda_setup(self):
        yaml = generate_workflow()
        assert "setup-miniconda" in yaml
        assert "rag_hs_code" in yaml

    def test_contains_python_version(self):
        yaml = generate_workflow()
        assert "3.11" in yaml

    def test_contains_pytest_steps(self):
        yaml = generate_workflow()
        assert "pytest" in yaml

    def test_contains_all_phases(self):
        yaml = generate_workflow()
        assert "Phase 1" in yaml
        assert "Phase 2" in yaml
        assert "Phase 3" in yaml
        assert "Phase 4" in yaml
        assert "Phase 5" in yaml

    def test_contains_checkout(self):
        yaml = generate_workflow()
        assert "actions/checkout" in yaml

    def test_contains_artifact_upload(self):
        yaml = generate_workflow()
        assert "upload-artifact" in yaml

    def test_contains_junit_xml(self):
        yaml = generate_workflow()
        assert "junitxml" in yaml

    def test_custom_runner(self):
        config = CIConfig(runs_on="self-hosted")
        yaml = generate_workflow(config)
        assert "self-hosted" in yaml


class TestWriteWorkflow:
    """Tests for writing workflow files"""

    def test_creates_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_workflow(project_root=tmpdir)
            assert os.path.exists(path)
            assert path.endswith("tests.yml")

    def test_creates_directories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_workflow(project_root=tmpdir)
            workflow_dir = Path(tmpdir) / ".github" / "workflows"
            assert workflow_dir.exists()

    def test_file_content(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = write_workflow(project_root=tmpdir)
            content = Path(path).read_text()
            assert "name:" in content
            assert "pytest" in content


class TestValidateWorkflow:
    """Tests for workflow validation"""

    def test_valid_workflow(self):
        yaml = generate_workflow()
        result = validate_workflow(yaml)
        assert result["valid"] is True
        assert len(result["issues"]) == 0

    def test_empty_content(self):
        result = validate_workflow("")
        assert result["valid"] is False

    def test_missing_name(self):
        result = validate_workflow("on:\njobs:\n  steps:")
        assert result["valid"] is False

    def test_missing_jobs(self):
        result = validate_workflow("name: test\non: push")
        assert result["valid"] is False

    def test_has_checkout(self):
        yaml = generate_workflow()
        result = validate_workflow(yaml)
        assert result["has_checkout"] is True

    def test_has_conda(self):
        yaml = generate_workflow()
        result = validate_workflow(yaml)
        assert result["has_conda"] is True

    def test_has_pytest(self):
        yaml = generate_workflow()
        result = validate_workflow(yaml)
        assert result["has_pytest"] is True

    def test_has_artifacts(self):
        yaml = generate_workflow()
        result = validate_workflow(yaml)
        assert result["has_artifacts"] is True

    def test_warnings_for_minimal(self):
        result = validate_workflow("name: test\non: push\njobs:\n  test:\n    steps:")
        assert result["valid"] is True
        assert len(result["warnings"]) > 0


class TestBranchProtection:
    """Tests for branch protection rules"""

    def test_returns_dict(self):
        rules = get_branch_protection_rules()
        assert isinstance(rules, dict)

    def test_targets_main(self):
        rules = get_branch_protection_rules()
        assert rules["branch"] == "main"

    def test_requires_reviews(self):
        rules = get_branch_protection_rules()
        assert rules["rules"]["require_pull_request_reviews"]["required_approving_review_count"] >= 1

    def test_requires_status_checks(self):
        rules = get_branch_protection_rules()
        assert "test" in rules["rules"]["require_status_checks"]["contexts"]

    def test_has_setup_command(self):
        rules = get_branch_protection_rules()
        assert "gh api" in rules["setup_command"]
