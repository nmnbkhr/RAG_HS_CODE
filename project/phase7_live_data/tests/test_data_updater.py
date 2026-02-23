"""
Phase 7: Live Data Integration - Data Freshness Checker Tests
"""

import os
import time
import json
import pytest
from unittest.mock import MagicMock
from data_updater import DataFreshnessChecker, StaleDataReport


class TestStaleDataReport:
    """Tests for StaleDataReport dataclass"""

    def test_create(self):
        report = StaleDataReport(
            module="fed_rates",
            hs_code="8703.2300",
            field_name="fed_rate",
            static_value=7.5,
            live_value=10.0,
            difference_pct=2.5,
            recommendation="update_static",
        )
        assert report.module == "fed_rates"
        assert report.difference_pct == 2.5

    def test_to_dict(self):
        report = StaleDataReport(
            module="fed_rates", hs_code="8703.2300", field_name="fed_rate",
            static_value=7.5, live_value=10.0, difference_pct=2.5,
            recommendation="update_static",
        )
        d = report.to_dict()
        assert d["module"] == "fed_rates"
        assert d["hs_code"] == "8703.2300"
        assert d["static_value"] == 7.5
        assert d["live_value"] == 10.0


class TestDataFreshnessChecker:
    """Tests for DataFreshnessChecker"""

    def test_init_creates_db(self, tmp_db_dir):
        db_path = os.path.join(tmp_db_dir, "freshness.db")
        checker = DataFreshnessChecker(db_path=db_path)
        assert os.path.exists(db_path)

    def test_needs_check_first_time(self, tmp_db_dir):
        db_path = os.path.join(tmp_db_dir, "freshness.db")
        checker = DataFreshnessChecker(db_path=db_path)
        assert checker.needs_check() is True

    def test_get_last_check_time_none(self, tmp_db_dir):
        db_path = os.path.join(tmp_db_dir, "freshness.db")
        checker = DataFreshnessChecker(db_path=db_path)
        assert checker.get_last_check_time() is None

    def test_check_fed_rates_no_modules(self, tmp_db_dir):
        db_path = os.path.join(tmp_db_dir, "freshness.db")
        checker = DataFreshnessChecker(db_path=db_path)
        reports = checker.check_fed_rates()
        assert reports == []

    def test_check_fed_rates_no_tipp(self, tmp_db_dir):
        db_path = os.path.join(tmp_db_dir, "freshness.db")
        mock_fed = MagicMock()
        mock_fed.FED_RATES = {"8703.2300": MagicMock(rate_pct=7.5)}
        checker = DataFreshnessChecker(
            fed_rates_module=mock_fed, db_path=db_path
        )
        reports = checker.check_fed_rates()
        assert reports == []  # No TIPP cache = nothing to compare

    def test_check_fed_rates_match(self, tmp_db_dir):
        db_path = os.path.join(tmp_db_dir, "freshness.db")
        mock_fed = MagicMock()
        mock_entry = MagicMock()
        mock_entry.rate_pct = 7.5
        mock_fed.FED_RATES = {"8703.2300": mock_entry}

        mock_tipp = MagicMock()
        mock_tipp_result = MagicMock()
        mock_tipp_result.fed_rate = 7.5
        mock_tipp.get.return_value = mock_tipp_result
        mock_tipp.get_or_fallback.return_value = mock_tipp_result

        checker = DataFreshnessChecker(
            tipp_cache=mock_tipp, fed_rates_module=mock_fed, db_path=db_path
        )
        reports = checker.check_fed_rates()
        assert len(reports) == 0  # No discrepancy

    def test_check_fed_rates_discrepancy(self, tmp_db_dir):
        db_path = os.path.join(tmp_db_dir, "freshness.db")
        mock_fed = MagicMock()
        mock_entry = MagicMock()
        mock_entry.rate_pct = 7.5
        mock_fed.FED_RATES = {"8703.2300": mock_entry}

        mock_tipp = MagicMock()
        mock_tipp_result = MagicMock()
        mock_tipp_result.fed_rate = 10.0  # Different!
        mock_tipp.get.return_value = mock_tipp_result
        mock_tipp.get_or_fallback.return_value = mock_tipp_result

        checker = DataFreshnessChecker(
            tipp_cache=mock_tipp, fed_rates_module=mock_fed,
            db_path=db_path, threshold=0.5,
        )
        reports = checker.check_fed_rates()
        assert len(reports) == 1
        assert reports[0].static_value == 7.5
        assert reports[0].live_value == 10.0
        assert reports[0].difference_pct == 2.5
        assert reports[0].recommendation == "update_static"

    def test_check_fed_rates_small_difference_ignored(self, tmp_db_dir):
        db_path = os.path.join(tmp_db_dir, "freshness.db")
        mock_fed = MagicMock()
        mock_entry = MagicMock()
        mock_entry.rate_pct = 7.5
        mock_fed.FED_RATES = {"8703.2300": mock_entry}

        mock_tipp = MagicMock()
        mock_tipp_result = MagicMock()
        mock_tipp_result.fed_rate = 7.6  # Small difference
        mock_tipp.get.return_value = mock_tipp_result
        mock_tipp.get_or_fallback.return_value = mock_tipp_result

        checker = DataFreshnessChecker(
            tipp_cache=mock_tipp, fed_rates_module=mock_fed,
            db_path=db_path, threshold=0.5,
        )
        reports = checker.check_fed_rates()
        assert len(reports) == 0  # Below threshold

    def test_check_fifth_schedule_discrepancy(self, tmp_db_dir):
        db_path = os.path.join(tmp_db_dir, "freshness.db")
        mock_fifth = MagicMock()
        mock_entry = MagicMock()
        mock_entry.mfn_cd_rate = 20.0
        mock_fifth.FIFTH_SCHEDULE_RATES = {"8471.3000": mock_entry}

        mock_tipp = MagicMock()
        mock_tipp_result = MagicMock()
        mock_tipp_result.mfn_cd_rate = 25.0  # Changed!
        mock_tipp.get.return_value = mock_tipp_result
        mock_tipp.get_or_fallback.return_value = mock_tipp_result

        checker = DataFreshnessChecker(
            tipp_cache=mock_tipp, fifth_schedule_module=mock_fifth,
            db_path=db_path,
        )
        reports = checker.check_fifth_schedule()
        assert len(reports) == 1
        assert reports[0].field_name == "mfn_cd_rate"

    def test_check_fta_rates_discrepancy(self, tmp_db_dir):
        db_path = os.path.join(tmp_db_dir, "freshness.db")
        mock_fta = MagicMock()
        mock_rate = MagicMock()
        mock_rate.hs_code = "0808.1000"
        mock_rate.preferential_cd_rate = 0.0
        mock_fta.PREFERENTIAL_RATES = {"CPFTA": [mock_rate]}

        mock_tipp = MagicMock()
        mock_tipp_result = MagicMock()
        mock_tipp_result.preferential_rates = {"CPFTA": 5.0}  # Changed!
        mock_tipp.get.return_value = mock_tipp_result
        mock_tipp.get_or_fallback.return_value = mock_tipp_result

        checker = DataFreshnessChecker(
            tipp_cache=mock_tipp, fta_pta_module=mock_fta,
            db_path=db_path,
        )
        reports = checker.check_fta_rates()
        assert len(reports) == 1
        assert "CPFTA" in reports[0].field_name

    def test_run_full_check(self, tmp_db_dir):
        db_path = os.path.join(tmp_db_dir, "freshness.db")
        checker = DataFreshnessChecker(db_path=db_path)
        results = checker.run_full_check()
        assert "fed_rates" in results
        assert "fifth_schedule" in results
        assert "fta_pta" in results

    def test_run_full_check_records_timestamp(self, tmp_db_dir):
        db_path = os.path.join(tmp_db_dir, "freshness.db")
        checker = DataFreshnessChecker(db_path=db_path)
        checker.run_full_check()
        last = checker.get_last_check_time()
        assert last is not None
        assert last > 0

    def test_needs_check_after_run(self, tmp_db_dir):
        db_path = os.path.join(tmp_db_dir, "freshness.db")
        checker = DataFreshnessChecker(db_path=db_path)
        checker.run_full_check()
        # Just ran — shouldn't need check for another week
        assert checker.needs_check(interval_hours=168) is False
        # But needs check if interval is 0
        assert checker.needs_check(interval_hours=0) is True

    def test_get_summary(self, tmp_db_dir):
        db_path = os.path.join(tmp_db_dir, "freshness.db")
        checker = DataFreshnessChecker(db_path=db_path)
        summary = checker.get_summary()
        assert "last_check" in summary
        assert "needs_check" in summary
        assert "modules" in summary
        assert summary["last_check_display"] == "never"

    def test_get_summary_after_check(self, tmp_db_dir):
        db_path = os.path.join(tmp_db_dir, "freshness.db")
        checker = DataFreshnessChecker(db_path=db_path)
        checker.run_full_check()
        summary = checker.get_summary()
        assert summary["last_check"] is not None
        assert summary["last_check_display"] != "never"

    def test_get_last_report_empty(self, tmp_db_dir):
        db_path = os.path.join(tmp_db_dir, "freshness.db")
        checker = DataFreshnessChecker(db_path=db_path)
        report = checker.get_last_report()
        assert report["fed_rates"] == []
        assert report["fifth_schedule"] == []
        assert report["fta_pta"] == []

    def test_sample_codes_parameter(self, tmp_db_dir):
        db_path = os.path.join(tmp_db_dir, "freshness.db")
        mock_fed = MagicMock()
        mock_entry = MagicMock()
        mock_entry.rate_pct = 7.5
        mock_fed.FED_RATES = {"8703.2300": mock_entry, "8703.2400": MagicMock(rate_pct=10.0)}

        mock_tipp = MagicMock()
        mock_tipp_result = MagicMock()
        mock_tipp_result.fed_rate = 7.5
        mock_tipp.get.return_value = mock_tipp_result
        mock_tipp.get_or_fallback.return_value = mock_tipp_result

        checker = DataFreshnessChecker(
            tipp_cache=mock_tipp, fed_rates_module=mock_fed, db_path=db_path
        )
        # Only check one code
        reports = checker.check_fed_rates(sample_codes=["8703.2300"])
        assert len(reports) == 0
