"""
Phase 6: Compliance - FED Rate Lookup Tests
"""

import pytest
from fed_rates import (
    FEDEntry, FEDRateType, FEDBasis, FED_RATES,
    lookup_fed_rate, get_fed_rate_for_import,
    get_all_fed_headings, get_fed_summary
)


class TestFEDEntry:
    """Tests for FEDEntry dataclass"""

    def test_create_ad_valorem(self):
        entry = FEDEntry(
            hs_heading="8703.2300",
            description="Motor cars 1501-1800cc",
            rate_pct=7.5,
        )
        assert entry.rate_pct == 7.5
        assert entry.rate_type == FEDRateType.AD_VALOREM
        assert entry.basis == FEDBasis.CIF_PLUS_CD

    def test_create_specific(self):
        entry = FEDEntry(
            hs_heading="2523",
            description="Cement",
            rate_pct=0.0,
            rate_type=FEDRateType.SPECIFIC,
            specific_rate_pkr=2.0,
            specific_unit="kg"
        )
        assert entry.rate_type == FEDRateType.SPECIFIC
        assert entry.specific_rate_pkr == 2.0

    def test_create_retail_price(self):
        entry = FEDEntry(
            hs_heading="2402",
            description="Cigarettes",
            rate_pct=65.0,
            rate_type=FEDRateType.RETAIL_PRICE,
            basis=FEDBasis.RETAIL_PRICE,
        )
        assert entry.rate_type == FEDRateType.RETAIL_PRICE
        assert entry.basis == FEDBasis.RETAIL_PRICE


class TestFEDRatesData:
    """Tests for FED_RATES static data"""

    def test_data_not_empty(self):
        assert len(FED_RATES) > 0

    def test_tobacco_rate(self):
        assert "2402" in FED_RATES
        entry = FED_RATES["2402"]
        assert entry.rate_pct == 65.0
        assert entry.rate_type == FEDRateType.RETAIL_PRICE

    def test_vehicle_rates_exist(self):
        assert "8703.2100" in FED_RATES  # <= 1000cc
        assert "8703.2200" in FED_RATES  # 1001-1500cc
        assert "8703.2300" in FED_RATES  # 1501-1800cc
        assert "8703.2400" in FED_RATES  # 1801-3000cc

    def test_vehicle_rate_progression(self):
        rates = [
            FED_RATES["8703.2100"].rate_pct,  # 2.5%
            FED_RATES["8703.2200"].rate_pct,  # 5.0%
            FED_RATES["8703.2300"].rate_pct,  # 7.5%
            FED_RATES["8703.2400"].rate_pct,  # 10.0%
        ]
        # Rates should increase with engine size
        assert rates == sorted(rates)

    def test_cement_is_specific(self):
        assert "2523" in FED_RATES
        entry = FED_RATES["2523"]
        assert entry.rate_type == FEDRateType.SPECIFIC
        assert entry.specific_rate_pkr > 0

    def test_beverages_rate(self):
        assert "2202" in FED_RATES
        assert FED_RATES["2202"].rate_pct == 13.0

    def test_cosmetics_rates(self):
        assert "3303" in FED_RATES
        assert "3304" in FED_RATES
        assert FED_RATES["3303"].rate_pct == 5.0

    def test_all_entries_have_description(self):
        for code, entry in FED_RATES.items():
            assert entry.description, f"Missing description for {code}"


class TestLookupFEDRate:
    """Tests for lookup_fed_rate()"""

    def test_exact_8digit_match(self):
        result = lookup_fed_rate("8703.2300")
        assert result is not None
        assert result.rate_pct == 7.5

    def test_exact_match_no_dot(self):
        result = lookup_fed_rate("87032300")
        assert result is not None
        assert result.rate_pct == 7.5

    def test_heading_match(self):
        result = lookup_fed_rate("2402.1000")
        assert result is not None
        assert result.hs_heading == "2402"

    def test_heading_4digit(self):
        result = lookup_fed_rate("2523")
        assert result is not None
        assert result.rate_type == FEDRateType.SPECIFIC

    def test_no_match(self):
        result = lookup_fed_rate("0808.1000")  # Fresh apples — no FED
        assert result is None

    def test_empty_code(self):
        result = lookup_fed_rate("")
        assert result is None

    def test_none_code(self):
        result = lookup_fed_rate(None)
        assert result is None

    def test_whitespace_handling(self):
        result = lookup_fed_rate("  8703.2300  ")
        assert result is not None


class TestGetFEDRateForImport:
    """Tests for get_fed_rate_for_import()"""

    def test_ad_valorem_cif_plus_cd(self):
        # Vehicle 1501-1800cc = 7.5% ad-valorem on CIF+CD
        rate = get_fed_rate_for_import("8703.2300")
        assert rate == 7.5

    def test_specific_rate_returns_zero(self):
        # Cement has specific rate, can't be expressed as %
        rate = get_fed_rate_for_import("2523.1000")
        assert rate == 0.0

    def test_retail_price_returns_zero(self):
        # Tobacco uses retail price basis, not CIF+CD
        rate = get_fed_rate_for_import("2402.1000")
        assert rate == 0.0

    def test_no_fed_returns_zero(self):
        rate = get_fed_rate_for_import("0808.1000")
        assert rate == 0.0

    def test_cosmetics_rate(self):
        rate = get_fed_rate_for_import("3303.0000")
        assert rate == 5.0

    def test_empty_returns_zero(self):
        rate = get_fed_rate_for_import("")
        assert rate == 0.0


class TestGetAllFEDHeadings:
    """Tests for get_all_fed_headings()"""

    def test_returns_sorted_list(self):
        headings = get_all_fed_headings()
        assert len(headings) > 0
        assert headings == sorted(headings)

    def test_contains_known_headings(self):
        headings = get_all_fed_headings()
        assert "2402" in headings
        assert "2523" in headings


class TestGetFEDSummary:
    """Tests for get_fed_summary()"""

    def test_returns_list_of_dicts(self):
        summary = get_fed_summary()
        assert len(summary) > 0
        for item in summary:
            assert "hs_code" in item
            assert "description" in item
            assert "rate" in item
            assert "type" in item
            assert "basis" in item

    def test_specific_rate_formatted(self):
        summary = get_fed_summary()
        cement = [s for s in summary if s["hs_code"] == "2523"]
        assert len(cement) == 1
        assert "Rs." in cement[0]["rate"]
