"""
Phase 4: Features - Multi-Currency Manager Tests

High-grade tests for multi-currency rate management and conversion.
"""

import pytest
from multi_currency import (
    MultiCurrencyManager, CurrencyRate, ConversionResult,
    SUPPORTED_CURRENCIES
)


@pytest.fixture
def manager():
    m = MultiCurrencyManager()
    m.set_rate("USD", 280.50, "NBP", "selling")
    m.set_rate("EUR", 310.00, "NBP", "selling")
    m.set_rate("GBP", 355.00, "NBP", "selling")
    m.set_rate("AED", 76.40, "NBP", "selling")
    return m


class TestCurrencyRate:
    """Tests for CurrencyRate dataclass"""

    def test_create(self):
        rate = CurrencyRate("USD", "PKR", 280.50, "NBP", "2026-01-01", "selling")
        assert rate.from_currency == "USD"
        assert rate.rate == 280.50

    def test_inverse(self):
        rate = CurrencyRate("USD", "PKR", 280.50, "NBP", "2026-01-01")
        assert abs(rate.inverse - (1.0 / 280.50)) < 0.0001

    def test_inverse_zero_rate(self):
        rate = CurrencyRate("USD", "PKR", 0, "NBP", "2026-01-01")
        assert rate.inverse == 0.0

    def test_to_dict(self):
        rate = CurrencyRate("USD", "PKR", 280.50, "NBP", "2026-01-01", "selling")
        d = rate.to_dict()
        assert d["from"] == "USD"
        assert d["to"] == "PKR"
        assert d["rate"] == 280.50
        assert "inverse" in d


class TestConversionResult:
    """Tests for ConversionResult"""

    def test_create(self):
        result = ConversionResult("USD", "PKR", 100.0, 28050.0, 280.50, "NBP")
        assert result.to_amount == 28050.0

    def test_to_dict(self):
        result = ConversionResult("USD", "PKR", 100.0, 28050.0, 280.50, "NBP")
        d = result.to_dict()
        assert d["from_currency"] == "USD"
        assert d["to_amount"] == 28050.0


class TestMultiCurrencyManager:
    """Tests for MultiCurrencyManager core"""

    def test_set_rate(self):
        m = MultiCurrencyManager()
        rate = m.set_rate("USD", 280.50, "NBP")
        assert rate.from_currency == "USD"
        assert rate.rate == 280.50

    def test_set_rate_validates_currency(self):
        m = MultiCurrencyManager()
        # Valid unknown 3-letter code should work
        rate = m.set_rate("XYZ", 100.0)
        assert rate.rate == 100.0

    def test_set_rate_rejects_pkr(self):
        m = MultiCurrencyManager()
        with pytest.raises(ValueError, match="base currency"):
            m.set_rate("PKR", 1.0)

    def test_set_rate_rejects_negative(self):
        m = MultiCurrencyManager()
        with pytest.raises(ValueError, match="positive"):
            m.set_rate("USD", -280.0)

    def test_set_rate_rejects_zero(self):
        m = MultiCurrencyManager()
        with pytest.raises(ValueError, match="positive"):
            m.set_rate("USD", 0)

    def test_set_rate_invalid_code(self):
        m = MultiCurrencyManager()
        with pytest.raises(ValueError, match="Unknown"):
            m.set_rate("INVALID", 280.0)

    def test_get_rate(self, manager):
        rate = manager.get_rate("USD")
        assert rate is not None
        assert rate.rate == 280.50

    def test_get_rate_case_insensitive(self, manager):
        rate = manager.get_rate("usd")
        assert rate is not None

    def test_get_rate_pkr(self, manager):
        rate = manager.get_rate("PKR")
        assert rate.rate == 1.0

    def test_get_rate_nonexistent(self, manager):
        assert manager.get_rate("JPY") is None

    def test_get_all_rates(self, manager):
        rates = manager.get_all_rates()
        assert len(rates) == 4

    def test_currency_count(self, manager):
        assert manager.currency_count == 4

    def test_clear(self, manager):
        manager.clear()
        assert manager.currency_count == 0

    def test_rate_overwrites(self):
        m = MultiCurrencyManager()
        m.set_rate("USD", 280.0)
        m.set_rate("USD", 282.0)
        rate = m.get_rate("USD")
        assert rate.rate == 282.0


class TestCurrencyConversion:
    """Tests for currency conversions"""

    def test_to_pkr(self, manager):
        result = manager.convert(100.0, "USD", "PKR")
        assert result is not None
        assert result.to_amount == 28050.0

    def test_from_pkr(self, manager):
        result = manager.convert(28050.0, "PKR", "USD")
        assert result is not None
        assert abs(result.to_amount - 100.0) < 0.01

    def test_same_currency(self, manager):
        result = manager.convert(100.0, "USD", "USD")
        assert result.to_amount == 100.0
        assert result.rate_used == 1.0

    def test_cross_rate(self, manager):
        """Convert USD to EUR via PKR"""
        result = manager.convert(100.0, "USD", "EUR")
        assert result is not None
        assert result.via_pkr is True
        # 100 USD * 280.50 = 28050 PKR / 310 = ~90.48 EUR
        expected = (100.0 * 280.50) / 310.00
        assert abs(result.to_amount - round(expected, 2)) < 0.01

    def test_cross_rate_reverse(self, manager):
        result = manager.convert(100.0, "EUR", "USD")
        assert result is not None
        assert result.via_pkr is True

    def test_negative_amount(self, manager):
        result = manager.convert(-100.0, "USD", "PKR")
        assert result is None

    def test_zero_amount(self, manager):
        result = manager.convert(0.0, "USD", "PKR")
        assert result is not None
        assert result.to_amount == 0.0

    def test_missing_rate(self):
        m = MultiCurrencyManager()
        result = m.convert(100.0, "USD", "PKR")
        assert result is None

    def test_large_amount(self, manager):
        result = manager.convert(1000000.0, "USD", "PKR")
        assert result is not None
        assert result.to_amount == 280500000.0


class TestCrossRateCalculation:
    """Tests for cross-rate calculation"""

    def test_get_cross_rate(self, manager):
        rate = manager.get_cross_rate("USD", "EUR")
        assert rate is not None
        expected = 280.50 / 310.00
        assert abs(rate - round(expected, 6)) < 0.0001

    def test_cross_rate_inverse(self, manager):
        usd_eur = manager.get_cross_rate("USD", "EUR")
        eur_usd = manager.get_cross_rate("EUR", "USD")
        assert abs(usd_eur * eur_usd - 1.0) < 0.001

    def test_cross_rate_unavailable(self):
        m = MultiCurrencyManager()
        assert m.get_cross_rate("USD", "EUR") is None


class TestRateHistory:
    """Tests for rate history"""

    def test_history_recorded(self):
        m = MultiCurrencyManager()
        m.set_rate("USD", 280.0)
        m.set_rate("USD", 281.0)
        m.set_rate("USD", 282.0)

        history = m.get_rate_history("USD")
        assert len(history) == 3
        assert history[0].rate == 280.0
        assert history[2].rate == 282.0

    def test_history_empty(self, manager):
        history = manager.get_rate_history("JPY")
        assert len(history) == 0


class TestCurrencyValidation:
    """Tests for currency code validation"""

    def test_valid_known(self):
        assert MultiCurrencyManager.is_valid_currency("USD") is True
        assert MultiCurrencyManager.is_valid_currency("EUR") is True
        assert MultiCurrencyManager.is_valid_currency("PKR") is True

    def test_valid_unknown_3letter(self):
        assert MultiCurrencyManager.is_valid_currency("XYZ") is True

    def test_invalid_too_short(self):
        assert MultiCurrencyManager.is_valid_currency("US") is False

    def test_invalid_too_long(self):
        assert MultiCurrencyManager.is_valid_currency("USDX") is False

    def test_invalid_numbers(self):
        assert MultiCurrencyManager.is_valid_currency("123") is False

    def test_case_insensitive(self):
        assert MultiCurrencyManager.is_valid_currency("usd") is True


class TestCurrencyInfo:
    """Tests for currency information"""

    def test_get_info(self):
        info = MultiCurrencyManager.get_currency_info("USD")
        assert info is not None
        assert info["name"] == "US Dollar"
        assert info["symbol"] == "$"

    def test_get_info_unknown(self):
        info = MultiCurrencyManager.get_currency_info("XYZ")
        assert info is None

    def test_supported_currencies_list(self):
        currencies = MultiCurrencyManager.get_supported_currencies()
        assert len(currencies) == len(SUPPORTED_CURRENCIES)
        codes = [c["code"] for c in currencies]
        assert "USD" in codes
        assert "PKR" in codes

    def test_rate_table(self, manager):
        table = manager.get_rate_table()
        assert len(table) == 4
        assert all("code" in entry for entry in table)
        assert all("rate_pkr" in entry for entry in table)


class TestMultipleCurrencyScenarios:
    """Integration tests for real-world scenarios"""

    def test_ten_plus_currencies(self):
        """Acceptance criteria: support 10+ currency pairs"""
        m = MultiCurrencyManager()
        rates = {
            "USD": 280.50, "EUR": 310.00, "GBP": 355.00,
            "AED": 76.40, "SAR": 74.80, "CNY": 38.50,
            "JPY": 1.85, "CAD": 205.00, "AUD": 182.00,
            "CHF": 320.00, "INR": 3.35
        }
        for curr, rate in rates.items():
            m.set_rate(curr, rate)

        assert m.currency_count == 11

        # Cross-rate should work between any pair
        result = m.convert(1000.0, "EUR", "JPY")
        assert result is not None
        assert result.via_pkr is True
