"""
Phase 4: Features - Duty Comparator Tests

High-grade tests for side-by-side duty comparison.
"""

import pytest
from duty_comparator import DutyComparator, DutyProfile, ComparisonResult, ComparisonItem


# --- Test Profiles ---

APPLES = DutyProfile("0808.1000", "Fresh apples", 20.0, 18.0, 5.5)
HORSES = DutyProfile("0101.2100", "Live horses", 0.0, 18.0, 5.5)
VEHICLES = DutyProfile("8703.2300", "Motor vehicles", 50.0, 18.0, 6.0, 7.0, 15.0)
PHONES = DutyProfile("8517.1200", "Mobile phones", 0.0, 18.0, 5.5)
SHIRTS = DutyProfile("6109.1000", "Cotton T-shirts", 20.0, 18.0, 5.5)


class TestDutyProfile:
    """Tests for DutyProfile"""

    def test_create(self):
        p = DutyProfile("0808.1000", "Apples", 20.0, 18.0, 5.5)
        assert p.hs_code == "0808.1000"
        assert p.customs_duty_rate == 20.0

    def test_total_effective_rates(self):
        p = DutyProfile("0808.1000", "Apples", 20.0, 18.0, 5.5, 7.0, 15.0)
        assert p.total_effective_rates == 65.5

    def test_zero_rates(self):
        p = DutyProfile("0101.2100", "Horses", 0.0, 0.0, 0.0)
        assert p.total_effective_rates == 0.0


class TestDutyComparator:
    """Tests for DutyComparator"""

    def test_compare_two_codes(self):
        result = DutyComparator.compare(
            [APPLES, HORSES],
            quantity=100, unit="kg", unit_value=10.0,
            currency="USD", exchange_rate=280.0
        )
        assert result.item_count == 2
        assert result.cheapest_code != ""
        assert result.most_expensive_code != ""

    def test_compare_five_codes(self):
        """Acceptance criteria: compare up to 5 HS codes"""
        result = DutyComparator.compare(
            [APPLES, HORSES, VEHICLES, PHONES, SHIRTS],
            quantity=100, unit="kg", unit_value=10.0,
            currency="USD", exchange_rate=280.0
        )
        assert result.item_count == 5

    def test_single_code(self):
        result = DutyComparator.compare(
            [APPLES],
            quantity=100, unit="kg", unit_value=10.0,
            currency="USD", exchange_rate=280.0
        )
        assert result.item_count == 1
        assert result.items[0].is_cheapest is True

    def test_exceeds_max_codes(self):
        profiles = [APPLES, HORSES, VEHICLES, PHONES, SHIRTS,
                    DutyProfile("9999.9999", "Extra", 10.0, 18.0, 5.5)]
        with pytest.raises(ValueError, match="Maximum"):
            DutyComparator.compare(
                profiles, quantity=100, unit="kg", unit_value=10.0,
                currency="USD", exchange_rate=280.0
            )

    def test_empty_profiles(self):
        with pytest.raises(ValueError, match="At least one"):
            DutyComparator.compare(
                [], quantity=100, unit="kg", unit_value=10.0,
                currency="USD", exchange_rate=280.0
            )

    def test_negative_quantity(self):
        with pytest.raises(ValueError, match="positive"):
            DutyComparator.compare(
                [APPLES], quantity=-1, unit="kg", unit_value=10.0,
                currency="USD", exchange_rate=280.0
            )

    def test_zero_exchange_rate(self):
        with pytest.raises(ValueError, match="positive"):
            DutyComparator.compare(
                [APPLES], quantity=100, unit="kg", unit_value=10.0,
                currency="USD", exchange_rate=0
            )


class TestComparisonRanking:
    """Tests for comparison ranking"""

    def test_ranked_by_cost(self):
        result = DutyComparator.compare(
            [APPLES, HORSES],
            quantity=100, unit="kg", unit_value=10.0,
            currency="USD", exchange_rate=280.0
        )
        # Horses (0% CD) should be cheaper than Apples (20% CD)
        assert result.items[0].hs_code == "0101.2100"  # Cheapest
        assert result.items[0].is_cheapest is True

    def test_most_expensive_marked(self):
        result = DutyComparator.compare(
            [APPLES, HORSES, VEHICLES],
            quantity=100, unit="kg", unit_value=10.0,
            currency="USD", exchange_rate=280.0
        )
        # Vehicles (50% CD + 7% AD + 15% RD) should be most expensive
        assert result.items[-1].hs_code == "8703.2300"
        assert result.items[-1].is_most_expensive is True

    def test_rank_numbers(self):
        result = DutyComparator.compare(
            [APPLES, HORSES, VEHICLES],
            quantity=100, unit="kg", unit_value=10.0,
            currency="USD", exchange_rate=280.0
        )
        ranks = [item.rank for item in result.items]
        assert ranks == [1, 2, 3]

    def test_max_savings(self):
        result = DutyComparator.compare(
            [APPLES, HORSES],
            quantity=100, unit="kg", unit_value=10.0,
            currency="USD", exchange_rate=280.0
        )
        assert result.max_savings > 0
        assert result.max_savings == (
            result.items[-1].total_landed_cost - result.items[0].total_landed_cost
        )

    def test_difference_from_cheapest(self):
        result = DutyComparator.compare(
            [APPLES, HORSES, VEHICLES],
            quantity=100, unit="kg", unit_value=10.0,
            currency="USD", exchange_rate=280.0
        )
        assert result.items[0].difference_from_cheapest == 0.0
        assert result.items[1].difference_from_cheapest > 0
        assert result.items[2].difference_from_cheapest > result.items[1].difference_from_cheapest


class TestComparisonCalculations:
    """Tests for mathematical accuracy"""

    def test_same_cif_for_all(self):
        """All items should have same CIF since inputs are shared"""
        result = DutyComparator.compare(
            [APPLES, HORSES, VEHICLES],
            quantity=100, unit="kg", unit_value=10.0,
            currency="USD", exchange_rate=280.0
        )
        cif_values = set(item.cif_value_pkr for item in result.items)
        assert len(cif_values) == 1
        assert 280000.0 in cif_values

    def test_customs_duty_calculation(self):
        """Verify CD = CIF x CD%"""
        result = DutyComparator.compare(
            [APPLES],
            quantity=100, unit="kg", unit_value=10.0,
            currency="USD", exchange_rate=280.0
        )
        item = result.items[0]
        expected_cd = 280000.0 * 0.20
        assert abs(item.customs_duty_amount - expected_cd) < 0.01

    def test_sales_tax_base(self):
        """Verify ST Base = CIF + CD + AD + RD"""
        result = DutyComparator.compare(
            [VEHICLES],
            quantity=1, unit="units", unit_value=25000.0,
            currency="USD", exchange_rate=280.0
        )
        item = result.items[0]
        expected_base = (item.cif_value_pkr + item.customs_duty_amount +
                        item.additional_duty_amount + item.regulatory_duty_amount)
        assert abs(item.sales_tax_base - expected_base) < 0.01

    def test_total_duties_sum(self):
        """Verify Total = CD + AD + RD + ST + IT"""
        result = DutyComparator.compare(
            [VEHICLES],
            quantity=1, unit="units", unit_value=25000.0,
            currency="USD", exchange_rate=280.0
        )
        item = result.items[0]
        expected = (item.customs_duty_amount + item.additional_duty_amount +
                   item.regulatory_duty_amount + item.sales_tax_amount +
                   item.income_tax_amount)
        assert abs(item.total_duties - expected) < 0.01

    def test_landed_cost(self):
        """Verify Landed = CIF + Total Duties"""
        result = DutyComparator.compare(
            [APPLES],
            quantity=100, unit="kg", unit_value=10.0,
            currency="USD", exchange_rate=280.0
        )
        item = result.items[0]
        assert abs(item.total_landed_cost - (item.cif_value_pkr + item.total_duties)) < 0.01

    def test_zero_duty_code(self):
        """0% CD should result in lower total"""
        result = DutyComparator.compare(
            [HORSES],
            quantity=100, unit="kg", unit_value=10.0,
            currency="USD", exchange_rate=280.0
        )
        item = result.items[0]
        assert item.customs_duty_amount == 0.0
        assert item.total_duties > 0  # Still has ST + IT

    def test_effective_rate(self):
        result = DutyComparator.compare(
            [APPLES],
            quantity=100, unit="kg", unit_value=10.0,
            currency="USD", exchange_rate=280.0
        )
        item = result.items[0]
        expected = item.total_duties / item.cif_value_pkr * 100
        assert abs(item.effective_duty_rate - round(expected, 2)) < 0.01

    def test_with_freight_insurance(self):
        result = DutyComparator.compare(
            [APPLES],
            quantity=100, unit="kg", unit_value=10.0,
            currency="USD", exchange_rate=280.0,
            freight=50.0, insurance=10.0
        )
        item = result.items[0]
        # CIF = (100*10 + 50 + 10) * 280
        expected_cif = 1060.0 * 280.0
        assert abs(item.cif_value_pkr - expected_cif) < 0.01


class TestComparisonSerialization:
    """Tests for serialization"""

    def test_comparison_to_dict(self):
        result = DutyComparator.compare(
            [APPLES, HORSES],
            quantity=100, unit="kg", unit_value=10.0,
            currency="USD", exchange_rate=280.0
        )
        d = result.to_dict()
        assert "comparison_id" in d
        assert "results" in d
        assert len(d["results"]) == 2
        assert "summary" in d

    def test_item_to_dict(self):
        result = DutyComparator.compare(
            [APPLES],
            quantity=100, unit="kg", unit_value=10.0,
            currency="USD", exchange_rate=280.0
        )
        d = result.items[0].to_dict()
        assert "hs_code" in d
        assert "rates" in d
        assert "amounts" in d
        assert "rank" in d
