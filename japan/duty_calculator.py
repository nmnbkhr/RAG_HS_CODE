"""
Japan import duty calculator — full calculation pipeline.

Flow:
  1. CIF_JPY = (FOB + Freight + Insurance) x get_customs_fx(currency)
  2. If simplified and CIF < 200K: apply simplified rate
  3. Else: get_rates → select_rate → apply rate
  4. Excise tax (alcohol/tobacco/petroleum)
  5. Consumption tax: (CIF + duty + excise) x 10% or 8%
  6. Total = CIF + duty + excise + consumption_tax
"""

from japan.tariff_scraper import JapanTariffScraper
from japan.rate_selector import select_rate, RateResult
from japan.exchange_rate import get_customs_fx
from japan.consumption_tax import get_rate as get_consumption_rate, is_food_item
from japan.excise_tax import calc_excise, get_excise_info
from japan.simplified_tariff import is_eligible as simplified_eligible, get_simplified_rate
from japan.hs_normalizer import normalize


class JapanDutyCalculator:
    """Full Japan import duty calculator."""

    def __init__(self):
        self.scraper = JapanTariffScraper()
        self.scraper.load_cache()

    def calculate(
        self,
        hs_code: str,
        country: str,
        fob: float,
        freight: float,
        insurance: float,
        currency: str,
        quantity: float,
        unit: str,
        use_simplified: bool = False,
        manual_fx_rate: float = 0.0,
    ) -> dict:
        """
        Full Japan import duty calculation.

        Args:
            hs_code: HS code (any format — will be normalized)
            country: ISO 2-letter country code (e.g., 'VN')
            fob: FOB value in foreign currency
            freight: freight cost in foreign currency
            insurance: insurance cost in foreign currency
            currency: currency code (e.g., 'USD')
            quantity: quantity of goods
            unit: unit of measure (e.g., 'kg', 'liter')
            use_simplified: if True, try simplified tariff
            manual_fx_rate: if > 0, use this rate instead of auto-fetch

        Returns:
            dict with all calculation details
        """
        normalized = normalize(hs_code)

        # 1. Exchange rate
        if manual_fx_rate > 0:
            fx_rate = manual_fx_rate
            fx_source = 'Manual rate'
        else:
            fx_rate, fx_source = get_customs_fx(currency)

        # 2. CIF calculation
        cif_foreign = fob + freight + insurance
        cif_jpy = cif_foreign * fx_rate

        # 3. Get tariff rates
        rates = self.scraper.get_rates(normalized)
        all_rates = rates if rates else {}

        # 4. Determine duty
        customs_duty = 0.0
        selected_rate = None
        is_simplified = False

        if use_simplified and simplified_eligible(cif_jpy):
            # Simplified tariff
            simp = get_simplified_rate(normalized)
            is_simplified = True
            if simp['type'] == 'ad_valorem':
                customs_duty = cif_jpy * simp['rate']
                selected_rate = RateResult(
                    value=simp['rate'] * 100,
                    rate_type='ad_valorem',
                    agreement='Simplified',
                    duty_type='ad_valorem',
                    per_unit_value=None,
                    per_unit_name=None,
                )
            else:
                # Specific
                customs_duty = quantity * simp['rate']
                selected_rate = RateResult(
                    value=None,
                    rate_type='specific',
                    agreement='Simplified',
                    duty_type='specific',
                    per_unit_value=simp['rate'],
                    per_unit_name=simp.get('per', 'unit'),
                )
        else:
            # Normal tariff
            if rates:
                selected_rate = select_rate(normalized, country, rates)
                if selected_rate.rate_type == 'ad_valorem':
                    customs_duty = cif_jpy * (selected_rate.value / 100.0) if selected_rate.value else 0.0
                elif selected_rate.rate_type == 'specific':
                    per_val = selected_rate.per_unit_value or 0.0
                    customs_duty = quantity * per_val
                elif selected_rate.rate_type == 'combined':
                    ad_val = cif_jpy * (selected_rate.value / 100.0) if selected_rate.value else 0.0
                    per_val = selected_rate.per_unit_value or 0.0
                    specific_val = quantity * per_val
                    customs_duty = ad_val + specific_val
            else:
                # No rates found — duty-free fallback
                selected_rate = RateResult(
                    value=0.0, rate_type='ad_valorem', agreement='Unknown',
                    duty_type='ad_valorem', per_unit_value=None, per_unit_name=None,
                )

        # 5. Excise tax
        excise = calc_excise(normalized, quantity, unit)
        excise_info = get_excise_info(normalized)

        # 6. Consumption tax
        consumption_rate = get_consumption_rate(normalized)
        tax_base = cif_jpy + customs_duty + excise
        consumption_tax = tax_base * consumption_rate

        # 7. Total
        total_landed = cif_jpy + customs_duty + excise + consumption_tax

        # Description from scraper
        desc_en = all_rates.get('desc_en', '') if all_rates else ''
        desc_jp = all_rates.get('desc_jp', '') if all_rates else ''

        return {
            'hs_code': normalized,
            'description_en': desc_en,
            'description_jp': desc_jp,
            'cif_jpy': round(cif_jpy, 0),
            'cif_original': round(cif_foreign, 2),
            'currency': currency.upper(),
            'fx_rate': fx_rate,
            'fx_source': fx_source,
            'selected_rate': selected_rate,
            'customs_duty': round(customs_duty, 0),
            'excise': round(excise, 0),
            'excise_info': excise_info,
            'consumption_tax': round(consumption_tax, 0),
            'consumption_rate': consumption_rate,
            'is_food': is_food_item(normalized),
            'total_landed': round(total_landed, 0),
            'is_simplified': is_simplified,
            'all_rates': all_rates,
            'fob': fob,
            'freight': freight,
            'insurance': insurance,
            'quantity': quantity,
            'unit': unit,
            'country': country,
        }
