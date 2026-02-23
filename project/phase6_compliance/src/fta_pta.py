"""
RAG_HS_CODE - FTA/PTA Preferential Tariff Lookup
Phase 6: Compliance

Pakistan has several Free Trade Agreements (FTA) and Preferential
Trade Agreements (PTA) that provide reduced customs duty rates
for imports from partner countries, subject to Certificate of
Origin (COO) requirements.

Key agreements:
- CPFTA Phase II (China) - most comprehensive
- SAFTA (SAARC countries)
- MPFTA (Malaysia)
- PKSL (Sri Lanka)
- PKIRN (Iran)
- PKINDN (Indonesia)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class TradeAgreement:
    """A trade agreement between Pakistan and partner country/region"""
    code: str                   # Short code (e.g., "CPFTA")
    name: str                   # Full name
    partner: str                # Partner country/region
    sro_reference: str          # Notifying SRO
    coo_required: bool = True   # Certificate of Origin required
    active: bool = True
    notes: str = ""


@dataclass
class PreferentialRate:
    """A preferential tariff rate under a trade agreement"""
    hs_code: str                # 4 or 8 digit HS code
    description: str
    agreement_code: str         # Links to TradeAgreement.code
    preferential_cd_rate: float # Reduced CD rate (%)
    mfn_cd_rate: float          # Normal MFN rate for comparison
    margin_of_preference: float = 0.0  # % reduction from MFN

    @property
    def savings_pct(self) -> float:
        """Percentage point savings vs MFN rate"""
        return round(self.mfn_cd_rate - self.preferential_cd_rate, 2)


# Active trade agreements
TRADE_AGREEMENTS: Dict[str, TradeAgreement] = {
    "CPFTA": TradeAgreement(
        code="CPFTA",
        name="China-Pakistan Free Trade Agreement (Phase II)",
        partner="China",
        sro_reference="SRO 237(I)/2020",
        notes="Phase II effective Jan 2020; covers ~75% of tariff lines"
    ),
    "SAFTA": TradeAgreement(
        code="SAFTA",
        name="South Asian Free Trade Area",
        partner="SAARC (India, Bangladesh, Sri Lanka, Nepal, Bhutan, Maldives, Afghanistan)",
        sro_reference="SRO 659(I)/2006",
        notes="Sensitive lists limit coverage; India on restricted list"
    ),
    "MPFTA": TradeAgreement(
        code="MPFTA",
        name="Malaysia-Pakistan Free Trade Agreement",
        partner="Malaysia",
        sro_reference="SRO 35(I)/2008",
    ),
    "PKSL": TradeAgreement(
        code="PKSL",
        name="Pakistan-Sri Lanka Free Trade Agreement",
        partner="Sri Lanka",
        sro_reference="SRO 574(I)/2005",
    ),
    "PKIRN": TradeAgreement(
        code="PKIRN",
        name="Pakistan-Iran Preferential Trade Agreement",
        partner="Iran",
        sro_reference="SRO 216(I)/2006",
    ),
    "PKINDN": TradeAgreement(
        code="PKINDN",
        name="Pakistan-Indonesia Preferential Trade Agreement",
        partner="Indonesia",
        sro_reference="SRO 864(I)/2013",
    ),
}

# Country to agreements mapping
COUNTRY_TO_AGREEMENTS: Dict[str, List[str]] = {
    "china": ["CPFTA"],
    "malaysia": ["MPFTA"],
    "sri lanka": ["PKSL", "SAFTA"],
    "india": ["SAFTA"],
    "bangladesh": ["SAFTA"],
    "nepal": ["SAFTA"],
    "bhutan": ["SAFTA"],
    "maldives": ["SAFTA"],
    "afghanistan": ["SAFTA"],
    "iran": ["PKIRN"],
    "indonesia": ["PKINDN"],
}

# Sample preferential rates (key items under each agreement)
PREFERENTIAL_RATES: Dict[str, List[PreferentialRate]] = {
    "CPFTA": [
        # Agriculture
        PreferentialRate("0808.1000", "Fresh apples", "CPFTA", 0.0, 20.0, 100.0),
        PreferentialRate("0805.1000", "Oranges, fresh", "CPFTA", 0.0, 20.0, 100.0),
        PreferentialRate("0802.1100", "Almonds in shell", "CPFTA", 5.0, 16.0, 68.75),
        # Textiles
        PreferentialRate("5208.1100", "Plain weave cotton fabric (unbleached)", "CPFTA", 3.0, 11.0, 72.7),
        PreferentialRate("6109.1000", "T-shirts, cotton, knitted", "CPFTA", 7.5, 20.0, 62.5),
        # Electronics
        PreferentialRate("8517.1200", "Telephones for cellular networks", "CPFTA", 0.0, 0.0, 0.0),
        PreferentialRate("8471.3000", "Portable digital computers (laptops)", "CPFTA", 0.0, 0.0, 0.0),
        # Machinery
        PreferentialRate("8431.4300", "Parts of boring/sinking machinery", "CPFTA", 0.0, 5.0, 100.0),
        PreferentialRate("8481.8000", "Taps, cocks, valves", "CPFTA", 5.0, 20.0, 75.0),
        # Chemicals
        PreferentialRate("2903.1100", "Chloromethane", "CPFTA", 0.0, 5.0, 100.0),
    ],
    "SAFTA": [
        PreferentialRate("0713.2000", "Chickpeas (dried)", "SAFTA", 5.0, 11.0, 54.5),
        PreferentialRate("1006.3000", "Semi-milled or wholly milled rice", "SAFTA", 10.0, 20.0, 50.0),
        PreferentialRate("5208.1100", "Plain weave cotton fabric", "SAFTA", 5.0, 11.0, 54.5),
        PreferentialRate("3004.9000", "Medicaments (retail)", "SAFTA", 5.0, 11.0, 54.5),
    ],
    "MPFTA": [
        PreferentialRate("1511.1000", "Crude palm oil", "MPFTA", 10.0, 16.0, 37.5),
        PreferentialRate("1511.9000", "Refined palm oil", "MPFTA", 12.5, 20.0, 37.5),
        PreferentialRate("4001.2100", "Natural rubber (smoked sheets)", "MPFTA", 0.0, 5.0, 100.0),
        PreferentialRate("4011.1000", "New pneumatic tyres for motor cars", "MPFTA", 15.0, 25.0, 40.0),
    ],
    "PKSL": [
        PreferentialRate("0902.1000", "Green tea (unfermented)", "PKSL", 5.0, 11.0, 54.5),
        PreferentialRate("0801.1100", "Desiccated coconut", "PKSL", 0.0, 11.0, 100.0),
    ],
    "PKIRN": [
        PreferentialRate("2709.0000", "Petroleum oils, crude", "PKIRN", 0.0, 5.0, 100.0),
        PreferentialRate("0802.5000", "Pistachios", "PKIRN", 5.0, 16.0, 68.75),
    ],
    "PKINDN": [
        PreferentialRate("1511.1000", "Crude palm oil", "PKINDN", 12.0, 16.0, 25.0),
        PreferentialRate("4001.2100", "Natural rubber", "PKINDN", 0.0, 5.0, 100.0),
    ],
}


def get_agreement(code: str) -> Optional[TradeAgreement]:
    """Get trade agreement by code."""
    return TRADE_AGREEMENTS.get(code.upper())


def get_agreements_for_country(country: str) -> List[TradeAgreement]:
    """
    Get all applicable trade agreements for a country.

    Args:
        country: Country name (case-insensitive)

    Returns:
        List of TradeAgreement objects
    """
    country_lower = country.strip().lower()
    agreement_codes = COUNTRY_TO_AGREEMENTS.get(country_lower, [])
    return [TRADE_AGREEMENTS[code] for code in agreement_codes if code in TRADE_AGREEMENTS]


def get_preferential_rates(hs_code: str, agreement_code: str) -> List[PreferentialRate]:
    """
    Get preferential rates for an HS code under a specific agreement.

    Args:
        hs_code: HS code string
        agreement_code: Agreement code (e.g., "CPFTA")

    Returns:
        List of matching PreferentialRate entries
    """
    if not hs_code or not agreement_code:
        return []

    clean = hs_code.strip().replace(".", "").replace(" ", "")
    heading = clean[:4] if len(clean) >= 4 else clean

    rates = PREFERENTIAL_RATES.get(agreement_code.upper(), [])
    results = []

    for rate in rates:
        rate_clean = rate.hs_code.replace(".", "")
        # Exact match
        if len(clean) >= 8 and rate_clean == clean[:len(rate_clean)]:
            results.append(rate)
        # Heading match
        elif rate_clean[:4] == heading and rate not in results:
            results.append(rate)

    return results


def get_best_rate(hs_code: str, origin_country: str) -> Optional[PreferentialRate]:
    """
    Get the best (lowest) preferential rate for an HS code from a given country.

    Args:
        hs_code: HS code string
        origin_country: Country of origin

    Returns:
        PreferentialRate with lowest rate, or None if no preferential rate exists
    """
    if not hs_code or not origin_country:
        return None

    agreements = get_agreements_for_country(origin_country)
    best = None

    for agreement in agreements:
        rates = get_preferential_rates(hs_code, agreement.code)
        for rate in rates:
            if best is None or rate.preferential_cd_rate < best.preferential_cd_rate:
                best = rate

    return best


def get_all_countries() -> List[str]:
    """Get list of all countries with trade agreements."""
    return sorted([c.title() for c in COUNTRY_TO_AGREEMENTS.keys()])


def get_rate_comparison(hs_code: str) -> List[Dict]:
    """
    Get comparison of all available rates for an HS code across all agreements.

    Args:
        hs_code: HS code string

    Returns:
        List of dicts with agreement name, rate, and savings info
    """
    results = []

    for code, agreement in TRADE_AGREEMENTS.items():
        rates = get_preferential_rates(hs_code, code)
        for rate in rates:
            results.append({
                "agreement": agreement.name,
                "agreement_code": code,
                "partner": agreement.partner,
                "preferential_rate": rate.preferential_cd_rate,
                "mfn_rate": rate.mfn_cd_rate,
                "savings": rate.savings_pct,
                "coo_required": agreement.coo_required,
                "sro": agreement.sro_reference,
            })

    # Sort by preferential rate (lowest first)
    results.sort(key=lambda x: x["preferential_rate"])
    return results
