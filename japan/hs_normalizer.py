"""Japan HS code normalizer — 9-digit format XXXX.XX-XXX."""

import re


def normalize(code: str) -> str:
    """
    Normalize a Japan HS code to XXXX.XX-XXX format.

    Accepts: 090121010, 0901.21-010, 0901.21010, 090121-010, 0901.21.010
    Returns: 0901.21-010
    """
    digits = re.sub(r'[^0-9]', '', code.strip())
    if len(digits) < 9:
        digits = digits.ljust(9, '0')
    elif len(digits) > 9:
        digits = digits[:9]
    return f"{digits[:4]}.{digits[4:6]}-{digits[6:9]}"


def is_valid(code: str) -> bool:
    """Check if code can be parsed as a valid Japan 9-digit HS code."""
    digits = re.sub(r'[^0-9]', '', code.strip())
    if len(digits) < 4 or len(digits) > 9:
        return False
    chapter = int(digits[:2])
    return 1 <= chapter <= 97


def get_chapter(code: str) -> int:
    """Extract 2-digit chapter number (01-97) from an HS code."""
    digits = re.sub(r'[^0-9]', '', code.strip())
    if len(digits) < 2:
        return 0
    return int(digits[:2])


def get_heading(code: str) -> str:
    """Extract 4-digit heading (e.g., '0901') from an HS code."""
    digits = re.sub(r'[^0-9]', '', code.strip())
    if len(digits) < 4:
        return digits.ljust(4, '0')
    return digits[:4]
