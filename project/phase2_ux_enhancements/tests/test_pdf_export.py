"""
Phase 2: UX Enhancements - PDF Export Tests

Comprehensive tests for PDF report generation:
- Import duty reports
- Export proceeds reports
- Configuration options
- PDF structure validation
"""

import pytest
import io
from pdf_exporter import DutyCalculationPDF, PDFConfig, generate_import_pdf


class TestPDFConfig:
    """Tests for PDF configuration"""

    def test_default_config(self):
        """Test default configuration values"""
        config = PDFConfig()

        assert config.title == "Pakistan Customs - Duty Calculation Report"
        assert config.include_footer is True
        assert config.include_disclaimer is True

    def test_custom_config(self):
        """Test custom configuration"""
        config = PDFConfig(
            title="Custom Report",
            include_footer=False,
            include_disclaimer=False
        )

        assert config.title == "Custom Report"
        assert config.include_footer is False
        assert config.include_disclaimer is False


class TestDutyCalculationPDF:
    """Tests for DutyCalculationPDF class"""

    def test_init_default(self):
        """Test initialization with default config"""
        pdf = DutyCalculationPDF()

        assert pdf.config is not None
        assert pdf.config.include_footer is True

    def test_init_custom_config(self):
        """Test initialization with custom config"""
        config = PDFConfig(include_disclaimer=False)
        pdf = DutyCalculationPDF(config=config)

        assert pdf.config.include_disclaimer is False


class TestImportPDFGeneration:
    """Tests for import PDF generation"""

    def test_generate_import_report_returns_bytes(self):
        """Test that import report returns bytes"""
        pdf = DutyCalculationPDF()

        result = pdf.generate_import_report(
            hs_code="0808.1000",
            description="Fresh apples",
            quantity=100.0,
            unit="kg",
            unit_value=10.0,
            currency="USD",
            exchange_rate=280.0,
            exchange_rate_source="NBP TT Selling",
            fob_value=1000.0,
            freight=0.0,
            insurance=0.0,
            other_charges=0.0,
            cif_foreign=1000.0,
            cif_pkr=280000.0,
            customs_duty_rate=20.0,
            customs_duty_amount=56000.0,
            sales_tax_rate=18.0,
            sales_tax_amount=60480.0,
            income_tax_rate=5.5,
            income_tax_amount=15400.0,
            total_duties=131880.0,
            landed_cost=411880.0
        )

        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_generate_import_report_is_valid_pdf(self):
        """Test that output is a valid PDF"""
        pdf = DutyCalculationPDF()

        result = pdf.generate_import_report(
            hs_code="0808.1000",
            description="Fresh apples",
            quantity=100.0,
            unit="kg",
            unit_value=10.0,
            currency="USD",
            exchange_rate=280.0,
            exchange_rate_source="NBP",
            fob_value=1000.0,
            freight=0.0,
            insurance=0.0,
            other_charges=0.0,
            cif_foreign=1000.0,
            cif_pkr=280000.0,
            customs_duty_rate=20.0,
            customs_duty_amount=56000.0,
            sales_tax_rate=18.0,
            sales_tax_amount=60480.0,
            income_tax_rate=5.5,
            income_tax_amount=15400.0,
            total_duties=131880.0,
            landed_cost=411880.0
        )

        # PDF files start with %PDF
        assert result[:4] == b'%PDF'

    def test_generate_import_report_with_additional_duties(self):
        """Test import report with additional and regulatory duties"""
        pdf = DutyCalculationPDF()

        result = pdf.generate_import_report(
            hs_code="8703.2300",
            description="Motor vehicles",
            quantity=1.0,
            unit="unit",
            unit_value=25000.0,
            currency="USD",
            exchange_rate=280.0,
            exchange_rate_source="NBP TT Selling",
            fob_value=25000.0,
            freight=500.0,
            insurance=250.0,
            other_charges=100.0,
            cif_foreign=25850.0,
            cif_pkr=7238000.0,
            customs_duty_rate=50.0,
            customs_duty_amount=3619000.0,
            additional_duty_rate=7.0,
            additional_duty_amount=506660.0,
            regulatory_duty_rate=15.0,
            regulatory_duty_amount=1085700.0,
            sales_tax_rate=18.0,
            sales_tax_amount=2240928.0,
            income_tax_rate=6.0,
            income_tax_amount=434280.0,
            total_duties=7886568.0,
            landed_cost=15124568.0
        )

        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_generate_import_report_with_freight_insurance(self):
        """Test import report with freight and insurance"""
        pdf = DutyCalculationPDF()

        result = pdf.generate_import_report(
            hs_code="0808.1000",
            description="Fresh apples",
            quantity=1000.0,
            unit="kg",
            unit_value=10.0,
            currency="USD",
            exchange_rate=280.0,
            exchange_rate_source="NBP",
            fob_value=10000.0,
            freight=500.0,
            insurance=105.0,
            other_charges=0.0,
            cif_foreign=10605.0,
            cif_pkr=2969400.0,
            customs_duty_rate=20.0,
            customs_duty_amount=593880.0,
            sales_tax_rate=18.0,
            sales_tax_amount=641390.0,
            income_tax_rate=5.5,
            income_tax_amount=163317.0,
            total_duties=1398587.0,
            landed_cost=4367987.0
        )

        assert isinstance(result, bytes)

    def test_generate_import_report_long_description(self):
        """Test that long descriptions are truncated"""
        pdf = DutyCalculationPDF()

        long_desc = "Fresh apples of the Granny Smith variety imported from Washington State, USA, Grade A quality, certified organic"

        result = pdf.generate_import_report(
            hs_code="0808.1000",
            description=long_desc,
            quantity=100.0,
            unit="kg",
            unit_value=10.0,
            currency="USD",
            exchange_rate=280.0,
            exchange_rate_source="NBP",
            fob_value=1000.0,
            freight=0.0,
            insurance=0.0,
            other_charges=0.0,
            cif_foreign=1000.0,
            cif_pkr=280000.0,
            customs_duty_rate=20.0,
            customs_duty_amount=56000.0,
            sales_tax_rate=18.0,
            sales_tax_amount=60480.0,
            income_tax_rate=5.5,
            income_tax_amount=15400.0,
            total_duties=131880.0,
            landed_cost=411880.0
        )

        # Should generate without error even with long description
        assert isinstance(result, bytes)

    def test_generate_import_report_minimal_values(self):
        """Test import report with minimal/zero values"""
        pdf = DutyCalculationPDF()

        result = pdf.generate_import_report(
            hs_code="0808.1000",
            description="Test",
            quantity=1.0,
            unit="pcs",
            unit_value=0.0,
            currency="USD",
            exchange_rate=280.0,
            exchange_rate_source="Manual",
            fob_value=0.0,
            freight=0.0,
            insurance=0.0,
            other_charges=0.0,
            cif_foreign=0.0,
            cif_pkr=0.0,
            customs_duty_rate=0.0,
            customs_duty_amount=0.0,
            sales_tax_rate=0.0,
            sales_tax_amount=0.0,
            income_tax_rate=0.0,
            income_tax_amount=0.0,
            total_duties=0.0,
            landed_cost=0.0
        )

        assert isinstance(result, bytes)


class TestExportPDFGeneration:
    """Tests for export PDF generation"""

    def test_generate_export_report_returns_bytes(self):
        """Test that export report returns bytes"""
        pdf = DutyCalculationPDF()

        result = pdf.generate_export_report(
            hs_code="5201.0000",
            description="Raw cotton",
            quantity=1000.0,
            unit="kg",
            fob_per_unit=2.0,
            currency="USD",
            total_fob_foreign=2000.0,
            exchange_rate=278.0,
            exchange_rate_source="NBP TT Buying",
            total_fob_pkr=556000.0,
            regulatory_duty_rate=0.0,
            regulatory_duty_amount=0.0,
            net_proceeds=556000.0
        )

        assert isinstance(result, bytes)
        assert len(result) > 0

    def test_generate_export_report_is_valid_pdf(self):
        """Test that export output is a valid PDF"""
        pdf = DutyCalculationPDF()

        result = pdf.generate_export_report(
            hs_code="5201.0000",
            description="Raw cotton",
            quantity=1000.0,
            unit="kg",
            fob_per_unit=2.0,
            currency="USD",
            total_fob_foreign=2000.0,
            exchange_rate=278.0,
            exchange_rate_source="NBP",
            total_fob_pkr=556000.0,
            net_proceeds=556000.0
        )

        # PDF files start with %PDF
        assert result[:4] == b'%PDF'

    def test_generate_export_report_with_regulatory_duty(self):
        """Test export report with regulatory duty"""
        pdf = DutyCalculationPDF()

        result = pdf.generate_export_report(
            hs_code="7204.1000",
            description="Ferrous scrap",
            quantity=5000.0,
            unit="kg",
            fob_per_unit=0.5,
            currency="USD",
            total_fob_foreign=2500.0,
            exchange_rate=278.0,
            exchange_rate_source="NBP TT Buying",
            total_fob_pkr=695000.0,
            regulatory_duty_rate=15.0,
            regulatory_duty_amount=104250.0,
            net_proceeds=590750.0,
            export_scheme="Normal Export"
        )

        assert isinstance(result, bytes)

    def test_generate_export_report_with_destination(self):
        """Test export report with destination country"""
        pdf = DutyCalculationPDF()

        result = pdf.generate_export_report(
            hs_code="5201.0000",
            description="Raw cotton",
            quantity=10000.0,
            unit="kg",
            fob_per_unit=2.0,
            currency="USD",
            total_fob_foreign=20000.0,
            exchange_rate=278.0,
            exchange_rate_source="NBP",
            total_fob_pkr=5560000.0,
            net_proceeds=5560000.0,
            destination="China"
        )

        assert isinstance(result, bytes)

    def test_generate_export_report_different_schemes(self):
        """Test export report with different export schemes"""
        pdf = DutyCalculationPDF()

        schemes = ["Normal Export", "DTRE Scheme", "EOU Scheme", "SRO Exemption"]

        for scheme in schemes:
            result = pdf.generate_export_report(
                hs_code="5201.0000",
                description="Cotton",
                quantity=1000.0,
                unit="kg",
                fob_per_unit=2.0,
                currency="USD",
                total_fob_foreign=2000.0,
                exchange_rate=278.0,
                exchange_rate_source="NBP",
                total_fob_pkr=556000.0,
                net_proceeds=556000.0,
                export_scheme=scheme
            )

            assert isinstance(result, bytes)


class TestConvenienceFunction:
    """Tests for convenience functions"""

    def test_generate_import_pdf(self):
        """Test generate_import_pdf convenience function"""
        calculation_result = {
            'hs_code': '0808.1000',
            'description': 'Fresh apples',
            'quantity': 100.0,
            'unit_of_measure': 'kg',
            'unit_value_foreign': 10.0,
            'currency': 'USD',
            'exchange_rate': 280.0,
            'exchange_rate_source': 'NBP',
            'fob_value_foreign': 1000.0,
            'freight_foreign': 0.0,
            'insurance_foreign': 0.0,
            'other_charges_foreign': 0.0,
            'cif_value_foreign': 1000.0,
            'cif_value_pkr': 280000.0,
            'customs_duty_rate': 20.0,
            'customs_duty_amount': 56000.0,
            'sales_tax_rate': 18.0,
            'sales_tax_amount': 60480.0,
            'income_tax_rate': 5.5,
            'income_tax_amount': 15400.0,
            'total_duties': 131880.0,
            'total_landed_cost': 411880.0,
            'data_source': 'WEBOC'
        }

        result = generate_import_pdf(calculation_result)

        assert isinstance(result, bytes)
        assert result[:4] == b'%PDF'

    def test_generate_import_pdf_with_missing_fields(self):
        """Test convenience function handles missing fields gracefully"""
        calculation_result = {
            'hs_code': '0808.1000',
            'quantity': 100.0
            # Missing many fields
        }

        result = generate_import_pdf(calculation_result)

        assert isinstance(result, bytes)


class TestPDFFileIntegrity:
    """Tests for PDF file integrity"""

    def test_pdf_can_be_written_to_file(self):
        """Test that PDF can be written to a file"""
        pdf = DutyCalculationPDF()

        result = pdf.generate_import_report(
            hs_code="0808.1000",
            description="Test",
            quantity=100.0,
            unit="kg",
            unit_value=10.0,
            currency="USD",
            exchange_rate=280.0,
            exchange_rate_source="NBP",
            fob_value=1000.0,
            freight=0.0,
            insurance=0.0,
            other_charges=0.0,
            cif_foreign=1000.0,
            cif_pkr=280000.0,
            customs_duty_rate=20.0,
            customs_duty_amount=56000.0,
            sales_tax_rate=18.0,
            sales_tax_amount=60480.0,
            income_tax_rate=5.5,
            income_tax_amount=15400.0,
            total_duties=131880.0,
            landed_cost=411880.0
        )

        # Write to BytesIO (simulating file write)
        buffer = io.BytesIO(result)
        buffer.seek(0)

        # Verify we can read it back
        content = buffer.read()
        assert content == result

    def test_pdf_has_reasonable_size(self):
        """Test that PDF has reasonable file size"""
        pdf = DutyCalculationPDF()

        result = pdf.generate_import_report(
            hs_code="0808.1000",
            description="Fresh apples",
            quantity=100.0,
            unit="kg",
            unit_value=10.0,
            currency="USD",
            exchange_rate=280.0,
            exchange_rate_source="NBP",
            fob_value=1000.0,
            freight=0.0,
            insurance=0.0,
            other_charges=0.0,
            cif_foreign=1000.0,
            cif_pkr=280000.0,
            customs_duty_rate=20.0,
            customs_duty_amount=56000.0,
            sales_tax_rate=18.0,
            sales_tax_amount=60480.0,
            income_tax_rate=5.5,
            income_tax_amount=15400.0,
            total_duties=131880.0,
            landed_cost=411880.0
        )

        # PDF should be between 1KB and 1MB
        assert len(result) > 1000  # > 1KB
        assert len(result) < 1000000  # < 1MB


class TestPDFConfigurationOptions:
    """Tests for PDF configuration options"""

    def test_pdf_without_footer(self):
        """Test PDF generation without footer"""
        config = PDFConfig(include_footer=False)
        pdf = DutyCalculationPDF(config=config)

        result = pdf.generate_import_report(
            hs_code="0808.1000",
            description="Test",
            quantity=100.0,
            unit="kg",
            unit_value=10.0,
            currency="USD",
            exchange_rate=280.0,
            exchange_rate_source="NBP",
            fob_value=1000.0,
            freight=0.0,
            insurance=0.0,
            other_charges=0.0,
            cif_foreign=1000.0,
            cif_pkr=280000.0,
            customs_duty_rate=20.0,
            customs_duty_amount=56000.0,
            sales_tax_rate=18.0,
            sales_tax_amount=60480.0,
            income_tax_rate=5.5,
            income_tax_amount=15400.0,
            total_duties=131880.0,
            landed_cost=411880.0
        )

        assert isinstance(result, bytes)

    def test_pdf_without_disclaimer(self):
        """Test PDF generation without disclaimer"""
        config = PDFConfig(include_disclaimer=False)
        pdf = DutyCalculationPDF(config=config)

        result = pdf.generate_import_report(
            hs_code="0808.1000",
            description="Test",
            quantity=100.0,
            unit="kg",
            unit_value=10.0,
            currency="USD",
            exchange_rate=280.0,
            exchange_rate_source="NBP",
            fob_value=1000.0,
            freight=0.0,
            insurance=0.0,
            other_charges=0.0,
            cif_foreign=1000.0,
            cif_pkr=280000.0,
            customs_duty_rate=20.0,
            customs_duty_amount=56000.0,
            sales_tax_rate=18.0,
            sales_tax_amount=60480.0,
            income_tax_rate=5.5,
            income_tax_amount=15400.0,
            total_duties=131880.0,
            landed_cost=411880.0
        )

        assert isinstance(result, bytes)


class TestPDFEdgeCases:
    """Edge case tests for PDF generation"""

    def test_unicode_characters_in_description(self):
        """Test handling of unicode characters"""
        pdf = DutyCalculationPDF()

        result = pdf.generate_import_report(
            hs_code="0808.1000",
            description="Fresh apples (Grade A) - certified organic",
            quantity=100.0,
            unit="kg",
            unit_value=10.0,
            currency="USD",
            exchange_rate=280.0,
            exchange_rate_source="NBP",
            fob_value=1000.0,
            freight=0.0,
            insurance=0.0,
            other_charges=0.0,
            cif_foreign=1000.0,
            cif_pkr=280000.0,
            customs_duty_rate=20.0,
            customs_duty_amount=56000.0,
            sales_tax_rate=18.0,
            sales_tax_amount=60480.0,
            income_tax_rate=5.5,
            income_tax_amount=15400.0,
            total_duties=131880.0,
            landed_cost=411880.0
        )

        assert isinstance(result, bytes)

    def test_large_numeric_values(self):
        """Test handling of large numeric values"""
        pdf = DutyCalculationPDF()

        result = pdf.generate_import_report(
            hs_code="8802.4000",
            description="Aircraft",
            quantity=1.0,
            unit="unit",
            unit_value=50000000.0,
            currency="USD",
            exchange_rate=280.0,
            exchange_rate_source="NBP",
            fob_value=50000000.0,
            freight=100000.0,
            insurance=500000.0,
            other_charges=50000.0,
            cif_foreign=50650000.0,
            cif_pkr=14182000000.0,
            customs_duty_rate=5.0,
            customs_duty_amount=709100000.0,
            sales_tax_rate=0.0,
            sales_tax_amount=0.0,
            income_tax_rate=0.0,
            income_tax_amount=0.0,
            total_duties=709100000.0,
            landed_cost=14891100000.0
        )

        assert isinstance(result, bytes)

    def test_decimal_precision(self):
        """Test handling of decimal precision"""
        pdf = DutyCalculationPDF()

        result = pdf.generate_import_report(
            hs_code="0808.1000",
            description="Test",
            quantity=100.5555,
            unit="kg",
            unit_value=10.1234,
            currency="USD",
            exchange_rate=280.5678,
            exchange_rate_source="NBP",
            fob_value=1017.40267,
            freight=0.0,
            insurance=0.0,
            other_charges=0.0,
            cif_foreign=1017.40267,
            cif_pkr=285382.6,
            customs_duty_rate=20.0,
            customs_duty_amount=57076.52,
            sales_tax_rate=18.0,
            sales_tax_amount=61642.64,
            income_tax_rate=5.5,
            income_tax_amount=15696.04,
            total_duties=134415.2,
            landed_cost=419797.8
        )

        assert isinstance(result, bytes)
