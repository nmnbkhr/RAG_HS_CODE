"""
Phase 4: Features - Batch Processor Tests

High-grade tests for batch import duty processing from CSV.
"""

import pytest
from batch_processor import (
    parse_csv, validate_row, calculate_row, process_batch,
    export_batch_csv, generate_sample_csv,
    BatchRow, BatchResult, RowStatus, _resolve_column, _safe_float
)


# --- Test Data ---

VALID_CSV = """hs_code,description,quantity,unit,unit_value,currency,freight,insurance,customs_duty,sales_tax,income_tax
0808.1000,Fresh apples,100,kg,10.0,USD,50,10,20,18,5.5
8517.1200,Mobile phones,50,units,200.0,USD,100,20,0,18,5.5
6109.1000,Cotton T-shirts,500,units,5.0,USD,80,15,20,18,5.5
"""

MINIMAL_CSV = """hs_code,quantity,unit_value,currency
0808.1000,100,10.0,USD
8517.1200,50,200.0,USD
"""

MIXED_CSV = """hs_code,description,quantity,unit_value,currency
0808.1000,Apples,100,10.0,USD
INVALID,,0,0,
8517.1200,Phones,50,200.0,USD
,,,,
6109.1000,Shirts,500,5.0,USD
"""

ALTERNATE_HEADERS_CSV = """HSCode,Desc,Qty,Price,Curr
0808.1000,Apples,100,10.0,USD
"""


class TestColumnResolution:
    """Tests for column alias resolution"""

    def test_standard_name(self):
        assert _resolve_column("hs_code") == "hs_code"

    def test_alias_hscode(self):
        assert _resolve_column("hscode") == "hs_code"

    def test_alias_quantity(self):
        assert _resolve_column("qty") == "quantity"

    def test_alias_description(self):
        assert _resolve_column("desc") == "description"

    def test_alias_value(self):
        assert _resolve_column("price") == "unit_value"

    def test_unknown_column(self):
        assert _resolve_column("foo_bar") is None

    def test_case_insensitive(self):
        assert _resolve_column("HS Code") == "hs_code"

    def test_customs_duty_alias(self):
        assert _resolve_column("cd_rate") == "customs_duty_rate"

    def test_sales_tax_alias(self):
        assert _resolve_column("gst") == "sales_tax_rate"


class TestSafeFloat:
    """Tests for safe float conversion"""

    def test_valid_number(self):
        assert _safe_float("10.5") == 10.5

    def test_integer(self):
        assert _safe_float("100") == 100.0

    def test_comma_separated(self):
        assert _safe_float("1,000.50") == 1000.50

    def test_empty_string(self):
        assert _safe_float("") == 0.0

    def test_none(self):
        assert _safe_float(None) == 0.0

    def test_invalid_string(self):
        assert _safe_float("abc") == 0.0

    def test_default_value(self):
        assert _safe_float("", 99.0) == 99.0


class TestParseCSV:
    """Tests for CSV parsing"""

    def test_valid_csv(self):
        rows, errors = parse_csv(VALID_CSV)
        assert len(errors) == 0
        assert len(rows) == 3

    def test_minimal_csv(self):
        rows, errors = parse_csv(MINIMAL_CSV)
        assert len(errors) == 0
        assert len(rows) == 2

    def test_empty_csv(self):
        rows, errors = parse_csv("")
        assert len(rows) == 0

    def test_headers_only(self):
        rows, errors = parse_csv("hs_code,quantity,unit_value,currency\n")
        assert len(rows) == 0

    def test_missing_required_column(self):
        rows, errors = parse_csv("description,quantity\nApples,100\n")
        assert len(errors) > 0
        assert "hs_code" in errors[0].lower()

    def test_mapped_headers(self):
        rows, errors = parse_csv(VALID_CSV)
        assert rows[0].get("hs_code") == "0808.1000"
        assert rows[0].get("quantity") == "100"

    def test_row_numbers(self):
        rows, errors = parse_csv(VALID_CSV)
        assert rows[0]["_row_number"] == 2  # Row 1 is header
        assert rows[1]["_row_number"] == 3


class TestValidateRow:
    """Tests for row validation"""

    def test_valid_row(self):
        row = {"hs_code": "0808.1000", "quantity": "100", "unit_value": "10.0", "currency": "USD"}
        batch_row, error = validate_row(row, 1)
        assert batch_row is not None
        assert error == ""
        assert batch_row.hs_code == "0808.1000"
        assert batch_row.quantity == 100.0

    def test_missing_hs_code(self):
        row = {"quantity": "100", "unit_value": "10.0", "currency": "USD"}
        batch_row, error = validate_row(row, 1)
        assert batch_row is None
        assert "HS code" in error

    def test_invalid_hs_code(self):
        row = {"hs_code": "12", "quantity": "100", "unit_value": "10.0", "currency": "USD"}
        batch_row, error = validate_row(row, 1)
        assert batch_row is None
        assert "Invalid" in error

    def test_zero_quantity(self):
        row = {"hs_code": "0808.1000", "quantity": "0", "unit_value": "10.0", "currency": "USD"}
        batch_row, error = validate_row(row, 1)
        assert batch_row is None
        assert "Quantity" in error

    def test_negative_quantity(self):
        row = {"hs_code": "0808.1000", "quantity": "-5", "unit_value": "10.0", "currency": "USD"}
        batch_row, error = validate_row(row, 1)
        assert batch_row is None

    def test_zero_unit_value(self):
        row = {"hs_code": "0808.1000", "quantity": "100", "unit_value": "0", "currency": "USD"}
        batch_row, error = validate_row(row, 1)
        assert batch_row is None
        assert "Unit value" in error

    def test_invalid_currency(self):
        row = {"hs_code": "0808.1000", "quantity": "100", "unit_value": "10.0", "currency": "X"}
        batch_row, error = validate_row(row, 1)
        assert batch_row is None
        assert "currency" in error.lower()

    def test_default_values(self):
        row = {"hs_code": "0808.1000", "quantity": "100", "unit_value": "10.0", "currency": "USD"}
        batch_row, _ = validate_row(row, 1)
        assert batch_row.unit == "kg"
        assert batch_row.freight == 0.0
        assert batch_row.insurance == 0.0

    def test_optional_fields(self):
        row = {
            "hs_code": "0808.1000", "quantity": "100", "unit_value": "10.0",
            "currency": "USD", "freight": "50", "insurance": "10",
            "description": "Fresh apples", "unit": "tonnes"
        }
        batch_row, _ = validate_row(row, 1)
        assert batch_row.freight == 50.0
        assert batch_row.insurance == 10.0
        assert batch_row.description == "Fresh apples"
        assert batch_row.unit == "tonnes"

    def test_negative_freight_rejected(self):
        row = {
            "hs_code": "0808.1000", "quantity": "100", "unit_value": "10.0",
            "currency": "USD", "freight": "-50"
        }
        batch_row, error = validate_row(row, 1)
        assert batch_row is None
        assert "negative" in error.lower()


class TestCalculateRow:
    """Tests for single row calculation"""

    def test_basic_calculation(self):
        row = BatchRow(
            row_number=1, hs_code="0808.1000", description="Apples",
            quantity=100, unit="kg", unit_value=10.0, currency="USD",
            customs_duty_rate=20.0, sales_tax_rate=18.0, income_tax_rate=5.5
        )
        result = calculate_row(row, 280.0, "NBP")

        assert result.status == RowStatus.SUCCESS
        assert result.cif_value_foreign == 1000.0
        assert result.cif_value_pkr == 280000.0
        assert result.customs_duty_amount == 56000.0
        assert result.total_duties > 0
        assert result.total_landed_cost > result.cif_value_pkr

    def test_calculation_with_freight(self):
        row = BatchRow(
            row_number=1, hs_code="0808.1000", description="Apples",
            quantity=100, unit="kg", unit_value=10.0, currency="USD",
            freight=50.0, insurance=10.0,
            customs_duty_rate=20.0, sales_tax_rate=18.0, income_tax_rate=5.5
        )
        result = calculate_row(row, 280.0, "NBP")

        assert result.cif_value_foreign == 1060.0  # 1000 + 50 + 10

    def test_default_rates(self):
        row = BatchRow(
            row_number=1, hs_code="0808.1000", description="Apples",
            quantity=100, unit="kg", unit_value=10.0, currency="USD"
        )
        defaults = {"customs_duty": 20.0, "sales_tax": 18.0, "income_tax": 5.5}
        result = calculate_row(row, 280.0, "NBP", defaults)

        assert result.customs_duty_rate == 20.0
        assert result.customs_duty_amount == 56000.0

    def test_zero_duty_rates(self):
        row = BatchRow(
            row_number=1, hs_code="0808.1000", description="Exempt",
            quantity=100, unit="kg", unit_value=10.0, currency="USD",
            customs_duty_rate=0, sales_tax_rate=0, income_tax_rate=0
        )
        result = calculate_row(row, 280.0, "NBP")

        assert result.total_duties == 0.0
        assert result.total_landed_cost == result.cif_value_pkr

    def test_effective_duty_rate(self):
        row = BatchRow(
            row_number=1, hs_code="0808.1000", description="Apples",
            quantity=100, unit="kg", unit_value=10.0, currency="USD",
            customs_duty_rate=20.0, sales_tax_rate=18.0, income_tax_rate=5.5
        )
        result = calculate_row(row, 280.0, "NBP")

        assert result.effective_duty_rate > 0
        expected_effective = result.total_duties / result.cif_value_pkr * 100
        assert abs(result.effective_duty_rate - round(expected_effective, 2)) < 0.01


class TestProcessBatch:
    """Tests for full batch processing"""

    def test_valid_batch(self):
        result = process_batch(VALID_CSV, 280.0)
        assert result.total_rows == 3
        assert result.succeeded == 3
        assert result.failed == 0

    def test_minimal_batch(self):
        result = process_batch(MINIMAL_CSV, 280.0, default_rates={"customs_duty": 20.0, "sales_tax": 18.0, "income_tax": 5.5})
        assert result.total_rows == 2
        assert result.succeeded == 2

    def test_mixed_batch(self):
        result = process_batch(MIXED_CSV, 280.0, default_rates={"customs_duty": 20.0, "sales_tax": 18.0, "income_tax": 5.5})
        assert result.succeeded >= 3
        assert result.failed >= 1  # INVALID row + empty row

    def test_empty_csv(self):
        result = process_batch("", 280.0)
        assert result.total_rows == 0

    def test_batch_id_generated(self):
        result = process_batch(VALID_CSV, 280.0)
        assert result.batch_id != ""

    def test_timestamp_set(self):
        result = process_batch(VALID_CSV, 280.0)
        assert result.timestamp != ""

    def test_processing_time_tracked(self):
        result = process_batch(VALID_CSV, 280.0)
        assert result.processing_time_ms > 0

    def test_exchange_rate_stored(self):
        result = process_batch(VALID_CSV, 282.50)
        assert result.exchange_rate == 282.50

    def test_totals(self):
        result = process_batch(VALID_CSV, 280.0)
        assert result.total_landed_cost_all > 0
        assert result.total_duties_all > 0

    def test_success_rate(self):
        result = process_batch(VALID_CSV, 280.0)
        assert result.success_rate == 100.0

    def test_errors_list(self):
        result = process_batch(MIXED_CSV, 280.0, default_rates={"customs_duty": 20.0, "sales_tax": 18.0})
        errors = result.get_errors()
        assert len(errors) >= 1

    def test_summary_dict(self):
        result = process_batch(VALID_CSV, 280.0)
        summary = result.to_summary_dict()
        assert "total_rows" in summary
        assert "succeeded" in summary
        assert "total_duties" in summary

    def test_max_rows_limit(self):
        big_csv = "hs_code,quantity,unit_value,currency\n"
        for i in range(200):
            big_csv += f"0808.{i:04d},100,10.0,USD\n"
        result = process_batch(big_csv, 280.0, max_rows=50,
                              default_rates={"customs_duty": 20.0, "sales_tax": 18.0, "income_tax": 5.5})
        assert result.total_rows == 50

    def test_100_plus_items(self):
        """Acceptance criteria: batch process 100+ items"""
        big_csv = "hs_code,quantity,unit_value,currency,customs_duty,sales_tax,income_tax\n"
        for i in range(150):
            big_csv += f"0808.{i:04d},100,10.0,USD,20,18,5.5\n"
        result = process_batch(big_csv, 280.0)
        assert result.total_rows == 150
        assert result.succeeded == 150


class TestExportBatchCSV:
    """Tests for CSV export"""

    def test_export_valid_result(self):
        result = process_batch(VALID_CSV, 280.0)
        csv_output = export_batch_csv(result)
        assert isinstance(csv_output, str)
        assert len(csv_output) > 0
        assert "HS Code" in csv_output
        assert "SUMMARY" in csv_output

    def test_export_contains_all_rows(self):
        result = process_batch(VALID_CSV, 280.0)
        csv_output = export_batch_csv(result)
        assert "0808.1000" in csv_output
        assert "8517.1200" in csv_output
        assert "6109.1000" in csv_output

    def test_export_contains_summary(self):
        result = process_batch(VALID_CSV, 280.0)
        csv_output = export_batch_csv(result)
        assert "Total Rows" in csv_output
        assert "Succeeded" in csv_output


class TestSampleCSV:
    """Tests for sample CSV generation"""

    def test_generate_sample(self):
        sample = generate_sample_csv()
        assert isinstance(sample, str)
        assert "hs_code" in sample
        assert "0808.1000" in sample

    def test_sample_is_parseable(self):
        sample = generate_sample_csv()
        rows, errors = parse_csv(sample)
        assert len(errors) == 0
        assert len(rows) == 4

    def test_sample_is_processable(self):
        sample = generate_sample_csv()
        result = process_batch(sample, 280.0)
        assert result.succeeded == 4


class TestBatchVerification:
    """Tests for calculation verification across batch"""

    def test_cif_formula(self):
        """Verify CIF = (Qty x UnitValue) + Freight + Insurance + Other"""
        result = process_batch(VALID_CSV, 280.0)
        for row in result.rows:
            if row.status == RowStatus.SUCCESS:
                expected = row.quantity * row.unit_value + row.freight + row.insurance + row.other_charges
                assert abs(row.cif_value_foreign - expected) < 0.01

    def test_pkr_conversion(self):
        """Verify CIF PKR = CIF Foreign x Exchange Rate"""
        result = process_batch(VALID_CSV, 280.0)
        for row in result.rows:
            if row.status == RowStatus.SUCCESS:
                expected = row.cif_value_foreign * 280.0
                assert abs(row.cif_value_pkr - expected) < 0.01

    def test_total_duties_sum(self):
        """Verify Total = CD + AD + RD + ST + IT"""
        result = process_batch(VALID_CSV, 280.0)
        for row in result.rows:
            if row.status == RowStatus.SUCCESS:
                expected = (
                    row.customs_duty_amount + row.additional_duty_amount +
                    row.regulatory_duty_amount + row.sales_tax_amount +
                    row.income_tax_amount
                )
                assert abs(row.total_duties - expected) < 0.01

    def test_landed_cost(self):
        """Verify Landed Cost = CIF PKR + Total Duties"""
        result = process_batch(VALID_CSV, 280.0)
        for row in result.rows:
            if row.status == RowStatus.SUCCESS:
                expected = row.cif_value_pkr + row.total_duties
                assert abs(row.total_landed_cost - expected) < 0.01
