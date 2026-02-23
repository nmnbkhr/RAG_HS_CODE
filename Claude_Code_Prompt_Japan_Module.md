## PROJECT
Repository: github.com/nmnbkhr/RAG_HS_CODE (branch: api-key-handling)
Existing app: Streamlit-based Pakistan Customs HS Code + Duty Calculator.
Entry: app_integrated.py (3,188 lines, 156KB) launched by run.sh on port 8502.

## TASK
Create a STANDALONE Japan Customs HS Code + Duty Calculator app.
It must be 100% ISOLATED from the Pakistan code. Zero shared code.

## HARD RULES (NEVER VIOLATE)
1. DO NOT modify, import from, or reference app_integrated.py
2. DO NOT modify run.sh, pct_latest.pdf, faiss_index/, or any existing file
3. DO NOT create any combined/multi-country entry point
4. DO NOT share classes, functions, or utilities between PK and JP
5. DO NOT reuse WEBOCTariffScraper, fetch_usd_rate_from_nbp, or any Pakistan-specific code
6. DO NOT touch any .db SQLite cache file (query.db, weboc.db, tipp.db, exchange_rate.db, favorites.db, api_health.db, data_freshness.db)
7. DO NOT import from project/ folder or any phase module (phase1-7)
8. DO NOT use or mimic the MODULE_STATUS phase architecture / graceful degradation pattern
9. DO NOT reference _fetch_hs_data_all_sources, the orchestrator, or TIPP
10. DO NOT use the Pakistan FTA/PTA logic (Japan has its own EPA system)
11. DO NOT inherit the Pakistan Green CSS theme or .streamlit/config.toml
12. Japan module lives entirely in japan/ package + app_japan.py + run_japan.sh
13. All UI strings go through japan/i18n.py bilingual system
14. The two apps run on SEPARATE ports (PK stays on 8502, JP on 8503)

## CONTEXT FROM ANALYSIS (what exists — DO NOT touch)
The Pakistan app (app_integrated.py) is a 3,188-line monolith with:
- 7 Streamlit tabs: HS Lookup, Import Calc, Export Calc, Batch Processor, Duty Comparator, Favorites & History, System Status
- 7 phase module directories under project/phase{1-7}_*/src/ with MODULE_STATUS graceful degradation
- 7 SQLite .db cache files in repo root
- Core classes: WEBOCTariffScraper (ASP.NET form POST scraper for weboc.gov.pk)
- Core functions: fetch_usd_rate_from_nbp() (NBP TT Selling/Buying), get_exchange_rate() (PKR conversion), normalize_hs_code() (8-digit XXXX.XXXX)
- _fetch_hs_data_all_sources() orchestrator: WEBOC → TIPP → RAG pipeline
- RAG pipeline: PyPDFLoader → RecursiveCharacterTextSplitter(800/200) → OpenAIEmbeddings → FAISS → GPT-4 LCEL chain
- FTA/PTA country-of-origin → preferential CD rate logic
- Phase 6 compliance: FED rates, Fifth Schedule concessions, SRO database
- Import formula: CIF → CD → AD → RD → FED (on CIF+CD) → ST (on CIF+CD+AD+RD+FED) → IT (on CIF)
- Export rules: No general export duty, DTRE/Manufacturing Bond/EOU schemes
- Pakistan Green UI theme (#01411C) in CSS + .streamlit/config.toml
- HS_CHAPTERS (97 chapters) and HS_KEYWORD_CHAPTERS (~80 keywords) dictionaries
- st.session_state holds: weboc_scraper, orchestrator, caches, qa_chain, vectorstore

The Japan app must be a SIMPLE, FLAT architecture:
- No phase modules, no MODULE_STATUS, no graceful degradation pattern
- JSON file cache (not SQLite)
- Own theme/colors (Japan Blue #1B4F72 primary, #E8F0FE light)
- Only 2 tabs: HS Code Lookup + Import Duty Calculator
- Own .streamlit_japan/ config if custom theme needed

## CREATE THESE FILES (in order):

### 1. japan/__init__.py
Package init. Expose main classes:
```python
from japan.duty_calculator import JapanDutyCalculator
from japan.tariff_scraper import JapanTariffScraper
from japan.i18n import t
```

### 2. japan/i18n.py
Bilingual EN/JP string dictionary with ALL UI labels.
```python
STRINGS = {'en': {...}, 'ja': {...}}
def t(key, lang='en') -> str
```
Cover: app_title, tab names, all form labels, result labels, EPA badge text, disclaimers, error messages, sidebar labels, rate column headers, duty type names, country group names.

Full Japanese translations with proper kanji/katakana:
- app_title → "日本税関関税計算機"
- tab_lookup → "🔍 HSコード検索"
- tab_calc → "🧮 輸入関税計算"
- customs_duty → "関税"
- consumption_tax → "消費税"
- country_origin → "原産国"
- total → "総輸入原価"
- disclaimer → "参考情報です。税関（tax.customs.go.jp）でご確認ください。"
- And all other field labels (FOB→FOB価格, freight→運賃, insurance→保険, etc.)

### 3. japan/hs_normalizer.py
Japan uses 9-digit codes: XXXX.XX-XXX (vs Pakistan 8-digit XXXX.XXXX)
```python
def normalize(code: str) -> str
    # Accepts: 090121010, 0901.21-010, 0901.21010, 090121-010
    # Returns: 0901.21-010

def is_valid(code: str) -> bool

def get_chapter(code: str) -> int
    # Extract 2-digit chapter number (01-97)
```

### 4. japan/epa_database.py
Hardcoded EPA agreement to country mappings. No external data fetch.
```python
EPA_AGREEMENTS = {
    'CPTPP': ['AU','BN','CA','CL','MY','MX','NZ','PE','SG','VN'],
    'RCEP': ['CN','KR','AU','NZ','BN','KH','ID','LA','MY','MM',
             'PH','SG','TH','VN'],
    'Japan-EU': ['AT','BE','BG','HR','CY','CZ','DK','EE','FI','FR',
                 'DE','GR','HU','IE','IT','LV','LT','LU','MT','NL',
                 'PL','PT','RO','SK','SI','ES','SE'],
    'Japan-UK': ['GB'],
    'Japan-US': ['US'],
    'Japan-Singapore': ['SG'],
    'Japan-Mexico': ['MX'],
    'Japan-Malaysia': ['MY'],
    'Japan-Thailand': ['TH'],
    'Japan-Indonesia': ['ID'],
    'Japan-Philippines': ['PH'],
    'Japan-Switzerland': ['CH'],
    'Japan-India': ['IN'],
    'Japan-Mongolia': ['MN'],
}

GSP_BENEFICIARIES = ['PK','BD','LK','NP','KH','LA','MM','ET',
                     'TZ','MZ','SN','MG', ...]

COUNTRY_NAMES = {
    'en': {'AU': 'Australia', 'PK': 'Pakistan', 'CN': 'China', ...},
    'ja': {'AU': 'オーストラリア', 'PK': 'パキスタン', 'CN': '中国', ...}
}

def get_epa_for_country(code: str) -> str | None
    # Returns best EPA agreement name or None
    # Priority if country in multiple: bilateral > CPTPP > RCEP

def get_all_countries() -> dict[str, str]
    # For dropdown population

def get_countries_grouped_by_epa() -> dict[str, list]
    # For grouped dropdown: {'CPTPP': [...], 'RCEP': [...], ...}
```

### 5. japan/tariff_scraper.py
```python
class JapanTariffScraper:
    """
    Scrape Japan Customs HTML tariff tables.
    Source: customs.go.jp/english/tariff/2026_01_01/data/e_XX.htm
    (XX = chapter 01-97)
    """
    def __init__(self, cache_dir='japan/data'):
        self.cache_path = os.path.join(cache_dir, 'jp_tariff.json')
        self.data = {}  # hs_code -> entry dict

    def scrape_chapter(self, chapter_num: int) -> list[dict]:
        # Fetch HTML page, parse table rows
        # Extract: statistical_code, desc_en, desc_jp, unit,
        #          general_rate, wto_rate, temporary_rate
        # Handle rate format parsing (see below)

    def scrape_all(self) -> None:
        # Loop chapters 01-97, scrape each, save to cache JSON

    def get_rates(self, hs_code: str) -> dict | None:
        # Lookup single code. Returns dict with all rate columns.
        # Keys: statistical_code, desc_en, desc_jp, unit,
        #       general_rate, wto_rate, temporary_rate, gsp_rate,
        #       duty_type ('ad_valorem'|'specific'|'combined')

    def search_description(self, query: str, lang='en') -> list[dict]:
        # Fuzzy text search on descriptions. Return top 20 matches.

    def load_cache(self) -> bool:
        # Load from japan/data/jp_tariff.json if exists
        # Returns True if loaded, False if need to scrape

    def save_cache(self) -> None:
        # Save self.data to JSON
```

Rate format parsing rules:
- `'3.9%'` → ad_valorem, value=0.039
- `'Free'` → ad_valorem, value=0.0
- `'70yen/l'` or `'¥70/l'` → specific, value=70.0, per_unit='liter'
- `'23.8%+985yen/kg'` → combined, pct=0.238, per_unit_value=985.0
- `'—'` or empty → None (rate not applicable)

### 6. japan/rate_selector.py
```python
from collections import namedtuple

RateResult = namedtuple('RateResult',
    ['value', 'rate_type', 'agreement', 'duty_type', 'per_unit_value', 'per_unit_name'])
# per_unit_value and per_unit_name only used for specific/combined duties

def select_rate(hs_code: str, country_of_origin: str, rates: dict) -> RateResult:
    """
    Japan rate priority (STRICT ORDER):
      1. EPA rate  (if country has EPA with Japan)
      2. GSP rate  (if country is designated developing country)
      3. WTO rate  (if lower than Temporary and General)
      4. Temporary (if exists, overrides General)
      5. General   (default fallback)
    """
    # Uses epa_database.get_epa_for_country() for EPA check
    # Uses epa_database.GSP_BENEFICIARIES for GSP check
    # Compares numeric rate values for WTO vs Temp vs General
    # Returns RateResult with all fields populated
```

### 7. japan/consumption_tax.py
```python
STANDARD_RATE = 0.10   # 10% (7.8% national + 2.2% local)
REDUCED_RATE = 0.08    # 8% (6.24% national + 1.76% local)

def get_rate(hs_code: str) -> float:
    """
    Chapters 01-24 (food/agriculture) → 0.08 (reduced)
    EXCEPT: Chapter 22 subheadings for alcohol (2203-2208) → 0.10
    Everything else → 0.10 (standard)
    """

def is_food_item(hs_code: str) -> bool:
    # Helper for UI display
```

### 8. japan/excise_tax.py
```python
EXCISE_RATES = {
    # Chapter 22 - Alcohol
    '2203': {'rate': 77.0, 'per': '350ml', 'name_en': 'Beer', 'name_ja': 'ビール'},
    '2204': {'rate': 70.0, 'per': 'liter', 'name_en': 'Wine', 'name_ja': 'ワイン'},
    '2208': {'rate': 20.0, 'per': 'liter', 'name_en': 'Spirits', 'name_ja': '蒸留酒'},
    # Chapter 24 - Tobacco
    '2402': {'rate': 15244.0, 'per': '1000_sticks', 'name_en': 'Cigarettes', 'name_ja': 'たばこ'},
    # Chapter 27 - Petroleum
    '2710': {'rate': 53.8, 'per': 'liter', 'name_en': 'Gasoline', 'name_ja': 'ガソリン'},
}

def calc_excise(hs_code: str, quantity: float, unit: str) -> float:
    # Returns excise amount in JPY. Returns 0.0 if not subject.

def get_excise_info(hs_code: str) -> dict | None:
    # Returns rate info for display, or None if no excise applies
```

### 9. japan/exchange_rate.py
```python
def get_customs_fx(currency: str) -> tuple[float, str]:
    """
    Returns (jpy_per_unit, source_description)
    Try: Japan Customs weekly published rates
    Fallback: exchangerate-api.com/v4/latest/{currency}
    Final fallback: hardcoded reasonable defaults

    Support: USD, EUR, GBP, CNY, KRW, PKR, AUD, CAD, THB, SGD
    Cache rate in st.session_state for 24 hours.
    """

# Hardcoded fallbacks (approximate, updated Feb 2026):
FALLBACK_RATES = {
    'USD': 150.0,
    'EUR': 162.0,
    'GBP': 190.0,
    'CNY': 20.5,
    'KRW': 0.11,
    'PKR': 0.53,
    'AUD': 96.0,
}
```

### 10. japan/simplified_tariff.py
```python
# For commercial imports with total CIF < ¥200,000
SIMPLIFIED_RATES = {
    'wine': {'rate': 70, 'type': 'specific', 'per': 'liter', 'chapters': ['2204']},
    'spirits': {'rate': 20, 'type': 'specific', 'per': 'liter', 'chapters': ['2208']},
    'sake': {'rate': 30, 'type': 'specific', 'per': 'liter', 'chapters': ['2206']},
    'ketchup_ice': {'rate': 0.20, 'type': 'ad_valorem', 'chapters': ['2103','2105']},
    'coffee_tea': {'rate': 0.15, 'type': 'ad_valorem', 'chapters': ['09']},
    'veg_fruit': {'rate': 0.10, 'type': 'ad_valorem', 'chapters': ['07','08']},
    'tableware_toys': {'rate': 0.03, 'type': 'ad_valorem', 'chapters': ['69','95']},
    'rubber_paper': {'rate': 0.00, 'type': 'ad_valorem', 'chapters': ['40','48']},
    'other': {'rate': 0.05, 'type': 'ad_valorem', 'chapters': []},
}

def is_eligible(cif_jpy: float) -> bool:
    return cif_jpy < 200_000

def get_simplified_rate(hs_code: str) -> dict:
    # Match hs_code chapter to SIMPLIFIED_RATES category
    # Returns {'rate': float, 'type': str, 'category': str}
```

### 11. japan/duty_calculator.py
```python
class JapanDutyCalculator:
    def __init__(self):
        self.scraper = JapanTariffScraper()
        self.scraper.load_cache()

    def calculate(self, hs_code, country, fob, freight, insurance,
                  currency, quantity, unit, use_simplified=False) -> dict:
        """
        Full Japan import duty calculation.

        Flow:
        1. CIF_JPY = (FOB + Freight + Insurance) × get_customs_fx(currency)
        2. If use_simplified and CIF < ¥200K: apply simplified rate
        3. Else:
           a. get_rates(hs_code) → all 5 rate columns
           b. select_rate(hs_code, country, rates) → applicable rate
           c. duty = CIF × rate% (ad_valorem)
                  or quantity × rate_per_unit (specific)
                  or both (combined)
        4. excise = calc_excise(hs_code, quantity, unit)
        5. tax_base = CIF + duty + excise
        6. cons_tax = tax_base × get_rate(hs_code)  # 10% or 8%
        7. total = CIF + duty + excise + cons_tax

        Returns dict:
        {
            'hs_code': str,
            'description_en': str,
            'description_jp': str,
            'cif_jpy': float,
            'cif_original': float,
            'currency': str,
            'fx_rate': float,
            'fx_source': str,
            'selected_rate': RateResult,
            'customs_duty': float,
            'excise': float,
            'excise_info': dict | None,
            'consumption_tax': float,
            'consumption_rate': float,  # 0.10 or 0.08
            'is_food': bool,
            'total_landed': float,
            'is_simplified': bool,
            'all_rates': dict,  # all 5 columns for comparison table
        }
        """
```

### 12. app_japan.py (Streamlit Entry Point)
Standalone Streamlit app. Runs independently on port 8503.
Imports ONLY from japan/ package and standard/third-party libs.

```
STRUCTURE:

Page Config:
  st.set_page_config(
      page_title="Japan Customs Calculator / 日本税関計算機",
      page_icon="🇯🇵",
      layout="wide"
  )

Sidebar:
  - 🌐 Language toggle: English / 日本語 (radio, horizontal)
  - 💱 Current FX rate display (JPY/USD)
  - 📋 About section with Japan Customs official links
  - ⚠️ Bilingual disclaimer

Tab 1: HS Code Lookup (検索)
  - Text input for 9-digit code or description (EN or JP)
  - Search button
  - Results show:
    * Bilingual descriptions (EN + JP) side by side in 2 columns
    * All 5 rate columns in a table
    * Unit of measurement
    * Consumption tax rate indicator (10% standard or 8% reduced)
  - Quick example buttons:
    Coffee 0901.21 | Rice 1006.30 | Automobiles 8703.23 | Electronics 8517.12

Tab 2: Import Duty Calculator (計算機)
  - HS code input (can pre-fill from Tab 1 via session_state)
  - Country of Origin dropdown:
    * Grouped by EPA: "── CPTPP ──", "── RCEP ──", "── EU ──", etc.
    * Shows country name in selected language
  - Auto-detect EPA: green badge "✅ EPA: CPTPP" or red badge "❌ No EPA"
  - Input row 1: FOB | Freight | Insurance
  - Input row 2: Currency dropdown (USD,EUR,GBP,CNY,KRW,PKR) | Quantity | Unit
  - Checkbox: "Use Simplified Tariff (< ¥200,000)"
  - Big blue CALCULATE button
  - Results section:
    * 4-column metric row: CIF | Duty | Tax | Total (¥ format)
    * Full breakdown table:
        CIF Value (JPY)           ¥XXX,XXX
        Applied Rate              X.X% (EPA-CPTPP)
        Customs Duty              ¥XX,XXX
        Excise Tax                ¥X,XXX (or "N/A")
        Consumption Tax (10%)     ¥XX,XXX
        ─────────────────────────────────
        Total Landed Cost         ¥XXX,XXX
    * Rate comparison table:
        Agreement    Rate    Status
        General      12%     —
        WTO          12%     —
        Temporary    —       —
        CPTPP        Free    ✅ Applied
        RCEP         8.4%    —
      (Applied rate row highlighted green)
    * Bilingual disclaimer

Footer: Disclaimer in selected language + data source links

CSS/Theme:
  - Primary color: #1B4F72 (Japan Blue)
  - Light background: #E8F0FE
  - Accent: #2E86C1
  - DO NOT use Pakistan Green (#01411C)
```

### 13. run_japan.sh
```bash
#!/bin/bash
# Japan Customs HS Code Calculator - Standalone Launcher
# Runs independently from Pakistan app

# Activate conda environment
source activate rag_hs_env 2>/dev/null || conda activate rag_hs_env 2>/dev/null

# Create japan/data directory if missing
mkdir -p japan/data

# Run on separate port from Pakistan app (PK=8502, JP=8503)
streamlit run app_japan.py --server.port 8503
```

## IMPLEMENTATION ORDER
```
 1. japan/__init__.py          → verify: python -c "import japan"
 2. japan/i18n.py              → verify: python -c "from japan.i18n import t; print(t('app_title','ja'))"
 3. japan/hs_normalizer.py     → verify: python -c "from japan.hs_normalizer import normalize; print(normalize('090121010'))"
 4. japan/epa_database.py      → verify: python -c "from japan.epa_database import get_epa_for_country; print(get_epa_for_country('VN'))"
 5. japan/tariff_scraper.py    → verify: python -c "from japan.tariff_scraper import JapanTariffScraper; print('OK')"
 6. japan/rate_selector.py     → verify: python -c "from japan.rate_selector import select_rate; print('OK')"
 7. japan/consumption_tax.py   → verify: python -c "from japan.consumption_tax import get_rate; print(get_rate('0901.21-010'))"
 8. japan/excise_tax.py        → verify: python -c "from japan.excise_tax import calc_excise; print(calc_excise('2204.21-100', 10, 'liter'))"
 9. japan/exchange_rate.py     → verify: python -c "from japan.exchange_rate import FALLBACK_RATES; print(FALLBACK_RATES)"
10. japan/simplified_tariff.py → verify: python -c "from japan.simplified_tariff import is_eligible; print(is_eligible(150000))"
11. japan/duty_calculator.py   → verify: python -c "from japan.duty_calculator import JapanDutyCalculator; print('OK')"
12. app_japan.py               → run: streamlit run app_japan.py --server.port 8503
13. run_japan.sh               → run: bash run_japan.sh
```

After each file, run the verify command. Fix any import errors before proceeding.

## ISOLATION VERIFICATION (run after all files created)
```bash
# These must ALL return zero matches:
grep -r "app_integrated" japan/ app_japan.py
grep -r "WEBOC" japan/ app_japan.py
grep -r "weboc" japan/ app_japan.py
grep -r "nbp" japan/ app_japan.py
grep -r "faiss_index" japan/ app_japan.py
grep -r "pct_latest" japan/ app_japan.py
grep -r "fbr\.gov" japan/ app_japan.py
grep -r "MODULE_STATUS" japan/ app_japan.py
grep -r "phase[0-9]" japan/ app_japan.py
grep -r "from project" japan/ app_japan.py
grep -r "01411C" japan/ app_japan.py
grep -r "\.db" japan/ app_japan.py | grep -v ".dba"

# This must work:
python -c "from japan import JapanDutyCalculator, JapanTariffScraper, t; print(t('app_title','ja'))"
```

## REMINDER
japan/ is self-contained. app_japan.py imports ONLY from japan/ and standard/third-party libs. The Pakistan app and Japan app share NOTHING except the git repository and conda environment.
