"""
RAG_HS_CODE - CI/CD Configuration Generator
Phase 5: Infrastructure

Generates GitHub Actions workflow YAML and validates CI configuration.
"""

import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


WORKFLOW_TEMPLATE = """\
name: RAG_HS_CODE Tests

on:
  push:
    branches: [{branches}]
  pull_request:
    branches: [{branches}]

jobs:
  test:
    runs-on: {runs_on}
    defaults:
      run:
        shell: bash -l {{0}}

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Conda
        uses: conda-incubator/setup-miniconda@v3
        with:
          activate-environment: {conda_env}
          environment-file: environment.yml
          python-version: "{python_version}"
          auto-activate-base: false

      - name: Install dev dependencies
        run: |
          pip install pytest pytest-cov reportlab openpyxl

      - name: Run Phase 1 Tests
        run: |
          cd project/phase1_security_validation
          python -m pytest tests/ -v --tb=short --junitxml=test-results-phase1.xml

      - name: Run Phase 2 Tests
        run: |
          cd project/phase2_ux_enhancements
          python -m pytest tests/ -v --tb=short --junitxml=test-results-phase2.xml

      - name: Run Phase 3 Tests
        run: |
          cd project/phase3_performance
          python -m pytest tests/ -v --tb=short --junitxml=test-results-phase3.xml

      - name: Run Phase 4 Tests
        run: |
          cd project/phase4_features
          python -m pytest tests/ -v --tb=short --junitxml=test-results-phase4.xml

      - name: Run Phase 5 Tests
        run: |
          cd project/phase5_infrastructure
          python -m pytest tests/ -v --tb=short --junitxml=test-results-phase5.xml

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: test-results
          path: project/**/test-results-*.xml
"""


@dataclass
class CIConfig:
    """CI/CD pipeline configuration."""
    branches: List[str] = field(default_factory=lambda: ["main", "api-key-handling"])
    runs_on: str = "ubuntu-latest"
    python_version: str = "3.11"
    conda_env: str = "rag_hs_code"
    phases: List[str] = field(default_factory=lambda: [
        "phase1", "phase2", "phase3", "phase4", "phase5"
    ])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "branches": self.branches,
            "runs_on": self.runs_on,
            "python_version": self.python_version,
            "conda_env": self.conda_env,
            "phases": self.phases,
        }


def generate_workflow(config: Optional[CIConfig] = None) -> str:
    """
    Generate a GitHub Actions workflow YAML string.

    Args:
        config: CI configuration (uses defaults if None)

    Returns:
        YAML workflow content as string
    """
    if config is None:
        config = CIConfig()

    branches = ", ".join(config.branches)
    return WORKFLOW_TEMPLATE.format(
        branches=branches,
        runs_on=config.runs_on,
        python_version=config.python_version,
        conda_env=config.conda_env,
    )


def write_workflow(
    project_root: Optional[str] = None,
    config: Optional[CIConfig] = None,
) -> str:
    """
    Write the GitHub Actions workflow file to .github/workflows/.

    Args:
        project_root: Root directory of the project
        config: CI configuration

    Returns:
        Path to the written file
    """
    if project_root is None:
        project_root = str(Path(__file__).resolve().parent.parent.parent.parent)

    workflow_dir = Path(project_root) / ".github" / "workflows"
    workflow_dir.mkdir(parents=True, exist_ok=True)

    filepath = workflow_dir / "tests.yml"
    content = generate_workflow(config)
    filepath.write_text(content)

    return str(filepath)


def validate_workflow(content: str) -> Dict[str, Any]:
    """
    Validate a workflow YAML string for common issues.

    Args:
        content: YAML workflow content

    Returns:
        Validation result dict
    """
    issues = []
    warnings = []

    if not content.strip():
        issues.append("Workflow content is empty")
        return {"valid": False, "issues": issues, "warnings": warnings}

    # Check required keys
    required_keys = ["name:", "on:", "jobs:"]
    for key in required_keys:
        if key not in content:
            issues.append(f"Missing required key: {key}")

    # Check for steps
    if "steps:" not in content:
        issues.append("No steps defined in jobs")

    # Check for checkout
    if "actions/checkout" not in content:
        warnings.append("No checkout step (actions/checkout) found")

    # Check for conda setup
    if "setup-miniconda" not in content and "conda" not in content.lower():
        warnings.append("No conda setup step found")

    # Check for test execution
    if "pytest" not in content:
        warnings.append("No pytest step found")

    # Check for artifact upload
    if "upload-artifact" not in content:
        warnings.append("No artifact upload step found")

    return {
        "valid": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
        "has_checkout": "actions/checkout" in content,
        "has_conda": "setup-miniconda" in content,
        "has_pytest": "pytest" in content,
        "has_artifacts": "upload-artifact" in content,
    }


def get_branch_protection_rules() -> Dict[str, Any]:
    """
    Generate recommended branch protection rules for GitHub.

    Returns:
        Dict with branch protection configuration
    """
    return {
        "branch": "main",
        "rules": {
            "require_pull_request_reviews": {
                "required_approving_review_count": 1,
                "dismiss_stale_reviews": True,
            },
            "require_status_checks": {
                "strict": True,
                "contexts": ["test"],
            },
            "enforce_admins": False,
            "required_linear_history": False,
        },
        "setup_command": (
            "gh api repos/{owner}/{repo}/branches/main/protection "
            "--method PUT --input branch-protection.json"
        ),
    }
