"""
RAG_HS_CODE - SBP Exchange Rate Fetcher
Phase 7: Live Data Integration

Fetches exchange rates from State Bank of Pakistan as a fallback
source when NBP is unavailable. SBP publishes daily exchange rates
at https://www.sbp.org.pk/ecodata/rates/m2m/m2m-current.asp

SBP rates are generally close to NBP TT rates (within ~0.5 PKR).
"""

import re
import time
from dataclasses import dataclass
from typing import Dict, Optional

try:
    import requests
except ImportError:
    requests = None


@dataclass
class SBPRate:
    """Exchange rate from State Bank of Pakistan"""
    currency: str
    tt_buying: float
    tt_selling: float
    source: str = "SBP"
    fetched_at: float = 0.0

    @property
    def midpoint(self) -> float:
        """Average of buying and selling rates."""
        return round((self.tt_buying + self.tt_selling) / 2, 4)


class SBPRateFetcher:
    """
    Fetches exchange rates from State Bank of Pakistan.

    Uses the SBP M2M (Market to Market) rates page as data source.
    This is a backup/fallback when NBP rates are unavailable.

    Features:
    - USD rate fetching (primary use case)
    - Multi-currency support
    - Rate validation (200-400 PKR range for USD)
    - Timeout and error handling
    """

    URL = "https://www.sbp.org.pk/ecodata/rates/m2m/m2m-current.asp"
    TIMEOUT = 10  # seconds
    # PKR/USD validation range
    MIN_RATE = 200.0
    MAX_RATE = 400.0

    def __init__(self, url: Optional[str] = None, timeout: int = TIMEOUT):
        self.url = url or self.URL
        self.timeout = timeout
        self.last_error: Optional[str] = None

    def fetch_usd_rate(self) -> Optional[SBPRate]:
        """
        Fetch USD/PKR exchange rate from SBP.

        Returns:
            SBPRate for USD, or None if fetch fails
        """
        return self.fetch_rate("USD")

    def fetch_rate(self, currency: str) -> Optional[SBPRate]:
        """
        Fetch exchange rate for a specific currency from SBP.

        Args:
            currency: ISO currency code (e.g., "USD", "EUR")

        Returns:
            SBPRate if found, None otherwise
        """
        all_rates = self._fetch_all_rates()
        if not all_rates:
            return None
        return all_rates.get(currency.upper())

    def _fetch_all_rates(self) -> Dict[str, SBPRate]:
        """
        Fetch all exchange rates from SBP page.

        Returns:
            Dict mapping currency code to SBPRate
        """
        if requests is None:
            self.last_error = "requests library not available"
            return {}

        try:
            response = requests.get(self.url, timeout=self.timeout)
            if response.status_code != 200:
                self.last_error = f"HTTP {response.status_code}"
                return {}
            return self._parse_sbp_page(response.text)
        except requests.Timeout:
            self.last_error = "SBP request timed out"
            return {}
        except requests.ConnectionError:
            self.last_error = "SBP connection failed"
            return {}
        except Exception as e:
            self.last_error = f"SBP fetch error: {str(e)}"
            return {}

    def _parse_sbp_page(self, html: str) -> Dict[str, SBPRate]:
        """
        Parse SBP exchange rate HTML page.

        SBP page contains a table with columns like:
        Currency | Symbol | Buying | Selling

        Args:
            html: Raw HTML content

        Returns:
            Dict mapping currency code to SBPRate
        """
        now = time.time()
        rates = {}

        # Currency patterns: look for 3-letter codes followed by numeric values
        # SBP format varies, so we use multiple strategies

        # Strategy 1: Table rows with currency codes and rates
        # Pattern: USD ... buying_rate ... selling_rate
        currency_pattern = re.compile(
            r'(?:>|\s)(USD|EUR|GBP|AED|SAR|CNY|JPY|CAD|AUD|CHF|INR|MYR|SGD|KWD|QAR|BHD|OMR)'
            r'[^0-9]*?(\d{1,4}\.\d{2,4})[^0-9]*?(\d{1,4}\.\d{2,4})',
            re.IGNORECASE
        )

        for match in currency_pattern.finditer(html):
            code = match.group(1).upper()
            val1 = float(match.group(2))
            val2 = float(match.group(3))

            # Determine buying/selling (buying is usually lower)
            buying = min(val1, val2)
            selling = max(val1, val2)

            # Validate USD range
            if code == "USD" and not (self.MIN_RATE <= selling <= self.MAX_RATE):
                continue

            rates[code] = SBPRate(
                currency=code,
                tt_buying=buying,
                tt_selling=selling,
                source="SBP",
                fetched_at=now
            )

        # Strategy 2: Fallback — look for USD-specific patterns
        if "USD" not in rates:
            usd_patterns = [
                r'USD[^\d]*?(\d{3}\.\d{2,4})[^\d]*?(\d{3}\.\d{2,4})',
                r'Dollar[^\d]*?(\d{3}\.\d{2,4})[^\d]*?(\d{3}\.\d{2,4})',
            ]
            for pattern in usd_patterns:
                match = re.search(pattern, html, re.IGNORECASE)
                if match:
                    val1 = float(match.group(1))
                    val2 = float(match.group(2))
                    buying = min(val1, val2)
                    selling = max(val1, val2)
                    if self.MIN_RATE <= selling <= self.MAX_RATE:
                        rates["USD"] = SBPRate(
                            currency="USD",
                            tt_buying=buying,
                            tt_selling=selling,
                            source="SBP",
                            fetched_at=now
                        )
                        break

        if not rates:
            self.last_error = "No rates found in SBP page"

        return rates

    def validate_rate(self, rate: SBPRate) -> bool:
        """Validate that an SBP rate is within expected range."""
        if rate.currency == "USD":
            return self.MIN_RATE <= rate.tt_selling <= self.MAX_RATE
        # For other currencies, just check positive
        return rate.tt_buying > 0 and rate.tt_selling > 0
