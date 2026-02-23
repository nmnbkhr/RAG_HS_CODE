"""
Japan consumption tax rates.

Standard rate: 10% (7.8% national + 2.2% local)
Reduced rate:   8% (6.24% national + 1.76% local) — food & non-alcoholic beverages
"""

from japan.hs_normalizer import get_chapter, get_heading

STANDARD_RATE = 0.10
REDUCED_RATE = 0.08

# Alcohol headings within Chapter 22 that get the standard rate
_ALCOHOL_HEADINGS = {'2203', '2204', '2205', '2206', '2207', '2208'}


def get_rate(hs_code: str) -> float:
    """
    Determine the consumption tax rate for an HS code.

    Chapters 01-24 (food/agriculture) → 0.08 (reduced)
    EXCEPT: Chapter 22 subheadings for alcohol (2203-2208) → 0.10
    Everything else → 0.10 (standard)
    """
    chapter = get_chapter(hs_code)
    if chapter < 1:
        return STANDARD_RATE
    if 1 <= chapter <= 24:
        # Check alcohol exception
        if chapter == 22:
            heading = get_heading(hs_code)
            if heading in _ALCOHOL_HEADINGS:
                return STANDARD_RATE
        return REDUCED_RATE
    return STANDARD_RATE


def is_food_item(hs_code: str) -> bool:
    """Check if HS code falls under food/agriculture (chapters 01-24, excl. alcohol)."""
    return get_rate(hs_code) == REDUCED_RATE
