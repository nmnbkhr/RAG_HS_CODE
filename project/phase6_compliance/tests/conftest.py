"""
Phase 6: Compliance - Test Configuration

Adds Phase 6 src directory to sys.path for imports.
"""

import sys
from pathlib import Path

# Add Phase 6 src to path
PHASE6_SRC = Path(__file__).resolve().parent.parent / "src"
if str(PHASE6_SRC) not in sys.path:
    sys.path.insert(0, str(PHASE6_SRC))
