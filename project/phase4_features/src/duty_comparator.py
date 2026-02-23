"""
RAG_HS_CODE - Duty Comparison Module
Phase 4: Features

Compare import duties across multiple HS codes side-by-side.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP


@dataclass
class DutyProfile:
    """Duty profile for a single HS code"""
    hs_code: str
    description: str
    customs_duty_rate: float
    sales_tax_rate: float
    income_tax_rate: float
    additional_duty_rate: float = 0.0
    regulatory_duty_rate: float = 0.0
    federal_excise_duty_rate: float = 0.0
    data_source: str = "WEBOC"

    @property
    def total_effective_rates(self) -> float:
        """Approximate effective rate (simplified, not exact due to cascading)"""
        return (self.customs_duty_rate + self.sales_tax_rate +
                self.income_tax_rate + self.additional_duty_rate +
                self.regulatory_duty_rate + self.federal_excise_duty_rate)


@dataclass
class ComparisonItem:
    """Calculated comparison for one HS code"""
    hs_code: str
    description: str
    data_source: str

    # Rates
    customs_duty_rate: float
    sales_tax_rate: float
    income_tax_rate: float
    additional_duty_rate: float
    regulatory_duty_rate: float
    federal_excise_duty_rate: float

    # Calculated amounts (PKR)
    cif_value_pkr: float
    customs_duty_amount: float
    additional_duty_amount: float
    regulatory_duty_amount: float
    federal_excise_duty_amount: float
    sales_tax_base: float
    sales_tax_amount: float
    income_tax_amount: float
    total_duties: float
    total_landed_cost: float
    effective_duty_rate: float

    # Ranking
    rank: int = 0
    is_cheapest: bool = False
    is_most_expensive: bool = False
    difference_from_cheapest: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hs_code": self.hs_code,
            "description": self.description,
            "data_source": self.data_source,
            "rates": {
                "customs_duty": self.customs_duty_rate,
                "sales_tax": self.sales_tax_rate,
                "income_tax": self.income_tax_rate,
                "additional_duty": self.additional_duty_rate,
                "regulatory_duty": self.regulatory_duty_rate,
                "federal_excise_duty": self.federal_excise_duty_rate
            },
            "amounts": {
                "cif_pkr": self.cif_value_pkr,
                "customs_duty": self.customs_duty_amount,
                "additional_duty": self.additional_duty_amount,
                "regulatory_duty": self.regulatory_duty_amount,
                "federal_excise_duty": self.federal_excise_duty_amount,
                "sales_tax_base": self.sales_tax_base,
                "sales_tax": self.sales_tax_amount,
                "income_tax": self.income_tax_amount,
                "total_duties": self.total_duties,
                "total_landed_cost": self.total_landed_cost
            },
            "effective_rate": self.effective_duty_rate,
            "rank": self.rank,
            "is_cheapest": self.is_cheapest,
            "is_most_expensive": self.is_most_expensive,
            "savings_vs_most_expensive": self.difference_from_cheapest
        }


@dataclass
class ComparisonResult:
    """Complete comparison result"""
    comparison_id: str
    timestamp: str

    # Shared input values
    quantity: float
    unit: str
    unit_value: float
    currency: str
    exchange_rate: float
    exchange_rate_source: str
    freight: float
    insurance: float
    other_charges: float

    # Results
    items: List[ComparisonItem] = field(default_factory=list)
    cheapest_code: str = ""
    most_expensive_code: str = ""
    max_savings: float = 0.0

    @property
    def item_count(self) -> int:
        return len(self.items)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "comparison_id": self.comparison_id,
            "timestamp": self.timestamp,
            "inputs": {
                "quantity": self.quantity,
                "unit": self.unit,
                "unit_value": self.unit_value,
                "currency": self.currency,
                "exchange_rate": self.exchange_rate,
                "freight": self.freight,
                "insurance": self.insurance,
                "other_charges": self.other_charges
            },
            "results": [item.to_dict() for item in self.items],
            "summary": {
                "cheapest": self.cheapest_code,
                "most_expensive": self.most_expensive_code,
                "max_savings": self.max_savings,
                "item_count": self.item_count
            }
        }


class DutyComparator:
    """
    Compares import duties across multiple HS codes.

    Uses the same calculation formula as Phase 1 ImportDutyCalculator:
    1. CIF (PKR) = CIF (Foreign) x Exchange Rate
    2. CD = CIF x CD%
    3. AD = CIF x AD%
    4. RD = CIF x RD%
    5. FED = (CIF + CD) x FED%
    6. ST Base = CIF + CD + AD + RD + FED
    7. ST = ST Base x ST%
    8. IT = CIF x IT%
    9. Total = CD + AD + RD + FED + ST + IT
    10. Landed = CIF + Total

    Maximum 5 codes per comparison.
    """

    MAX_CODES = 5

    @classmethod
    def compare(
        cls,
        duty_profiles: List[DutyProfile],
        quantity: float,
        unit: str,
        unit_value: float,
        currency: str,
        exchange_rate: float,
        exchange_rate_source: str = "NBP",
        freight: float = 0.0,
        insurance: float = 0.0,
        other_charges: float = 0.0
    ) -> ComparisonResult:
        """
        Compare duties across multiple HS codes.

        Args:
            duty_profiles: List of DutyProfile objects (max 5)
            quantity: Number of units
            unit: Unit of measure
            unit_value: Value per unit in foreign currency
            currency: Currency code
            exchange_rate: PKR per unit foreign currency
            exchange_rate_source: Rate source
            freight: Freight charges in foreign currency
            insurance: Insurance charges in foreign currency
            other_charges: Other charges in foreign currency

        Returns:
            ComparisonResult with ranked items

        Raises:
            ValueError: If inputs are invalid
        """
        if not duty_profiles:
            raise ValueError("At least one duty profile is required")
        if len(duty_profiles) > cls.MAX_CODES:
            raise ValueError(f"Maximum {cls.MAX_CODES} HS codes can be compared")
        if quantity <= 0:
            raise ValueError("Quantity must be positive")
        if unit_value < 0:
            raise ValueError("Unit value cannot be negative")
        if exchange_rate <= 0:
            raise ValueError("Exchange rate must be positive")

        comparison_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        timestamp = datetime.now().isoformat()

        # Calculate CIF (same for all codes since inputs are shared)
        fob_value = quantity * unit_value
        cif_foreign = fob_value + freight + insurance + other_charges
        cif_pkr = cif_foreign * exchange_rate

        # Calculate duties for each profile
        items = []
        for profile in duty_profiles:
            item = cls._calculate_for_profile(profile, cif_pkr)
            items.append(item)

        # Rank by total landed cost (ascending = cheapest first)
        items.sort(key=lambda x: x.total_landed_cost)

        for rank, item in enumerate(items, start=1):
            item.rank = rank

        # Mark cheapest and most expensive
        if items:
            cheapest = items[0]
            most_expensive = items[-1]

            cheapest.is_cheapest = True
            most_expensive.is_most_expensive = True

            # If only one item, it's both cheapest and most expensive
            if len(items) == 1:
                most_expensive.is_most_expensive = True

            max_savings = most_expensive.total_landed_cost - cheapest.total_landed_cost

            # Calculate difference from cheapest for each
            for item in items:
                item.difference_from_cheapest = round(
                    item.total_landed_cost - cheapest.total_landed_cost, 2
                )
        else:
            max_savings = 0.0

        return ComparisonResult(
            comparison_id=comparison_id,
            timestamp=timestamp,
            quantity=quantity,
            unit=unit,
            unit_value=unit_value,
            currency=currency,
            exchange_rate=exchange_rate,
            exchange_rate_source=exchange_rate_source,
            freight=freight,
            insurance=insurance,
            other_charges=other_charges,
            items=items,
            cheapest_code=items[0].hs_code if items else "",
            most_expensive_code=items[-1].hs_code if items else "",
            max_savings=round(max_savings, 2)
        )

    @classmethod
    def _calculate_for_profile(cls, profile: DutyProfile, cif_pkr: float) -> ComparisonItem:
        """Calculate duties for a single profile."""
        # Use Decimal for precision
        def to_dec(v: float) -> Decimal:
            return Decimal(str(v))

        def to_flt(v: Decimal) -> float:
            return float(v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

        cif = to_dec(cif_pkr)

        cd = cif * to_dec(profile.customs_duty_rate) / Decimal("100")
        ad = cif * to_dec(profile.additional_duty_rate) / Decimal("100")
        rd = cif * to_dec(profile.regulatory_duty_rate) / Decimal("100")
        fed = (cif + cd) * to_dec(profile.federal_excise_duty_rate) / Decimal("100")
        st_base = cif + cd + ad + rd + fed
        st = st_base * to_dec(profile.sales_tax_rate) / Decimal("100")
        it = cif * to_dec(profile.income_tax_rate) / Decimal("100")

        total_duties = cd + ad + rd + fed + st + it
        landed = cif + total_duties
        eff_rate = (total_duties / cif * Decimal("100")) if cif > 0 else Decimal("0")

        return ComparisonItem(
            hs_code=profile.hs_code,
            description=profile.description,
            data_source=profile.data_source,
            customs_duty_rate=profile.customs_duty_rate,
            sales_tax_rate=profile.sales_tax_rate,
            income_tax_rate=profile.income_tax_rate,
            additional_duty_rate=profile.additional_duty_rate,
            regulatory_duty_rate=profile.regulatory_duty_rate,
            federal_excise_duty_rate=profile.federal_excise_duty_rate,
            cif_value_pkr=to_flt(cif),
            customs_duty_amount=to_flt(cd),
            additional_duty_amount=to_flt(ad),
            regulatory_duty_amount=to_flt(rd),
            federal_excise_duty_amount=to_flt(fed),
            sales_tax_base=to_flt(st_base),
            sales_tax_amount=to_flt(st),
            income_tax_amount=to_flt(it),
            total_duties=to_flt(total_duties),
            total_landed_cost=to_flt(landed),
            effective_duty_rate=to_flt(eff_rate)
        )
