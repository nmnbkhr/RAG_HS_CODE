"""
Phase 6: Compliance - SRO Database Tests
"""

import pytest
from datetime import date
from sro_database import (
    SROEntry, SROType, AffectedDuty, SRO_DATABASE,
    lookup_sros_for_hs_code, get_active_sros,
    get_sros_by_type, get_sros_by_duty,
    get_sro_summary, search_sros
)


class TestSROEntry:
    """Tests for SROEntry dataclass"""

    def test_create(self):
        sro = SROEntry(
            sro_number="999(I)/2024",
            title="Test SRO",
            sro_type=SROType.RATE_CHANGE,
            affected_duty=AffectedDuty.CUSTOMS_DUTY,
        )
        assert sro.sro_number == "999(I)/2024"
        assert sro.sro_type == SROType.RATE_CHANGE

    def test_is_active_no_dates(self):
        sro = SROEntry(
            sro_number="TEST",
            title="Test",
            sro_type=SROType.EXEMPTION,
            affected_duty=AffectedDuty.CUSTOMS_DUTY,
        )
        assert sro.is_active is True

    def test_is_active_with_dates(self):
        sro = SROEntry(
            sro_number="TEST",
            title="Test",
            sro_type=SROType.EXEMPTION,
            affected_duty=AffectedDuty.CUSTOMS_DUTY,
            effective_from=date(2020, 1, 1),
        )
        assert sro.is_active is True

    def test_expired(self):
        sro = SROEntry(
            sro_number="TEST",
            title="Test",
            sro_type=SROType.EXEMPTION,
            affected_duty=AffectedDuty.CUSTOMS_DUTY,
            effective_from=date(2020, 1, 1),
            effective_to=date(2020, 12, 31),
        )
        assert sro.is_active is False
        assert sro.status == "expired"

    def test_not_yet_effective(self):
        sro = SROEntry(
            sro_number="TEST",
            title="Test",
            sro_type=SROType.EXEMPTION,
            affected_duty=AffectedDuty.CUSTOMS_DUTY,
            effective_from=date(2099, 1, 1),
        )
        assert sro.is_active is False
        assert sro.status == "not_yet_effective"

    def test_status_active(self):
        sro = SROEntry(
            sro_number="TEST",
            title="Test",
            sro_type=SROType.EXEMPTION,
            affected_duty=AffectedDuty.CUSTOMS_DUTY,
            effective_from=date(2020, 1, 1),
        )
        assert sro.status == "active"


class TestSRODatabaseData:
    """Tests for SRO_DATABASE data"""

    def test_database_not_empty(self):
        assert len(SRO_DATABASE) > 0

    def test_all_have_sro_number(self):
        for sro in SRO_DATABASE:
            assert sro.sro_number, "SRO missing number"

    def test_all_have_title(self):
        for sro in SRO_DATABASE:
            assert sro.title, f"SRO {sro.sro_number} missing title"

    def test_key_sros_exist(self):
        numbers = [sro.sro_number for sro in SRO_DATABASE]
        assert "929(I)/2024" in numbers    # ACD
        assert "1035(I)/2023" in numbers   # RD luxury
        assert "565(I)/2006" in numbers    # Fifth Schedule
        assert "237(I)/2020" in numbers    # CPFTA

    def test_most_sros_active(self):
        active = [sro for sro in SRO_DATABASE if sro.is_active]
        assert len(active) >= len(SRO_DATABASE) // 2


class TestLookupSROsForHSCode:
    """Tests for lookup_sros_for_hs_code()"""

    def test_vehicle_sros(self):
        results = lookup_sros_for_hs_code("8703.2300")
        assert len(results) >= 1
        # Should include RD luxury and/or ACD
        sro_numbers = [s.sro_number for s in results]
        assert any("1035" in n for n in sro_numbers) or \
               any("929" in n for n in sro_numbers)

    def test_tobacco_sros(self):
        results = lookup_sros_for_hs_code("2402.1000")
        assert len(results) >= 1
        # Should include FED notification
        sro_numbers = [s.sro_number for s in results]
        assert any("655" in n for n in sro_numbers)

    def test_agriculture_machinery(self):
        results = lookup_sros_for_hs_code("8432.1000")
        assert len(results) >= 1
        # Should include Fifth Schedule
        sro_numbers = [s.sro_number for s in results]
        assert any("565" in n for n in sro_numbers)

    def test_apples_from_china(self):
        results = lookup_sros_for_hs_code("0808.1000")
        assert len(results) >= 1
        # Should include CPFTA
        sro_numbers = [s.sro_number for s in results]
        assert any("237" in n for n in sro_numbers)

    def test_broad_sros_included(self):
        # SROs with empty affected_hs_codes apply broadly
        results = lookup_sros_for_hs_code("0808.1000")
        broad = [s for s in results if not s.affected_hs_codes]
        assert len(broad) >= 1  # IT withholding applies to all

    def test_empty_code(self):
        results = lookup_sros_for_hs_code("")
        assert len(results) == 0

    def test_none_code(self):
        results = lookup_sros_for_hs_code(None)
        assert len(results) == 0


class TestGetActiveSROs:
    """Tests for get_active_sros()"""

    def test_returns_active_only(self):
        active = get_active_sros()
        for sro in active:
            assert sro.is_active


class TestGetSROsByType:
    """Tests for get_sros_by_type()"""

    def test_exemptions(self):
        results = get_sros_by_type(SROType.EXEMPTION)
        for sro in results:
            assert sro.sro_type == SROType.EXEMPTION

    def test_rate_changes(self):
        results = get_sros_by_type(SROType.RATE_CHANGE)
        assert len(results) >= 1

    def test_regulatory_duty(self):
        results = get_sros_by_type(SROType.REGULATORY_DUTY)
        assert len(results) >= 1


class TestGetSROsByDuty:
    """Tests for get_sros_by_duty()"""

    def test_customs_duty(self):
        results = get_sros_by_duty(AffectedDuty.CUSTOMS_DUTY)
        assert len(results) >= 1

    def test_fed(self):
        results = get_sros_by_duty(AffectedDuty.FEDERAL_EXCISE_DUTY)
        assert len(results) >= 1

    def test_income_tax(self):
        results = get_sros_by_duty(AffectedDuty.INCOME_TAX)
        assert len(results) >= 1


class TestGetSROSummary:
    """Tests for get_sro_summary()"""

    def test_returns_list(self):
        summary = get_sro_summary()
        assert len(summary) > 0

    def test_structure(self):
        summary = get_sro_summary()
        for item in summary:
            assert "sro_number" in item
            assert "title" in item
            assert "type" in item
            assert "duty" in item
            assert "status" in item


class TestSearchSROs:
    """Tests for search_sros()"""

    def test_search_by_number(self):
        results = search_sros("929")
        assert len(results) >= 1

    def test_search_by_keyword(self):
        results = search_sros("luxury")
        assert len(results) >= 1

    def test_search_by_duty_type(self):
        results = search_sros("FED")
        assert len(results) >= 1

    def test_case_insensitive(self):
        results = search_sros("cpfta")
        assert len(results) >= 1

    def test_empty_query(self):
        results = search_sros("")
        assert len(results) == 0

    def test_no_match(self):
        results = search_sros("xyznonexistent123")
        assert len(results) == 0
