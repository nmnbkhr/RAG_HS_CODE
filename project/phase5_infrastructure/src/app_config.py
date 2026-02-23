"""
RAG_HS_CODE - Unified Application Configuration
Phase 5: Infrastructure

Single source of truth for all application settings, paths, and constants.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass(frozen=True)
class AppPaths:
    """All application file paths."""
    project_root: str
    pdf_path: str
    faiss_index_path: str
    env_file: str
    log_dir: str
    cache_dir: str

    @classmethod
    def from_root(cls, root: Optional[str] = None) -> "AppPaths":
        """Build paths from a project root directory."""
        if root is None:
            root = str(Path(__file__).resolve().parent.parent.parent.parent)

        root_path = Path(root)
        return cls(
            project_root=str(root_path),
            pdf_path=str(root_path / "pct_latest.pdf"),
            faiss_index_path=os.getenv(
                "FAISS_INDEX_PATH",
                "/mnt/e/rag_hs_codedata/faiss_index"
            ),
            env_file=str(root_path / ".env"),
            log_dir=str(root_path / "logs"),
            cache_dir=str(root_path / "cache"),
        )


@dataclass(frozen=True)
class ExternalURLs:
    """All external service URLs."""
    pdf_source: str = (
        "https://download1.fbr.gov.pk/Docs/"
        "20241021010287106PakistanCustomsTariff-2024-25.pdf"
    )
    weboc_tariff: str = "https://www.weboc.gov.pk/Shared/TariffList.aspx"
    nbp_rates: str = (
        "https://www.nbp.com.pk/RateSheet/index.aspx?view=ExternalLink"
    )
    openai_api: str = "https://api.openai.com/v1"
    tipp_portal: str = "https://tipp.fbr.gov.pk"
    sbp_rates: str = (
        "https://www.sbp.org.pk/ecodata/rates/m2m/m2m-current.asp"
    )


@dataclass(frozen=True)
class CacheSettings:
    """Cache TTL and capacity settings."""
    exchange_rate_ttl_hours: float = 4.0
    weboc_ttl_hours: float = 24.0
    query_ttl_hours: float = 12.0
    tipp_ttl_hours: float = 48.0
    weboc_max_entries: int = 10000
    tipp_max_entries: int = 10000
    query_hot_cache_size: int = 100


@dataclass(frozen=True)
class AppLimits:
    """Application operational limits."""
    max_batch_rows: int = 10000
    max_comparison_codes: int = 5
    max_favorites: int = 500
    max_currency_history: int = 50
    max_calculation_history: int = 100
    request_timeout_seconds: int = 30
    streamlit_port: int = 8502


# Default duty rates for Pakistan Customs
DEFAULT_DUTY_RATES = {
    "customs_duty": 20.0,
    "sales_tax": 18.0,
    "income_tax": 5.5,
    "additional_duty": 0.0,
    "regulatory_duty": 0.0,
}

# Supported currencies (ISO 4217)
SUPPORTED_CURRENCY_CODES = [
    "USD", "EUR", "GBP", "AED", "SAR", "CNY", "JPY", "CAD",
    "AUD", "CHF", "INR", "MYR", "SGD", "KWD", "QAR", "BHD",
    "OMR", "TRY", "AFN", "PKR",
]

# Required environment variables
REQUIRED_ENV_VARS = ["OPENAI_API_KEY"]
OPTIONAL_ENV_VARS = ["FAISS_INDEX_PATH", "STREAMLIT_PORT", "LOG_LEVEL"]


@dataclass
class EnvValidationResult:
    """Result of environment variable validation."""
    valid: bool
    missing: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    values: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "valid": self.valid,
            "missing": self.missing,
            "warnings": self.warnings,
        }


def validate_env_vars(env: Optional[Dict[str, str]] = None) -> EnvValidationResult:
    """
    Validate that all required environment variables are set.

    Args:
        env: Environment dict (defaults to os.environ)

    Returns:
        EnvValidationResult with validation status
    """
    if env is None:
        env = dict(os.environ)

    missing = []
    warnings = []
    values = {}

    for var in REQUIRED_ENV_VARS:
        val = env.get(var, "").strip()
        if not val:
            missing.append(var)
        else:
            values[var] = _mask_value(var, val)

    for var in OPTIONAL_ENV_VARS:
        val = env.get(var, "").strip()
        if not val:
            warnings.append(f"{var} not set (using default)")
        else:
            values[var] = _mask_value(var, val)

    return EnvValidationResult(
        valid=len(missing) == 0,
        missing=missing,
        warnings=warnings,
        values=values,
    )


def _mask_value(key: str, value: str) -> str:
    """Mask sensitive values for display."""
    sensitive_patterns = ["key", "secret", "password", "token"]
    if any(p in key.lower() for p in sensitive_patterns):
        if len(value) > 8:
            return value[:4] + "****" + value[-4:]
        return "****"
    return value


def validate_api_key(key: Optional[str] = None) -> bool:
    """
    Validate that an OpenAI API key has the correct format.

    Args:
        key: API key string (defaults to OPENAI_API_KEY env var)

    Returns:
        True if the key format is valid
    """
    if key is None:
        key = os.getenv("OPENAI_API_KEY", "")

    if not key or not isinstance(key, str):
        return False

    key = key.strip()
    # OpenAI keys start with sk- and are 40+ chars
    return bool(re.match(r'^sk-[a-zA-Z0-9_-]{20,}$', key))


def get_config(root: Optional[str] = None) -> Dict[str, Any]:
    """
    Get the full application configuration as a dictionary.

    Args:
        root: Project root path (auto-detected if None)

    Returns:
        Configuration dictionary
    """
    paths = AppPaths.from_root(root)
    urls = ExternalURLs()
    cache = CacheSettings()
    limits = AppLimits()
    env_result = validate_env_vars()

    return {
        "paths": {
            "project_root": paths.project_root,
            "pdf_path": paths.pdf_path,
            "faiss_index_path": paths.faiss_index_path,
            "env_file": paths.env_file,
            "log_dir": paths.log_dir,
            "cache_dir": paths.cache_dir,
        },
        "urls": {
            "pdf_source": urls.pdf_source,
            "weboc_tariff": urls.weboc_tariff,
            "nbp_rates": urls.nbp_rates,
            "openai_api": urls.openai_api,
            "tipp_portal": urls.tipp_portal,
            "sbp_rates": urls.sbp_rates,
        },
        "cache": {
            "exchange_rate_ttl_hours": cache.exchange_rate_ttl_hours,
            "weboc_ttl_hours": cache.weboc_ttl_hours,
            "query_ttl_hours": cache.query_ttl_hours,
            "tipp_ttl_hours": cache.tipp_ttl_hours,
            "weboc_max_entries": cache.weboc_max_entries,
            "tipp_max_entries": cache.tipp_max_entries,
        },
        "limits": {
            "max_batch_rows": limits.max_batch_rows,
            "max_comparison_codes": limits.max_comparison_codes,
            "max_favorites": limits.max_favorites,
            "streamlit_port": limits.streamlit_port,
        },
        "environment": env_result.to_dict(),
        "default_duty_rates": DEFAULT_DUTY_RATES,
        "supported_currencies": SUPPORTED_CURRENCY_CODES,
    }
