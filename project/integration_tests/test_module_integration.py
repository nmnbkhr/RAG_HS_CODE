"""
Integration Tests - Cross-Module Integration

Tests that phase modules work together correctly WITHOUT Streamlit.
"""

import pytest
import os
import tempfile
from decimal import Decimal


class TestValidatorCalculatorIntegration:
    """Phase 1 validators + calculators working together."""

    def test_validated_hs_code_feeds_into_calculator(self):
        from validators import HSCodeValidator
        from calculators import ImportDutyCalculator, DutyRates, CIFComponents

        result = HSCodeValidator.validate("0808.1000")
        assert result.is_valid

        calc = ImportDutyCalculator.calculate(
            hs_code=result.value, quantity=100, unit_of_measure="kg",
            unit_value=10.0, currency="USD", exchange_rate=280.0,
            exchange_rate_source="Test", duty_rates=DutyRates(customs_duty=20.0, sales_tax=18.0, income_tax=5.5),
            cif_components=CIFComponents(fob_value=1000.0),
        )
        assert calc.cif_value_pkr == 280000.0
        assert calc.customs_duty_amount == 56000.0

    def test_partial_hs_code_normalized_then_calculated(self):
        from validators import HSCodeValidator
        from calculators import ImportDutyCalculator, DutyRates, CIFComponents

        result = HSCodeValidator.validate("0808.10")
        assert result.is_valid
        assert result.value == "0808.1000"

        calc = ImportDutyCalculator.calculate(
            hs_code=result.value, quantity=1, unit_of_measure="kg",
            unit_value=100.0, currency="USD", exchange_rate=280.0,
            exchange_rate_source="Test", duty_rates=DutyRates(customs_duty=10.0, sales_tax=18.0, income_tax=5.5),
            cif_components=CIFComponents(fob_value=100.0),
        )
        assert calc.total_landed_cost > calc.cif_value_pkr

    def test_invalid_hs_code_rejected_before_calculation(self):
        from validators import HSCodeValidator

        result = HSCodeValidator.validate("abc")
        assert not result.is_valid

    def test_numeric_validator_on_calculator_inputs(self):
        from validators import NumericValidator

        qty = NumericValidator.validate_positive(100, "Quantity", allow_zero=False)
        assert qty.is_valid
        assert qty.value == 100.0

        neg = NumericValidator.validate_positive(-5, "Quantity")
        assert not neg.is_valid

    def test_exchange_rate_validator_bounds(self):
        from validators import ExchangeRateValidator

        valid = ExchangeRateValidator.validate_pkr_rate(280.50)
        assert valid.is_valid

        too_low = ExchangeRateValidator.validate_pkr_rate(100.0)
        assert not too_low.is_valid

    def test_export_calculator_with_validation(self):
        from validators import HSCodeValidator
        from calculators import ExportCalculator

        result = HSCodeValidator.validate("6109.1000")
        assert result.is_valid

        export = ExportCalculator.calculate(
            hs_code=result.value, quantity=50, unit_of_measure="units",
            fob_per_unit=15.0, currency="USD", exchange_rate=278.50,
            exchange_rate_source="Test",
        )
        assert export.total_fob_pkr > 0
        assert export.net_proceeds_pkr == export.total_fob_pkr  # No regulatory duty


class TestCalculatorHistoryIntegration:
    """Phase 1 calculators + Phase 2 history working together."""

    def test_import_calculation_recorded_in_history(self, history_manager):
        from calculators import ImportDutyCalculator, DutyRates, CIFComponents

        calc = ImportDutyCalculator.calculate(
            hs_code="0808.1000", quantity=100, unit_of_measure="kg",
            unit_value=10.0, currency="USD", exchange_rate=280.0,
            exchange_rate_source="Test", duty_rates=DutyRates(customs_duty=20.0, sales_tax=18.0, income_tax=5.5),
            cif_components=CIFComponents(fob_value=1000.0),
        )

        entry = history_manager.add_import_calculation(
            hs_code=calc.hs_code, description="Fresh apples",
            quantity=calc.quantity, unit=calc.unit_of_measure,
            unit_value=calc.unit_value_foreign, currency=calc.currency,
            exchange_rate=calc.exchange_rate,
            cif_pkr=calc.cif_value_pkr, total_duties=calc.total_duties,
            landed_cost=calc.total_landed_cost,
        )

        assert history_manager.count == 1
        assert entry.input_summary.hs_code == "0808.1000"
        assert entry.result_summary.landed_cost == calc.total_landed_cost

    def test_export_calculation_recorded_in_history(self, history_manager):
        from calculators import ExportCalculator

        export = ExportCalculator.calculate(
            hs_code="6109.1000", quantity=50, unit_of_measure="units",
            fob_per_unit=15.0, currency="USD", exchange_rate=278.50,
            exchange_rate_source="Test",
        )

        entry = history_manager.add_export_calculation(
            hs_code=export.hs_code, description="Cotton T-shirts",
            quantity=export.quantity, unit=export.unit_of_measure,
            unit_value=export.fob_per_unit_foreign, currency=export.currency,
            exchange_rate=export.exchange_rate,
            fob_pkr=export.total_fob_pkr, net_proceeds=export.net_proceeds_pkr,
        )

        assert history_manager.count == 1
        assert entry.result_summary.net_proceeds == export.net_proceeds_pkr

    def test_history_search_finds_recorded_calculation(self, history_manager):
        history_manager.add_import_calculation(
            hs_code="0808.1000", description="Fresh apples",
            quantity=100, unit="kg", unit_value=10.0, currency="USD",
            exchange_rate=280.0, cif_pkr=280000.0, total_duties=131880.0,
            landed_cost=411880.0,
        )

        results = history_manager.search("0808")
        assert len(results) == 1
        assert results[0].input_summary.hs_code == "0808.1000"


class TestCalculatorExporterIntegration:
    """Phase 1 calculators + Phase 2 PDF/Excel exporters."""

    def test_calculator_result_generates_pdf(self):
        from calculators import ImportDutyCalculator, DutyRates, CIFComponents
        from pdf_exporter import DutyCalculationPDF

        calc = ImportDutyCalculator.calculate(
            hs_code="0808.1000", quantity=100, unit_of_measure="kg",
            unit_value=10.0, currency="USD", exchange_rate=280.0,
            exchange_rate_source="Test", duty_rates=DutyRates(customs_duty=20.0, sales_tax=18.0, income_tax=5.5),
            cif_components=CIFComponents(fob_value=1000.0),
        )

        pdf = DutyCalculationPDF()
        pdf_bytes = pdf.generate_import_report(
            hs_code=calc.hs_code, description="Fresh apples",
            quantity=calc.quantity, unit=calc.unit_of_measure,
            unit_value=calc.unit_value_foreign, currency=calc.currency,
            exchange_rate=calc.exchange_rate, exchange_rate_source=calc.exchange_rate_source,
            fob_value=calc.fob_value_foreign, freight=0, insurance=0, other_charges=0,
            cif_foreign=calc.cif_value_foreign, cif_pkr=calc.cif_value_pkr,
            customs_duty_rate=calc.customs_duty_rate, customs_duty_amount=calc.customs_duty_amount,
            sales_tax_rate=calc.sales_tax_rate, sales_tax_amount=calc.sales_tax_amount,
            income_tax_rate=calc.income_tax_rate, income_tax_amount=calc.income_tax_amount,
            total_duties=calc.total_duties, landed_cost=calc.total_landed_cost,
        )

        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 100
        assert pdf_bytes[:4] == b'%PDF'

    def test_calculator_result_generates_excel(self):
        from calculators import ImportDutyCalculator, DutyRates, CIFComponents
        from excel_exporter import DutyCalculationExcel

        calc = ImportDutyCalculator.calculate(
            hs_code="0808.1000", quantity=100, unit_of_measure="kg",
            unit_value=10.0, currency="USD", exchange_rate=280.0,
            exchange_rate_source="Test", duty_rates=DutyRates(customs_duty=20.0, sales_tax=18.0, income_tax=5.5),
            cif_components=CIFComponents(fob_value=1000.0),
        )

        excel = DutyCalculationExcel()
        excel_bytes = excel.generate_import_workbook(
            hs_code=calc.hs_code, description="Fresh apples",
            quantity=calc.quantity, unit=calc.unit_of_measure,
            unit_value=calc.unit_value_foreign, currency=calc.currency,
            exchange_rate=calc.exchange_rate, exchange_rate_source=calc.exchange_rate_source,
            customs_duty_rate=calc.customs_duty_rate, sales_tax_rate=calc.sales_tax_rate,
            income_tax_rate=calc.income_tax_rate,
        )

        assert isinstance(excel_bytes, bytes)
        assert len(excel_bytes) > 100


class TestCacheIntegration:
    """Phase 3 caches working with data."""

    def test_exchange_rate_cache_stores_and_retrieves(self, exchange_cache):
        exchange_cache.put("USD", tt_buying=278.50, tt_selling=280.50, source="Test")
        cached = exchange_cache.get("USD")
        assert cached is not None
        assert cached.tt_buying == 278.50
        assert cached.tt_selling == 280.50

    def test_exchange_rate_cache_fallback_on_expired(self, exchange_cache):
        import time
        # Use very short TTL cache
        from exchange_rate_cache import ExchangeRateCache
        short_cache = ExchangeRateCache(
            db_path=os.path.join(os.path.dirname(exchange_cache.db_path), "short.db"),
            ttl=1
        )
        short_cache.put("USD", tt_buying=278.50, tt_selling=280.50, source="Test")
        time.sleep(1.1)

        # get() returns None for expired
        assert short_cache.get("USD") is None

        # get_or_fallback() returns expired data as fallback
        fallback = short_cache.get_or_fallback("USD")
        assert fallback is not None
        assert fallback.tt_buying == 278.50

    def test_weboc_cache_stores_duty_data(self, weboc_cache):
        duty_data = {
            "customs_duty": 20.0, "sales_tax": 18.0,
            "income_tax": 5.5, "additional_duty": 0, "regulatory_duty": 0,
            "description": "Fresh apples", "unit_of_measure": "kg",
        }
        weboc_cache.put(hs_code="0808.1000", duty_data=duty_data, source="Test")
        cached = weboc_cache.get("0808.1000")
        assert cached is not None
        assert cached.customs_duty == 20.0
        assert cached.description == "Fresh apples"

    def test_query_cache_normalizes_and_stores(self, query_cache):
        query_cache.put("What is HS code 0808.1000?", "It is fresh apples with 20% CD")
        cached = query_cache.get("What is HS code 0808.1000?")
        assert cached is not None
        assert "apples" in cached

    def test_query_cache_deduplication(self, query_cache):
        query_cache.put("What is the duty for 0808.1000?", "Result A")
        query_cache.put("what is the duty for 0808.1000", "Result B")
        # Same normalized query should be overwritten
        cached = query_cache.get("What is the duty for 0808.1000?")
        assert cached is not None


class TestBatchProcessorIntegration:
    """Phase 4 batch processor integration."""

    def test_batch_processes_csv(self, sample_csv):
        from batch_processor import process_batch

        result = process_batch(sample_csv, exchange_rate=280.0, exchange_rate_source="Test")
        assert result.total_rows == 2
        assert result.succeeded >= 1
        assert result.total_landed_cost_all > 0

    def test_batch_export_produces_csv(self, sample_csv):
        from batch_processor import process_batch, export_batch_csv

        result = process_batch(sample_csv, exchange_rate=280.0, exchange_rate_source="Test")
        csv_output = export_batch_csv(result)
        assert "HS Code" in csv_output
        assert "0808.1000" in csv_output

    def test_batch_sample_csv_valid(self):
        from batch_processor import generate_sample_csv, process_batch

        sample = generate_sample_csv()
        assert "hs_code" in sample
        result = process_batch(sample, exchange_rate=280.0)
        assert result.total_rows > 0


class TestDutyComparatorIntegration:
    """Phase 4 duty comparator integration."""

    def test_comparator_ranks_results(self):
        from duty_comparator import DutyComparator, DutyProfile

        profiles = [
            DutyProfile(hs_code="0808.1000", description="Apples", customs_duty_rate=20.0,
                        sales_tax_rate=18.0, income_tax_rate=5.5),
            DutyProfile(hs_code="0101.2100", description="Horses", customs_duty_rate=0.0,
                        sales_tax_rate=18.0, income_tax_rate=5.5),
        ]
        result = DutyComparator.compare(
            profiles, quantity=100, unit="kg", unit_value=10.0,
            currency="USD", exchange_rate=280.0,
        )
        assert result.item_count == 2
        assert result.cheapest_code == "0101.2100"
        assert result.max_savings > 0

    def test_comparator_single_item_is_cheapest(self):
        from duty_comparator import DutyComparator, DutyProfile

        profiles = [
            DutyProfile(hs_code="0808.1000", description="Apples", customs_duty_rate=20.0,
                        sales_tax_rate=18.0, income_tax_rate=5.5),
        ]
        result = DutyComparator.compare(
            profiles, quantity=100, unit="kg", unit_value=10.0,
            currency="USD", exchange_rate=280.0,
        )
        assert result.items[0].is_cheapest


class TestMultiCurrencyIntegration:
    """Phase 4 multi-currency with calculators."""

    def test_currency_conversion_for_import(self, currency_manager):
        # Get EUR rate and use it for import calculation
        eur_rate = currency_manager.get_rate("EUR")
        assert eur_rate is not None
        assert eur_rate.rate > 0

        from calculators import ImportDutyCalculator, DutyRates, CIFComponents
        calc = ImportDutyCalculator.calculate(
            hs_code="0808.1000", quantity=100, unit_of_measure="kg",
            unit_value=10.0, currency="EUR", exchange_rate=eur_rate.rate,
            exchange_rate_source="Test MultiCurrency",
            duty_rates=DutyRates(customs_duty=20.0, sales_tax=18.0, income_tax=5.5),
            cif_components=CIFComponents(fob_value=1000.0),
        )
        assert calc.cif_value_pkr > 0
        assert calc.currency == "EUR"

    def test_cross_rate_conversion(self, currency_manager):
        result = currency_manager.convert(100, "USD", "EUR")
        assert result is not None
        assert result.to_amount > 0
        assert result.via_pkr  # Cross-rate through PKR


class TestFavoritesIntegration:
    """Phase 4 favorites manager integration."""

    def test_add_and_retrieve_favorite(self, favorites_manager):
        favorites_manager.add(hs_code="0808.1000", description="Fresh apples",
                              customs_duty_rate=20.0, sales_tax_rate=18.0, income_tax_rate=5.5)
        fav = favorites_manager.get("0808.1000")
        assert fav is not None
        assert fav.description == "Fresh apples"
        assert fav.customs_duty_rate == 20.0

    def test_favorites_search(self, favorites_manager):
        favorites_manager.add(hs_code="0808.1000", description="Fresh apples")
        favorites_manager.add(hs_code="6109.1000", description="Cotton T-shirts")

        results = favorites_manager.search("apples")
        assert len(results) == 1
        assert results[0].hs_code == "0808.1000"

    def test_favorites_export_import_json(self, favorites_manager, tmp_db_dir):
        favorites_manager.add(hs_code="0808.1000", description="Fresh apples")
        json_data = favorites_manager.export_json()
        assert "0808.1000" in json_data

        # Import into new manager
        from favorites_manager import FavoritesManager
        new_mgr = FavoritesManager(db_path=os.path.join(tmp_db_dir, "import_test.db"))
        added, skipped = new_mgr.import_json(json_data)
        assert added == 1


class TestConfigIntegration:
    """Phase 5 config used by other modules."""

    def test_app_paths_from_project_root(self):
        from app_config import AppPaths
        paths = AppPaths.from_root(str(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        assert "pct_latest.pdf" in paths.pdf_path
        assert paths.project_root != ""

    def test_default_duty_rates_match_calculators(self):
        from app_config import DEFAULT_DUTY_RATES
        assert DEFAULT_DUTY_RATES["customs_duty"] == 20.0
        assert DEFAULT_DUTY_RATES["sales_tax"] == 18.0
        assert DEFAULT_DUTY_RATES["income_tax"] == 5.5


class TestPerformanceMonitorIntegration:
    """Phase 3 performance monitor tracking operations."""

    def test_monitor_tracks_calculation_timing(self, perf_monitor):
        from calculators import ImportDutyCalculator, DutyRates, CIFComponents

        with perf_monitor.track("import_calculation"):
            ImportDutyCalculator.calculate(
                hs_code="0808.1000", quantity=100, unit_of_measure="kg",
                unit_value=10.0, currency="USD", exchange_rate=280.0,
                exchange_rate_source="Test",
                duty_rates=DutyRates(customs_duty=20.0, sales_tax=18.0, income_tax=5.5),
                cif_components=CIFComponents(fob_value=1000.0),
            )

        stats = perf_monitor.get_stats("import_calculation")
        assert stats is not None
        assert stats["count"] == 1
        assert stats["avg_ms"] >= 0
