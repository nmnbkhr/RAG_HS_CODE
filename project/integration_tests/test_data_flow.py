"""
Integration Tests - End-to-End Data Flow

Tests complete data flows through multiple modules with mocked external services.
"""

import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock


class TestImportDataFlow:
    """Full import calculation flow through modules."""

    def test_hs_code_to_calculation_to_history(self, history_manager):
        """HS code validation -> duty calculation -> history record."""
        from validators import HSCodeValidator
        from calculators import ImportDutyCalculator, DutyRates, CIFComponents

        # Step 1: Validate HS code
        hs_result = HSCodeValidator.validate("08081000")
        assert hs_result.is_valid
        assert hs_result.value == "0808.1000"

        # Step 2: Calculate duties
        calc = ImportDutyCalculator.calculate(
            hs_code=hs_result.value, quantity=100, unit_of_measure="kg",
            unit_value=10.0, currency="USD", exchange_rate=280.0,
            exchange_rate_source="Test",
            duty_rates=DutyRates(customs_duty=20.0, sales_tax=18.0, income_tax=5.5),
            cif_components=CIFComponents(fob_value=1000.0),
        )
        assert calc.validation_passed
        assert calc.total_landed_cost > 0

        # Step 3: Record in history
        entry = history_manager.add_import_calculation(
            hs_code=calc.hs_code, description="Fresh apples",
            quantity=calc.quantity, unit=calc.unit_of_measure,
            unit_value=calc.unit_value_foreign, currency=calc.currency,
            exchange_rate=calc.exchange_rate,
            cif_pkr=calc.cif_value_pkr, total_duties=calc.total_duties,
            landed_cost=calc.total_landed_cost,
        )
        assert entry is not None

        # Step 4: Verify history
        assert history_manager.count == 1
        found = history_manager.search("0808")
        assert len(found) == 1
        assert found[0].result_summary.landed_cost == calc.total_landed_cost

    def test_calculation_to_pdf_export(self):
        """Calculation -> PDF export produces valid PDF."""
        from calculators import ImportDutyCalculator, DutyRates, CIFComponents
        from pdf_exporter import DutyCalculationPDF

        calc = ImportDutyCalculator.calculate(
            hs_code="0808.1000", quantity=100, unit_of_measure="kg",
            unit_value=10.0, currency="USD", exchange_rate=280.0,
            exchange_rate_source="Test",
            duty_rates=DutyRates(customs_duty=20.0, sales_tax=18.0, income_tax=5.5),
            cif_components=CIFComponents(fob_value=1000.0),
        )

        pdf = DutyCalculationPDF()
        pdf_bytes = pdf.generate_import_report(
            hs_code=calc.hs_code, description="Fresh apples",
            quantity=calc.quantity, unit=calc.unit_of_measure,
            unit_value=calc.unit_value_foreign, currency=calc.currency,
            exchange_rate=calc.exchange_rate, exchange_rate_source="Test",
            fob_value=calc.fob_value_foreign, freight=0, insurance=0, other_charges=0,
            cif_foreign=calc.cif_value_foreign, cif_pkr=calc.cif_value_pkr,
            customs_duty_rate=calc.customs_duty_rate, customs_duty_amount=calc.customs_duty_amount,
            sales_tax_rate=calc.sales_tax_rate, sales_tax_amount=calc.sales_tax_amount,
            income_tax_rate=calc.income_tax_rate, income_tax_amount=calc.income_tax_amount,
            total_duties=calc.total_duties, landed_cost=calc.total_landed_cost,
        )

        assert pdf_bytes[:4] == b'%PDF'
        assert len(pdf_bytes) > 1000

    def test_calculation_to_excel_export(self):
        """Calculation -> Excel export produces valid Excel."""
        from calculators import ImportDutyCalculator, DutyRates, CIFComponents
        from excel_exporter import DutyCalculationExcel

        calc = ImportDutyCalculator.calculate(
            hs_code="0808.1000", quantity=100, unit_of_measure="kg",
            unit_value=10.0, currency="USD", exchange_rate=280.0,
            exchange_rate_source="Test",
            duty_rates=DutyRates(customs_duty=20.0, sales_tax=18.0, income_tax=5.5),
            cif_components=CIFComponents(fob_value=1000.0),
        )

        excel = DutyCalculationExcel()
        excel_bytes = excel.generate_import_workbook(
            hs_code=calc.hs_code, description="Fresh apples",
            quantity=calc.quantity, unit=calc.unit_of_measure,
            unit_value=calc.unit_value_foreign, currency=calc.currency,
            exchange_rate=calc.exchange_rate, exchange_rate_source="Test",
            customs_duty_rate=calc.customs_duty_rate,
            sales_tax_rate=calc.sales_tax_rate,
            income_tax_rate=calc.income_tax_rate,
        )

        assert len(excel_bytes) > 1000
        # Excel files start with PK (ZIP format)
        assert excel_bytes[:2] == b'PK'


class TestExportDataFlow:
    """Full export calculation flow through modules."""

    def test_export_calculation_to_history(self, history_manager):
        from calculators import ExportCalculator

        export = ExportCalculator.calculate(
            hs_code="6109.1000", quantity=50, unit_of_measure="units",
            fob_per_unit=15.0, currency="USD", exchange_rate=278.50,
            exchange_rate_source="Test", export_scheme="Normal Export",
        )
        assert export.validation_passed

        entry = history_manager.add_export_calculation(
            hs_code=export.hs_code, description="Cotton T-shirts",
            quantity=export.quantity, unit=export.unit_of_measure,
            unit_value=export.fob_per_unit_foreign, currency=export.currency,
            exchange_rate=export.exchange_rate,
            fob_pkr=export.total_fob_pkr, net_proceeds=export.net_proceeds_pkr,
        )
        assert entry.result_summary.net_proceeds == export.net_proceeds_pkr

    def test_export_with_regulatory_duty(self):
        from calculators import ExportCalculator

        export = ExportCalculator.calculate(
            hs_code="2523.1000", quantity=1000, unit_of_measure="kg",
            fob_per_unit=0.50, currency="USD", exchange_rate=278.50,
            exchange_rate_source="Test",
            regulatory_duty_rate=5.0, export_scheme="Normal Export",
        )
        assert export.regulatory_duty_amount > 0
        assert export.net_proceeds_pkr < export.total_fob_pkr

    def test_export_drawback_eligible(self):
        from calculators import ExportCalculator

        export = ExportCalculator.calculate(
            hs_code="6109.1000", quantity=50, unit_of_measure="units",
            fob_per_unit=15.0, currency="USD", exchange_rate=278.50,
            exchange_rate_source="Test",
            export_scheme="DTRE (Duty & Tax Remission)",
        )
        assert export.drawback_eligible
        assert export.estimated_drawback > 0


class TestBatchDataFlow:
    """Batch processing data flow."""

    def test_csv_to_batch_results_to_export(self, sample_csv):
        from batch_processor import process_batch, export_batch_csv

        result = process_batch(sample_csv, exchange_rate=280.0, exchange_rate_source="Test")
        assert result.total_rows == 2
        assert result.succeeded >= 1

        csv_output = export_batch_csv(result)
        assert "Row" in csv_output
        assert "Landed Cost" in csv_output
        lines = csv_output.strip().split('\n')
        assert len(lines) >= 2  # header + at least 1 data row

    def test_batch_with_default_rates(self):
        from batch_processor import process_batch

        csv = "hs_code,quantity,unit_value\n0808.1000,100,10.00\n"
        result = process_batch(
            csv, exchange_rate=280.0, exchange_rate_source="Test",
            default_rates={"customs_duty": 20.0, "sales_tax": 18.0, "income_tax": 5.5}
        )
        assert result.succeeded == 1
        row = result.rows[0]
        assert row.customs_duty_rate == 20.0
        assert row.total_landed_cost > 0

    def test_batch_handles_invalid_rows(self):
        from batch_processor import process_batch

        csv = "hs_code,quantity,unit_value\n0808.1000,100,10.00\n,0,-5\n"
        result = process_batch(csv, exchange_rate=280.0)
        assert result.failed >= 1


class TestComparisonDataFlow:
    """Duty comparison data flow."""

    def test_multiple_codes_compared_and_ranked(self):
        from duty_comparator import DutyComparator, DutyProfile

        profiles = [
            DutyProfile(hs_code="0808.1000", description="Apples",
                        customs_duty_rate=20.0, sales_tax_rate=18.0, income_tax_rate=5.5),
            DutyProfile(hs_code="0101.2100", description="Horses",
                        customs_duty_rate=0.0, sales_tax_rate=18.0, income_tax_rate=5.5),
            DutyProfile(hs_code="6109.1000", description="T-shirts",
                        customs_duty_rate=25.0, sales_tax_rate=18.0, income_tax_rate=5.5,
                        additional_duty_rate=2.0),
        ]

        result = DutyComparator.compare(
            profiles, quantity=100, unit="kg", unit_value=10.0,
            currency="USD", exchange_rate=280.0,
        )

        assert result.item_count == 3
        assert result.cheapest_code == "0101.2100"  # 0% CD
        assert result.most_expensive_code == "6109.1000"  # 25% CD + 2% AD

        # Verify ranking order
        for i, item in enumerate(result.items):
            assert item.rank == i + 1

        # Cheapest should have 0 difference
        cheapest = [i for i in result.items if i.is_cheapest][0]
        assert cheapest.difference_from_cheapest == 0


class TestCacheDataFlow:
    """Cache data flow through operations."""

    def test_exchange_rate_cached_and_reused(self, exchange_cache):
        # First call: store rate
        exchange_cache.put("USD", tt_buying=278.50, tt_selling=280.50, source="NBP")

        # Second call: retrieve from cache
        cached = exchange_cache.get("USD")
        assert cached is not None
        assert cached.tt_selling == 280.50
        assert not cached.is_expired

    def test_weboc_cache_stores_and_converts_to_dict(self, weboc_cache):
        duty_data = {
            "customs_duty": 20.0, "sales_tax": 18.0,
            "income_tax": 5.5, "additional_duty": 0, "regulatory_duty": 0,
            "description": "Fresh apples", "unit_of_measure": "kg",
        }
        weboc_cache.put(hs_code="0808.1000", duty_data=duty_data, source="WEBOC")

        cached = weboc_cache.get("0808.1000")
        assert cached is not None

        # Convert to dict (same format as WEBOC scraper output)
        d = cached.to_dict()
        assert d["status"] == "success"
        assert d["customs_duty"] == 20.0
        assert d["cached"] is True

    def test_query_cache_deduplicates_similar_queries(self, query_cache):
        query_cache.put("What is the duty for apples?", "20% CD")
        # Similar query (different case)
        cached = query_cache.get("what is the duty for apples?")
        # Should find it via normalization
        assert cached is not None


class TestFavoritesDataFlow:
    """Favorites data flow."""

    def test_favorite_lifecycle(self, favorites_manager):
        # Add
        favorites_manager.add(hs_code="0808.1000", description="Fresh apples",
                              customs_duty_rate=20.0, tags=["fruit", "food"])
        # Retrieve
        fav = favorites_manager.get("0808.1000")
        assert fav is not None
        assert "fruit" in fav.tags

        # Record usage
        favorites_manager.record_use("0808.1000")
        fav = favorites_manager.get("0808.1000")
        assert fav.use_count == 1

        # Search
        results = favorites_manager.search("apple")
        assert len(results) == 1

        # Get by tag
        by_tag = favorites_manager.get_by_tag("fruit")
        assert len(by_tag) == 1

        # Export
        json_data = favorites_manager.export_json()
        assert "0808.1000" in json_data

        # Remove
        favorites_manager.remove("0808.1000")
        assert favorites_manager.get("0808.1000") is None

    def test_favorites_persist_across_instances(self, tmp_db_dir):
        from favorites_manager import FavoritesManager

        db_path = os.path.join(tmp_db_dir, "persist_test.db")

        # Instance 1: Add favorite
        fm1 = FavoritesManager(db_path=db_path)
        fm1.add(hs_code="0808.1000", description="Fresh apples")

        # Instance 2: Should find it (same DB)
        fm2 = FavoritesManager(db_path=db_path)
        fav = fm2.get("0808.1000")
        assert fav is not None
        assert fav.description == "Fresh apples"


class TestPerformanceTracking:
    """Performance tracking across operations."""

    def test_multiple_operations_tracked(self, perf_monitor):
        import time

        with perf_monitor.track("fast_op"):
            pass  # Very fast operation

        with perf_monitor.track("slow_op"):
            time.sleep(0.01)

        summary = perf_monitor.get_summary()
        assert summary["total_requests"] == 2

        fast_stats = perf_monitor.get_stats("fast_op")
        assert fast_stats["count"] == 1

        slow_stats = perf_monitor.get_stats("slow_op")
        assert slow_stats["count"] == 1
        assert slow_stats["avg_ms"] >= 5  # At least 5ms

    def test_all_stats_returns_all_operations(self, perf_monitor):
        with perf_monitor.track("op_a"):
            pass
        with perf_monitor.track("op_b"):
            pass

        all_stats = perf_monitor.get_all_stats()
        assert "op_a" in all_stats
        assert "op_b" in all_stats


class TestConfigDataFlow:
    """Config used throughout the application."""

    def test_config_provides_all_required_values(self):
        from app_config import AppPaths, ExternalURLs, CacheSettings, AppLimits

        urls = ExternalURLs()
        assert "weboc.gov.pk" in urls.weboc_tariff
        assert "nbp.com.pk" in urls.nbp_rates
        assert "fbr.gov.pk" in urls.pdf_source

        cache = CacheSettings()
        assert cache.exchange_rate_ttl_hours == 4.0
        assert cache.weboc_ttl_hours == 24.0

        limits = AppLimits()
        assert limits.max_batch_rows == 10000
        assert limits.max_comparison_codes == 5

    def test_env_validation(self):
        from app_config import validate_env_vars

        result = validate_env_vars({"OPENAI_API_KEY": "sk-test12345678901234567890"})
        assert result.valid

        result_missing = validate_env_vars({})
        assert not result_missing.valid
        assert "OPENAI_API_KEY" in result_missing.missing
