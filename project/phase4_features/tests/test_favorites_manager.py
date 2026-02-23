"""
Phase 4: Features - Favorites Manager Tests

High-grade tests for HS code favorites/bookmarks storage.
"""

import pytest
import os
import json
import tempfile
from favorites_manager import FavoritesManager, Favorite


@pytest.fixture
def temp_db():
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    yield path
    if os.path.exists(path):
        os.unlink(path)


@pytest.fixture
def manager(temp_db):
    return FavoritesManager(db_path=temp_db)


class TestFavoriteDataclass:
    """Tests for Favorite dataclass"""

    def test_create(self):
        fav = Favorite(
            id=1, hs_code="0808.1000", description="Fresh apples",
            notes="Common import", tags=["food", "fruit"],
            customs_duty_rate=20.0, sales_tax_rate=18.0, income_tax_rate=5.5
        )
        assert fav.hs_code == "0808.1000"
        assert fav.tags == ["food", "fruit"]

    def test_to_dict(self):
        fav = Favorite(
            id=1, hs_code="0808.1000", description="Apples",
            tags=["food"], customs_duty_rate=20.0
        )
        d = fav.to_dict()
        assert d["hs_code"] == "0808.1000"
        assert d["rates"]["customs_duty"] == 20.0
        assert d["tags"] == ["food"]

    def test_from_dict(self):
        data = {
            "id": 1, "hs_code": "0808.1000", "description": "Apples",
            "notes": "", "tags": ["food"],
            "rates": {"customs_duty": 20.0, "sales_tax": 18.0, "income_tax": 5.5},
            "unit_of_measure": "kg", "created_at": "", "updated_at": "", "use_count": 0
        }
        fav = Favorite.from_dict(data)
        assert fav.hs_code == "0808.1000"
        assert fav.customs_duty_rate == 20.0

    def test_from_dict_missing_rates(self):
        data = {"id": 1, "hs_code": "0808.1000", "description": "Apples"}
        fav = Favorite.from_dict(data)
        assert fav.customs_duty_rate is None


class TestFavoritesManager:
    """Tests for FavoritesManager CRUD"""

    def test_add(self, manager):
        fav = manager.add("0808.1000", "Fresh apples", notes="Test")
        assert fav is not None
        assert fav.hs_code == "0808.1000"
        assert fav.description == "Fresh apples"

    def test_add_normalizes_code(self, manager):
        fav = manager.add("08081000", "Apples")
        assert fav.hs_code == "0808.1000"

    def test_add_with_tags(self, manager):
        fav = manager.add("0808.1000", "Apples", tags=["food", "fruit"])
        retrieved = manager.get("0808.1000")
        assert retrieved.tags == ["food", "fruit"]

    def test_add_with_rates(self, manager):
        fav = manager.add(
            "0808.1000", "Apples",
            customs_duty_rate=20.0, sales_tax_rate=18.0, income_tax_rate=5.5
        )
        retrieved = manager.get("0808.1000")
        assert retrieved.customs_duty_rate == 20.0
        assert retrieved.sales_tax_rate == 18.0

    def test_add_duplicate_updates(self, manager):
        manager.add("0808.1000", "Apples v1")
        manager.add("0808.1000", "Apples v2")
        assert manager.count() == 1
        retrieved = manager.get("0808.1000")
        assert retrieved.description == "Apples v2"

    def test_get(self, manager):
        manager.add("0808.1000", "Apples")
        fav = manager.get("0808.1000")
        assert fav is not None
        assert fav.description == "Apples"

    def test_get_nonexistent(self, manager):
        assert manager.get("9999.9999") is None

    def test_get_by_id(self, manager):
        added = manager.add("0808.1000", "Apples")
        fav = manager.get_by_id(added.id)
        assert fav is not None
        assert fav.hs_code == "0808.1000"

    def test_remove(self, manager):
        manager.add("0808.1000", "Apples")
        result = manager.remove("0808.1000")
        assert result is True
        assert manager.get("0808.1000") is None

    def test_remove_nonexistent(self, manager):
        assert manager.remove("9999.9999") is False

    def test_count(self, manager):
        assert manager.count() == 0
        manager.add("0808.1000", "Apples")
        assert manager.count() == 1
        manager.add("8517.1200", "Phones")
        assert manager.count() == 2

    def test_clear(self, manager):
        manager.add("0808.1000", "Apples")
        manager.add("8517.1200", "Phones")
        count = manager.clear()
        assert count == 2
        assert manager.count() == 0

    def test_is_favorite(self, manager):
        manager.add("0808.1000", "Apples")
        assert manager.is_favorite("0808.1000") is True
        assert manager.is_favorite("9999.9999") is False

    def test_is_favorite_normalized(self, manager):
        manager.add("0808.1000", "Apples")
        assert manager.is_favorite("08081000") is True


class TestFavoritesOrdering:
    """Tests for ordering and sorting"""

    def test_get_all_by_use_count(self, manager):
        manager.add("0808.1000", "Apples")
        manager.add("8517.1200", "Phones")
        manager.record_use("8517.1200")
        manager.record_use("8517.1200")

        all_favs = manager.get_all(order_by="use_count")
        assert all_favs[0].hs_code == "8517.1200"  # Most used first

    def test_get_all_by_hs_code(self, manager):
        manager.add("8517.1200", "Phones")
        manager.add("0808.1000", "Apples")

        all_favs = manager.get_all(order_by="hs_code")
        assert all_favs[0].hs_code == "0808.1000"

    def test_get_most_used(self, manager):
        manager.add("0808.1000", "Apples")
        manager.add("8517.1200", "Phones")
        manager.add("6109.1000", "Shirts")
        manager.record_use("8517.1200")
        manager.record_use("8517.1200")
        manager.record_use("6109.1000")

        most_used = manager.get_most_used(limit=2)
        assert len(most_used) == 2
        assert most_used[0].hs_code == "8517.1200"


class TestFavoritesSearch:
    """Tests for search functionality"""

    def test_search_by_code(self, manager):
        manager.add("0808.1000", "Apples")
        manager.add("0808.2000", "Pears")
        manager.add("8517.1200", "Phones")

        results = manager.search("0808")
        assert len(results) == 2

    def test_search_by_description(self, manager):
        manager.add("0808.1000", "Fresh apples")
        manager.add("8517.1200", "Mobile phones")

        results = manager.search("apples")
        assert len(results) == 1
        assert results[0].hs_code == "0808.1000"

    def test_search_by_notes(self, manager):
        manager.add("0808.1000", "Apples", notes="common import item")
        results = manager.search("common")
        assert len(results) == 1

    def test_search_case_insensitive(self, manager):
        manager.add("0808.1000", "Fresh Apples")
        results = manager.search("APPLES")
        assert len(results) == 1

    def test_search_no_results(self, manager):
        manager.add("0808.1000", "Apples")
        results = manager.search("electronics")
        assert len(results) == 0

    def test_get_by_tag(self, manager):
        manager.add("0808.1000", "Apples", tags=["food", "fruit"])
        manager.add("8517.1200", "Phones", tags=["electronics"])

        results = manager.get_by_tag("food")
        assert len(results) == 1
        assert results[0].hs_code == "0808.1000"

    def test_get_all_tags(self, manager):
        manager.add("0808.1000", "Apples", tags=["food", "fruit"])
        manager.add("8517.1200", "Phones", tags=["electronics", "tech"])

        tags = manager.get_all_tags()
        assert "food" in tags
        assert "electronics" in tags
        assert len(tags) == 4


class TestFavoritesUsageTracking:
    """Tests for usage tracking"""

    def test_record_use(self, manager):
        manager.add("0808.1000", "Apples")
        manager.record_use("0808.1000")
        manager.record_use("0808.1000")

        fav = manager.get("0808.1000")
        assert fav.use_count == 2

    def test_record_use_nonexistent(self, manager):
        result = manager.record_use("9999.9999")
        assert result is False


class TestFavoritesImportExport:
    """Tests for JSON import/export"""

    def test_export_json(self, manager):
        manager.add("0808.1000", "Apples", tags=["food"])
        manager.add("8517.1200", "Phones", tags=["tech"])

        json_str = manager.export_json()
        data = json.loads(json_str)

        assert data["version"] == "1.0"
        assert data["count"] == 2
        assert len(data["favorites"]) == 2

    def test_import_json(self, manager):
        json_data = json.dumps({
            "version": "1.0",
            "favorites": [
                {"hs_code": "0808.1000", "description": "Apples",
                 "notes": "", "tags": ["food"], "rates": {"customs_duty": 20.0},
                 "unit_of_measure": "kg"},
                {"hs_code": "8517.1200", "description": "Phones",
                 "notes": "", "tags": [], "rates": {},
                 "unit_of_measure": "units"}
            ]
        })

        imported, skipped = manager.import_json(json_data)
        assert imported == 2
        assert skipped == 0
        assert manager.count() == 2

    def test_import_invalid_json(self, manager):
        imported, skipped = manager.import_json("not valid json")
        assert imported == 0

    def test_roundtrip(self, manager):
        manager.add("0808.1000", "Apples", tags=["food"], customs_duty_rate=20.0)
        manager.add("8517.1200", "Phones", tags=["tech"])

        exported = manager.export_json()
        manager.clear()
        assert manager.count() == 0

        imported, _ = manager.import_json(exported)
        assert imported == 2
        assert manager.get("0808.1000").customs_duty_rate == 20.0


class TestFavoritesCapacity:
    """Tests for capacity limits"""

    def test_max_capacity(self, temp_db):
        manager = FavoritesManager(db_path=temp_db, max_favorites=5)

        for i in range(5):
            result = manager.add(f"{i:04d}.0000", f"Item {i}")
            assert result is not None

        # 6th should fail
        result = manager.add("9999.0000", "Overflow")
        assert result is None
        assert manager.count() == 5

    def test_500_favorites(self, temp_db):
        """Acceptance criteria: save/load 500+ entries"""
        manager = FavoritesManager(db_path=temp_db, max_favorites=600)

        for i in range(500):
            manager.add(f"{i:04d}.{i % 10000:04d}", f"Item {i}")

        assert manager.count() == 500


class TestFavoritesPersistence:
    """Tests for cross-instance persistence"""

    def test_persists(self, temp_db):
        m1 = FavoritesManager(db_path=temp_db)
        m1.add("0808.1000", "Apples", tags=["food"])

        m2 = FavoritesManager(db_path=temp_db)
        fav = m2.get("0808.1000")
        assert fav is not None
        assert fav.tags == ["food"]
