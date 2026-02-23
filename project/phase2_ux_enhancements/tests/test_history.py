"""
Phase 2: UX Enhancements - History Manager Tests

Comprehensive tests for calculation history management:
- FIFO storage with capacity limits
- Search and filter functionality
- CSV export
- JSON serialization/deserialization
"""

import pytest
import json
from datetime import datetime
from history_manager import (
    HistoryManager, HistoryEntry, InputSummary, ResultSummary,
    CalculationType
)


class TestHistoryEntry:
    """Tests for HistoryEntry dataclass"""

    def test_create_import_entry(self):
        """Test creating an import history entry"""
        entry = HistoryEntry(
            id="test-123",
            timestamp="2026-01-25T10:00:00",
            calc_type=CalculationType.IMPORT,
            input_summary=InputSummary(
                hs_code="0808.1000",
                description="Fresh apples",
                quantity=100.0,
                unit="kg",
                unit_value=10.0,
                currency="USD",
                exchange_rate=280.0
            ),
            result_summary=ResultSummary(
                cif_pkr=280000.0,
                total_duties=131880.0,
                landed_cost=411880.0
            )
        )

        assert entry.id == "test-123"
        assert entry.calc_type == CalculationType.IMPORT
        assert entry.input_summary.hs_code == "0808.1000"
        assert entry.result_summary.landed_cost == 411880.0

    def test_create_export_entry(self):
        """Test creating an export history entry"""
        entry = HistoryEntry(
            id="test-456",
            timestamp="2026-01-25T11:00:00",
            calc_type=CalculationType.EXPORT,
            input_summary=InputSummary(
                hs_code="5201.0000",
                description="Raw cotton",
                quantity=1000.0,
                unit="kg",
                unit_value=2.0,
                currency="USD",
                exchange_rate=278.0
            ),
            result_summary=ResultSummary(
                fob_pkr=556000.0,
                net_proceeds=556000.0
            )
        )

        assert entry.calc_type == CalculationType.EXPORT
        assert entry.result_summary.net_proceeds == 556000.0

    def test_to_dict(self):
        """Test converting entry to dictionary"""
        entry = HistoryEntry(
            id="test-789",
            timestamp="2026-01-25T12:00:00",
            calc_type=CalculationType.IMPORT,
            input_summary=InputSummary(
                hs_code="0808.1000",
                description="Apples",
                quantity=50.0,
                unit="kg",
                unit_value=15.0,
                currency="USD",
                exchange_rate=280.0
            ),
            result_summary=ResultSummary(
                cif_pkr=210000.0,
                total_duties=98910.0,
                landed_cost=308910.0
            )
        )

        data = entry.to_dict()

        assert data['id'] == "test-789"
        assert data['type'] == "import"
        assert data['input']['hs_code'] == "0808.1000"
        assert data['result']['landed_cost'] == 308910.0

    def test_from_dict(self):
        """Test creating entry from dictionary"""
        data = {
            'id': 'from-dict-123',
            'timestamp': '2026-01-25T13:00:00',
            'type': 'export',
            'input': {
                'hs_code': '5201.0000',
                'description': 'Cotton',
                'quantity': 500.0,
                'unit': 'kg',
                'unit_value': 2.5,
                'currency': 'USD',
                'exchange_rate': 278.0
            },
            'result': {
                'cif_pkr': 0.0,
                'fob_pkr': 347500.0,
                'total_duties': 0.0,
                'landed_cost': 0.0,
                'net_proceeds': 347500.0
            }
        }

        entry = HistoryEntry.from_dict(data)

        assert entry.id == 'from-dict-123'
        assert entry.calc_type == CalculationType.EXPORT
        assert entry.input_summary.description == 'Cotton'
        assert entry.result_summary.net_proceeds == 347500.0

    def test_display_title(self):
        """Test display title generation"""
        entry = HistoryEntry(
            id="test",
            timestamp="2026-01-25T10:00:00",
            calc_type=CalculationType.IMPORT,
            input_summary=InputSummary(
                hs_code="0808.1000",
                description="Fresh apples from Washington state orchards",
                quantity=100.0,
                unit="kg",
                unit_value=10.0,
                currency="USD",
                exchange_rate=280.0
            ),
            result_summary=ResultSummary()
        )

        title = entry.get_display_title()

        assert "0808.1000" in title
        # Should truncate long descriptions
        assert len(title) <= 45  # HS code + " - " + 30 chars

    def test_display_subtitle_import(self):
        """Test display subtitle for import"""
        entry = HistoryEntry(
            id="test",
            timestamp="2026-01-25T10:00:00",
            calc_type=CalculationType.IMPORT,
            input_summary=InputSummary(
                hs_code="0808.1000",
                description="Apples",
                quantity=100.0,
                unit="kg",
                unit_value=10.0,
                currency="USD",
                exchange_rate=280.0
            ),
            result_summary=ResultSummary(landed_cost=411880.0)
        )

        subtitle = entry.get_display_subtitle()

        assert "Landed" in subtitle
        assert "411,880" in subtitle

    def test_display_subtitle_export(self):
        """Test display subtitle for export"""
        entry = HistoryEntry(
            id="test",
            timestamp="2026-01-25T10:00:00",
            calc_type=CalculationType.EXPORT,
            input_summary=InputSummary(
                hs_code="5201.0000",
                description="Cotton",
                quantity=1000.0,
                unit="kg",
                unit_value=2.0,
                currency="USD",
                exchange_rate=278.0
            ),
            result_summary=ResultSummary(net_proceeds=556000.0)
        )

        subtitle = entry.get_display_subtitle()

        assert "Proceeds" in subtitle
        assert "556,000" in subtitle


class TestHistoryManager:
    """Tests for HistoryManager class"""

    def test_init_default_capacity(self):
        """Test initialization with default capacity"""
        manager = HistoryManager()

        assert manager.capacity == 50
        assert manager.count == 0
        assert manager.is_empty

    def test_init_custom_capacity(self):
        """Test initialization with custom capacity"""
        manager = HistoryManager(capacity=100)

        assert manager.capacity == 100

    def test_add_import_calculation(self):
        """Test adding import calculation to history"""
        manager = HistoryManager()

        entry = manager.add_import_calculation(
            hs_code="0808.1000",
            description="Fresh apples",
            quantity=100.0,
            unit="kg",
            unit_value=10.0,
            currency="USD",
            exchange_rate=280.0,
            cif_pkr=280000.0,
            total_duties=131880.0,
            landed_cost=411880.0
        )

        assert manager.count == 1
        assert not manager.is_empty
        assert entry.id is not None
        assert entry.calc_type == CalculationType.IMPORT
        assert entry.result_summary.landed_cost == 411880.0

    def test_add_export_calculation(self):
        """Test adding export calculation to history"""
        manager = HistoryManager()

        entry = manager.add_export_calculation(
            hs_code="5201.0000",
            description="Raw cotton",
            quantity=1000.0,
            unit="kg",
            unit_value=2.0,
            currency="USD",
            exchange_rate=278.0,
            fob_pkr=556000.0,
            net_proceeds=556000.0
        )

        assert manager.count == 1
        assert entry.calc_type == CalculationType.EXPORT
        assert entry.result_summary.net_proceeds == 556000.0

    def test_fifo_eviction(self):
        """Test FIFO eviction when capacity is reached"""
        manager = HistoryManager(capacity=3)

        # Add 3 entries
        entry1 = manager.add_import_calculation(
            hs_code="0808.1000", description="Apples batch 1",
            quantity=100, unit="kg", unit_value=10, currency="USD",
            exchange_rate=280, cif_pkr=280000, total_duties=131880,
            landed_cost=411880
        )
        id1 = entry1.id

        manager.add_import_calculation(
            hs_code="0808.1000", description="Apples batch 2",
            quantity=200, unit="kg", unit_value=10, currency="USD",
            exchange_rate=280, cif_pkr=560000, total_duties=263760,
            landed_cost=823760
        )

        manager.add_import_calculation(
            hs_code="0808.1000", description="Apples batch 3",
            quantity=300, unit="kg", unit_value=10, currency="USD",
            exchange_rate=280, cif_pkr=840000, total_duties=395640,
            landed_cost=1235640
        )

        assert manager.count == 3

        # Add 4th entry - should evict first
        manager.add_import_calculation(
            hs_code="0808.1000", description="Apples batch 4",
            quantity=400, unit="kg", unit_value=10, currency="USD",
            exchange_rate=280, cif_pkr=1120000, total_duties=527520,
            landed_cost=1647520
        )

        assert manager.count == 3  # Still at capacity
        assert manager.get_entry(id1) is None  # First entry evicted

    def test_get_entry(self):
        """Test retrieving entry by ID"""
        manager = HistoryManager()

        entry = manager.add_import_calculation(
            hs_code="0808.1000", description="Apples",
            quantity=100, unit="kg", unit_value=10, currency="USD",
            exchange_rate=280, cif_pkr=280000, total_duties=131880,
            landed_cost=411880
        )

        retrieved = manager.get_entry(entry.id)

        assert retrieved is not None
        assert retrieved.id == entry.id

    def test_get_entry_not_found(self):
        """Test retrieving non-existent entry"""
        manager = HistoryManager()

        result = manager.get_entry("nonexistent-id")

        assert result is None

    def test_get_all_default_order(self):
        """Test get all entries (newest first by default)"""
        manager = HistoryManager()

        manager.add_import_calculation(
            hs_code="0808.1000", description="First",
            quantity=100, unit="kg", unit_value=10, currency="USD",
            exchange_rate=280, cif_pkr=280000, total_duties=131880,
            landed_cost=411880
        )

        manager.add_import_calculation(
            hs_code="0808.1000", description="Second",
            quantity=200, unit="kg", unit_value=10, currency="USD",
            exchange_rate=280, cif_pkr=560000, total_duties=263760,
            landed_cost=823760
        )

        entries = manager.get_all()

        assert len(entries) == 2
        assert entries[0].input_summary.description == "Second"  # Newest first
        assert entries[1].input_summary.description == "First"

    def test_get_all_oldest_first(self):
        """Test get all entries oldest first"""
        manager = HistoryManager()

        manager.add_import_calculation(
            hs_code="0808.1000", description="First",
            quantity=100, unit="kg", unit_value=10, currency="USD",
            exchange_rate=280, cif_pkr=280000, total_duties=131880,
            landed_cost=411880
        )

        manager.add_import_calculation(
            hs_code="0808.1000", description="Second",
            quantity=200, unit="kg", unit_value=10, currency="USD",
            exchange_rate=280, cif_pkr=560000, total_duties=263760,
            landed_cost=823760
        )

        entries = manager.get_all(reverse=False)

        assert entries[0].input_summary.description == "First"  # Oldest first

    def test_get_recent(self):
        """Test getting recent entries"""
        manager = HistoryManager()

        for i in range(10):
            manager.add_import_calculation(
                hs_code=f"0808.100{i}", description=f"Batch {i}",
                quantity=100, unit="kg", unit_value=10, currency="USD",
                exchange_rate=280, cif_pkr=280000, total_duties=131880,
                landed_cost=411880
            )

        recent = manager.get_recent(5)

        assert len(recent) == 5
        assert "Batch 9" in recent[0].input_summary.description  # Most recent

    def test_filter_by_type_import(self):
        """Test filtering by import type"""
        manager = HistoryManager()

        manager.add_import_calculation(
            hs_code="0808.1000", description="Import 1",
            quantity=100, unit="kg", unit_value=10, currency="USD",
            exchange_rate=280, cif_pkr=280000, total_duties=131880,
            landed_cost=411880
        )

        manager.add_export_calculation(
            hs_code="5201.0000", description="Export 1",
            quantity=1000, unit="kg", unit_value=2, currency="USD",
            exchange_rate=278, fob_pkr=556000, net_proceeds=556000
        )

        manager.add_import_calculation(
            hs_code="0808.1000", description="Import 2",
            quantity=200, unit="kg", unit_value=10, currency="USD",
            exchange_rate=280, cif_pkr=560000, total_duties=263760,
            landed_cost=823760
        )

        imports = manager.filter_by_type(CalculationType.IMPORT)

        assert len(imports) == 2
        assert all(e.calc_type == CalculationType.IMPORT for e in imports)

    def test_filter_by_type_export(self):
        """Test filtering by export type"""
        manager = HistoryManager()

        manager.add_import_calculation(
            hs_code="0808.1000", description="Import",
            quantity=100, unit="kg", unit_value=10, currency="USD",
            exchange_rate=280, cif_pkr=280000, total_duties=131880,
            landed_cost=411880
        )

        manager.add_export_calculation(
            hs_code="5201.0000", description="Export",
            quantity=1000, unit="kg", unit_value=2, currency="USD",
            exchange_rate=278, fob_pkr=556000, net_proceeds=556000
        )

        exports = manager.filter_by_type(CalculationType.EXPORT)

        assert len(exports) == 1
        assert exports[0].calc_type == CalculationType.EXPORT

    def test_search_by_hs_code(self):
        """Test searching by HS code"""
        manager = HistoryManager()

        manager.add_import_calculation(
            hs_code="0808.1000", description="Apples",
            quantity=100, unit="kg", unit_value=10, currency="USD",
            exchange_rate=280, cif_pkr=280000, total_duties=131880,
            landed_cost=411880
        )

        manager.add_import_calculation(
            hs_code="0809.1000", description="Apricots",
            quantity=100, unit="kg", unit_value=15, currency="USD",
            exchange_rate=280, cif_pkr=420000, total_duties=197820,
            landed_cost=617820
        )

        results = manager.search("0808")

        assert len(results) == 1
        assert results[0].input_summary.hs_code == "0808.1000"

    def test_search_by_description(self):
        """Test searching by description"""
        manager = HistoryManager()

        manager.add_import_calculation(
            hs_code="0808.1000", description="Fresh apples from USA",
            quantity=100, unit="kg", unit_value=10, currency="USD",
            exchange_rate=280, cif_pkr=280000, total_duties=131880,
            landed_cost=411880
        )

        manager.add_import_calculation(
            hs_code="0808.2000", description="Fresh pears from China",
            quantity=100, unit="kg", unit_value=12, currency="USD",
            exchange_rate=280, cif_pkr=336000, total_duties=158256,
            landed_cost=494256
        )

        results = manager.search("apples")

        assert len(results) == 1
        assert "apples" in results[0].input_summary.description.lower()

    def test_search_case_insensitive(self):
        """Test search is case insensitive"""
        manager = HistoryManager()

        manager.add_import_calculation(
            hs_code="0808.1000", description="FRESH APPLES",
            quantity=100, unit="kg", unit_value=10, currency="USD",
            exchange_rate=280, cif_pkr=280000, total_duties=131880,
            landed_cost=411880
        )

        results = manager.search("fresh apples")

        assert len(results) == 1

    def test_search_no_results(self):
        """Test search with no matching results"""
        manager = HistoryManager()

        manager.add_import_calculation(
            hs_code="0808.1000", description="Apples",
            quantity=100, unit="kg", unit_value=10, currency="USD",
            exchange_rate=280, cif_pkr=280000, total_duties=131880,
            landed_cost=411880
        )

        results = manager.search("bananas")

        assert len(results) == 0

    def test_delete_entry(self):
        """Test deleting an entry"""
        manager = HistoryManager()

        entry = manager.add_import_calculation(
            hs_code="0808.1000", description="Apples",
            quantity=100, unit="kg", unit_value=10, currency="USD",
            exchange_rate=280, cif_pkr=280000, total_duties=131880,
            landed_cost=411880
        )

        assert manager.count == 1

        result = manager.delete_entry(entry.id)

        assert result is True
        assert manager.count == 0
        assert manager.get_entry(entry.id) is None

    def test_delete_nonexistent_entry(self):
        """Test deleting non-existent entry"""
        manager = HistoryManager()

        result = manager.delete_entry("nonexistent-id")

        assert result is False

    def test_clear(self):
        """Test clearing all history"""
        manager = HistoryManager()

        for i in range(5):
            manager.add_import_calculation(
                hs_code=f"0808.100{i}", description=f"Batch {i}",
                quantity=100, unit="kg", unit_value=10, currency="USD",
                exchange_rate=280, cif_pkr=280000, total_duties=131880,
                landed_cost=411880
            )

        assert manager.count == 5

        cleared = manager.clear()

        assert cleared == 5
        assert manager.count == 0
        assert manager.is_empty


class TestHistoryManagerSerialization:
    """Tests for JSON serialization"""

    def test_to_json(self):
        """Test serializing history to JSON"""
        manager = HistoryManager()

        manager.add_import_calculation(
            hs_code="0808.1000", description="Apples",
            quantity=100, unit="kg", unit_value=10, currency="USD",
            exchange_rate=280, cif_pkr=280000, total_duties=131880,
            landed_cost=411880
        )

        json_str = manager.to_json()

        # Should be valid JSON
        data = json.loads(json_str)
        assert len(data) == 1
        assert data[0]['input']['hs_code'] == "0808.1000"

    def test_from_json(self):
        """Test loading history from JSON"""
        json_data = '''[
            {
                "id": "test-1",
                "timestamp": "2026-01-25T10:00:00",
                "type": "import",
                "input": {
                    "hs_code": "0808.1000",
                    "description": "Apples",
                    "quantity": 100.0,
                    "unit": "kg",
                    "unit_value": 10.0,
                    "currency": "USD",
                    "exchange_rate": 280.0
                },
                "result": {
                    "cif_pkr": 280000.0,
                    "fob_pkr": 0.0,
                    "total_duties": 131880.0,
                    "landed_cost": 411880.0,
                    "net_proceeds": 0.0
                }
            }
        ]'''

        manager = HistoryManager()
        count = manager.from_json(json_data)

        assert count == 1
        assert manager.count == 1

        entries = manager.get_all()
        assert entries[0].input_summary.hs_code == "0808.1000"

    def test_from_json_invalid(self):
        """Test loading invalid JSON raises error"""
        manager = HistoryManager()

        with pytest.raises(ValueError) as excinfo:
            manager.from_json("not valid json")

        assert "Invalid history JSON" in str(excinfo.value)

    def test_roundtrip_serialization(self):
        """Test serialization roundtrip preserves data"""
        manager1 = HistoryManager()

        manager1.add_import_calculation(
            hs_code="0808.1000", description="Apples",
            quantity=100, unit="kg", unit_value=10, currency="USD",
            exchange_rate=280, cif_pkr=280000, total_duties=131880,
            landed_cost=411880
        )

        manager1.add_export_calculation(
            hs_code="5201.0000", description="Cotton",
            quantity=1000, unit="kg", unit_value=2, currency="USD",
            exchange_rate=278, fob_pkr=556000, net_proceeds=556000
        )

        # Serialize
        json_str = manager1.to_json()

        # Load into new manager
        manager2 = HistoryManager()
        manager2.from_json(json_str)

        assert manager2.count == 2

        entries = manager2.get_all()
        assert entries[0].calc_type == CalculationType.EXPORT  # Newest first
        assert entries[1].calc_type == CalculationType.IMPORT


class TestHistoryManagerCSVExport:
    """Tests for CSV export functionality"""

    def test_export_to_csv_empty(self):
        """Test CSV export with empty history"""
        manager = HistoryManager()

        csv_str = manager.export_to_csv()

        # Should have header row only
        lines = csv_str.strip().split('\n')
        assert len(lines) == 1  # Just header

    def test_export_to_csv_with_data(self):
        """Test CSV export with entries"""
        manager = HistoryManager()

        manager.add_import_calculation(
            hs_code="0808.1000", description="Apples",
            quantity=100, unit="kg", unit_value=10, currency="USD",
            exchange_rate=280, cif_pkr=280000, total_duties=131880,
            landed_cost=411880
        )

        csv_str = manager.export_to_csv()

        lines = csv_str.strip().split('\n')
        assert len(lines) == 2  # Header + 1 data row

        # Check header
        assert "HS Code" in lines[0]
        assert "Description" in lines[0]

        # Check data
        assert "0808.1000" in lines[1]
        assert "Apples" in lines[1]

    def test_export_to_csv_multiple_entries(self):
        """Test CSV export with multiple entries"""
        manager = HistoryManager()

        for i in range(5):
            manager.add_import_calculation(
                hs_code=f"0808.100{i}", description=f"Batch {i}",
                quantity=100, unit="kg", unit_value=10, currency="USD",
                exchange_rate=280, cif_pkr=280000, total_duties=131880,
                landed_cost=411880
            )

        csv_str = manager.export_to_csv()

        lines = csv_str.strip().split('\n')
        assert len(lines) == 6  # Header + 5 data rows


class TestHistoryManagerStatistics:
    """Tests for statistics functionality"""

    def test_statistics_empty(self):
        """Test statistics with empty history"""
        manager = HistoryManager()

        stats = manager.get_statistics()

        assert stats['total_entries'] == 0
        assert stats['import_count'] == 0
        assert stats['export_count'] == 0
        assert stats['total_import_value'] == 0
        assert stats['total_export_value'] == 0

    def test_statistics_with_data(self):
        """Test statistics with mixed entries"""
        manager = HistoryManager()

        manager.add_import_calculation(
            hs_code="0808.1000", description="Import 1",
            quantity=100, unit="kg", unit_value=10, currency="USD",
            exchange_rate=280, cif_pkr=280000, total_duties=131880,
            landed_cost=411880
        )

        manager.add_import_calculation(
            hs_code="0808.1000", description="Import 2",
            quantity=200, unit="kg", unit_value=10, currency="USD",
            exchange_rate=280, cif_pkr=560000, total_duties=263760,
            landed_cost=823760
        )

        manager.add_export_calculation(
            hs_code="5201.0000", description="Export 1",
            quantity=1000, unit="kg", unit_value=2, currency="USD",
            exchange_rate=278, fob_pkr=556000, net_proceeds=556000
        )

        stats = manager.get_statistics()

        assert stats['total_entries'] == 3
        assert stats['import_count'] == 2
        assert stats['export_count'] == 1
        assert stats['total_import_value'] == 411880 + 823760
        assert stats['total_export_value'] == 556000
        assert stats['capacity_used'] == "3/50"


class TestHistoryManagerEdgeCases:
    """Edge case tests"""

    def test_empty_description_handled(self):
        """Test that empty description is handled"""
        manager = HistoryManager()

        entry = manager.add_import_calculation(
            hs_code="0808.1000", description="",
            quantity=100, unit="kg", unit_value=10, currency="USD",
            exchange_rate=280, cif_pkr=280000, total_duties=131880,
            landed_cost=411880
        )

        # Should use default description
        assert entry.input_summary.description == "Import calculation"

    def test_full_result_stored(self):
        """Test that full result is stored when provided"""
        manager = HistoryManager()

        full_result = {
            'detailed_breakdown': {'cd': 56000, 'st': 60480, 'it': 15400},
            'verification': 'passed'
        }

        entry = manager.add_import_calculation(
            hs_code="0808.1000", description="Apples",
            quantity=100, unit="kg", unit_value=10, currency="USD",
            exchange_rate=280, cif_pkr=280000, total_duties=131880,
            landed_cost=411880, full_result=full_result
        )

        assert entry.full_result == full_result

    def test_capacity_boundary(self):
        """Test exact capacity boundary"""
        manager = HistoryManager(capacity=2)

        # Add exactly at capacity
        entry1 = manager.add_import_calculation(
            hs_code="0808.1000", description="First",
            quantity=100, unit="kg", unit_value=10, currency="USD",
            exchange_rate=280, cif_pkr=280000, total_duties=131880,
            landed_cost=411880
        )

        entry2 = manager.add_import_calculation(
            hs_code="0808.1000", description="Second",
            quantity=200, unit="kg", unit_value=10, currency="USD",
            exchange_rate=280, cif_pkr=560000, total_duties=263760,
            landed_cost=823760
        )

        assert manager.count == 2
        assert manager.get_entry(entry1.id) is not None
        assert manager.get_entry(entry2.id) is not None

        # Add one more - should evict first
        entry3 = manager.add_import_calculation(
            hs_code="0808.1000", description="Third",
            quantity=300, unit="kg", unit_value=10, currency="USD",
            exchange_rate=280, cif_pkr=840000, total_duties=395640,
            landed_cost=1235640
        )

        assert manager.count == 2
        assert manager.get_entry(entry1.id) is None  # Evicted
        assert manager.get_entry(entry2.id) is not None
        assert manager.get_entry(entry3.id) is not None
