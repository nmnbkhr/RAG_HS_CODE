"""
Phase 7: Live Data Integration - Test Configuration

Adds Phase 7 src directory + all dependency phase src dirs to sys.path.
"""

import sys
import os
import tempfile
from pathlib import Path

import pytest

# Add all phase src directories to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
PHASE_DIRS = [
    PROJECT_ROOT / "project" / "phase1_security_validation" / "src",
    PROJECT_ROOT / "project" / "phase2_ux_enhancements" / "src",
    PROJECT_ROOT / "project" / "phase3_performance" / "src",
    PROJECT_ROOT / "project" / "phase4_features" / "src",
    PROJECT_ROOT / "project" / "phase5_infrastructure" / "src",
    PROJECT_ROOT / "project" / "phase6_compliance" / "src",
    PROJECT_ROOT / "project" / "phase7_live_data" / "src",
]

for phase_dir in PHASE_DIRS:
    dir_str = str(phase_dir)
    if dir_str not in sys.path:
        sys.path.insert(0, dir_str)


@pytest.fixture
def tmp_db_dir():
    """Provide a temporary directory for SQLite databases."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def tmp_db_path(tmp_db_dir):
    """Provide a temp database file path."""
    return os.path.join(tmp_db_dir, "test.db")
