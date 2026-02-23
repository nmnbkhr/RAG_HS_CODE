"""
RAG_HS_CODE - Calculator Tests
Phase 1: Security & Validation

Comprehensive test suite for duty calculations.
Run with: pytest test_calculators.py -v

All test cases are based on Pakistan Customs calculation methodology.
"""

import pytest
from decimal import Decimal

from calculators import (
    ImportDutyCalculator,
    ExportCalculator,
    DutyRates,
    CIFComponents,
    CalculationResult,
    ExportResult
)


class TestDutyRates:
    """Test DutyRates dataclass"""

    def test_valid_rates(self):
        """Test valid duty rates"""
        rates = DutyRates(
            customs_duty=20.0,
            sales_tax=18.0,
            income_tax=5.5,
            additional_duty=0.0,
            regulatory_duty=0.0
        )
        errors = rates.validate()
        assert len(errors) == 0

    def test_negative_rate_error(self):
        """Test negative rates are flagged"""
        rates = DutyRates(customs_duty=-5.0)
        errors = rates.validate()
        assert len(errors) > 0
        assert "negative" in errors[0]

    def test_over_100_rate_error(self):
        """Test rates over 100% are flagged"""
        rates = DutyRates(customs_duty=150.0)
        errors = rates.validate()
        assert len(errors) > 0
        assert "100%" in errors[0]

    def test_to_dict(self):
        """Test conversion to dictionary"""
        rates = DutyRates(customs_duty=20.0, sales_tax=18.0)
        d = rates.to_dict()
        assert d['customs_duty_pct'] == 20.0
        assert d['sales_tax_pct'] == 18.0


class TestCIFComponents:
    """Test CIFComponents dataclass"""

    def test_total_cif_calculation(self):
        """Test CIF total calculation"""
        cif = CIFComponents(
            fob_value=1000.0,
            freight=100.0,
            insurance=50.0,
            other_charges=25.0
        )
        assert cif.total_cif == 1175.0

    def test_valid_components(self):
        """Test valid CIF components"""
        cif = CIFComponents(fob_value=1000.0)
        errors = cif.validate()
        assert len(errors) == 0

    def test_negative_fob_error(self):
        """Test negative FOB is flagged"""
        cif = CIFComponents(fob_value=-100.0)
        errors = cif.validate()
        assert len(errors) > 0
        assert "FOB" in errors[0]


class TestImportDutyCalculator:
    """Test import duty calculations"""

    # ==================== BASIC CALCULATIONS ====================

    def test_basic_import_calculation(self):
        """
        Test Case: Basic import with 20% CD, 18% ST, 5.5% IT

        Input:
        - Quantity: 100 kg
        - Unit price: $10/kg
        - FOB: $1,000
        - Exchange rate: 280 PKR/USD

        Expected:
        - CIF (PKR): 280,000
        - Customs Duty (20%): 56,000
        - Sales Tax Base: 336,000 (CIF + CD)
        - Sales Tax (18%): 60,480
        - Income Tax (5.5%): 15,400
        - Total Duties: 131,880
        - Landed Cost: 411,880
        """
        rates = DutyRates(customs_duty=20.0, sales_tax=18.0, income_tax=5.5)
        cif = CIFComponents(fob_value=1000.0)

        result = ImportDutyCalculator.calculate(
            hs_code="0808.1000",
            quantity=100,
            unit_of_measure="kg",
            unit_value=10.0,
            currency="USD",
            exchange_rate=280.0,
            exchange_rate_source="Test",
            duty_rates=rates,
            cif_components=cif
        )

        # Verify calculations with tolerance of 0.01
        assert abs(result.cif_value_pkr - 280000.0) < 0.01
        assert abs(result.customs_duty_amount - 56000.0) < 0.01
        assert abs(result.sales_tax_base - 336000.0) < 0.01
        assert abs(result.sales_tax_amount - 60480.0) < 0.01
        assert abs(result.income_tax_amount - 15400.0) < 0.01
        assert abs(result.total_duties - 131880.0) < 0.01
        assert abs(result.total_landed_cost - 411880.0) < 0.01

    def test_zero_duty_calculation(self):
        """
        Test Case: Zero customs duty item

        Input:
        - FOB: $5,000
        - CD: 0%, ST: 18%, IT: 5.5%
        - Exchange rate: 280

        Expected:
        - CIF (PKR): 1,400,000
        - Customs Duty: 0
        - Sales Tax Base: 1,400,000 (CIF only, no CD)
        - Sales Tax: 252,000
        - Income Tax: 77,000
        """
        rates = DutyRates(customs_duty=0.0, sales_tax=18.0, income_tax=5.5)
        cif = CIFComponents(fob_value=5000.0)

        result = ImportDutyCalculator.calculate(
            hs_code="0101.2100",
            quantity=1,
            unit_of_measure="units",
            unit_value=5000.0,
            currency="USD",
            exchange_rate=280.0,
            exchange_rate_source="Test",
            duty_rates=rates,
            cif_components=cif
        )

        assert abs(result.cif_value_pkr - 1400000.0) < 0.01
        assert result.customs_duty_amount == 0.0
        assert abs(result.sales_tax_base - 1400000.0) < 0.01
        assert abs(result.sales_tax_amount - 252000.0) < 0.01
        assert abs(result.income_tax_amount - 77000.0) < 0.01

    def test_with_freight_and_insurance(self):
        """
        Test Case: Import with CIF components

        Input:
        - FOB: $1,000
        - Freight: $100
        - Insurance: $50
        - CIF: $1,150
        - CD: 20%, ST: 18%
        - Exchange rate: 280

        Expected:
        - CIF (Foreign): 1,150
        - CIF (PKR): 322,000
        """
        rates = DutyRates(customs_duty=20.0, sales_tax=18.0, income_tax=5.5)
        cif = CIFComponents(
            fob_value=1000.0,
            freight=100.0,
            insurance=50.0
        )

        result = ImportDutyCalculator.calculate(
            hs_code="0808.1000",
            quantity=1,
            unit_of_measure="units",
            unit_value=1000.0,
            currency="USD",
            exchange_rate=280.0,
            exchange_rate_source="Test",
            duty_rates=rates,
            cif_components=cif
        )

        assert abs(result.cif_value_foreign - 1150.0) < 0.01
        assert abs(result.cif_value_pkr - 322000.0) < 0.01

    def test_with_regulatory_duty(self):
        """
        Test Case: Import with regulatory duty

        Input:
        - CIF (PKR): 280,000
        - CD: 20% (56,000)
        - RD: 10% (28,000)
        - ST Base: 364,000 (CIF + CD + RD)
        - ST: 18% (65,520)
        """
        rates = DutyRates(
            customs_duty=20.0,
            regulatory_duty=10.0,
            sales_tax=18.0,
            income_tax=5.5
        )
        cif = CIFComponents(fob_value=1000.0)

        result = ImportDutyCalculator.calculate(
            hs_code="8517.1200",
            quantity=1,
            unit_of_measure="units",
            unit_value=1000.0,
            currency="USD",
            exchange_rate=280.0,
            exchange_rate_source="Test",
            duty_rates=rates,
            cif_components=cif
        )

        assert abs(result.regulatory_duty_amount - 28000.0) < 0.01
        assert abs(result.sales_tax_base - 364000.0) < 0.01
        assert abs(result.sales_tax_amount - 65520.0) < 0.01

    # ==================== EDGE CASES ====================

    def test_small_quantity(self):
        """Test calculation with small quantity"""
        rates = DutyRates(customs_duty=20.0, sales_tax=18.0)
        cif = CIFComponents(fob_value=10.0)

        result = ImportDutyCalculator.calculate(
            hs_code="0808.1000",
            quantity=1,
            unit_of_measure="kg",
            unit_value=10.0,
            currency="USD",
            exchange_rate=280.0,
            exchange_rate_source="Test",
            duty_rates=rates,
            cif_components=cif
        )

        assert result.validation_passed is True
        assert result.cif_value_pkr == 2800.0

    def test_large_quantity(self):
        """Test calculation with large quantity"""
        rates = DutyRates(customs_duty=20.0, sales_tax=18.0)
        cif = CIFComponents(fob_value=1000000.0)

        result = ImportDutyCalculator.calculate(
            hs_code="0808.1000",
            quantity=1000000,
            unit_of_measure="kg",
            unit_value=1.0,
            currency="USD",
            exchange_rate=280.0,
            exchange_rate_source="Test",
            duty_rates=rates,
            cif_components=cif
        )

        assert result.validation_passed is True
        assert result.cif_value_pkr == 280000000.0

    def test_decimal_values(self):
        """Test calculation with decimal values"""
        rates = DutyRates(customs_duty=17.5, sales_tax=18.0, income_tax=5.5)
        cif = CIFComponents(fob_value=1234.56)

        result = ImportDutyCalculator.calculate(
            hs_code="0808.1000",
            quantity=12.5,
            unit_of_measure="kg",
            unit_value=98.7648,
            currency="USD",
            exchange_rate=278.75,
            exchange_rate_source="Test",
            duty_rates=rates,
            cif_components=cif
        )

        assert result.validation_passed is True
        # Verify calculation is reasonable
        assert result.cif_value_pkr > 0
        assert result.total_duties > 0

    # ==================== VALIDATION ERRORS ====================

    def test_negative_quantity_error(self):
        """Test negative quantity generates error"""
        rates = DutyRates(customs_duty=20.0)
        cif = CIFComponents(fob_value=1000.0)

        result = ImportDutyCalculator.calculate(
            hs_code="0808.1000",
            quantity=-10,
            unit_of_measure="kg",
            unit_value=10.0,
            currency="USD",
            exchange_rate=280.0,
            exchange_rate_source="Test",
            duty_rates=rates,
            cif_components=cif
        )

        assert result.validation_passed is False
        assert "Quantity" in result.validation_errors[0]

    def test_negative_exchange_rate_error(self):
        """Test negative exchange rate generates error"""
        rates = DutyRates(customs_duty=20.0)
        cif = CIFComponents(fob_value=1000.0)

        result = ImportDutyCalculator.calculate(
            hs_code="0808.1000",
            quantity=10,
            unit_of_measure="kg",
            unit_value=10.0,
            currency="USD",
            exchange_rate=-280.0,
            exchange_rate_source="Test",
            duty_rates=rates,
            cif_components=cif
        )

        assert result.validation_passed is False
        assert "Exchange rate" in result.validation_errors[0]

    # ==================== VERIFICATION ====================

    def test_calculation_verification(self):
        """Test that calculation can be verified"""
        rates = DutyRates(customs_duty=20.0, sales_tax=18.0, income_tax=5.5)
        cif = CIFComponents(fob_value=1000.0)

        result = ImportDutyCalculator.calculate(
            hs_code="0808.1000",
            quantity=100,
            unit_of_measure="kg",
            unit_value=10.0,
            currency="USD",
            exchange_rate=280.0,
            exchange_rate_source="Test",
            duty_rates=rates,
            cif_components=cif
        )

        verification = ImportDutyCalculator.verify_calculation(result)

        # All checks should pass
        for check_name, passed in verification.items():
            assert passed, f"Verification failed for: {check_name}"

    # ==================== SERIALIZATION ====================

    def test_to_dict(self):
        """Test result serialization to dict"""
        rates = DutyRates(customs_duty=20.0, sales_tax=18.0)
        cif = CIFComponents(fob_value=1000.0)

        result = ImportDutyCalculator.calculate(
            hs_code="0808.1000",
            quantity=100,
            unit_of_measure="kg",
            unit_value=10.0,
            currency="USD",
            exchange_rate=280.0,
            exchange_rate_source="Test",
            duty_rates=rates,
            cif_components=cif
        )

        d = result.to_dict()

        assert 'input' in d
        assert 'cif' in d
        assert 'rates' in d
        assert 'duties' in d
        assert 'totals' in d
        assert 'audit' in d

        assert d['input']['hs_code'] == "0808.1000"
        assert d['input']['quantity'] == 100

    def test_to_json(self):
        """Test result serialization to JSON"""
        rates = DutyRates(customs_duty=20.0, sales_tax=18.0)
        cif = CIFComponents(fob_value=1000.0)

        result = ImportDutyCalculator.calculate(
            hs_code="0808.1000",
            quantity=100,
            unit_of_measure="kg",
            unit_value=10.0,
            currency="USD",
            exchange_rate=280.0,
            exchange_rate_source="Test",
            duty_rates=rates,
            cif_components=cif
        )

        json_str = result.to_json()
        assert isinstance(json_str, str)
        assert "0808.1000" in json_str


class TestExportCalculator:
    """Test export proceeds calculations"""

    def test_basic_export_calculation(self):
        """
        Test Case: Basic export

        Input:
        - Quantity: 100 kg
        - FOB: $10/kg
        - Total FOB: $1,000
        - TT Buying rate: 278 PKR/USD

        Expected:
        - FOB (PKR): 278,000
        - Regulatory Duty: 0
        - Net Proceeds: 278,000
        """
        result = ExportCalculator.calculate(
            hs_code="0808.1000",
            quantity=100,
            unit_of_measure="kg",
            fob_per_unit=10.0,
            currency="USD",
            exchange_rate=278.0,
            exchange_rate_source="NBP TT Buying"
        )

        assert result.total_fob_foreign == 1000.0
        assert result.total_fob_pkr == 278000.0
        assert result.regulatory_duty_amount == 0.0
        assert result.net_proceeds_pkr == 278000.0

    def test_export_with_regulatory_duty(self):
        """
        Test Case: Export with regulatory duty

        Input:
        - FOB (PKR): 278,000
        - Regulatory Duty: 5%

        Expected:
        - Regulatory Duty: 13,900
        - Net Proceeds: 264,100
        """
        result = ExportCalculator.calculate(
            hs_code="0808.1000",
            quantity=100,
            unit_of_measure="kg",
            fob_per_unit=10.0,
            currency="USD",
            exchange_rate=278.0,
            exchange_rate_source="NBP TT Buying",
            regulatory_duty_rate=5.0
        )

        assert result.regulatory_duty_rate == 5.0
        assert abs(result.regulatory_duty_amount - 13900.0) < 0.01
        assert abs(result.net_proceeds_pkr - 264100.0) < 0.01

    def test_drawback_eligible_scheme(self):
        """Test DTRE scheme is drawback eligible"""
        result = ExportCalculator.calculate(
            hs_code="6109.1000",
            quantity=1000,
            unit_of_measure="units",
            fob_per_unit=5.0,
            currency="USD",
            exchange_rate=278.0,
            exchange_rate_source="NBP TT Buying",
            export_scheme="DTRE (Duty & Tax Remission)"
        )

        assert result.drawback_eligible is True
        assert result.estimated_drawback > 0

    def test_normal_export_not_drawback_eligible(self):
        """Test normal export is not drawback eligible"""
        result = ExportCalculator.calculate(
            hs_code="6109.1000",
            quantity=1000,
            unit_of_measure="units",
            fob_per_unit=5.0,
            currency="USD",
            exchange_rate=278.0,
            exchange_rate_source="NBP TT Buying",
            export_scheme="Normal Export"
        )

        assert result.drawback_eligible is False
        assert result.estimated_drawback == 0

    def test_export_validation_errors(self):
        """Test export validation errors"""
        result = ExportCalculator.calculate(
            hs_code="6109.1000",
            quantity=-100,  # Invalid
            unit_of_measure="units",
            fob_per_unit=5.0,
            currency="USD",
            exchange_rate=278.0,
            exchange_rate_source="Test"
        )

        assert result.validation_passed is False
        assert "Quantity" in result.validation_errors[0]


class TestCalculationAccuracy:
    """
    Test calculation accuracy against known values.
    These are regression tests to ensure calculations don't drift.
    """

    @pytest.mark.parametrize("cif_pkr,cd_rate,st_rate,it_rate,expected_cd,expected_st,expected_it", [
        # (CIF PKR, CD%, ST%, IT%, Expected CD, Expected ST, Expected IT)
        (100000, 20, 18, 5.5, 20000, 21600, 5500),
        (280000, 20, 18, 5.5, 56000, 60480, 15400),
        (500000, 10, 18, 5.5, 50000, 99000, 27500),
        (1000000, 0, 18, 5.5, 0, 180000, 55000),
        (1000000, 25, 18, 5.5, 250000, 225000, 55000),
    ])
    def test_calculation_accuracy(
        self, cif_pkr, cd_rate, st_rate, it_rate,
        expected_cd, expected_st, expected_it
    ):
        """Test calculation accuracy against expected values"""
        # Reverse engineer the inputs to get the desired CIF
        exchange_rate = 280.0
        fob_foreign = cif_pkr / exchange_rate

        rates = DutyRates(customs_duty=cd_rate, sales_tax=st_rate, income_tax=it_rate)
        cif = CIFComponents(fob_value=fob_foreign)

        result = ImportDutyCalculator.calculate(
            hs_code="0808.1000",
            quantity=1,
            unit_of_measure="units",
            unit_value=fob_foreign,
            currency="USD",
            exchange_rate=exchange_rate,
            exchange_rate_source="Test",
            duty_rates=rates,
            cif_components=cif
        )

        # Allow small tolerance for floating point
        assert abs(result.customs_duty_amount - expected_cd) < 1.0
        assert abs(result.sales_tax_amount - expected_st) < 1.0
        assert abs(result.income_tax_amount - expected_it) < 1.0

    def test_effective_duty_rate_calculation(self):
        """Test effective duty rate is calculated correctly"""
        rates = DutyRates(customs_duty=20.0, sales_tax=18.0, income_tax=5.5)
        cif = CIFComponents(fob_value=1000.0)

        result = ImportDutyCalculator.calculate(
            hs_code="0808.1000",
            quantity=1,
            unit_of_measure="units",
            unit_value=1000.0,
            currency="USD",
            exchange_rate=280.0,
            exchange_rate_source="Test",
            duty_rates=rates,
            cif_components=cif
        )

        # Effective rate = Total Duties / CIF × 100
        expected_effective = (result.total_duties / result.cif_value_pkr) * 100
        assert abs(result.effective_duty_rate - expected_effective) < 0.01


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
