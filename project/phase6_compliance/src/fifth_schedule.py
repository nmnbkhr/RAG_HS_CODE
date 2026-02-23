"""
RAG_HS_CODE - Fifth Schedule Concessionary Rate Lookup
Phase 6: Compliance

Pakistan Customs Tariff Fifth Schedule provides concessionary
(reduced) customs duty rates for specific goods, typically to
promote agriculture, industry, IT, and renewable energy sectors.

Reference: Customs Act 1969, Fifth Schedule
SRO 565(I)/2006 and amendments
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class ConcessionEntry:
    """A single Fifth Schedule concessionary rate entry"""
    hs_code: str                    # 4 or 8 digit HS code
    description: str
    concessionary_cd_rate: float    # Reduced CD rate (%)
    mfn_cd_rate: float              # Normal MFN rate for comparison
    part: str                       # Fifth Schedule part (I, II, III, etc.)
    conditions: str = ""            # Conditions for eligibility
    sro_reference: str = "SRO 565(I)/2006"
    sector: str = ""                # Sector category

    @property
    def savings_pct(self) -> float:
        """Percentage savings vs MFN rate"""
        if self.mfn_cd_rate <= 0:
            return 0.0
        return round(self.mfn_cd_rate - self.concessionary_cd_rate, 2)


# Fifth Schedule concessionary rates — key items
# Part I: Import of plant, machinery and equipment for various sectors
# Part II: Import of raw materials for specific industries
FIFTH_SCHEDULE_RATES: Dict[str, ConcessionEntry] = {
    # Agriculture Machinery (Part I) — 0% CD
    "8432.1000": ConcessionEntry(
        hs_code="8432.1000",
        description="Ploughs for agricultural use",
        concessionary_cd_rate=0.0,
        mfn_cd_rate=5.0,
        part="I",
        sector="Agriculture",
        conditions="For bona fide agriculturists; end-use certificate required"
    ),
    "8432.2100": ConcessionEntry(
        hs_code="8432.2100",
        description="Disc harrows for agricultural use",
        concessionary_cd_rate=0.0,
        mfn_cd_rate=5.0,
        part="I",
        sector="Agriculture",
        conditions="For bona fide agriculturists"
    ),
    "8433.5100": ConcessionEntry(
        hs_code="8433.5100",
        description="Combine harvester-threshers",
        concessionary_cd_rate=0.0,
        mfn_cd_rate=5.0,
        part="I",
        sector="Agriculture",
        conditions="For agricultural use"
    ),

    # Dairy Equipment (Part I) — 0% CD
    "8434.1000": ConcessionEntry(
        hs_code="8434.1000",
        description="Milking machines",
        concessionary_cd_rate=0.0,
        mfn_cd_rate=5.0,
        part="I",
        sector="Dairy",
        conditions="For dairy sector"
    ),
    "8434.2000": ConcessionEntry(
        hs_code="8434.2000",
        description="Dairy machinery (processing)",
        concessionary_cd_rate=0.0,
        mfn_cd_rate=5.0,
        part="I",
        sector="Dairy",
        conditions="For dairy processing plants"
    ),

    # IT Hardware (Part I) — 0% CD
    "8471.3000": ConcessionEntry(
        hs_code="8471.3000",
        description="Portable digital automatic data processing machines (laptops)",
        concessionary_cd_rate=0.0,
        mfn_cd_rate=10.0,
        part="I",
        sector="IT",
        conditions="ITA-1 commitment; 0% CD per WTO"
    ),
    "8471.4100": ConcessionEntry(
        hs_code="8471.4100",
        description="Other digital automatic data processing machines (desktops)",
        concessionary_cd_rate=0.0,
        mfn_cd_rate=10.0,
        part="I",
        sector="IT",
    ),
    "8471.8000": ConcessionEntry(
        hs_code="8471.8000",
        description="Other units of automatic data processing machines",
        concessionary_cd_rate=0.0,
        mfn_cd_rate=10.0,
        part="I",
        sector="IT",
    ),

    # Solar / Renewable Energy (Part I) — 0% CD
    "8541.4000": ConcessionEntry(
        hs_code="8541.4000",
        description="Photovoltaic cells / solar panels",
        concessionary_cd_rate=0.0,
        mfn_cd_rate=20.0,
        part="I",
        sector="Renewable Energy",
        conditions="For solar energy generation"
    ),
    "8502.3100": ConcessionEntry(
        hs_code="8502.3100",
        description="Wind-powered electric generating sets",
        concessionary_cd_rate=0.0,
        mfn_cd_rate=5.0,
        part="I",
        sector="Renewable Energy",
    ),

    # Pharmaceutical Raw Materials (Part II) — 3% CD
    "2941.1000": ConcessionEntry(
        hs_code="2941.1000",
        description="Penicillins and derivatives (API)",
        concessionary_cd_rate=3.0,
        mfn_cd_rate=11.0,
        part="II",
        sector="Pharmaceuticals",
        conditions="Active Pharmaceutical Ingredients; DRAP approval"
    ),
    "2941.9000": ConcessionEntry(
        hs_code="2941.9000",
        description="Other antibiotics (API)",
        concessionary_cd_rate=3.0,
        mfn_cd_rate=11.0,
        part="II",
        sector="Pharmaceuticals",
        conditions="Active Pharmaceutical Ingredients; DRAP approval"
    ),
    "3003.1000": ConcessionEntry(
        hs_code="3003.1000",
        description="Medicaments containing penicillins (bulk, not retail)",
        concessionary_cd_rate=3.0,
        mfn_cd_rate=11.0,
        part="II",
        sector="Pharmaceuticals",
    ),

    # Textile Machinery (Part I) — 5% CD
    "8445.1100": ConcessionEntry(
        hs_code="8445.1100",
        description="Carding machines for textile fibres",
        concessionary_cd_rate=5.0,
        mfn_cd_rate=16.0,
        part="I",
        sector="Textile",
        conditions="For textile manufacturing"
    ),
    "8446.1000": ConcessionEntry(
        hs_code="8446.1000",
        description="Weaving machines (looms) for fabrics ≤30cm",
        concessionary_cd_rate=5.0,
        mfn_cd_rate=16.0,
        part="I",
        sector="Textile",
    ),

    # Medical Equipment (Part I) — 0% CD
    "9018.1100": ConcessionEntry(
        hs_code="9018.1100",
        description="Electro-cardiographs",
        concessionary_cd_rate=0.0,
        mfn_cd_rate=11.0,
        part="I",
        sector="Healthcare",
    ),
    "9022.1200": ConcessionEntry(
        hs_code="9022.1200",
        description="Computed tomography (CT) apparatus",
        concessionary_cd_rate=0.0,
        mfn_cd_rate=11.0,
        part="I",
        sector="Healthcare",
    ),
}


def lookup_concession(hs_code: str) -> Optional[ConcessionEntry]:
    """
    Look up Fifth Schedule concessionary rate for an HS code.

    Tries exact 8-digit match first, then heading match.

    Args:
        hs_code: HS code string

    Returns:
        ConcessionEntry if found, None if no concession applies
    """
    if not hs_code:
        return None

    # Normalize
    clean = hs_code.strip().replace(".", "").replace(" ", "")

    # Try exact 8-digit match
    if len(clean) >= 8:
        formatted = f"{clean[:4]}.{clean[4:8]}"
        if formatted in FIFTH_SCHEDULE_RATES:
            return FIFTH_SCHEDULE_RATES[formatted]

    # Try 4-digit heading
    heading = clean[:4] if len(clean) >= 4 else clean
    for code, entry in FIFTH_SCHEDULE_RATES.items():
        entry_clean = code.replace(".", "")
        if entry_clean[:4] == heading:
            return entry

    return None


def get_applicable_concessions(hs_code: str) -> List[ConcessionEntry]:
    """
    Get all applicable concessions for an HS code (exact + heading matches).

    Args:
        hs_code: HS code string

    Returns:
        List of matching ConcessionEntry objects
    """
    if not hs_code:
        return []

    clean = hs_code.strip().replace(".", "").replace(" ", "")
    heading = clean[:4] if len(clean) >= 4 else clean
    results = []

    for code, entry in FIFTH_SCHEDULE_RATES.items():
        entry_clean = code.replace(".", "")
        # Exact match
        if len(clean) >= 8 and entry_clean == clean[:len(entry_clean)]:
            results.append(entry)
        # Heading match
        elif entry_clean[:4] == heading and entry not in results:
            results.append(entry)

    return results


def get_sectors() -> List[str]:
    """Get list of all sectors with Fifth Schedule concessions."""
    sectors = set()
    for entry in FIFTH_SCHEDULE_RATES.values():
        if entry.sector:
            sectors.add(entry.sector)
    return sorted(sectors)


def get_concessions_by_sector(sector: str) -> List[ConcessionEntry]:
    """Get all concessions for a specific sector."""
    return [
        entry for entry in FIFTH_SCHEDULE_RATES.values()
        if entry.sector.lower() == sector.lower()
    ]


def get_concession_summary() -> List[Dict]:
    """Get summary of all Fifth Schedule concessions for display."""
    return [
        {
            "hs_code": entry.hs_code,
            "description": entry.description,
            "concessionary_rate": f"{entry.concessionary_cd_rate}%",
            "mfn_rate": f"{entry.mfn_cd_rate}%",
            "savings": f"{entry.savings_pct}%",
            "sector": entry.sector,
            "part": entry.part,
        }
        for entry in FIFTH_SCHEDULE_RATES.values()
    ]
