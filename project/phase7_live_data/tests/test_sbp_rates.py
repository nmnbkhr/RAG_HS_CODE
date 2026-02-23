"""
Phase 7: Live Data Integration - SBP Rate Fetcher Tests
"""

import pytest
from unittest.mock import patch, MagicMock
from sbp_rates import SBPRate, SBPRateFetcher


class TestSBPRate:
    """Tests for SBPRate dataclass"""

    def test_create(self):
        rate = SBPRate(currency="USD", tt_buying=278.00, tt_selling=280.50)
        assert rate.currency == "USD"
        assert rate.source == "SBP"
        assert rate.tt_buying == 278.00
        assert rate.tt_selling == 280.50

    def test_midpoint(self):
        rate = SBPRate(currency="USD", tt_buying=278.00, tt_selling=280.00)
        assert rate.midpoint == 279.0

    def test_midpoint_precision(self):
        rate = SBPRate(currency="EUR", tt_buying=310.50, tt_selling=312.75)
        assert rate.midpoint == 311.625


class TestSBPRateFetcher:
    """Tests for SBPRateFetcher"""

    def test_init_defaults(self):
        fetcher = SBPRateFetcher()
        assert "sbp.org.pk" in fetcher.url
        assert fetcher.timeout == 10

    def test_init_custom_url(self):
        fetcher = SBPRateFetcher(url="https://example.com", timeout=5)
        assert fetcher.url == "https://example.com"
        assert fetcher.timeout == 5

    def test_parse_sbp_page_with_usd(self):
        html = """
        <table>
            <tr><td>USD</td><td>278.50</td><td>280.50</td></tr>
            <tr><td>EUR</td><td>310.00</td><td>312.00</td></tr>
        </table>
        """
        fetcher = SBPRateFetcher()
        rates = fetcher._parse_sbp_page(html)
        assert "USD" in rates
        assert rates["USD"].tt_buying == 278.50
        assert rates["USD"].tt_selling == 280.50

    def test_parse_sbp_page_with_eur(self):
        html = """
        <table>
            <tr><td>USD</td><td>278.50</td><td>280.50</td></tr>
            <tr><td>EUR</td><td>310.00</td><td>312.00</td></tr>
        </table>
        """
        fetcher = SBPRateFetcher()
        rates = fetcher._parse_sbp_page(html)
        assert "EUR" in rates
        assert rates["EUR"].tt_buying == 310.00

    def test_parse_sbp_page_buying_selling_order(self):
        # Ensure min=buying, max=selling
        html = "<tr><td>USD</td><td>280.50</td><td>278.00</td></tr>"
        fetcher = SBPRateFetcher()
        rates = fetcher._parse_sbp_page(html)
        assert "USD" in rates
        assert rates["USD"].tt_buying == 278.00
        assert rates["USD"].tt_selling == 280.50

    def test_parse_sbp_page_usd_validation(self):
        # Rate outside 200-400 range should be rejected
        html = "<tr><td>USD</td><td>50.00</td><td>52.00</td></tr>"
        fetcher = SBPRateFetcher()
        rates = fetcher._parse_sbp_page(html)
        assert "USD" not in rates

    def test_parse_sbp_page_fallback_pattern(self):
        html = "USD exchange rate: 279.50 buying 281.50 selling"
        fetcher = SBPRateFetcher()
        rates = fetcher._parse_sbp_page(html)
        assert "USD" in rates

    def test_parse_sbp_page_dollar_pattern(self):
        html = "Dollar 279.50 281.50"
        fetcher = SBPRateFetcher()
        rates = fetcher._parse_sbp_page(html)
        assert "USD" in rates

    def test_parse_sbp_page_empty_html(self):
        fetcher = SBPRateFetcher()
        rates = fetcher._parse_sbp_page("")
        assert len(rates) == 0
        assert fetcher.last_error == "No rates found in SBP page"

    def test_parse_sbp_page_no_rates(self):
        html = "<table><tr><td>No data available</td></tr></table>"
        fetcher = SBPRateFetcher()
        rates = fetcher._parse_sbp_page(html)
        assert len(rates) == 0

    def test_parse_multiple_currencies(self):
        html = """
        <tr><td>USD</td><td>278.50</td><td>280.50</td></tr>
        <tr><td>EUR</td><td>310.00</td><td>312.00</td></tr>
        <tr><td>GBP</td><td>355.00</td><td>358.00</td></tr>
        <tr><td>AED</td><td>75.00</td><td>76.50</td></tr>
        """
        fetcher = SBPRateFetcher()
        rates = fetcher._parse_sbp_page(html)
        assert len(rates) >= 4
        assert "AED" in rates

    def test_validate_rate_usd_valid(self):
        fetcher = SBPRateFetcher()
        rate = SBPRate(currency="USD", tt_buying=278.0, tt_selling=280.0)
        assert fetcher.validate_rate(rate) is True

    def test_validate_rate_usd_too_low(self):
        fetcher = SBPRateFetcher()
        rate = SBPRate(currency="USD", tt_buying=50.0, tt_selling=52.0)
        assert fetcher.validate_rate(rate) is False

    def test_validate_rate_usd_too_high(self):
        fetcher = SBPRateFetcher()
        rate = SBPRate(currency="USD", tt_buying=450.0, tt_selling=455.0)
        assert fetcher.validate_rate(rate) is False

    def test_validate_rate_non_usd(self):
        fetcher = SBPRateFetcher()
        rate = SBPRate(currency="EUR", tt_buying=310.0, tt_selling=312.0)
        assert fetcher.validate_rate(rate) is True

    def test_validate_rate_non_usd_negative(self):
        fetcher = SBPRateFetcher()
        rate = SBPRate(currency="EUR", tt_buying=-1.0, tt_selling=312.0)
        assert fetcher.validate_rate(rate) is False

    @patch('sbp_rates.requests', None)
    def test_fetch_without_requests_lib(self):
        fetcher = SBPRateFetcher()
        result = fetcher.fetch_usd_rate()
        assert result is None
        assert "not available" in fetcher.last_error

    def test_fetch_rate_delegates_to_fetch_all(self):
        fetcher = SBPRateFetcher()
        fetcher._fetch_all_rates = MagicMock(return_value={
            "USD": SBPRate("USD", 278.0, 280.0),
            "EUR": SBPRate("EUR", 310.0, 312.0),
        })
        result = fetcher.fetch_rate("EUR")
        assert result is not None
        assert result.currency == "EUR"

    def test_fetch_rate_case_insensitive(self):
        fetcher = SBPRateFetcher()
        fetcher._fetch_all_rates = MagicMock(return_value={
            "USD": SBPRate("USD", 278.0, 280.0),
        })
        result = fetcher.fetch_rate("usd")
        assert result is not None

    def test_fetch_rate_not_found(self):
        fetcher = SBPRateFetcher()
        fetcher._fetch_all_rates = MagicMock(return_value={
            "USD": SBPRate("USD", 278.0, 280.0),
        })
        result = fetcher.fetch_rate("JPY")
        assert result is None
