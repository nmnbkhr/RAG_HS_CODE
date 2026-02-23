"""
Phase 7: Live Data Integration - Source Orchestrator Tests
"""

import time
import pytest
from unittest.mock import MagicMock, patch
from source_orchestrator import (
    SourceOrchestrator, DataSourcePriority, SourceResult,
    DEFAULT_DUTY_RATES, DEFAULT_USD_RATE
)


class TestDataSourcePriority:
    """Tests for DataSourcePriority enum"""

    def test_ordering(self):
        assert DataSourcePriority.LIVE_TIPP.value < DataSourcePriority.LIVE_WEBOC.value
        assert DataSourcePriority.LIVE_WEBOC.value < DataSourcePriority.CACHED_TIPP.value
        assert DataSourcePriority.CACHED_TIPP.value < DataSourcePriority.STATIC_PHASE6.value
        assert DataSourcePriority.STATIC_PHASE6.value < DataSourcePriority.HARDCODED.value


class TestSourceResult:
    """Tests for SourceResult dataclass"""

    def test_create(self):
        result = SourceResult(
            data={"customs_duty": 20.0},
            source="TIPP (live)",
            priority=DataSourcePriority.LIVE_TIPP,
            fetched_at=time.time(),
        )
        assert result.source == "TIPP (live)"
        assert result.is_cached is False

    def test_freshness_label_static(self):
        result = SourceResult(data={}, source="defaults", priority=DataSourcePriority.HARDCODED)
        assert result.freshness_label == "static"

    def test_freshness_label_recent(self):
        result = SourceResult(
            data={}, source="TIPP", priority=DataSourcePriority.LIVE_TIPP,
            fetched_at=time.time() - 300  # 5 min ago
        )
        assert "m ago" in result.freshness_label


class TestSourceOrchestratorInit:
    """Tests for SourceOrchestrator initialization"""

    def test_init_empty(self):
        orch = SourceOrchestrator()
        assert orch.weboc_cache is None
        assert orch.tipp_cache is None
        assert orch.last_source is None

    def test_init_with_dependencies(self):
        mock_cache = MagicMock()
        orch = SourceOrchestrator(weboc_cache=mock_cache)
        assert orch.weboc_cache is mock_cache


class TestGetDutyRates:
    """Tests for get_duty_rates() fallback chain"""

    def test_empty_code_returns_defaults(self):
        orch = SourceOrchestrator()
        data, source = orch.get_duty_rates("")
        assert source == "defaults"
        assert data["customs_duty"] == DEFAULT_DUTY_RATES["customs_duty"]

    def test_no_sources_returns_defaults(self):
        orch = SourceOrchestrator()
        data, source = orch.get_duty_rates("0808.1000")
        assert source == "defaults"

    def test_tipp_cache_hit(self):
        mock_tipp_cache = MagicMock()
        mock_result = MagicMock()
        mock_result.mfn_cd_rate = 20.0
        mock_result.sales_tax_rate = 18.0
        mock_result.additional_duty_rate = 0.0
        mock_result.regulatory_duty_rate = 0.0
        mock_result.fed_rate = 0.0
        mock_result.fed_applicable = False
        mock_result.preferential_rates = {}
        mock_result.sro_references = []
        mock_result.description = "Fresh apples"
        mock_result.source = "TIPP"
        mock_result.fetched_at = time.time()
        mock_tipp_cache.get.return_value = mock_result

        orch = SourceOrchestrator(tipp_cache=mock_tipp_cache)
        data, source = orch.get_duty_rates("0808.1000")
        assert "TIPP" in source
        assert data["customs_duty"] == 20.0

    def test_weboc_cache_hit(self):
        mock_weboc_cache = MagicMock()
        mock_cached = MagicMock()
        mock_cached.customs_duty = 20.0
        mock_cached.sales_tax = 18.0
        mock_cached.income_tax = 5.5
        mock_cached.additional_duty = 0.0
        mock_cached.regulatory_duty = 0.0
        mock_cached.federal_excise_duty = 0.0
        mock_cached.description = "Fresh apples"
        mock_cached.source = "WEBOC"
        mock_cached.fetched_at = time.time()
        mock_weboc_cache.get.return_value = mock_cached
        mock_weboc_cache.get_or_fallback.return_value = None

        orch = SourceOrchestrator(weboc_cache=mock_weboc_cache)
        data, source = orch.get_duty_rates("0808.1000")
        assert "WEBOC" in source
        assert data["customs_duty"] == 20.0

    def test_tipp_cache_preferred_over_weboc(self):
        mock_tipp = MagicMock()
        mock_tipp_result = MagicMock()
        mock_tipp_result.mfn_cd_rate = 20.0
        mock_tipp_result.sales_tax_rate = 18.0
        mock_tipp_result.additional_duty_rate = 0.0
        mock_tipp_result.regulatory_duty_rate = 0.0
        mock_tipp_result.fed_rate = 0.0
        mock_tipp_result.fed_applicable = False
        mock_tipp_result.preferential_rates = {}
        mock_tipp_result.sro_references = []
        mock_tipp_result.description = "Apples"
        mock_tipp_result.source = "TIPP"
        mock_tipp_result.fetched_at = time.time()
        mock_tipp.get.return_value = mock_tipp_result

        mock_weboc = MagicMock()
        mock_weboc.get.return_value = MagicMock(customs_duty=25.0)

        orch = SourceOrchestrator(tipp_cache=mock_tipp, weboc_cache=mock_weboc)
        data, source = orch.get_duty_rates("0808.1000")
        assert "TIPP" in source  # TIPP should be used first
        assert data["customs_duty"] == 20.0

    def test_fallback_to_weboc_stale(self):
        mock_tipp = MagicMock()
        mock_tipp.get.return_value = None
        mock_tipp.get_or_fallback.return_value = None

        mock_weboc = MagicMock()
        mock_weboc.get.return_value = None  # Fresh miss
        mock_cached = MagicMock()
        mock_cached.customs_duty = 22.0
        mock_cached.sales_tax = 18.0
        mock_cached.income_tax = 5.5
        mock_cached.additional_duty = 0.0
        mock_cached.regulatory_duty = 0.0
        mock_cached.federal_excise_duty = 0.0
        mock_cached.description = "Apples"
        mock_cached.source = "WEBOC"
        mock_cached.fetched_at = time.time()
        mock_weboc.get_or_fallback.return_value = mock_cached

        orch = SourceOrchestrator(tipp_cache=mock_tipp, weboc_cache=mock_weboc)
        data, source = orch.get_duty_rates("0808.1000")
        assert "WEBOC" in source
        assert "stale" in source
        assert data["customs_duty"] == 22.0

    def test_fallback_to_phase6_static(self):
        mock_fed = MagicMock()
        mock_fed.get_fed_rate_for_import.return_value = 7.5

        mock_fifth = MagicMock()
        mock_fifth.lookup_concession.return_value = None

        orch = SourceOrchestrator(fed_rates_module=mock_fed, fifth_schedule_module=mock_fifth)
        data, source = orch.get_duty_rates("8703.2300")
        assert source == "Phase 6 static"
        assert data["federal_excise_duty"] == 7.5

    def test_phase6_fifth_schedule(self):
        mock_fifth = MagicMock()
        concession = MagicMock()
        concession.concessionary_cd_rate = 0.0
        concession.sector = "IT"
        mock_fifth.lookup_concession.return_value = concession

        orch = SourceOrchestrator(fifth_schedule_module=mock_fifth)
        data, source = orch.get_duty_rates("8471.3000")
        assert source == "Phase 6 static"
        assert data["customs_duty"] == 0.0
        assert data["fifth_schedule_applicable"] is True

    def test_fallback_chain_tracked(self):
        orch = SourceOrchestrator()
        orch.get_duty_rates("0808.1000")
        assert "defaults" in orch.last_fallback_chain


class TestGetExchangeRate:
    """Tests for get_exchange_rate() fallback chain"""

    def test_default_currency_is_usd(self):
        orch = SourceOrchestrator()
        selling, buying, source = orch.get_exchange_rate()
        assert source == "defaults"
        assert selling == DEFAULT_USD_RATE["tt_selling"]
        assert buying == DEFAULT_USD_RATE["tt_buying"]

    def test_exchange_cache_hit(self):
        mock_cache = MagicMock()
        mock_rate = MagicMock()
        mock_rate.tt_selling = 280.50
        mock_rate.tt_buying = 278.50
        mock_rate.source = "NBP"
        mock_cache.get.return_value = mock_rate

        orch = SourceOrchestrator(exchange_cache=mock_cache)
        selling, buying, source = orch.get_exchange_rate("USD")
        assert selling == 280.50
        assert buying == 278.50
        assert "NBP" in source

    def test_sbp_live_fallback(self):
        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_cache.get_or_fallback.return_value = None

        mock_sbp = MagicMock()
        mock_rate = MagicMock()
        mock_rate.tt_selling = 279.00
        mock_rate.tt_buying = 277.00
        mock_sbp.fetch_rate.return_value = mock_rate
        mock_sbp.last_error = None

        orch = SourceOrchestrator(exchange_cache=mock_cache, sbp_fetcher=mock_sbp)
        selling, buying, source = orch.get_exchange_rate("USD")
        assert "SBP" in source
        assert selling == 279.00

    def test_stale_cache_fallback(self):
        mock_cache = MagicMock()
        mock_cache.get.return_value = None
        mock_stale = MagicMock()
        mock_stale.tt_selling = 275.00
        mock_stale.tt_buying = 273.00
        mock_stale.source = "NBP"
        mock_cache.get_or_fallback.return_value = mock_stale

        orch = SourceOrchestrator(exchange_cache=mock_cache)
        selling, buying, source = orch.get_exchange_rate("USD")
        assert selling == 275.00
        assert "stale" in source

    def test_no_sources_returns_hardcoded(self):
        orch = SourceOrchestrator()
        selling, buying, source = orch.get_exchange_rate("USD")
        assert source == "defaults"


class TestGetComplianceInfo:
    """Tests for get_compliance_info()"""

    def test_empty_code(self):
        orch = SourceOrchestrator()
        info = orch.get_compliance_info("")
        assert info["fed"] is None
        assert info["fifth_schedule"] is None
        assert info["fta_pta"] == []

    def test_fed_info(self):
        mock_fed = MagicMock()
        entry = MagicMock()
        entry.rate_pct = 7.5
        entry.rate_type = MagicMock(value="ad_valorem")
        entry.basis = MagicMock(value="cif_plus_cd")
        entry.description = "Motor cars"
        mock_fed.lookup_fed_rate.return_value = entry

        orch = SourceOrchestrator(fed_rates_module=mock_fed)
        info = orch.get_compliance_info("8703.2300")
        assert info["fed"] is not None
        assert info["fed"]["rate_pct"] == 7.5

    def test_fifth_schedule_info(self):
        mock_fifth = MagicMock()
        concession = MagicMock()
        concession.concessionary_cd_rate = 0.0
        concession.mfn_cd_rate = 20.0
        concession.savings_pct = 20.0
        concession.sector = "IT"
        concession.part = "I"
        mock_fifth.lookup_concession.return_value = concession

        orch = SourceOrchestrator(fifth_schedule_module=mock_fifth)
        info = orch.get_compliance_info("8471.3000")
        assert info["fifth_schedule"] is not None
        assert info["fifth_schedule"]["concessionary_rate"] == 0.0

    def test_sro_references(self):
        mock_sro = MagicMock()
        sro1 = MagicMock()
        sro1.sro_number = "929(I)/2024"
        sro1.title = "ACD"
        sro1.sro_type = MagicMock(value="rate_change")
        sro1.status = "active"
        mock_sro.lookup_sros_for_hs_code.return_value = [sro1]

        orch = SourceOrchestrator(sro_database_module=mock_sro)
        info = orch.get_compliance_info("8703.2300")
        assert len(info["sro_references"]) == 1
        assert info["sro_references"][0]["sro_number"] == "929(I)/2024"


class TestGetSourceStatus:
    """Tests for get_source_status()"""

    def test_no_modules(self):
        orch = SourceOrchestrator()
        status = orch.get_source_status()
        assert status["TIPP"] == "not_configured"
        assert status["WEBOC"] == "not_configured"
        assert status["SBP"] == "not_configured"

    def test_with_modules(self):
        orch = SourceOrchestrator(
            tipp_scraper=MagicMock(),
            weboc_cache=MagicMock(),
            sbp_fetcher=MagicMock(),
        )
        status = orch.get_source_status()
        # These won't be "not_configured" since modules exist
        assert status["TIPP"] != "not_configured"
        assert status["WEBOC"] != "not_configured"
        assert status["SBP"] != "not_configured"

    def test_phase6_modules_status(self):
        orch = SourceOrchestrator(
            fed_rates_module=MagicMock(),
            fifth_schedule_module=MagicMock(),
        )
        status = orch.get_source_status()
        assert status["Phase 6 FED"] == "online"
        assert status["Phase 6 Fifth Schedule"] == "online"
        assert status["Phase 6 FTA/PTA"] == "not_configured"


class TestFallbackChainSummary:
    """Tests for get_fallback_chain_summary()"""

    def test_no_requests(self):
        orch = SourceOrchestrator()
        assert "No requests" in orch.get_fallback_chain_summary()

    def test_after_request(self):
        orch = SourceOrchestrator()
        orch.get_duty_rates("0808.1000")
        summary = orch.get_fallback_chain_summary()
        assert "Tried:" in summary
        assert "Used:" in summary
