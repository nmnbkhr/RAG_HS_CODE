"""
Phase 2: UX Enhancements - Pytest Configuration

Adds the src directory to Python path for test imports.
"""

import sys
from pathlib import Path

# Add src directory to path
src_dir = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_dir))
