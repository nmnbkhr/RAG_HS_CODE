"""
Japan excise (liquor/tobacco/petroleum) tax calculations.
Specific duties per unit, not ad-valorem.
"""

from japan.hs_normalizer import get_heading

EXCISE_RATES = {
    # Chapter 22 — Alcohol
    '2203': {
        'rate': 77.0, 'per': '350ml',
        'per_liters': 220.0,  # 77.0 / 0.35
        'name_en': 'Beer', 'name_ja': '\u30d3\u30fc\u30eb',
    },
    '2204': {
        'rate': 70.0, 'per': 'liter',
        'per_liters': 70.0,
        'name_en': 'Wine', 'name_ja': '\u30ef\u30a4\u30f3',
    },
    '2205': {
        'rate': 70.0, 'per': 'liter',
        'per_liters': 70.0,
        'name_en': 'Vermouth', 'name_ja': '\u30d9\u30eb\u30e2\u30c3\u30c8',
    },
    '2206': {
        'rate': 80.0, 'per': 'liter',
        'per_liters': 80.0,
        'name_en': 'Sake/Other fermented', 'name_ja': '\u65e5\u672c\u9152\u30fb\u305d\u306e\u4ed6',
    },
    '2208': {
        'rate': 200.0, 'per': 'liter',
        'per_liters': 200.0,
        'name_en': 'Spirits', 'name_ja': '\u84b8\u7559\u9152',
    },
    # Chapter 24 — Tobacco
    '2402': {
        'rate': 15244.0, 'per': '1000_sticks',
        'per_liters': None,  # not liquid
        'name_en': 'Cigarettes', 'name_ja': '\u305f\u3070\u3053',
    },
    # Chapter 27 — Petroleum
    '2710': {
        'rate': 53.8, 'per': 'liter',
        'per_liters': 53.8,
        'name_en': 'Gasoline', 'name_ja': '\u30ac\u30bd\u30ea\u30f3',
    },
}

# Unit conversion helpers
_UNIT_TO_LITERS = {
    'l': 1.0, 'liter': 1.0, 'liters': 1.0, 'litre': 1.0, 'litres': 1.0,
    'kl': 1000.0,
    'ml': 0.001,
}


def calc_excise(hs_code: str, quantity: float, unit: str) -> float:
    """
    Calculate excise tax amount in JPY.
    Returns 0.0 if HS code is not subject to excise tax.

    Args:
        hs_code: HS code string
        quantity: number of units
        unit: unit of measure (e.g., 'liter', 'kg', 'units')
    """
    heading = get_heading(hs_code)
    info = EXCISE_RATES.get(heading)
    if not info:
        return 0.0

    rate_per = info['per']

    if rate_per == '1000_sticks':
        # Tobacco: rate is per 1000 sticks
        return (quantity / 1000.0) * info['rate']

    # Liquid — convert unit to liters
    per_liter = info.get('per_liters', info['rate'])
    if per_liter is None:
        return 0.0

    unit_lower = unit.lower().strip()
    liter_factor = _UNIT_TO_LITERS.get(unit_lower)
    if liter_factor:
        liters = quantity * liter_factor
    elif unit_lower in ('kg', 'kgs', 'kilogram'):
        liters = quantity  # Approximate: 1 kg ≈ 1 liter for most liquids
    else:
        liters = quantity  # Assume quantity is already in liters

    return liters * per_liter


def get_excise_info(hs_code: str) -> dict | None:
    """Return excise rate info for display, or None if no excise applies."""
    heading = get_heading(hs_code)
    info = EXCISE_RATES.get(heading)
    if not info:
        return None
    return {
        'heading': heading,
        'rate': info['rate'],
        'per': info['per'],
        'name_en': info['name_en'],
        'name_ja': info['name_ja'],
    }
