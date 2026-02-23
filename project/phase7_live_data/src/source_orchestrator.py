"""
RAG_HS_CODE - Multi-Source Data Orchestrator
Phase 7: Live Data Integration

Central router that picks the best available data source for each
request type, with automatic fallback chains:

Duty Rates:
  TIPP (live) → WEBOC (live) → TIPP (cached) → WEBOC (cached)
  → Phase 6 static → Hardcoded defaults

Exchange Rates:
  ExchangeRateCache (fresh) → NBP (live) → SBP (live)
  → ExchangeRateCache (stale) → Hardcoded fallback

Compliance:
  TIPP live SRO references → Phase 6 static (FED, 5th Schedule, FTA/PTA, SRO DB)
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class DataSourcePriority(Enum):
    """Priority levels for data sources (lower = better)."""
    LIVE_TIPP = 1
    LIVE_WEBOC = 2
    CACHED_TIPP = 3
    CACHED_WEBOC = 4
    STATIC_PHASE6 = 5
    HARDCODED = 6


@dataclass
class SourceResult:
    """Result from a data source with provenance metadata."""
    data: Dict[str, Any]
    source: str                    # Human-readable source name
    priority: DataSourcePriority
    is_cached: bool = False
    is_stale: bool = False         # True if using expired cache
    fetched_at: float = 0.0

    @property
    def freshness_label(self) -> str:
        """Human-readable freshness description."""
        if self.fetched_at == 0:
            return "static"
        age = time.time() - self.fetched_at
        if age < 3600:
            return f"{age / 60:.0f}m ago"
        elif age < 86400:
            return f"{age / 3600:.1f}h ago"
        else:
            return f"{age / 86400:.1f}d ago"


# Default duty rates when all sources fail
DEFAULT_DUTY_RATES = {
    "customs_duty": 20.0,
    "sales_tax": 18.0,
    "income_tax": 6.0,
    "additional_duty": 7.0,
    "regulatory_duty": 0.0,
    "federal_excise_duty": 0.0,
}

# Default exchange rate (USD/PKR) when all sources fail
DEFAULT_USD_RATE = {
    "tt_selling": 278.50,
    "tt_buying": 278.00,
}


class SourceOrchestrator:
    """
    Routes data requests to the best available source with fallback.

    Accepts optional references to caches, scrapers, and Phase 6
    modules. Any missing dependency is gracefully skipped.

    Usage:
        orchestrator = SourceOrchestrator(
            weboc_cache=weboc_cache,
            tipp_cache=tipp_cache,
            tipp_scraper=tipp_scraper,
            exchange_cache=exchange_cache,
            sbp_fetcher=sbp_fetcher,
            offline_manager=offline_mgr,
            health_dashboard=health_dashboard,
        )
        rates, source_name = orchestrator.get_duty_rates("8703.2300")
    """

    def __init__(
        self,
        weboc_cache=None,
        tipp_cache=None,
        tipp_scraper=None,
        exchange_cache=None,
        sbp_fetcher=None,
        offline_manager=None,
        health_dashboard=None,
        # Phase 6 static modules (optional)
        fed_rates_module=None,
        fifth_schedule_module=None,
        fta_pta_module=None,
        sro_database_module=None,
    ):
        self.weboc_cache = weboc_cache
        self.tipp_cache = tipp_cache
        self.tipp_scraper = tipp_scraper
        self.exchange_cache = exchange_cache
        self.sbp_fetcher = sbp_fetcher
        self.offline_manager = offline_manager
        self.health_dashboard = health_dashboard

        self.fed_rates = fed_rates_module
        self.fifth_schedule = fifth_schedule_module
        self.fta_pta = fta_pta_module
        self.sro_database = sro_database_module

        # Track what happened in the last request
        self.last_source: Optional[str] = None
        self.last_fallback_chain: List[str] = []

    # ------------------------------------------------------------------
    # Duty Rates
    # ------------------------------------------------------------------

    def get_duty_rates(self, hs_code: str) -> Tuple[Dict[str, Any], str]:
        """
        Get duty rates from the best available source.

        Fallback chain:
          1. TIPP cache (fresh)
          2. WEBOC cache (fresh)
          3. TIPP live fetch
          4. WEBOC cache (stale)
          5. TIPP cache (stale)
          6. Phase 6 static FED + defaults
          7. Hardcoded defaults

        Args:
            hs_code: HS code to look up

        Returns:
            (duty_data_dict, source_name)
        """
        self.last_fallback_chain = []

        if not hs_code or not hs_code.strip():
            return dict(DEFAULT_DUTY_RATES), "defaults"

        # Step 1: Try TIPP cache (fresh)
        result = self._try_tipp_cache(hs_code, stale_ok=False)
        if result:
            return result

        # Step 2: Try WEBOC cache (fresh)
        result = self._try_weboc_cache(hs_code, stale_ok=False)
        if result:
            return result

        # Step 3: Try live TIPP fetch
        result = self._try_tipp_live(hs_code)
        if result:
            return result

        # Step 4: Try WEBOC cache (stale)
        result = self._try_weboc_cache(hs_code, stale_ok=True)
        if result:
            return result

        # Step 5: Try TIPP cache (stale)
        result = self._try_tipp_cache(hs_code, stale_ok=True)
        if result:
            return result

        # Step 6: Phase 6 static data
        result = self._try_phase6_static(hs_code)
        if result:
            return result

        # Step 7: Hardcoded defaults
        self.last_fallback_chain.append("defaults")
        self.last_source = "defaults"
        return dict(DEFAULT_DUTY_RATES), "defaults"

    def _try_tipp_cache(self, hs_code: str, stale_ok: bool) -> Optional[Tuple[Dict, str]]:
        """Try TIPP cache."""
        if not self.tipp_cache:
            return None

        label = "TIPP cache (stale)" if stale_ok else "TIPP cache"
        self.last_fallback_chain.append(label)

        try:
            if stale_ok:
                result = self.tipp_cache.get_or_fallback(hs_code)
            else:
                result = self.tipp_cache.get(hs_code)

            if result:
                data = self._tipp_result_to_duty_dict(result)
                source = f"TIPP (cached{', stale' if stale_ok else ''})"
                self.last_source = source
                return data, source
        except Exception:
            pass
        return None

    def _try_weboc_cache(self, hs_code: str, stale_ok: bool) -> Optional[Tuple[Dict, str]]:
        """Try WEBOC cache."""
        if not self.weboc_cache:
            return None

        label = "WEBOC cache (stale)" if stale_ok else "WEBOC cache"
        self.last_fallback_chain.append(label)

        try:
            if stale_ok:
                result = self.weboc_cache.get_or_fallback(hs_code)
            else:
                result = self.weboc_cache.get(hs_code)

            if result:
                data = self._weboc_data_to_duty_dict(result)
                source = f"WEBOC (cached{', stale' if stale_ok else ''})"
                self.last_source = source
                return data, source
        except Exception:
            pass
        return None

    def _try_tipp_live(self, hs_code: str) -> Optional[Tuple[Dict, str]]:
        """Try live TIPP fetch."""
        if not self.tipp_scraper:
            return None

        # Check if TIPP is available
        if self.offline_manager:
            try:
                health = self.offline_manager.get_health("tipp")
                if hasattr(health, "is_available") and not health.is_available:
                    self.last_fallback_chain.append("TIPP live (skipped - offline)")
                    return None
            except Exception:
                pass

        self.last_fallback_chain.append("TIPP live")

        start = time.time()
        try:
            result = self.tipp_scraper.search(hs_code)
            elapsed_ms = (time.time() - start) * 1000

            # Record health
            if self.health_dashboard:
                self.health_dashboard.record(
                    "TIPP", elapsed_ms, result is not None,
                    200 if result else 0,
                    "" if result else (self.tipp_scraper.last_error or "no result")
                )

            if result:
                # Cache the result
                if self.tipp_cache:
                    self.tipp_cache.put(hs_code, result)

                data = self._tipp_result_to_duty_dict(result)
                self.last_source = "TIPP (live)"
                return data, "TIPP (live)"
        except Exception:
            elapsed_ms = (time.time() - start) * 1000
            if self.health_dashboard:
                self.health_dashboard.record("TIPP", elapsed_ms, False, 0, "exception")
        return None

    def _try_phase6_static(self, hs_code: str) -> Optional[Tuple[Dict, str]]:
        """Try Phase 6 static data (FED rates, Fifth Schedule, etc.)."""
        self.last_fallback_chain.append("Phase 6 static")

        data = dict(DEFAULT_DUTY_RATES)
        found_anything = False

        # FED lookup
        if self.fed_rates:
            try:
                fed_rate = self.fed_rates.get_fed_rate_for_import(hs_code)
                if fed_rate > 0:
                    data["federal_excise_duty"] = fed_rate
                    found_anything = True
            except Exception:
                pass

        # Fifth Schedule concession
        if self.fifth_schedule:
            try:
                concession = self.fifth_schedule.lookup_concession(hs_code)
                if concession:
                    data["customs_duty"] = concession.concessionary_cd_rate
                    data["fifth_schedule_applicable"] = True
                    data["fifth_schedule_sector"] = concession.sector
                    found_anything = True
            except Exception:
                pass

        if found_anything:
            self.last_source = "Phase 6 static"
            return data, "Phase 6 static"

        return None

    @staticmethod
    def _tipp_result_to_duty_dict(result) -> Dict[str, Any]:
        """Convert TIPPResult to standard duty rate dict."""
        return {
            "customs_duty": result.mfn_cd_rate,
            "sales_tax": result.sales_tax_rate,
            "income_tax": 6.0,  # TIPP doesn't have IT withholding
            "additional_duty": result.additional_duty_rate,
            "regulatory_duty": result.regulatory_duty_rate,
            "federal_excise_duty": result.fed_rate,
            "fed_applicable": result.fed_applicable,
            "preferential_rates": result.preferential_rates,
            "sro_references": result.sro_references,
            "description": result.description,
            "unit_of_measure": getattr(result, "unit_of_measure", "units"),
            "source": result.source,
            "fetched_at": result.fetched_at,
        }

    @staticmethod
    def _weboc_data_to_duty_dict(cached_data) -> Dict[str, Any]:
        """Convert CachedDutyData to standard duty rate dict."""
        return {
            "customs_duty": cached_data.customs_duty,
            "sales_tax": cached_data.sales_tax,
            "income_tax": cached_data.income_tax,
            "additional_duty": cached_data.additional_duty,
            "regulatory_duty": cached_data.regulatory_duty,
            "federal_excise_duty": getattr(cached_data, "federal_excise_duty", 0.0) or 0.0,
            "description": getattr(cached_data, "description", ""),
            "unit_of_measure": getattr(cached_data, "unit_of_measure", "units"),
            "source": getattr(cached_data, "source", "WEBOC"),
            "fetched_at": getattr(cached_data, "fetched_at", 0.0),
        }

    # ------------------------------------------------------------------
    # Exchange Rates
    # ------------------------------------------------------------------

    def get_exchange_rate(self, currency: str = "USD") -> Tuple[float, float, str]:
        """
        Get exchange rate from best available source.

        Fallback chain:
          1. ExchangeRateCache (fresh)
          2. NBP (via offline_manager check + direct)
          3. SBP (live)
          4. ExchangeRateCache (stale)
          5. Hardcoded default

        Args:
            currency: ISO currency code (default USD)

        Returns:
            (tt_selling, tt_buying, source_name)
        """
        self.last_fallback_chain = []
        currency = (currency or "USD").upper().strip()

        # Step 1: Exchange rate cache (fresh)
        result = self._try_exchange_cache(currency, stale_ok=False)
        if result:
            return result

        # Step 2: SBP live (faster to check than retrying NBP)
        result = self._try_sbp_live(currency)
        if result:
            return result

        # Step 3: Exchange rate cache (stale)
        result = self._try_exchange_cache(currency, stale_ok=True)
        if result:
            return result

        # Step 4: Hardcoded default
        self.last_fallback_chain.append("defaults")
        self.last_source = "defaults"
        defaults = DEFAULT_USD_RATE
        return defaults["tt_selling"], defaults["tt_buying"], "defaults"

    def _try_exchange_cache(self, currency: str, stale_ok: bool) -> Optional[Tuple[float, float, str]]:
        """Try exchange rate cache."""
        if not self.exchange_cache:
            return None

        label = "ExchangeRate cache (stale)" if stale_ok else "ExchangeRate cache"
        self.last_fallback_chain.append(label)

        try:
            if stale_ok:
                rate = self.exchange_cache.get_or_fallback(currency)
            else:
                rate = self.exchange_cache.get(currency)

            if rate:
                source = f"{rate.source} (cached{', stale' if stale_ok else ''})"
                self.last_source = source
                return rate.tt_selling, rate.tt_buying, source
        except Exception:
            pass
        return None

    def _try_sbp_live(self, currency: str) -> Optional[Tuple[float, float, str]]:
        """Try live SBP fetch."""
        if not self.sbp_fetcher:
            return None

        self.last_fallback_chain.append("SBP live")

        start = time.time()
        try:
            rate = self.sbp_fetcher.fetch_rate(currency)
            elapsed_ms = (time.time() - start) * 1000

            if self.health_dashboard:
                self.health_dashboard.record(
                    "SBP", elapsed_ms, rate is not None,
                    200 if rate else 0,
                    "" if rate else (self.sbp_fetcher.last_error or "no rate")
                )

            if rate:
                # Cache the result
                if self.exchange_cache:
                    self.exchange_cache.put(
                        currency, rate.tt_buying, rate.tt_selling, "SBP"
                    )
                self.last_source = "SBP (live)"
                return rate.tt_selling, rate.tt_buying, "SBP (live)"
        except Exception:
            elapsed_ms = (time.time() - start) * 1000
            if self.health_dashboard:
                self.health_dashboard.record("SBP", elapsed_ms, False, 0, "exception")
        return None

    # ------------------------------------------------------------------
    # Compliance Info
    # ------------------------------------------------------------------

    def get_compliance_info(self, hs_code: str, country: str = "") -> Dict[str, Any]:
        """
        Get combined compliance information from all sources.

        Merges TIPP live data with Phase 6 static data.
        TIPP data overrides static where available.

        Args:
            hs_code: HS code to check
            country: Origin country for FTA/PTA lookup

        Returns:
            Dict with fed, fifth_schedule, fta_pta, sro info
        """
        info: Dict[str, Any] = {
            "fed": None,
            "fifth_schedule": None,
            "fta_pta": [],
            "sro_references": [],
            "best_preferential_rate": None,
        }

        if not hs_code:
            return info

        # FED from Phase 6
        if self.fed_rates:
            try:
                fed_entry = self.fed_rates.lookup_fed_rate(hs_code)
                if fed_entry:
                    info["fed"] = {
                        "rate_pct": fed_entry.rate_pct,
                        "rate_type": fed_entry.rate_type.value if hasattr(fed_entry.rate_type, "value") else str(fed_entry.rate_type),
                        "basis": fed_entry.basis.value if hasattr(fed_entry.basis, "value") else str(fed_entry.basis),
                        "description": fed_entry.description,
                    }
            except Exception:
                pass

        # Fifth Schedule from Phase 6
        if self.fifth_schedule:
            try:
                concession = self.fifth_schedule.lookup_concession(hs_code)
                if concession:
                    info["fifth_schedule"] = {
                        "concessionary_rate": concession.concessionary_cd_rate,
                        "mfn_rate": concession.mfn_cd_rate,
                        "savings_pct": concession.savings_pct,
                        "sector": concession.sector,
                        "part": concession.part,
                    }
            except Exception:
                pass

        # FTA/PTA from Phase 6
        if self.fta_pta and country:
            try:
                best = self.fta_pta.get_best_rate(hs_code, country)
                if best:
                    info["best_preferential_rate"] = {
                        "agreement_code": best.agreement_code,
                        "preferential_rate": best.preferential_cd_rate,
                        "mfn_rate": best.mfn_cd_rate,
                        "savings_pct": best.savings_pct,
                    }
                # All matching rates
                comparisons = self.fta_pta.get_rate_comparison(hs_code)
                if comparisons:
                    info["fta_pta"] = comparisons
            except Exception:
                pass

        # SRO references from Phase 6
        if self.sro_database:
            try:
                sros = self.sro_database.lookup_sros_for_hs_code(hs_code)
                info["sro_references"] = [
                    {
                        "sro_number": s.sro_number,
                        "title": s.title,
                        "type": s.sro_type.value if hasattr(s.sro_type, "value") else str(s.sro_type),
                        "status": s.status,
                    }
                    for s in sros
                ]
            except Exception:
                pass

        # Override with TIPP data if available
        if self.tipp_cache:
            try:
                tipp = self.tipp_cache.get(hs_code) or self.tipp_cache.get_or_fallback(hs_code)
                if tipp:
                    # Add TIPP SRO references
                    if tipp.sro_references:
                        existing_sro_numbers = {s["sro_number"] for s in info["sro_references"]}
                        for sro_ref in tipp.sro_references:
                            if sro_ref not in existing_sro_numbers:
                                info["sro_references"].append({
                                    "sro_number": sro_ref,
                                    "title": "(from TIPP)",
                                    "type": "unknown",
                                    "status": "active",
                                })
                    # Add TIPP preferential rates
                    if tipp.preferential_rates:
                        info["tipp_preferential_rates"] = tipp.preferential_rates
            except Exception:
                pass

        return info

    # ------------------------------------------------------------------
    # Source Status
    # ------------------------------------------------------------------

    def get_source_status(self) -> Dict[str, str]:
        """
        Get status of all data sources.

        Returns:
            Dict mapping source name to status string
            ("online", "degraded", "offline", "not_configured")
        """
        status = {}

        # TIPP
        if self.tipp_scraper:
            status["TIPP"] = self._check_source_health("TIPP")
        else:
            status["TIPP"] = "not_configured"

        # WEBOC
        if self.weboc_cache:
            status["WEBOC"] = self._check_source_health("WEBOC")
        else:
            status["WEBOC"] = "not_configured"

        # SBP
        if self.sbp_fetcher:
            status["SBP"] = self._check_source_health("SBP")
        else:
            status["SBP"] = "not_configured"

        # NBP
        status["NBP"] = self._check_source_health("NBP")

        # Phase 6 static modules
        status["Phase 6 FED"] = "online" if self.fed_rates else "not_configured"
        status["Phase 6 Fifth Schedule"] = "online" if self.fifth_schedule else "not_configured"
        status["Phase 6 FTA/PTA"] = "online" if self.fta_pta else "not_configured"
        status["Phase 6 SRO DB"] = "online" if self.sro_database else "not_configured"

        return status

    def _check_source_health(self, source: str) -> str:
        """Check health of a specific source via health dashboard."""
        if self.health_dashboard:
            try:
                health = self.health_dashboard.get_health(source)
                return health.get("status", "unknown")
            except Exception:
                pass

        if self.offline_manager:
            try:
                svc_health = self.offline_manager.get_health(source.lower())
                if hasattr(svc_health, "is_available"):
                    return "online" if svc_health.is_available else "offline"
            except Exception:
                pass

        return "unknown"

    def get_fallback_chain_summary(self) -> str:
        """Human-readable summary of the last fallback chain."""
        if not self.last_fallback_chain:
            return "No requests yet"
        chain = " → ".join(self.last_fallback_chain)
        result = f"Tried: {chain}"
        if self.last_source:
            result += f"\nUsed: {self.last_source}"
        return result
