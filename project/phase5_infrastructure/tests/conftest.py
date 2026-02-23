"""Phase 5: Infrastructure - Test Configuration"""

import sys
import os

# Add Phase 5 src to path
phase5_src = os.path.join(os.path.dirname(os.path.dirname(__file__)), "src")
sys.path.insert(0, phase5_src)

# Add project root for cross-phase access
project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, project_root)
