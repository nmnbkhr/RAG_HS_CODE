"""
RAG_HS_CODE - Input Validators Module
Phase 1: Security & Validation

This module provides comprehensive input validation for:
- HS codes (format, range, normalization)
- Numeric values (quantities, prices, rates)
- Exchange rates (range validation)
- Text inputs (sanitization)
"""

import re
from typing import Tuple, Optional, Union
from dataclasses import dataclass
from enum import Enum


class ValidationError(Exception):
    """Custom exception for validation errors"""
    def __init__(self, message: str, field: str = None, code: str = None):
        self.message = message
        self.field = field
        self.code = code
        super().__init__(self.message)


class HSCodeFormat(Enum):
    """HS Code format types"""
    FULL_8_DIGIT = "full"      # XXXX.XXXX
    SIX_DIGIT = "six"          # XXXX.XX
    FOUR_DIGIT = "heading"     # XXXX
    CHAPTER = "chapter"        # XX
    INVALID = "invalid"


@dataclass
class ValidationResult:
    """Result of a validation operation"""
    is_valid: bool
    value: any
    original: any
    message: str = ""
    warnings: list = None

    def __post_init__(self):
        if self.warnings is None:
            self.warnings = []


class HSCodeValidator:
    """
    Validates and normalizes HS/PCT codes for Pakistan Customs Tariff.

    Valid formats:
    - 8 digits: XXXX.XXXX (e.g., 0808.1000) - Full tariff line
    - 6 digits: XXXX.XX (e.g., 0808.10) - Subheading
    - 4 digits: XXXX (e.g., 0808) - Heading
    - 2 digits: XX (e.g., 08) - Chapter (search only)

    Validation rules:
    - Chapter (first 2 digits): 01-99
    - All digits must be numeric
    - Proper format with period separator
    """

    # Valid chapter range (Pakistan uses WCO HS chapters 01-97, with 98-99 special)
    MIN_CHAPTER = 1
    MAX_CHAPTER = 99

    # Regex patterns for different formats
    PATTERN_FULL = re.compile(r'^(\d{4})\.(\d{4})$')
    PATTERN_SIX = re.compile(r'^(\d{4})\.(\d{2})$')
    PATTERN_FOUR = re.compile(r'^(\d{4})$')
    PATTERN_CHAPTER = re.compile(r'^(\d{2})$')
    PATTERN_DIGITS_ONLY = re.compile(r'^(\d+)$')

    @classmethod
    def detect_format(cls, hs_code: str) -> HSCodeFormat:
        """Detect the format of an HS code string"""
        if not hs_code:
            return HSCodeFormat.INVALID

        code = hs_code.strip()

        if cls.PATTERN_FULL.match(code):
            return HSCodeFormat.FULL_8_DIGIT
        elif cls.PATTERN_SIX.match(code):
            return HSCodeFormat.SIX_DIGIT
        elif cls.PATTERN_FOUR.match(code):
            return HSCodeFormat.FOUR_DIGIT
        elif cls.PATTERN_CHAPTER.match(code):
            return HSCodeFormat.CHAPTER

        return HSCodeFormat.INVALID

    @classmethod
    def validate(cls, hs_code: str, allow_partial: bool = True) -> ValidationResult:
        """
        Validate and normalize an HS code.

        Args:
            hs_code: The HS code to validate
            allow_partial: If True, allow 2, 4, 6 digit codes. If False, require 8 digits.

        Returns:
            ValidationResult with normalized code or error message
        """
        if not hs_code or not hs_code.strip():
            return ValidationResult(
                is_valid=False,
                value=None,
                original=hs_code,
                message="HS code is required"
            )

        # Clean input
        code = hs_code.strip().upper()

        # Check for invalid characters (only digits and period allowed)
        if re.search(r'[^\d.]', code):
            return ValidationResult(
                is_valid=False,
                value=None,
                original=hs_code,
                message="Invalid HS code format. Use XXXX.XXXX (e.g., 0808.1000)"
            )

        # If only digits, try to format
        if cls.PATTERN_DIGITS_ONLY.match(code):
            code = cls._format_digits(code)

        cleaned = code

        # Detect format
        fmt = cls.detect_format(cleaned)

        if fmt == HSCodeFormat.INVALID:
            return ValidationResult(
                is_valid=False,
                value=None,
                original=hs_code,
                message="Invalid HS code format. Use XXXX.XXXX (e.g., 0808.1000)"
            )

        # Check if partial codes are allowed
        if not allow_partial and fmt != HSCodeFormat.FULL_8_DIGIT:
            return ValidationResult(
                is_valid=False,
                value=None,
                original=hs_code,
                message="Full 8-digit HS code required (XXXX.XXXX)"
            )

        # Validate chapter range
        chapter = int(cleaned[:2])
        if chapter < cls.MIN_CHAPTER or chapter > cls.MAX_CHAPTER:
            return ValidationResult(
                is_valid=False,
                value=None,
                original=hs_code,
                message=f"Invalid chapter: {chapter:02d}. Must be between 01-99"
            )

        # Normalize to full format
        normalized = cls._normalize(cleaned, fmt)

        warnings = []
        if fmt != HSCodeFormat.FULL_8_DIGIT:
            warnings.append(f"Code normalized from {cleaned} to {normalized}")

        return ValidationResult(
            is_valid=True,
            value=normalized,
            original=hs_code,
            message="Valid HS code",
            warnings=warnings
        )

    @classmethod
    def _format_digits(cls, digits: str) -> str:
        """Format a string of digits into HS code format"""
        # Don't strip leading zeros - they're significant in HS codes
        # Pad with leading zeros if needed for proper format

        if len(digits) <= 2:
            # Chapter code: pad to 2 digits
            return digits.zfill(2)
        elif len(digits) <= 4:
            # Heading code: pad to 4 digits
            return digits.zfill(4)
        elif len(digits) <= 6:
            # Subheading: first 4 digits, then remaining padded to 2
            padded = digits.zfill(6)
            return f"{padded[:4]}.{padded[4:6]}"
        elif len(digits) <= 8:
            # Full code: first 4 digits, then next 4
            padded = digits.zfill(8)
            return f"{padded[:4]}.{padded[4:8]}"
        else:
            # Truncate to 8 digits
            return f"{digits[:4]}.{digits[4:8]}"

    @classmethod
    def _normalize(cls, code: str, fmt: HSCodeFormat) -> str:
        """Normalize code to full 8-digit format"""
        if fmt == HSCodeFormat.FULL_8_DIGIT:
            return code
        elif fmt == HSCodeFormat.SIX_DIGIT:
            return f"{code}00"
        elif fmt == HSCodeFormat.FOUR_DIGIT:
            return f"{code}.0000"
        elif fmt == HSCodeFormat.CHAPTER:
            return f"{code}00.0000"
        return code

    @classmethod
    def extract_components(cls, hs_code: str) -> dict:
        """Extract chapter, heading, subheading from validated HS code"""
        result = cls.validate(hs_code)
        if not result.is_valid:
            return None

        code = result.value.replace('.', '')
        return {
            'chapter': code[:2],
            'heading': code[:4],
            'subheading': code[:6],
            'tariff_line': code,
            'formatted': f"{code[:4]}.{code[4:]}"
        }


class NumericValidator:
    """Validates numeric inputs for calculations"""

    @staticmethod
    def validate_positive(
        value: Union[int, float, str],
        field_name: str = "Value",
        allow_zero: bool = True,
        max_value: float = None
    ) -> ValidationResult:
        """
        Validate a positive numeric value.

        Args:
            value: The value to validate
            field_name: Name for error messages
            allow_zero: If True, zero is valid
            max_value: Maximum allowed value

        Returns:
            ValidationResult with float value or error
        """
        try:
            num = float(value)
        except (TypeError, ValueError):
            return ValidationResult(
                is_valid=False,
                value=None,
                original=value,
                message=f"{field_name} must be a valid number"
            )

        if num < 0:
            return ValidationResult(
                is_valid=False,
                value=None,
                original=value,
                message=f"{field_name} cannot be negative"
            )

        if not allow_zero and num == 0:
            return ValidationResult(
                is_valid=False,
                value=None,
                original=value,
                message=f"{field_name} must be greater than zero"
            )

        if max_value is not None and num > max_value:
            return ValidationResult(
                is_valid=False,
                value=None,
                original=value,
                message=f"{field_name} cannot exceed {max_value}"
            )

        return ValidationResult(
            is_valid=True,
            value=num,
            original=value,
            message="Valid"
        )

    @staticmethod
    def validate_percentage(
        value: Union[int, float, str],
        field_name: str = "Rate"
    ) -> ValidationResult:
        """Validate a percentage value (0-100)"""
        result = NumericValidator.validate_positive(value, field_name, allow_zero=True)
        if not result.is_valid:
            return result

        if result.value > 100:
            return ValidationResult(
                is_valid=False,
                value=None,
                original=value,
                message=f"{field_name} cannot exceed 100%"
            )

        return result


class ExchangeRateValidator:
    """Validates exchange rates with realistic bounds"""

    # PKR/USD rate bounds (reasonable range for 2024-2026)
    MIN_PKR_USD = 200.0
    MAX_PKR_USD = 400.0

    # Maximum spread between buying/selling
    MAX_SPREAD = 10.0

    @classmethod
    def validate_pkr_rate(
        cls,
        rate: Union[int, float, str],
        rate_type: str = "exchange"
    ) -> ValidationResult:
        """
        Validate PKR exchange rate is within realistic bounds.

        Args:
            rate: The exchange rate to validate
            rate_type: "buying" or "selling" for context

        Returns:
            ValidationResult with validated rate
        """
        try:
            rate_float = float(rate)
        except (TypeError, ValueError):
            return ValidationResult(
                is_valid=False,
                value=None,
                original=rate,
                message="Exchange rate must be a valid number"
            )

        if rate_float <= 0:
            return ValidationResult(
                is_valid=False,
                value=None,
                original=rate,
                message="Exchange rate must be positive"
            )

        warnings = []

        if rate_float < cls.MIN_PKR_USD:
            return ValidationResult(
                is_valid=False,
                value=None,
                original=rate,
                message=f"Exchange rate {rate_float:.2f} is below minimum expected ({cls.MIN_PKR_USD})"
            )

        if rate_float > cls.MAX_PKR_USD:
            return ValidationResult(
                is_valid=False,
                value=None,
                original=rate,
                message=f"Exchange rate {rate_float:.2f} exceeds maximum expected ({cls.MAX_PKR_USD})"
            )

        return ValidationResult(
            is_valid=True,
            value=rate_float,
            original=rate,
            message="Valid exchange rate",
            warnings=warnings
        )

    @classmethod
    def validate_rate_pair(
        cls,
        buying_rate: float,
        selling_rate: float
    ) -> ValidationResult:
        """
        Validate that buying/selling rates are consistent.
        Selling rate should be higher than buying rate.
        """
        buy_result = cls.validate_pkr_rate(buying_rate, "buying")
        sell_result = cls.validate_pkr_rate(selling_rate, "selling")

        if not buy_result.is_valid:
            return buy_result
        if not sell_result.is_valid:
            return sell_result

        spread = sell_result.value - buy_result.value

        if spread < 0:
            return ValidationResult(
                is_valid=False,
                value=None,
                original=(buying_rate, selling_rate),
                message="Selling rate must be higher than buying rate"
            )

        warnings = []
        if spread > cls.MAX_SPREAD:
            warnings.append(f"Unusually high spread: {spread:.2f} PKR")

        return ValidationResult(
            is_valid=True,
            value={'buying': buy_result.value, 'selling': sell_result.value, 'spread': spread},
            original=(buying_rate, selling_rate),
            message="Valid rate pair",
            warnings=warnings
        )


class TextValidator:
    """Validates and sanitizes text inputs"""

    # Characters that could be problematic
    DANGEROUS_PATTERNS = [
        r'<script',
        r'javascript:',
        r'on\w+=',
        r'data:text/html',
    ]

    @classmethod
    def sanitize(cls, text: str, max_length: int = 500) -> ValidationResult:
        """
        Sanitize text input for safe display.

        Args:
            text: Input text
            max_length: Maximum allowed length

        Returns:
            ValidationResult with sanitized text
        """
        if not text:
            return ValidationResult(
                is_valid=True,
                value="",
                original=text,
                message="Empty input"
            )

        # Trim whitespace
        cleaned = text.strip()

        # Check for dangerous patterns
        text_lower = cleaned.lower()
        for pattern in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return ValidationResult(
                    is_valid=False,
                    value=None,
                    original=text,
                    message="Invalid characters detected"
                )

        # Truncate if too long
        warnings = []
        if len(cleaned) > max_length:
            cleaned = cleaned[:max_length]
            warnings.append(f"Text truncated to {max_length} characters")

        # Remove control characters
        cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', cleaned)

        return ValidationResult(
            is_valid=True,
            value=cleaned,
            original=text,
            message="Valid text",
            warnings=warnings
        )


# Convenience functions for quick validation
def validate_hs_code(code: str, require_full: bool = False) -> Tuple[bool, str, str]:
    """
    Quick validation of HS code.

    Returns:
        Tuple of (is_valid, normalized_code or None, error_message or "")
    """
    result = HSCodeValidator.validate(code, allow_partial=not require_full)
    return result.is_valid, result.value, result.message if not result.is_valid else ""


def validate_calculation_inputs(
    quantity: float,
    unit_value: float,
    exchange_rate: float,
    duty_rate: float
) -> Tuple[bool, str]:
    """
    Validate all inputs for a duty calculation.

    Returns:
        Tuple of (is_valid, error_message or "")
    """
    # Validate quantity
    qty_result = NumericValidator.validate_positive(quantity, "Quantity", allow_zero=False)
    if not qty_result.is_valid:
        return False, qty_result.message

    # Validate unit value
    val_result = NumericValidator.validate_positive(unit_value, "Unit value", allow_zero=False)
    if not val_result.is_valid:
        return False, val_result.message

    # Validate exchange rate
    rate_result = ExchangeRateValidator.validate_pkr_rate(exchange_rate)
    if not rate_result.is_valid:
        return False, rate_result.message

    # Validate duty rate
    duty_result = NumericValidator.validate_percentage(duty_rate, "Duty rate")
    if not duty_result.is_valid:
        return False, duty_result.message

    return True, ""


if __name__ == "__main__":
    # Quick test
    print("Testing HS Code Validator...")
    test_codes = ["0808.1000", "0808.10", "0808", "08", "abc", "", "0000.0000"]
    for code in test_codes:
        result = HSCodeValidator.validate(code)
        status = "✓" if result.is_valid else "✗"
        print(f"  {status} '{code}' -> {result.value} ({result.message})")

    print("\nTesting Exchange Rate Validator...")
    test_rates = [280.50, 150.0, 500.0, -10, "abc"]
    for rate in test_rates:
        result = ExchangeRateValidator.validate_pkr_rate(rate)
        status = "✓" if result.is_valid else "✗"
        print(f"  {status} {rate} -> {result.value} ({result.message})")
