"""
Japan tariff rate selector.

Priority (strict order):
  1. EPA rate  (if country has EPA with Japan)
  2. GSP rate  (if country is designated developing country)
  3. WTO rate  (if lower than Temporary and General)
  4. Temporary (if exists, overrides General)
  5. General   (default fallback)
"""

from collections import namedtuple

from japan.epa_database import get_epa_for_country, is_gsp_country
from japan.tariff_scraper import _parse_rate

# Map epa_database agreement names → scraper column names in table#datatable
_EPA_COLUMN_MAP = {
    'CPTPP': 'CPTPP',
    'RCEP': 'RCEP-ASEAN/ANZ',         # default RCEP column
    'Japan-EU': 'EU',
    'Japan-UK': 'UK',
    'Japan-US': 'Japan-US',            # col 29 in scraper
    'Japan-Singapore': 'Singapore',
    'Japan-Mexico': 'Mexico',
    'Japan-Malaysia': 'Malaysia',
    'Japan-Chile': 'Chile',
    'Japan-Thailand': 'Thailand',
    'Japan-Indonesia': 'Indonesia',
    'Japan-Brunei': 'Brunei',
    'Japan-Philippines': 'Philippines',
    'Japan-Switzerland': 'Switzerland',
    'Japan-Vietnam': 'Vietnam',
    'Japan-India': 'India',
    'Japan-Peru': 'Peru',
    'Japan-Australia': 'Australia',
    'Japan-Mongolia': 'Mongolia',
}

# For RCEP, map specific countries to the correct RCEP sub-column
_RCEP_COLUMN_MAP = {
    'CN': 'RCEP-China',
    'KR': 'RCEP-Korea',
}

RateResult = namedtuple('RateResult', [
    'value',            # float — percentage for ad_valorem, None for specific-only
    'rate_type',        # str — 'ad_valorem', 'specific', 'combined'
    'agreement',        # str — 'CPTPP', 'RCEP', 'GSP', 'WTO', 'Temporary', 'General'
    'duty_type',        # str — same as rate_type (kept for display)
    'per_unit_value',   # float | None — yen per unit for specific/combined
    'per_unit_name',    # str | None — unit name for specific/combined
])


def _rate_value(parsed: dict | None) -> float | None:
    """Extract the numeric percentage value from a parsed rate, or None."""
    if parsed is None:
        return None
    if parsed['duty_type'] == 'ad_valorem':
        return parsed['value']
    if parsed['duty_type'] == 'combined':
        return parsed['value']  # The ad-valorem component
    # specific only — no percentage
    return None


def _make_result(parsed: dict, agreement: str) -> RateResult:
    """Create a RateResult from a parsed rate dict."""
    return RateResult(
        value=parsed.get('value'),
        rate_type=parsed['duty_type'],
        agreement=agreement,
        duty_type=parsed['duty_type'],
        per_unit_value=parsed.get('per_unit_value'),
        per_unit_name=parsed.get('per_unit_name'),
    )


def select_rate(hs_code: str, country_of_origin: str, rates: dict) -> RateResult:
    """
    Select the best applicable tariff rate for an import.

    Args:
        hs_code: Normalized 9-digit HS code
        country_of_origin: ISO 2-letter country code (e.g., 'VN', 'DE')
        rates: dict from JapanTariffScraper.get_rates() containing
               general_rate, wto_rate, temporary_rate, gsp_rate,
               and their _parsed counterparts

    Returns:
        RateResult namedtuple
    """
    country = country_of_origin.upper() if country_of_origin else ''

    general_parsed = rates.get('general_parsed') or _parse_rate(rates.get('general_rate', ''))
    wto_parsed = rates.get('wto_parsed') or _parse_rate(rates.get('wto_rate', ''))
    temp_parsed = rates.get('temporary_parsed') or _parse_rate(rates.get('temporary_rate', ''))
    gsp_parsed = rates.get('gsp_parsed') or _parse_rate(rates.get('gsp_rate', ''))

    # 1. EPA rate — if country has an EPA, use the actual EPA column
    epa_name = get_epa_for_country(country) if country else None
    if epa_name:
        epa_rates = rates.get('epa_rates', {})

        # Determine the correct scraper column name
        col_name = _EPA_COLUMN_MAP.get(epa_name, epa_name)

        # For RCEP, check country-specific sub-columns first
        if epa_name == 'RCEP' and country in _RCEP_COLUMN_MAP:
            rcep_col = _RCEP_COLUMN_MAP[country]
            rcep_text = epa_rates.get(rcep_col, '')
            rcep_parsed = _parse_rate(rcep_text) if rcep_text else None
            if rcep_parsed:
                return _make_result(rcep_parsed, epa_name)

        # Try the mapped column name
        epa_rate_text = epa_rates.get(col_name, '')
        epa_parsed = _parse_rate(epa_rate_text) if epa_rate_text else None
        if epa_parsed:
            return _make_result(epa_parsed, epa_name)

        # Also check jp_us_rate for Japan-US agreement
        if epa_name == 'Japan-US':
            jp_us_text = rates.get('jp_us_rate', '')
            jp_us_parsed = _parse_rate(jp_us_text) if jp_us_text else None
            if jp_us_parsed:
                return _make_result(jp_us_parsed, epa_name)

        # Fallback: try WTO rate as EPA proxy
        if wto_parsed:
            return _make_result(wto_parsed, epa_name)

    # 2. GSP rate — if country is GSP beneficiary
    if country and is_gsp_country(country):
        if gsp_parsed:
            return _make_result(gsp_parsed, 'GSP')
        # GSP countries often get WTO rate or better
        if wto_parsed:
            return _make_result(wto_parsed, 'GSP')

    # 3. WTO rate — if lower than Temporary and General
    wto_val = _rate_value(wto_parsed)
    temp_val = _rate_value(temp_parsed)
    general_val = _rate_value(general_parsed)

    # 4. Temporary — overrides General if it exists
    if temp_parsed:
        if wto_parsed and wto_val is not None and temp_val is not None:
            if wto_val < temp_val:
                return _make_result(wto_parsed, 'WTO')
        return _make_result(temp_parsed, 'Temporary')

    # 3 (continued). WTO vs General
    if wto_parsed and general_parsed:
        if wto_val is not None and general_val is not None:
            if wto_val <= general_val:
                return _make_result(wto_parsed, 'WTO')

    # 5. General — default fallback
    if general_parsed:
        return _make_result(general_parsed, 'General')

    # Absolute fallback
    if wto_parsed:
        return _make_result(wto_parsed, 'WTO')

    # Nothing found — free by default
    return RateResult(
        value=0.0, rate_type='ad_valorem', agreement='General',
        duty_type='ad_valorem', per_unit_value=None, per_unit_name=None,
    )
