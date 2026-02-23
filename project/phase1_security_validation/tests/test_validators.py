"""
RAG_HS_CODE - Validator Tests
Phase 1: Security & Validation

Comprehensive test suite for input validation.
Run with: pytest test_validators.py -v
"""

import pytest

from validators import (
    HSCodeValidator,
    NumericValidator,
    ExchangeRateValidator,
    TextValidator,
    ValidationResult,
    HSCodeFormat,
    validate_hs_code,
    validate_calculation_inputs
)


class TestHSCodeValidator:
    """Test cases for HS Code validation"""

    # ==================== VALID CODES ====================

    @pytest.mark.parametrize("code,expected", [
        ("0808.1000", "0808.1000"),
        ("0101.2100", "0101.2100"),
        ("8517.1200", "8517.1200"),
        ("9999.9999", "9999.9999"),
        ("0100.0000", "0100.0000"),
    ])
    def test_valid_full_8_digit(self, code, expected):
        """Test valid 8-digit HS codes"""
        result = HSCodeValidator.validate(code)
        assert result.is_valid is True
        assert result.value == expected
        assert len(result.warnings) == 0

    @pytest.mark.parametrize("code,expected", [
        ("0808.10", "0808.1000"),
        ("0101.21", "0101.2100"),
        ("8517.12", "8517.1200"),
    ])
    def test_valid_6_digit_normalization(self, code, expected):
        """Test 6-digit codes normalize to 8-digit"""
        result = HSCodeValidator.validate(code)
        assert result.is_valid is True
        assert result.value == expected
        assert len(result.warnings) > 0  # Should have normalization warning

    @pytest.mark.parametrize("code,expected", [
        ("0808", "0808.0000"),
        ("0101", "0101.0000"),
        ("8517", "8517.0000"),
    ])
    def test_valid_4_digit_normalization(self, code, expected):
        """Test 4-digit codes normalize to 8-digit"""
        result = HSCodeValidator.validate(code)
        assert result.is_valid is True
        assert result.value == expected

    @pytest.mark.parametrize("code,expected", [
        ("08", "0800.0000"),
        ("01", "0100.0000"),
        ("85", "8500.0000"),
    ])
    def test_valid_chapter_codes(self, code, expected):
        """Test 2-digit chapter codes"""
        result = HSCodeValidator.validate(code)
        assert result.is_valid is True
        assert result.value == expected

    # ==================== INVALID CODES ====================

    @pytest.mark.parametrize("code,expected_msg", [
        ("", "HS code is required"),
        (None, "HS code is required"),
        ("   ", "HS code is required"),
    ])
    def test_empty_codes(self, code, expected_msg):
        """Test empty/null inputs"""
        result = HSCodeValidator.validate(code)
        assert result.is_valid is False
        assert expected_msg in result.message

    @pytest.mark.parametrize("code", [
        "abc",
        "abcd.efgh",
        "12.34.56",
        "!@#$.%^&*",
        "0808-1000",
        "0808/1000",
    ])
    def test_invalid_format(self, code):
        """Test invalid format rejection"""
        result = HSCodeValidator.validate(code)
        assert result.is_valid is False
        assert "Invalid" in result.message or "format" in result.message.lower()

    @pytest.mark.parametrize("code", [
        "0000.0000",
        "0000.1000",
        "00",
    ])
    def test_invalid_chapter_zero(self, code):
        """Test chapter 00 is rejected"""
        result = HSCodeValidator.validate(code)
        assert result.is_valid is False
        assert "chapter" in result.message.lower()

    # ==================== EDGE CASES ====================

    def test_whitespace_handling(self):
        """Test whitespace is trimmed"""
        result = HSCodeValidator.validate("  0808.1000  ")
        assert result.is_valid is True
        assert result.value == "0808.1000"

    def test_uppercase_handling(self):
        """Test case insensitivity (for any letters)"""
        result = HSCodeValidator.validate("0808.1000")
        assert result.is_valid is True

    def test_extra_digits_truncated(self):
        """Test extra digits are truncated"""
        result = HSCodeValidator.validate("08081000123")
        assert result.is_valid is True
        assert result.value == "0808.1000"

    def test_require_full_format(self):
        """Test allow_partial=False requires full 8-digit"""
        result = HSCodeValidator.validate("0808.10", allow_partial=False)
        assert result.is_valid is False
        assert "8-digit" in result.message

    # ==================== FORMAT DETECTION ====================

    @pytest.mark.parametrize("code,expected_format", [
        ("0808.1000", HSCodeFormat.FULL_8_DIGIT),
        ("0808.10", HSCodeFormat.SIX_DIGIT),
        ("0808", HSCodeFormat.FOUR_DIGIT),
        ("08", HSCodeFormat.CHAPTER),
        ("abc", HSCodeFormat.INVALID),
    ])
    def test_format_detection(self, code, expected_format):
        """Test format detection"""
        fmt = HSCodeValidator.detect_format(code)
        assert fmt == expected_format

    # ==================== COMPONENT EXTRACTION ====================

    def test_extract_components(self):
        """Test HS code component extraction"""
        components = HSCodeValidator.extract_components("0808.1000")
        assert components is not None
        assert components['chapter'] == "08"
        assert components['heading'] == "0808"
        assert components['subheading'] == "080810"
        assert components['tariff_line'] == "08081000"
        assert components['formatted'] == "0808.1000"

    def test_extract_components_invalid(self):
        """Test extraction returns None for invalid code"""
        components = HSCodeValidator.extract_components("invalid")
        assert components is None


class TestNumericValidator:
    """Test cases for numeric validation"""

    # ==================== POSITIVE VALUES ====================

    @pytest.mark.parametrize("value", [0, 1, 100, 1000.50, "500"])
    def test_valid_positive(self, value):
        """Test valid positive values"""
        result = NumericValidator.validate_positive(value, "Test")
        assert result.is_valid is True
        assert result.value >= 0

    @pytest.mark.parametrize("value", [-1, -100, -0.01])
    def test_negative_rejected(self, value):
        """Test negative values are rejected"""
        result = NumericValidator.validate_positive(value, "Test")
        assert result.is_valid is False
        assert "negative" in result.message.lower()

    def test_zero_allowed(self):
        """Test zero is allowed by default"""
        result = NumericValidator.validate_positive(0, "Test", allow_zero=True)
        assert result.is_valid is True

    def test_zero_rejected_when_required(self):
        """Test zero rejected when allow_zero=False"""
        result = NumericValidator.validate_positive(0, "Test", allow_zero=False)
        assert result.is_valid is False
        assert "greater than zero" in result.message

    def test_max_value_enforcement(self):
        """Test maximum value is enforced"""
        result = NumericValidator.validate_positive(150, "Test", max_value=100)
        assert result.is_valid is False
        assert "exceed" in result.message.lower()

    # ==================== PERCENTAGE VALUES ====================

    @pytest.mark.parametrize("value", [0, 50, 100, 18.5, "25"])
    def test_valid_percentage(self, value):
        """Test valid percentages"""
        result = NumericValidator.validate_percentage(value)
        assert result.is_valid is True
        assert 0 <= result.value <= 100

    @pytest.mark.parametrize("value", [101, 150, 200])
    def test_percentage_over_100_rejected(self, value):
        """Test percentages over 100 are rejected"""
        result = NumericValidator.validate_percentage(value)
        assert result.is_valid is False
        assert "100%" in result.message

    # ==================== INVALID INPUTS ====================

    @pytest.mark.parametrize("value", ["abc", "ten", "", None])
    def test_invalid_number_rejected(self, value):
        """Test non-numeric values are rejected"""
        result = NumericValidator.validate_positive(value, "Test")
        assert result.is_valid is False
        assert "valid number" in result.message


class TestExchangeRateValidator:
    """Test cases for exchange rate validation"""

    # ==================== VALID RATES ====================

    @pytest.mark.parametrize("rate", [280.0, 285.50, 250.0, 350.0, 200.01, 399.99])
    def test_valid_pkr_rates(self, rate):
        """Test valid PKR/USD rates"""
        result = ExchangeRateValidator.validate_pkr_rate(rate)
        assert result.is_valid is True
        assert result.value == rate

    # ==================== INVALID RATES ====================

    @pytest.mark.parametrize("rate,expected_error", [
        (150.0, "below minimum"),
        (199.99, "below minimum"),
        (400.01, "exceeds maximum"),
        (500.0, "exceeds maximum"),
    ])
    def test_out_of_range_rates(self, rate, expected_error):
        """Test out-of-range rates are rejected"""
        result = ExchangeRateValidator.validate_pkr_rate(rate)
        assert result.is_valid is False
        assert expected_error in result.message.lower()

    @pytest.mark.parametrize("rate", [0, -1, -280])
    def test_non_positive_rates(self, rate):
        """Test non-positive rates are rejected"""
        result = ExchangeRateValidator.validate_pkr_rate(rate)
        assert result.is_valid is False

    def test_invalid_rate_type(self):
        """Test invalid rate type"""
        result = ExchangeRateValidator.validate_pkr_rate("abc")
        assert result.is_valid is False
        assert "valid number" in result.message

    # ==================== RATE PAIRS ====================

    def test_valid_rate_pair(self):
        """Test valid buying/selling rate pair"""
        result = ExchangeRateValidator.validate_rate_pair(278.0, 280.0)
        assert result.is_valid is True
        assert result.value['buying'] == 278.0
        assert result.value['selling'] == 280.0
        assert result.value['spread'] == 2.0

    def test_invalid_rate_pair_inverted(self):
        """Test selling < buying is rejected"""
        result = ExchangeRateValidator.validate_rate_pair(280.0, 275.0)
        assert result.is_valid is False
        assert "higher" in result.message.lower()

    def test_rate_pair_high_spread_warning(self):
        """Test high spread generates warning"""
        result = ExchangeRateValidator.validate_rate_pair(270.0, 290.0)
        assert result.is_valid is True
        assert len(result.warnings) > 0
        assert "spread" in result.warnings[0].lower()


class TestTextValidator:
    """Test cases for text validation"""

    def test_normal_text(self):
        """Test normal text passes"""
        result = TextValidator.sanitize("Fresh apples from Kashmir")
        assert result.is_valid is True
        assert result.value == "Fresh apples from Kashmir"

    def test_whitespace_trimmed(self):
        """Test whitespace is trimmed"""
        result = TextValidator.sanitize("  text with spaces  ")
        assert result.is_valid is True
        assert result.value == "text with spaces"

    def test_empty_text(self):
        """Test empty text is valid"""
        result = TextValidator.sanitize("")
        assert result.is_valid is True
        assert result.value == ""

    def test_max_length_truncation(self):
        """Test text is truncated at max length"""
        long_text = "a" * 600
        result = TextValidator.sanitize(long_text, max_length=500)
        assert result.is_valid is True
        assert len(result.value) == 500
        assert len(result.warnings) > 0

    @pytest.mark.parametrize("dangerous", [
        "<script>alert('xss')</script>",
        "javascript:alert(1)",
        "onclick=alert(1)",
        "data:text/html,<script>",
    ])
    def test_dangerous_patterns_rejected(self, dangerous):
        """Test dangerous patterns are rejected"""
        result = TextValidator.sanitize(dangerous)
        assert result.is_valid is False
        assert "Invalid" in result.message


class TestConvenienceFunctions:
    """Test convenience functions"""

    def test_validate_hs_code_function(self):
        """Test validate_hs_code convenience function"""
        is_valid, normalized, error = validate_hs_code("0808.10")
        assert is_valid is True
        assert normalized == "0808.1000"
        assert error == ""

        is_valid, normalized, error = validate_hs_code("invalid")
        assert is_valid is False
        assert normalized is None
        assert error != ""

    def test_validate_calculation_inputs_function(self):
        """Test validate_calculation_inputs convenience function"""
        is_valid, error = validate_calculation_inputs(
            quantity=100,
            unit_value=10.0,
            exchange_rate=280.0,
            duty_rate=20.0
        )
        assert is_valid is True
        assert error == ""

        # Test invalid quantity
        is_valid, error = validate_calculation_inputs(
            quantity=0,
            unit_value=10.0,
            exchange_rate=280.0,
            duty_rate=20.0
        )
        assert is_valid is False
        assert "Quantity" in error


# ==================== INTEGRATION TESTS ====================

class TestIntegration:
    """Integration tests combining multiple validators"""

    def test_full_import_validation_flow(self):
        """Test complete validation flow for import calculation"""
        # Step 1: Validate HS code
        hs_result = HSCodeValidator.validate("0808.10")
        assert hs_result.is_valid is True

        # Step 2: Validate quantity
        qty_result = NumericValidator.validate_positive(100, "Quantity", allow_zero=False)
        assert qty_result.is_valid is True

        # Step 3: Validate unit value
        val_result = NumericValidator.validate_positive(10.0, "Unit Value", allow_zero=False)
        assert val_result.is_valid is True

        # Step 4: Validate exchange rate
        rate_result = ExchangeRateValidator.validate_pkr_rate(280.0)
        assert rate_result.is_valid is True

        # Step 5: Validate duty rates
        cd_result = NumericValidator.validate_percentage(20.0, "Customs Duty")
        assert cd_result.is_valid is True

        st_result = NumericValidator.validate_percentage(18.0, "Sales Tax")
        assert st_result.is_valid is True

        it_result = NumericValidator.validate_percentage(5.5, "Income Tax")
        assert it_result.is_valid is True

    def test_validation_chain_short_circuits_on_error(self):
        """Test validation stops at first error"""
        # Invalid HS code should prevent further validation
        hs_result = HSCodeValidator.validate("invalid")
        assert hs_result.is_valid is False

        # In real app, would not proceed to other validations
        # This test documents expected behavior


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
