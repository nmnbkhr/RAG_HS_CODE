"""
Integration Tests - Shared Fixtures and Path Setup

Provides sys.path configuration, mock data, and reusable fixtures
for testing the integrated app across all 5 phases.
"""

import sys
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Add all phase src directories to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
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


# --- Sample Data ---

SAMPLE_HS_CODE = "0808.1000"
SAMPLE_HS_CODE_ALT = "6109.1000"

SAMPLE_WEBOC_RESULT = {
    "hs_code": "0808.1000",
    "status": "success",
    "customs_duty": 20.0,
    "sales_tax": 18.0,
    "income_tax": 5.5,
    "additional_duty": 0.0,
    "regulatory_duty": 0.0,
    "description": "Fresh apples",
    "unit_of_measure": "kg",
    "source": "WEBOC",
}

SAMPLE_WEBOC_RESULT_ALT = {
    "hs_code": "6109.1000",
    "status": "success",
    "customs_duty": 25.0,
    "sales_tax": 18.0,
    "income_tax": 5.5,
    "additional_duty": 2.0,
    "regulatory_duty": 0.0,
    "description": "T-shirts, singlets and other vests, knitted or crocheted, of cotton",
    "unit_of_measure": "units",
    "source": "WEBOC",
}

SAMPLE_NBP_RATES = {
    "tt_buying": 278.50,
    "tt_selling": 280.50,
    "source": "NBP",
}

SAMPLE_EXCHANGE_RATE = 280.50
SAMPLE_EXCHANGE_RATE_SOURCE = "NBP TT Selling (Import Rate)"

SAMPLE_CSV_CONTENT = """hs_code,description,quantity,unit,unit_value,currency,customs_duty,sales_tax,income_tax
0808.1000,Fresh Apples,100,kg,10.00,USD,20,18,5.5
6109.1000,Cotton T-shirts,50,units,15.00,USD,25,18,5.5
"""

SAMPLE_CSV_CONTENT_MINIMAL = """hs_code,quantity,unit_value
0808.1000,100,10.00
"""


# --- Fixtures ---

@pytest.fixture
def tmp_db_dir():
    """Provide a temporary directory for SQLite databases."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_weboc_data():
    """Sample WEBOC duty data."""
    return SAMPLE_WEBOC_RESULT.copy()


@pytest.fixture
def sample_weboc_data_alt():
    """Alternate sample WEBOC duty data."""
    return SAMPLE_WEBOC_RESULT_ALT.copy()


@pytest.fixture
def sample_exchange_rate():
    """Sample exchange rate tuple."""
    return SAMPLE_EXCHANGE_RATE, SAMPLE_EXCHANGE_RATE_SOURCE


@pytest.fixture
def sample_csv():
    """Sample CSV content."""
    return SAMPLE_CSV_CONTENT


@pytest.fixture
def history_manager():
    """Fresh HistoryManager instance."""
    from history_manager import HistoryManager
    return HistoryManager(capacity=50)


@pytest.fixture
def favorites_manager(tmp_db_dir):
    """FavoritesManager with temp database."""
    from favorites_manager import FavoritesManager
    db_path = os.path.join(tmp_db_dir, "favorites_test.db")
    return FavoritesManager(db_path=db_path)


@pytest.fixture
def exchange_cache(tmp_db_dir):
    """ExchangeRateCache with temp database."""
    from exchange_rate_cache import ExchangeRateCache
    db_path = os.path.join(tmp_db_dir, "exchange_test.db")
    return ExchangeRateCache(db_path=db_path, ttl=3600)


@pytest.fixture
def weboc_cache(tmp_db_dir):
    """WEBOCCache with temp database."""
    from weboc_cache import WEBOCCache
    db_path = os.path.join(tmp_db_dir, "weboc_test.db")
    return WEBOCCache(db_path=db_path, ttl=86400)


@pytest.fixture
def query_cache(tmp_db_dir):
    """QueryCache with temp database."""
    from query_cache import QueryCache
    db_path = os.path.join(tmp_db_dir, "query_test.db")
    return QueryCache(db_path=db_path, ttl=43200)


@pytest.fixture
def perf_monitor():
    """Fresh PerformanceMonitor."""
    from performance_monitor import PerformanceMonitor
    return PerformanceMonitor()


@pytest.fixture
def currency_manager():
    """Fresh MultiCurrencyManager."""
    from multi_currency import MultiCurrencyManager
    mgr = MultiCurrencyManager()
    mgr.set_rate("USD", 280.50, source="Test")
    mgr.set_rate("EUR", 310.00, source="Test")
    mgr.set_rate("GBP", 360.00, source="Test")
    return mgr
