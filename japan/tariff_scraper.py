"""
Japan Customs Tariff scraper.
English: customs.go.jp/english/tariff/{version}/data/e_XX.htm
Japanese: customs.go.jp/tariff/{version}/data/j_XX.htm
Page encoding: Shift_JIS. Table: id="datatable" with 33 columns.
Caches results to japan/data/jp_tariff.json.
"""

import json
import os
import re
import time

import requests
from bs4 import BeautifulSoup

from japan.hs_normalizer import normalize, get_chapter

# Latest tariff schedule (2025-04-01). Update when new version is published.
_TARIFF_VERSION = "2025_04_01"
_BASE_URL_EN = (
    "https://www.customs.go.jp/english/tariff/"
    + _TARIFF_VERSION
    + "/data/e_{chapter:02d}.htm"
)
_BASE_URL_JP = (
    "https://www.customs.go.jp/tariff/"
    + _TARIFF_VERSION
    + "/data/j_{chapter:02d}.htm"
)
_SESSION_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
}

# -----------------------------------------------------------------------
# Fixed column indices in the 33-cell data rows of table#datatable
# -----------------------------------------------------------------------
_COL_HS_CODE = 0       # HS heading (e.g. "8701.10")
_COL_SUBCODE = 1       # Sub-code suffix (e.g. "000", "010")
_COL_DESC = 2          # English description
_COL_GENERAL = 3       # General rate
_COL_TEMPORARY = 4     # Temporary rate
_COL_WTO = 5           # WTO rate
_COL_GSP = 6           # GSP (Special Preferential) rate
_COL_LDC = 7           # LDC (Least Developed Countries) rate
# Columns 8-28: EPA rates (21 agreements)
_COL_EPA_START = 8
_EPA_NAMES = [
    'Singapore', 'Mexico', 'Malaysia', 'Chile', 'Thailand',
    'Indonesia', 'Brunei', 'ASEAN', 'Philippines', 'Switzerland',
    'Vietnam', 'India', 'Peru', 'Australia', 'Mongolia',
    'CPTPP', 'EU', 'UK', 'RCEP-ASEAN/ANZ', 'RCEP-China', 'RCEP-Korea',
]
_COL_JP_US = 29        # Japan-US Trade Agreement
_COL_UNIT1 = 30        # Unit I
_COL_UNIT2 = 31        # Unit II
_COL_LAW = 32          # Law reference

# Keyword → HS chapter/heading synonyms for natural-language search
KEYWORD_SYNONYMS = {
    'ev': ['electric', 'motor vehicle', '8703.80'],
    'car': ['motor car', 'automobile', 'vehicle', 'passenger', '8703'],
    'truck': ['motor vehicle', 'goods transport', '8704'],
    'motorcycle': ['motor cycle', '8711'],
    'bicycle': ['cycle', '8712'],
    'bus': ['motor vehicle', 'transport of persons', '8702'],
    'tractor': ['8701'],
    'phone': ['telephone', 'cellular', 'mobile', '8517'],
    'mobile': ['telephone', 'cellular', 'portable', '8517'],
    'computer': ['data processing', 'automatic', '8471'],
    'laptop': ['portable', 'data processing', '8471'],
    'tv': ['television', 'monitor', '8528'],
    'camera': ['photographic', 'digital', '9006'],
    'rice': ['1006'],
    'wheat': ['1001'],
    'coffee': ['0901'],
    'tea': ['0902'],
    'wine': ['2204'],
    'beer': ['2203'],
    'whisky': ['whiskey', 'spirits', '2208'],
    'sake': ['rice wine', '2206'],
    'cigarette': ['tobacco', '2402'],
    'gasoline': ['petroleum', 'fuel', '2710'],
    'steel': ['iron', '72'],
    'aluminium': ['aluminum', '76'],
    'copper': ['74'],
    'plastic': ['39'],
    'rubber': ['tyre', 'tire', '40'],
    'cotton': ['52'],
    'silk': ['50'],
    'wool': ['51'],
    'leather': ['hide', 'skin', '41', '42'],
    'shoe': ['footwear', '64'],
    'furniture': ['94'],
    'toy': ['game', '95'],
    'medicine': ['pharmaceutical', 'drug', '30'],
    'cosmetic': ['perfume', 'beauty', '33'],
    'soap': ['detergent', '34'],
    'paper': ['48'],
    'wood': ['timber', 'lumber', '44'],
    'glass': ['70'],
    'ceramic': ['porcelain', '69'],
    'battery': ['accumulator', '8507'],
    'semiconductor': ['integrated circuit', '8542'],
    'solar': ['photovoltaic', '8541'],
    'machinery': ['machine', '84'],
    'electrical': ['electric', '85'],
    'aircraft': ['airplane', '88'],
    'ship': ['vessel', 'boat', '89'],
    'watch': ['clock', '91'],
    'instrument': ['apparatus', '90'],
    'jewelry': ['jewellery', 'precious', '71'],
    'gold': ['71'],
    'diamond': ['71'],
    'fish': ['03'],
    'meat': ['02'],
    'fruit': ['08'],
    'vegetable': ['07'],
    'cheese': ['dairy', '0406'],
    'butter': ['0405'],
    'milk': ['0401', '0402'],
    'sugar': ['17'],
    'chocolate': ['cocoa', '18'],
    'oil': ['15', '27'],
    'fertilizer': ['31'],
    'cement': ['25'],
    'tyre': ['tire', 'rubber', '4011'],
    'tire': ['tyre', 'rubber', '4011'],
    'pipe': ['tube', '73'],
    'wire': ['cable', '7312', '8544'],
    'bolt': ['screw', 'nut', '7318'],
    'bearing': ['8482'],
    'pump': ['8413'],
    'engine': ['motor', '8407', '8408'],
    'turbine': ['8406'],
    'refrigerator': ['freezer', '8418'],
    'air conditioner': ['8415'],
    'washing machine': ['8450'],
    'printer': ['8443'],
    'robot': ['8479', '8428'],
    'led': ['light emitting', '8541'],
    'display': ['screen', 'panel', '8528'],
    'sensor': ['8541', '9031'],
    'textile': ['fabric', 'cloth', '50', '51', '52', '53', '54', '55'],
    'apparel': ['clothing', 'garment', '61', '62'],
    'bag': ['suitcase', 'luggage', '4202'],
    'umbrella': ['66'],
    'carpet': ['rug', '57'],
    'front wheel drive': ['motor car', 'vehicle', '8703'],
    'seater': ['persons', 'passenger', '8702', '8703'],
}


def _parse_rate(text: str) -> dict | None:
    """
    Parse a tariff rate string into structured data.

    Returns dict with keys: duty_type, value, per_unit_value, per_unit_name
    - '3.9%'           -> ad_valorem, value=3.9
    - 'Free'           -> ad_valorem, value=0.0
    - '(Free)'         -> ad_valorem, value=0.0
    - '70yen/l'        -> specific, per_unit_value=70.0, per_unit_name='l'
    - '23.8%+985yen/kg'-> combined, value=23.8, per_unit_value=985.0, per_unit_name='kg'
    - dash / empty     -> None
    """
    if not text:
        return None
    text = text.strip().strip('()')
    if not text or text in ('\u2014', '-', '\u2015', '\u2013', 'N/A'):
        return None
    if text.lower() == 'free':
        return {'duty_type': 'ad_valorem', 'value': 0.0,
                'per_unit_value': None, 'per_unit_name': None}

    # Combined: "X.X% + Nyen/unit"  or  "X.X%+Nyen/unit"
    combined_match = re.match(
        r'([\d.]+)\s*%\s*[+\uFF0B]\s*([\d.]+)\s*yen\s*/\s*(\w+)', text, re.IGNORECASE
    )
    if combined_match:
        return {
            'duty_type': 'combined',
            'value': float(combined_match.group(1)),
            'per_unit_value': float(combined_match.group(2)),
            'per_unit_name': combined_match.group(3),
        }

    # Specific: "Nyen/unit" or "¥N/unit"
    specific_match = re.match(
        r'[\u00a5]?\s*([\d.]+)\s*yen\s*/\s*(\w+)', text, re.IGNORECASE
    )
    if specific_match:
        return {
            'duty_type': 'specific',
            'value': None,
            'per_unit_value': float(specific_match.group(1)),
            'per_unit_name': specific_match.group(2),
        }

    # Ad valorem: "X.X%" or "X%"
    pct_match = re.match(r'([\d.]+)\s*%', text)
    if pct_match:
        return {
            'duty_type': 'ad_valorem',
            'value': float(pct_match.group(1)),
            'per_unit_value': None,
            'per_unit_name': None,
        }

    return None


def _cell_text(cells: list, index: int) -> str:
    """Safely get text from a cell list by index."""
    if index < len(cells):
        return cells[index].get_text(strip=True)
    return ''


class JapanTariffScraper:
    """Scrape Japan Customs HTML tariff tables and cache to JSON."""

    def __init__(self, cache_dir: str = None):
        if cache_dir is None:
            cache_dir = os.path.join(os.path.dirname(__file__), 'data')
        os.makedirs(cache_dir, exist_ok=True)
        self.cache_path = os.path.join(cache_dir, 'jp_tariff.json')
        self.data: dict[str, dict] = {}
        # heading_code (e.g. "8703") → heading description from Type A rows
        self.headings: dict[str, str] = {}
        self.session = requests.Session()
        self.session.headers.update(_SESSION_HEADERS)

    def _scrape_jp_descriptions(self, chapter_num: int) -> dict[str, str]:
        """
        Fetch the Japanese-language page for a chapter and extract
        statistical_code → Japanese description mapping.

        Japanese pages have the same table structure as English pages
        (same columns, same statistical codes) but col 2 is in Japanese.
        """
        url = _BASE_URL_JP.format(chapter=chapter_num)
        try:
            resp = self.session.get(url, timeout=30)
            if resp.status_code != 200:
                return {}
            resp.encoding = 'shift_jis'
        except Exception:
            return {}

        soup = BeautifulSoup(resp.text, 'html.parser')
        table = soup.find('table', id='datatable')
        if not table:
            return {}

        jp_map: dict[str, str] = {}
        rows = table.find_all('tr')
        last_heading = ''

        for row in rows:
            cells = row.find_all('td')
            if len(cells) < 10:
                continue

            col0 = _cell_text(cells, _COL_HS_CODE)
            col1 = _cell_text(cells, _COL_SUBCODE)
            desc = _cell_text(cells, _COL_DESC)

            if re.match(r'^\d{2}\.\d{2}$', col0):
                last_heading = ''
                continue

            if re.match(r'^\d{4}\.\d{2}$', col0):
                last_heading = col0
                if col1 and re.match(r'^\d{3}$', col1):
                    stat_code = f"{col0}-{col1}"
                elif desc:
                    stat_code = f"{col0}-000"
                else:
                    continue
            elif not col0 and col1 and re.match(r'^\d{3}$', col1):
                if last_heading:
                    stat_code = f"{last_heading}-{col1}"
                else:
                    continue
            else:
                continue

            if desc:
                jp_map[stat_code] = desc[:300]

        return jp_map

    def scrape_chapter(self, chapter_num: int) -> list[dict]:
        """
        Fetch a single chapter page and parse table#datatable.

        The table has 33 columns per data row. Row types:
          A) Heading row: cell 0 = "87.01", cell 1 empty, rates empty
          B) Single sub-code: cell 0 = "8701.10", cell 1 = "000", rates filled
          C) Multi sub-code parent: cell 0 = "8701.91", cell 1 empty, rates may exist
          C') Multi sub-code child: cell 0 empty, cell 1 = "010", rates may inherit
        """
        url = _BASE_URL_EN.format(chapter=chapter_num)
        try:
            resp = self.session.get(url, timeout=30)
            if resp.status_code != 200:
                return []
            # Page is Shift_JIS encoded
            resp.encoding = 'shift_jis'
        except Exception:
            return []

        soup = BeautifulSoup(resp.text, 'html.parser')
        results = []

        # Target the specific tariff data table
        table = soup.find('table', id='datatable')
        if not table:
            return []

        rows = table.find_all('tr')
        last_heading = ''  # Track last seen XXXX.XX for sub-code reconstruction
        last_rates = {}    # Inherit rates from parent subheading for child rows

        for row in rows:
            cells = row.find_all('td')
            if len(cells) < 10:
                continue  # Skip header rows (they use <th>)

            col0 = _cell_text(cells, _COL_HS_CODE)    # HS heading
            col1 = _cell_text(cells, _COL_SUBCODE)     # Sub-code suffix
            desc = _cell_text(cells, _COL_DESC)         # Description

            # ---- Determine the full statistical code ----

            # Type A: chapter heading like "87.01" — store description, skip entry
            if re.match(r'^\d{2}\.\d{2}$', col0):
                last_heading = ''
                # Store heading description for search context (e.g. "8703" key)
                heading_key = col0.replace('.', '')
                if desc:
                    self.headings[heading_key] = desc[:300]
                continue

            # Type B or C parent: cell 0 has "XXXX.XX"
            if re.match(r'^\d{4}\.\d{2}$', col0):
                last_heading = col0
                if col1 and re.match(r'^\d{3}$', col1):
                    # Type B: single sub-code (e.g., 8701.10 + 000)
                    stat_code = f"{col0}-{col1}"
                else:
                    # Type C parent: heading with no specific sub-code yet
                    # Store rates as defaults for child rows
                    last_rates = {
                        'general_rate': _cell_text(cells, _COL_GENERAL),
                        'temporary_rate': _cell_text(cells, _COL_TEMPORARY),
                        'wto_rate': _cell_text(cells, _COL_WTO),
                        'gsp_rate': _cell_text(cells, _COL_GSP),
                        'ldc_rate': _cell_text(cells, _COL_LDC),
                    }
                    # Also store EPA rates
                    for i, epa_name in enumerate(_EPA_NAMES):
                        last_rates[f'epa_{epa_name}'] = _cell_text(cells, _COL_EPA_START + i)
                    last_rates['jp_us_rate'] = _cell_text(cells, _COL_JP_US)

                    # If this row also has a description, save it as a 000 entry
                    if desc:
                        stat_code = f"{col0}-000"
                    else:
                        continue

            # Type C child: cell 0 empty, cell 1 has sub-code suffix
            elif not col0 and col1 and re.match(r'^\d{3}$', col1):
                if last_heading:
                    stat_code = f"{last_heading}-{col1}"
                else:
                    continue
            else:
                continue

            # ---- Extract rates ----
            general_rate = _cell_text(cells, _COL_GENERAL) or last_rates.get('general_rate', '')
            temporary_rate = _cell_text(cells, _COL_TEMPORARY) or last_rates.get('temporary_rate', '')
            wto_rate = _cell_text(cells, _COL_WTO) or last_rates.get('wto_rate', '')
            gsp_rate = _cell_text(cells, _COL_GSP) or last_rates.get('gsp_rate', '')
            ldc_rate = _cell_text(cells, _COL_LDC) or last_rates.get('ldc_rate', '')

            # EPA rates
            epa_rates = {}
            for i, epa_name in enumerate(_EPA_NAMES):
                val = _cell_text(cells, _COL_EPA_START + i) or last_rates.get(f'epa_{epa_name}', '')
                if val:
                    epa_rates[epa_name] = val

            jp_us_rate = _cell_text(cells, _COL_JP_US) or last_rates.get('jp_us_rate', '')

            # Units
            unit1 = _cell_text(cells, _COL_UNIT1)
            unit2 = _cell_text(cells, _COL_UNIT2)
            unit = unit1 or unit2 or 'KG'

            entry = {
                'statistical_code': stat_code,
                'desc_en': desc[:300],
                'desc_jp': '',
                'unit': unit,
                'general_rate': general_rate,
                'temporary_rate': temporary_rate,
                'wto_rate': wto_rate,
                'gsp_rate': gsp_rate,
                'ldc_rate': ldc_rate,
                'epa_rates': epa_rates,
                'jp_us_rate': jp_us_rate,
                'general_parsed': _parse_rate(general_rate),
                'temporary_parsed': _parse_rate(temporary_rate),
                'wto_parsed': _parse_rate(wto_rate),
                'gsp_parsed': _parse_rate(gsp_rate),
            }
            results.append(entry)
            self.data[stat_code] = entry

        # Fetch Japanese descriptions and merge into entries
        if results:
            jp_map = self._scrape_jp_descriptions(chapter_num)
            for entry in results:
                jp_desc = jp_map.get(entry['statistical_code'], '')
                if jp_desc:
                    entry['desc_jp'] = jp_desc
                    self.data[entry['statistical_code']]['desc_jp'] = jp_desc

        return results

    def scrape_all(self, progress_callback=None) -> int:
        """
        Scrape all 97 chapters and save to cache.
        Returns total number of entries scraped.
        """
        total = 0
        for ch in range(1, 98):
            entries = self.scrape_chapter(ch)
            total += len(entries)
            if progress_callback:
                progress_callback(ch, len(entries), total)
            time.sleep(0.5)  # Be polite to customs.go.jp (2 pages per chapter)
        self.save_cache()
        return total

    def get_rates(self, hs_code: str) -> dict | None:
        """Lookup a single code. Returns entry dict or None."""
        normalized = normalize(hs_code)
        entry = self.data.get(normalized)
        if entry:
            return entry
        # Try prefix match (6-digit heading)
        prefix = normalized[:7]  # "XXXX.XX"
        for code, e in self.data.items():
            if code.startswith(prefix):
                return e
        return None

    def search(self, query: str, lang: str = 'en', limit: int = 15) -> list[dict]:
        """
        Smart search with heading-aware scoring.

        Scoring layers:
          1. HS code prefix match                   → 100 pts
          2. Synonym-expanded HS code prefix match   → 50 pts
          3. Token match in entry description         → 10 pts per token
          4. Original (non-expanded) token match      → +5 pts each
          5. Heading-context bonus: heading desc
             matches query concept                    → +25 pts
          6. Propulsion/specificity bonus for EV/
             hybrid queries                           → +15 pts
          7. "For motor vehicles" parts penalty       → -15 pts
          8. Child-row penalty (desc starts "- ")     → -5 pts
          9. Score threshold: drop below 40% of top
        """
        query = query.strip()
        if not query:
            return []

        scored: dict[str, tuple[int, dict]] = {}  # code -> (score, entry)

        # 1. HS code prefix search
        digits = re.sub(r'[^0-9]', '', query)
        if digits and len(digits) >= 2:
            for code, entry in self.data.items():
                code_digits = re.sub(r'[^0-9]', '', code)
                if code_digits.startswith(digits):
                    old_score = scored.get(code, (0, entry))[0]
                    scored[code] = (max(old_score, 100), entry)

        # 2. Tokenized description search
        tokens = re.findall(r'[a-zA-Z]+', query.lower())
        if not tokens:
            results = sorted(
                scored.values(),
                key=lambda x: (-x[0], x[1].get('statistical_code', '')),
            )
            return [entry for _, entry in results[:limit]]

        # Expand tokens with synonyms
        expanded_tokens = set(tokens)
        expanded_codes = set()  # HS code prefixes from synonyms
        for token in tokens:
            syns = KEYWORD_SYNONYMS.get(token, [])
            for syn in syns:
                if re.match(r'^\d', syn):
                    expanded_codes.add(syn)
                else:
                    expanded_tokens.update(syn.lower().split())

        # Detect if this is a vehicle-related query
        _vehicle_words = {
            'car', 'ev', 'vehicle', 'automobile', 'truck', 'bus',
            'motorcycle', 'hybrid', 'phev', 'sedan', 'suv', 'van',
            'tractor', 'motor car',
        }
        is_vehicle_query = bool(set(tokens) & _vehicle_words)

        # Detect EV / electric / hybrid intent
        _ev_words = {'ev', 'electric', 'hybrid', 'phev', 'bev', 'plugin'}
        is_ev_query = bool(set(tokens) & _ev_words)

        # Pre-compute heading matches: which 4-digit headings match expanded tokens
        heading_matches: set[str] = set()  # e.g. {"8703", "8702"}
        for h_code, h_desc in self.headings.items():
            h_lower = h_desc.lower()
            if any(t in h_lower for t in expanded_tokens):
                heading_matches.add(h_code)

        # Score each entry
        for code, entry in self.data.items():
            desc_en = entry.get('desc_en', '').lower()
            desc_jp = entry.get('desc_jp', '')

            match_count = 0
            for token in expanded_tokens:
                if token in desc_en or token in desc_jp:
                    match_count += 1

            if match_count == 0:
                # Still check synonym HS code prefixes below
                continue

            score = match_count * 10

            # Bonus for matching original (non-expanded) tokens
            original_matches = sum(
                1 for t in tokens if t in desc_en or t in desc_jp
            )
            score += original_matches * 5

            # --- Heading-context bonus ---
            entry_heading = code[:4]  # "8703" from "8703.80-000"
            if entry_heading in heading_matches:
                score += 25

            # --- Vehicle-query: boost ch87 vehicles, penalize ch84/85 parts ---
            if is_vehicle_query:
                chapter = code[:2]
                if chapter == '87' and entry_heading in (
                    '8701', '8702', '8703', '8704', '8705',
                ):
                    score += 20  # complete vehicle headings
                if 'for motor vehicle' in desc_en:
                    score -= 15  # it's a part, not a vehicle

            # --- EV/electric propulsion bonus ---
            if is_ev_query:
                if 'only electric motor for propulsion' in desc_en:
                    score += 25  # pure EV — best match
                elif (
                    'capable of being charged by plugging' in desc_en
                    or 'plug-in' in desc_en
                ):
                    score += 15  # PHEV
                elif 'electric motor' in desc_en and 'propulsion' in desc_en:
                    score += 10  # hybrid (has electric motor but not "only")
                elif (
                    'electric motor' in desc_en
                    and entry_heading in ('8703', '8702', '8704')
                ):
                    score += 5  # mentions electric motor in vehicle heading
                # Penalize irrelevant "electric" matches
                if 'cigarette' in desc_en or 'vaporis' in desc_en:
                    score -= 20
                if 'heating resistor' in desc_en:
                    score -= 20
                if ('fan' in desc_en
                        and entry_heading not in ('8703', '8702', '8704')):
                    score -= 10

            # --- Child-row penalty (sub-item like "- Used", "- Other") ---
            raw_desc = entry.get('desc_en', '')
            if raw_desc.startswith(('- ', '-- ')):
                score -= 5

            old_score = scored.get(code, (0, entry))[0]
            scored[code] = (max(old_score, score), entry)

        # Also match by expanded HS code prefixes from synonyms
        for prefix in expanded_codes:
            prefix_digits = prefix.replace('.', '')
            for code, entry in self.data.items():
                code_digits = re.sub(r'[^0-9]', '', code)
                if code_digits.startswith(prefix_digits):
                    old_score = scored.get(code, (0, entry))[0]
                    scored[code] = (max(old_score, 50), entry)

        # Sort by score descending, then by code
        ranked = sorted(
            scored.values(),
            key=lambda x: (-x[0], x[1].get('statistical_code', '')),
        )

        # Score-threshold filtering: drop entries below 40% of top score
        if ranked:
            top_score = ranked[0][0]
            threshold = max(top_score * 0.4, 10)
            ranked = [(s, e) for s, e in ranked if s >= threshold]

        return [entry for _, entry in ranked[:limit]]

    # Keep old method name as alias
    def search_description(self, query: str, lang: str = 'en') -> list[dict]:
        """Alias for search() — backward compatible."""
        return self.search(query, lang=lang)

    def load_cache(self) -> bool:
        """Load from japan/data/jp_tariff.json. Returns True if loaded."""
        if os.path.exists(self.cache_path):
            try:
                with open(self.cache_path, 'r', encoding='utf-8') as f:
                    raw = json.load(f)
                # Cache format: {"_headings": {...}, "XXXX.XX-XXX": {...}, ...}
                if '_headings' in raw:
                    self.headings = raw.pop('_headings')
                self.data = raw
                return bool(self.data)
            except (json.JSONDecodeError, IOError):
                return False
        return False

    def save_cache(self) -> None:
        """Save self.data + self.headings to JSON cache."""
        to_save = dict(self.data)
        to_save['_headings'] = self.headings
        with open(self.cache_path, 'w', encoding='utf-8') as f:
            json.dump(to_save, f, ensure_ascii=False, indent=2)

    def cache_size(self) -> int:
        """Return number of entries in cache."""
        return len(self.data)
