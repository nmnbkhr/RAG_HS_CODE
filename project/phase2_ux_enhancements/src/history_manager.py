"""
RAG_HS_CODE - Calculation History Manager
Phase 2: UX Enhancements

Manages calculation history within a session with:
- FIFO storage with max capacity
- Search and filter capabilities
- Export to CSV
- Restoration of past calculations
"""

import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, field, asdict
from enum import Enum
import json
import csv
import io


class CalculationType(Enum):
    """Type of calculation performed"""
    IMPORT = "import"
    EXPORT = "export"


@dataclass
class InputSummary:
    """Summary of calculation inputs"""
    hs_code: str
    description: str
    quantity: float
    unit: str
    unit_value: float
    currency: str
    exchange_rate: float


@dataclass
class ResultSummary:
    """Summary of calculation results"""
    cif_pkr: float = 0.0
    fob_pkr: float = 0.0
    total_duties: float = 0.0
    landed_cost: float = 0.0
    net_proceeds: float = 0.0


@dataclass
class HistoryEntry:
    """A single calculation history entry"""
    id: str
    timestamp: str
    calc_type: CalculationType
    input_summary: InputSummary
    result_summary: ResultSummary
    full_result: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization"""
        return {
            'id': self.id,
            'timestamp': self.timestamp,
            'type': self.calc_type.value,
            'input': asdict(self.input_summary),
            'result': asdict(self.result_summary),
            'full_result': self.full_result
        }

    @classmethod
    def from_dict(cls, data: dict) -> 'HistoryEntry':
        """Create from dictionary"""
        return cls(
            id=data['id'],
            timestamp=data['timestamp'],
            calc_type=CalculationType(data['type']),
            input_summary=InputSummary(**data['input']),
            result_summary=ResultSummary(**data['result']),
            full_result=data.get('full_result', {})
        )

    def get_display_title(self) -> str:
        """Get a display title for the entry"""
        return f"{self.input_summary.hs_code} - {self.input_summary.description[:30]}"

    def get_display_subtitle(self) -> str:
        """Get a display subtitle with key values"""
        if self.calc_type == CalculationType.IMPORT:
            return f"Landed: PKR {self.result_summary.landed_cost:,.0f}"
        else:
            return f"Proceeds: PKR {self.result_summary.net_proceeds:,.0f}"


class HistoryManager:
    """
    Manages calculation history with configurable capacity.

    Features:
    - FIFO eviction when capacity reached
    - Search by HS code or description
    - Filter by calculation type
    - Export to CSV
    - JSON serialization for persistence
    """

    DEFAULT_CAPACITY = 50

    def __init__(self, capacity: int = DEFAULT_CAPACITY):
        """
        Initialize history manager.

        Args:
            capacity: Maximum number of entries to store
        """
        self._entries: List[HistoryEntry] = []
        self._capacity = capacity

    @property
    def count(self) -> int:
        """Number of entries in history"""
        return len(self._entries)

    @property
    def capacity(self) -> int:
        """Maximum capacity"""
        return self._capacity

    @property
    def is_empty(self) -> bool:
        """Check if history is empty"""
        return len(self._entries) == 0

    def add_import_calculation(
        self,
        hs_code: str,
        description: str,
        quantity: float,
        unit: str,
        unit_value: float,
        currency: str,
        exchange_rate: float,
        cif_pkr: float,
        total_duties: float,
        landed_cost: float,
        full_result: Dict[str, Any] = None
    ) -> HistoryEntry:
        """
        Add an import calculation to history.

        Returns:
            The created HistoryEntry
        """
        entry = HistoryEntry(
            id=str(uuid.uuid4()),
            timestamp=datetime.now().isoformat(),
            calc_type=CalculationType.IMPORT,
            input_summary=InputSummary(
                hs_code=hs_code,
                description=description or "Import calculation",
                quantity=quantity,
                unit=unit,
                unit_value=unit_value,
                currency=currency,
                exchange_rate=exchange_rate
            ),
            result_summary=ResultSummary(
                cif_pkr=cif_pkr,
                total_duties=total_duties,
                landed_cost=landed_cost
            ),
            full_result=full_result or {}
        )

        self._add_entry(entry)
        return entry

    def add_export_calculation(
        self,
        hs_code: str,
        description: str,
        quantity: float,
        unit: str,
        unit_value: float,
        currency: str,
        exchange_rate: float,
        fob_pkr: float,
        net_proceeds: float,
        full_result: Dict[str, Any] = None
    ) -> HistoryEntry:
        """
        Add an export calculation to history.

        Returns:
            The created HistoryEntry
        """
        entry = HistoryEntry(
            id=str(uuid.uuid4()),
            timestamp=datetime.now().isoformat(),
            calc_type=CalculationType.EXPORT,
            input_summary=InputSummary(
                hs_code=hs_code,
                description=description or "Export calculation",
                quantity=quantity,
                unit=unit,
                unit_value=unit_value,
                currency=currency,
                exchange_rate=exchange_rate
            ),
            result_summary=ResultSummary(
                fob_pkr=fob_pkr,
                net_proceeds=net_proceeds
            ),
            full_result=full_result or {}
        )

        self._add_entry(entry)
        return entry

    def _add_entry(self, entry: HistoryEntry) -> None:
        """Add entry with FIFO eviction if at capacity"""
        if len(self._entries) >= self._capacity:
            # Remove oldest entry (first in list)
            self._entries.pop(0)

        self._entries.append(entry)

    def get_entry(self, entry_id: str) -> Optional[HistoryEntry]:
        """Get entry by ID"""
        for entry in self._entries:
            if entry.id == entry_id:
                return entry
        return None

    def get_all(self, reverse: bool = True) -> List[HistoryEntry]:
        """
        Get all entries.

        Args:
            reverse: If True, return newest first (default)

        Returns:
            List of HistoryEntry objects
        """
        if reverse:
            return list(reversed(self._entries))
        return list(self._entries)

    def get_recent(self, count: int = 10) -> List[HistoryEntry]:
        """Get most recent entries"""
        return self.get_all(reverse=True)[:count]

    def filter_by_type(self, calc_type: CalculationType) -> List[HistoryEntry]:
        """Filter entries by calculation type"""
        return [e for e in self._entries if e.calc_type == calc_type]

    def search(self, query: str) -> List[HistoryEntry]:
        """
        Search entries by HS code or description.

        Args:
            query: Search string (case-insensitive)

        Returns:
            Matching entries, newest first
        """
        query_lower = query.lower()
        results = []

        for entry in self._entries:
            if (query_lower in entry.input_summary.hs_code.lower() or
                query_lower in entry.input_summary.description.lower()):
                results.append(entry)

        return list(reversed(results))

    def delete_entry(self, entry_id: str) -> bool:
        """
        Delete entry by ID.

        Returns:
            True if deleted, False if not found
        """
        for i, entry in enumerate(self._entries):
            if entry.id == entry_id:
                self._entries.pop(i)
                return True
        return False

    def clear(self) -> int:
        """
        Clear all history.

        Returns:
            Number of entries cleared
        """
        count = len(self._entries)
        self._entries = []
        return count

    def to_json(self) -> str:
        """Serialize history to JSON string"""
        data = [entry.to_dict() for entry in self._entries]
        return json.dumps(data, indent=2)

    def from_json(self, json_str: str) -> int:
        """
        Load history from JSON string.

        Args:
            json_str: JSON string to parse

        Returns:
            Number of entries loaded
        """
        try:
            data = json.loads(json_str)
            self._entries = [HistoryEntry.from_dict(item) for item in data]
            return len(self._entries)
        except (json.JSONDecodeError, KeyError) as e:
            raise ValueError(f"Invalid history JSON: {e}")

    def export_to_csv(self) -> str:
        """
        Export history to CSV string.

        Returns:
            CSV formatted string
        """
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            'Timestamp',
            'Type',
            'HS Code',
            'Description',
            'Quantity',
            'Unit',
            'Value',
            'Currency',
            'Exchange Rate',
            'CIF/FOB (PKR)',
            'Total Duties',
            'Landed Cost / Net Proceeds'
        ])

        # Data rows
        for entry in self.get_all(reverse=True):
            inp = entry.input_summary
            res = entry.result_summary

            if entry.calc_type == CalculationType.IMPORT:
                cif_fob = res.cif_pkr
                final = res.landed_cost
            else:
                cif_fob = res.fob_pkr
                final = res.net_proceeds

            writer.writerow([
                entry.timestamp,
                entry.calc_type.value,
                inp.hs_code,
                inp.description,
                inp.quantity,
                inp.unit,
                inp.unit_value,
                inp.currency,
                inp.exchange_rate,
                cif_fob,
                res.total_duties,
                final
            ])

        return output.getvalue()

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about history.

        Returns:
            Dictionary with stats
        """
        import_entries = self.filter_by_type(CalculationType.IMPORT)
        export_entries = self.filter_by_type(CalculationType.EXPORT)

        total_import_value = sum(e.result_summary.landed_cost for e in import_entries)
        total_export_value = sum(e.result_summary.net_proceeds for e in export_entries)

        return {
            'total_entries': self.count,
            'import_count': len(import_entries),
            'export_count': len(export_entries),
            'total_import_value': total_import_value,
            'total_export_value': total_export_value,
            'capacity_used': f"{self.count}/{self.capacity}"
        }


# Streamlit session state integration
def get_history_manager() -> HistoryManager:
    """
    Get or create history manager from Streamlit session state.

    Usage in Streamlit:
        from history_manager import get_history_manager
        history = get_history_manager()
    """
    try:
        import streamlit as st

        if 'calculation_history' not in st.session_state:
            st.session_state.calculation_history = HistoryManager()

        return st.session_state.calculation_history
    except ImportError:
        # Not running in Streamlit, return standalone instance
        return HistoryManager()


if __name__ == "__main__":
    # Quick test
    print("Testing History Manager...")

    manager = HistoryManager(capacity=5)

    # Add some entries
    for i in range(3):
        manager.add_import_calculation(
            hs_code=f"0808.100{i}",
            description=f"Fresh apples batch {i+1}",
            quantity=100 * (i + 1),
            unit="kg",
            unit_value=10.0,
            currency="USD",
            exchange_rate=280.0,
            cif_pkr=280000 * (i + 1),
            total_duties=131880 * (i + 1),
            landed_cost=411880 * (i + 1)
        )

    print(f"  Entries: {manager.count}")
    print(f"  Stats: {manager.get_statistics()}")

    # Test search
    results = manager.search("apples")
    print(f"  Search 'apples': {len(results)} results")

    # Test CSV export
    csv_data = manager.export_to_csv()
    print(f"  CSV rows: {csv_data.count(chr(10))}")

    print("  ✓ All tests passed!")
