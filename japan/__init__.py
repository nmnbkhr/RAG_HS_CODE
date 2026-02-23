"""Japan Customs HS Code & Duty Calculator package."""

from japan.duty_calculator import JapanDutyCalculator
from japan.tariff_scraper import JapanTariffScraper
from japan.i18n import t

try:
    from japan.llm_search import llm_search, is_llm_available
except ImportError:
    llm_search = None  # type: ignore[assignment]
    is_llm_available = None  # type: ignore[assignment]

__all__ = [
    "JapanDutyCalculator", "JapanTariffScraper", "t",
    "llm_search", "is_llm_available",
]
