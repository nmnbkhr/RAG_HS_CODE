"""
Pytest configuration for Phase 1 tests.
Sets up the path to find src modules.
"""

import sys
from pathlib import Path

# Add src directory to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))
