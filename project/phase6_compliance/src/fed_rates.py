"""
RAG_HS_CODE - Federal Excise Duty Rate Lookup
Phase 6: Compliance

FED rate lookup based on Pakistan's First Schedule to the
Federal Excise Act, 2005 (as amended by Finance Act 2024).

FED applies to specific goods on import. The base is typically
CIF + Customs Duty (assessable value) for ad-valorem rates.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum


class FEDRateType(Enum):
    """FED rate calculation type"""
    AD_VALOREM = "ad_valorem"        # Percentage of assessable value
    SPECIFIC = "specific"            # Fixed PKR amount per unit
    RETAIL_PRICE = "retail_price"    # Percentage of retail price


class FEDBasis(Enum):
    """Base for FED calculation"""
    CIF_PLUS_CD = "cif_plus_cd"      # CIF + Customs Duty (most imports)
    RETAIL_PRICE = "retail_price"     # Maximum Retail Price (beverages, tobacco)
    CIF_VALUE = "cif_value"          # CIF value only


@dataclass
class FEDEntry:
    """A single FED rate entry from the First Schedule"""
    hs_heading: str              # 4-digit heading or 8-digit code
    description: str
    rate_pct: float              # Ad-valorem rate (0 if specific)
    rate_type: FEDRateType = FEDRateType.AD_VALOREM
    basis: FEDBasis = FEDBasis.CIF_PLUS_CD
    specific_rate_pkr: float = 0.0  # Per-unit amount if specific
    specific_unit: str = ""         # Unit for specific rate (e.g., "kg", "liter")
    sro_reference: str = ""
    notes: str = ""


# First Schedule data — key FED items for imports
# Reference: Federal Excise Act 2005, First Schedule (Table I)
FED_RATES: Dict[str, FEDEntry] = {
    # Tobacco products (Chapter 24)
    "2402": FEDEntry(
        hs_heading="2402",
        description="Cigars, cheroots, cigarillos and cigarettes",
        rate_pct=65.0,
        rate_type=FEDRateType.RETAIL_PRICE,
        basis=FEDBasis.RETAIL_PRICE,
        notes="65% of retail price; specific rates also apply per tier"
    ),
    "2403": FEDEntry(
        hs_heading="2403",
        description="Other manufactured tobacco and substitutes",
        rate_pct=65.0,
        rate_type=FEDRateType.RETAIL_PRICE,
        basis=FEDBasis.RETAIL_PRICE,
    ),

    # Aerated/sweetened beverages (Chapter 22)
    "2202": FEDEntry(
        hs_heading="2202",
        description="Waters with added sugar/sweetening/flavouring; other non-alcoholic beverages",
        rate_pct=13.0,
        rate_type=FEDRateType.AD_VALOREM,
        basis=FEDBasis.RETAIL_PRICE,
        notes="13% of retail price for aerated beverages"
    ),

    # Cement (Chapter 25)
    "2523": FEDEntry(
        hs_heading="2523",
        description="Portland cement, aluminous cement, slag cement",
        rate_pct=0.0,
        rate_type=FEDRateType.SPECIFIC,
        basis=FEDBasis.CIF_PLUS_CD,
        specific_rate_pkr=2.0,
        specific_unit="kg",
        notes="Rs. 2/kg specific rate"
    ),

    # Vehicles (Chapter 87)
    "8703.2100": FEDEntry(
        hs_heading="8703.2100",
        description="Motor cars - cylinder capacity <= 1000cc",
        rate_pct=2.5,
        rate_type=FEDRateType.AD_VALOREM,
        basis=FEDBasis.CIF_PLUS_CD,
    ),
    "8703.2200": FEDEntry(
        hs_heading="8703.2200",
        description="Motor cars - cylinder capacity 1001-1500cc",
        rate_pct=5.0,
        rate_type=FEDRateType.AD_VALOREM,
        basis=FEDBasis.CIF_PLUS_CD,
    ),
    "8703.2300": FEDEntry(
        hs_heading="8703.2300",
        description="Motor cars - cylinder capacity 1501-1800cc",
        rate_pct=7.5,
        rate_type=FEDRateType.AD_VALOREM,
        basis=FEDBasis.CIF_PLUS_CD,
    ),
    "8703.2400": FEDEntry(
        hs_heading="8703.2400",
        description="Motor cars - cylinder capacity 1801-3000cc",
        rate_pct=10.0,
        rate_type=FEDRateType.AD_VALOREM,
        basis=FEDBasis.CIF_PLUS_CD,
    ),
    "8703.3300": FEDEntry(
        hs_heading="8703.3300",
        description="Motor cars - cylinder capacity > 3000cc (diesel)",
        rate_pct=20.0,
        rate_type=FEDRateType.AD_VALOREM,
        basis=FEDBasis.CIF_PLUS_CD,
    ),

    # Cosmetics/perfumes (Chapter 33)
    "3303": FEDEntry(
        hs_heading="3303",
        description="Perfumes and toilet waters",
        rate_pct=5.0,
        rate_type=FEDRateType.AD_VALOREM,
        basis=FEDBasis.CIF_PLUS_CD,
    ),
    "3304": FEDEntry(
        hs_heading="3304",
        description="Beauty/make-up preparations, skin care preparations",
        rate_pct=5.0,
        rate_type=FEDRateType.AD_VALOREM,
        basis=FEDBasis.CIF_PLUS_CD,
    ),

    # Lubricating oils (Chapter 27)
    "2710.1991": FEDEntry(
        hs_heading="2710.1991",
        description="Lubricating oils",
        rate_pct=5.0,
        rate_type=FEDRateType.AD_VALOREM,
        basis=FEDBasis.CIF_PLUS_CD,
    ),
    "2710.1999": FEDEntry(
        hs_heading="2710.1999",
        description="Other lubricating preparations",
        rate_pct=5.0,
        rate_type=FEDRateType.AD_VALOREM,
        basis=FEDBasis.CIF_PLUS_CD,
    ),

    # Fruit juices (Chapter 20)
    "2009": FEDEntry(
        hs_heading="2009",
        description="Fruit juices and vegetable juices, unfermented",
        rate_pct=13.0,
        rate_type=FEDRateType.AD_VALOREM,
        basis=FEDBasis.RETAIL_PRICE,
        notes="13% of retail price for sweetened juices"
    ),

    # Air conditioning machines (Chapter 84)
    "8415": FEDEntry(
        hs_heading="8415",
        description="Air conditioning machines",
        rate_pct=5.0,
        rate_type=FEDRateType.AD_VALOREM,
        basis=FEDBasis.CIF_PLUS_CD,
    ),
}


def lookup_fed_rate(hs_code: str) -> Optional[FEDEntry]:
    """
    Look up FED rate for an HS code.

    Tries exact match first (8-digit), then heading match (4-digit).

    Args:
        hs_code: HS code string (e.g., "8703.2300" or "87032300")

    Returns:
        FEDEntry if found, None if FED doesn't apply
    """
    if not hs_code:
        return None

    # Normalize: remove dots and spaces
    clean = hs_code.strip().replace(".", "").replace(" ", "")

    # Try exact 8-digit match first
    formatted_8 = f"{clean[:4]}.{clean[4:8]}" if len(clean) >= 8 else None
    if formatted_8 and formatted_8 in FED_RATES:
        return FED_RATES[formatted_8]

    # Try 4-digit heading match
    heading = clean[:4] if len(clean) >= 4 else clean
    if heading in FED_RATES:
        return FED_RATES[heading]

    return None


def get_fed_rate_for_import(hs_code: str) -> float:
    """
    Get the FED ad-valorem rate for import duty calculation.

    Returns 0.0 for specific-rate or retail-price items since those
    can't be calculated with a simple percentage of assessable value.

    Args:
        hs_code: HS code string

    Returns:
        FED rate as percentage (e.g., 5.0 for 5%), or 0.0 if not applicable
    """
    entry = lookup_fed_rate(hs_code)
    if entry is None:
        return 0.0

    # Only return ad-valorem rates that can be applied as CIF+CD percentage
    if entry.rate_type == FEDRateType.AD_VALOREM and entry.basis == FEDBasis.CIF_PLUS_CD:
        return entry.rate_pct

    return 0.0


def get_all_fed_headings() -> List[str]:
    """Get all HS headings/codes that have FED rates."""
    return sorted(FED_RATES.keys())


def get_fed_summary() -> List[Dict]:
    """Get summary of all FED rates for display."""
    return [
        {
            "hs_code": entry.hs_heading,
            "description": entry.description,
            "rate": f"{entry.rate_pct}%" if entry.rate_type != FEDRateType.SPECIFIC
                   else f"Rs. {entry.specific_rate_pkr}/{entry.specific_unit}",
            "type": entry.rate_type.value,
            "basis": entry.basis.value,
        }
        for entry in FED_RATES.values()
    ]
