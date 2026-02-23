"""
RAG_HS_CODE - Integrated Streamlit Application
Wires all phase modules into a unified multi-tab UI.

Phase 1: Security & Validation (validators, calculators)
Phase 2: UX Enhancements (history_manager, pdf_exporter, excel_exporter)
Phase 3: Performance & Caching (exchange_rate_cache, weboc_cache, query_cache,
         performance_monitor, offline_manager)
Phase 4: Features (batch_processor, duty_comparator, multi_currency, favorites_manager)
Phase 5: Infrastructure (app_config, health_check)
Phase 6: Compliance (fed_rates, fifth_schedule, fta_pta, sro_database)
Phase 7: Live Data (tipp_scraper, sbp_rates, source_orchestrator, api_health, data_updater)
"""

import os
import re
import sys
import shutil
import io
import json
import jellyfish
from rapidfuzz import fuzz as rfuzz
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import FAISS
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough

# Load environment variables
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if OPENAI_API_KEY:
    OPENAI_API_KEY = OPENAI_API_KEY.strip()
    os.environ["OPENAI_API_KEY"] = OPENAI_API_KEY

# ---------------------------------------------------------------------------
# Phase Module Imports (graceful degradation)
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent
_PHASE_SRC_DIRS = [
    PROJECT_ROOT / "project" / "phase1_security_validation" / "src",
    PROJECT_ROOT / "project" / "phase2_ux_enhancements" / "src",
    PROJECT_ROOT / "project" / "phase3_performance" / "src",
    PROJECT_ROOT / "project" / "phase4_features" / "src",
    PROJECT_ROOT / "project" / "phase5_infrastructure" / "src",
    PROJECT_ROOT / "project" / "phase6_compliance" / "src",
    PROJECT_ROOT / "project" / "phase7_live_data" / "src",
]
for _d in _PHASE_SRC_DIRS:
    _ds = str(_d)
    if _ds not in sys.path:
        sys.path.insert(0, _ds)

MODULE_STATUS = {}

# Phase 1 - Validators
try:
    from validators import (
        HSCodeValidator, NumericValidator, ExchangeRateValidator,
        TextValidator, validate_hs_code
    )
    MODULE_STATUS["validators"] = True
except Exception:
    MODULE_STATUS["validators"] = False

# Phase 1 - Calculators
try:
    from calculators import (
        ImportDutyCalculator, ExportCalculator,
        DutyRates, CIFComponents, CalculationResult, ExportResult
    )
    MODULE_STATUS["calculators"] = True
except Exception:
    MODULE_STATUS["calculators"] = False

# Phase 2 - History
try:
    from history_manager import HistoryManager, CalculationType
    MODULE_STATUS["history_manager"] = True
except Exception:
    MODULE_STATUS["history_manager"] = False

# Phase 2 - PDF Exporter
try:
    from pdf_exporter import DutyCalculationPDF
    MODULE_STATUS["pdf_exporter"] = True
except Exception:
    MODULE_STATUS["pdf_exporter"] = False

# Phase 2 - Excel Exporter
try:
    from excel_exporter import DutyCalculationExcel
    MODULE_STATUS["excel_exporter"] = True
except Exception:
    MODULE_STATUS["excel_exporter"] = False

# Phase 3 - Exchange Rate Cache
try:
    from exchange_rate_cache import ExchangeRateCache
    MODULE_STATUS["exchange_rate_cache"] = True
except Exception:
    MODULE_STATUS["exchange_rate_cache"] = False

# Phase 3 - WEBOC Cache
try:
    from weboc_cache import WEBOCCache
    MODULE_STATUS["weboc_cache"] = True
except Exception:
    MODULE_STATUS["weboc_cache"] = False

# Phase 3 - Query Cache
try:
    from query_cache import QueryCache
    MODULE_STATUS["query_cache"] = True
except Exception:
    MODULE_STATUS["query_cache"] = False

# Phase 3 - Performance Monitor
try:
    from performance_monitor import PerformanceMonitor, get_monitor
    MODULE_STATUS["performance_monitor"] = True
except Exception:
    MODULE_STATUS["performance_monitor"] = False

# Phase 3 - Offline Manager
try:
    from offline_manager import OfflineManager, get_offline_manager
    MODULE_STATUS["offline_manager"] = True
except Exception:
    MODULE_STATUS["offline_manager"] = False

# Phase 4 - Batch Processor
try:
    from batch_processor import (
        process_batch, export_batch_csv, generate_sample_csv
    )
    MODULE_STATUS["batch_processor"] = True
except Exception:
    MODULE_STATUS["batch_processor"] = False

# Phase 4 - Duty Comparator
try:
    from duty_comparator import DutyComparator, DutyProfile
    MODULE_STATUS["duty_comparator"] = True
except Exception:
    MODULE_STATUS["duty_comparator"] = False

# Phase 4 - Multi Currency
try:
    from multi_currency import MultiCurrencyManager, SUPPORTED_CURRENCIES
    MODULE_STATUS["multi_currency"] = True
except Exception:
    MODULE_STATUS["multi_currency"] = False

# Phase 4 - Favorites
try:
    from favorites_manager import FavoritesManager
    MODULE_STATUS["favorites_manager"] = True
except Exception:
    MODULE_STATUS["favorites_manager"] = False

# Phase 5 - App Config
try:
    from app_config import (
        AppPaths, ExternalURLs, CacheSettings, AppLimits,
        DEFAULT_DUTY_RATES, SUPPORTED_CURRENCY_CODES,
        validate_env_vars, validate_api_key
    )
    MODULE_STATUS["app_config"] = True
except Exception:
    MODULE_STATUS["app_config"] = False

# Phase 5 - Health Check
try:
    from health_check import run_health_check
    MODULE_STATUS["health_check"] = True
except Exception:
    MODULE_STATUS["health_check"] = False

# Phase 6 - FED Rates
try:
    from fed_rates import lookup_fed_rate, get_fed_rate_for_import
    MODULE_STATUS["fed_rates"] = True
except Exception:
    MODULE_STATUS["fed_rates"] = False

# Phase 6 - Fifth Schedule
try:
    from fifth_schedule import lookup_concession, get_applicable_concessions
    MODULE_STATUS["fifth_schedule"] = True
except Exception:
    MODULE_STATUS["fifth_schedule"] = False

# Phase 6 - FTA/PTA
try:
    from fta_pta import (
        get_best_rate as get_best_fta_rate, get_agreements_for_country,
        get_rate_comparison, get_all_countries
    )
    MODULE_STATUS["fta_pta"] = True
except Exception:
    MODULE_STATUS["fta_pta"] = False

# Phase 6 - SRO Database
try:
    from sro_database import lookup_sros_for_hs_code, get_active_sros, search_sros
    MODULE_STATUS["sro_database"] = True
except Exception:
    MODULE_STATUS["sro_database"] = False

# Phase 7 - TIPP Scraper
try:
    from tipp_scraper import TIPPScraper, TIPPCache
    MODULE_STATUS["tipp_scraper"] = True
except Exception:
    MODULE_STATUS["tipp_scraper"] = False

# Phase 7 - SBP Rates
try:
    from sbp_rates import SBPRateFetcher
    MODULE_STATUS["sbp_rates"] = True
except Exception:
    MODULE_STATUS["sbp_rates"] = False

# Phase 7 - Source Orchestrator
try:
    from source_orchestrator import SourceOrchestrator
    MODULE_STATUS["source_orchestrator"] = True
except Exception:
    MODULE_STATUS["source_orchestrator"] = False

# Phase 7 - API Health
try:
    from api_health import APIHealthDashboard
    MODULE_STATUS["api_health"] = True
except Exception:
    MODULE_STATUS["api_health"] = False

# Phase 7 - Data Updater
try:
    from data_updater import DataFreshnessChecker
    MODULE_STATUS["data_updater"] = True
except Exception:
    MODULE_STATUS["data_updater"] = False

# Pakistan LLM Search
try:
    from pakistan.llm_search import LLMHSSearch
    from pakistan.pct_hierarchy import (
        get_classification_path, get_heading_description,
        is_part_not_product, HEADING_DESCRIPTIONS
    )
    MODULE_STATUS["llm_search"] = True
except Exception:
    MODULE_STATUS["llm_search"] = False


# ---------------------------------------------------------------------------
# Configuration (use Phase 5 app_config or fallback to inline constants)
# ---------------------------------------------------------------------------
if MODULE_STATUS.get("app_config"):
    _paths = AppPaths.from_root(str(PROJECT_ROOT))
    _urls = ExternalURLs()
    _cache_settings = CacheSettings()
    _limits = AppLimits()

    PDF_URL = _urls.pdf_source
    PDF_PATH = _paths.pdf_path
    FAISS_INDEX_PATH = _paths.faiss_index_path
    WEBOC_TARIFF_URL = _urls.weboc_tariff
    NBP_USD_RATE_URL = _urls.nbp_rates
else:
    PDF_URL = "https://download1.fbr.gov.pk/Docs/20241021010287106PakistanCustomsTariff-2024-25.pdf"
    PDF_PATH = "pct_latest.pdf"
    FAISS_INDEX_PATH = "/mnt/e/rag_hs_codedata/faiss_index"
    WEBOC_TARIFF_URL = "https://www.weboc.gov.pk/Shared/TariffList.aspx"
    NBP_USD_RATE_URL = "https://www.nbp.com.pk/RateSheet/index.aspx?view=ExternalLink"

# Currency list (use Phase 4 or fallback)
if MODULE_STATUS.get("multi_currency"):
    CURRENCY_LIST = list(SUPPORTED_CURRENCIES.keys())
else:
    CURRENCY_LIST = ["USD", "PKR", "EUR", "GBP", "AED", "SAR", "CNY"]


# ---------------------------------------------------------------------------
# HS Code Chapter Names (WCO Harmonized System)
# ---------------------------------------------------------------------------
HS_CHAPTERS = {
    "01": "Live Animals", "02": "Meat", "03": "Fish", "04": "Dairy, Eggs, Honey",
    "05": "Animal Products NES", "06": "Live Trees, Plants", "07": "Vegetables",
    "08": "Edible Fruit & Nuts", "09": "Coffee, Tea, Spices", "10": "Cereals",
    "11": "Milling Products", "12": "Oil Seeds", "13": "Lac, Gums, Resins",
    "14": "Vegetable Plaiting Materials", "15": "Fats & Oils", "16": "Preparations of Meat/Fish",
    "17": "Sugars", "18": "Cocoa", "19": "Preparations of Cereals",
    "20": "Preparations of Vegetables/Fruit", "21": "Misc Edible Preparations",
    "22": "Beverages, Spirits", "23": "Residues, Animal Feed", "24": "Tobacco",
    "25": "Salt, Sulphur, Earths, Stone", "26": "Ores, Slag, Ash",
    "27": "Mineral Fuels, Oils", "28": "Inorganic Chemicals", "29": "Organic Chemicals",
    "30": "Pharmaceutical Products", "31": "Fertilizers", "32": "Tanning, Dyeing Extracts",
    "33": "Essential Oils, Cosmetics", "34": "Soap, Waxes",
    "35": "Albuminoidal Substances, Glues", "36": "Explosives, Matches",
    "37": "Photographic Goods", "38": "Misc Chemical Products",
    "39": "Plastics", "40": "Rubber", "41": "Raw Hides & Skins", "42": "Leather Articles",
    "43": "Furskins", "44": "Wood", "45": "Cork", "46": "Straw, Basketware",
    "47": "Wood Pulp", "48": "Paper & Paperboard", "49": "Printed Books, Newspapers",
    "50": "Silk", "51": "Wool", "52": "Cotton", "53": "Vegetable Textile Fibres",
    "54": "Man-Made Filaments", "55": "Man-Made Staple Fibres", "56": "Wadding, Felt",
    "57": "Carpets", "58": "Special Woven Fabrics", "59": "Impregnated Textiles",
    "60": "Knitted Fabrics", "61": "Knitted Apparel", "62": "Woven Apparel",
    "63": "Other Textile Articles", "64": "Footwear", "65": "Headgear",
    "66": "Umbrellas, Walking-Sticks", "67": "Prepared Feathers",
    "68": "Articles of Stone", "69": "Ceramic Products", "70": "Glass",
    "71": "Precious Metals, Jewellery", "72": "Iron and Steel",
    "73": "Articles of Iron or Steel", "74": "Copper", "75": "Nickel",
    "76": "Aluminium", "78": "Lead", "79": "Zinc", "80": "Tin",
    "81": "Other Base Metals", "82": "Tools of Base Metal",
    "83": "Misc Articles of Base Metal", "84": "Machinery",
    "85": "Electrical Machinery", "86": "Railway Equipment",
    "87": "Vehicles", "88": "Aircraft", "89": "Ships, Boats",
    "90": "Optical, Medical Instruments", "91": "Clocks & Watches",
    "92": "Musical Instruments", "93": "Arms & Ammunition",
    "94": "Furniture, Lighting", "95": "Toys, Games, Sports",
    "96": "Misc Manufactured Articles", "97": "Works of Art",
}


def _detect_broad_category(user_input: str) -> dict:
    """
    Detect if input is a broad HS category (chapter or heading).
    Returns: {'is_broad': bool, 'level': str, 'code': str, 'chapter': str, 'chapter_name': str}
    """
    cleaned = re.sub(r'[^0-9.]', '', user_input.strip())
    digits = cleaned.replace('.', '')

    if not digits:
        return {'is_broad': False, 'level': 'text_search', 'code': user_input,
                'chapter': '', 'chapter_name': ''}

    chapter = digits[:2] if len(digits) >= 2 else digits.zfill(2)
    chapter_name = HS_CHAPTERS.get(chapter, "")

    if len(digits) <= 2:
        return {'is_broad': True, 'level': 'chapter', 'code': chapter,
                'chapter': chapter, 'chapter_name': chapter_name}
    elif len(digits) <= 4:
        return {'is_broad': True, 'level': 'heading', 'code': digits[:4],
                'chapter': chapter, 'chapter_name': chapter_name}
    elif len(digits) <= 6:
        return {'is_broad': True, 'level': 'subheading', 'code': digits[:6],
                'chapter': chapter, 'chapter_name': chapter_name}
    else:
        return {'is_broad': False, 'level': 'specific', 'code': digits[:8],
                'chapter': chapter, 'chapter_name': chapter_name}


# Keyword → chapter mapping for common trade terms
HS_KEYWORD_CHAPTERS = {
    "iron": ["72", "73"], "steel": ["72", "73"], "ferrous": ["72"],
    "copper": ["74"], "nickel": ["75"], "aluminium": ["76"], "aluminum": ["76"],
    "lead": ["78"], "zinc": ["79"], "tin": ["80"],
    "cotton": ["52"], "silk": ["50"], "wool": ["51"], "textile": ["50", "51", "52", "53", "54", "55", "56", "57", "58", "59", "60", "61", "62", "63"],
    "plastic": ["39"], "rubber": ["40"], "leather": ["41", "42"],
    "wood": ["44"], "paper": ["48"], "glass": ["70"], "ceramic": ["69"],
    "vehicle": ["87"], "car": ["87"], "automobile": ["87"], "motorcycle": ["87"],
    "machinery": ["84"], "machine": ["84"], "electrical": ["85"], "electronic": ["85"],
    "pharmaceutical": ["30"], "medicine": ["30"], "drug": ["30"],
    "chemical": ["28", "29", "38"], "fertilizer": ["31"], "fertiliser": ["31"],
    "fruit": ["08"], "apple": ["08"], "mango": ["08"], "orange": ["08"], "grape": ["08"],
    "banana": ["08"], "pear": ["08"], "peach": ["08"], "cherry": ["08"], "date": ["08"],
    "strawberry": ["08"], "watermelon": ["08"], "lemon": ["08"], "lime": ["08"],
    "pineapple": ["08"], "plum": ["08"], "apricot": ["08"], "guava": ["08"], "pomegranate": ["08"],
    "vegetable": ["07"], "potato": ["07"], "tomato": ["07"], "onion": ["07"], "garlic": ["07"],
    "carrot": ["07"], "pea": ["07"], "bean": ["07"], "chilli": ["07"], "pepper": ["07"],
    "meat": ["02"], "chicken": ["02"], "beef": ["02"], "mutton": ["02"],
    "fish": ["03"], "shrimp": ["03"], "prawn": ["03"],
    "dairy": ["04"], "milk": ["04"], "butter": ["04"], "cheese": ["04"], "egg": ["04"],
    "cereal": ["10"], "rice": ["10"], "wheat": ["10"], "maize": ["10"], "corn": ["10"],
    "flour": ["11"], "sugar": ["17"],
    "oil": ["15", "27"], "fuel": ["27"], "petroleum": ["27"], "gas": ["27"],
    "tobacco": ["24"], "tea": ["09"], "coffee": ["09"], "spice": ["09"],
    "furniture": ["94"], "toy": ["95"], "footwear": ["64"], "shoe": ["64"],
    "jewellery": ["71"], "jewelry": ["71"], "gold": ["71"], "silver": ["71"],
    "cement": ["25"], "stone": ["25", "68"], "marble": ["25", "68"],
    "aircraft": ["88"], "ship": ["89"], "boat": ["89"], "railway": ["86"],
    "instrument": ["90"], "medical": ["90"], "watch": ["91"], "clock": ["91"],
    "arms": ["93"], "weapon": ["93"], "ammunition": ["93"],
    "soap": ["34"], "cosmetic": ["33"], "perfume": ["33"],
    "carpet": ["57"], "rug": ["57"],
    "mobile": ["85"], "phone": ["85"], "computer": ["84"], "laptop": ["84"],
    "battery": ["85"], "cable": ["85"], "wire": ["72", "73", "74", "76"],
    "pipe": ["73"], "tube": ["73"], "bolt": ["73"], "screw": ["73"], "nail": ["73"],
    "tyre": ["40"], "tire": ["40"],
    # Clothing & apparel (Ch. 61 knitted, Ch. 62 woven, Ch. 63 other textiles)
    "shirt": ["61", "62"], "t-shirt": ["61"], "tshirt": ["61"], "tee": ["61"],
    "trouser": ["61", "62"], "pant": ["61", "62"], "jean": ["62"], "denim": ["62"],
    "jacket": ["61", "62"], "coat": ["61", "62"], "sweater": ["61"], "hoodie": ["61"],
    "dress": ["61", "62"], "skirt": ["61", "62"], "blouse": ["62"],
    "underwear": ["61", "62"], "sock": ["61"], "stocking": ["61"],
    "scarf": ["61", "62"], "shawl": ["62"], "tie": ["62"], "necktie": ["62"],
    "glove": ["61", "62"], "hat": ["65"], "cap": ["65"], "headgear": ["65"],
    "garment": ["61", "62"], "apparel": ["61", "62"], "clothing": ["61", "62"],
    "uniform": ["61", "62"], "sportswear": ["61", "62"],
    "blanket": ["63"], "bedsheet": ["63"], "towel": ["63"], "curtain": ["63"],
    "bag": ["42", "63"], "suitcase": ["42"], "handbag": ["42"],
}


def _depluralize(word: str) -> set:
    """Return a set of possible singular stems for a word."""
    stems = {word}
    if word.endswith("s"):
        stems.add(word[:-1])       # apples → apple
    if word.endswith("es"):
        stems.add(word[:-2])       # tomatoes → tomato
    if word.endswith("ies"):
        stems.add(word[:-3] + "y") # batteries → battery
    return stems


def _phonetic_keys(word: str) -> set:
    """Return a set of phonetic encodings for a word (Soundex + Metaphone)."""
    keys = set()
    try:
        keys.add(jellyfish.soundex(word))
    except Exception:
        pass
    try:
        keys.add(jellyfish.metaphone(word))
    except Exception:
        pass
    return {k for k in keys if k}


def _match_strength(query: str, description: str) -> int:
    """
    Score how well a query matches an HS code description (0-100).
    Combines exact substring, phonetic, and fuzzy matching.
    """
    if not query or not description:
        return 0
    q = query.strip().lower()
    desc = description.lower()
    stems = _depluralize(q)
    q_phonetics = set()
    for s in stems:
        q_phonetics.update(_phonetic_keys(s))

    # Exact substring match in description → highest score
    for s in stems:
        if s in desc:
            # Boost if it matches a whole word
            words = desc.split()
            for w in words:
                if s == w:
                    return 100  # exact word match
            return 95  # substring match

    # Per-word scoring: phonetic + fuzzy against each description word
    desc_words = [w for w in desc.split() if len(w) > 2]
    best = 0
    for dw in desc_words:
        dw_phonetics = _phonetic_keys(dw)
        phonetic_bonus = 15 if (q_phonetics & dw_phonetics) else 0
        for s in stems:
            fz = rfuzz.ratio(s, dw)
            score = min(fz + phonetic_bonus, 100)
            if score > best:
                best = score
    return int(best)


def _strength_color(score: int) -> str:
    """Return a hex color for match strength: green (strong) → yellow → red (weak)."""
    if score >= 90:
        return "#1B5E20"   # dark green — exact/near-exact
    elif score >= 80:
        return "#2E7D32"   # green — strong
    elif score >= 70:
        return "#F9A825"   # amber — moderate
    elif score >= 60:
        return "#E65100"   # orange — weak
    else:
        return "#B71C1C"   # red — poor


def _get_chapters_for_keyword(keyword: str) -> list:
    """
    Get matching chapter codes for a keyword. Priority order:
    0. Multi-word: try full phrase, hyphenated, and each word separately
    1. Exact match (iron → iron)
    2. Depluralized stem (apples → apple)
    3. Substring containment (medicines contains medicine)
    4. Phonetic match confirmed by fuzzy ≥ 70%
    5. Pure fuzzy ≥ 90% (catches typos that change phonetic codes)
    Returns list of 2-digit chapter strings.
    """
    keyword_lower = keyword.strip().lower()
    if not keyword_lower:
        return []

    # --- Tier 0: Multi-word handling ---
    # "tee shirt" → try "tee shirt", "tee-shirt", "teeshirt", then "tee" and "shirt" individually
    words = keyword_lower.split()
    if len(words) > 1:
        # Try joined variants: "tee shirt" → "tee-shirt", "teeshirt"
        hyphenated = "-".join(words)
        joined = "".join(words)
        for variant in [keyword_lower, hyphenated, joined]:
            if variant in HS_KEYWORD_CHAPTERS:
                return HS_KEYWORD_CHAPTERS[variant]
        # Try each word individually, merge chapters
        all_chapters = set()
        for w in words:
            chs = _get_chapters_for_keyword(w)  # recursive single-word lookup
            all_chapters.update(chs)
        if all_chapters:
            return sorted(all_chapters)

    # --- Tier 1: Exact match ---
    if keyword_lower in HS_KEYWORD_CHAPTERS:
        return HS_KEYWORD_CHAPTERS[keyword_lower]

    # --- Tier 2: Depluralized stem match ---
    stems = _depluralize(keyword_lower)
    for stem in stems:
        if stem in HS_KEYWORD_CHAPTERS:
            return HS_KEYWORD_CHAPTERS[stem]

    # --- Tier 3: Substring / partial match ---
    partial_matches = set()
    for key, chapters in HS_KEYWORD_CHAPTERS.items():
        for stem in stems:
            if key in stem or stem in key:
                partial_matches.update(chapters)
    if partial_matches:
        return sorted(partial_matches)

    # --- Tier 4: Phonetic match confirmed by fuzzy ≥ 70% ---
    # Phonetic codes already confirm the words sound alike,
    # so a lower fuzzy threshold is safe (e.g. iren→iron 75%, koper→copper 73%)
    input_phonetics = set()
    for stem in stems:
        input_phonetics.update(_phonetic_keys(stem))

    ph_best_score = 0
    ph_best_chapters = []
    for key, chapters in HS_KEYWORD_CHAPTERS.items():
        key_phonetics = _phonetic_keys(key)
        if not (input_phonetics & key_phonetics):
            continue
        for stem in stems:
            score = rfuzz.ratio(stem, key)
            if score > ph_best_score:
                ph_best_score = score
                ph_best_chapters = chapters

    if ph_best_score >= 70:
        return ph_best_chapters

    # --- Tier 5: Pure fuzzy ≥ 90% (strict, no phonetic needed) ---
    # Catches typos like "applse"→"apple" where phonetic codes differ
    fz_best_score = 0
    fz_best_chapters = []
    for key, chapters in HS_KEYWORD_CHAPTERS.items():
        for stem in stems:
            score = rfuzz.ratio(stem, key)
            if score > fz_best_score:
                fz_best_score = score
                fz_best_chapters = chapters

    if fz_best_score >= 90:
        return fz_best_chapters

    return []


# ---------------------------------------------------------------------------
# WEBOC Scraper (kept from original app - core RAG functionality)
# ---------------------------------------------------------------------------
class WEBOCTariffScraper:
    """Enhanced scraper for WEBOC duty data with UOM extraction"""

    def __init__(self, base_url: str = None):
        self.base_url = base_url or WEBOC_TARIFF_URL
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.last_error = None
        self.hs_code_cache = None

    def normalize_hs_code(self, hs_code: str) -> str:
        digits = re.sub(r'\D', '', hs_code)
        if len(digits) < 8:
            digits = digits.ljust(8, '0')
        elif len(digits) > 8:
            digits = digits[:8]
        return f"{digits[:4]}.{digits[4:]}"

    def get_form_data(self, html: str) -> dict:
        soup = BeautifulSoup(html, 'html.parser')
        hidden_fields = soup.find_all('input', type='hidden')
        data = {}
        for field in hidden_fields:
            name = field.get('name')
            value = field.get('value', '')
            if name:
                data[name] = value
        return data

    def extract_unit_of_measure(self, text: str) -> str:
        uom_patterns = {
            r'\bkg\b|\bkilogram|\bkgs\b': 'kg',
            r'\blitre|\bliter|\blitres|\bliters': 'liters',
            r'\btonne|\bton\b|\btonnes|\btons\b|\bmt\b': 'tonnes',
            r'\bunit|\bunits|\bpiece|\bpieces|\bpcs\b|\bno\b|\bnos\b': 'units',
            r'\bmetre|\bmeter|\bmetres|\bmeters|\bmtr\b': 'meters',
            r'\bpair|\bpairs|\bprs\b': 'pairs',
            r'\bdozen|\bdozens|\bdoz\b': 'dozens',
            r'\bset|\bsets': 'sets',
            r'\bsqm|\bsq\.m|\bsquare meter': 'sqm',
            r'\bcum|\bcu\.m|\bcubic meter': 'cum'
        }
        text_lower = text.lower()
        for pattern, uom in uom_patterns.items():
            if re.search(pattern, text_lower):
                return uom
        return 'units'

    def search_hs_code(self, hs_code: str) -> dict:
        normalized_code = self.normalize_hs_code(hs_code)
        try:
            response = self.session.get(self.base_url, timeout=15, allow_redirects=True)
            if response.status_code != 200:
                return self._error_result(normalized_code, f"HTTP {response.status_code}")

            actual_url = response.url
            form_data = self.get_form_data(response.text)

            if not form_data.get('__VIEWSTATE'):
                return self._error_result(normalized_code, "Session expired")

            soup = BeautifulSoup(response.text, 'html.parser')
            search_box = soup.find('input', {'id': re.compile('txtSearch', re.I)})
            search_button = soup.find('input', {'id': re.compile('btnSearch', re.I)})

            if not search_box:
                return self._error_result(normalized_code, "Search controls not found")

            search_box_name = search_box.get('name', 'TariffList$txtSearch')
            search_button_name = search_button.get('name', 'TariffList$btnSearch') if search_button else 'TariffList$btnSearch'

            payload = {
                **form_data,
                search_box_name: normalized_code,
                search_button_name: 'Search'
            }

            post_response = self.session.post(
                actual_url,
                data=payload,
                headers={
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Referer': actual_url
                },
                timeout=20
            )

            if post_response.status_code != 200:
                return self._error_result(normalized_code, "Search failed")

            result = self.parse_duty_table(post_response.text, normalized_code)
            if result:
                result['status'] = 'success'
                result['search_code'] = normalized_code
                return result
            else:
                return self._error_result(normalized_code, "No duty data found")

        except Exception as e:
            return self._error_result(normalized_code, str(e))

    def _error_result(self, code: str, error: str) -> dict:
        self.last_error = error
        return {
            'search_code': code, 'status': 'failed', 'error': error,
            'customs_duty': None, 'sales_tax': None, 'income_tax': None,
            'additional_duty': None, 'regulatory_duty': None,
            'description': None, 'unit_of_measure': 'units'
        }

    def parse_duty_table(self, html: str, hs_code: str) -> dict:
        soup = BeautifulSoup(html, 'html.parser')
        duty_table = soup.find('table', {'id': re.compile('dgDutyDetail', re.I)})
        if not duty_table:
            duty_table = soup.find('table', class_=re.compile('duty', re.I))
        if not duty_table:
            tables = soup.find_all('table')
            for table in tables:
                text = table.get_text().lower()
                if 'customs duty' in text or 'sales tax' in text:
                    duty_table = table
                    break
        if not duty_table:
            return None

        result = {
            'hs_code': hs_code, 'customs_duty': None, 'sales_tax': None,
            'income_tax': None, 'additional_duty': None, 'regulatory_duty': None,
            'description': None, 'unit_of_measure': 'units'
        }

        desc_selectors = [
            {'id': re.compile('lblDescription|Description', re.I)},
            {'class': re.compile('description', re.I)}
        ]
        for selector in desc_selectors:
            desc_element = soup.find('span', selector) or soup.find('div', selector)
            if desc_element:
                result['description'] = desc_element.get_text(strip=True)
                result['unit_of_measure'] = self.extract_unit_of_measure(result['description'])
                break

        rows = duty_table.find_all('tr')
        for row in rows:
            cells = row.find_all(['td', 'th'])
            if len(cells) >= 2:
                label = cells[0].get_text(strip=True).lower()
                value_text = cells[1].get_text(strip=True)
                try:
                    value = float(re.search(r'[\d.]+', value_text).group())
                except (AttributeError, ValueError):
                    value = None
                if 'customs duty' in label or 'cd' == label:
                    result['customs_duty'] = value
                elif 'sales tax' in label or 'st' == label:
                    result['sales_tax'] = value
                elif 'income tax' in label or 'it' == label:
                    result['income_tax'] = value
                elif 'additional' in label or 'ad' == label:
                    result['additional_duty'] = value
                elif 'regulatory' in label or 'rd' == label:
                    result['regulatory_duty'] = value
        return result

    def _ensure_cache_loaded(self):
        """Load full HS code list from WEBOC into cache on first call."""
        if not self.hs_code_cache:
            all_codes = self.fetch_hs_code_list("")
            if all_codes:
                self.hs_code_cache = all_codes

    def search_hs_codes_autocomplete(self, query: str, limit: int = 50) -> list:
        self._ensure_cache_loaded()
        if self.hs_code_cache:
            query_clean = query.replace('.', '').lower()
            is_text = not query_clean.replace('.', '').isdigit()
            results = []
            # 1. Exact substring match (fast)
            for item in self.hs_code_cache:
                code_clean = item['code'].replace('.', '')
                desc_clean = item['description'].lower()
                if query_clean in code_clean or query_clean in desc_clean:
                    results.append(item)
                    if len(results) >= limit:
                        break
            # 2. Only if exact substring found NOTHING, try fuzzy on descriptions
            if is_text and not results:
                seen = set()
                fuzzy_scored = []
                for item in self.hs_code_cache:
                    desc = item['description'].lower()
                    # Use plain ratio (not token_set) to avoid loose matches on long descriptions
                    # Compare query against individual words in description for tighter matching
                    desc_words = desc.split()
                    best_word_score = max(
                        (rfuzz.ratio(query_clean, w) for w in desc_words),
                        default=0
                    )
                    if best_word_score >= 85:
                        fuzzy_scored.append((best_word_score, item))
                fuzzy_scored.sort(key=lambda x: x[0], reverse=True)
                for _score, item in fuzzy_scored[:limit]:
                    if item['code'] not in seen:
                        seen.add(item['code'])
                        results.append(item)
            return results
        return self.fetch_hs_code_list(query)[:limit]

    def fetch_hs_code_list(self, search_prefix: str = "") -> list:
        try:
            response = self.session.get(self.base_url, timeout=15, allow_redirects=True)
            if response.status_code != 200:
                return []
            soup = BeautifulSoup(response.text, 'html.parser')
            hs_codes = []
            select_elements = soup.find_all('select')
            for select in select_elements:
                options = select.find_all('option')
                for option in options:
                    code = option.get('value', '').strip()
                    text = option.get_text(strip=True)
                    if code and re.match(r'\d{4}\.\d{4}', code):
                        hs_codes.append({'code': code, 'description': text,
                                         'unit': self.extract_unit_of_measure(text)})
            if not hs_codes:
                tables = soup.find_all('table')
                for table in tables:
                    rows = table.find_all('tr')
                    for row in rows:
                        cells = row.find_all(['td', 'th'])
                        if len(cells) >= 2:
                            code_text = cells[0].get_text(strip=True)
                            desc_text = cells[1].get_text(strip=True) if len(cells) > 1 else ''
                            if re.match(r'\d{4}\.\d{4}', code_text):
                                hs_codes.append({'code': code_text, 'description': desc_text,
                                                 'unit': self.extract_unit_of_measure(desc_text)})
            if search_prefix:
                search_clean = search_prefix.replace('.', '').strip()
                if search_clean.isdigit():
                    # Numeric → prefix match on code
                    hs_codes = [item for item in hs_codes if item['code'].replace('.', '').startswith(search_clean)]
                else:
                    # Text → match in description (case-insensitive)
                    search_lower = search_clean.lower()
                    hs_codes = [item for item in hs_codes if search_lower in item.get('description', '').lower()]
            seen = set()
            unique_codes = []
            for item in hs_codes:
                if item['code'] not in seen:
                    seen.add(item['code'])
                    unique_codes.append(item)
            return unique_codes[:1000]
        except Exception:
            return []


# ---------------------------------------------------------------------------
# Exchange Rate Functions (with optional cache)
# ---------------------------------------------------------------------------
def fetch_usd_rate_from_nbp():
    """Fetch USD exchange rates from NBP"""
    rates = {'tt_selling': None, 'tt_buying': None}
    try:
        response = requests.get(NBP_USD_RATE_URL, timeout=15)
        if response.status_code == 200:
            text = response.text
            selling_patterns = [
                r'TT.*?Selling[^\d]*(\d{3}\.\d{2,4})',
                r'Selling.*?TT[^\d]*(\d{3}\.\d{2,4})',
                r'USD.*?Selling[^\d]*(\d{3}\.\d{2,4})',
            ]
            buying_patterns = [
                r'TT.*?Buying[^\d]*(\d{3}\.\d{2,4})',
                r'Buying.*?TT[^\d]*(\d{3}\.\d{2,4})',
                r'USD.*?Buying[^\d]*(\d{3}\.\d{2,4})',
            ]
            for pattern in selling_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    rate = float(match.group(1))
                    if 200 < rate < 400:
                        rates['tt_selling'] = rate
                        break
            for pattern in buying_patterns:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    rate = float(match.group(1))
                    if 200 < rate < 400:
                        rates['tt_buying'] = rate
                        break
            if rates['tt_selling'] or rates['tt_buying']:
                if not rates['tt_selling'] and rates['tt_buying']:
                    rates['tt_selling'] = rates['tt_buying'] + 2.0
                if not rates['tt_buying'] and rates['tt_selling']:
                    rates['tt_buying'] = rates['tt_selling'] - 2.0
                return rates
        try:
            sbp_response = requests.get(
                "https://www.sbp.org.pk/ecodata/rates/m2m/m2m-current.asp", timeout=10)
            if sbp_response.status_code == 200:
                match = re.search(r'USD[^\d]*(\d{3}\.\d{2,4})', sbp_response.text)
                if match:
                    rate = float(match.group(1))
                    if 200 < rate < 400:
                        return {'tt_selling': rate + 1.0, 'tt_buying': rate - 1.0}
        except Exception:
            pass
    except Exception:
        pass
    return {'tt_selling': 280.50, 'tt_buying': 278.50}


def get_exchange_rate(from_currency, transaction_type='import'):
    """Get PKR conversion rate with optional Phase 3 caching."""
    currency = from_currency.upper()
    if currency == "PKR":
        return 1.0, "PKR (no conversion)"

    # Try Phase 3 cache first
    if MODULE_STATUS.get("exchange_rate_cache") and "exchange_cache" in st.session_state:
        cache = st.session_state.exchange_cache
        cached = cache.get(currency)
        if cached:
            if transaction_type == 'export':
                return cached.tt_buying, f"Cached NBP TT Buying ({cached.age_display})"
            else:
                return cached.tt_selling, f"Cached NBP TT Selling ({cached.age_display})"

    if currency == "USD":
        rates = fetch_usd_rate_from_nbp()

        # Store in cache
        if MODULE_STATUS.get("exchange_rate_cache") and "exchange_cache" in st.session_state:
            cache = st.session_state.exchange_cache
            if rates['tt_buying'] and rates['tt_selling']:
                cache.put(currency, rates['tt_buying'], rates['tt_selling'], source="NBP")

        if transaction_type == 'export':
            if rates['tt_buying'] and rates['tt_buying'] > 200:
                return rates['tt_buying'], "NBP TT Buying (Export Rate)"
            return 278.50, "Estimated TT Buying (Export)"
        else:
            if rates['tt_selling'] and rates['tt_selling'] > 200:
                return rates['tt_selling'], "NBP TT Selling (Import Rate)"
            return 280.50, "Estimated TT Selling (Import)"

    try:
        response = requests.get(f"https://api.exchangerate-api.com/v4/latest/{currency}", timeout=10)
        if response.status_code == 200:
            rate_data = response.json().get("rates", {})
            pkr_rate = rate_data.get("PKR")
            if pkr_rate:
                return pkr_rate, "Market Rate"
    except Exception:
        pass
    return 1.0, "Default"


def _get_weboc_data_cached(scraper, hs_code):
    """Fetch WEBOC data with optional Phase 3 caching."""
    if MODULE_STATUS.get("weboc_cache") and "weboc_cache" in st.session_state:
        cache = st.session_state.weboc_cache
        cached = cache.get(hs_code)
        if cached:
            return cached.to_dict()

    # Track performance
    monitor = st.session_state.get("perf_monitor")
    if monitor and MODULE_STATUS.get("performance_monitor"):
        with monitor.track("weboc_search", {"hs_code": hs_code}):
            result = scraper.search_hs_code(hs_code)
    else:
        result = scraper.search_hs_code(hs_code)

    # Cache successful results
    if result.get('status') == 'success' and MODULE_STATUS.get("weboc_cache") and "weboc_cache" in st.session_state:
        cache = st.session_state.weboc_cache
        cache.put(
            hs_code=hs_code,
            duty_data={
                'customs_duty': result.get('customs_duty'),
                'sales_tax': result.get('sales_tax'),
                'income_tax': result.get('income_tax'),
                'additional_duty': result.get('additional_duty'),
                'regulatory_duty': result.get('regulatory_duty'),
                'description': result.get('description'),
                'unit_of_measure': result.get('unit_of_measure', 'units'),
            },
            source="WEBOC"
        )

    return result


def _detect_unit(text: str) -> str:
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


PERSIST_BASE = "/mnt/e/raghscode"


def _persist_hs_definition(data: dict, country: str = "Pakistan"):
    """
    Save an HS code tariff definition to disk.
    Path: /mnt/e/raghscode/{country}/{YYYY-MM-DD}_{hs_code}.json
    Silently skips if the disk path is unavailable.
    """
    try:
        hs_code = data.get("hs_code", "unknown").replace(".", "")
        today = datetime.now().strftime("%Y-%m-%d")
        country_clean = re.sub(r'[^\w\s-]', '', country.strip()).replace(" ", "_") or "Pakistan"

        folder = os.path.join(PERSIST_BASE, country_clean)
        os.makedirs(folder, exist_ok=True)

        filename = f"{today}_{hs_code}.json"
        filepath = os.path.join(folder, filename)

        record = {
            "hs_code": data.get("hs_code", ""),
            "description": data.get("description", ""),
            "customs_duty_pct": data.get("customs_duty", 0),
            "sales_tax_pct": data.get("sales_tax", 0),
            "income_tax_pct": data.get("income_tax", 0),
            "additional_duty_pct": data.get("additional_duty", 0),
            "regulatory_duty_pct": data.get("regulatory_duty", 0),
            "federal_excise_duty_pct": data.get("federal_excise_duty", 0),
            "unit_of_measure": data.get("unit_of_measure", "units"),
            "source": data.get("source", "unknown"),
            "country": country,
            "fetched_at": datetime.now().isoformat(),
            "sro_references": data.get("sro_references", []),
        }

        # If file already exists for today, update it (latest data wins)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2, ensure_ascii=False)
    except Exception:
        pass  # Disk unavailable or permission error — don't break the app


def _persist_subcodes(subcodes: list, prefix: str, country: str = "Pakistan"):
    """Save a batch of sub-codes under a chapter/heading to disk."""
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        country_clean = re.sub(r'[^\w\s-]', '', country.strip()).replace(" ", "_") or "Pakistan"
        folder = os.path.join(PERSIST_BASE, country_clean)
        os.makedirs(folder, exist_ok=True)

        filename = f"{today}_chapter_{prefix}.json"
        filepath = os.path.join(folder, filename)

        records = []
        for sc in subcodes:
            records.append({
                "hs_code": sc.get("code", ""),
                "description": sc.get("description", ""),
                "customs_duty_pct": sc.get("customs_duty"),
                "unit_of_measure": sc.get("unit", "units"),
            })

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump({
                "prefix": prefix,
                "chapter_name": HS_CHAPTERS.get(prefix[:2], ""),
                "country": country,
                "fetched_at": datetime.now().isoformat(),
                "count": len(records),
                "codes": records,
            }, f, indent=2, ensure_ascii=False)
    except Exception:
        pass


def _get_subcodes(prefix: str, limit: int = 50) -> list:
    """
    Get all sub-codes under a prefix from WEBOC cache and TIPP cache.
    Returns: list of {'code': str, 'description': str, 'unit': str, 'customs_duty': float|None}
    """
    results = []
    seen = set()
    prefix_clean = prefix.replace('.', '')

    # 1. Try WEBOC autocomplete cache (fastest, in-memory)
    try:
        weboc = st.session_state.get('weboc_scraper')
        if weboc:
            matches = weboc.search_hs_codes_autocomplete(prefix_clean, limit=limit)
            for m in matches:
                code = m.get('code', '')
                if code.replace('.', '').startswith(prefix_clean) and code not in seen:
                    seen.add(code)
                    results.append({
                        'code': code, 'description': m.get('description', ''),
                        'unit': m.get('unit', 'units'), 'customs_duty': None
                    })
    except Exception:
        pass

    # 2. If cache missed, try fetching directly from WEBOC with prefix filter
    if not results:
        try:
            weboc = st.session_state.get('weboc_scraper')
            if weboc:
                direct = weboc.fetch_hs_code_list(prefix_clean)
                for m in direct:
                    code = m.get('code', '')
                    if code not in seen:
                        seen.add(code)
                        results.append({
                            'code': code, 'description': m.get('description', ''),
                            'unit': m.get('unit', 'units'), 'customs_duty': None
                        })
        except Exception:
            pass

    # 3. Enrich from TIPP cache (has duty rates)
    if MODULE_STATUS.get("tipp_scraper"):
        try:
            cache_path = os.path.join(os.path.dirname(__file__), "tipp_cache.db")
            if os.path.exists(cache_path):
                cache = TIPPCache(db_path=cache_path)
                tipp_results = cache.search(prefix_clean)
                for tr in tipp_results:
                    if tr.hs_code not in seen:
                        seen.add(tr.hs_code)
                        results.append({
                            'code': tr.hs_code, 'description': tr.description,
                            'unit': tr.unit_of_measure, 'customs_duty': tr.mfn_cd_rate
                        })
                    else:
                        for r in results:
                            if r['code'] == tr.hs_code and r['customs_duty'] is None:
                                r['customs_duty'] = tr.mfn_cd_rate
                                if not r['description']:
                                    r['description'] = tr.description
        except Exception:
            pass

    # 4. If still nothing, try TIPP scraper live for a few headings under the prefix
    if not results and MODULE_STATUS.get("tipp_scraper"):
        try:
            scraper = TIPPScraper()
            tipp_result = scraper.search(prefix_clean)
            if tipp_result:
                results.append({
                    'code': tipp_result.hs_code, 'description': tipp_result.description,
                    'unit': getattr(tipp_result, 'unit_of_measure', 'units'),
                    'customs_duty': tipp_result.mfn_cd_rate
                })
        except Exception:
            pass

    # 5. Last resort: ask RAG/vectorstore for sub-codes under this prefix
    if not results:
        try:
            chapter_name = HS_CHAPTERS.get(prefix_clean[:2], "")
            rag_query = (
                f"List ALL HS/PCT codes (full 8-digit format like XXXX.XXXX) under "
                f"chapter/heading {prefix_clean} ({chapter_name}). "
                f"For each code provide: HS Code, Description, Customs Duty (CD) %. "
                f"Format each as: XXXX.XXXX | Description | XX%"
            )
            rag_result = _invoke_qa_chain(rag_query)
            if rag_result:
                # Parse lines like "7201.1010 | Description text | 3%"  or "7201.1010 - Description - CD 3%"
                code_pattern = re.compile(
                    r'(\d{4}\.\d{4})\s*[\|:\-–]\s*(.+?)(?:\s*[\|:\-–]\s*(?:CD\s*)?(\d+(?:\.\d+)?)\s*%)?$',
                    re.MULTILINE
                )
                for m in code_pattern.finditer(rag_result):
                    code = m.group(1)
                    if code.replace('.', '').startswith(prefix_clean) and code not in seen:
                        seen.add(code)
                        desc = m.group(2).strip().rstrip('|').strip()
                        cd = float(m.group(3)) if m.group(3) else None
                        results.append({
                            'code': code, 'description': desc,
                            'unit': _detect_unit(desc), 'customs_duty': cd
                        })
                # Also try simpler pattern: just 8-digit codes in the text
                if not results:
                    simple_codes = re.findall(r'\b(\d{4}\.\d{4})\b', rag_result)
                    for code in simple_codes:
                        if code.replace('.', '').startswith(prefix_clean) and code not in seen:
                            seen.add(code)
                            # Extract nearby description text
                            idx = rag_result.find(code)
                            nearby = rag_result[idx:idx+150] if idx >= 0 else ""
                            desc_m = re.search(r'\d{4}\.\d{4}\s*[\|:\-–]?\s*(.+?)(?:\n|$)', nearby)
                            desc = desc_m.group(1).strip()[:80] if desc_m else ""
                            results.append({
                                'code': code, 'description': desc,
                                'unit': _detect_unit(desc), 'customs_duty': None
                            })
        except Exception:
            pass

    results.sort(key=lambda x: x['code'])
    final = results[:limit]
    if final:
        _persist_subcodes(final, prefix)
    return final


def _fetch_hs_data_all_sources(hs_code: str, country: str = "Pakistan") -> dict:
    """
    Fetch HS code data from all available sources (orchestrator → WEBOC → TIPP → RAG).
    Returns a unified dict with status, duty rates, description, unit, and source.
    Persists successful results to /mnt/e/raghscode/{country}/.
    """
    hs_code = hs_code.strip()
    if not hs_code:
        return {"status": "error", "error": "Empty HS code"}

    # 1. Try SourceOrchestrator (aggregates TIPP + WEBOC + Phase 6 static data)
    if MODULE_STATUS.get("source_orchestrator") and "orchestrator" in st.session_state:
        try:
            orch = st.session_state.orchestrator
            duty_data, source = orch.get_duty_rates(hs_code)
            if duty_data and duty_data.get("customs_duty") is not None:
                desc = duty_data.get("description", "")
                unit = duty_data.get("unit_of_measure", "")
                if not unit or unit == "units":
                    unit = _detect_unit(desc)
                result = {
                    "hs_code": hs_code,
                    "status": "success",
                    "customs_duty": duty_data.get("customs_duty", 0),
                    "sales_tax": duty_data.get("sales_tax", 18.0),
                    "income_tax": duty_data.get("income_tax", 6.0),
                    "additional_duty": duty_data.get("additional_duty", 0),
                    "regulatory_duty": duty_data.get("regulatory_duty", 0),
                    "description": desc,
                    "unit_of_measure": unit,
                    "source": source or "Orchestrator",
                }
                # Enrich with compliance info
                try:
                    compliance = orch.get_compliance_info(hs_code)
                    if compliance.get("fed") and compliance["fed"].get("applicable"):
                        result["federal_excise_duty"] = compliance["fed"].get("rate", 0)
                    if compliance.get("sro_references"):
                        result["sro_references"] = compliance["sro_references"]
                    if compliance.get("best_preferential_rate") is not None:
                        result["best_preferential_rate"] = compliance["best_preferential_rate"]
                except Exception:
                    pass
                _persist_hs_definition(result, country)
                return result
        except Exception:
            pass

    # 2. Try WEBOC directly
    try:
        weboc_result = _get_weboc_data_cached(st.session_state.weboc_scraper, hs_code)
        if weboc_result.get("status") == "success":
            # If WEBOC returned no description, try to enrich from TIPP or RAG
            if not weboc_result.get("description"):
                # Try TIPP for description
                if MODULE_STATUS.get("tipp_scraper"):
                    try:
                        _scraper = TIPPScraper()
                        _tipp = _scraper.search(hs_code)
                        if _tipp and _tipp.description:
                            weboc_result["description"] = _tipp.description
                            if not weboc_result.get("unit_of_measure") or weboc_result["unit_of_measure"] == "units":
                                weboc_result["unit_of_measure"] = getattr(_tipp, 'unit_of_measure', '') or _detect_unit(_tipp.description)
                    except Exception:
                        pass
                # Still no description — try RAG
                if not weboc_result.get("description"):
                    try:
                        _qa = _invoke_qa_chain(f"What is the description for HS/PCT code {hs_code}?")
                        if _qa:
                            _dm = re.search(r'(?:Description|classify|refers to)[:\s]*(.+?)(?:\n|Customs|$)', _qa, re.IGNORECASE | re.DOTALL)
                            if _dm:
                                weboc_result["description"] = _dm.group(1).strip()
                    except Exception:
                        pass
            # Detect unit from description if still missing
            if weboc_result.get("description") and (not weboc_result.get("unit_of_measure") or weboc_result["unit_of_measure"] == "units"):
                weboc_result["unit_of_measure"] = _detect_unit(weboc_result["description"])
            _persist_hs_definition(weboc_result, country)
            return weboc_result
    except Exception:
        pass

    # 3. Try TIPP scraper directly
    if MODULE_STATUS.get("tipp_scraper"):
        try:
            scraper = TIPPScraper()
            tipp_result = scraper.search(hs_code)
            if tipp_result:
                desc = tipp_result.description or ""
                unit = getattr(tipp_result, 'unit_of_measure', '') or _detect_unit(desc)
                tipp_data = {
                    "hs_code": hs_code,
                    "status": "success",
                    "customs_duty": tipp_result.mfn_cd_rate,
                    "sales_tax": tipp_result.sales_tax_rate,
                    "income_tax": 6.0,
                    "additional_duty": tipp_result.additional_duty_rate,
                    "regulatory_duty": tipp_result.regulatory_duty_rate,
                    "description": desc,
                    "unit_of_measure": unit,
                    "source": "TIPP",
                }
                _persist_hs_definition(tipp_data, country)
                return tipp_data
        except Exception:
            pass

    # 4. Fallback to RAG/QA chain
    try:
        qa_result = _invoke_qa_chain(
            f"What is the detailed classification, description, and Customs Duty (CD %) for HS/PCT code {hs_code}?"
        )
        if qa_result:
            cd_match = re.search(r'Customs\s+Duty.*?(\d+(?:\.\d+)?)\s*%', qa_result, re.IGNORECASE)
            desc_match = re.search(r'Description:\s*(.+?)(?:\n|Customs|$)', qa_result, re.IGNORECASE | re.DOTALL)
            st_match = re.search(r'Sales\s+Tax.*?(\d+(?:\.\d+)?)\s*%', qa_result, re.IGNORECASE)
            it_match = re.search(r'(?:Income|Advance)\s+Tax.*?(\d+(?:\.\d+)?)\s*%', qa_result, re.IGNORECASE)
            desc_text = desc_match.group(1).strip() if desc_match else ""
            rag_data = {
                "hs_code": hs_code,
                "status": "success",
                "customs_duty": float(cd_match.group(1)) if cd_match else 0,
                "sales_tax": float(st_match.group(1)) if st_match else 18.0,
                "income_tax": float(it_match.group(1)) if it_match else 6.0,
                "additional_duty": 0,
                "regulatory_duty": 0,
                "description": desc_text,
                "unit_of_measure": _detect_unit(desc_text) if desc_text else _detect_unit(qa_result),
                "source": "PCT Tariff Database",
            }
            _persist_hs_definition(rag_data, country)
            return rag_data
    except Exception:
        pass

    return {"hs_code": hs_code, "status": "error", "error": "Not found in any source"}


# ---------------------------------------------------------------------------
# PDF & Vectorstore Functions (kept from original app)
# ---------------------------------------------------------------------------
def check_pdf_update(url, local_path):
    try:
        response = requests.head(url, timeout=10)
        if response.status_code == 200:
            last_modified_str = response.headers.get('Last-Modified')
            if last_modified_str:
                remote_date = datetime.strptime(last_modified_str, '%a, %d %b %Y %H:%M:%S GMT')
                if os.path.exists(local_path):
                    local_date = datetime.fromtimestamp(os.path.getmtime(local_path))
                    if remote_date > local_date:
                        download_latest_pdf(url, local_path)
                        return True, "PDF updated - vectorstore will be rebuilt"
                    else:
                        return False, "PDF is up-to-date"
                else:
                    download_latest_pdf(url, local_path)
                    return True, "PDF downloaded - vectorstore will be created"
            else:
                if not os.path.exists(local_path):
                    download_latest_pdf(url, local_path)
                    return True, "PDF downloaded"
                return False, "PDF exists locally"
        else:
            return False, f"Failed to check PDF: HTTP {response.status_code}"
    except Exception as e:
        return False, f"Error checking PDF: {str(e)}"


def download_latest_pdf(url, save_path):
    try:
        response = requests.get(url, timeout=30, stream=True)
        if response.status_code == 200:
            with open(save_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True, f"Downloaded {os.path.getsize(save_path) / (1024*1024):.2f} MB"
        else:
            return False, f"Download failed: HTTP {response.status_code}"
    except Exception as e:
        return False, f"Download error: {str(e)}"


def get_pdf_info():
    if os.path.exists(PDF_PATH):
        size_mb = os.path.getsize(PDF_PATH) / (1024 * 1024)
        modified_time = datetime.fromtimestamp(os.path.getmtime(PDF_PATH))
        return {'exists': True, 'size_mb': size_mb, 'modified': modified_time,
                'modified_str': modified_time.strftime('%Y-%m-%d %H:%M:%S')}
    return {'exists': False}


def rebuild_vectorstore_from_pdf():
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise Exception("OPENAI_API_KEY not found")
    if not os.path.exists(PDF_PATH):
        raise Exception(f"PDF file not found at {PDF_PATH}")
    loader = PyPDFLoader(PDF_PATH)
    documents = loader.load()
    processed_documents = []
    for doc in documents:
        page_num = doc.metadata.get('page', 0)
        hs_codes = re.findall(r'\b\d{4}\.\d{4}\b', doc.page_content)
        metadata = {
            'source': PDF_PATH, 'page': page_num,
            'hs_codes': ', '.join(hs_codes[:5]) if hs_codes else '',
            'document_type': 'Pakistan Customs Tariff FY 2024-25',
            'created_at': datetime.now().isoformat()
        }
        processed_documents.append(Document(page_content=doc.page_content, metadata=metadata))
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=800, chunk_overlap=200, separators=["\n\n", "\n", "|", " ", ""]
    )
    texts = text_splitter.split_documents(processed_documents)
    embeddings = OpenAIEmbeddings(openai_api_key=api_key)
    vectorstore = FAISS.from_documents(texts, embeddings)
    vectorstore.save_local(FAISS_INDEX_PATH)
    return len(texts), len(documents)


@st.cache_resource
def get_vectorstore():
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        st.error("OPENAI_API_KEY not found in environment variables.")
        return None
    if os.path.exists(FAISS_INDEX_PATH):
        try:
            embeddings = OpenAIEmbeddings(openai_api_key=api_key)
            vectorstore = FAISS.load_local(
                FAISS_INDEX_PATH, embeddings, allow_dangerous_deserialization=True)
            if getattr(vectorstore, 'index', getattr(vectorstore, '_index', None)) is not None:
                return vectorstore
            else:
                st.warning("Vectorstore corrupted, will rebuild...")
                shutil.rmtree(FAISS_INDEX_PATH)
        except Exception as e:
            st.warning(f"Error loading vectorstore: {e}. Will rebuild...")
            if os.path.exists(FAISS_INDEX_PATH):
                shutil.rmtree(FAISS_INDEX_PATH)
    if not os.path.exists(PDF_PATH):
        st.info("Downloading Pakistan Customs Tariff PDF...")
        success, message = check_pdf_update(PDF_URL, PDF_PATH)
        if not success and not os.path.exists(PDF_PATH):
            st.error(f"Failed to download PDF: {message}")
            return None
    try:
        st.info("Building vectorstore from PDF. This may take a few minutes...")
        progress_placeholder = st.empty()
        with progress_placeholder.container():
            with st.spinner("Processing PDF and creating embeddings..."):
                chunks, pages = rebuild_vectorstore_from_pdf()
        embeddings = OpenAIEmbeddings(openai_api_key=api_key)
        vectorstore = FAISS.load_local(
            FAISS_INDEX_PATH, embeddings, allow_dangerous_deserialization=True)
        progress_placeholder.success(f"Vectorstore created! {pages} pages -> {chunks} chunks.")
        return vectorstore
    except Exception as e:
        st.error(f"Failed to build vectorstore: {str(e)}")
        return None


def setup_qa_chain(vectorstore):
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None
    llm = ChatOpenAI(temperature=0.3, model="gpt-4", openai_api_key=api_key)
    prompt_template = """You are an expert in Pakistan Customs Tariff (PCT) classification.

REQUIREMENTS:
1. Use FULL 8-digit HS codes (e.g., 0808.1000)
2. Include Customs Duty (CD) percentage
3. Extract: PCT CODE | DESCRIPTION | CD (%)

OUTPUT FORMAT:
HS/PCT Code: [FULL 8-digit code]
Description: [complete description]
Customs Duty (CD): [percentage]%

Context: {context}
Question: {question}

Answer:"""
    prompt = ChatPromptTemplate.from_template(prompt_template)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 8})

    def format_docs(docs):
        return "\n\n".join(doc.page_content for doc in docs)

    rag_chain = (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | prompt | llm | StrOutputParser()
    )
    return rag_chain


def normalize_hs_code(code):
    """Normalize HS code - use Phase 1 validator if available."""
    if MODULE_STATUS.get("validators"):
        result = HSCodeValidator.validate(code, allow_partial=True)
        if result.is_valid:
            return result.value
    if not code:
        return code
    code = code.strip()
    code = re.sub(r'[^\d.]', '', code)
    if re.match(r'^\d{4}\.\d{4}$', code):
        return code
    match = re.match(r'^(\d{4})\.(\d+)$', code)
    if match:
        prefix = match.group(1)
        suffix = match.group(2).ljust(4, '0')
        return f"{prefix}.{suffix}"
    return code


def _build_tariff_data_for_search():
    """Build {hs_code: {description: ...}} dict from caches for LLM validation."""
    if 'tariff_data_for_search' in st.session_state:
        return st.session_state.tariff_data_for_search

    import sqlite3
    tariff_data = {}

    # 1. WEBOC cache DB
    try:
        db_path = os.path.join(os.path.dirname(__file__), "weboc_cache.db")
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            for row in conn.execute("SELECT hs_code, description FROM duty_data WHERE description IS NOT NULL AND description != ''"):
                tariff_data[row[0]] = {'description': row[1]}
            conn.close()
    except Exception:
        pass

    # 2. TIPP cache DB
    try:
        db_path = os.path.join(os.path.dirname(__file__), "tipp_cache.db")
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            for row in conn.execute("SELECT hs_code, data_json FROM tipp_cache"):
                if row[0] not in tariff_data:
                    try:
                        data = json.loads(row[1])
                        tariff_data[row[0]] = {'description': data.get('description', '')}
                    except Exception:
                        pass
            conn.close()
    except Exception:
        pass

    # 3. FAISS vectorstore — parse HS codes from document chunks
    try:
        vs = st.session_state.get('vectorstore')
        if vs and len(tariff_data) < 100:
            all_docs = vs.similarity_search("customs tariff", k=50)
            code_pat = re.compile(r'(\d{4}\.\d{4})\s*[\|:\-–]?\s*(.+?)(?:\n|\d{4}\.\d{4}|$)')
            for doc in all_docs:
                for m in code_pat.finditer(doc.page_content):
                    code, desc = m.group(1), m.group(2).strip()[:100]
                    if code not in tariff_data and desc:
                        tariff_data[code] = {'description': desc}
    except Exception:
        pass

    if tariff_data:
        st.session_state.tariff_data_for_search = tariff_data

    return tariff_data


def _invoke_qa_chain(query):
    """Invoke QA chain with optional Phase 3 caching."""
    if MODULE_STATUS.get("query_cache") and "query_cache" in st.session_state:
        cache = st.session_state.query_cache
        cached = cache.get(query)
        if cached:
            return cached

    if 'qa_chain' not in st.session_state:
        return None

    monitor = st.session_state.get("perf_monitor")
    if monitor and MODULE_STATUS.get("performance_monitor"):
        with monitor.track("rag_query", {"query": query[:50]}):
            result = st.session_state.qa_chain.invoke(query)
    else:
        result = st.session_state.qa_chain.invoke(query)

    if MODULE_STATUS.get("query_cache") and "query_cache" in st.session_state:
        st.session_state.query_cache.put(query, result)

    return result


# ---------------------------------------------------------------------------
# Helper: Calculate import duties using Phase 1 calculator or inline fallback
# ---------------------------------------------------------------------------
def _calculate_import_duties(
    hs_code, quantity, unit, unit_value, currency,
    exchange_rate, rate_source, duty_data, freight, insurance, other_charges,
    preferential_cd_rate=None, origin_country=None
):
    """Return a dict with all calculated values."""
    cd_rate = duty_data.get('customs_duty', 0) or 0
    mfn_cd_rate = cd_rate
    if preferential_cd_rate is not None:
        cd_rate = preferential_cd_rate
    st_rate = duty_data.get('sales_tax', 0) or 0
    it_rate = duty_data.get('income_tax', 0) or 0
    ad_rate = duty_data.get('additional_duty', 0) or 0
    rd_rate = duty_data.get('regulatory_duty', 0) or 0
    fed_rate = duty_data.get('federal_excise_duty', 0) or 0
    data_source = duty_data.get('source', 'WEBOC')

    # Auto-lookup FED rate from Phase 6 if not provided by WEBOC
    if fed_rate == 0 and MODULE_STATUS.get("fed_rates"):
        fed_rate = get_fed_rate_for_import(hs_code)

    if MODULE_STATUS.get("calculators"):
        rates = DutyRates(
            customs_duty=cd_rate, sales_tax=st_rate, income_tax=it_rate,
            additional_duty=ad_rate, regulatory_duty=rd_rate,
            federal_excise_duty=fed_rate
        )
        cif = CIFComponents(
            fob_value=unit_value * quantity,
            freight=freight, insurance=insurance, other_charges=other_charges
        )
        calc_result = ImportDutyCalculator.calculate(
            hs_code=hs_code, quantity=quantity, unit_of_measure=unit,
            unit_value=unit_value, currency=currency,
            exchange_rate=exchange_rate, exchange_rate_source=rate_source,
            duty_rates=rates, cif_components=cif, data_source=data_source
        )
        return {
            'fob_value': calc_result.fob_value_foreign,
            'cif_value_foreign': calc_result.cif_value_foreign,
            'cif_value_pkr': calc_result.cif_value_pkr,
            'cd_rate': calc_result.customs_duty_rate,
            'st_rate': calc_result.sales_tax_rate,
            'it_rate': calc_result.income_tax_rate,
            'ad_rate': calc_result.additional_duty_rate,
            'rd_rate': calc_result.regulatory_duty_rate,
            'fed_rate': calc_result.federal_excise_duty_rate,
            'customs_duty': calc_result.customs_duty_amount,
            'additional_duty': calc_result.additional_duty_amount,
            'regulatory_duty': calc_result.regulatory_duty_amount,
            'federal_excise_duty': calc_result.federal_excise_duty_amount,
            'sales_tax': calc_result.sales_tax_amount,
            'income_tax': calc_result.income_tax_amount,
            'total_duties': calc_result.total_duties,
            'total_landed_cost': calc_result.total_landed_cost,
            'effective_rate': calc_result.effective_duty_rate,
            'exchange_rate': exchange_rate,
            'rate_source': rate_source,
            'data_source': data_source,
            'calc_result_obj': calc_result,
            'mfn_cd_rate': mfn_cd_rate,
            'origin_country': origin_country or '',
        }

    # Inline fallback (same formula as original appuiux.py)
    fob_value = unit_value * quantity
    cif_value_foreign = fob_value + freight + insurance + other_charges
    cif_value_pkr = cif_value_foreign * exchange_rate
    customs_duty = cif_value_pkr * (cd_rate / 100)
    additional_duty = cif_value_pkr * (ad_rate / 100)
    regulatory_duty = cif_value_pkr * (rd_rate / 100)
    federal_excise_duty = (cif_value_pkr + customs_duty) * (fed_rate / 100)
    sales_tax_base = cif_value_pkr + customs_duty + additional_duty + regulatory_duty + federal_excise_duty
    sales_tax = sales_tax_base * (st_rate / 100)
    income_tax = cif_value_pkr * (it_rate / 100)
    total_duties = customs_duty + additional_duty + regulatory_duty + federal_excise_duty + sales_tax + income_tax
    total_landed_cost = cif_value_pkr + total_duties

    return {
        'fob_value': fob_value,
        'cif_value_foreign': cif_value_foreign,
        'cif_value_pkr': cif_value_pkr,
        'cd_rate': cd_rate, 'st_rate': st_rate, 'it_rate': it_rate,
        'ad_rate': ad_rate, 'rd_rate': rd_rate, 'fed_rate': fed_rate,
        'customs_duty': customs_duty, 'additional_duty': additional_duty,
        'regulatory_duty': regulatory_duty, 'federal_excise_duty': federal_excise_duty,
        'sales_tax': sales_tax,
        'income_tax': income_tax, 'total_duties': total_duties,
        'total_landed_cost': total_landed_cost,
        'effective_rate': (total_duties / cif_value_pkr * 100) if cif_value_pkr > 0 else 0,
        'exchange_rate': exchange_rate, 'rate_source': rate_source,
        'data_source': data_source, 'calc_result_obj': None,
        'mfn_cd_rate': mfn_cd_rate, 'origin_country': origin_country or '',
    }


# ---------------------------------------------------------------------------
# Streamlit App Configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Pakistan Customs - HS Code & Duty Calculator",
    page_icon="🇵🇰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS — Pakistan Green Professional Theme
st.markdown("""
<style>
    /* ===== CSS VARIABLES ===== */
    :root {
        --pk-green: #01411C;
        --pk-green-light: #1B6E4A;
        --pk-green-pale: #E8F5E9;
        --bg: #F8F9FA;
        --card-bg: #FFFFFF;
        --text-primary: #1A1A2E;
        --text-secondary: #4A5568;
        --border: #E2E8F0;
        --success: #16A34A;
        --warning: #D97706;
        --error: #DC2626;
        --info: #2563EB;
        --radius: 8px;
        --shadow: 0 2px 8px rgba(0,0,0,0.06);
        --shadow-lg: 0 4px 16px rgba(0,0,0,0.1);
    }

    /* ===== BASE ===== */
    .main { padding: 1rem 2rem; background: var(--bg); }
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }

    /* ===== HEADER ===== */
    .main-header {
        background: linear-gradient(135deg, #01411C 0%, #1B6E4A 60%, #2D8B5E 100%);
        padding: 2rem 2.5rem; border-radius: var(--radius); color: white;
        margin-bottom: 2rem; box-shadow: var(--shadow-lg);
        border-bottom: 4px solid #014F22;
        position: relative; overflow: hidden;
    }
    .main-header::before {
        content: ''; position: absolute; top: -50%; right: -20%;
        width: 300px; height: 300px;
        background: radial-gradient(circle, rgba(255,255,255,0.06) 0%, transparent 70%);
        border-radius: 50%;
    }
    .main-header h1 { margin: 0; font-size: 2.2rem; font-weight: 800; letter-spacing: -0.5px; }
    .main-header p { margin: 0.5rem 0 0 0; font-size: 1.05rem; opacity: 0.85; }
    .header-badge {
        display: inline-block; background: rgba(255,255,255,0.15);
        border: 1px solid rgba(255,255,255,0.25);
        padding: 0.2rem 0.75rem; border-radius: 20px;
        font-size: 0.8rem; margin-top: 0.5rem; font-weight: 500;
    }

    /* ===== TAB BAR ===== */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem; background-color: var(--card-bg);
        padding: 0.5rem; border-radius: var(--radius);
        border: 1px solid var(--border); box-shadow: var(--shadow);
    }
    .stTabs [data-baseweb="tab"] {
        padding: 0.75rem 1.5rem; border-radius: 6px; font-weight: 600;
        font-size: 0.9rem; color: var(--text-secondary);
        border-bottom: 3px solid transparent; transition: all 0.2s ease;
    }
    .stTabs [data-baseweb="tab"]:hover {
        background: var(--pk-green-pale); color: var(--pk-green);
    }
    .stTabs [aria-selected="true"] {
        color: var(--pk-green) !important;
        border-bottom: 3px solid var(--pk-green) !important;
        background: var(--pk-green-pale) !important; font-weight: 700;
    }

    /* ===== SECTION HEADERS ===== */
    .section-header {
        font-size: 1.2rem; font-weight: 700; color: var(--text-primary);
        margin: 1.5rem 0 1rem 0; padding: 0.6rem 0 0.5rem 1rem;
        border-left: 4px solid var(--pk-green);
        border-bottom: 1px solid var(--border);
        background: linear-gradient(90deg, var(--pk-green-pale) 0%, transparent 100%);
        border-radius: 0 var(--radius) 0 0;
    }

    /* ===== BUTTONS ===== */
    .stButton > button {
        border-radius: 6px; font-weight: 600;
        transition: all 0.2s ease; border: none; letter-spacing: 0.3px;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(1, 65, 28, 0.25);
    }
    /* Primary buttons — force Pakistan Green */
    .stButton > button[kind="primary"],
    .stButton > button[data-testid="stBaseButton-primary"],
    button[data-testid="baseButton-primary"] {
        background: linear-gradient(135deg, #01411C 0%, #1B6E4A 100%) !important;
        color: white !important; border: none !important;
    }
    .stButton > button[kind="primary"]:hover,
    .stButton > button[data-testid="stBaseButton-primary"]:hover,
    button[data-testid="baseButton-primary"]:hover {
        background: linear-gradient(135deg, #012F14 0%, #01411C 100%) !important;
    }
    /* Secondary buttons — green outline */
    .stButton > button[kind="secondary"],
    .stButton > button[data-testid="stBaseButton-secondary"],
    button[data-testid="baseButton-secondary"] {
        background: white !important; color: #01411C !important;
        border: 2px solid #01411C !important;
    }
    .stButton > button[kind="secondary"]:hover,
    .stButton > button[data-testid="stBaseButton-secondary"]:hover,
    button[data-testid="baseButton-secondary"]:hover {
        background: #E8F5E9 !important;
    }
    /* Download buttons — green */
    .stDownloadButton > button {
        background: linear-gradient(135deg, #01411C 0%, #1B6E4A 100%) !important;
        color: white !important; border: none !important;
        border-radius: 6px; font-weight: 600;
    }
    .stDownloadButton > button:hover {
        background: linear-gradient(135deg, #012F14 0%, #01411C 100%) !important;
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(1, 65, 28, 0.25);
    }

    /* ===== INPUT FOCUS STATES ===== */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stSelectbox > div > div > select {
        border-radius: 6px; border: 2px solid var(--border); padding: 0.75rem;
        transition: border-color 0.2s ease, box-shadow 0.2s ease;
    }
    .stTextInput > div > div > input:focus,
    .stNumberInput > div > div > input:focus {
        border-color: var(--pk-green) !important;
        box-shadow: 0 0 0 3px rgba(1, 65, 28, 0.15) !important;
        outline: none;
    }
    div[data-baseweb="select"] > div {
        border-radius: 6px !important;
        transition: border-color 0.2s ease, box-shadow 0.2s ease;
    }
    div[data-baseweb="select"] > div:focus-within {
        border-color: var(--pk-green) !important;
        box-shadow: 0 0 0 3px rgba(1, 65, 28, 0.15) !important;
    }

    /* ===== METRIC CARDS ===== */
    [data-testid="stMetric"] {
        background: var(--card-bg); border: 1px solid var(--border);
        border-left: 4px solid var(--pk-green); border-radius: var(--radius);
        padding: 1rem 1.25rem; box-shadow: var(--shadow);
        transition: box-shadow 0.2s ease;
    }
    [data-testid="stMetric"]:hover { box-shadow: var(--shadow-lg); }
    [data-testid="stMetricLabel"] {
        font-size: 0.8rem; font-weight: 600; color: var(--text-secondary);
        text-transform: uppercase; letter-spacing: 0.5px;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.6rem; font-weight: 700; color: var(--pk-green);
    }

    /* ===== FORM CARDS ===== */
    .form-card {
        background: var(--card-bg); border: 1px solid var(--border);
        border-radius: var(--radius); padding: 1.5rem;
        margin-bottom: 1.5rem; box-shadow: var(--shadow);
    }
    .info-card {
        background: var(--card-bg); border: 1px solid var(--border);
        border-radius: var(--radius); padding: 1.5rem;
        margin-bottom: 1rem; box-shadow: var(--shadow);
    }

    /* ===== STATUS BADGES ===== */
    .status-badge {
        display: inline-flex; align-items: center; gap: 6px;
        padding: 0.25rem 0.75rem; border-radius: 20px;
        font-size: 0.8rem; font-weight: 600; letter-spacing: 0.3px;
    }
    .status-badge::before {
        content: ''; width: 8px; height: 8px;
        border-radius: 50%; display: inline-block;
    }
    .status-online { background: #D1FAE5; color: #065F46; }
    .status-online::before { background: #16A34A; box-shadow: 0 0 4px #16A34A; }
    .status-offline { background: #FEE2E2; color: #991B1B; }
    .status-offline::before { background: #DC2626; box-shadow: 0 0 4px #DC2626; }
    .status-slow, .status-degraded { background: #FEF3C7; color: #92400E; }
    .status-slow::before, .status-degraded::before { background: #D97706; box-shadow: 0 0 4px #D97706; }
    .status-unknown, .status-not-configured { background: #F3F4F6; color: #6B7280; }
    .status-unknown::before, .status-not-configured::before { background: #9CA3AF; }

    /* ===== SUCCESS / INFO / WARNING BOXES ===== */
    .success-box {
        background: linear-gradient(135deg, #D1FAE5 0%, #ECFDF5 100%);
        border-left: 4px solid var(--success);
        padding: 1rem 1.25rem; border-radius: 0 var(--radius) var(--radius) 0;
        margin: 1rem 0; box-shadow: var(--shadow);
    }
    .info-box {
        background: linear-gradient(135deg, #DBEAFE 0%, #EFF6FF 100%);
        border-left: 4px solid var(--info);
        padding: 1rem 1.25rem; border-radius: 0 var(--radius) var(--radius) 0;
        margin: 1rem 0; box-shadow: var(--shadow);
    }
    .warning-box {
        background: linear-gradient(135deg, #FEF3C7 0%, #FFFBEB 100%);
        border-left: 4px solid var(--warning);
        padding: 1rem 1.25rem; border-radius: 0 var(--radius) var(--radius) 0;
        margin: 1rem 0; box-shadow: var(--shadow);
    }

    /* ===== ALERTS ===== */
    .stAlert { border-radius: var(--radius); border-left: 4px solid; padding: 1rem 1.25rem; }

    /* ===== DATAFRAMES ===== */
    .stDataFrame {
        border-radius: var(--radius); overflow: hidden;
        box-shadow: var(--shadow); border: 1px solid var(--border);
    }
    /* Table header — green */
    .stDataFrame [data-testid="stDataFrameResizable"] th,
    .stDataFrame thead th {
        background: #01411C !important; color: white !important;
        font-weight: 600; font-size: 0.85rem; text-transform: uppercase;
        letter-spacing: 0.3px;
    }
    /* Alternating rows */
    .stDataFrame tbody tr:nth-child(even) {
        background: #F0F7F2;
    }
    .stDataFrame tbody tr:hover {
        background: #E8F5E9;
    }

    /* ===== SIDEBAR ===== */
    .sidebar-card {
        background: var(--card-bg); border: 1px solid var(--border);
        border-radius: var(--radius); padding: 1rem;
        margin-bottom: 0.75rem; box-shadow: var(--shadow);
    }
    .sidebar-card h4 {
        margin: 0 0 0.5rem 0; font-size: 0.85rem; font-weight: 700;
        color: var(--pk-green); text-transform: uppercase; letter-spacing: 0.5px;
    }
    section[data-testid="stSidebar"] { background: #F0F7F2; border-right: 1px solid var(--border); }
    section[data-testid="stSidebar"] .stMarkdown h3 {
        color: var(--pk-green); font-size: 0.95rem;
        text-transform: uppercase; letter-spacing: 0.5px;
    }

    /* ===== FOOTER ===== */
    .app-footer {
        background: linear-gradient(135deg, #01411C 0%, #1B6E4A 100%);
        color: white; padding: 1.5rem 2rem; border-radius: var(--radius);
        margin-top: 2rem; text-align: center;
    }
    .app-footer p { margin: 0.25rem 0; font-size: 0.9rem; opacity: 0.9; }
    .app-footer .footer-title { font-weight: 700; font-size: 1rem; opacity: 1; letter-spacing: 0.3px; }
    .app-footer .footer-disclaimer {
        font-size: 0.75rem; opacity: 0.7; margin-top: 0.75rem;
        padding-top: 0.75rem; border-top: 1px solid rgba(255,255,255,0.2);
    }
    .app-footer a { color: #A7F3D0; text-decoration: none; }
    .app-footer a:hover { text-decoration: underline; }

    /* ===== SECTION DIVIDER ===== */
    .section-divider {
        height: 1px;
        background: linear-gradient(90deg, transparent, var(--border), transparent);
        margin: 1.5rem 0; border: none;
    }

    /* ===== MOBILE ===== */
    @media (max-width: 768px) {
        .main { padding: 0.5rem 1rem; }
        .main-header { padding: 1.25rem; }
        .main-header h1 { font-size: 1.6rem; }
        .stTabs [data-baseweb="tab-list"] { gap: 0.25rem; padding: 0.25rem; }
        .stTabs [data-baseweb="tab"] { padding: 0.5rem 0.75rem; font-size: 0.8rem; }
        [data-testid="stMetric"] { padding: 0.75rem; }
        [data-testid="stMetricValue"] { font-size: 1.2rem; }
        .section-header { font-size: 1rem; padding: 0.5rem 0 0.5rem 0.75rem; }
        .form-card { padding: 1rem; }
        .app-footer { padding: 1rem; }
    }
    @media (max-width: 480px) {
        .main-header h1 { font-size: 1.3rem; }
        .stTabs [data-baseweb="tab"] { padding: 0.4rem 0.5rem; font-size: 0.75rem; }
    }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Session State Initialization
# ---------------------------------------------------------------------------
if 'weboc_scraper' not in st.session_state:
    st.session_state.weboc_scraper = WEBOCTariffScraper()
if 'last_search_result' not in st.session_state:
    st.session_state.last_search_result = None
if 'hs_code_options' not in st.session_state:
    st.session_state.hs_code_options = []
if 'selected_hs_info' not in st.session_state:
    st.session_state.selected_hs_info = None
if 'export_prefill_active' not in st.session_state:
    st.session_state.export_prefill_active = False
if 'comparator_prefill_active' not in st.session_state:
    st.session_state.comparator_prefill_active = False
if 'import_origin_country' not in st.session_state:
    st.session_state.import_origin_country = "None (MFN Rate)"
if 'import_use_preferential' not in st.session_state:
    st.session_state.import_use_preferential = False

# Phase module session state
if MODULE_STATUS.get("history_manager") and 'history_mgr' not in st.session_state:
    st.session_state.history_mgr = HistoryManager(capacity=100)
if MODULE_STATUS.get("favorites_manager") and 'favorites_mgr' not in st.session_state:
    st.session_state.favorites_mgr = FavoritesManager()
if MODULE_STATUS.get("exchange_rate_cache") and 'exchange_cache' not in st.session_state:
    st.session_state.exchange_cache = ExchangeRateCache()
if MODULE_STATUS.get("weboc_cache") and 'weboc_cache' not in st.session_state:
    st.session_state.weboc_cache = WEBOCCache()
if MODULE_STATUS.get("query_cache") and 'query_cache' not in st.session_state:
    st.session_state.query_cache = QueryCache()
if MODULE_STATUS.get("multi_currency") and 'currency_mgr' not in st.session_state:
    st.session_state.currency_mgr = MultiCurrencyManager()
if MODULE_STATUS.get("performance_monitor") and 'perf_monitor' not in st.session_state:
    st.session_state.perf_monitor = get_monitor()

# Phase 7 session state
if MODULE_STATUS.get("tipp_scraper") and 'tipp_cache' not in st.session_state:
    st.session_state.tipp_cache = TIPPCache()
if MODULE_STATUS.get("sbp_rates") and 'sbp_fetcher' not in st.session_state:
    st.session_state.sbp_fetcher = SBPRateFetcher()
if MODULE_STATUS.get("api_health") and 'health_dashboard' not in st.session_state:
    st.session_state.health_dashboard = APIHealthDashboard()
if MODULE_STATUS.get("source_orchestrator") and 'orchestrator' not in st.session_state:
    # Wire up the orchestrator with all available components
    import fed_rates as _fed_mod, fifth_schedule as _fifth_mod, fta_pta as _fta_mod, sro_database as _sro_mod
    st.session_state.orchestrator = SourceOrchestrator(
        weboc_cache=st.session_state.get("weboc_cache"),
        tipp_cache=st.session_state.get("tipp_cache"),
        tipp_scraper=TIPPScraper() if MODULE_STATUS.get("tipp_scraper") else None,
        exchange_cache=st.session_state.get("exchange_cache"),
        sbp_fetcher=st.session_state.get("sbp_fetcher"),
        offline_manager=get_offline_manager() if MODULE_STATUS.get("offline_manager") else None,
        health_dashboard=st.session_state.get("health_dashboard"),
        fed_rates_module=_fed_mod if MODULE_STATUS.get("fed_rates") else None,
        fifth_schedule_module=_fifth_mod if MODULE_STATUS.get("fifth_schedule") else None,
        fta_pta_module=_fta_mod if MODULE_STATUS.get("fta_pta") else None,
        sro_database_module=_sro_mod if MODULE_STATUS.get("sro_database") else None,
    )

# LLM Search session state
if MODULE_STATUS.get("llm_search") and 'llm_searcher' not in st.session_state:
    st.session_state.llm_searcher = LLMHSSearch(model="gpt-4o-mini")

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown("""
<div class="main-header">
    <h1>Pakistan Customs HS Code & Duty Calculator</h1>
    <p>HS Code Classification, WEBOC Tariff Lookup & Import/Export Duty Calculation</p>
    <span class="header-badge">FY 2024-25 &bull; Pakistan Customs Tariff</span>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    # Card 1: Settings
    st.markdown('<div class="sidebar-card"><h4>Settings</h4>', unsafe_allow_html=True)
    with st.expander("Advanced Settings", expanded=False):
        custom_weboc_url = st.text_input(
            "Custom WEBOC URL",
            placeholder="https://www.weboc.gov.pk/(S(...))/...",
            help="Paste WEBOC URL with session token if needed"
        )
        if custom_weboc_url and st.button("Apply URL", use_container_width=True):
            st.session_state.weboc_scraper = WEBOCTariffScraper(custom_weboc_url)
            st.success("URL updated!")

        st.markdown("**PDF Management**")
        pdf_info = get_pdf_info()
        if pdf_info['exists']:
            st.caption(f"Size: {pdf_info['size_mb']:.2f} MB")
            st.caption(f"Modified: {pdf_info['modified_str']}")
        else:
            st.warning("PDF not found locally")

        if st.button("Check for PDF Updates", use_container_width=True):
            with st.spinner("Checking FBR website..."):
                updated, message = check_pdf_update(PDF_URL, PDF_PATH)
                if updated:
                    st.success(message)
                    if os.path.exists(FAISS_INDEX_PATH):
                        shutil.rmtree(FAISS_INDEX_PATH)
                    st.cache_resource.clear()
                    st.markdown('<div class="warning-box">Please refresh the page to rebuild vectorstore.</div>', unsafe_allow_html=True)
                else:
                    st.info(message)
    st.markdown('</div>', unsafe_allow_html=True)

    # Card 2: System Status
    st.markdown('<div class="sidebar-card"><h4>System Status</h4>', unsafe_allow_html=True)
    if MODULE_STATUS.get("offline_manager"):
        try:
            om = get_offline_manager()
            status_data = om.get_ui_status()
            overall = status_data.get("overall", "unknown")
            if overall == "online":
                st.markdown('<span class="status-badge status-online">All Services Online</span>', unsafe_allow_html=True)
            elif overall == "degraded":
                st.markdown('<span class="status-badge status-degraded">Some Services Degraded</span>', unsafe_allow_html=True)
            else:
                st.markdown('<span class="status-badge status-offline">Services Offline</span>', unsafe_allow_html=True)
        except Exception:
            st.caption("Connectivity: Unknown")

    status_col1, status_col2 = st.columns(2)
    with status_col1:
        if os.path.exists(FAISS_INDEX_PATH):
            st.success("Online")
        else:
            st.error("Offline")
        st.caption("Vectorstore")
    with status_col2:
        if os.path.exists(PDF_PATH):
            st.success("Ready")
        else:
            st.warning("Missing")
        st.caption("PDF File")
    st.markdown('</div>', unsafe_allow_html=True)

    # Card 3: Diagnostics
    st.markdown('<div class="sidebar-card"><h4>Diagnostics</h4>', unsafe_allow_html=True)
    with st.expander("Module Status", expanded=False):
        active = sum(1 for v in MODULE_STATUS.values() if v)
        total = len(MODULE_STATUS)
        st.caption(f"{active}/{total} modules loaded")
        for mod, ok in MODULE_STATUS.items():
            if ok:
                st.caption(f"  {mod}")
            else:
                st.caption(f"  {mod} (unavailable)")

    if MODULE_STATUS.get("performance_monitor") and 'perf_monitor' in st.session_state:
        with st.expander("Performance", expanded=False):
            try:
                summary = st.session_state.perf_monitor.get_summary()
                if summary.get("total_operations", 0) > 0:
                    st.caption(f"Operations: {summary['total_operations']}")
                    st.caption(f"Avg: {summary.get('average_ms', 0):.0f}ms")
                else:
                    st.caption("No operations tracked yet")
            except Exception:
                st.caption("Performance data unavailable")

    if MODULE_STATUS.get("health_check"):
        with st.expander("Health Check", expanded=False):
            if st.button("Run Health Check", use_container_width=True):
                try:
                    report = run_health_check()
                    st.caption(f"Status: {report.overall_status}")
                    for check in report.checks:
                        st.caption(f"  {check.name}: {check.status}")
                except Exception as e:
                    st.error(f"Health check failed: {e}")
    st.markdown('</div>', unsafe_allow_html=True)

    # Card 4: Info & Resources
    st.markdown('<div class="sidebar-card"><h4>Tariff Information</h4>', unsafe_allow_html=True)
    st.caption("Pakistan Customs Tariff FY 2024-25")

    if st.session_state.last_search_result:
        st.markdown("**Recent Search:**")
        result = st.session_state.last_search_result
        st.code(f"{result.get('hs_code', 'N/A')}", language="")

    st.markdown("**Resources:**")
    st.markdown("""
- [FBR Official](https://fbr.gov.pk)
- [WEBOC Portal](https://weboc.gov.pk)
- [NBP Exchange Rates](https://nbp.com.pk)
    """)
    st.markdown('</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Initialize vectorstore and QA chain
# ---------------------------------------------------------------------------
if 'vectorstore' not in st.session_state:
    with st.spinner("Initializing AI system..."):
        vectorstore = get_vectorstore()
        if vectorstore:
            qa_chain = setup_qa_chain(vectorstore)
            if qa_chain:
                st.session_state.vectorstore = vectorstore
                st.session_state.qa_chain = qa_chain

# ---------------------------------------------------------------------------
# TABS
# ---------------------------------------------------------------------------
tab_labels = ["HS Code Lookup", "Import Calculator", "Export Calculator"]
if MODULE_STATUS.get("batch_processor"):
    tab_labels.append("Batch Processor")
if MODULE_STATUS.get("duty_comparator"):
    tab_labels.append("Duty Comparator")
if MODULE_STATUS.get("history_manager") or MODULE_STATUS.get("favorites_manager"):
    tab_labels.append("Favorites & History")
if MODULE_STATUS.get("api_health") or MODULE_STATUS.get("source_orchestrator"):
    tab_labels.append("System Status")

tabs = st.tabs(tab_labels)
tab_idx = 0

# ===== TAB 1: HS Code Lookup =====
with tabs[tab_idx]:
    tab_idx += 1
    st.markdown('<div class="section-header">HS Code Lookup & Classification</div>', unsafe_allow_html=True)
    st.caption("Search and classify items using Pakistan Customs Tariff FY 2024-25")

    col1, col2 = st.columns([4, 1])
    with col1:
        hs_input = st.text_input(
            "Search HS Code or Item Description",
            placeholder="Enter HS code (e.g., 0808.1000) or item name (e.g., 'fresh apples')",
            key="hs_lookup"
        )
    with col2:
        st.write("")
        search_btn = st.button("Search", use_container_width=True, type="primary", key="search_hs")

    # Search mode toggle
    if MODULE_STATUS.get("llm_search"):
        search_mode = st.radio(
            "Search Mode",
            ["Smart Search (EN / Urdu / Roman Urdu)", "Document Search (RAG)"],
            horizontal=True,
            help="Smart Search uses AI to understand natural language in any language. Document Search queries the PCT PDF directly.",
            key="search_mode_radio",
        )
    else:
        search_mode = "Document Search (RAG)"

    st.markdown("**Quick Examples:**")
    ex_cols = st.columns(4)
    examples = [
        ("Fresh Apples", "0808.10"), ("Live Horses", "0101.21"),
        ("Cotton T-shirts", "6109.10"), ("Mobile Phones", "8517.12")
    ]
    for idx, (label, code) in enumerate(examples):
        with ex_cols[idx]:
            if st.button(label, use_container_width=True, key=f"ex_{idx}"):
                hs_input = code
                search_btn = True

    if search_btn and hs_input:
        # ---- Smart Search (LLM) path ----
        if "Smart Search" in search_mode and MODULE_STATUS.get("llm_search") and 'llm_searcher' in st.session_state:
            with st.spinner("Analyzing query..."):
                tariff_data = _build_tariff_data_for_search()
                llm_result = st.session_state.llm_searcher.search(hs_input, tariff_data)

            llm = llm_result.get('llm_result')
            if llm:
                st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
                # What LLM understood
                st.caption(
                    f"Understood: **{llm.get('understood_query', '')}** "
                    f"| Language: {llm.get('language_detected', 'en')}"
                )

                # Ignored terms
                ignored = llm.get('ignored_terms', [])
                if ignored:
                    reason = llm.get('ignored_reason', 'Not classified in HS system')
                    st.info(f"Terms not used in HS classification: **{', '.join(ignored)}** — {reason}")

                # Disambiguation
                disambig = llm.get('disambiguation')
                if disambig:
                    st.warning(disambig)

                # Likely codes from LLM
                likely = llm.get('likely_codes', [])
                if likely:
                    for i, suggestion in enumerate(likely):
                        code = suggestion.get('code', '')
                        desc = suggestion.get('description', '')
                        conf = suggestion.get('confidence', '')
                        reason = suggestion.get('reasoning', '')

                        badge_map = {'high': '#4CAF50', 'medium': '#FF9800', 'low': '#F44336'}
                        badge_color = badge_map.get(conf, '#999')
                        conf_label = conf.title() if conf else 'Unknown'

                        # Get hierarchy breadcrumb
                        hierarchy = get_classification_path(code) if MODULE_STATUS.get("llm_search") else {}
                        heading_ctx = get_heading_description(code) if MODULE_STATUS.get("llm_search") else ''
                        is_part = is_part_not_product(desc) if MODULE_STATUS.get("llm_search") else False

                        with st.expander(
                            f"{'[HIGH]' if conf == 'high' else '[MED]' if conf == 'medium' else '[LOW]'} {code} — {desc[:80]}",
                            expanded=(i == 0),
                        ):
                            # Hierarchy breadcrumb
                            if hierarchy:
                                st.caption(
                                    f"Section {hierarchy.get('section', '')} > "
                                    f"Chapter {hierarchy.get('chapter', '')} "
                                    f"({hierarchy.get('chapter_desc', '')}) > "
                                    f"{hierarchy.get('heading', '')} > {code}"
                                )

                            if heading_ctx:
                                st.markdown(f"**Heading:** {heading_ctx}")

                            st.markdown(f"**Description:** {desc}")
                            st.markdown(
                                f'**Confidence:** <span style="background:{badge_color};color:white;'
                                f'padding:2px 8px;border-radius:4px;font-size:13px">{conf_label}</span>',
                                unsafe_allow_html=True,
                            )
                            st.markdown(f"**Reasoning:** {reason}")

                            if is_part:
                                st.warning("This is a PART/ACCESSORY, not a complete product")

                            bcol1, bcol2 = st.columns(2)
                            with bcol1:
                                if st.button("Use in Calculator", key=f"calc_{code}_{i}"):
                                    all_source_data = _fetch_hs_data_all_sources(code)
                                    st.session_state.last_search_result = all_source_data
                                    st.session_state.prefill_data = all_source_data
                                    st.rerun()
                            with bcol2:
                                if st.button("Lookup Full Rates", key=f"weboc_{code}_{i}"):
                                    all_source_data = _fetch_hs_data_all_sources(code)
                                    st.session_state.last_search_result = all_source_data
                                    st.rerun()

                # Data matches from tariff cache
                data_matches = llm_result.get('matches', [])
                if data_matches:
                    st.markdown(f"**Validated Data Matches ({len(data_matches)}):**")
                    for m in data_matches[:10]:
                        with st.expander(f"{m['hs_code']} — {m.get('description', '')[:80]}"):
                            st.write(f"**Code:** {m['hs_code']}")
                            st.write(f"**Description:** {m.get('description', '')}")
                            if m.get('llm_reasoning'):
                                st.caption(f"Match reason: {m['llm_reasoning']}")
                            if st.button("Use This Code", key=f"dm_{m['hs_code']}"):
                                all_source_data = _fetch_hs_data_all_sources(m['hs_code'])
                                st.session_state.last_search_result = all_source_data
                                st.rerun()
            else:
                st.error("Smart search could not process query. Falling back to Document Search...")
                search_mode = "Document Search (RAG)"

        # ---- Document Search (RAG) path ----
        if "Document Search" in search_mode:
            if 'qa_chain' not in st.session_state:
                st.error("System not initialized. Please refresh the page.")
            else:
                cat_info = _detect_broad_category(hs_input)

                # --- Broad category path (chapter / heading / subheading) ---
                if cat_info['is_broad']:
                    level_label = cat_info['level'].title()
                    chapter_name = cat_info['chapter_name']
                    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
                    st.markdown(
                        f'<div class="info-box"><b>{level_label} {cat_info["code"]}</b>'
                        f' &mdash; {chapter_name}<br>'
                        f'This is a broad {cat_info["level"]}. Select a specific 8-digit code below.</div>',
                        unsafe_allow_html=True,
                    )

                    with st.spinner(f"Loading sub-codes under {cat_info['code']}..."):
                        subcodes = _get_subcodes(cat_info['code'])

                    if subcodes:
                        st.success(f"Found {len(subcodes)} sub-codes under {cat_info['code']}")
                        hdr = st.columns([2, 5, 1, 1])
                        with hdr[0]:
                            st.markdown("**HS Code**")
                        with hdr[1]:
                            st.markdown("**Description**")
                        with hdr[2]:
                            st.markdown("**CD %**")
                        with hdr[3]:
                            st.markdown("")
                        for sc in subcodes:
                            cd_display = f"{sc['customs_duty']}%" if sc['customs_duty'] is not None else "—"
                            desc_short = (sc['description'][:60] + "...") if len(sc.get('description', '') or '') > 60 else (sc.get('description') or '')
                            cols = st.columns([2, 5, 1, 1])
                            with cols[0]:
                                st.text(sc['code'])
                            with cols[1]:
                                st.text(desc_short or "—")
                            with cols[2]:
                                st.text(cd_display)
                            with cols[3]:
                                if st.button("Select", key=f"sub_{sc['code']}"):
                                    all_source_data = _fetch_hs_data_all_sources(sc['code'])
                                    st.session_state.last_search_result = all_source_data
                                    st.rerun()
                    else:
                        st.warning("No sub-codes found in cache. Try entering more digits or a description.")

                # --- Specific code or text search path ---
                else:
                    with st.spinner("Searching Pakistan Customs Tariff..."):
                        is_numeric = re.match(r'^\d{2,4}\.?\d{0,4}$', hs_input.replace('.', ''))
                        if is_numeric:
                            normalized = normalize_hs_code(hs_input)
                            query = f"What is the classification, description, and Customs Duty for HS code {normalized}?"
                        else:
                            query = f"Classify '{hs_input}' to HS code with description and Customs Duty"

                        result = _invoke_qa_chain(query)

                        if is_numeric:
                            all_source_data = _fetch_hs_data_all_sources(hs_input)
                            st.session_state.last_search_result = all_source_data

                        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
                        if result:
                            _hs_m = re.search(r'(?:HS|PCT|Code)[:\s]*(\d{4}[.\s]?\d{4})', result, re.IGNORECASE)
                            _desc_m = re.search(r'Description[:\s]*(.+?)(?:Customs|CD|Sales|$)', result, re.IGNORECASE | re.DOTALL)
                            _cd_m = re.search(r'(?:Customs\s*Duty|CD)[:\s()]*(\d+(?:\.\d+)?)\s*%', result, re.IGNORECASE)
                            _st_m = re.search(r'(?:Sales\s*Tax|ST)[:\s()]*(\d+(?:\.\d+)?)\s*%', result, re.IGNORECASE)
                            _it_m = re.search(r'(?:Income\s*Tax|IT|Advance\s*Tax)[:\s()]*(\d+(?:\.\d+)?)\s*%', result, re.IGNORECASE)

                            if _hs_m:
                                _hs_code = _hs_m.group(1).replace(' ', '.')
                                _desc = _desc_m.group(1).strip().rstrip('- ').strip() if _desc_m else ""
                                _cd = f"{_cd_m.group(1)}%" if _cd_m else "—"
                                _st = f"{_st_m.group(1)}%" if _st_m else "18%"
                                _it = f"{_it_m.group(1)}%" if _it_m else "6%"
                                st.markdown(f'''
                                <div style="background:#E8F5E9;border-left:4px solid #1B5E20;padding:16px;border-radius:8px;margin-bottom:12px">
                                    <div style="font-size:13px;color:#666;margin-bottom:4px">Best Match</div>
                                    <div style="font-size:22px;font-weight:bold;color:#1B5E20;margin-bottom:6px">{_hs_code}</div>
                                    <div style="font-size:15px;color:#333;margin-bottom:10px">{_desc}</div>
                                    <div style="display:flex;gap:24px">
                                        <span style="background:#1B5E20;color:white;padding:4px 12px;border-radius:4px">CD: {_cd}</span>
                                        <span style="background:#2E7D32;color:white;padding:4px 12px;border-radius:4px">ST: {_st}</span>
                                        <span style="background:#388E3C;color:white;padding:4px 12px;border-radius:4px">IT: {_it}</span>
                                    </div>
                                </div>''', unsafe_allow_html=True)
                            else:
                                st.markdown(f'<div class="success-box">{result}</div>', unsafe_allow_html=True)
                        else:
                            st.warning("No results found")

                        # Text search: show matching codes grouped by chapter
                        if not is_numeric:
                            all_text_matches = []
                            seen_codes = set()

                            # 1. PRIMARY: Search vectorstore/PCT descriptions directly
                            try:
                                vs = st.session_state.get('vectorstore')
                                if vs:
                                    docs = vs.similarity_search(hs_input, k=20)
                                    code_pattern = re.compile(r'\b(\d{4}\.\d{4})\b')
                                    for doc in docs:
                                        text = doc.page_content
                                        codes_in_doc = code_pattern.findall(text)
                                        for code in codes_in_doc:
                                            if code not in seen_codes:
                                                seen_codes.add(code)
                                                idx = text.find(code)
                                                nearby = text[idx:idx+200] if idx >= 0 else ""
                                                desc_m = re.search(
                                                    r'\d{4}\.\d{4}\s*[\|:\-–]?\s*(.+?)(?:\n|\d{4}\.\d{4}|$)',
                                                    nearby
                                                )
                                                desc = desc_m.group(1).strip()[:80] if desc_m else ""
                                                desc = re.sub(r'^[\-–\s]+', '', desc)
                                                cd_trail = re.search(r'\s+(\d{1,3})$', desc)
                                                cd_val = None
                                                if cd_trail:
                                                    cd_val = float(cd_trail.group(1))
                                                    desc = desc[:cd_trail.start()].strip()
                                                all_text_matches.append({
                                                    'code': code, 'description': desc,
                                                    'unit': _detect_unit(desc), 'customs_duty': cd_val
                                                })
                            except Exception:
                                pass

                            # 2. WEBOC description search (if cache loaded)
                            try:
                                weboc_matches = st.session_state.weboc_scraper.search_hs_codes_autocomplete(hs_input, limit=50)
                                for m in weboc_matches:
                                    if m['code'] not in seen_codes:
                                        seen_codes.add(m['code'])
                                        all_text_matches.append({
                                            'code': m['code'], 'description': m.get('description', ''),
                                            'unit': m.get('unit', 'units'), 'customs_duty': None
                                        })
                            except Exception:
                                pass

                            # 3. FALLBACK: Keyword chapter mapping + sub-codes
                            if len(all_text_matches) < 5:
                                kw_chapters = _get_chapters_for_keyword(hs_input)
                                if kw_chapters:
                                    ch_labels = ", ".join(
                                        f"Chapter {ch} ({HS_CHAPTERS.get(ch, '')})" for ch in kw_chapters
                                    )
                                    st.markdown(
                                        f'<div class="info-box"><b>Related Chapters:</b> {ch_labels}</div>',
                                        unsafe_allow_html=True,
                                    )
                                    with st.spinner(f"Loading HS codes for '{hs_input}'..."):
                                        for ch in kw_chapters:
                                            ch_subcodes = _get_subcodes(ch, limit=50)
                                            for sc in ch_subcodes:
                                                if sc['code'] not in seen_codes:
                                                    seen_codes.add(sc['code'])
                                                    all_text_matches.append(sc)

                            # 4. Score each result by match strength, sort best first
                            if all_text_matches:
                                for m in all_text_matches:
                                    m['_score'] = _match_strength(hs_input, m.get('description', ''))
                                all_text_matches.sort(key=lambda x: x['_score'], reverse=True)

                                st.markdown(f"**Matching HS Codes for '{hs_input}' ({len(all_text_matches)} codes):**")

                                hdr = st.columns([1, 2, 5, 1, 1])
                                with hdr[0]:
                                    st.markdown("**Match**")
                                with hdr[1]:
                                    st.markdown("**HS Code**")
                                with hdr[2]:
                                    st.markdown("**Description**")
                                with hdr[3]:
                                    st.markdown("**CD %**")
                                with hdr[4]:
                                    st.markdown("")

                                for item in all_text_matches:
                                    score = item.get('_score', 0)
                                    color = _strength_color(score)
                                    cd_display = f"{item['customs_duty']}%" if item.get('customs_duty') is not None else "—"
                                    desc_text = (item.get('description') or '—')[:70]
                                    ic = st.columns([1, 2, 5, 1, 1])
                                    with ic[0]:
                                        st.markdown(
                                            f'<span style="color:{color};font-weight:bold">{score}%</span>',
                                            unsafe_allow_html=True,
                                        )
                                    with ic[1]:
                                        st.text(item['code'])
                                    with ic[2]:
                                        st.text(desc_text)
                                    with ic[3]:
                                        st.text(cd_display)
                                    with ic[4]:
                                        if st.button("Use", key=f"txt_{item['code']}"):
                                            fetched = _fetch_hs_data_all_sources(item['code'])
                                            st.session_state.last_search_result = fetched
                                            st.rerun()

        # Favorite star button (works for both search modes)
        if (MODULE_STATUS.get("favorites_manager")
                and st.session_state.last_search_result
                and st.session_state.last_search_result.get('status') == 'success'):
            sr = st.session_state.last_search_result
            if st.button("Add to Favorites", key="fav_from_search"):
                fm = st.session_state.favorites_mgr
                fm.add(
                    hs_code=sr.get('hs_code', hs_input),
                    description=sr.get('description', '') or '',
                    customs_duty_rate=sr.get('customs_duty'),
                    sales_tax_rate=sr.get('sales_tax'),
                    income_tax_rate=sr.get('income_tax'),
                    unit_of_measure=sr.get('unit_of_measure', 'kg'),
                )
                st.success("Added to favorites!")

        if (st.session_state.last_search_result
                and st.session_state.last_search_result.get('status') == 'success'):
            if st.button("Use in Duty Calculator", type="secondary", use_container_width=True):
                st.session_state.prefill_data = st.session_state.last_search_result
                st.info("Data saved! Switch to Import Calculator tab.")


# ===== TAB 2: Import Calculator =====
with tabs[tab_idx]:
    tab_idx += 1
    st.markdown('<div class="section-header">WEBOC Duty Calculator</div>', unsafe_allow_html=True)
    st.caption("Calculate customs duties and taxes based on WEBOC rates")

    if (st.session_state.last_search_result
            and st.session_state.last_search_result.get('status') == 'success'):
        last_result = st.session_state.last_search_result
        description = last_result.get('description') or 'N/A'
        description_display = description[:80] if description != 'N/A' else 'N/A'
        st.markdown('<div class="info-box">', unsafe_allow_html=True)
        st.markdown(f"**Data Available:** {last_result.get('hs_code')} - {description_display}...")
        prefill_cols = st.columns([1, 1, 2])
        with prefill_cols[0]:
            if st.button("Pre-fill Data", use_container_width=True):
                st.session_state.prefill_data = last_result
                st.rerun()
        with prefill_cols[1]:
            if st.button("Clear", use_container_width=True, key="clear_prefill"):
                if 'prefill_data' in st.session_state:
                    del st.session_state.prefill_data
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    prefill = st.session_state.get('prefill_data', {})

    st.markdown('<div class="form-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-header">1. Select HS Code</div>', unsafe_allow_html=True)
    input_method = st.radio(
        "Input Method", ["Manual Entry", "Search Database"],
        horizontal=True, key="hs_input_method", label_visibility="collapsed"
    )

    calc_hs_code = ""
    auto_detected_unit = "kg"
    auto_detected_description = ""

    if input_method == "Manual Entry":
        man_col1, man_col2 = st.columns([3, 1])
        with man_col1:
            calc_hs_code = st.text_input(
                "HS Code", value=prefill.get('hs_code', ''),
                placeholder="e.g., 0808.1000", key="calc_hs_manual"
            )
        with man_col2:
            if calc_hs_code and st.button("Fetch", use_container_width=True, key="fetch_hs"):
                cat_info = _detect_broad_category(calc_hs_code)
                if cat_info['is_broad']:
                    # Broad code → load sub-codes into hs_code_options for selectbox
                    with st.spinner(f"Loading sub-codes under {cat_info['code']}..."):
                        subcodes = _get_subcodes(cat_info['code'])
                    if subcodes:
                        st.session_state.hs_code_options = [
                            {'code': sc['code'], 'description': sc.get('description') or '', 'unit': sc.get('unit', 'units')}
                            for sc in subcodes
                        ]
                        st.session_state._broad_category_msg = (
                            f"'{calc_hs_code}' is a {cat_info['level']}"
                            f" ({cat_info['chapter_name']}). Found {len(subcodes)} sub-codes:"
                        )
                        st.rerun()
                    else:
                        st.warning(f"No sub-codes found under {cat_info['code']}. Try a more specific code.")
                else:
                    # Specific code → single-code fetch (existing behavior)
                    with st.spinner("Fetching tariff data..."):
                        fetched = _fetch_hs_data_all_sources(calc_hs_code)
                        if fetched.get('status') == 'success':
                            if not fetched.get('description'):
                                fetched['description'] = f"HS {calc_hs_code} - Item classification"
                            st.session_state.selected_hs_info = fetched
                            st.session_state.last_search_result = fetched
                            src = fetched.get('source', 'Unknown')
                            st.success(f"Loaded from {src}")
                            st.rerun()
                        else:
                            st.error("Could not find tariff data in any source (WEBOC, TIPP, PCT Database)")
        # Show broad category message if set
        if st.session_state.get('_broad_category_msg'):
            st.info(st.session_state._broad_category_msg)
            st.session_state._broad_category_msg = None
        # Show sub-code picker for broad category results in Manual Entry
        if st.session_state.hs_code_options and input_method == "Manual Entry":
            st.success(f"Found {len(st.session_state.hs_code_options)} sub-codes")
            options_display = [
                f"{item['code']} - {item['description'][:70]}{'...' if len(item.get('description',''))>70 else ''} [{item.get('unit','units')}]"
                for item in st.session_state.hs_code_options
            ]
            selected_sub = st.selectbox(
                "Select Sub-Code", range(len(options_display)),
                format_func=lambda x: options_display[x],
                key="manual_subcode_selector", label_visibility="collapsed"
            )
            if selected_sub is not None:
                sel_item = st.session_state.hs_code_options[selected_sub]
                calc_hs_code = sel_item['code']
                auto_detected_unit = sel_item.get('unit', 'units')
                auto_detected_description = sel_item.get('description', '')
                if st.button("Confirm Selection", use_container_width=True, type="primary", key="confirm_sub_sel"):
                    with st.spinner("Loading tariff data..."):
                        fetched = _fetch_hs_data_all_sources(calc_hs_code)
                        if fetched.get('status') == 'success':
                            if not fetched.get('description'):
                                fetched['description'] = auto_detected_description or "Item classification"
                            st.session_state.selected_hs_info = fetched
                            st.session_state.last_search_result = fetched
                            st.session_state.hs_code_options = []
                            st.success(f"{calc_hs_code} loaded from {fetched.get('source', 'Multiple Sources')}")
                            st.rerun()
                        else:
                            st.warning("Could not fetch live rates. Using defaults.")
                            st.session_state.selected_hs_info = {
                                'hs_code': calc_hs_code, 'status': 'success',
                                'customs_duty': 0, 'sales_tax': 18.0, 'income_tax': 6.0,
                                'additional_duty': 0, 'regulatory_duty': 0,
                                'description': auto_detected_description or "Item classification",
                                'unit_of_measure': auto_detected_unit, 'source': 'Default Rates'
                            }
                            st.session_state.hs_code_options = []
                            st.rerun()
    else:
        search_col1, search_col2 = st.columns([4, 1])
        with search_col1:
            search_query = st.text_input(
                "Search", placeholder="Enter HS code or description",
                key="hs_search_query"
            )
        with search_col2:
            search_btn2 = st.button("Search", use_container_width=True, type="secondary", key="search_db")
        if search_btn2 and search_query:
            with st.spinner("Searching WEBOC..."):
                results = st.session_state.weboc_scraper.search_hs_codes_autocomplete(search_query, limit=100)
                st.session_state.hs_code_options = results
        if st.session_state.hs_code_options:
            st.success(f"Found {len(st.session_state.hs_code_options)} results")
            options_display = [
                f"{item['code']} - {item['description'][:70]}... [{item['unit']}]"
                for item in st.session_state.hs_code_options
            ]
            selected_option = st.selectbox(
                "Select HS Code", range(len(options_display)),
                format_func=lambda x: options_display[x],
                key="hs_code_selector", label_visibility="collapsed"
            )
            if selected_option is not None:
                selected_item = st.session_state.hs_code_options[selected_option]
                calc_hs_code = selected_item['code']
                auto_detected_unit = selected_item['unit']
                auto_detected_description = selected_item['description']
                if st.button("Confirm Selection", use_container_width=True, type="primary", key="confirm_sel"):
                    with st.spinner("Loading tariff data..."):
                        fetched = _fetch_hs_data_all_sources(calc_hs_code)
                        if fetched.get('status') == 'success':
                            # Preserve autocomplete description/unit if fetch didn't return them
                            if not fetched.get('description'):
                                fetched['description'] = auto_detected_description or "Item classification"
                            if fetched.get('unit_of_measure', 'kg') == 'kg' and auto_detected_unit != 'kg':
                                fetched['unit_of_measure'] = auto_detected_unit
                            st.session_state.selected_hs_info = fetched
                            st.session_state.last_search_result = fetched
                            st.success(f"{calc_hs_code} loaded from {fetched.get('source', 'Multiple Sources')}")
                            st.rerun()
                        else:
                            st.warning("Could not fetch live rates. Using standard defaults.")
                            st.session_state.selected_hs_info = {
                                'hs_code': calc_hs_code, 'status': 'success',
                                'customs_duty': 0, 'sales_tax': 18.0, 'income_tax': 6.0,
                                'additional_duty': 0, 'regulatory_duty': 0,
                                'description': auto_detected_description or "Item classification",
                                'unit_of_measure': auto_detected_unit, 'source': 'Default Rates'
                            }
                            st.rerun()
        else:
            st.info("Enter search term to browse HS codes")

    # Selected HS Info Display
    if st.session_state.selected_hs_info and st.session_state.selected_hs_info.get('status') == 'success':
        info = st.session_state.selected_hs_info
        calc_hs_code = info.get('hs_code', calc_hs_code)
        auto_detected_unit = info.get('unit_of_measure', auto_detected_unit)
        auto_detected_description = info.get('description', auto_detected_description)
        data_source = info.get('source', 'WEBOC')
        source_badge = "WEBOC" if 'PCT' not in str(data_source) else "PCT Database"

        st.markdown('<div class="success-box">', unsafe_allow_html=True)
        st.markdown(f"**Selected HS Code:** `{calc_hs_code}` ({source_badge})")
        if auto_detected_description and auto_detected_description != 'N/A':
            st.markdown(f"**Description:** {auto_detected_description}")
        duty_cols = st.columns(4)
        metrics_data = [
            ("CD", info.get('customs_duty', 0)), ("ST", info.get('sales_tax', 0)),
            ("IT", info.get('income_tax', 0)), ("Unit", auto_detected_unit)
        ]
        for idx, (label, value) in enumerate(metrics_data):
            with duty_cols[idx]:
                if label != "Unit":
                    st.metric(label, f"{value}%" if value else "N/A")
                else:
                    st.metric(label, value)
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

    # Country of Origin (FTA/PTA)
    st.markdown('<div class="form-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-header">1b. Country of Origin (Optional)</div>', unsafe_allow_html=True)
    if MODULE_STATUS.get("fta_pta"):
        _fta_countries = ["None (MFN Rate)"] + get_all_countries()
        origin_country = st.selectbox(
            "Country of Origin",
            _fta_countries,
            key="import_origin_country",
            help="Select origin country to check for preferential tariff rates under FTA/PTA agreements"
        )

        if origin_country != "None (MFN Rate)" and calc_hs_code:
            _pref_rate = get_best_fta_rate(calc_hs_code, origin_country)
            _agreements = get_agreements_for_country(origin_country)
            _agreement_name = _agreements[0].name if _agreements else "Unknown"
            _sro_ref = _agreements[0].sro_reference if _agreements else ""

            if _pref_rate:
                st.markdown('<div class="success-box">', unsafe_allow_html=True)
                st.markdown(f"**Preferential Rate Available** under {_agreement_name}")
                pref_cols = st.columns(3)
                with pref_cols[0]:
                    st.metric("MFN Rate (Standard)", f"{_pref_rate.mfn_cd_rate}%")
                with pref_cols[1]:
                    st.metric("Preferential Rate", f"{_pref_rate.preferential_cd_rate}%")
                with pref_cols[2]:
                    st.metric("Savings", f"{_pref_rate.savings_pct} pp",
                              delta=f"-{_pref_rate.savings_pct}%")
                rate_choice = st.radio(
                    "Apply Rate",
                    ["MFN Rate (Standard)", f"Preferential Rate ({_pref_rate.agreement_code})"],
                    horizontal=True, key="import_rate_choice"
                )
                st.session_state.import_use_preferential = "Preferential" in rate_choice
                if st.session_state.import_use_preferential:
                    st.markdown('<div class="warning-box">', unsafe_allow_html=True)
                    st.markdown(
                        f"**Certificate of Origin Required:** To claim the preferential rate under "
                        f"**{_agreement_name}**, a valid Certificate of Origin (COO) from "
                        f"**{origin_country}** must be presented at customs clearance. "
                        f"Ref: {_sro_ref}"
                    )
                    st.markdown('</div>', unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="info-box">', unsafe_allow_html=True)
                st.markdown(
                    f"**{origin_country}** has a trade agreement with Pakistan "
                    f"(**{_agreement_name}**), but no preferential rate is listed for "
                    f"HS code `{calc_hs_code}`. Standard MFN rate will apply."
                )
                st.markdown('</div>', unsafe_allow_html=True)
                st.session_state.import_use_preferential = False
        else:
            st.session_state.import_use_preferential = False
    else:
        st.caption("FTA/PTA module not available — using standard MFN rates")
        st.session_state.import_use_preferential = False
    st.markdown('</div>', unsafe_allow_html=True)

    # Calculation Inputs
    st.markdown('<div class="form-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-header">2. Enter Values</div>', unsafe_allow_html=True)
    val_col1, val_col2 = st.columns(2)
    with val_col1:
        calc_quantity = st.number_input("Quantity", min_value=0.0, step=1.0, value=1.0, key="calc_qty")
        if st.session_state.selected_hs_info:
            default_unit = st.session_state.selected_hs_info.get('unit_of_measure', 'kg')
        elif auto_detected_unit:
            default_unit = auto_detected_unit
        else:
            default_unit = prefill.get('unit_of_measure', 'kg')
        unit_options = ["kg", "units", "liters", "tonnes", "meters", "pairs", "dozens", "sets", "sqm", "cum"]
        if default_unit not in unit_options:
            unit_options.insert(0, default_unit)
        default_index = unit_options.index(default_unit) if default_unit in unit_options else 0
        calc_unit = st.selectbox(f"Unit ({default_unit} detected)", unit_options, index=default_index, key="calc_unit")
    with val_col2:
        calc_currency = st.selectbox("Currency", CURRENCY_LIST[:7], key="calc_curr")
        calc_value = st.number_input(f"Value per {calc_unit}", min_value=0.0, step=0.01, key="calc_val")
        manual_rate = st.number_input(
            "Exchange Rate (optional)", min_value=0.0, step=0.01, value=0.0,
            help="Leave at 0 to auto-fetch NBP TT Selling rate", key="calc_rate"
        )

    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="form-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-header">3. CIF Components</div>', unsafe_allow_html=True)
    cif_cols = st.columns(3)
    with cif_cols[0]:
        freight = st.number_input("Freight", min_value=0.0, step=0.01, value=0.0, key="calc_freight")
    with cif_cols[1]:
        insurance = st.number_input("Insurance", min_value=0.0, step=0.01, value=0.0, key="calc_insurance")
    with cif_cols[2]:
        other_charges = st.number_input("Other Charges", min_value=0.0, step=0.01, value=0.0, key="calc_other")
    st.markdown('</div>', unsafe_allow_html=True)

    if st.button("Calculate Duties & Taxes", type="primary", use_container_width=True, key="calc_import"):
        if not calc_hs_code or calc_quantity <= 0 or calc_value <= 0:
            st.error("Please provide valid HS code, quantity, and value")
        else:
            with st.spinner("Calculating duties and taxes..."):
                if st.session_state.selected_hs_info and st.session_state.selected_hs_info.get('hs_code') == calc_hs_code:
                    duty_data = st.session_state.selected_hs_info
                else:
                    duty_data = _fetch_hs_data_all_sources(calc_hs_code)

                if duty_data.get('status') == 'success':
                    if manual_rate > 0:
                        exchange_rate = manual_rate
                        rate_source = "Custom Rate"
                    else:
                        exchange_rate, rate_source = get_exchange_rate(calc_currency, transaction_type='import')

                    # Resolve preferential rate if selected
                    _pref_cd_rate = None
                    _origin = None
                    if st.session_state.get('import_use_preferential') and MODULE_STATUS.get("fta_pta"):
                        _origin = st.session_state.get('import_origin_country', 'None (MFN Rate)')
                        if _origin != "None (MFN Rate)":
                            _best = get_best_fta_rate(calc_hs_code, _origin)
                            if _best:
                                _pref_cd_rate = _best.preferential_cd_rate

                    calc = _calculate_import_duties(
                        calc_hs_code, calc_quantity, calc_unit, calc_value, calc_currency,
                        exchange_rate, rate_source, duty_data, freight, insurance, other_charges,
                        preferential_cd_rate=_pref_cd_rate, origin_country=_origin
                    )

                    # Display results
                    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
                    st.markdown('<div class="section-header">Calculation Results</div>', unsafe_allow_html=True)
                    result_cols = st.columns(4)
                    with result_cols[0]:
                        st.metric("CIF Value", f"PKR {calc['cif_value_pkr']:,.0f}")
                    with result_cols[1]:
                        st.metric("Total Duties", f"PKR {calc['total_duties']:,.0f}")
                    with result_cols[2]:
                        st.metric("Landed Cost", f"PKR {calc['total_landed_cost']:,.0f}")
                    with result_cols[3]:
                        st.metric("FX Rate", f"{exchange_rate:.2f}")

                    if calc.get('origin_country'):
                        st.markdown(
                            f'<div class="success-box">'
                            f'Using <b>preferential CD rate</b> ({calc["cd_rate"]}%) for imports from '
                            f'<b>{calc["origin_country"]}</b> (MFN rate: {calc.get("mfn_cd_rate", "N/A")}%)'
                            f'</div>',
                            unsafe_allow_html=True
                        )

                    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

                    _cd_label = f"Customs Duty ({calc['cd_rate']}%"
                    if calc.get('origin_country'):
                        _cd_label += " - Preferential)"
                    else:
                        _cd_label += " - MFN)"

                    import pandas as pd
                    breakdown_data = {
                        "Component": [
                            "FOB Value", "Freight", "Insurance", "Other Charges",
                            "CIF Value (Foreign)", "CIF Value (PKR)", "",
                            _cd_label,
                        ],
                        "Amount": [
                            f"{calc['fob_value']:,.2f} {calc_currency}",
                            f"{freight:,.2f} {calc_currency}",
                            f"{insurance:,.2f} {calc_currency}",
                            f"{other_charges:,.2f} {calc_currency}",
                            f"{calc['cif_value_foreign']:,.2f} {calc_currency}",
                            f"{calc['cif_value_pkr']:,.2f} PKR", "",
                            f"{calc['customs_duty']:,.2f} PKR",
                        ]
                    }
                    if calc['ad_rate'] > 0:
                        breakdown_data["Component"].append(f"Additional Duty ({calc['ad_rate']}%)")
                        breakdown_data["Amount"].append(f"{calc['additional_duty']:,.2f} PKR")
                    if calc['rd_rate'] > 0:
                        breakdown_data["Component"].append(f"Regulatory Duty ({calc['rd_rate']}%)")
                        breakdown_data["Amount"].append(f"{calc['regulatory_duty']:,.2f} PKR")
                    if calc.get('fed_rate', 0) > 0:
                        breakdown_data["Component"].append(f"Federal Excise Duty ({calc['fed_rate']}%)")
                        breakdown_data["Amount"].append(f"{calc['federal_excise_duty']:,.2f} PKR")
                    breakdown_data["Component"].extend([
                        f"Sales Tax ({calc['st_rate']}%)", f"Income Tax ({calc['it_rate']}%)",
                        "", "Total Duties & Taxes", "Total Landed Cost"
                    ])
                    breakdown_data["Amount"].extend([
                        f"{calc['sales_tax']:,.2f} PKR", f"{calc['income_tax']:,.2f} PKR",
                        "", f"{calc['total_duties']:,.2f} PKR", f"{calc['total_landed_cost']:,.2f} PKR"
                    ])
                    df = pd.DataFrame(breakdown_data)
                    st.dataframe(df, use_container_width=True, hide_index=True)

                    # Record in history
                    if MODULE_STATUS.get("history_manager") and 'history_mgr' in st.session_state:
                        st.session_state.history_mgr.add_import_calculation(
                            hs_code=calc_hs_code,
                            description=duty_data.get('description', ''),
                            quantity=calc_quantity, unit=calc_unit,
                            unit_value=calc_value, currency=calc_currency,
                            exchange_rate=exchange_rate,
                            cif_pkr=calc['cif_value_pkr'],
                            total_duties=calc['total_duties'],
                            landed_cost=calc['total_landed_cost'],
                        )

                    # Export buttons
                    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
                    export_cols = st.columns(3)
                    desc_text = duty_data.get('description', '') or ''
                    with export_cols[0]:
                        if MODULE_STATUS.get("pdf_exporter"):
                            try:
                                pdf_gen = DutyCalculationPDF()
                                pdf_bytes = pdf_gen.generate_import_report(
                                    hs_code=calc_hs_code, description=desc_text,
                                    quantity=calc_quantity, unit=calc_unit,
                                    unit_value=calc_value, currency=calc_currency,
                                    exchange_rate=exchange_rate, exchange_rate_source=rate_source,
                                    fob_value=calc['fob_value'], freight=freight,
                                    insurance=insurance, other_charges=other_charges,
                                    cif_foreign=calc['cif_value_foreign'], cif_pkr=calc['cif_value_pkr'],
                                    customs_duty_rate=calc['cd_rate'], customs_duty_amount=calc['customs_duty'],
                                    additional_duty_rate=calc['ad_rate'], additional_duty_amount=calc['additional_duty'],
                                    regulatory_duty_rate=calc['rd_rate'], regulatory_duty_amount=calc['regulatory_duty'],
                                    federal_excise_duty_rate=calc.get('fed_rate', 0), federal_excise_duty_amount=calc.get('federal_excise_duty', 0),
                                    sales_tax_rate=calc['st_rate'], sales_tax_amount=calc['sales_tax'],
                                    income_tax_rate=calc['it_rate'], income_tax_amount=calc['income_tax'],
                                    total_duties=calc['total_duties'], landed_cost=calc['total_landed_cost'],
                                    data_source=calc['data_source'],
                                )
                                st.download_button("Download PDF", pdf_bytes, "duty_report.pdf",
                                                   mime="application/pdf", use_container_width=True)
                            except Exception as e:
                                st.caption(f"PDF export error: {e}")
                    with export_cols[1]:
                        if MODULE_STATUS.get("excel_exporter"):
                            try:
                                excel_gen = DutyCalculationExcel()
                                excel_bytes = excel_gen.generate_import_workbook(
                                    hs_code=calc_hs_code, description=desc_text,
                                    quantity=calc_quantity, unit=calc_unit,
                                    unit_value=calc_value, currency=calc_currency,
                                    exchange_rate=exchange_rate, exchange_rate_source=rate_source,
                                    freight=freight, insurance=insurance, other_charges=other_charges,
                                    customs_duty_rate=calc['cd_rate'], additional_duty_rate=calc['ad_rate'],
                                    regulatory_duty_rate=calc['rd_rate'], federal_excise_duty_rate=calc.get('fed_rate', 0),
                                    sales_tax_rate=calc['st_rate'],
                                    income_tax_rate=calc['it_rate'], data_source=calc['data_source'],
                                )
                                st.download_button("Download Excel", excel_bytes, "duty_report.xlsx",
                                                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                                   use_container_width=True)
                            except Exception as e:
                                st.caption(f"Excel export error: {e}")

                    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
                    st.caption(f"Exchange Rate: {rate_source} ({exchange_rate:.4f}) | HS Code: {calc_hs_code} | Data: {calc['data_source']}")
                else:
                    st.error("Could not fetch duty rates. Please verify the HS code.")


# ===== TAB 3: Export Calculator =====
with tabs[tab_idx]:
    tab_idx += 1
    st.markdown('<div class="section-header">Export Proceeds Calculator</div>', unsafe_allow_html=True)
    st.caption("Calculate export proceeds and compliance - FOB basis with TT Buying rate")

    # Auto-prefill from HS Code Lookup
    export_prefill = {}
    if (st.session_state.last_search_result
            and st.session_state.last_search_result.get('status') == 'success'):
        export_prefill = st.session_state.last_search_result
        ep_desc = (export_prefill.get('description') or 'N/A')[:80]
        st.markdown('<div class="success-box">', unsafe_allow_html=True)
        st.markdown(f"**Data Available:** `{export_prefill.get('hs_code', '')}` - {ep_desc}")
        ep_cols = st.columns([1, 1, 2])
        with ep_cols[0]:
            if st.button("Use for Export", use_container_width=True, key="export_prefill_btn"):
                st.session_state.export_prefill_active = True
                st.rerun()
        with ep_cols[1]:
            if st.button("Clear", use_container_width=True, key="export_clear_prefill"):
                st.session_state.export_prefill_active = False
                st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="info-box">', unsafe_allow_html=True)
    st.markdown("""
    **Pakistan Export Rules:**
    - General Rule: No export duty on goods exported from Pakistan
    - Exception: Regulatory duty may apply (check notifications)
    - Proceeds: Calculated using NBP TT Buying rate (bank buys your USD)
    - Drawback: Duty drawback/refund may be available (check eligibility)
    """)
    st.markdown('</div>', unsafe_allow_html=True)
    st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

    # Resolve prefill values
    _ep_active = st.session_state.get('export_prefill_active', False)
    _ep_hs = export_prefill.get('hs_code', '') if _ep_active else ''
    _ep_desc = (export_prefill.get('description') or '') if _ep_active else ''
    _ep_unit = export_prefill.get('unit_of_measure', 'kg') if _ep_active else 'kg'
    _unit_options = ["kg", "units", "liters", "tonnes", "meters", "pairs", "dozens", "sets"]
    if _ep_unit and _ep_unit not in _unit_options:
        _unit_options.insert(0, _ep_unit)
    _ep_unit_idx = _unit_options.index(_ep_unit) if _ep_unit in _unit_options else 0

    st.markdown('<div class="form-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-header">1. Export Item Details</div>', unsafe_allow_html=True)
    exp_col1, exp_col2 = st.columns(2)
    with exp_col1:
        exp_hs_col, exp_fetch_col = st.columns([3, 1])
        with exp_hs_col:
            export_hs_code = st.text_input("HS Code", value=_ep_hs, placeholder="e.g., 0808.1000", key="export_hs_code")
        with exp_fetch_col:
            st.write("")
            if export_hs_code and not _ep_active and st.button("Fetch", use_container_width=True, key="export_fetch_hs"):
                with st.spinner("Fetching..."):
                    exp_fetched = _fetch_hs_data_all_sources(export_hs_code)
                    if exp_fetched.get('status') == 'success':
                        st.session_state.last_search_result = exp_fetched
                        st.session_state.export_prefill_active = True
                        st.rerun()
                    else:
                        st.error("Not found")
        export_description = st.text_input("Item Description", value=_ep_desc, placeholder="e.g., Fresh Apples", key="export_description")
        export_quantity = st.number_input("Quantity", min_value=0.0, step=1.0, value=1.0, key="export_qty")
    with exp_col2:
        export_unit = st.selectbox("Unit of Measurement", _unit_options, index=_ep_unit_idx,
                                   key="export_unit")
        export_destination = st.selectbox("Destination Country",
                                          ["UAE", "USA", "UK", "China", "Saudi Arabia", "Afghanistan", "Bangladesh",
                                           "India", "Sri Lanka", "Malaysia", "Indonesia", "Iran", "Other"],
                                          key="export_dest")
        # WCO HS classification note
        if export_hs_code and export_destination != "Other":
            _hs_6 = export_hs_code.replace(".", "").replace(" ", "")[:6]
            if len(_hs_6) >= 6:
                _fmt = f"{_hs_6[:4]}.{_hs_6[4:6]}"
                st.caption(
                    f"HS {_fmt}xx applies internationally (WCO). "
                    f"{export_destination} may have different sub-headings beyond 6 digits."
                )
        export_scheme = st.selectbox("Export Scheme",
                                     ["Normal Export", "DTRE (Duty & Tax Remission)", "Manufacturing Bond",
                                      "Export Oriented Unit", "Other"],
                                     key="export_scheme")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="form-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-header">2. FOB Value & Exchange</div>', unsafe_allow_html=True)
    fob_col1, fob_col2, fob_col3 = st.columns(3)
    with fob_col1:
        export_currency = st.selectbox("Currency", CURRENCY_LIST[:6], key="export_curr")
    with fob_col2:
        export_fob_per_unit = st.number_input(f"FOB Value per {export_unit}", min_value=0.0, step=0.01, key="export_fob_unit")
    with fob_col3:
        export_manual_rate = st.number_input("TT Buying Rate (optional)", min_value=0.0, step=0.01,
                                             value=0.0, key="export_manual_rate")
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="form-card">', unsafe_allow_html=True)
    st.markdown('<div class="section-header">3. Regulatory Duty Check</div>', unsafe_allow_html=True)
    rd_col1, rd_col2 = st.columns(2)
    with rd_col1:
        has_regulatory_duty = st.checkbox("Regulatory Duty Applicable?", value=False, key="export_has_rd")
    with rd_col2:
        if has_regulatory_duty:
            regulatory_duty_rate = st.number_input("Regulatory Duty Rate (%)", min_value=0.0, max_value=100.0,
                                                   step=0.1, value=0.0, key="export_rd_rate")
        else:
            regulatory_duty_rate = 0.0
            st.info("No export duty (general rule)")
    st.markdown('</div>', unsafe_allow_html=True)

    if st.button("Calculate Export Proceeds", type="primary", use_container_width=True, key="calc_export"):
        if not export_hs_code or export_quantity <= 0 or export_fob_per_unit <= 0:
            st.error("Please provide valid HS code, quantity, and FOB value")
        else:
            with st.spinner("Calculating export proceeds..."):
                if export_manual_rate > 0:
                    tt_buying_rate = export_manual_rate
                    rate_source = "Custom TT Buying Rate"
                else:
                    tt_buying_rate, rate_source = get_exchange_rate(export_currency, transaction_type='export')

                if MODULE_STATUS.get("calculators"):
                    export_result = ExportCalculator.calculate(
                        hs_code=export_hs_code, quantity=export_quantity,
                        unit_of_measure=export_unit, fob_per_unit=export_fob_per_unit,
                        currency=export_currency, exchange_rate=tt_buying_rate,
                        exchange_rate_source=rate_source,
                        regulatory_duty_rate=regulatory_duty_rate,
                        export_scheme=export_scheme
                    )
                    total_fob_foreign = export_result.total_fob_foreign
                    total_fob_pkr = export_result.total_fob_pkr
                    regulatory_duty_amount = export_result.regulatory_duty_amount
                    net_proceeds_pkr = export_result.net_proceeds_pkr
                    drawback_eligible = export_result.drawback_eligible
                    estimated_drawback = export_result.estimated_drawback
                else:
                    total_fob_foreign = export_fob_per_unit * export_quantity
                    total_fob_pkr = total_fob_foreign * tt_buying_rate
                    regulatory_duty_amount = total_fob_pkr * (regulatory_duty_rate / 100) if has_regulatory_duty else 0
                    net_proceeds_pkr = total_fob_pkr - regulatory_duty_amount
                    drawback_eligible = export_scheme in ["DTRE (Duty & Tax Remission)", "Manufacturing Bond", "Export Oriented Unit"]
                    estimated_drawback = total_fob_pkr * 0.03 if drawback_eligible else 0

                st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
                st.markdown('<div class="section-header">Export Calculation Results</div>', unsafe_allow_html=True)
                export_result_cols = st.columns(4)
                with export_result_cols[0]:
                    st.metric("FOB Value", f"{total_fob_foreign:,.2f} {export_currency}")
                with export_result_cols[1]:
                    st.metric("PKR Proceeds", f"PKR {total_fob_pkr:,.0f}")
                with export_result_cols[2]:
                    st.metric("Regulatory Duty", f"PKR {regulatory_duty_amount:,.0f}")
                with export_result_cols[3]:
                    st.metric("Net Proceeds", f"PKR {net_proceeds_pkr:,.0f}")

                st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
                import pandas as pd
                export_breakdown = {
                    "Component": [
                        "FOB Value per Unit", "Quantity", "Total FOB Value (Foreign)",
                        "TT Buying Rate (NBP)", "**Total FOB Value (PKR)**", "",
                        "Export Duty",
                        f"Regulatory Duty ({regulatory_duty_rate}%)" if has_regulatory_duty else "Regulatory Duty",
                        "", "**Net Export Proceeds**",
                    ],
                    "Amount": [
                        f"{export_fob_per_unit:,.2f} {export_currency}",
                        f"{export_quantity:,.2f} {export_unit}",
                        f"{total_fob_foreign:,.2f} {export_currency}",
                        f"{tt_buying_rate:.4f}",
                        f"**{total_fob_pkr:,.2f} PKR**", "",
                        "0 PKR (No export duty - general rule)",
                        f"{regulatory_duty_amount:,.2f} PKR" if has_regulatory_duty else "0 PKR (Not applicable)",
                        "", f"**{net_proceeds_pkr:,.2f} PKR**",
                    ]
                }
                df_export = pd.DataFrame(export_breakdown)
                st.dataframe(df_export, use_container_width=True, hide_index=True)

                # Record in history
                if MODULE_STATUS.get("history_manager") and 'history_mgr' in st.session_state:
                    st.session_state.history_mgr.add_export_calculation(
                        hs_code=export_hs_code,
                        description=export_description or "Export",
                        quantity=export_quantity, unit=export_unit,
                        unit_value=export_fob_per_unit, currency=export_currency,
                        exchange_rate=tt_buying_rate,
                        fob_pkr=total_fob_pkr, net_proceeds=net_proceeds_pkr,
                    )

                st.caption(f"Exchange Rate: {rate_source} ({tt_buying_rate:.4f}) | HS Code: {export_hs_code}")

                # FTA/PTA note for destination country
                if MODULE_STATUS.get("fta_pta"):
                    _dest_lower_list = [c.lower() for c in get_all_countries()]
                    if export_destination.lower() in _dest_lower_list:
                        _dest_agreements = get_agreements_for_country(export_destination)
                        if _dest_agreements:
                            st.markdown('<div class="info-box">', unsafe_allow_html=True)
                            st.markdown(
                                f"**Trade Agreement Note:** {export_destination} has a trade agreement "
                                f"with Pakistan (**{_dest_agreements[0].name}**). The importer in "
                                f"{export_destination} may benefit from preferential import duties. "
                                f"Ensure you can provide a **Certificate of Origin (COO)** from Pakistan."
                            )
                            st.markdown('</div>', unsafe_allow_html=True)


# ===== TAB 4: Batch Processor (Phase 4) =====
if MODULE_STATUS.get("batch_processor") and tab_idx < len(tabs):
    with tabs[tab_idx]:
        tab_idx += 1
        st.markdown('<div class="section-header">Batch Import Duty Calculator</div>', unsafe_allow_html=True)
        st.caption("Upload a CSV file to calculate duties for multiple items at once")

        batch_cols = st.columns([3, 1])
        with batch_cols[0]:
            uploaded_file = st.file_uploader("Upload CSV", type=["csv"], key="batch_csv")
        with batch_cols[1]:
            st.markdown("<br>", unsafe_allow_html=True)
            sample_csv = generate_sample_csv()
            st.download_button("Download Sample CSV", sample_csv, "sample_batch.csv",
                               mime="text/csv", use_container_width=True)

        batch_rate_cols = st.columns(2)
        with batch_rate_cols[0]:
            batch_currency = st.selectbox("Default Currency", CURRENCY_LIST[:7], key="batch_curr")
        with batch_rate_cols[1]:
            batch_manual_rate = st.number_input("Exchange Rate", min_value=0.0, value=0.0,
                                                  help="Leave at 0 to auto-fetch NBP rate", key="batch_rate")

        if uploaded_file and st.button("Process Batch", type="primary", use_container_width=True, key="process_batch"):
            with st.spinner("Processing batch..."):
                csv_content = uploaded_file.getvalue().decode('utf-8')
                if batch_manual_rate > 0:
                    rate = batch_manual_rate
                    rate_src = "Custom Rate"
                else:
                    rate, rate_src = get_exchange_rate(batch_currency, transaction_type='import')

                batch_result = process_batch(csv_content, rate, rate_src)

                st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
                st.markdown('<div class="section-header">Batch Results</div>', unsafe_allow_html=True)
                result_cols = st.columns(4)
                with result_cols[0]:
                    st.metric("Total Rows", batch_result.total_rows)
                with result_cols[1]:
                    st.metric("Succeeded", batch_result.succeeded)
                with result_cols[2]:
                    st.metric("Failed", batch_result.failed)
                with result_cols[3]:
                    st.metric("Success Rate", f"{batch_result.success_rate}%")

                if batch_result.succeeded > 0:
                    st.metric("Total Landed Cost", f"PKR {batch_result.total_landed_cost_all:,.0f}")

                    import pandas as pd
                    rows_data = []
                    for row in batch_result.rows:
                        rows_data.append({
                            "Row": row.row_number,
                            "Status": row.status.value,
                            "HS Code": row.hs_code,
                            "Description": row.description[:30],
                            "CIF PKR": f"{row.cif_value_pkr:,.0f}" if row.cif_value_pkr else "",
                            "Total Duties": f"{row.total_duties:,.0f}" if row.total_duties else "",
                            "Landed Cost": f"{row.total_landed_cost:,.0f}" if row.total_landed_cost else "",
                            "Error": row.error_message or "",
                        })
                    df_batch = pd.DataFrame(rows_data)
                    st.dataframe(df_batch, use_container_width=True, hide_index=True)

                    csv_export = export_batch_csv(batch_result)
                    st.download_button("Export Results CSV", csv_export, "batch_results.csv",
                                       mime="text/csv", use_container_width=True)

                if batch_result.failed > 0:
                    with st.expander("View Errors"):
                        for err in batch_result.get_errors():
                            st.caption(f"Row {err['row']}: {err['error']}")

# ===== TAB 5: Duty Comparator (Phase 4) =====
if MODULE_STATUS.get("duty_comparator") and tab_idx < len(tabs):
    with tabs[tab_idx]:
        tab_idx += 1
        st.markdown('<div class="section-header">Duty Comparison Tool</div>', unsafe_allow_html=True)
        st.caption("Compare import duties across multiple HS codes side-by-side (max 5)")

        # Auto-prefill from HS Code Lookup
        comp_prefill = {}
        if (st.session_state.last_search_result
                and st.session_state.last_search_result.get('status') == 'success'):
            comp_prefill = st.session_state.last_search_result
            cp_desc = (comp_prefill.get('description') or 'N/A')[:80]
            st.markdown('<div class="success-box">', unsafe_allow_html=True)
            st.markdown(f"**Data Available:** `{comp_prefill.get('hs_code', '')}` - {cp_desc}")
            cp_cols = st.columns([1, 1, 2])
            with cp_cols[0]:
                if st.button("Use for Slot 1", use_container_width=True, key="comp_prefill_btn"):
                    st.session_state.comparator_prefill_active = True
                    st.rerun()
            with cp_cols[1]:
                if st.button("Clear", use_container_width=True, key="comp_clear_prefill"):
                    st.session_state.comparator_prefill_active = False
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)

        _cp_active = st.session_state.get('comparator_prefill_active', False)
        _cp_hs = comp_prefill.get('hs_code', '') if _cp_active else ''
        _cp_desc = (comp_prefill.get('description') or '') if _cp_active else ''
        _cp_cd = float(comp_prefill.get('customs_duty', 0.0)) if _cp_active else 0.0
        _cp_st = float(comp_prefill.get('sales_tax', 18.0)) if _cp_active else 18.0

        num_codes = st.slider("Number of HS codes to compare", 2, 5, 2, key="num_compare")

        hs_codes_input = []
        comp_cols = st.columns(num_codes)
        for i in range(num_codes):
            with comp_cols[i]:
                if i == 0 and _cp_active:
                    code = st.text_input(f"HS Code {i+1}", value=_cp_hs, key=f"comp_hs_{i}", placeholder="XXXX.XXXX")
                    desc = st.text_input(f"Description {i+1}", value=_cp_desc, key=f"comp_desc_{i}", placeholder="Item name")
                    cd = st.number_input(f"CD% #{i+1}", min_value=0.0, max_value=100.0, value=_cp_cd, key=f"comp_cd_{i}")
                    st_val = st.number_input(f"ST% #{i+1}", min_value=0.0, max_value=100.0, value=_cp_st, key=f"comp_st_{i}")
                else:
                    code = st.text_input(f"HS Code {i+1}", key=f"comp_hs_{i}", placeholder="XXXX.XXXX")
                    desc = st.text_input(f"Description {i+1}", key=f"comp_desc_{i}", placeholder="Item name")
                    cd = st.number_input(f"CD% #{i+1}", min_value=0.0, max_value=100.0, value=0.0, key=f"comp_cd_{i}")
                    st_val = st.number_input(f"ST% #{i+1}", min_value=0.0, max_value=100.0, value=18.0, key=f"comp_st_{i}")
                it_val = st.number_input(f"IT% #{i+1}", min_value=0.0, max_value=100.0, value=5.5, key=f"comp_it_{i}")
                hs_codes_input.append({"code": code, "desc": desc, "cd": cd, "st": st_val, "it": it_val})

        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
        st.markdown("**Shared Values:**")
        shared_cols = st.columns(4)
        with shared_cols[0]:
            comp_qty = st.number_input("Quantity", min_value=0.1, value=100.0, key="comp_qty")
        with shared_cols[1]:
            comp_unit_val = st.number_input("Unit Value", min_value=0.01, value=10.0, key="comp_unit_val")
        with shared_cols[2]:
            comp_curr = st.selectbox("Currency", CURRENCY_LIST[:7], key="comp_curr")
        with shared_cols[3]:
            comp_rate = st.number_input("Exchange Rate", min_value=0.0, value=0.0,
                                          help="Leave at 0 to auto-fetch NBP rate", key="comp_rate")

        # Auto-fetch rates for all entered HS codes
        fetch_cols = st.columns([1, 1])
        with fetch_cols[0]:
            if st.button("Fetch Rates for All", use_container_width=True, key="comp_fetch_all"):
                codes_to_fetch = [h["code"].strip() for h in hs_codes_input if h["code"].strip()]
                if not codes_to_fetch:
                    st.warning("Enter at least one HS code first")
                else:
                    with st.spinner(f"Fetching rates for {len(codes_to_fetch)} codes..."):
                        for idx, code in enumerate(codes_to_fetch):
                            fetched = _fetch_hs_data_all_sources(code)
                            if fetched.get('status') == 'success':
                                st.session_state[f"comp_cd_{idx}"] = float(fetched.get('customs_duty', 0))
                                st.session_state[f"comp_st_{idx}"] = float(fetched.get('sales_tax', 18.0))
                                st.session_state[f"comp_it_{idx}"] = float(fetched.get('income_tax', 6.0))
                                if fetched.get('description'):
                                    st.session_state[f"comp_desc_{idx}"] = fetched['description'][:70]
                        st.success("Rates fetched! Values updated.")
                        st.rerun()
        with fetch_cols[1]:
            pass

        if st.button("Compare Duties", type="primary", use_container_width=True, key="run_compare"):
            valid_codes = [h for h in hs_codes_input if h["code"].strip()]
            if len(valid_codes) < 2:
                st.error("Please enter at least 2 HS codes")
            else:
                if comp_rate > 0:
                    rate = comp_rate
                    rate_src = "Custom Rate"
                else:
                    rate, rate_src = get_exchange_rate(comp_curr, transaction_type='import')

                profiles = [
                    DutyProfile(
                        hs_code=h["code"], description=h["desc"] or h["code"],
                        customs_duty_rate=h["cd"], sales_tax_rate=h["st"],
                        income_tax_rate=h["it"]
                    )
                    for h in valid_codes
                ]
                comparison = DutyComparator.compare(
                    duty_profiles=profiles, quantity=comp_qty, unit="units",
                    unit_value=comp_unit_val, currency=comp_curr,
                    exchange_rate=rate, exchange_rate_source=rate_src
                )

                st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
                st.markdown('<div class="section-header">Comparison Results</div>', unsafe_allow_html=True)

                if comparison.cheapest_code:
                    st.success(f"Cheapest: {comparison.cheapest_code} | Savings: PKR {comparison.max_savings:,.0f}")

                import pandas as pd
                comp_data = []
                for item in comparison.items:
                    comp_data.append({
                        "Rank": item.rank,
                        "HS Code": item.hs_code,
                        "Description": item.description[:30],
                        "CD%": item.customs_duty_rate,
                        "Total Duties": f"PKR {item.total_duties:,.0f}",
                        "Landed Cost": f"PKR {item.total_landed_cost:,.0f}",
                        "Effective Rate": f"{item.effective_duty_rate:.1f}%",
                        "vs Cheapest": f"+PKR {item.difference_from_cheapest:,.0f}" if not item.is_cheapest else "Cheapest",
                    })
                df_comp = pd.DataFrame(comp_data)
                st.dataframe(df_comp, use_container_width=True, hide_index=True)


# ===== TAB 6: Favorites & History =====
if (MODULE_STATUS.get("history_manager") or MODULE_STATUS.get("favorites_manager")) and tab_idx < len(tabs):
    with tabs[tab_idx]:
        tab_idx += 1
        st.markdown('<div class="section-header">Favorites & History</div>', unsafe_allow_html=True)

        fh_view = st.radio("View", ["Favorites", "History"], horizontal=True, key="fh_view")

        if fh_view == "Favorites" and MODULE_STATUS.get("favorites_manager"):
            fm = st.session_state.get("favorites_mgr")
            if fm:
                add_cols = st.columns([2, 2, 1])
                with add_cols[0]:
                    fav_code = st.text_input("HS Code", key="fav_add_code", placeholder="XXXX.XXXX")
                with add_cols[1]:
                    fav_desc = st.text_input("Description", key="fav_add_desc", placeholder="Item name")
                with add_cols[2]:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("Add", use_container_width=True, key="add_fav"):
                        if fav_code:
                            fm.add(hs_code=fav_code, description=fav_desc or fav_code)
                            st.success(f"Added {fav_code}")
                            st.rerun()

                st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
                fav_search = st.text_input("Search favorites", key="fav_search", placeholder="Search by code or description")

                if fav_search:
                    favs = fm.search(fav_search)
                else:
                    favs = fm.get_most_used(limit=50)

                if favs:
                    import pandas as pd
                    fav_data = []
                    for f in favs:
                        fav_data.append({
                            "HS Code": f.hs_code,
                            "Description": f.description[:40],
                            "CD%": f.customs_duty_rate or "N/A",
                            "Uses": f.use_count,
                            "Tags": ", ".join(f.tags) if f.tags else "",
                        })
                    df_fav = pd.DataFrame(fav_data)
                    st.dataframe(df_fav, use_container_width=True, hide_index=True)

                    # Export/Import
                    exp_cols = st.columns(2)
                    with exp_cols[0]:
                        json_export = fm.export_json()
                        st.download_button("Export JSON", json_export, "favorites.json",
                                           mime="application/json", use_container_width=True)
                    with exp_cols[1]:
                        json_file = st.file_uploader("Import JSON", type=["json"], key="fav_import")
                        if json_file:
                            json_content = json_file.getvalue().decode('utf-8')
                            added, skipped = fm.import_json(json_content)
                            st.success(f"Imported {added} favorites ({skipped} skipped)")
                else:
                    st.info("No favorites yet. Add HS codes from the search tab or above.")

        elif fh_view == "History" and MODULE_STATUS.get("history_manager"):
            hm = st.session_state.get("history_mgr")
            if hm and not hm.is_empty:
                hist_filter = st.radio("Filter", ["All", "Import", "Export"], horizontal=True, key="hist_filter")
                if hist_filter == "Import":
                    entries = hm.filter_by_type(CalculationType.IMPORT)
                elif hist_filter == "Export":
                    entries = hm.filter_by_type(CalculationType.EXPORT)
                else:
                    entries = hm.get_all()

                if entries:
                    import pandas as pd
                    hist_data = []
                    for entry in entries:
                        hist_data.append({
                            "Time": entry.timestamp[:19],
                            "Type": entry.calc_type.value.title(),
                            "HS Code": entry.input_summary.hs_code,
                            "Description": entry.input_summary.description[:30],
                            "Currency": entry.input_summary.currency,
                            "Result": entry.get_display_subtitle(),
                        })
                    df_hist = pd.DataFrame(hist_data)
                    st.dataframe(df_hist, use_container_width=True, hide_index=True)

                    csv_data = hm.export_to_csv()
                    st.download_button("Export History CSV", csv_data, "calculation_history.csv",
                                       mime="text/csv", use_container_width=True)

                    stats = hm.get_statistics()
                    st.caption(f"Total: {stats['total']} | Imports: {stats.get('imports', 0)} | Exports: {stats.get('exports', 0)}")
                else:
                    st.info("No matching entries found")
            else:
                st.info("No calculation history yet. Calculations from Import/Export tabs will appear here.")


# ===== TAB: System Status (Phase 7) =====
if MODULE_STATUS.get("api_health") or MODULE_STATUS.get("source_orchestrator"):
    with tabs[tab_idx]:
        tab_idx += 1
        st.markdown('<div class="section-header">System Status & API Health</div>', unsafe_allow_html=True)

        # API Health Dashboard
        if MODULE_STATUS.get("api_health") and "health_dashboard" in st.session_state:
            dashboard = st.session_state.health_dashboard
            st.markdown("#### API Health Dashboard")
            all_health = dashboard.get_all_health(hours=24)

            # Status badges row
            if all_health:
                badge_cols = st.columns(len(all_health))
                for i, (src_name, hlth) in enumerate(all_health.items()):
                    with badge_cols[i]:
                        css_cls = hlth['status'].lower().replace('_', '-')
                        st.markdown(
                            f'<span class="status-badge status-{css_cls}">{src_name}: {hlth["status"].title()}</span>',
                            unsafe_allow_html=True
                        )

            import pandas as pd
            health_rows = []
            for source_name, health in all_health.items():
                health_rows.append({
                    "Source": source_name,
                    "Status": health['status'].title(),
                    "Uptime": f"{health['uptime_pct']:.1f}%",
                    "Avg Response": f"{health['avg_response_ms']:.0f}ms" if health['avg_response_ms'] > 0 else "N/A",
                    "Last Check": health.get("last_check_display", "Never"),
                    "Checks": health["total_checks"],
                })
            if health_rows:
                st.dataframe(pd.DataFrame(health_rows), use_container_width=True, hide_index=True)
            else:
                st.info("No health data recorded yet. Health data is collected as API calls are made.")

        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

        # Source Orchestrator Status
        if MODULE_STATUS.get("source_orchestrator") and "orchestrator" in st.session_state:
            orchestrator = st.session_state.orchestrator
            st.markdown("#### Data Source Status")

            source_status = orchestrator.get_source_status()
            cols = st.columns(4)
            for i, (name, status) in enumerate(source_status.items()):
                with cols[i % 4]:
                    css_cls = status.lower().replace('_', '-')
                    st.markdown(
                        f'<div style="text-align:center; padding:0.5rem 0;">'
                        f'<span class="status-badge status-{css_cls}">{status.replace("_", " ").title()}</span>'
                        f'<p style="margin:0.25rem 0 0; font-weight:600; color:#4A5568; font-size:0.8rem;">{name}</p>'
                        f'</div>',
                        unsafe_allow_html=True
                    )

        st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)

        # Module Status
        st.markdown("#### Module Status")
        phase_groups = {
            "Phase 1 - Security": ["validators", "calculators"],
            "Phase 2 - UX": ["history_manager", "pdf_exporter", "excel_exporter"],
            "Phase 3 - Performance": ["exchange_rate_cache", "weboc_cache", "query_cache", "performance_monitor", "offline_manager"],
            "Phase 4 - Features": ["batch_processor", "duty_comparator", "multi_currency", "favorites_manager"],
            "Phase 5 - Infrastructure": ["app_config", "health_check"],
            "Phase 6 - Compliance": ["fed_rates", "fifth_schedule", "fta_pta", "sro_database"],
            "Phase 7 - Live Data": ["tipp_scraper", "sbp_rates", "source_orchestrator", "api_health", "data_updater"],
        }
        for phase_name, modules in phase_groups.items():
            loaded = sum(1 for m in modules if MODULE_STATUS.get(m))
            total = len(modules)
            st.caption(f"**{phase_name}**: {loaded}/{total} modules loaded")

        # Data Freshness
        if MODULE_STATUS.get("data_updater"):
            st.markdown('<div class="section-divider"></div>', unsafe_allow_html=True)
            st.markdown("#### Data Freshness")
            st.caption("Compares Phase 6 static data against live TIPP data to detect stale rates.")
            if st.button("Run Freshness Check", use_container_width=True, key="freshness_check"):
                with st.spinner("Checking data freshness..."):
                    try:
                        checker = DataFreshnessChecker(
                            tipp_cache=st.session_state.get("tipp_cache"),
                            fed_rates_module=__import__("fed_rates") if MODULE_STATUS.get("fed_rates") else None,
                            fifth_schedule_module=__import__("fifth_schedule") if MODULE_STATUS.get("fifth_schedule") else None,
                            fta_pta_module=__import__("fta_pta") if MODULE_STATUS.get("fta_pta") else None,
                        )
                        summary = checker.get_summary()
                        st.caption(f"Last check: {summary['last_check_display']}")
                        for mod, info in summary.get("modules", {}).items():
                            if info["status"] == "up_to_date":
                                st.caption(f"  {mod}: ✅ Up to date")
                            else:
                                st.caption(f"  {mod}: ⚠️ {info['discrepancies']} discrepancies")
                    except Exception as e:
                        st.error(f"Freshness check error: {e}")

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown("""
<div class="app-footer">
    <p class="footer-title">Pakistan Customs &mdash; HS Code & Import/Export Duty Calculator</p>
    <p>Import: CIF Basis + TT Selling Rate | Export: FOB Basis + TT Buying Rate</p>
    <p>Data Sources: <a href="https://fbr.gov.pk" target="_blank">FBR</a> |
       <a href="https://weboc.gov.pk" target="_blank">WEBOC</a> |
       <a href="https://nbp.com.pk" target="_blank">NBP</a> | SBP | TIPP</p>
    <p class="footer-disclaimer">
        Pakistan Customs Tariff FY 2024-25. For official assessments, verify with FBR/WEBOC.
        This tool provides estimates for reference only.
    </p>
</div>
""", unsafe_allow_html=True)
