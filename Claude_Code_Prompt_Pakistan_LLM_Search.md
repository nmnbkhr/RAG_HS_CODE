## PROJECT
Repository: github.com/nmnbkhr/RAG_HS_CODE (branch: api-key-handling)
Existing app: app_integrated.py (3,188 lines) — Pakistan Customs HS Code Calculator
Running on port 8502 via run.sh
OpenAI API key already loaded in .env, ChatOpenAI already imported and used.

## TASK
Add LLM-POWERED SMART SEARCH to the Pakistan app for natural language,
Urdu, Roman Urdu, and phonetic HS code lookup. Uses the EXISTING OpenAI
API key and ChatOpenAI that the app already has.

## WHY LLM INSTEAD OF STATIC DICTIONARY
The previous approach used a hardcoded synonym dictionary (250+ entries).
Problems with that:
- Can never cover all terms (always missing edge cases)
- Can't handle misspellings ("elctric vehical" fails)
- Can't handle phonetic Roman Urdu ("gaari" vs "gari" vs "gaadi")
- Can't understand context ("apple" = fruit Ch.08 vs "apple" = iPhone Ch.85)
- Maintenance nightmare as new products emerge

LLM solves ALL of these because it:
- Understands Urdu script, Roman Urdu, and English natively
- Handles misspellings and phonetic variations
- Understands context (disambiguates "apple" based on rest of query)
- Knows HS classification hierarchy (trained on trade documentation)
- Requires ZERO maintenance when new products appear
- Already paid for (OpenAI API key in .env)

## WHAT EXISTS (DO NOT BREAK)
- RAG pipeline: FAISS → ChatOpenAI (for document-based Q&A)
- WEBOC scraper: WEBOCTariffScraper class
- TIPP integration: _fetch_hs_data_all_sources() orchestrator
- normalize_hs_code(): 8-digit XXXX.XXXX
- OpenAI API key loaded via dotenv
- ChatOpenAI imported from langchain_openai
- All other tabs and calculators

## RULES
1. DO NOT rewrite or refactor app_integrated.py (minimal integration only)
2. DO NOT break existing RAG, WEBOC, or TIPP search
3. DO NOT touch Import/Export Calculators or other tabs
4. Create new files in pakistan/ package
5. DO NOT touch japan/ folder
6. Reuse the EXISTING OpenAI API key and ChatOpenAI setup
7. Smart search is ADDITIONAL — user can toggle between modes

## CREATE THESE FILES:

### 1. pakistan/__init__.py
```python
from pakistan.llm_search import LLMHSSearch
from pakistan.pct_hierarchy import get_classification_path, HEADING_DESCRIPTIONS
```

### 2. pakistan/pct_hierarchy.py

HS classification hierarchy knowledge. Keep this file — it's used for
DISPLAY (breadcrumb paths) and POST-SEARCH validation, not for the
search itself. The LLM handles the search intelligence.

```python
"""
Pakistan Customs Tariff (PCT) hierarchy for display and validation.
The LLM handles search intelligence — this module handles:
  - Classification breadcrumb display
  - Parts vs Products detection
  - Heading context display
  - User education on what HS does/doesn't classify
"""

# Heading descriptions — top 200 traded headings
# Used for: displaying heading context in search results
HEADING_DESCRIPTIONS = {
    # Chapter 87 — Vehicles
    '8701': 'Tractors (other than tractors of heading 87.09)',
    '8702': 'Motor vehicles for the transport of ten or more persons, including the driver',
    '8703': 'Motor cars and other motor vehicles principally designed for the transport of persons (other than those of heading 87.02), including station wagons and racing cars',
    '8704': 'Motor vehicles for the transport of goods',
    '8705': 'Special purpose motor vehicles',
    '8708': 'Parts and accessories of the motor vehicles of headings 87.01 to 87.05',
    '8711': 'Motorcycles (including mopeds) and cycles fitted with an auxiliary motor',
    '8712': 'Bicycles and other cycles, not motorised',
    '8716': 'Trailers and semi-trailers',
    
    # Chapter 85 — Electronics
    '8517': 'Telephone sets, including smartphones; other apparatus for transmission or reception of voice, images or other data',
    '8471': 'Automatic data processing machines and units thereof',
    '8528': 'Monitors and projectors; reception apparatus for television',
    '8507': 'Electric accumulators, including separators therefor',
    '8541': 'Semiconductor devices; light-emitting diodes; photovoltaic cells',
    '8542': 'Electronic integrated circuits',
    '8414': 'Air or vacuum pumps; fans',
    '8415': 'Air conditioning machines',
    '8418': 'Refrigerators, freezers',
    '8450': 'Household washing machines',
    '8516': 'Electric instantaneous or storage water heaters; electric irons, hair dryers',
    
    # Chapter 84 — Machinery
    '8407': 'Spark-ignition internal combustion piston engines',
    '8408': 'Compression-ignition internal combustion piston engines (diesel)',
    '8413': 'Pumps for liquids',
    '8429': 'Self-propelled bulldozers, graders, scrapers, excavators',
    '8431': 'Parts for machinery of headings 84.25 to 84.30',
    '8443': 'Printing machinery; printers, copying machines, facsimile machines',
    '8474': 'Machinery for sorting, screening, mixing or kneading earth, stone, ores',
    
    # Food & Agriculture
    '0901': 'Coffee, whether or not roasted or decaffeinated',
    '0902': 'Tea, whether or not flavoured',
    '0910': 'Ginger, saffron, turmeric, thyme, curry and other spices',
    '1001': 'Wheat and meslin',
    '1005': 'Maize (corn)',
    '1006': 'Rice',
    '1701': 'Cane or beet sugar and chemically pure sucrose',
    '1507': 'Soya-bean oil',
    '1511': 'Palm oil',
    '1512': 'Sunflower-seed or safflower oil',
    '0713': 'Dried leguminous vegetables (lentils, chickpeas, beans)',
    
    # Petroleum & Chemicals
    '2709': 'Petroleum oils, crude',
    '2710': 'Petroleum oils, other than crude',
    '2711': 'Petroleum gases and other gaseous hydrocarbons',
    '3004': 'Medicaments for therapeutic or prophylactic uses, in dosage',
    '3102': 'Mineral or chemical fertilisers, nitrogenous',
    '3105': 'Mineral or chemical fertilisers containing NPK',
    
    # Textiles (Pakistan TOP export)
    '5201': 'Cotton, not carded or combed',
    '5208': 'Woven fabrics of cotton, ≥85% cotton, ≤200 g/m²',
    '5209': 'Woven fabrics of cotton, ≥85% cotton, >200 g/m²',
    '5210': 'Woven fabrics of cotton, <85% cotton, mixed with man-made fibres',
    '6109': 'T-shirts, singlets and other vests, knitted or crocheted',
    '6110': 'Jerseys, pullovers, cardigans, knitted or crocheted',
    '6203': "Men's or boys' suits, jackets, trousers",
    '6204': "Women's or girls' suits, jackets, dresses, skirts",
    '6302': 'Bed linen, table linen, toilet linen and kitchen linen',
    '5701': 'Carpets and other textile floor coverings, knotted',
    '5702': 'Carpets and other textile floor coverings, woven',
    '6301': 'Blankets and travelling rugs',
    
    # Iron & Steel
    '7208': 'Flat-rolled products of iron/steel, ≥600mm wide, hot-rolled',
    '7210': 'Flat-rolled products of iron/steel, ≥600mm wide, clad/plated/coated',
    '7213': 'Bars and rods, hot-rolled, of iron or non-alloy steel',
    '7214': 'Other bars and rods of iron or non-alloy steel',
    '7304': 'Tubes, pipes and hollow profiles, seamless, of iron or steel',
    '7306': 'Other tubes, pipes and hollow profiles, of iron or steel',
    
    # Other key Pakistan imports
    '2523': 'Portland cement, aluminous cement, slag cement',
    '3901': 'Polymers of ethylene, in primary forms',
    '3923': 'Articles for packing of goods, of plastics',
    '4011': 'New pneumatic tyres, of rubber',
    '6403': 'Footwear with outer soles of rubber/plastics, uppers of leather',
    '7108': 'Gold, unwrought or in semi-manufactured forms',
    '7113': 'Articles of jewellery, of precious metal',
    '7601': 'Unwrought aluminium',
    '9018': 'Instruments and appliances used in medical, surgical or veterinary sciences',
    
    # Add more headings as needed
}

# Chapter descriptions
CHAPTER_DESCRIPTIONS = {
    1: 'Live animals', 2: 'Meat and edible meat offal',
    3: 'Fish and crustaceans', 4: 'Dairy produce; eggs; honey',
    5: 'Products of animal origin', 6: 'Live trees and plants',
    7: 'Edible vegetables', 8: 'Edible fruit and nuts',
    9: 'Coffee, tea, mate and spices', 10: 'Cereals',
    11: 'Products of milling industry', 12: 'Oil seeds',
    13: 'Lac; gums, resins', 14: 'Vegetable plaiting materials',
    15: 'Animal/vegetable fats and oils', 16: 'Preparations of meat/fish',
    17: 'Sugars and confectionery', 18: 'Cocoa and cocoa preparations',
    19: 'Preparations of cereals/flour', 20: 'Preparations of vegetables/fruit',
    21: 'Miscellaneous edible preparations', 22: 'Beverages, spirits, vinegar',
    23: 'Residues from food industries', 24: 'Tobacco',
    25: 'Salt; sulphur; cement', 26: 'Ores, slag and ash',
    27: 'Mineral fuels, petroleum', 28: 'Inorganic chemicals',
    29: 'Organic chemicals', 30: 'Pharmaceutical products',
    31: 'Fertilisers', 32: 'Tanning/dyeing extracts; paints',
    33: 'Essential oils; perfumery; cosmetics', 34: 'Soap; washing preparations',
    35: 'Albuminoidal substances; glues', 36: 'Explosives',
    37: 'Photographic goods', 38: 'Miscellaneous chemical products',
    39: 'Plastics and articles thereof', 40: 'Rubber and articles thereof',
    41: 'Raw hides and skins', 42: 'Articles of leather',
    43: 'Furskins and artificial fur', 44: 'Wood and articles of wood',
    45: 'Cork', 46: 'Basketware',
    47: 'Pulp of wood', 48: 'Paper and paperboard',
    49: 'Printed books, newspapers', 50: 'Silk',
    51: 'Wool and animal hair', 52: 'Cotton',
    53: 'Other vegetable textile fibres', 54: 'Man-made filaments',
    55: 'Man-made staple fibres', 56: 'Wadding, felt, nonwovens',
    57: 'Carpets and textile floor coverings', 58: 'Special woven fabrics',
    59: 'Impregnated/coated textile fabrics', 60: 'Knitted or crocheted fabrics',
    61: 'Knitted or crocheted garments', 62: 'Non-knitted garments',
    63: 'Other made up textile articles', 64: 'Footwear',
    65: 'Headgear', 66: 'Umbrellas',
    67: 'Prepared feathers; artificial flowers', 68: 'Articles of stone/cement',
    69: 'Ceramic products', 70: 'Glass and glassware',
    71: 'Precious metals; jewellery', 72: 'Iron and steel',
    73: 'Articles of iron or steel', 74: 'Copper',
    75: 'Nickel', 76: 'Aluminium',
    78: 'Lead', 79: 'Zinc', 80: 'Tin', 81: 'Other base metals',
    82: 'Tools of base metal', 83: 'Miscellaneous articles of base metal',
    84: 'Nuclear reactors; boilers; machinery', 85: 'Electrical machinery and equipment',
    86: 'Railway locomotives', 87: 'Vehicles other than railway',
    88: 'Aircraft and spacecraft', 89: 'Ships, boats',
    90: 'Optical, measuring, medical instruments', 91: 'Clocks and watches',
    92: 'Musical instruments', 93: 'Arms and ammunition',
    94: 'Furniture; bedding; lamps', 95: 'Toys, games, sports',
    96: 'Miscellaneous manufactured articles', 97: 'Works of art; antiques',
}

def get_heading_description(hs_code):
    """Get 4-digit heading description for any HS code"""
    clean = hs_code.replace('.', '').replace('-', '').replace(' ', '')
    heading = clean[:4]
    return HEADING_DESCRIPTIONS.get(heading, '')

def get_chapter_description(hs_code):
    """Get chapter description"""
    clean = hs_code.replace('.', '').replace('-', '').replace(' ', '')
    try:
        chapter = int(clean[:2])
        return CHAPTER_DESCRIPTIONS.get(chapter, '')
    except ValueError:
        return ''

def get_classification_path(hs_code):
    """Full breadcrumb for display"""
    clean = hs_code.replace('.', '').replace('-', '').replace(' ', '')
    try:
        chapter_num = int(clean[:2])
    except ValueError:
        return {}
    heading = clean[:4]
    
    return {
        'section': _get_section(chapter_num),
        'chapter': f"{chapter_num:02d}",
        'chapter_desc': CHAPTER_DESCRIPTIONS.get(chapter_num, ''),
        'heading': f"{heading[:2]}.{heading[2:]}",
        'heading_desc': HEADING_DESCRIPTIONS.get(heading, ''),
        'full_code': hs_code,
    }

def is_part_not_product(description):
    """Detect if entry is a PART/ACCESSORY rather than complete product"""
    if not description:
        return False
    desc_lower = description.lower()
    part_indicators = [
        'for motor vehicles', 'parts and accessories', 'parts suitable for',
        'parts of', 'suitable for use', 'of the vehicles of',
        'of the machines of', 'for the engines of',
    ]
    return any(ind in desc_lower for ind in part_indicators)

def _get_section(chapter):
    sections = [
        (1,5,'I'), (6,14,'II'), (15,15,'III'), (16,24,'IV'),
        (25,27,'V'), (28,38,'VI'), (39,40,'VII'), (41,43,'VIII'),
        (44,46,'IX'), (47,49,'X'), (50,63,'XI'), (64,67,'XII'),
        (68,70,'XIII'), (71,71,'XIV'), (72,83,'XV'), (84,85,'XVI'),
        (86,89,'XVII'), (90,92,'XVIII'), (93,93,'XIX'), (94,96,'XX'),
        (97,97,'XXI'),
    ]
    for start, end, num in sections:
        if start <= chapter <= end:
            return num
    return ''
```

### 3. pakistan/llm_search.py

THE CORE MODULE. Uses OpenAI GPT to understand any query in any language
and translate it to official HS classification terms.

```python
"""
LLM-Powered HS Code Search for Pakistan Customs Tariff

Uses OpenAI GPT (already available in the app) to:
1. Understand queries in English, Urdu, Roman Urdu, mixed, misspelled
2. Translate consumer language to official WCO/HS trade terminology
3. Identify likely HS chapter, heading, and subheading
4. Suggest specific PCT codes with confidence levels
5. Explain WHY a classification was chosen (classification reasoning)
6. Tell user which of their search terms HS doesn't classify

This replaces the static synonym dictionary approach entirely.
One LLM call handles what 300+ dictionary entries could not.
"""

import json
import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# The system prompt that turns GPT into an HS classification expert
HS_CLASSIFIER_PROMPT = """You are a Pakistan Customs Tariff (PCT) classification expert.
Your job: translate ANY user query into official HS/PCT codes.

CONTEXT:
- Pakistan uses 8-digit PCT codes: XXXX.XXXX format
- First 6 digits follow WCO Harmonized System (same worldwide)
- 7th-8th digits are Pakistan national extensions
- You must understand: English, Urdu (اردو), Roman Urdu, mixed languages, 
  misspellings, phonetic spellings, trade slang, consumer language

HS CLASSIFICATION HIERARCHY (ask in this order):
1. WHAT IS IT? → Chapter (2-digit: 01-97)
2. PURPOSE/USE? → Heading (4-digit)
3. MATERIAL/PROPULSION/PROCESS? → Subheading (6-digit)
4. SIZE/CAPACITY/GRADE? → within subheading
5. PAKISTAN NATIONAL SPECIFICS → 7th-8th digit

FEATURES HS CLASSIFIES BY:
- Product type, purpose, material composition, propulsion type
- Engine capacity (cc), processing level, weight (for some)
- Pakistan-specific: SUV 4x4 distinction at 8703.2323

FEATURES HS DOES NOT CLASSIFY (tell the user):
- Brand/make/manufacturer, color, number of doors
- Drivetrain (FWD/RWD/AWD) — EXCEPT Pakistan has SUV 4x4
- Seating count under 10 (only 87.02 = "10+ persons")
- Body style (sedan/hatchback/coupe), model year
- Automatic vs manual transmission

PAKISTAN KEY TRADE CODES (most commonly looked up):
- 8703.2321-2323: Passenger cars 1500-3000cc (Pakistan splits by cc band + SUV)
- 8703.8000: Electric vehicles (BEV)
- 8703.4000/6000: Hybrid/PHEV
- 8517.1211/1219: Smartphones (CKD/CBU)
- 8471: Computers/laptops
- 1006: Rice (Pakistan major export)
- 5208-5212: Cotton fabrics (Pakistan major export)
- 6109: T-shirts (Pakistan major export)
- 9018: Surgical instruments (Pakistan specialty export)
- 2710: Petroleum products
- 2523: Cement
- 3102/3105: Fertilizers
- 7213/7214: Steel bars/rods
- 4011: Tyres
- 8507: Batteries
- 8541.40: Solar panels

RESPOND IN THIS EXACT JSON FORMAT (no markdown, no backticks):
{
  "understood_query": "what you understood the user is looking for",
  "language_detected": "en|ur|roman_ur|mixed",
  "search_terms_en": ["official", "hs", "trade", "terms"],
  "likely_chapter": 87,
  "likely_heading": "8703",
  "likely_codes": [
    {
      "code": "8703.8000",
      "description": "Motor vehicles with only electric motor for propulsion",
      "confidence": "high",
      "reasoning": "User asked for EV/electric car → 87.03 for passenger vehicles, .80 for electric-only propulsion"
    },
    {
      "code": "8703.6000",
      "description": "PHEV spark-ignition + electric, plug-in capable",
      "confidence": "medium",
      "reasoning": "If user means plug-in hybrid rather than pure EV"
    }
  ],
  "ignored_terms": ["front wheel drive", "4 seater"],
  "ignored_reason": "HS does not classify by drivetrain or seating count (under 10 persons)",
  "disambiguation": "If you meant iPhone/Apple product, look at Chapter 85 (8517.12 for phones, 8471 for computers)",
  "related_headings": ["8703", "8702", "8711"]
}

RULES:
- Always respond with valid JSON only. No explanation text outside JSON.
- "likely_codes" must have 1-5 entries, sorted by confidence (high first)
- "confidence" is "high", "medium", or "low"
- Include "ignored_terms" for ANY user terms that HS doesn't classify
- Include "disambiguation" ONLY if the query is ambiguous
- "search_terms_en" are the official English WCO terms to search in the PCT database
- If query is in Urdu/Roman Urdu, still return search_terms_en in ENGLISH
- For Roman Urdu, handle phonetic variations: gaari/gari/gaadi all = vehicle
"""


class LLMHSSearch:
    """
    LLM-powered HS code search engine.
    
    Uses GPT to understand natural language queries in any language
    and return structured HS classification results.
    """
    
    def __init__(self, model="gpt-4o-mini"):
        """
        Initialize with OpenAI client.
        Uses gpt-4o-mini by default (fast, cheap, good enough for classification).
        Can upgrade to gpt-4o for complex queries.
        
        Args:
            model: OpenAI model name. "gpt-4o-mini" recommended for speed/cost.
                   "gpt-4o" for maximum accuracy on edge cases.
        """
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.model = model
        self._cache = {}  # Simple in-memory cache to avoid repeat API calls
    
    def classify(self, query, use_cache=True):
        """
        Main method: Send user query to LLM, get structured HS classification.
        
        Args:
            query: User search string (any language, any format)
            use_cache: Cache results for identical queries (default True)
        
        Returns:
            dict with keys: understood_query, language_detected, 
            search_terms_en, likely_chapter, likely_heading, likely_codes,
            ignored_terms, ignored_reason, disambiguation, related_headings
            
            Returns None if API call fails.
        """
        query = query.strip()
        if not query:
            return None
        
        # Check cache
        cache_key = query.lower()
        if use_cache and cache_key in self._cache:
            return self._cache[cache_key]
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": HS_CLASSIFIER_PROMPT},
                    {"role": "user", "content": query}
                ],
                temperature=0.1,  # Low temperature for consistent classification
                max_tokens=800,
                response_format={"type": "json_object"}  # Force JSON response
            )
            
            result_text = response.choices[0].message.content
            result = json.loads(result_text)
            
            # Cache it
            if use_cache:
                self._cache[cache_key] = result
            
            return result
            
        except json.JSONDecodeError:
            # LLM didn't return valid JSON — try to extract
            try:
                # Sometimes LLM wraps in ```json ... ```
                cleaned = result_text.strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned.split("```")[1]
                    if cleaned.startswith("json"):
                        cleaned = cleaned[4:]
                result = json.loads(cleaned)
                if use_cache:
                    self._cache[cache_key] = result
                return result
            except:
                return None
        except Exception as e:
            # API error — return None, caller should fallback to RAG
            print(f"LLM Search error: {e}")
            return None
    
    def search(self, query, tariff_data=None):
        """
        Full search pipeline:
        1. LLM classifies the query → structured result
        2. If tariff_data provided, lookup actual codes in data
        3. Merge LLM suggestions with actual data matches
        
        Args:
            query: User search string
            tariff_data: Optional dict {hs_code: {description: str, ...}}
                        If provided, validates LLM suggestions against actual data
        
        Returns:
            dict with:
              'llm_result': raw LLM classification
              'matches': list of actual matching entries from tariff_data
              'search_terms': English terms for secondary search
        """
        # Step 1: LLM classification
        llm_result = self.classify(query)
        
        if llm_result is None:
            return {
                'llm_result': None,
                'matches': [],
                'search_terms': [],
                'error': 'LLM classification failed. Try RAG search.'
            }
        
        # Step 2: If we have tariff data, validate and enrich
        matches = []
        if tariff_data:
            # Look up each suggested code
            for suggestion in llm_result.get('likely_codes', []):
                code = suggestion.get('code', '')
                code_prefix = code.replace('.', '').replace('-', '').replace(' ', '')
                
                for data_code, entry in tariff_data.items():
                    data_clean = data_code.replace('.', '').replace('-', '')
                    if data_clean.startswith(code_prefix) or code_prefix.startswith(data_clean[:6]):
                        matches.append({
                            'hs_code': data_code,
                            'description': entry.get('description', ''),
                            'llm_confidence': suggestion.get('confidence', 'low'),
                            'llm_reasoning': suggestion.get('reasoning', ''),
                            **entry  # include any other data (rates, etc.)
                        })
            
            # Also search by LLM-provided English terms
            search_terms = llm_result.get('search_terms_en', [])
            if search_terms and len(matches) < 5:
                for code, entry in tariff_data.items():
                    desc = (entry.get('description', '') or '').lower()
                    match_count = sum(1 for t in search_terms if t.lower() in desc)
                    if match_count >= 2 and code not in [m['hs_code'] for m in matches]:
                        matches.append({
                            'hs_code': code,
                            'description': entry.get('description', ''),
                            'llm_confidence': 'low',
                            'llm_reasoning': f'Matched {match_count} search terms',
                            **entry
                        })
            
            # Deduplicate
            seen = set()
            unique_matches = []
            for m in matches:
                if m['hs_code'] not in seen:
                    seen.add(m['hs_code'])
                    unique_matches.append(m)
            matches = unique_matches[:15]
        
        return {
            'llm_result': llm_result,
            'matches': matches,
            'search_terms': llm_result.get('search_terms_en', []),
        }
    
    def clear_cache(self):
        """Clear the query cache"""
        self._cache = {}


# Convenience function for simple usage
def llm_search(query, tariff_data=None, model="gpt-4o-mini"):
    """Quick search without instantiating class"""
    searcher = LLMHSSearch(model=model)
    return searcher.search(query, tariff_data)
```

### 4. Integration into app_integrated.py

MINIMAL changes. Add LLM search as a third search mode alongside 
existing RAG search in Tab 1.

```
CHANGES TO app_integrated.py:

# ============================================================
# CHANGE 1: Add import at top (after existing imports, ~line 30-50)
# ============================================================

try:
    from pakistan.llm_search import LLMHSSearch
    from pakistan.pct_hierarchy import (
        get_classification_path, get_heading_description, 
        is_part_not_product, HEADING_DESCRIPTIONS
    )
    LLM_SEARCH_AVAILABLE = True
except ImportError:
    LLM_SEARCH_AVAILABLE = False


# ============================================================
# CHANGE 2: Initialize LLM searcher in session_state (after existing inits)
# ============================================================

if LLM_SEARCH_AVAILABLE and 'llm_searcher' not in st.session_state:
    st.session_state.llm_searcher = LLMHSSearch(model="gpt-4o-mini")


# ============================================================
# CHANGE 3: In Tab 1 (HS Code Lookup), add search mode toggle
# Find the existing search area and ADD this before the search button.
# DO NOT remove existing search code — wrap it in the else branch.
# ============================================================

if LLM_SEARCH_AVAILABLE:
    search_mode = st.radio(
        "🔍 Search Mode / تلاش کا طریقہ",
        ["🤖 Smart Search (EN / اردو / Roman Urdu)", "📚 Document Search (RAG)"],
        horizontal=True,
        help="Smart Search uses AI to understand natural language in any language. Document Search queries the PCT PDF directly."
    )
else:
    search_mode = "📚 Document Search (RAG)"

# When search button is clicked:

if "Smart Search" in search_mode and LLM_SEARCH_AVAILABLE:
    
    with st.spinner("🔍 Analyzing query... / تلاش جاری ہے..."):
        # Build tariff_data from existing cached data if available
        # (from WEBOC cache, TIPP cache, or FAISS documents)
        tariff_data = _build_tariff_data_for_search()  # see helper below
        
        result = st.session_state.llm_searcher.search(user_query, tariff_data)
    
    llm = result.get('llm_result')
    
    if llm:
        # Show what LLM understood
        st.caption(f"🧠 Understood: **{llm.get('understood_query', '')}** "
                   f"| Language: {llm.get('language_detected', 'en')}")
        
        # Show ignored terms if any
        ignored = llm.get('ignored_terms', [])
        if ignored:
            reason = llm.get('ignored_reason', 'Not classified in HS system')
            st.info(f"ℹ️ Terms not used in HS: **{', '.join(ignored)}** — {reason}")
        
        # Show disambiguation if any
        disambig = llm.get('disambiguation')
        if disambig:
            st.warning(f"💡 {disambig}")
        
        # Show likely codes from LLM
        likely = llm.get('likely_codes', [])
        
        if likely:
            for i, suggestion in enumerate(likely):
                code = suggestion.get('code', '')
                desc = suggestion.get('description', '')
                conf = suggestion.get('confidence', '')
                reason = suggestion.get('reasoning', '')
                
                # Confidence badge
                badge = {'high': '🟢', 'medium': '🟡', 'low': '🔴'}.get(conf, '⚪')
                
                # Get hierarchy
                hierarchy = get_classification_path(code)
                heading_ctx = get_heading_description(code)
                is_part = is_part_not_product(desc)
                
                with st.expander(
                    f"{badge} {code} — {desc[:80]}",
                    expanded=(i == 0)  # First result expanded
                ):
                    # Hierarchy breadcrumb
                    if hierarchy:
                        st.caption(
                            f"Section {hierarchy.get('section', '')} → "
                            f"Chapter {hierarchy.get('chapter', '')} "
                            f"({hierarchy.get('chapter_desc', '')}) → "
                            f"{hierarchy.get('heading', '')} → {code}"
                        )
                    
                    # Heading context
                    if heading_ctx:
                        st.markdown(f"**📋 Heading:** {heading_ctx}")
                    
                    st.markdown(f"**Description:** {desc}")
                    st.markdown(f"**Confidence:** {badge} {conf.title()}")
                    st.markdown(f"**Reasoning:** {reason}")
                    
                    if is_part:
                        st.warning("⚠️ This is a PART/ACCESSORY, not a complete product")
                    
                    # Buttons row
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button(f"🧮 Use in Calculator →", key=f"calc_{code}_{i}"):
                            st.session_state.selected_hs = code
                            st.rerun()
                    with col2:
                        if st.button(f"🔎 Lookup rates on WEBOC", key=f"weboc_{code}_{i}"):
                            # Trigger existing WEBOC lookup
                            st.session_state.weboc_lookup = code
                            st.rerun()
        
        # Also show text-matched results from tariff_data
        data_matches = result.get('matches', [])
        if data_matches:
            st.subheader(f"📄 Data Matches ({len(data_matches)})")
            for m in data_matches[:10]:
                with st.expander(f"{m['hs_code']} — {m.get('description', '')[:80]}"):
                    st.write(f"**Code:** {m['hs_code']}")
                    st.write(f"**Description:** {m.get('description', '')}")
                    if m.get('llm_reasoning'):
                        st.caption(f"Match reason: {m['llm_reasoning']}")
    
    else:
        st.error("Smart search failed. Please try Document Search (RAG).")

else:
    # ============================================================
    # EXISTING RAG SEARCH CODE GOES HERE — UNCHANGED
    # ============================================================
    pass  # existing code


# ============================================================
# HELPER FUNCTION: Build tariff_data from existing caches
# Add this function somewhere accessible in the file
# ============================================================

def _build_tariff_data_for_search():
    """
    Build a {hs_code: {description: str}} dict from existing cached data.
    
    Try sources in order:
    1. WEBOC cache (weboc.db) — already has code→description mapping
    2. TIPP cache (tipp.db) — another cached source
    3. FAISS vectorstore — parse HS codes from document chunks
    4. Empty dict — LLM search still works, just can't validate
    
    Cache in session_state to avoid rebuilding every search.
    """
    if 'tariff_data_for_search' in st.session_state:
        return st.session_state.tariff_data_for_search
    
    tariff_data = {}
    
    # Try WEBOC cache first
    try:
        import sqlite3
        if os.path.exists('weboc.db'):
            conn = sqlite3.connect('weboc.db')
            cursor = conn.execute(
                "SELECT DISTINCT hs_code, description FROM weboc_cache"
            )
            for row in cursor:
                if row[0] and row[1]:
                    tariff_data[row[0]] = {'description': row[1]}
            conn.close()
    except Exception:
        pass
    
    # Try TIPP cache
    try:
        if os.path.exists('tipp.db'):
            conn = sqlite3.connect('tipp.db')
            cursor = conn.execute(
                "SELECT DISTINCT hs_code, description FROM tipp_cache"
            )
            for row in cursor:
                if row[0] and row[1] and row[0] not in tariff_data:
                    tariff_data[row[0]] = {'description': row[1]}
            conn.close()
    except Exception:
        pass
    
    # If we got data, cache it
    if tariff_data:
        st.session_state.tariff_data_for_search = tariff_data
    
    return tariff_data
```

## IMPLEMENTATION ORDER
```
1. pakistan/__init__.py       → python -c "import pakistan"
2. pakistan/pct_hierarchy.py  → python -c "from pakistan.pct_hierarchy import get_heading_description; print(get_heading_description('8703'))"
3. pakistan/llm_search.py     → python -c "from pakistan.llm_search import LLMHSSearch; s=LLMHSSearch(); r=s.classify('EV car'); print(r)"
4. Integration in app_integrated.py → Minimal: import + toggle + results display
```

## VERIFICATION TESTS

Run these AFTER step 3 (llm_search.py) to verify LLM responses:

```python
from pakistan.llm_search import LLMHSSearch
s = LLMHSSearch(model="gpt-4o-mini")

# Test 1: English natural language
r = s.classify("EV car front wheel drive 4 seater")
assert r['likely_codes'][0]['code'].startswith('8703.8')
assert 'front wheel drive' in r['ignored_terms'] or 'seater' in r['ignored_terms']
print("✅ Test 1 passed:", r['likely_codes'][0]['code'])

# Test 2: Urdu script
r = s.classify("الیکٹرک گاڑی")
assert r['likely_codes'][0]['code'].startswith('8703.8')
assert r['language_detected'] in ['ur', 'urdu']
print("✅ Test 2 passed:", r['understood_query'])

# Test 3: Roman Urdu
r = s.classify("chawal basmati")
assert r['likely_chapter'] == 10 or r['likely_codes'][0]['code'].startswith('1006')
print("✅ Test 3 passed:", r['likely_codes'][0]['code'])

# Test 4: Roman Urdu with phonetic variation
r = s.classify("mobile fone")
assert r['likely_codes'][0]['code'].startswith('8517')
print("✅ Test 4 passed:", r['likely_codes'][0]['code'])

# Test 5: Mixed Urdu + English
r = s.classify("steel کا پائپ")
assert int(r['likely_chapter']) in [72, 73]
print("✅ Test 5 passed:", r['likely_codes'][0]['code'])

# Test 6: Pakistan-specific SUV
r = s.classify("SUV 4x4 gaari")
assert '8703.2323' in r['likely_codes'][0]['code'] or '8703.23' in r['likely_codes'][0]['code']
print("✅ Test 6 passed:", r['likely_codes'][0]['code'])

# Test 7: Urdu for fertilizer
r = s.classify("کھاد یوریا")
assert r['likely_codes'][0]['code'].startswith('310')
print("✅ Test 7 passed:", r['likely_codes'][0]['code'])

# Test 8: Misspelling tolerance
r = s.classify("elctric vehical bateery")
assert r['likely_codes'][0]['code'].startswith('8703.8') or r['likely_codes'][0]['code'].startswith('8507')
print("✅ Test 8 passed:", r['likely_codes'][0]['code'])

# Test 9: Disambiguation
r = s.classify("apple")
assert r.get('disambiguation')  # Should mention fruit vs electronics
print("✅ Test 9 passed: disambiguation =", r['disambiguation'][:60])

# Test 10: Surgical instruments (Pakistan specialty)
r = s.classify("سرجیکل آلات")
assert r['likely_codes'][0]['code'].startswith('9018')
print("✅ Test 10 passed:", r['likely_codes'][0]['code'])

print("\n🎉 All tests passed!")
```

## COST ESTIMATE
- gpt-4o-mini: ~$0.15/1M input tokens, ~$0.60/1M output tokens
- Each search = ~500 input tokens (prompt) + ~300 output tokens (response)
- Cost per search: ~$0.0003 (less than 1 paisa)
- 1000 searches/day = ~$0.30/day = ~PKR 85/day
- With caching, repeated queries are FREE

## DO NOT:
- Rewrite app_integrated.py
- Remove or modify RAG search (keep as fallback)
- Remove or modify WEBOC scraper
- Remove or modify TIPP integration
- Touch japan/ folder
- Touch Import/Export Calculators or other tabs
- Change any existing function signatures
- Modify any .db cache files

## ADVANTAGES OVER STATIC DICTIONARY APPROACH
1. Handles ALL languages natively (Urdu, Roman Urdu, English, mixed)
2. Understands misspellings and phonetic variations
3. Context-aware disambiguation ("apple" fruit vs electronics)
4. Knows HS hierarchy and classification reasoning
5. Explains WHY a code was chosen (educational for users)
6. Tells user which terms HS doesn't classify (front wheel drive, seating)
7. Zero maintenance — no dictionary updates needed
8. Already paid for (existing OpenAI API key)
9. 3 files to create vs 4 files with 300+ dictionary entries
10. Handles edge cases the dictionary would miss
