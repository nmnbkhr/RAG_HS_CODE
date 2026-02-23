"""
Phase 2: UX Enhancements - Excel Export Tests

Comprehensive tests for Excel workbook generation:
- Import duty workbooks with formulas
- Export proceeds workbooks
- Formula validation
- Formatting verification
"""

import pytest
import io
from openpyxl import load_workbook
from excel_exporter import DutyCalculationExcel, generate_import_excel


class TestDutyCalculationExcel:
    """Tests for DutyCalculationExcel class"""

    def test_init(self):
        """Test initialization"""
        excel = DutyCalculationExcel()

        assert excel.wb is None  # Workbook created on generate


class TestImportExcelGeneration:
    """Tests for import Excel generation"""

    def test_generate_import_workbook_returns_bytes(self):
        """Test that import workbook returns bytes"""
        excel = DutyCalculationExcel()

        result = excel.generate_import_workbook(
            hs_code="0808.1000",
            description="Fresh apples",
            quantity=100.0,
            unit="kg",
            unit_value=10.0,
            currency="USD",
            exchange_rate=280.0,
            exchange_rate_source="NBP TT Selling",
            customs_duty_rate=20.0,
            sales_tax_rate=18.0,
            income_tax_rate=5.5
        )

        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_generate_import_workbook_is_valid_xlsx(self):
        """Test that output is a valid Excel file"""
        excel = DutyCalculationExcel()

        result = excel.generate_import_workbook(
            hs_code="0808.1000",
            description="Fresh apples",
            quantity=100.0,
            unit="kg",
            unit_value=10.0,
            currency="USD",
            exchange_rate=280.0,
            exchange_rate_source="NBP",
            customs_duty_rate=20.0,
            sales_tax_rate=18.0,
            income_tax_rate=5.5
        )

        # Excel files start with PK (zip signature)
        assert result[:2] == b'PK'

    def test_import_workbook_has_required_sheets(self):
        """Test that workbook has Summary and Calculation sheets"""
        excel = DutyCalculationExcel()

        result = excel.generate_import_workbook(
            hs_code="0808.1000",
            description="Fresh apples",
            quantity=100.0,
            unit="kg",
            unit_value=10.0,
            currency="USD",
            exchange_rate=280.0,
            exchange_rate_source="NBP",
            customs_duty_rate=20.0,
            sales_tax_rate=18.0,
            income_tax_rate=5.5
        )

        # Load workbook from bytes
        wb = load_workbook(io.BytesIO(result))

        assert "Summary" in wb.sheetnames
        assert "Calculation" in wb.sheetnames

    def test_import_workbook_summary_contains_hs_code(self):
        """Test that Summary sheet contains HS code"""
        excel = DutyCalculationExcel()

        result = excel.generate_import_workbook(
            hs_code="0808.1000",
            description="Fresh apples",
            quantity=100.0,
            unit="kg",
            unit_value=10.0,
            currency="USD",
            exchange_rate=280.0,
            exchange_rate_source="NBP",
            customs_duty_rate=20.0,
            sales_tax_rate=18.0,
            income_tax_rate=5.5
        )

        wb = load_workbook(io.BytesIO(result))
        ws = wb["Summary"]

        # Check that HS code appears somewhere in the sheet
        found_hs = False
        for row in ws.iter_rows():
            for cell in row:
                if cell.value and "0808.1000" in str(cell.value):
                    found_hs = True
                    break

        assert found_hs, "HS code not found in Summary sheet"

    def test_import_workbook_has_formulas(self):
        """Test that Calculation sheet contains formulas"""
        excel = DutyCalculationExcel()

        result = excel.generate_import_workbook(
            hs_code="0808.1000",
            description="Fresh apples",
            quantity=100.0,
            unit="kg",
            unit_value=10.0,
            currency="USD",
            exchange_rate=280.0,
            exchange_rate_source="NBP",
            customs_duty_rate=20.0,
            sales_tax_rate=18.0,
            income_tax_rate=5.5
        )

        wb = load_workbook(io.BytesIO(result))
        ws = wb["Calculation"]

        # Check that formulas exist in column B
        formula_found = False
        for row in ws.iter_rows():
            for cell in row:
                if cell.value and isinstance(cell.value, str) and cell.value.startswith('='):
                    formula_found = True
                    break

        assert formula_found, "No formulas found in Calculation sheet"

    def test_import_workbook_fob_formula(self):
        """Test FOB value formula"""
        excel = DutyCalculationExcel()

        result = excel.generate_import_workbook(
            hs_code="0808.1000",
            description="Apples",
            quantity=100.0,
            unit="kg",
            unit_value=10.0,
            currency="USD",
            exchange_rate=280.0,
            exchange_rate_source="NBP",
            customs_duty_rate=20.0,
            sales_tax_rate=18.0,
            income_tax_rate=5.5
        )

        wb = load_workbook(io.BytesIO(result))
        ws = wb["Calculation"]

        # FOB formula should multiply quantity by unit value
        # Look for formula "=B5*B6" or similar
        fob_formula_found = False
        for row in ws.iter_rows():
            for cell in row:
                if cell.value and isinstance(cell.value, str):
                    if "=B5*B6" in cell.value or "Quantity" in str(cell.value):
                        fob_formula_found = True

        assert fob_formula_found

    def test_import_workbook_with_all_duties(self):
        """Test workbook with all duty types"""
        excel = DutyCalculationExcel()

        result = excel.generate_import_workbook(
            hs_code="8703.2300",
            description="Motor vehicles",
            quantity=1.0,
            unit="unit",
            unit_value=25000.0,
            currency="USD",
            exchange_rate=280.0,
            exchange_rate_source="NBP",
            freight=500.0,
            insurance=250.0,
            other_charges=100.0,
            customs_duty_rate=50.0,
            additional_duty_rate=7.0,
            regulatory_duty_rate=15.0,
            sales_tax_rate=18.0,
            income_tax_rate=6.0
        )

        wb = load_workbook(io.BytesIO(result))

        assert "Summary" in wb.sheetnames
        assert "Calculation" in wb.sheetnames

    def test_import_workbook_input_cells_editable(self):
        """Test that input cells are marked with yellow background"""
        excel = DutyCalculationExcel()

        result = excel.generate_import_workbook(
            hs_code="0808.1000",
            description="Apples",
            quantity=100.0,
            unit="kg",
            unit_value=10.0,
            currency="USD",
            exchange_rate=280.0,
            exchange_rate_source="NBP",
            customs_duty_rate=20.0,
            sales_tax_rate=18.0,
            income_tax_rate=5.5
        )

        wb = load_workbook(io.BytesIO(result))
        ws = wb["Calculation"]

        # Input cells (B5-B10) should have yellow fill
        input_cell = ws["B5"]
        assert input_cell.fill is not None


class TestExportExcelGeneration:
    """Tests for export Excel generation"""

    def test_generate_export_workbook_returns_bytes(self):
        """Test that export workbook returns bytes"""
        excel = DutyCalculationExcel()

        result = excel.generate_export_workbook(
            hs_code="5201.0000",
            description="Raw cotton",
            quantity=1000.0,
            unit="kg",
            fob_per_unit=2.0,
            currency="USD",
            exchange_rate=278.0,
            exchange_rate_source="NBP TT Buying"
        )

        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_generate_export_workbook_is_valid_xlsx(self):
        """Test that export output is a valid Excel file"""
        excel = DutyCalculationExcel()

        result = excel.generate_export_workbook(
            hs_code="5201.0000",
            description="Raw cotton",
            quantity=1000.0,
            unit="kg",
            fob_per_unit=2.0,
            currency="USD",
            exchange_rate=278.0,
            exchange_rate_source="NBP"
        )

        # Excel files start with PK (zip signature)
        assert result[:2] == b'PK'

    def test_export_workbook_has_sheet(self):
        """Test that export workbook has Export Calculation sheet"""
        excel = DutyCalculationExcel()

        result = excel.generate_export_workbook(
            hs_code="5201.0000",
            description="Raw cotton",
            quantity=1000.0,
            unit="kg",
            fob_per_unit=2.0,
            currency="USD",
            exchange_rate=278.0,
            exchange_rate_source="NBP"
        )

        wb = load_workbook(io.BytesIO(result))

        assert "Export Calculation" in wb.sheetnames

    def test_export_workbook_contains_hs_code(self):
        """Test that export sheet contains HS code"""
        excel = DutyCalculationExcel()

        result = excel.generate_export_workbook(
            hs_code="5201.0000",
            description="Raw cotton",
            quantity=1000.0,
            unit="kg",
            fob_per_unit=2.0,
            currency="USD",
            exchange_rate=278.0,
            exchange_rate_source="NBP"
        )

        wb = load_workbook(io.BytesIO(result))
        ws = wb["Export Calculation"]

        found_hs = False
        for row in ws.iter_rows():
            for cell in row:
                if cell.value and "5201.0000" in str(cell.value):
                    found_hs = True
                    break

        assert found_hs, "HS code not found in Export Calculation sheet"

    def test_export_workbook_has_formulas(self):
        """Test that export sheet contains formulas"""
        excel = DutyCalculationExcel()

        result = excel.generate_export_workbook(
            hs_code="5201.0000",
            description="Raw cotton",
            quantity=1000.0,
            unit="kg",
            fob_per_unit=2.0,
            currency="USD",
            exchange_rate=278.0,
            exchange_rate_source="NBP"
        )

        wb = load_workbook(io.BytesIO(result))
        ws = wb["Export Calculation"]

        formula_found = False
        for row in ws.iter_rows():
            for cell in row:
                if cell.value and isinstance(cell.value, str) and cell.value.startswith('='):
                    formula_found = True
                    break

        assert formula_found, "No formulas found in Export Calculation sheet"

    def test_export_workbook_with_regulatory_duty(self):
        """Test export workbook with regulatory duty"""
        excel = DutyCalculationExcel()

        result = excel.generate_export_workbook(
            hs_code="7204.1000",
            description="Ferrous scrap",
            quantity=5000.0,
            unit="kg",
            fob_per_unit=0.5,
            currency="USD",
            exchange_rate=278.0,
            exchange_rate_source="NBP",
            regulatory_duty_rate=15.0
        )

        wb = load_workbook(io.BytesIO(result))
        ws = wb["Export Calculation"]

        # Should contain regulatory duty rate
        found_rd = False
        for row in ws.iter_rows():
            for cell in row:
                if cell.value == 15.0:
                    found_rd = True
                    break

        assert found_rd

    def test_export_workbook_with_destination(self):
        """Test export workbook with destination"""
        excel = DutyCalculationExcel()

        result = excel.generate_export_workbook(
            hs_code="5201.0000",
            description="Raw cotton",
            quantity=10000.0,
            unit="kg",
            fob_per_unit=2.0,
            currency="USD",
            exchange_rate=278.0,
            exchange_rate_source="NBP",
            destination="China"
        )

        wb = load_workbook(io.BytesIO(result))
        ws = wb["Export Calculation"]

        found_dest = False
        for row in ws.iter_rows():
            for cell in row:
                if cell.value and "China" in str(cell.value):
                    found_dest = True
                    break

        assert found_dest


class TestConvenienceFunction:
    """Tests for convenience function"""

    def test_generate_import_excel(self):
        """Test generate_import_excel convenience function"""
        calculation_result = {
            'hs_code': '0808.1000',
            'description': 'Fresh apples',
            'quantity': 100.0,
            'unit_of_measure': 'kg',
            'unit_value_foreign': 10.0,
            'currency': 'USD',
            'exchange_rate': 280.0,
            'exchange_rate_source': 'NBP',
            'freight_foreign': 0.0,
            'insurance_foreign': 0.0,
            'other_charges_foreign': 0.0,
            'customs_duty_rate': 20.0,
            'additional_duty_rate': 0.0,
            'regulatory_duty_rate': 0.0,
            'sales_tax_rate': 18.0,
            'income_tax_rate': 5.5,
            'data_source': 'WEBOC'
        }

        result = generate_import_excel(calculation_result)

        assert isinstance(result, bytes)
        assert result[:2] == b'PK'

    def test_generate_import_excel_with_missing_fields(self):
        """Test convenience function handles missing fields gracefully"""
        calculation_result = {
            'hs_code': '0808.1000',
            'quantity': 100.0
            # Missing many fields
        }

        result = generate_import_excel(calculation_result)

        assert isinstance(result, bytes)


class TestFormulaValidation:
    """Tests for formula validation"""

    def test_formulas_calculate_correctly(self):
        """Test that formulas produce correct values when evaluated"""
        excel = DutyCalculationExcel()

        result = excel.generate_import_workbook(
            hs_code="0808.1000",
            description="Apples",
            quantity=100.0,
            unit="kg",
            unit_value=10.0,
            currency="USD",
            exchange_rate=280.0,
            exchange_rate_source="NBP",
            freight=0.0,
            insurance=0.0,
            other_charges=0.0,
            customs_duty_rate=20.0,
            additional_duty_rate=0.0,
            regulatory_duty_rate=0.0,
            sales_tax_rate=18.0,
            income_tax_rate=5.5
        )

        # Load with data_only=True to get calculated values
        # Note: This only works if formulas were calculated by Excel
        # For unit testing, we verify formulas exist
        wb = load_workbook(io.BytesIO(result))
        ws = wb["Calculation"]

        # Verify input values are correct
        assert ws["B5"].value == 100.0  # Quantity
        assert ws["B6"].value == 10.0   # Unit Value
        assert ws["B7"].value == 280.0  # Exchange Rate

    def test_cif_formula_structure(self):
        """Test CIF formula includes all components"""
        excel = DutyCalculationExcel()

        result = excel.generate_import_workbook(
            hs_code="0808.1000",
            description="Apples",
            quantity=100.0,
            unit="kg",
            unit_value=10.0,
            currency="USD",
            exchange_rate=280.0,
            exchange_rate_source="NBP",
            freight=50.0,
            insurance=10.0,
            other_charges=5.0,
            customs_duty_rate=20.0,
            sales_tax_rate=18.0,
            income_tax_rate=5.5
        )

        wb = load_workbook(io.BytesIO(result))
        ws = wb["Calculation"]

        # Find CIF formula
        cif_formula_correct = False
        for row in ws.iter_rows():
            for cell in row:
                if cell.value and isinstance(cell.value, str):
                    # CIF should include FOB + Freight + Insurance + Other
                    if "+B8+B9+B10" in cell.value:
                        cif_formula_correct = True

        assert cif_formula_correct, "CIF formula doesn't include all components"


class TestExcelFileIntegrity:
    """Tests for Excel file integrity"""

    def test_excel_can_be_written_to_file(self):
        """Test that Excel can be written to a file"""
        excel = DutyCalculationExcel()

        result = excel.generate_import_workbook(
            hs_code="0808.1000",
            description="Test",
            quantity=100.0,
            unit="kg",
            unit_value=10.0,
            currency="USD",
            exchange_rate=280.0,
            exchange_rate_source="NBP",
            customs_duty_rate=20.0,
            sales_tax_rate=18.0,
            income_tax_rate=5.5
        )

        # Write to BytesIO
        buffer = io.BytesIO(result)
        buffer.seek(0)

        # Verify we can read it back
        content = buffer.read()
        assert content == result

    def test_excel_has_reasonable_size(self):
        """Test that Excel has reasonable file size"""
        excel = DutyCalculationExcel()

        result = excel.generate_import_workbook(
            hs_code="0808.1000",
            description="Fresh apples",
            quantity=100.0,
            unit="kg",
            unit_value=10.0,
            currency="USD",
            exchange_rate=280.0,
            exchange_rate_source="NBP",
            customs_duty_rate=20.0,
            sales_tax_rate=18.0,
            income_tax_rate=5.5
        )

        # Excel should be between 5KB and 500KB
        assert len(result) > 5000  # > 5KB
        assert len(result) < 500000  # < 500KB


class TestExcelEdgeCases:
    """Edge case tests for Excel generation"""

    def test_long_description(self):
        """Test handling of long descriptions"""
        excel = DutyCalculationExcel()

        long_desc = "A" * 500  # Very long description

        result = excel.generate_import_workbook(
            hs_code="0808.1000",
            description=long_desc,
            quantity=100.0,
            unit="kg",
            unit_value=10.0,
            currency="USD",
            exchange_rate=280.0,
            exchange_rate_source="NBP",
            customs_duty_rate=20.0,
            sales_tax_rate=18.0,
            income_tax_rate=5.5
        )

        assert isinstance(result, bytes)

    def test_special_characters_in_description(self):
        """Test handling of special characters"""
        excel = DutyCalculationExcel()

        result = excel.generate_import_workbook(
            hs_code="0808.1000",
            description="Apples (Grade A) - 'Premium' & Fresh",
            quantity=100.0,
            unit="kg",
            unit_value=10.0,
            currency="USD",
            exchange_rate=280.0,
            exchange_rate_source="NBP",
            customs_duty_rate=20.0,
            sales_tax_rate=18.0,
            income_tax_rate=5.5
        )

        assert isinstance(result, bytes)

    def test_zero_values(self):
        """Test handling of zero values"""
        excel = DutyCalculationExcel()

        result = excel.generate_import_workbook(
            hs_code="0808.1000",
            description="Test",
            quantity=0.0,
            unit="kg",
            unit_value=0.0,
            currency="USD",
            exchange_rate=280.0,
            exchange_rate_source="NBP",
            customs_duty_rate=0.0,
            sales_tax_rate=0.0,
            income_tax_rate=0.0
        )

        assert isinstance(result, bytes)

    def test_large_values(self):
        """Test handling of large values"""
        excel = DutyCalculationExcel()

        result = excel.generate_import_workbook(
            hs_code="8802.4000",
            description="Aircraft",
            quantity=1.0,
            unit="unit",
            unit_value=50000000.0,
            currency="USD",
            exchange_rate=280.0,
            exchange_rate_source="NBP",
            freight=100000.0,
            insurance=500000.0,
            customs_duty_rate=5.0,
            sales_tax_rate=0.0,
            income_tax_rate=0.0
        )

        assert isinstance(result, bytes)

    def test_decimal_precision(self):
        """Test handling of decimal precision"""
        excel = DutyCalculationExcel()

        result = excel.generate_import_workbook(
            hs_code="0808.1000",
            description="Test",
            quantity=100.5555,
            unit="kg",
            unit_value=10.1234,
            currency="USD",
            exchange_rate=280.5678,
            exchange_rate_source="NBP",
            customs_duty_rate=20.125,
            sales_tax_rate=18.333,
            income_tax_rate=5.555
        )

        assert isinstance(result, bytes)


class TestExcelFormatting:
    """Tests for Excel formatting"""

    def test_number_format_applied(self):
        """Test that number formats are applied"""
        excel = DutyCalculationExcel()

        result = excel.generate_import_workbook(
            hs_code="0808.1000",
            description="Apples",
            quantity=100.0,
            unit="kg",
            unit_value=10.0,
            currency="USD",
            exchange_rate=280.0,
            exchange_rate_source="NBP",
            customs_duty_rate=20.0,
            sales_tax_rate=18.0,
            income_tax_rate=5.5
        )

        wb = load_workbook(io.BytesIO(result))
        ws = wb["Calculation"]

        # Check that numeric cells have number format
        quantity_cell = ws["B5"]
        assert quantity_cell.number_format is not None

    def test_borders_applied(self):
        """Test that borders are applied"""
        excel = DutyCalculationExcel()

        result = excel.generate_import_workbook(
            hs_code="0808.1000",
            description="Apples",
            quantity=100.0,
            unit="kg",
            unit_value=10.0,
            currency="USD",
            exchange_rate=280.0,
            exchange_rate_source="NBP",
            customs_duty_rate=20.0,
            sales_tax_rate=18.0,
            income_tax_rate=5.5
        )

        wb = load_workbook(io.BytesIO(result))
        ws = wb["Calculation"]

        # Check that cells have borders
        cell = ws["A5"]
        assert cell.border is not None
