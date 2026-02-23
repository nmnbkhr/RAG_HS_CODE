"""
Phase 6: Compliance - FTA/PTA Preferential Tariff Tests
"""

import pytest
from fta_pta import (
    TradeAgreement, PreferentialRate,
    TRADE_AGREEMENTS, COUNTRY_TO_AGREEMENTS, PREFERENTIAL_RATES,
    get_agreement, get_agreements_for_country,
    get_preferential_rates, get_best_rate,
    get_all_countries, get_rate_comparison
)


class TestTradeAgreement:
    """Tests for TradeAgreement dataclass"""

    def test_create(self):
        ta = TradeAgreement(
            code="TEST",
            name="Test Agreement",
            partner="Test Country",
            sro_reference="SRO 123/2024",
        )
        assert ta.code == "TEST"
        assert ta.coo_required is True
        assert ta.active is True


class TestPreferentialRate:
    """Tests for PreferentialRate dataclass"""

    def test_create(self):
        pr = PreferentialRate(
            hs_code="0808.1000",
            description="Fresh apples",
            agreement_code="CPFTA",
            preferential_cd_rate=0.0,
            mfn_cd_rate=20.0,
        )
        assert pr.preferential_cd_rate == 0.0
        assert pr.mfn_cd_rate == 20.0

    def test_savings(self):
        pr = PreferentialRate("0808.1000", "Apples", "CPFTA", 0.0, 20.0)
        assert pr.savings_pct == 20.0

    def test_savings_partial(self):
        pr = PreferentialRate("6109.1000", "T-shirts", "CPFTA", 7.5, 20.0)
        assert pr.savings_pct == 12.5


class TestTradeAgreementsData:
    """Tests for TRADE_AGREEMENTS data"""

    def test_cpfta_exists(self):
        assert "CPFTA" in TRADE_AGREEMENTS
        assert TRADE_AGREEMENTS["CPFTA"].partner == "China"

    def test_safta_exists(self):
        assert "SAFTA" in TRADE_AGREEMENTS

    def test_mpfta_exists(self):
        assert "MPFTA" in TRADE_AGREEMENTS
        assert TRADE_AGREEMENTS["MPFTA"].partner == "Malaysia"

    def test_all_agreements_active(self):
        for code, ta in TRADE_AGREEMENTS.items():
            assert ta.active, f"{code} is not active"

    def test_all_have_sro_reference(self):
        for code, ta in TRADE_AGREEMENTS.items():
            assert ta.sro_reference, f"{code} missing SRO reference"


class TestCountryMapping:
    """Tests for COUNTRY_TO_AGREEMENTS mapping"""

    def test_china_maps_to_cpfta(self):
        assert "china" in COUNTRY_TO_AGREEMENTS
        assert "CPFTA" in COUNTRY_TO_AGREEMENTS["china"]

    def test_malaysia_maps_to_mpfta(self):
        assert "malaysia" in COUNTRY_TO_AGREEMENTS
        assert "MPFTA" in COUNTRY_TO_AGREEMENTS["malaysia"]

    def test_sri_lanka_has_multiple(self):
        assert "sri lanka" in COUNTRY_TO_AGREEMENTS
        codes = COUNTRY_TO_AGREEMENTS["sri lanka"]
        assert "PKSL" in codes
        assert "SAFTA" in codes

    def test_all_codes_valid(self):
        for country, codes in COUNTRY_TO_AGREEMENTS.items():
            for code in codes:
                assert code in TRADE_AGREEMENTS, \
                    f"Invalid agreement code {code} for {country}"


class TestPreferentialRatesData:
    """Tests for PREFERENTIAL_RATES data"""

    def test_cpfta_has_rates(self):
        assert "CPFTA" in PREFERENTIAL_RATES
        assert len(PREFERENTIAL_RATES["CPFTA"]) > 0

    def test_all_agreements_have_rates(self):
        for code in TRADE_AGREEMENTS:
            assert code in PREFERENTIAL_RATES, f"No rates for {code}"

    def test_preferential_less_than_mfn(self):
        for code, rates in PREFERENTIAL_RATES.items():
            for rate in rates:
                assert rate.preferential_cd_rate <= rate.mfn_cd_rate, \
                    f"{code}/{rate.hs_code}: pref {rate.preferential_cd_rate} > MFN {rate.mfn_cd_rate}"


class TestGetAgreement:
    """Tests for get_agreement()"""

    def test_valid_code(self):
        result = get_agreement("CPFTA")
        assert result is not None
        assert result.partner == "China"

    def test_case_insensitive(self):
        result = get_agreement("cpfta")
        assert result is not None

    def test_invalid_code(self):
        result = get_agreement("INVALID")
        assert result is None


class TestGetAgreementsForCountry:
    """Tests for get_agreements_for_country()"""

    def test_china(self):
        results = get_agreements_for_country("China")
        assert len(results) == 1
        assert results[0].code == "CPFTA"

    def test_sri_lanka(self):
        results = get_agreements_for_country("Sri Lanka")
        assert len(results) == 2

    def test_case_insensitive(self):
        results = get_agreements_for_country("CHINA")
        assert len(results) == 1

    def test_no_agreement(self):
        results = get_agreements_for_country("Japan")
        assert len(results) == 0

    def test_whitespace_handling(self):
        results = get_agreements_for_country("  China  ")
        assert len(results) == 1


class TestGetPreferentialRates:
    """Tests for get_preferential_rates()"""

    def test_apples_cpfta(self):
        results = get_preferential_rates("0808.1000", "CPFTA")
        assert len(results) >= 1
        assert results[0].preferential_cd_rate == 0.0

    def test_palm_oil_mpfta(self):
        results = get_preferential_rates("1511.1000", "MPFTA")
        assert len(results) >= 1

    def test_no_match(self):
        results = get_preferential_rates("9999.9999", "CPFTA")
        assert len(results) == 0

    def test_empty_code(self):
        results = get_preferential_rates("", "CPFTA")
        assert len(results) == 0

    def test_empty_agreement(self):
        results = get_preferential_rates("0808.1000", "")
        assert len(results) == 0


class TestGetBestRate:
    """Tests for get_best_rate()"""

    def test_apples_from_china(self):
        best = get_best_rate("0808.1000", "China")
        assert best is not None
        assert best.preferential_cd_rate == 0.0
        assert best.agreement_code == "CPFTA"

    def test_no_preferential(self):
        best = get_best_rate("9999.9999", "China")
        assert best is None

    def test_country_with_no_agreement(self):
        best = get_best_rate("0808.1000", "Japan")
        assert best is None

    def test_empty_inputs(self):
        assert get_best_rate("", "China") is None
        assert get_best_rate("0808.1000", "") is None


class TestGetAllCountries:
    """Tests for get_all_countries()"""

    def test_returns_sorted_list(self):
        countries = get_all_countries()
        assert len(countries) > 0
        assert countries == sorted(countries)

    def test_known_countries(self):
        countries = get_all_countries()
        assert "China" in countries
        assert "Malaysia" in countries
        assert "Iran" in countries


class TestGetRateComparison:
    """Tests for get_rate_comparison()"""

    def test_apples_comparison(self):
        results = get_rate_comparison("0808.1000")
        assert len(results) >= 1
        # Should include CPFTA rate for apples
        cpfta = [r for r in results if r["agreement_code"] == "CPFTA"]
        assert len(cpfta) >= 1

    def test_sorted_by_rate(self):
        results = get_rate_comparison("0808.1000")
        if len(results) >= 2:
            rates = [r["preferential_rate"] for r in results]
            assert rates == sorted(rates)

    def test_no_results(self):
        results = get_rate_comparison("9999.9999")
        assert len(results) == 0

    def test_result_structure(self):
        results = get_rate_comparison("0808.1000")
        if results:
            item = results[0]
            assert "agreement" in item
            assert "agreement_code" in item
            assert "preferential_rate" in item
            assert "mfn_rate" in item
            assert "savings" in item
            assert "coo_required" in item
