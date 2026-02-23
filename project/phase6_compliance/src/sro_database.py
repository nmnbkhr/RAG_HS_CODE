"""
RAG_HS_CODE - SRO (Statutory Regulatory Order) Database
Phase 6: Compliance

Tracks active SROs that modify duty rates, exemptions, or
regulatory requirements for specific HS codes.

SROs are issued by FBR (Federal Board of Revenue) and published
in the Gazette of Pakistan. They can modify CD, RD, ST, and
other duty components.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Dict, List, Optional
from enum import Enum


class SROType(Enum):
    """Type of SRO modification"""
    EXEMPTION = "exemption"              # Full or partial duty exemption
    RATE_CHANGE = "rate_change"          # Modified duty rate
    ADDITIONAL_DUTY = "additional_duty"  # Additional customs duty (ACD)
    REGULATORY_DUTY = "regulatory_duty"  # Regulatory duty imposition
    CONCESSIONARY = "concessionary"      # Fifth Schedule / concessionary
    PROCEDURE = "procedure"              # Procedural requirement


class AffectedDuty(Enum):
    """Which duty component the SRO affects"""
    CUSTOMS_DUTY = "CD"
    REGULATORY_DUTY = "RD"
    ADDITIONAL_CUSTOMS_DUTY = "ACD"
    SALES_TAX = "ST"
    FEDERAL_EXCISE_DUTY = "FED"
    INCOME_TAX = "IT"
    MULTIPLE = "Multiple"


@dataclass
class SROEntry:
    """A single SRO entry"""
    sro_number: str                 # e.g., "929(I)/2024"
    title: str
    sro_type: SROType
    affected_duty: AffectedDuty
    affected_hs_codes: List[str] = field(default_factory=list)
    rate_change_description: str = ""
    effective_from: Optional[date] = None
    effective_to: Optional[date] = None   # None = still active
    gazette_date: Optional[date] = None
    notes: str = ""

    @property
    def is_active(self) -> bool:
        """Check if SRO is currently active."""
        today = date.today()
        if self.effective_from and today < self.effective_from:
            return False
        if self.effective_to and today > self.effective_to:
            return False
        return True

    @property
    def status(self) -> str:
        if not self.is_active:
            if self.effective_to and date.today() > self.effective_to:
                return "expired"
            return "not_yet_effective"
        return "active"


# Key active SROs affecting import duties
SRO_DATABASE: List[SROEntry] = [
    # Additional Customs Duty (ACD)
    SROEntry(
        sro_number="929(I)/2024",
        title="Additional Customs Duty (ACD) on specified imports",
        sro_type=SROType.ADDITIONAL_DUTY,
        affected_duty=AffectedDuty.ADDITIONAL_CUSTOMS_DUTY,
        affected_hs_codes=["87", "33", "34", "71"],  # Chapters
        rate_change_description="2% ACD on vehicles, cosmetics, jewellery etc.",
        effective_from=date(2024, 6, 30),
        notes="Finance Act 2024; applies to luxury/non-essential imports"
    ),

    # Regulatory Duty on luxury items
    SROEntry(
        sro_number="1035(I)/2023",
        title="Regulatory Duty on luxury and non-essential items",
        sro_type=SROType.REGULATORY_DUTY,
        affected_duty=AffectedDuty.REGULATORY_DUTY,
        affected_hs_codes=[
            "8703", "8711",  # Vehicles, motorcycles
            "3303", "3304",  # Perfumes, cosmetics
            "7113",          # Gold/silver jewelry
            "8517.1200",     # Mobile phones (high-value)
            "6402", "6403", "6404",  # Footwear
        ],
        rate_change_description="RD 5-25% on luxury items; vehicles up to 100%",
        effective_from=date(2023, 9, 1),
        notes="Balance of payments measure"
    ),

    # Fifth Schedule - concessionary rates
    SROEntry(
        sro_number="565(I)/2006",
        title="Fifth Schedule - Concessionary customs duty rates",
        sro_type=SROType.CONCESSIONARY,
        affected_duty=AffectedDuty.CUSTOMS_DUTY,
        affected_hs_codes=[
            "8432", "8433", "8434",  # Agriculture/Dairy machinery
            "8471",                   # IT hardware
            "8541.4000",             # Solar panels
            "2941", "3003",          # Pharma raw materials
            "8445", "8446",          # Textile machinery
            "9018", "9022",          # Medical equipment
        ],
        rate_change_description="0-5% CD for agriculture, IT, solar, pharma, textile machinery",
        effective_from=date(2006, 6, 5),
        notes="Regularly amended; check latest Finance Act updates"
    ),

    # Sales Tax exemptions on essential goods
    SROEntry(
        sro_number="551(I)/2008",
        title="Sales Tax exemption on specified imported goods",
        sro_type=SROType.EXEMPTION,
        affected_duty=AffectedDuty.SALES_TAX,
        affected_hs_codes=[
            "0401", "0402",  # Milk and cream
            "1001",          # Wheat
            "1006",          # Rice (seed quality)
            "3002",          # Vaccines
        ],
        rate_change_description="0% ST on essential food items and medicines",
        effective_from=date(2008, 6, 12),
        notes="Regularly updated via amendments"
    ),

    # FED First Schedule notification
    SROEntry(
        sro_number="655(I)/2007",
        title="Federal Excise Duty - First Schedule notification",
        sro_type=SROType.RATE_CHANGE,
        affected_duty=AffectedDuty.FEDERAL_EXCISE_DUTY,
        affected_hs_codes=[
            "2402", "2403",  # Tobacco
            "2202", "2009",  # Beverages
            "2523",          # Cement
            "8703",          # Vehicles
            "3303", "3304",  # Cosmetics
        ],
        rate_change_description="FED rates per First Schedule: 2.5-65% depending on item",
        effective_from=date(2007, 7, 1),
        notes="Amended annually via Finance Act"
    ),

    # CPFTA Phase II preferential tariff
    SROEntry(
        sro_number="237(I)/2020",
        title="CPFTA Phase II - Preferential tariff rates for Chinese imports",
        sro_type=SROType.RATE_CHANGE,
        affected_duty=AffectedDuty.CUSTOMS_DUTY,
        affected_hs_codes=["0808", "0805", "5208", "6109", "8517", "8471"],
        rate_change_description="0-7.5% preferential CD on imports from China",
        effective_from=date(2020, 1, 1),
        notes="COO required; ~75% tariff lines covered"
    ),

    # Income Tax - import withholding
    SROEntry(
        sro_number="1125(I)/2011",
        title="Income Tax withholding on imports (Section 148)",
        sro_type=SROType.RATE_CHANGE,
        affected_duty=AffectedDuty.INCOME_TAX,
        affected_hs_codes=[],  # Applies broadly
        rate_change_description="5.5% for filers, 8% for non-filers on assessable value",
        effective_from=date(2011, 10, 1),
        notes="Advance tax on imports; adjustable against annual IT liability"
    ),
]


def lookup_sros_for_hs_code(hs_code: str) -> List[SROEntry]:
    """
    Find all active SROs affecting a specific HS code.

    Args:
        hs_code: HS code string

    Returns:
        List of active SROEntry objects that affect this HS code
    """
    if not hs_code:
        return []

    clean = hs_code.strip().replace(".", "").replace(" ", "")
    results = []

    for sro in SRO_DATABASE:
        if not sro.is_active:
            continue

        # Check if this HS code is affected
        for affected_code in sro.affected_hs_codes:
            affected_clean = affected_code.replace(".", "")
            if clean.startswith(affected_clean):
                results.append(sro)
                break

        # SROs with empty affected_hs_codes apply broadly
        if not sro.affected_hs_codes:
            results.append(sro)

    return results


def get_active_sros() -> List[SROEntry]:
    """Get all currently active SROs."""
    return [sro for sro in SRO_DATABASE if sro.is_active]


def get_sros_by_type(sro_type: SROType) -> List[SROEntry]:
    """Get all SROs of a specific type."""
    return [sro for sro in SRO_DATABASE if sro.sro_type == sro_type and sro.is_active]


def get_sros_by_duty(affected_duty: AffectedDuty) -> List[SROEntry]:
    """Get all SROs affecting a specific duty component."""
    return [sro for sro in SRO_DATABASE if sro.affected_duty == affected_duty and sro.is_active]


def get_sro_summary() -> List[Dict]:
    """Get summary of all SROs for display."""
    return [
        {
            "sro_number": sro.sro_number,
            "title": sro.title,
            "type": sro.sro_type.value,
            "duty": sro.affected_duty.value,
            "status": sro.status,
            "description": sro.rate_change_description,
            "effective_from": sro.effective_from.isoformat() if sro.effective_from else None,
        }
        for sro in SRO_DATABASE
    ]


def search_sros(query: str) -> List[SROEntry]:
    """
    Search SROs by number, title, or description.

    Args:
        query: Search query string

    Returns:
        List of matching SROEntry objects
    """
    if not query:
        return []

    query_lower = query.lower()
    results = []

    for sro in SRO_DATABASE:
        if (query_lower in sro.sro_number.lower() or
            query_lower in sro.title.lower() or
            query_lower in sro.rate_change_description.lower() or
            query_lower in sro.notes.lower()):
            results.append(sro)

    return results
