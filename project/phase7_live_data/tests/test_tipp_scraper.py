"""
Phase 7: Live Data Integration - TIPP Scraper & Cache Tests
"""

import os
import json
import time
import pytest
from tipp_scraper import (
    TIPPResult, TIPPScraper, TIPPCache, normalize_hs_code
)


class TestNormalizeHSCode:
    """Tests for normalize_hs_code()"""

    def test_dotted(self):
        assert normalize_hs_code("0808.1000") == "0808.1000"

    def test_no_dot(self):
        assert normalize_hs_code("08081000") == "0808.1000"

    def test_4_digit(self):
        assert normalize_hs_code("0808") == "0808"

    def test_empty(self):
        assert normalize_hs_code("") == ""

    def test_with_spaces(self):
        assert normalize_hs_code("  0808.1000  ") == "0808.1000"

    def test_with_extra_chars(self):
        assert normalize_hs_code("HS-0808.1000") == "0808.1000"


class TestTIPPResult:
    """Tests for TIPPResult dataclass"""

    def test_create_defaults(self):
        result = TIPPResult(hs_code="0808.1000")
        assert result.mfn_cd_rate == 0.0
        assert result.sales_tax_rate == 17.0
        assert result.source == "TIPP"
        assert result.preferential_rates == {}
        assert result.sro_references == []

    def test_create_full(self):
        result = TIPPResult(
            hs_code="0808.1000",
            description="Fresh apples",
            mfn_cd_rate=20.0,
            sales_tax_rate=18.0,
            additional_duty_rate=7.0,
            regulatory_duty_rate=0.0,
            fed_applicable=False,
            fed_rate=0.0,
            preferential_rates={"CPFTA": 0.0},
            sro_references=["237(I)/2020"],
        )
        assert result.mfn_cd_rate == 20.0
        assert result.preferential_rates["CPFTA"] == 0.0
        assert "237(I)/2020" in result.sro_references

    def test_to_dict(self):
        result = TIPPResult(hs_code="0808.1000", description="Apples", mfn_cd_rate=20.0)
        d = result.to_dict()
        assert d["hs_code"] == "0808.1000"
        assert d["mfn_cd_rate"] == 20.0
        assert d["source"] == "TIPP"
        assert isinstance(d["preferential_rates"], dict)

    def test_from_dict(self):
        d = {
            "hs_code": "0808.1000",
            "description": "Fresh apples",
            "mfn_cd_rate": 20.0,
            "sales_tax_rate": 18.0,
            "preferential_rates": {"CPFTA": 0.0},
            "sro_references": ["237(I)/2020"],
        }
        result = TIPPResult.from_dict(d)
        assert result.hs_code == "0808.1000"
        assert result.mfn_cd_rate == 20.0
        assert result.preferential_rates["CPFTA"] == 0.0

    def test_roundtrip(self):
        original = TIPPResult(
            hs_code="8703.2300", description="Cars", mfn_cd_rate=50.0,
            fed_rate=7.5, fed_applicable=True,
            preferential_rates={"CPFTA": 25.0},
            sro_references=["929(I)/2024"],
            fetched_at=time.time(),
        )
        d = original.to_dict()
        restored = TIPPResult.from_dict(d)
        assert restored.hs_code == original.hs_code
        assert restored.mfn_cd_rate == original.mfn_cd_rate
        assert restored.fed_rate == original.fed_rate
        assert restored.preferential_rates == original.preferential_rates

    def test_from_dict_empty(self):
        result = TIPPResult.from_dict({})
        assert result.hs_code == ""
        assert result.mfn_cd_rate == 0.0


class TestTIPPScraper:
    """Tests for TIPPScraper"""

    def test_init_defaults(self):
        scraper = TIPPScraper()
        assert "tipp.fbr.gov.pk" in scraper.base_url
        assert scraper.timeout == 15

    def test_init_custom(self):
        scraper = TIPPScraper(base_url="https://example.com", timeout=5)
        assert scraper.base_url == "https://example.com"

    def test_search_empty_code(self):
        scraper = TIPPScraper()
        result = scraper.search("")
        assert result is None
        assert "Empty" in scraper.last_error

    def test_search_short_code(self):
        scraper = TIPPScraper()
        result = scraper.search("08")
        assert result is None
        assert "too short" in scraper.last_error

    def test_parse_regex_customs_duty(self):
        html = """
        Customs Duty: 20%
        Sales Tax: 18%
        Additional Customs Duty: 7%
        Federal Excise: 5%
        Description: Fresh apples
        SRO 237(I)/2020
        CPFTA 0%
        """
        scraper = TIPPScraper()
        result = TIPPResult(hs_code="0808.1000", fetched_at=time.time())
        parsed = scraper._parse_with_regex(html, result)
        assert parsed is not None
        assert parsed.mfn_cd_rate == 20.0
        assert parsed.sales_tax_rate == 18.0
        assert parsed.additional_duty_rate == 7.0
        assert parsed.fed_rate == 5.0
        assert parsed.fed_applicable is True

    def test_parse_regex_sro_references(self):
        html = "Description: Fresh apples. Customs Duty: 20%. SRO 929(I)/2024 and S.R.O. 237(I)/2020 apply."
        scraper = TIPPScraper()
        result = TIPPResult(hs_code="0808.1000", fetched_at=time.time())
        parsed = scraper._parse_with_regex(html, result)
        assert parsed is not None
        assert "929(I)/2024" in parsed.sro_references
        assert "237(I)/2020" in parsed.sro_references

    def test_parse_regex_preferential_rates(self):
        html = "CPFTA: 0% and SAFTA: 5%"
        scraper = TIPPScraper()
        result = TIPPResult(hs_code="0808.1000", description="Test", fetched_at=time.time())
        parsed = scraper._parse_with_regex(html, result)
        assert parsed.preferential_rates.get("CPFTA") == 0.0
        assert parsed.preferential_rates.get("SAFTA") == 5.0

    def test_parse_regex_no_data(self):
        html = "<html><body>No tariff data here</body></html>"
        scraper = TIPPScraper()
        result = TIPPResult(hs_code="0808.1000", fetched_at=time.time())
        parsed = scraper._parse_with_regex(html, result)
        assert parsed is None

    def test_validate_result_valid(self):
        scraper = TIPPScraper()
        result = TIPPResult(hs_code="0808.1000", mfn_cd_rate=20.0, sales_tax_rate=18.0)
        assert scraper.validate_result(result) is True

    def test_validate_result_no_hs_code(self):
        scraper = TIPPScraper()
        result = TIPPResult(hs_code="")
        assert scraper.validate_result(result) is False

    def test_validate_result_invalid_cd_rate(self):
        scraper = TIPPScraper()
        result = TIPPResult(hs_code="0808.1000", mfn_cd_rate=150.0)
        assert scraper.validate_result(result) is False

    def test_validate_result_negative_st(self):
        scraper = TIPPScraper()
        result = TIPPResult(hs_code="0808.1000", sales_tax_rate=-5.0)
        assert scraper.validate_result(result) is False


class TestTIPPCache:
    """Tests for TIPPCache"""

    def test_init_creates_db(self, tmp_db_dir):
        db_path = os.path.join(tmp_db_dir, "tipp.db")
        cache = TIPPCache(db_path=db_path)
        assert os.path.exists(db_path)

    def test_put_and_get(self, tmp_db_dir):
        db_path = os.path.join(tmp_db_dir, "tipp.db")
        cache = TIPPCache(db_path=db_path)
        result = TIPPResult(hs_code="0808.1000", description="Apples", mfn_cd_rate=20.0, fetched_at=time.time())
        cache.put("0808.1000", result)
        cached = cache.get("0808.1000")
        assert cached is not None
        assert cached.hs_code == "0808.1000"
        assert cached.mfn_cd_rate == 20.0

    def test_get_miss(self, tmp_db_dir):
        db_path = os.path.join(tmp_db_dir, "tipp.db")
        cache = TIPPCache(db_path=db_path)
        assert cache.get("9999.9999") is None

    def test_get_empty_code(self, tmp_db_dir):
        db_path = os.path.join(tmp_db_dir, "tipp.db")
        cache = TIPPCache(db_path=db_path)
        assert cache.get("") is None

    def test_ttl_expiry(self, tmp_db_dir):
        db_path = os.path.join(tmp_db_dir, "tipp.db")
        cache = TIPPCache(db_path=db_path, ttl=1)  # 1 second TTL
        result = TIPPResult(hs_code="0808.1000", mfn_cd_rate=20.0, fetched_at=time.time())
        cache.put("0808.1000", result)
        time.sleep(1.1)
        assert cache.get("0808.1000") is None

    def test_get_or_fallback_expired(self, tmp_db_dir):
        db_path = os.path.join(tmp_db_dir, "tipp.db")
        cache = TIPPCache(db_path=db_path, ttl=1)
        result = TIPPResult(hs_code="0808.1000", mfn_cd_rate=20.0, fetched_at=time.time())
        cache.put("0808.1000", result)
        time.sleep(1.1)
        # get() returns None (expired)
        assert cache.get("0808.1000") is None
        # get_or_fallback() returns stale data
        fallback = cache.get_or_fallback("0808.1000")
        assert fallback is not None
        assert fallback.mfn_cd_rate == 20.0

    def test_get_or_fallback_no_data(self, tmp_db_dir):
        db_path = os.path.join(tmp_db_dir, "tipp.db")
        cache = TIPPCache(db_path=db_path)
        assert cache.get_or_fallback("9999.9999") is None

    def test_put_updates_existing(self, tmp_db_dir):
        db_path = os.path.join(tmp_db_dir, "tipp.db")
        cache = TIPPCache(db_path=db_path)
        r1 = TIPPResult(hs_code="0808.1000", mfn_cd_rate=20.0, fetched_at=time.time())
        cache.put("0808.1000", r1)
        r2 = TIPPResult(hs_code="0808.1000", mfn_cd_rate=25.0, fetched_at=time.time())
        cache.put("0808.1000", r2)
        cached = cache.get("0808.1000")
        assert cached.mfn_cd_rate == 25.0
        assert cache.get_entry_count() == 1

    def test_invalidate(self, tmp_db_dir):
        db_path = os.path.join(tmp_db_dir, "tipp.db")
        cache = TIPPCache(db_path=db_path)
        result = TIPPResult(hs_code="0808.1000", mfn_cd_rate=20.0, fetched_at=time.time())
        cache.put("0808.1000", result)
        cache.invalidate("0808.1000")
        assert cache.get("0808.1000") is None

    def test_invalidate_all(self, tmp_db_dir):
        db_path = os.path.join(tmp_db_dir, "tipp.db")
        cache = TIPPCache(db_path=db_path)
        for i in range(5):
            r = TIPPResult(hs_code=f"080{i}.1000", mfn_cd_rate=20.0, fetched_at=time.time())
            cache.put(f"080{i}.1000", r)
        assert cache.get_entry_count() == 5
        cache.invalidate_all()
        assert cache.get_entry_count() == 0

    def test_cleanup_expired(self, tmp_db_dir):
        db_path = os.path.join(tmp_db_dir, "tipp.db")
        cache = TIPPCache(db_path=db_path, ttl=1)
        result = TIPPResult(hs_code="0808.1000", mfn_cd_rate=20.0, fetched_at=time.time())
        cache.put("0808.1000", result)
        time.sleep(1.1)
        removed = cache.cleanup_expired()
        assert removed >= 1
        assert cache.get_entry_count() == 0

    def test_stats(self, tmp_db_dir):
        db_path = os.path.join(tmp_db_dir, "tipp.db")
        cache = TIPPCache(db_path=db_path)
        result = TIPPResult(hs_code="0808.1000", mfn_cd_rate=20.0, fetched_at=time.time())
        cache.put("0808.1000", result)
        cache.get("0808.1000")  # Hit
        cache.get("9999.9999")  # Miss
        stats = cache.stats
        assert stats["hits"] >= 1
        assert stats["misses"] >= 1
        assert stats["updates"] >= 1

    def test_search_by_prefix(self, tmp_db_dir):
        db_path = os.path.join(tmp_db_dir, "tipp.db")
        cache = TIPPCache(db_path=db_path)
        for code in ["0808.1000", "0808.2000", "0809.1000", "6109.1000"]:
            r = TIPPResult(hs_code=code, mfn_cd_rate=20.0, fetched_at=time.time())
            cache.put(code, r)
        results = cache.search("0808")
        assert len(results) == 2

    def test_search_empty_query(self, tmp_db_dir):
        db_path = os.path.join(tmp_db_dir, "tipp.db")
        cache = TIPPCache(db_path=db_path)
        assert cache.search("") == []

    def test_normalizes_hs_code(self, tmp_db_dir):
        db_path = os.path.join(tmp_db_dir, "tipp.db")
        cache = TIPPCache(db_path=db_path)
        result = TIPPResult(hs_code="0808.1000", mfn_cd_rate=20.0, fetched_at=time.time())
        cache.put("08081000", result)  # No dot
        cached = cache.get("0808.1000")  # With dot
        assert cached is not None
