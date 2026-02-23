"""
Japan simplified tariff rates.
For commercial imports with total CIF < JPY 200,000.
"""

from japan.hs_normalizer import get_chapter, get_heading

SIMPLIFIED_RATES = {
    'wine': {
        'rate': 70, 'type': 'specific', 'per': 'liter',
        'chapters': ['2204'],
        'name_en': 'Wine', 'name_ja': '\u30ef\u30a4\u30f3',
    },
    'spirits': {
        'rate': 20, 'type': 'specific', 'per': 'liter',
        'chapters': ['2208'],
        'name_en': 'Spirits', 'name_ja': '\u84b8\u7559\u9152',
    },
    'sake': {
        'rate': 30, 'type': 'specific', 'per': 'liter',
        'chapters': ['2206'],
        'name_en': 'Sake/Fermented beverages',
        'name_ja': '\u65e5\u672c\u9152\u30fb\u767a\u9175\u98f2\u6599',
    },
    'ketchup_ice': {
        'rate': 0.20, 'type': 'ad_valorem',
        'chapters': ['2103', '2105'],
        'name_en': 'Sauces/Ice cream', 'name_ja': '\u30bd\u30fc\u30b9\u30fb\u30a2\u30a4\u30b9',
    },
    'coffee_tea': {
        'rate': 0.15, 'type': 'ad_valorem',
        'chapters': ['09'],
        'name_en': 'Coffee/Tea/Spices', 'name_ja': '\u30b3\u30fc\u30d2\u30fc\u30fb\u8336\u30fb\u9999\u8f9b\u6599',
    },
    'veg_fruit': {
        'rate': 0.10, 'type': 'ad_valorem',
        'chapters': ['07', '08'],
        'name_en': 'Vegetables/Fruit', 'name_ja': '\u91ce\u83dc\u30fb\u679c\u7269',
    },
    'tableware_toys': {
        'rate': 0.03, 'type': 'ad_valorem',
        'chapters': ['69', '95'],
        'name_en': 'Tableware/Toys', 'name_ja': '\u98df\u5668\u30fb\u304a\u3082\u3061\u3083',
    },
    'rubber_paper': {
        'rate': 0.00, 'type': 'ad_valorem',
        'chapters': ['40', '48'],
        'name_en': 'Rubber/Paper (duty-free)', 'name_ja': '\u30b4\u30e0\u30fb\u7d19\uff08\u7121\u7a0e\uff09',
    },
    'other': {
        'rate': 0.05, 'type': 'ad_valorem',
        'chapters': [],  # Catch-all
        'name_en': 'Other goods', 'name_ja': '\u305d\u306e\u4ed6',
    },
}


def is_eligible(cif_jpy: float) -> bool:
    """Check if CIF value qualifies for simplified tariff (< JPY 200,000)."""
    return cif_jpy < 200_000


def get_simplified_rate(hs_code: str) -> dict:
    """
    Match HS code to simplified tariff category.
    Returns: {'rate': float, 'type': str, 'category': str, 'name_en': str, 'name_ja': str}
    """
    chapter = f"{get_chapter(hs_code):02d}"
    heading = get_heading(hs_code)

    for category, info in SIMPLIFIED_RATES.items():
        if category == 'other':
            continue  # Check catch-all last
        for ch in info['chapters']:
            if heading.startswith(ch) or chapter == ch:
                return {
                    'rate': info['rate'],
                    'type': info['type'],
                    'category': category,
                    'name_en': info['name_en'],
                    'name_ja': info['name_ja'],
                }

    # Catch-all
    other = SIMPLIFIED_RATES['other']
    return {
        'rate': other['rate'],
        'type': other['type'],
        'category': 'other',
        'name_en': other['name_en'],
        'name_ja': other['name_ja'],
    }
