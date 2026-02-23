"""Phase 4 test configuration"""
import sys
import os

# Add Phase 4 src
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Add Phase 1 src (for calculators and validators)
sys.path.insert(0, os.path.join(
    os.path.dirname(__file__), '..', '..', 'phase1_security_validation', 'src'
))

# Add Phase 3 src (for caching)
sys.path.insert(0, os.path.join(
    os.path.dirname(__file__), '..', '..', 'phase3_performance', 'src'
))
