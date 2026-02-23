"""
Japan Customs exchange rate fetcher.
Tries exchangerate-api.com, falls back to hardcoded defaults.
Caches in st.session_state for 24 hours when running under Streamlit.
"""

import time

import requests

# Hardcoded fallback rates (JPY per 1 unit of foreign currency)
FALLBACK_RATES = {
    'USD': 150.0,
    'EUR': 162.0,
    'GBP': 190.0,
    'CNY': 20.5,
    'KRW': 0.11,
    'PKR': 0.53,
    'AUD': 96.0,
    'CAD': 108.0,
    'THB': 4.2,
    'SGD': 112.0,
    'INR': 1.78,
    'MYR': 33.0,
    'IDR': 0.0094,
    'PHP': 2.6,
    'VND': 0.006,
    'CHF': 168.0,
    'NZD': 88.0,
}

_SUPPORTED = list(FALLBACK_RATES.keys())

# In-process cache: {currency: (rate, source, timestamp)}
_cache: dict[str, tuple[float, str, float]] = {}
_CACHE_TTL = 86400  # 24 hours


def get_customs_fx(currency: str) -> tuple[float, str]:
    """
    Get JPY per 1 unit of foreign currency.

    Returns: (jpy_per_unit, source_description)
    """
    currency = currency.upper()
    if currency == 'JPY':
        return 1.0, 'JPY (no conversion)'

    # Check in-process cache
    if currency in _cache:
        rate, source, ts = _cache[currency]
        if time.time() - ts < _CACHE_TTL:
            return rate, f"{source} (cached)"

    # Try exchangerate-api.com
    try:
        resp = requests.get(
            f"https://api.exchangerate-api.com/v4/latest/{currency}",
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            jpy_rate = data.get('rates', {}).get('JPY')
            if jpy_rate and jpy_rate > 0:
                source = 'exchangerate-api.com'
                _cache[currency] = (jpy_rate, source, time.time())
                return jpy_rate, source
    except Exception:
        pass

    # Fallback to hardcoded
    rate = FALLBACK_RATES.get(currency)
    if rate:
        return rate, 'Fallback (estimated)'

    # Unknown currency — try inverse via USD
    if currency != 'USD':
        try:
            resp = requests.get(
                f"https://api.exchangerate-api.com/v4/latest/USD",
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                target_per_usd = data.get('rates', {}).get(currency)
                jpy_per_usd = data.get('rates', {}).get('JPY')
                if target_per_usd and jpy_per_usd and target_per_usd > 0:
                    rate = jpy_per_usd / target_per_usd
                    _cache[currency] = (rate, 'exchangerate-api.com (via USD)', time.time())
                    return rate, 'exchangerate-api.com (via USD)'
        except Exception:
            pass

    return 1.0, 'Unknown currency'


def get_supported_currencies() -> list[str]:
    """Return list of supported currency codes."""
    return _SUPPORTED.copy()
