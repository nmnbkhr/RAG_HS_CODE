"""
RAG_HS_CODE - Static Data Freshness Checker
Phase 7: Live Data Integration

Compares live TIPP data against Phase 6 static tables and flags
discrepancies. Helps identify when hardcoded rates need updating
(e.g., after a Finance Act or new SRO).

Checks:
- FED rates: Compare static FED_RATES vs TIPP live FED values
- Fifth Schedule: Compare concessionary rates vs TIPP CD rates
- FTA/PTA rates: Compare preferential rates vs TIPP preferentials
"""

import time
import json
import sqlite3
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class StaleDataReport:
    """Report of a discrepancy between static and live data."""
    module: str               # "fed_rates", "fifth_schedule", "fta_pta"
    hs_code: str
    field_name: str           # "cd_rate", "fed_rate", etc.
    static_value: float
    live_value: float
    difference_pct: float     # Absolute difference in percentage points
    recommendation: str       # "update_static" or "investigate"

    def to_dict(self) -> dict:
        return {
            "module": self.module,
            "hs_code": self.hs_code,
            "field_name": self.field_name,
            "static_value": self.static_value,
            "live_value": self.live_value,
            "difference_pct": self.difference_pct,
            "recommendation": self.recommendation,
        }


class DataFreshnessChecker:
    """
    Compares live TIPP data against Phase 6 static tables.

    Requires:
    - tipp_cache: TIPPCache instance for live data lookups
    - Phase 6 modules (fed_rates, fifth_schedule, fta_pta)

    Features:
    - Checks FED rates, Fifth Schedule, and FTA/PTA rates
    - Configurable threshold for flagging discrepancies
    - Stores last check time in SQLite for scheduling
    - Weekly check interval by default
    """

    DB_FILENAME = "data_freshness.db"
    DEFAULT_CHECK_INTERVAL_HOURS = 168  # 1 week
    SIGNIFICANCE_THRESHOLD = 0.5  # Flag if difference > 0.5 percentage points

    def __init__(
        self,
        tipp_cache=None,
        fed_rates_module=None,
        fifth_schedule_module=None,
        fta_pta_module=None,
        db_path: Optional[str] = None,
        threshold: float = SIGNIFICANCE_THRESHOLD,
    ):
        self.tipp_cache = tipp_cache
        self.fed_rates = fed_rates_module
        self.fifth_schedule = fifth_schedule_module
        self.fta_pta = fta_pta_module
        self.db_path = db_path or self.DB_FILENAME
        self.threshold = threshold
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        """Initialize SQLite for check metadata."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS freshness_checks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        check_time REAL NOT NULL,
                        module TEXT NOT NULL,
                        total_checked INTEGER NOT NULL,
                        discrepancies INTEGER NOT NULL,
                        report_json TEXT
                    )
                """)
                conn.commit()
            finally:
                conn.close()

    # ------------------------------------------------------------------
    # FED Rate Check
    # ------------------------------------------------------------------

    def check_fed_rates(self, sample_codes: Optional[List[str]] = None) -> List[StaleDataReport]:
        """
        Compare static FED rates against TIPP live data.

        Args:
            sample_codes: HS codes to check. If None, checks all FED_RATES keys.

        Returns:
            List of discrepancy reports
        """
        if not self.fed_rates or not self.tipp_cache:
            return []

        reports = []
        try:
            fed_data = self.fed_rates.FED_RATES
        except AttributeError:
            return []

        codes = sample_codes or list(fed_data.keys())

        for code in codes:
            if code not in fed_data:
                continue

            static_entry = fed_data[code]
            live = self.tipp_cache.get(code) or self.tipp_cache.get_or_fallback(code)
            if not live:
                continue

            # Compare FED rate
            static_rate = static_entry.rate_pct
            live_rate = live.fed_rate
            diff = abs(static_rate - live_rate)

            if diff > self.threshold:
                reports.append(StaleDataReport(
                    module="fed_rates",
                    hs_code=code,
                    field_name="fed_rate",
                    static_value=static_rate,
                    live_value=live_rate,
                    difference_pct=diff,
                    recommendation="update_static" if diff > 2.0 else "investigate",
                ))

        return reports

    # ------------------------------------------------------------------
    # Fifth Schedule Check
    # ------------------------------------------------------------------

    def check_fifth_schedule(self, sample_codes: Optional[List[str]] = None) -> List[StaleDataReport]:
        """
        Compare static Fifth Schedule rates against TIPP live CD rates.

        Args:
            sample_codes: HS codes to check. If None, checks all.

        Returns:
            List of discrepancy reports
        """
        if not self.fifth_schedule or not self.tipp_cache:
            return []

        reports = []
        try:
            schedule_data = self.fifth_schedule.FIFTH_SCHEDULE_RATES
        except AttributeError:
            return []

        codes = sample_codes or list(schedule_data.keys())

        for code in codes:
            if code not in schedule_data:
                continue

            static_entry = schedule_data[code]
            live = self.tipp_cache.get(code) or self.tipp_cache.get_or_fallback(code)
            if not live:
                continue

            # Compare concessionary CD rate against live MFN CD
            # If live MFN is different from static MFN, that's a discrepancy
            static_mfn = static_entry.mfn_cd_rate
            live_mfn = live.mfn_cd_rate
            diff = abs(static_mfn - live_mfn)

            if diff > self.threshold:
                reports.append(StaleDataReport(
                    module="fifth_schedule",
                    hs_code=code,
                    field_name="mfn_cd_rate",
                    static_value=static_mfn,
                    live_value=live_mfn,
                    difference_pct=diff,
                    recommendation="update_static" if diff > 2.0 else "investigate",
                ))

        return reports

    # ------------------------------------------------------------------
    # FTA Rate Check
    # ------------------------------------------------------------------

    def check_fta_rates(self, sample_codes: Optional[List[str]] = None) -> List[StaleDataReport]:
        """
        Compare static FTA/PTA rates against TIPP live preferential rates.

        Args:
            sample_codes: HS codes to check. If None, checks a sample.

        Returns:
            List of discrepancy reports
        """
        if not self.fta_pta or not self.tipp_cache:
            return []

        reports = []
        try:
            pref_data = self.fta_pta.PREFERENTIAL_RATES
        except AttributeError:
            return []

        # Collect all unique HS codes from preferential rates
        all_codes = set()
        for agreement_code, rates in pref_data.items():
            for rate in rates:
                all_codes.add(rate.hs_code)

        codes = sample_codes or list(all_codes)

        for code in codes:
            live = self.tipp_cache.get(code) or self.tipp_cache.get_or_fallback(code)
            if not live or not live.preferential_rates:
                continue

            # Compare each agreement's rate
            for agreement_code, rates in pref_data.items():
                matching = [r for r in rates if r.hs_code == code]
                for static_rate in matching:
                    if agreement_code in live.preferential_rates:
                        static_val = static_rate.preferential_cd_rate
                        live_val = live.preferential_rates[agreement_code]
                        diff = abs(static_val - live_val)

                        if diff > self.threshold:
                            reports.append(StaleDataReport(
                                module="fta_pta",
                                hs_code=code,
                                field_name=f"{agreement_code}_preferential_rate",
                                static_value=static_val,
                                live_value=live_val,
                                difference_pct=diff,
                                recommendation="update_static" if diff > 2.0 else "investigate",
                            ))

        return reports

    # ------------------------------------------------------------------
    # Full Check
    # ------------------------------------------------------------------

    def run_full_check(self) -> Dict[str, List[StaleDataReport]]:
        """
        Run freshness check on all modules.

        Returns:
            Dict mapping module name to list of discrepancy reports
        """
        results = {
            "fed_rates": self.check_fed_rates(),
            "fifth_schedule": self.check_fifth_schedule(),
            "fta_pta": self.check_fta_rates(),
        }

        # Record the check
        self._record_check(results)
        return results

    def _record_check(self, results: Dict[str, List[StaleDataReport]]):
        """Store check results in database."""
        now = time.time()
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                for module, reports in results.items():
                    total = len(reports)
                    discrepancies = sum(1 for r in reports if r.difference_pct > self.threshold)
                    report_json = json.dumps([r.to_dict() for r in reports])

                    conn.execute(
                        "INSERT INTO freshness_checks "
                        "(check_time, module, total_checked, discrepancies, report_json) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (now, module, total, discrepancies, report_json)
                    )
                conn.commit()
            finally:
                conn.close()

    # ------------------------------------------------------------------
    # Scheduling
    # ------------------------------------------------------------------

    def get_last_check_time(self) -> Optional[float]:
        """Get timestamp of the most recent check."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.execute(
                    "SELECT MAX(check_time) FROM freshness_checks"
                )
                row = cursor.fetchone()
                return row[0] if row and row[0] else None
            finally:
                conn.close()

    def needs_check(self, interval_hours: int = DEFAULT_CHECK_INTERVAL_HOURS) -> bool:
        """
        Check if a freshness check is due.

        Args:
            interval_hours: Hours between checks (default: 168 = 1 week)

        Returns:
            True if last check was more than interval_hours ago (or never)
        """
        last = self.get_last_check_time()
        if last is None:
            return True
        age_hours = (time.time() - last) / 3600
        return age_hours > interval_hours

    def get_last_report(self) -> Dict[str, List[dict]]:
        """Get the most recent check report for each module."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                results = {}
                for module in ["fed_rates", "fifth_schedule", "fta_pta"]:
                    cursor = conn.execute(
                        "SELECT report_json FROM freshness_checks "
                        "WHERE module = ? ORDER BY check_time DESC LIMIT 1",
                        (module,)
                    )
                    row = cursor.fetchone()
                    if row and row[0]:
                        results[module] = json.loads(row[0])
                    else:
                        results[module] = []
                return results
            finally:
                conn.close()

    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of data freshness status.

        Returns:
            Dict with last_check, needs_check, modules with discrepancy counts
        """
        last = self.get_last_check_time()
        report = self.get_last_report()

        module_status = {}
        for module, items in report.items():
            disc_count = len(items)
            if disc_count == 0:
                module_status[module] = {"status": "up_to_date", "discrepancies": 0}
            else:
                module_status[module] = {"status": "has_discrepancies", "discrepancies": disc_count}

        return {
            "last_check": last,
            "last_check_display": self._format_age(last) if last else "never",
            "needs_check": self.needs_check(),
            "modules": module_status,
        }

    @staticmethod
    def _format_age(timestamp: float) -> str:
        """Format a timestamp as relative age."""
        age = time.time() - timestamp
        if age < 3600:
            return f"{age / 60:.0f}m ago"
        elif age < 86400:
            return f"{age / 3600:.1f}h ago"
        else:
            return f"{age / 86400:.1f}d ago"
