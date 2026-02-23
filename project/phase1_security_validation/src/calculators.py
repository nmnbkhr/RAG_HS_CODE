"""
RAG_HS_CODE - Verified Calculators Module
Phase 1: Security & Validation

This module provides mathematically verified calculations for:
- Import duty calculations (CIF basis)
- Export proceeds calculations (FOB basis)
- All calculations include validation and audit trail
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, List
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
import json


@dataclass
class DutyRates:
    """Container for duty rates"""
    customs_duty: float = 0.0       # CD %
    sales_tax: float = 0.0          # ST %
    income_tax: float = 0.0         # IT %
    additional_duty: float = 0.0    # AD %
    regulatory_duty: float = 0.0    # RD %
    federal_excise_duty: float = 0.0  # FED %

    def validate(self) -> List[str]:
        """Validate all rates are within bounds (0-100%)"""
        errors = []
        for field_name in ['customs_duty', 'sales_tax', 'income_tax', 'additional_duty',
                           'regulatory_duty', 'federal_excise_duty']:
            rate = getattr(self, field_name)
            if rate < 0:
                errors.append(f"{field_name} cannot be negative")
            if rate > 100:
                errors.append(f"{field_name} cannot exceed 100%")
        return errors

    def to_dict(self) -> dict:
        return {
            'customs_duty_pct': self.customs_duty,
            'sales_tax_pct': self.sales_tax,
            'income_tax_pct': self.income_tax,
            'additional_duty_pct': self.additional_duty,
            'regulatory_duty_pct': self.regulatory_duty,
            'federal_excise_duty_pct': self.federal_excise_duty
        }


@dataclass
class CIFComponents:
    """CIF (Cost, Insurance, Freight) components"""
    fob_value: float              # Free on Board value in foreign currency
    freight: float = 0.0          # Freight charges
    insurance: float = 0.0        # Insurance charges
    other_charges: float = 0.0    # Other charges

    @property
    def total_cif(self) -> float:
        """Calculate total CIF value"""
        return self.fob_value + self.freight + self.insurance + self.other_charges

    def validate(self) -> List[str]:
        """Validate all components are non-negative"""
        errors = []
        if self.fob_value < 0:
            errors.append("FOB value cannot be negative")
        if self.freight < 0:
            errors.append("Freight cannot be negative")
        if self.insurance < 0:
            errors.append("Insurance cannot be negative")
        if self.other_charges < 0:
            errors.append("Other charges cannot be negative")
        return errors


@dataclass
class CalculationResult:
    """
    Complete result of a duty calculation with full audit trail.
    All monetary values are in PKR unless otherwise specified.
    """
    # Input values
    hs_code: str
    quantity: float
    unit_of_measure: str
    unit_value_foreign: float
    currency: str
    exchange_rate: float
    exchange_rate_source: str

    # CIF values
    fob_value_foreign: float
    freight_foreign: float
    insurance_foreign: float
    other_charges_foreign: float
    cif_value_foreign: float
    cif_value_pkr: float

    # Duty rates applied
    customs_duty_rate: float
    sales_tax_rate: float
    income_tax_rate: float
    additional_duty_rate: float
    regulatory_duty_rate: float
    federal_excise_duty_rate: float

    # Calculated duties (PKR)
    customs_duty_amount: float
    additional_duty_amount: float
    regulatory_duty_amount: float
    federal_excise_duty_amount: float
    sales_tax_base: float
    sales_tax_amount: float
    income_tax_amount: float

    # Totals
    total_duties: float
    total_landed_cost: float
    effective_duty_rate: float

    # Audit trail
    calculation_timestamp: str
    calculation_version: str = "1.0"
    validation_passed: bool = True
    validation_errors: List[str] = field(default_factory=list)
    data_source: str = "WEBOC"

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'input': {
                'hs_code': self.hs_code,
                'quantity': self.quantity,
                'unit_of_measure': self.unit_of_measure,
                'unit_value': self.unit_value_foreign,
                'currency': self.currency,
                'exchange_rate': self.exchange_rate,
                'exchange_rate_source': self.exchange_rate_source
            },
            'cif': {
                'fob_value_foreign': self.fob_value_foreign,
                'freight': self.freight_foreign,
                'insurance': self.insurance_foreign,
                'other_charges': self.other_charges_foreign,
                'total_cif_foreign': self.cif_value_foreign,
                'total_cif_pkr': self.cif_value_pkr
            },
            'rates': {
                'customs_duty': self.customs_duty_rate,
                'sales_tax': self.sales_tax_rate,
                'income_tax': self.income_tax_rate,
                'additional_duty': self.additional_duty_rate,
                'regulatory_duty': self.regulatory_duty_rate,
                'federal_excise_duty': self.federal_excise_duty_rate
            },
            'duties': {
                'customs_duty': self.customs_duty_amount,
                'additional_duty': self.additional_duty_amount,
                'regulatory_duty': self.regulatory_duty_amount,
                'federal_excise_duty': self.federal_excise_duty_amount,
                'sales_tax_base': self.sales_tax_base,
                'sales_tax': self.sales_tax_amount,
                'income_tax': self.income_tax_amount,
                'total_duties': self.total_duties
            },
            'totals': {
                'landed_cost': self.total_landed_cost,
                'effective_duty_rate': self.effective_duty_rate
            },
            'audit': {
                'timestamp': self.calculation_timestamp,
                'version': self.calculation_version,
                'validation_passed': self.validation_passed,
                'validation_errors': self.validation_errors,
                'data_source': self.data_source
            }
        }

    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), indent=2)


class ImportDutyCalculator:
    """
    Calculates import duties for Pakistan Customs.

    Formula (per Pakistan Customs):
    1.  CIF Value (PKR) = CIF Value (Foreign) × Exchange Rate
    2.  Customs Duty (CD) = CIF × CD Rate%
    3.  Additional Duty (AD) = CIF × AD Rate%
    4.  Regulatory Duty (RD) = CIF × RD Rate%
    5.  Federal Excise Duty (FED) = (CIF + CD) × FED Rate%
    6.  Sales Tax Base = CIF + CD + AD + RD + FED
    7.  Sales Tax (ST) = Sales Tax Base × ST Rate%
    8.  Income Tax (IT) = CIF × IT Rate% (advance tax)
    9.  Total Duties = CD + AD + RD + FED + ST + IT
    10. Landed Cost = CIF + Total Duties
    """

    CALCULATION_VERSION = "1.1"
    PRECISION = 2  # Decimal places for PKR

    @classmethod
    def calculate(
        cls,
        hs_code: str,
        quantity: float,
        unit_of_measure: str,
        unit_value: float,
        currency: str,
        exchange_rate: float,
        exchange_rate_source: str,
        duty_rates: DutyRates,
        cif_components: CIFComponents,
        data_source: str = "WEBOC"
    ) -> CalculationResult:
        """
        Perform complete import duty calculation with validation.

        Args:
            hs_code: Validated HS code (XXXX.XXXX format)
            quantity: Number of units
            unit_of_measure: Unit (kg, units, etc.)
            unit_value: Value per unit in foreign currency
            currency: Currency code (USD, EUR, etc.)
            exchange_rate: PKR per unit of foreign currency
            exchange_rate_source: Source of exchange rate (NBP, manual, etc.)
            duty_rates: DutyRates object with all applicable rates
            cif_components: CIF breakdown (FOB, freight, insurance, other)
            data_source: Source of duty rates (WEBOC, PCT Database)

        Returns:
            CalculationResult with full breakdown and audit trail
        """
        # Collect validation errors
        errors = []
        errors.extend(duty_rates.validate())
        errors.extend(cif_components.validate())

        if quantity <= 0:
            errors.append("Quantity must be positive")
        if unit_value < 0:
            errors.append("Unit value cannot be negative")
        if exchange_rate <= 0:
            errors.append("Exchange rate must be positive")

        # Use Decimal for precise calculations
        def to_decimal(value: float) -> Decimal:
            return Decimal(str(value))

        def to_float(value: Decimal) -> float:
            return float(value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))

        # Step 1: Calculate FOB value
        fob_value_foreign = to_decimal(unit_value) * to_decimal(quantity)

        # Step 2: Calculate CIF value in foreign currency
        cif_foreign = (
            fob_value_foreign +
            to_decimal(cif_components.freight) +
            to_decimal(cif_components.insurance) +
            to_decimal(cif_components.other_charges)
        )

        # Step 3: Convert CIF to PKR
        rate = to_decimal(exchange_rate)
        cif_pkr = cif_foreign * rate

        # Step 4: Calculate duties
        cd_rate = to_decimal(duty_rates.customs_duty) / Decimal('100')
        ad_rate = to_decimal(duty_rates.additional_duty) / Decimal('100')
        rd_rate = to_decimal(duty_rates.regulatory_duty) / Decimal('100')
        fed_rate = to_decimal(duty_rates.federal_excise_duty) / Decimal('100')
        st_rate = to_decimal(duty_rates.sales_tax) / Decimal('100')
        it_rate = to_decimal(duty_rates.income_tax) / Decimal('100')

        # Customs Duty on CIF
        customs_duty = cif_pkr * cd_rate

        # Additional Duty on CIF
        additional_duty = cif_pkr * ad_rate

        # Regulatory Duty on CIF
        regulatory_duty = cif_pkr * rd_rate

        # Federal Excise Duty on (CIF + CD)
        fed_base = cif_pkr + customs_duty
        federal_excise_duty = fed_base * fed_rate

        # Sales Tax Base = CIF + CD + AD + RD + FED
        st_base = cif_pkr + customs_duty + additional_duty + regulatory_duty + federal_excise_duty

        # Sales Tax on base
        sales_tax = st_base * st_rate

        # Income Tax (advance) on CIF value
        income_tax = cif_pkr * it_rate

        # Total duties
        total_duties = (customs_duty + additional_duty + regulatory_duty +
                        federal_excise_duty + sales_tax + income_tax)

        # Landed cost
        landed_cost = cif_pkr + total_duties

        # Effective duty rate
        effective_rate = (total_duties / cif_pkr * Decimal('100')) if cif_pkr > 0 else Decimal('0')

        # Build result
        result = CalculationResult(
            # Inputs
            hs_code=hs_code,
            quantity=quantity,
            unit_of_measure=unit_of_measure,
            unit_value_foreign=unit_value,
            currency=currency,
            exchange_rate=exchange_rate,
            exchange_rate_source=exchange_rate_source,

            # CIF values
            fob_value_foreign=to_float(fob_value_foreign),
            freight_foreign=cif_components.freight,
            insurance_foreign=cif_components.insurance,
            other_charges_foreign=cif_components.other_charges,
            cif_value_foreign=to_float(cif_foreign),
            cif_value_pkr=to_float(cif_pkr),

            # Rates
            customs_duty_rate=duty_rates.customs_duty,
            sales_tax_rate=duty_rates.sales_tax,
            income_tax_rate=duty_rates.income_tax,
            additional_duty_rate=duty_rates.additional_duty,
            regulatory_duty_rate=duty_rates.regulatory_duty,
            federal_excise_duty_rate=duty_rates.federal_excise_duty,

            # Calculated duties
            customs_duty_amount=to_float(customs_duty),
            additional_duty_amount=to_float(additional_duty),
            regulatory_duty_amount=to_float(regulatory_duty),
            federal_excise_duty_amount=to_float(federal_excise_duty),
            sales_tax_base=to_float(st_base),
            sales_tax_amount=to_float(sales_tax),
            income_tax_amount=to_float(income_tax),

            # Totals
            total_duties=to_float(total_duties),
            total_landed_cost=to_float(landed_cost),
            effective_duty_rate=to_float(effective_rate),

            # Audit
            calculation_timestamp=datetime.now().isoformat(),
            calculation_version=cls.CALCULATION_VERSION,
            validation_passed=len(errors) == 0,
            validation_errors=errors,
            data_source=data_source
        )

        return result

    @classmethod
    def verify_calculation(cls, result: CalculationResult) -> Dict[str, bool]:
        """
        Verify a calculation result by recalculating and comparing.

        Returns:
            Dictionary of verification checks with pass/fail status
        """
        tolerance = Decimal('0.01')  # 1 paisa tolerance

        def approx_equal(a: float, b: float) -> bool:
            return abs(Decimal(str(a)) - Decimal(str(b))) <= tolerance

        checks = {}

        # Verify CIF calculation
        expected_cif = (
            result.fob_value_foreign +
            result.freight_foreign +
            result.insurance_foreign +
            result.other_charges_foreign
        )
        checks['cif_foreign'] = approx_equal(result.cif_value_foreign, expected_cif)

        # Verify PKR conversion
        expected_pkr = result.cif_value_foreign * result.exchange_rate
        checks['cif_pkr'] = approx_equal(result.cif_value_pkr, expected_pkr)

        # Verify customs duty
        expected_cd = result.cif_value_pkr * (result.customs_duty_rate / 100)
        checks['customs_duty'] = approx_equal(result.customs_duty_amount, expected_cd)

        # Verify FED (Federal Excise Duty on CIF + CD)
        expected_fed = (result.cif_value_pkr + result.customs_duty_amount) * (result.federal_excise_duty_rate / 100)
        checks['federal_excise_duty'] = approx_equal(result.federal_excise_duty_amount, expected_fed)

        # Verify sales tax base (CIF + CD + AD + RD + FED)
        expected_st_base = (
            result.cif_value_pkr +
            result.customs_duty_amount +
            result.additional_duty_amount +
            result.regulatory_duty_amount +
            result.federal_excise_duty_amount
        )
        checks['sales_tax_base'] = approx_equal(result.sales_tax_base, expected_st_base)

        # Verify sales tax
        expected_st = result.sales_tax_base * (result.sales_tax_rate / 100)
        checks['sales_tax'] = approx_equal(result.sales_tax_amount, expected_st)

        # Verify income tax
        expected_it = result.cif_value_pkr * (result.income_tax_rate / 100)
        checks['income_tax'] = approx_equal(result.income_tax_amount, expected_it)

        # Verify total duties
        expected_total = (
            result.customs_duty_amount +
            result.additional_duty_amount +
            result.regulatory_duty_amount +
            result.federal_excise_duty_amount +
            result.sales_tax_amount +
            result.income_tax_amount
        )
        checks['total_duties'] = approx_equal(result.total_duties, expected_total)

        # Verify landed cost
        expected_landed = result.cif_value_pkr + result.total_duties
        checks['landed_cost'] = approx_equal(result.total_landed_cost, expected_landed)

        return checks


@dataclass
class ExportResult:
    """Result of export proceeds calculation"""
    hs_code: str
    quantity: float
    unit_of_measure: str
    fob_per_unit_foreign: float
    currency: str
    total_fob_foreign: float

    exchange_rate: float
    exchange_rate_source: str
    total_fob_pkr: float

    regulatory_duty_rate: float
    regulatory_duty_amount: float
    net_proceeds_pkr: float

    export_scheme: str
    drawback_eligible: bool
    estimated_drawback: float

    calculation_timestamp: str
    validation_passed: bool = True
    validation_errors: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            'input': {
                'hs_code': self.hs_code,
                'quantity': self.quantity,
                'unit': self.unit_of_measure,
                'fob_per_unit': self.fob_per_unit_foreign,
                'currency': self.currency
            },
            'fob': {
                'total_foreign': self.total_fob_foreign,
                'exchange_rate': self.exchange_rate,
                'rate_source': self.exchange_rate_source,
                'total_pkr': self.total_fob_pkr
            },
            'duties': {
                'regulatory_duty_rate': self.regulatory_duty_rate,
                'regulatory_duty_amount': self.regulatory_duty_amount
            },
            'proceeds': {
                'net_pkr': self.net_proceeds_pkr,
                'scheme': self.export_scheme,
                'drawback_eligible': self.drawback_eligible,
                'estimated_drawback': self.estimated_drawback
            },
            'audit': {
                'timestamp': self.calculation_timestamp,
                'validation_passed': self.validation_passed,
                'errors': self.validation_errors
            }
        }


class ExportCalculator:
    """
    Calculates export proceeds for Pakistan.

    Key rules:
    - Pakistan generally has NO export duty
    - Regulatory duty may apply per specific SRO notifications
    - Uses TT Buying rate (bank buys your foreign currency)
    - Drawback may be available under certain schemes
    """

    @classmethod
    def calculate(
        cls,
        hs_code: str,
        quantity: float,
        unit_of_measure: str,
        fob_per_unit: float,
        currency: str,
        exchange_rate: float,
        exchange_rate_source: str,
        regulatory_duty_rate: float = 0.0,
        export_scheme: str = "Normal Export"
    ) -> ExportResult:
        """
        Calculate export proceeds.

        Args:
            hs_code: HS code of export item
            quantity: Number of units
            unit_of_measure: Unit (kg, units, etc.)
            fob_per_unit: FOB value per unit in foreign currency
            currency: Currency code
            exchange_rate: TT Buying rate (PKR per foreign currency)
            exchange_rate_source: Source of rate
            regulatory_duty_rate: If applicable per SRO (usually 0)
            export_scheme: Export scheme for drawback eligibility

        Returns:
            ExportResult with full breakdown
        """
        errors = []
        if quantity <= 0:
            errors.append("Quantity must be positive")
        if fob_per_unit < 0:
            errors.append("FOB value cannot be negative")
        if exchange_rate <= 0:
            errors.append("Exchange rate must be positive")
        if regulatory_duty_rate < 0 or regulatory_duty_rate > 100:
            errors.append("Regulatory duty rate must be 0-100%")

        # Calculate FOB values
        total_fob_foreign = fob_per_unit * quantity
        total_fob_pkr = total_fob_foreign * exchange_rate

        # Calculate regulatory duty if applicable
        regulatory_duty = total_fob_pkr * (regulatory_duty_rate / 100)

        # Net proceeds
        net_proceeds = total_fob_pkr - regulatory_duty

        # Check drawback eligibility
        drawback_schemes = [
            "DTRE (Duty & Tax Remission)",
            "Manufacturing Bond",
            "Export Oriented Unit"
        ]
        drawback_eligible = export_scheme in drawback_schemes

        # Estimate drawback (typically 1-7% of FOB, using 3% as estimate)
        estimated_drawback = total_fob_pkr * 0.03 if drawback_eligible else 0.0

        return ExportResult(
            hs_code=hs_code,
            quantity=quantity,
            unit_of_measure=unit_of_measure,
            fob_per_unit_foreign=fob_per_unit,
            currency=currency,
            total_fob_foreign=round(total_fob_foreign, 2),
            exchange_rate=exchange_rate,
            exchange_rate_source=exchange_rate_source,
            total_fob_pkr=round(total_fob_pkr, 2),
            regulatory_duty_rate=regulatory_duty_rate,
            regulatory_duty_amount=round(regulatory_duty, 2),
            net_proceeds_pkr=round(net_proceeds, 2),
            export_scheme=export_scheme,
            drawback_eligible=drawback_eligible,
            estimated_drawback=round(estimated_drawback, 2),
            calculation_timestamp=datetime.now().isoformat(),
            validation_passed=len(errors) == 0,
            validation_errors=errors
        )


# Test cases for verification
TEST_CASES = [
    {
        "name": "Basic Import - 20% CD",
        "inputs": {
            "hs_code": "0808.1000",
            "quantity": 100,
            "unit_value": 10.0,  # $10/kg
            "currency": "USD",
            "exchange_rate": 280.0,
            "duty_rates": DutyRates(customs_duty=20.0, sales_tax=18.0, income_tax=5.5),
            "cif": CIFComponents(fob_value=1000.0)  # 100 * $10
        },
        "expected": {
            "cif_pkr": 280000.0,
            "customs_duty": 56000.0,  # 280000 * 0.20
            "sales_tax_base": 336000.0,  # 280000 + 56000
            "sales_tax": 60480.0,  # 336000 * 0.18
            "income_tax": 15400.0,  # 280000 * 0.055
        }
    },
    {
        "name": "Zero Duty Item",
        "inputs": {
            "hs_code": "0101.2100",
            "quantity": 1,
            "unit_value": 5000.0,
            "currency": "USD",
            "exchange_rate": 280.0,
            "duty_rates": DutyRates(customs_duty=0.0, sales_tax=18.0, income_tax=5.5),
            "cif": CIFComponents(fob_value=5000.0)
        },
        "expected": {
            "cif_pkr": 1400000.0,
            "customs_duty": 0.0,
            "sales_tax": 252000.0,  # 1400000 * 0.18
            "income_tax": 77000.0,  # 1400000 * 0.055
        }
    }
]


if __name__ == "__main__":
    print("Testing Import Duty Calculator...")

    for test in TEST_CASES:
        print(f"\n  Test: {test['name']}")
        inputs = test['inputs']

        result = ImportDutyCalculator.calculate(
            hs_code=inputs['hs_code'],
            quantity=inputs['quantity'],
            unit_of_measure="kg",
            unit_value=inputs['unit_value'],
            currency=inputs['currency'],
            exchange_rate=inputs['exchange_rate'],
            exchange_rate_source="Test",
            duty_rates=inputs['duty_rates'],
            cif_components=inputs['cif']
        )

        # Verify
        verification = ImportDutyCalculator.verify_calculation(result)
        all_passed = all(verification.values())

        print(f"    CIF (PKR): {result.cif_value_pkr:,.2f}")
        print(f"    Customs Duty: {result.customs_duty_amount:,.2f}")
        print(f"    Sales Tax: {result.sales_tax_amount:,.2f}")
        print(f"    Income Tax: {result.income_tax_amount:,.2f}")
        print(f"    Total Landed: {result.total_landed_cost:,.2f}")
        print(f"    Verification: {'✓ PASSED' if all_passed else '✗ FAILED'}")

        if not all_passed:
            for check, passed in verification.items():
                if not passed:
                    print(f"      ✗ {check} failed")
