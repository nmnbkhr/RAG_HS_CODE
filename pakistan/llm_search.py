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
                cleaned = result_text.strip()
                if cleaned.startswith("```"):
                    cleaned = cleaned.split("```")[1]
                    if cleaned.startswith("json"):
                        cleaned = cleaned[4:]
                result = json.loads(cleaned)
                if use_cache:
                    self._cache[cache_key] = result
                return result
            except Exception:
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
