"""
RAG_HS_CODE - TIPP Portal Scraper & Cache
Phase 7: Live Data Integration

Scrapes FBR's Tariff Information and Preferential Pricing (TIPP)
portal at https://tipp.fbr.gov.pk for live tariff data including:
- MFN customs duty rates
- Sales tax rates
- Additional customs duty (ACD)
- Regulatory duty (RD)
- Federal Excise Duty (FED) applicability
- Preferential rates under FTAs/PTAs
- Active SRO references

TIPP is the single richest public data source for Pakistan tariff
information, combining data that otherwise requires checking WEBOC,
SBP, FBR, and individual SRO gazette notifications separately.
"""

import re
import json
import time
import sqlite3
import threading
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

try:
    import requests
except ImportError:
    requests = None

try:
    from bs4 import BeautifulSoup
except ImportError:
    BeautifulSoup = None


@dataclass
class TIPPResult:
    """Tariff data from the TIPP portal for a specific HS code."""
    hs_code: str
    description: str = ""
    mfn_cd_rate: float = 0.0            # MFN customs duty %
    sales_tax_rate: float = 17.0        # Sales tax % (default 17%)
    additional_duty_rate: float = 0.0   # ACD %
    regulatory_duty_rate: float = 0.0   # RD %
    fed_applicable: bool = False
    fed_rate: float = 0.0               # FED % (if ad-valorem)
    preferential_rates: Dict[str, float] = field(default_factory=dict)
    sro_references: List[str] = field(default_factory=list)
    fetched_at: float = 0.0
    source: str = "TIPP"
    unit_of_measure: str = "units"

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "hs_code": self.hs_code,
            "description": self.description,
            "mfn_cd_rate": self.mfn_cd_rate,
            "sales_tax_rate": self.sales_tax_rate,
            "additional_duty_rate": self.additional_duty_rate,
            "regulatory_duty_rate": self.regulatory_duty_rate,
            "fed_applicable": self.fed_applicable,
            "fed_rate": self.fed_rate,
            "preferential_rates": self.preferential_rates,
            "sro_references": self.sro_references,
            "fetched_at": self.fetched_at,
            "source": self.source,
            "unit_of_measure": self.unit_of_measure,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TIPPResult":
        """Reconstruct from a dictionary."""
        return cls(
            hs_code=data.get("hs_code", ""),
            description=data.get("description", ""),
            mfn_cd_rate=data.get("mfn_cd_rate", 0.0),
            sales_tax_rate=data.get("sales_tax_rate", 17.0),
            additional_duty_rate=data.get("additional_duty_rate", 0.0),
            regulatory_duty_rate=data.get("regulatory_duty_rate", 0.0),
            fed_applicable=data.get("fed_applicable", False),
            fed_rate=data.get("fed_rate", 0.0),
            preferential_rates=data.get("preferential_rates", {}),
            sro_references=data.get("sro_references", []),
            fetched_at=data.get("fetched_at", 0.0),
            source=data.get("source", "TIPP"),
            unit_of_measure=data.get("unit_of_measure", "units"),
        )


def detect_unit_from_text(text: str) -> str:
    """Detect unit of measure from description text."""
    if not text:
        return "units"
    text_lower = text.lower()
    uom_patterns = [
        (r'\bcbm\b|\bcum\b|\bcu\.m\b|\bcubic\s*met', 'cum'),
        (r'\bsqm\b|\bsq\.?\s*m\b|\bsquare\s*met', 'sqm'),
        (r'\btonne|\btons?\b|\bmt\b|\bmetric\s*ton', 'tonnes'),
        (r'\blitre|\bliter|\blitres|\bliters|\bltr\b', 'liters'),
        (r'\bmetre|\bmeter|\bmetres|\bmeters|\bmtr\b', 'meters'),
        (r'\bpair|\bpairs|\bprs\b', 'pairs'),
        (r'\bdozen|\bdozens|\bdoz\b', 'dozens'),
        (r'\bset\b|\bsets\b', 'sets'),
        (r'\bkg\b|\bkilogram|\bkgs\b|\bkilos?\b', 'kg'),
        (r'\bunit|\bunits|\bpiece|\bpieces|\bpcs\b|\bnos?\b|\bnumber', 'units'),
    ]
    for pattern, uom in uom_patterns:
        if re.search(pattern, text_lower):
            return uom
    return "units"


def normalize_hs_code(code: str) -> str:
    """Normalize HS code to XXXX.XXXX format."""
    if not code:
        return ""
    digits = re.sub(r"[^0-9]", "", code.strip())
    if len(digits) >= 8:
        return f"{digits[:4]}.{digits[4:8]}"
    elif len(digits) >= 4:
        return digits[:4]
    return digits


class TIPPScraper:
    """
    Scrapes FBR TIPP portal for HS code tariff data.

    The TIPP portal provides a searchable interface for Pakistan's
    tariff schedule. This scraper performs HTTP requests and parses
    the HTML response to extract duty rates and compliance data.

    Features:
    - HS code search with normalized input
    - MFN and preferential rate extraction
    - SRO reference extraction
    - FED applicability detection
    - Timeout and error handling
    - Rate validation
    """

    BASE_URL = "https://tipp.fbr.gov.pk"
    SEARCH_PATH = "/TariffSearch.aspx"
    TIMEOUT = 15  # seconds
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )

    def __init__(self, base_url: Optional[str] = None, timeout: int = TIMEOUT):
        self.base_url = base_url or self.BASE_URL
        self.timeout = timeout
        self.last_error: Optional[str] = None
        self._session: Optional[object] = None

    def _get_session(self):
        """Get or create a requests session with proper headers."""
        if requests is None:
            return None
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update({
                "User-Agent": self.USER_AGENT,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
            })
        return self._session

    def search(self, hs_code: str) -> Optional[TIPPResult]:
        """
        Search TIPP portal for tariff data.

        Args:
            hs_code: HS code (any format, will be normalized)

        Returns:
            TIPPResult if found, None if fetch fails
        """
        if not hs_code or not hs_code.strip():
            self.last_error = "Empty HS code"
            return None

        normalized = normalize_hs_code(hs_code)
        if len(normalized.replace(".", "")) < 4:
            self.last_error = "HS code too short (need at least 4 digits)"
            return None

        session = self._get_session()
        if session is None:
            self.last_error = "requests library not available"
            return None

        try:
            # TIPP uses a search form — attempt GET with query param
            url = f"{self.base_url}{self.SEARCH_PATH}"
            params = {"hsCode": normalized.replace(".", "")}

            response = session.get(url, params=params, timeout=self.timeout)
            if response.status_code != 200:
                self.last_error = f"HTTP {response.status_code}"
                return None

            return self._parse_tariff_page(response.text, normalized)

        except Exception as e:
            if requests and isinstance(e, requests.Timeout):
                self.last_error = "TIPP request timed out"
            elif requests and isinstance(e, requests.ConnectionError):
                self.last_error = "TIPP connection failed"
            else:
                self.last_error = f"TIPP fetch error: {str(e)}"
            return None

    def _parse_tariff_page(self, html: str, hs_code: str) -> Optional[TIPPResult]:
        """
        Parse TIPP tariff result page.

        Extracts duty rates, preferential tariffs, SRO references,
        and FED applicability from the HTML.

        Args:
            html: Raw HTML content
            hs_code: Normalized HS code

        Returns:
            TIPPResult or None if parsing fails
        """
        now = time.time()
        result = TIPPResult(hs_code=hs_code, fetched_at=now)

        # Try BeautifulSoup if available, fall back to regex
        if BeautifulSoup:
            return self._parse_with_bs4(html, result)
        return self._parse_with_regex(html, result)

    def _parse_with_bs4(self, html: str, result: TIPPResult) -> Optional[TIPPResult]:
        """Parse using BeautifulSoup (preferred)."""
        soup = BeautifulSoup(html, "html.parser")

        # Extract description
        desc_elem = soup.find(string=re.compile(r"Description", re.I))
        if desc_elem:
            parent = desc_elem.find_parent("tr")
            if parent:
                cells = parent.find_all("td")
                if len(cells) >= 2:
                    result.description = cells[-1].get_text(strip=True)

        # Extract duty rates from tables
        self._extract_duty_rates_bs4(soup, result)
        result.preferential_rates = self._extract_preferential_rates(soup)
        result.sro_references = self._extract_sro_references(soup)
        result.fed_applicable = result.fed_rate > 0

        # Detect unit of measure from description
        if result.description:
            result.unit_of_measure = detect_unit_from_text(result.description)

        if not result.description and not result.mfn_cd_rate:
            self.last_error = "Could not parse TIPP page (no data found)"
            return None

        return result

    def _extract_duty_rates_bs4(self, soup, result: TIPPResult):
        """Extract MFN duty rates from BS4-parsed page."""
        # Look for rate table rows
        for row in soup.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 2:
                continue

            label = cells[0].get_text(strip=True).lower()
            value_text = cells[-1].get_text(strip=True)

            # Try to extract numeric rate
            rate_match = re.search(r"(\d+(?:\.\d+)?)\s*%?", value_text)
            if not rate_match:
                continue
            rate_val = float(rate_match.group(1))

            if "customs duty" in label and "additional" not in label:
                result.mfn_cd_rate = rate_val
            elif "sales tax" in label:
                result.sales_tax_rate = rate_val
            elif "additional" in label and ("customs" in label or "duty" in label):
                result.additional_duty_rate = rate_val
            elif "regulatory" in label and "duty" in label:
                result.regulatory_duty_rate = rate_val
            elif "excise" in label or "fed" in label:
                result.fed_rate = rate_val

    def _extract_preferential_rates(self, soup) -> Dict[str, float]:
        """Extract preferential tariff rates from FTA/PTA section."""
        rates = {}

        # Look for preferential/FTA/PTA section
        pref_header = soup.find(
            string=re.compile(r"preferential|FTA|PTA|concession", re.I)
        )
        if not pref_header:
            return rates

        # Navigate to the containing table
        table = pref_header.find_parent("table")
        if not table:
            return rates

        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) < 2:
                continue

            # Look for agreement code and rate
            text = cells[0].get_text(strip=True)
            agreement_match = re.search(
                r"(CPFTA|SAFTA|MPFTA|PKSL|PKIRN|PKINDN|ECOTA|D-8)",
                text, re.I
            )
            if agreement_match:
                rate_text = cells[-1].get_text(strip=True)
                rate_match = re.search(r"(\d+(?:\.\d+)?)", rate_text)
                if rate_match:
                    code = agreement_match.group(1).upper()
                    rates[code] = float(rate_match.group(1))

        return rates

    def _extract_sro_references(self, soup) -> List[str]:
        """Extract SRO references mentioned on the page."""
        sros = set()

        # Find SRO pattern: SRO NNN(I)/YYYY or S.R.O. NNN(I)/YYYY
        text = soup.get_text()
        sro_pattern = re.compile(
            r"S\.?R\.?O\.?\s*(\d{1,4}\s*\([IViv]+\)\s*/\s*\d{4})",
            re.IGNORECASE
        )
        for match in sro_pattern.finditer(text):
            sro_num = re.sub(r"\s+", "", match.group(1))
            sros.add(sro_num)

        return sorted(sros)

    def _parse_with_regex(self, html: str, result: TIPPResult) -> Optional[TIPPResult]:
        """Fallback parser using only regex (no BeautifulSoup)."""
        # Extract description
        desc_match = re.search(
            r"(?:Description|Desc\.?)\s*[:=<>\s]*([^<]{5,120})",
            html, re.IGNORECASE
        )
        if desc_match:
            result.description = desc_match.group(1).strip()

        # Extract customs duty rate
        cd_match = re.search(
            r"(?:Customs\s+Duty|CD)\s*[:=<>\s]*(\d+(?:\.\d+)?)\s*%",
            html, re.IGNORECASE
        )
        if cd_match:
            result.mfn_cd_rate = float(cd_match.group(1))

        # Extract sales tax
        st_match = re.search(
            r"(?:Sales\s+Tax|ST|GST)\s*[:=<>\s]*(\d+(?:\.\d+)?)\s*%",
            html, re.IGNORECASE
        )
        if st_match:
            result.sales_tax_rate = float(st_match.group(1))

        # Extract additional customs duty
        acd_match = re.search(
            r"(?:Additional\s+(?:Customs\s+)?Duty|ACD)\s*[:=<>\s]*(\d+(?:\.\d+)?)\s*%",
            html, re.IGNORECASE
        )
        if acd_match:
            result.additional_duty_rate = float(acd_match.group(1))

        # Extract regulatory duty
        rd_match = re.search(
            r"(?:Regulatory\s+Duty|RD)\s*[:=<>\s]*(\d+(?:\.\d+)?)\s*%",
            html, re.IGNORECASE
        )
        if rd_match:
            result.regulatory_duty_rate = float(rd_match.group(1))

        # Extract FED
        fed_match = re.search(
            r"(?:Federal\s+Excise|FED)\s*[:=<>\s]*(\d+(?:\.\d+)?)\s*%",
            html, re.IGNORECASE
        )
        if fed_match:
            result.fed_rate = float(fed_match.group(1))
            result.fed_applicable = True

        # Extract SRO references
        sro_pattern = re.compile(
            r"S\.?R\.?O\.?\s*(\d{1,4}\s*\([IViv]+\)\s*/\s*\d{4})",
            re.IGNORECASE
        )
        sros = set()
        for match in sro_pattern.finditer(html):
            sro_num = re.sub(r"\s+", "", match.group(1))
            sros.add(sro_num)
        result.sro_references = sorted(sros)

        # Extract preferential rates (regex fallback)
        pref_pattern = re.compile(
            r"(CPFTA|SAFTA|MPFTA|PKSL|PKIRN|PKINDN|ECOTA|D-8)"
            r"[^0-9]*?(\d+(?:\.\d+)?)\s*%",
            re.IGNORECASE
        )
        for match in pref_pattern.finditer(html):
            code = match.group(1).upper()
            result.preferential_rates[code] = float(match.group(2))

        # Detect unit of measure from description
        if result.description:
            result.unit_of_measure = detect_unit_from_text(result.description)

        if not result.description and result.mfn_cd_rate == 0.0:
            self.last_error = "Could not parse TIPP page (no data found)"
            return None

        return result

    def validate_result(self, result: TIPPResult) -> bool:
        """Validate that a TIPP result has sensible values."""
        if not result.hs_code:
            return False
        # CD rate should be 0-100%
        if not (0 <= result.mfn_cd_rate <= 100):
            return False
        # ST rate should be 0-100%
        if not (0 <= result.sales_tax_rate <= 100):
            return False
        return True


class TIPPCache:
    """
    SQLite cache for TIPP tariff lookups.

    Features:
    - 48-hour TTL (TIPP data changes less frequently than WEBOC)
    - 10,000 max entries with LRU eviction
    - Stale fallback: returns expired data if live fetch fails
    - Thread-safe operations
    """

    DEFAULT_TTL = 48 * 3600    # 48 hours
    MAX_ENTRIES = 10000
    DB_FILENAME = "tipp_cache.db"

    def __init__(self, db_path: Optional[str] = None,
                 ttl: int = DEFAULT_TTL,
                 max_entries: int = MAX_ENTRIES):
        self.db_path = db_path or self.DB_FILENAME
        self.ttl = ttl
        self.max_entries = max_entries
        self._lock = threading.Lock()
        self._stats = {"hits": 0, "misses": 0, "updates": 0, "evictions": 0}
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS tipp_cache (
                        hs_code TEXT PRIMARY KEY,
                        data_json TEXT NOT NULL,
                        fetched_at REAL NOT NULL,
                        expires_at REAL NOT NULL,
                        last_accessed REAL NOT NULL
                    )
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_expires
                    ON tipp_cache(expires_at)
                """)
                conn.execute("""
                    CREATE INDEX IF NOT EXISTS idx_accessed
                    ON tipp_cache(last_accessed)
                """)
                conn.commit()
            finally:
                conn.close()

    def get(self, hs_code: str) -> Optional[TIPPResult]:
        """
        Get cached TIPP result if not expired.

        Args:
            hs_code: Normalized HS code

        Returns:
            TIPPResult if cached and not expired, None otherwise
        """
        if not hs_code:
            return None

        normalized = normalize_hs_code(hs_code)
        now = time.time()

        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.execute(
                    "SELECT data_json, expires_at FROM tipp_cache "
                    "WHERE hs_code = ? AND expires_at > ?",
                    (normalized, now)
                )
                row = cursor.fetchone()
                if row:
                    # Update last_accessed
                    conn.execute(
                        "UPDATE tipp_cache SET last_accessed = ? WHERE hs_code = ?",
                        (now, normalized)
                    )
                    conn.commit()
                    self._stats["hits"] += 1
                    return TIPPResult.from_dict(json.loads(row[0]))

                self._stats["misses"] += 1
                return None
            finally:
                conn.close()

    def get_or_fallback(self, hs_code: str) -> Optional[TIPPResult]:
        """
        Get cached result even if expired (stale fallback).

        Args:
            hs_code: Normalized HS code

        Returns:
            TIPPResult if any cached version exists (even expired)
        """
        if not hs_code:
            return None

        normalized = normalize_hs_code(hs_code)

        # First try non-expired
        result = self.get(hs_code)
        if result:
            return result

        # Fallback to expired
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.execute(
                    "SELECT data_json FROM tipp_cache WHERE hs_code = ?",
                    (normalized,)
                )
                row = cursor.fetchone()
                if row:
                    self._stats["hits"] += 1
                    return TIPPResult.from_dict(json.loads(row[0]))
                return None
            finally:
                conn.close()

    def put(self, hs_code: str, result: TIPPResult):
        """
        Store a TIPP result in cache.

        Args:
            hs_code: Normalized HS code
            result: TIPPResult to cache
        """
        if not hs_code or not result:
            return

        normalized = normalize_hs_code(hs_code)
        now = time.time()
        expires = now + self.ttl
        data_json = json.dumps(result.to_dict())

        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute(
                    "INSERT OR REPLACE INTO tipp_cache "
                    "(hs_code, data_json, fetched_at, expires_at, last_accessed) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (normalized, data_json, now, expires, now)
                )
                conn.commit()
                self._stats["updates"] += 1

                # Check if eviction needed
                cursor = conn.execute("SELECT COUNT(*) FROM tipp_cache")
                count = cursor.fetchone()[0]
                if count > self.max_entries:
                    self._evict_lru(conn)
            finally:
                conn.close()

    def invalidate(self, hs_code: str):
        """Remove a specific entry from cache."""
        if not hs_code:
            return
        normalized = normalize_hs_code(hs_code)
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("DELETE FROM tipp_cache WHERE hs_code = ?",
                             (normalized,))
                conn.commit()
            finally:
                conn.close()

    def invalidate_all(self):
        """Clear entire cache."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute("DELETE FROM tipp_cache")
                conn.commit()
            finally:
                conn.close()

    def cleanup_expired(self) -> int:
        """Remove all expired entries. Returns count of removed entries."""
        now = time.time()
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.execute(
                    "DELETE FROM tipp_cache WHERE expires_at < ?", (now,)
                )
                conn.commit()
                return cursor.rowcount
            finally:
                conn.close()

    def get_entry_count(self) -> int:
        """Get number of entries in cache."""
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.execute("SELECT COUNT(*) FROM tipp_cache")
                return cursor.fetchone()[0]
            finally:
                conn.close()

    @property
    def stats(self) -> dict:
        """Cache statistics."""
        return dict(self._stats)

    def _evict_lru(self, conn: sqlite3.Connection):
        """Remove oldest 10% of entries by last_accessed."""
        evict_count = self.max_entries // 10
        conn.execute(
            "DELETE FROM tipp_cache WHERE hs_code IN "
            "(SELECT hs_code FROM tipp_cache ORDER BY last_accessed ASC LIMIT ?)",
            (evict_count,)
        )
        conn.commit()
        self._stats["evictions"] += evict_count

    def search(self, query: str) -> List[TIPPResult]:
        """
        Search cache by HS code prefix.

        Args:
            query: HS code prefix to search for

        Returns:
            List of matching TIPPResult objects
        """
        if not query:
            return []

        normalized = normalize_hs_code(query)
        prefix = normalized.replace(".", "")

        with self._lock:
            conn = sqlite3.connect(self.db_path)
            try:
                cursor = conn.execute(
                    "SELECT data_json FROM tipp_cache "
                    "WHERE REPLACE(hs_code, '.', '') LIKE ? "
                    "ORDER BY hs_code LIMIT 50",
                    (f"{prefix}%",)
                )
                results = []
                for row in cursor.fetchall():
                    results.append(TIPPResult.from_dict(json.loads(row[0])))
                return results
            finally:
                conn.close()
