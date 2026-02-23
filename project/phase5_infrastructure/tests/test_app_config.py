"""
Phase 5: Infrastructure - App Configuration Tests

Tests for centralized application configuration.
"""

import pytest
import os
from pathlib import Path
from app_config import (
    AppPaths, ExternalURLs, CacheSettings, AppLimits,
    DEFAULT_DUTY_RATES, SUPPORTED_CURRENCY_CODES,
    REQUIRED_ENV_VARS, OPTIONAL_ENV_VARS,
    EnvValidationResult, validate_env_vars, validate_api_key,
    get_config, _mask_value,
)

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)


class TestAppPaths:
    """Tests for AppPaths dataclass"""

    def test_from_root(self):
        paths = AppPaths.from_root(PROJECT_ROOT)
        assert paths.project_root == PROJECT_ROOT
        assert "pct_latest.pdf" in paths.pdf_path

    def test_from_root_default(self):
        paths = AppPaths.from_root()
        assert paths.project_root != ""

    def test_env_file_path(self):
        paths = AppPaths.from_root(PROJECT_ROOT)
        assert paths.env_file.endswith(".env")

    def test_frozen(self):
        paths = AppPaths.from_root(PROJECT_ROOT)
        with pytest.raises(AttributeError):
            paths.project_root = "/tmp"


class TestExternalURLs:
    """Tests for ExternalURLs"""

    def test_defaults(self):
        urls = ExternalURLs()
        assert "fbr.gov.pk" in urls.pdf_source
        assert "weboc.gov.pk" in urls.weboc_tariff
        assert "nbp.com.pk" in urls.nbp_rates
        assert "openai.com" in urls.openai_api

    def test_frozen(self):
        urls = ExternalURLs()
        with pytest.raises(AttributeError):
            urls.weboc_tariff = "http://other.com"


class TestCacheSettings:
    """Tests for CacheSettings"""

    def test_defaults(self):
        cache = CacheSettings()
        assert cache.exchange_rate_ttl_hours == 4.0
        assert cache.weboc_ttl_hours == 24.0
        assert cache.query_ttl_hours == 12.0
        assert cache.weboc_max_entries == 10000

    def test_frozen(self):
        cache = CacheSettings()
        with pytest.raises(AttributeError):
            cache.exchange_rate_ttl_hours = 1.0


class TestAppLimits:
    """Tests for AppLimits"""

    def test_defaults(self):
        limits = AppLimits()
        assert limits.max_batch_rows == 10000
        assert limits.max_comparison_codes == 5
        assert limits.max_favorites == 500
        assert limits.streamlit_port == 8502

    def test_frozen(self):
        limits = AppLimits()
        with pytest.raises(AttributeError):
            limits.max_batch_rows = 999


class TestDefaultConstants:
    """Tests for default constants"""

    def test_duty_rates_keys(self):
        assert "customs_duty" in DEFAULT_DUTY_RATES
        assert "sales_tax" in DEFAULT_DUTY_RATES
        assert "income_tax" in DEFAULT_DUTY_RATES

    def test_duty_rates_values(self):
        assert DEFAULT_DUTY_RATES["customs_duty"] == 20.0
        assert DEFAULT_DUTY_RATES["sales_tax"] == 18.0
        assert DEFAULT_DUTY_RATES["income_tax"] == 5.5

    def test_currencies_list(self):
        assert "USD" in SUPPORTED_CURRENCY_CODES
        assert "EUR" in SUPPORTED_CURRENCY_CODES
        assert "PKR" in SUPPORTED_CURRENCY_CODES
        assert len(SUPPORTED_CURRENCY_CODES) == 20

    def test_required_env_vars(self):
        assert "OPENAI_API_KEY" in REQUIRED_ENV_VARS


class TestMaskValue:
    """Tests for value masking"""

    def test_masks_api_key(self):
        result = _mask_value("OPENAI_API_KEY", "sk-1234567890abcdef")
        assert result.startswith("sk-1")
        assert "****" in result
        assert result.endswith("cdef")

    def test_masks_password(self):
        result = _mask_value("DB_PASSWORD", "mysecretpass")
        assert "****" in result
        assert "mysecretpass" not in result

    def test_masks_short_secret(self):
        result = _mask_value("SECRET_TOKEN", "short")
        assert result == "****"

    def test_no_mask_normal(self):
        result = _mask_value("LOG_LEVEL", "DEBUG")
        assert result == "DEBUG"


class TestValidateEnvVars:
    """Tests for environment variable validation"""

    def test_valid_env(self):
        env = {"OPENAI_API_KEY": "sk-test1234567890"}
        result = validate_env_vars(env)
        assert result.valid is True
        assert len(result.missing) == 0

    def test_missing_required(self):
        env = {}
        result = validate_env_vars(env)
        assert result.valid is False
        assert "OPENAI_API_KEY" in result.missing

    def test_empty_value_treated_as_missing(self):
        env = {"OPENAI_API_KEY": "  "}
        result = validate_env_vars(env)
        assert result.valid is False

    def test_optional_warnings(self):
        env = {"OPENAI_API_KEY": "sk-test"}
        result = validate_env_vars(env)
        assert len(result.warnings) > 0  # Optional vars not set

    def test_to_dict(self):
        env = {"OPENAI_API_KEY": "sk-test1234567890"}
        result = validate_env_vars(env)
        d = result.to_dict()
        assert "valid" in d
        assert "missing" in d
        assert "warnings" in d


class TestValidateApiKey:
    """Tests for API key format validation"""

    def test_valid_key(self):
        assert validate_api_key("sk-abc123def456ghi789jkl012mno345pqr678stu9") is True

    def test_empty_key(self):
        assert validate_api_key("") is False

    def test_none_key(self):
        assert validate_api_key(None) is False

    def test_wrong_prefix(self):
        assert validate_api_key("pk-abc123def456ghi789jkl012mno345pqr678stu9") is False

    def test_too_short(self):
        assert validate_api_key("sk-short") is False

    def test_whitespace_stripped(self):
        assert validate_api_key("  sk-abc123def456ghi789jkl012mno345pqr678stu9  ") is True


class TestGetConfig:
    """Tests for full configuration retrieval"""

    def test_returns_dict(self):
        config = get_config(PROJECT_ROOT)
        assert isinstance(config, dict)

    def test_has_all_sections(self):
        config = get_config(PROJECT_ROOT)
        assert "paths" in config
        assert "urls" in config
        assert "cache" in config
        assert "limits" in config
        assert "environment" in config
        assert "default_duty_rates" in config
        assert "supported_currencies" in config

    def test_paths_section(self):
        config = get_config(PROJECT_ROOT)
        assert "project_root" in config["paths"]
        assert config["paths"]["project_root"] == PROJECT_ROOT

    def test_urls_section(self):
        config = get_config(PROJECT_ROOT)
        assert "weboc_tariff" in config["urls"]

    def test_cache_section(self):
        config = get_config(PROJECT_ROOT)
        assert config["cache"]["exchange_rate_ttl_hours"] == 4.0

    def test_limits_section(self):
        config = get_config(PROJECT_ROOT)
        assert config["limits"]["max_batch_rows"] == 10000
