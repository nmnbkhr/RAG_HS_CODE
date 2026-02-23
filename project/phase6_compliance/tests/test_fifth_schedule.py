"""
Phase 6: Compliance - Fifth Schedule Tests
"""

import pytest
from fifth_schedule import (
    ConcessionEntry, FIFTH_SCHEDULE_RATES,
    lookup_concession, get_applicable_concessions,
    get_sectors, get_concessions_by_sector, get_concession_summary
)


class TestConcessionEntry:
    """Tests for ConcessionEntry dataclass"""

    def test_create(self):
        entry = ConcessionEntry(
            hs_code="8432.1000",
            description="Ploughs",
            concessionary_cd_rate=0.0,
            mfn_cd_rate=5.0,
            part="I",
            sector="Agriculture"
        )
        assert entry.concessionary_cd_rate == 0.0
        assert entry.mfn_cd_rate == 5.0

    def test_savings_pct(self):
        entry = ConcessionEntry(
            hs_code="8445.1100",
            description="Carding machines",
            concessionary_cd_rate=5.0,
            mfn_cd_rate=16.0,
            part="I",
        )
        assert entry.savings_pct == 11.0

    def test_savings_pct_zero_mfn(self):
        entry = ConcessionEntry(
            hs_code="0000.0000",
            description="Test",
            concessionary_cd_rate=0.0,
            mfn_cd_rate=0.0,
            part="I",
        )
        assert entry.savings_pct == 0.0

    def test_full_exemption(self):
        entry = ConcessionEntry(
            hs_code="8541.4000",
            description="Solar panels",
            concessionary_cd_rate=0.0,
            mfn_cd_rate=20.0,
            part="I",
        )
        assert entry.savings_pct == 20.0


class TestFifthScheduleData:
    """Tests for FIFTH_SCHEDULE_RATES data"""

    def test_data_not_empty(self):
        assert len(FIFTH_SCHEDULE_RATES) > 0

    def test_agriculture_entries(self):
        assert "8432.1000" in FIFTH_SCHEDULE_RATES
        assert FIFTH_SCHEDULE_RATES["8432.1000"].concessionary_cd_rate == 0.0

    def test_it_hardware_entries(self):
        assert "8471.3000" in FIFTH_SCHEDULE_RATES
        assert FIFTH_SCHEDULE_RATES["8471.3000"].concessionary_cd_rate == 0.0

    def test_solar_entry(self):
        assert "8541.4000" in FIFTH_SCHEDULE_RATES
        entry = FIFTH_SCHEDULE_RATES["8541.4000"]
        assert entry.concessionary_cd_rate == 0.0
        assert entry.mfn_cd_rate == 20.0

    def test_pharma_entries(self):
        assert "2941.1000" in FIFTH_SCHEDULE_RATES
        assert FIFTH_SCHEDULE_RATES["2941.1000"].concessionary_cd_rate == 3.0

    def test_textile_entries(self):
        assert "8445.1100" in FIFTH_SCHEDULE_RATES
        assert FIFTH_SCHEDULE_RATES["8445.1100"].concessionary_cd_rate == 5.0

    def test_all_entries_have_part(self):
        for code, entry in FIFTH_SCHEDULE_RATES.items():
            assert entry.part, f"Missing part for {code}"

    def test_concessionary_less_than_mfn(self):
        for code, entry in FIFTH_SCHEDULE_RATES.items():
            assert entry.concessionary_cd_rate <= entry.mfn_cd_rate, \
                f"{code}: concessionary {entry.concessionary_cd_rate} > MFN {entry.mfn_cd_rate}"


class TestLookupConcession:
    """Tests for lookup_concession()"""

    def test_exact_match(self):
        result = lookup_concession("8471.3000")
        assert result is not None
        assert result.sector == "IT"
        assert result.concessionary_cd_rate == 0.0

    def test_no_dot(self):
        result = lookup_concession("84713000")
        assert result is not None

    def test_heading_match(self):
        result = lookup_concession("8432.9900")
        assert result is not None
        assert result.sector == "Agriculture"

    def test_no_match(self):
        result = lookup_concession("0808.1000")
        assert result is None

    def test_empty_code(self):
        result = lookup_concession("")
        assert result is None

    def test_none_code(self):
        result = lookup_concession(None)
        assert result is None


class TestGetApplicableConcessions:
    """Tests for get_applicable_concessions()"""

    def test_multiple_matches_same_heading(self):
        results = get_applicable_concessions("8432")
        assert len(results) >= 2  # ploughs + disc harrows

    def test_single_match(self):
        results = get_applicable_concessions("8541.4000")
        assert len(results) == 1
        assert results[0].description == "Photovoltaic cells / solar panels"

    def test_no_matches(self):
        results = get_applicable_concessions("0808.1000")
        assert len(results) == 0

    def test_empty_code(self):
        results = get_applicable_concessions("")
        assert len(results) == 0


class TestGetSectors:
    """Tests for get_sectors()"""

    def test_returns_sorted_list(self):
        sectors = get_sectors()
        assert len(sectors) > 0
        assert sectors == sorted(sectors)

    def test_known_sectors(self):
        sectors = get_sectors()
        assert "Agriculture" in sectors
        assert "IT" in sectors
        assert "Renewable Energy" in sectors
        assert "Pharmaceuticals" in sectors


class TestGetConcessionsBySector:
    """Tests for get_concessions_by_sector()"""

    def test_agriculture_sector(self):
        results = get_concessions_by_sector("Agriculture")
        assert len(results) >= 2

    def test_it_sector(self):
        results = get_concessions_by_sector("IT")
        assert len(results) >= 2

    def test_case_insensitive(self):
        results = get_concessions_by_sector("agriculture")
        assert len(results) >= 2

    def test_unknown_sector(self):
        results = get_concessions_by_sector("NonExistent")
        assert len(results) == 0


class TestGetConcessionSummary:
    """Tests for get_concession_summary()"""

    def test_returns_list_of_dicts(self):
        summary = get_concession_summary()
        assert len(summary) > 0
        for item in summary:
            assert "hs_code" in item
            assert "description" in item
            assert "concessionary_rate" in item
            assert "mfn_rate" in item
            assert "savings" in item
            assert "sector" in item
