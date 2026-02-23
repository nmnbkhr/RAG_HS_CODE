"""
RAG_HS_CODE - Multi-Currency Rate Manager
Phase 4: Features

Manages exchange rates for multiple currencies with cross-rate calculations.
"""

import re
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field


# ISO 4217 currency codes with names
SUPPORTED_CURRENCIES = {
    "USD": {"name": "US Dollar", "symbol": "$", "region": "Americas"},
    "EUR": {"name": "Euro", "symbol": "\u20ac", "region": "Europe"},
    "GBP": {"name": "British Pound", "symbol": "\u00a3", "region": "Europe"},
    "AED": {"name": "UAE Dirham", "symbol": "AED", "region": "Middle East"},
    "SAR": {"name": "Saudi Riyal", "symbol": "SAR", "region": "Middle East"},
    "CNY": {"name": "Chinese Yuan", "symbol": "\u00a5", "region": "Asia"},
    "JPY": {"name": "Japanese Yen", "symbol": "\u00a5", "region": "Asia"},
    "CAD": {"name": "Canadian Dollar", "symbol": "CA$", "region": "Americas"},
    "AUD": {"name": "Australian Dollar", "symbol": "A$", "region": "Oceania"},
    "CHF": {"name": "Swiss Franc", "symbol": "CHF", "region": "Europe"},
    "INR": {"name": "Indian Rupee", "symbol": "\u20b9", "region": "Asia"},
    "MYR": {"name": "Malaysian Ringgit", "symbol": "RM", "region": "Asia"},
    "SGD": {"name": "Singapore Dollar", "symbol": "S$", "region": "Asia"},
    "KWD": {"name": "Kuwaiti Dinar", "symbol": "KD", "region": "Middle East"},
    "QAR": {"name": "Qatari Riyal", "symbol": "QAR", "region": "Middle East"},
    "BHD": {"name": "Bahraini Dinar", "symbol": "BD", "region": "Middle East"},
    "OMR": {"name": "Omani Rial", "symbol": "OMR", "region": "Middle East"},
    "TRY": {"name": "Turkish Lira", "symbol": "\u20ba", "region": "Europe"},
    "AFN": {"name": "Afghan Afghani", "symbol": "Af", "region": "Asia"},
    "PKR": {"name": "Pakistani Rupee", "symbol": "Rs", "region": "Asia"},
}


@dataclass
class CurrencyRate:
    """Exchange rate for a single currency pair"""
    from_currency: str
    to_currency: str
    rate: float
    source: str
    timestamp: str
    rate_type: str = "mid"  # mid, buying, selling

    @property
    def inverse(self) -> float:
        """Get inverse rate."""
        return 1.0 / self.rate if self.rate > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "from": self.from_currency,
            "to": self.to_currency,
            "rate": self.rate,
            "inverse": round(self.inverse, 6),
            "source": self.source,
            "timestamp": self.timestamp,
            "rate_type": self.rate_type
        }


@dataclass
class ConversionResult:
    """Result of a currency conversion"""
    from_currency: str
    to_currency: str
    from_amount: float
    to_amount: float
    rate_used: float
    rate_source: str
    via_pkr: bool = False  # True if cross-rate via PKR

    def to_dict(self) -> Dict[str, Any]:
        return {
            "from_currency": self.from_currency,
            "from_amount": self.from_amount,
            "to_currency": self.to_currency,
            "to_amount": round(self.to_amount, 2),
            "rate": self.rate_used,
            "source": self.rate_source,
            "cross_rate": self.via_pkr
        }


class MultiCurrencyManager:
    """
    Manages exchange rates for multiple currencies.

    Features:
    - Support for 20+ currencies
    - Cross-rate calculation via PKR base
    - Rate validation
    - Currency code validation (ISO 4217)
    - Conversion with audit trail
    """

    BASE_CURRENCY = "PKR"

    def __init__(self):
        """Initialize with empty rate store."""
        self._rates: Dict[str, CurrencyRate] = {}  # Key: "USD/PKR"
        self._history: Dict[str, List[CurrencyRate]] = {}  # Key: "USD" -> [rates]
        self._max_history = 50

    def set_rate(
        self,
        currency: str,
        pkr_rate: float,
        source: str = "NBP",
        rate_type: str = "mid"
    ) -> CurrencyRate:
        """
        Set the PKR exchange rate for a currency.

        Args:
            currency: ISO 4217 currency code
            pkr_rate: How many PKR per 1 unit of currency
            source: Rate source name
            rate_type: 'mid', 'buying', or 'selling'

        Returns:
            CurrencyRate object

        Raises:
            ValueError: If currency or rate is invalid
        """
        currency = currency.upper()
        if currency == self.BASE_CURRENCY:
            raise ValueError("Cannot set rate for base currency PKR")

        if not self.is_valid_currency(currency):
            raise ValueError(f"Unknown currency code: {currency}")

        if pkr_rate <= 0:
            raise ValueError(f"Rate must be positive, got: {pkr_rate}")

        rate = CurrencyRate(
            from_currency=currency,
            to_currency=self.BASE_CURRENCY,
            rate=pkr_rate,
            source=source,
            timestamp=datetime.now().isoformat(),
            rate_type=rate_type
        )

        key = f"{currency}/{self.BASE_CURRENCY}"
        self._rates[key] = rate

        # Add to history
        if currency not in self._history:
            self._history[currency] = []
        self._history[currency].append(rate)
        if len(self._history[currency]) > self._max_history:
            self._history[currency] = self._history[currency][-self._max_history:]

        return rate

    def get_rate(self, currency: str) -> Optional[CurrencyRate]:
        """
        Get the current PKR rate for a currency.

        Args:
            currency: ISO 4217 currency code

        Returns:
            CurrencyRate or None if not set
        """
        currency = currency.upper()
        if currency == self.BASE_CURRENCY:
            return CurrencyRate(
                from_currency="PKR",
                to_currency="PKR",
                rate=1.0,
                source="Identity",
                timestamp=datetime.now().isoformat()
            )

        key = f"{currency}/{self.BASE_CURRENCY}"
        return self._rates.get(key)

    def get_all_rates(self) -> List[CurrencyRate]:
        """Get all currently set rates."""
        return list(self._rates.values())

    def get_rate_history(self, currency: str) -> List[CurrencyRate]:
        """Get rate history for a currency."""
        return self._history.get(currency.upper(), [])

    def convert(
        self,
        amount: float,
        from_currency: str,
        to_currency: str
    ) -> Optional[ConversionResult]:
        """
        Convert an amount between currencies.

        Uses PKR as the base for cross-rate calculations.

        Args:
            amount: Amount to convert
            from_currency: Source currency code
            to_currency: Target currency code

        Returns:
            ConversionResult or None if rates unavailable
        """
        from_currency = from_currency.upper()
        to_currency = to_currency.upper()

        if amount < 0:
            return None

        # Same currency
        if from_currency == to_currency:
            return ConversionResult(
                from_currency=from_currency,
                to_currency=to_currency,
                from_amount=amount,
                to_amount=amount,
                rate_used=1.0,
                rate_source="Identity"
            )

        # Direct to PKR
        if to_currency == self.BASE_CURRENCY:
            rate = self.get_rate(from_currency)
            if rate is None:
                return None
            return ConversionResult(
                from_currency=from_currency,
                to_currency=to_currency,
                from_amount=amount,
                to_amount=round(amount * rate.rate, 2),
                rate_used=rate.rate,
                rate_source=rate.source
            )

        # Direct from PKR
        if from_currency == self.BASE_CURRENCY:
            rate = self.get_rate(to_currency)
            if rate is None:
                return None
            converted = amount / rate.rate if rate.rate > 0 else 0
            return ConversionResult(
                from_currency=from_currency,
                to_currency=to_currency,
                from_amount=amount,
                to_amount=round(converted, 2),
                rate_used=round(1.0 / rate.rate, 6) if rate.rate > 0 else 0,
                rate_source=rate.source
            )

        # Cross-rate via PKR
        from_rate = self.get_rate(from_currency)
        to_rate = self.get_rate(to_currency)

        if from_rate is None or to_rate is None:
            return None

        # Convert: from_currency -> PKR -> to_currency
        pkr_amount = amount * from_rate.rate
        converted = pkr_amount / to_rate.rate if to_rate.rate > 0 else 0
        cross_rate = from_rate.rate / to_rate.rate if to_rate.rate > 0 else 0

        return ConversionResult(
            from_currency=from_currency,
            to_currency=to_currency,
            from_amount=amount,
            to_amount=round(converted, 2),
            rate_used=round(cross_rate, 6),
            rate_source=f"{from_rate.source} via PKR",
            via_pkr=True
        )

    def get_cross_rate(self, from_currency: str, to_currency: str) -> Optional[float]:
        """
        Calculate cross rate between two currencies.

        Args:
            from_currency: Source currency
            to_currency: Target currency

        Returns:
            Cross rate or None if unavailable
        """
        result = self.convert(1.0, from_currency, to_currency)
        return result.rate_used if result else None

    @staticmethod
    def is_valid_currency(code: str) -> bool:
        """Check if a currency code is valid (ISO 4217 format)."""
        code = code.upper()
        # Check known currencies first
        if code in SUPPORTED_CURRENCIES:
            return True
        # Allow any 3-letter uppercase code as potentially valid
        return bool(re.match(r'^[A-Z]{3}$', code))

    @staticmethod
    def get_currency_info(code: str) -> Optional[Dict[str, str]]:
        """Get currency information."""
        return SUPPORTED_CURRENCIES.get(code.upper())

    @staticmethod
    def get_supported_currencies() -> List[Dict[str, Any]]:
        """Get list of all supported currencies."""
        result = []
        for code, info in SUPPORTED_CURRENCIES.items():
            result.append({
                "code": code,
                "name": info["name"],
                "symbol": info["symbol"],
                "region": info["region"]
            })
        return sorted(result, key=lambda x: x["code"])

    def get_rate_table(self) -> List[Dict[str, Any]]:
        """
        Get a formatted rate table for display.

        Returns:
            List of rate entries for UI display
        """
        table = []
        for rate in self._rates.values():
            info = SUPPORTED_CURRENCIES.get(rate.from_currency, {})
            table.append({
                "code": rate.from_currency,
                "name": info.get("name", rate.from_currency),
                "symbol": info.get("symbol", ""),
                "rate_pkr": rate.rate,
                "rate_type": rate.rate_type,
                "source": rate.source,
                "updated": rate.timestamp
            })
        return sorted(table, key=lambda x: x["code"])

    @property
    def currency_count(self) -> int:
        """Number of currencies with rates set."""
        return len(self._rates)

    def clear(self):
        """Clear all rates."""
        self._rates.clear()
        self._history.clear()
