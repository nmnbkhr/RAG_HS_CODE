"""
LLM-powered smart search for Japan Customs tariff data.

Uses GPT-4o-mini as a query preprocessor to translate natural language
into structured HS code classification data, then performs deterministic
lookup against scraped tariff entries.  The LLM never returns tariff
rates — it only classifies.  Actual rates come from scraper.data.
"""

import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompt — the core of the LLM classifier
# ---------------------------------------------------------------------------
_SYSTEM_PROMPT = """\
You are an expert customs tariff classifier for Japan Customs (税関).
Your job is to translate a user's product description into structured HS
code classification data.  Return ONLY valid JSON.

## HS Code Structure (Japan 9-digit system)
- Chapter: 2 digits (01-97)
- Heading: 4 digits (XXXX)
- Subheading: 6 digits (XXXX.XX)
- Statistical code: 9 digits (XXXX.XX-XXX)

## Key Chapter References
01-05 Live animals, animal products | 06-14 Vegetable products |
15 Fats/oils | 16-24 Foodstuffs, beverages, tobacco |
25-27 Mineral products, fuels | 28-38 Chemicals |
39-40 Plastics, rubber | 41-43 Leather | 44-46 Wood |
47-49 Paper | 50-63 Textiles, apparel | 64-67 Footwear |
68-70 Stone, ceramic, glass | 71 Precious metals, jewelry |
72-83 Base metals | 84 Machinery | 85 Electrical/electronics |
86-89 Vehicles, aircraft, ships | 90 Instruments |
91 Clocks/watches | 94-96 Furniture, toys, misc.

## Vehicle Classification (Chapter 87 — critical)
- 8701 Tractors
- 8702 Motor vehicles >= 10 persons
- 8703 Motor cars / passenger vehicles
  - 8703.10     Snow vehicles, golf cars
  - 8703.21-24  Spark-ignition (petrol/gasoline) by cylinder capacity
  - 8703.31-33  Compression-ignition (diesel) by cylinder capacity
  - 8703.40     Spark-ignition + electric hybrid
  - 8703.50     Diesel + electric hybrid
  - 8703.60     Plug-in hybrid (spark-ignition)
  - 8703.70     Plug-in hybrid (diesel)
  - 8703.80     Only electric motor (pure EV/BEV)
- 8704 Trucks / goods transport
- 8711 Motorcycles

## Common Mappings
- smartphone/iPhone → 8517 | laptop → 8471 | TV/monitor → 8528
- Toyota Camry/sedan → 8703.23-24 | Tesla/EV → 8703.80
- sake/日本酒 → 2206 | green tea/抹茶 → 0902 | rice/米 → 1006
- coffee → 0901 | wine → 2204 | whisky → 2208
- solar panel → 8541 | lithium battery → 8507 | LED → 8541
- running shoes → 6404 | silk kimono → 6204 + Ch.50
- semiconductor/IC → 8542

## Instructions
1. Understand the query (English, Japanese, or mixed).
2. Identify the most likely chapter(s) and heading(s).
3. Suggest specific subheadings / 9-digit codes when possible.
4. Generate English search terms matching official tariff descriptions.
5. For Japanese input, also return Japanese search terms.
6. Rate confidence: high / medium / low.

## Required JSON Response
{
  "intent": "brief English description of what the user wants",
  "intent_jp": "Japanese equivalent (or empty string)",
  "chapter": [87],
  "headings": ["8703"],
  "subheadings": ["8703.21", "8703.22", "8703.23", "8703.24"],
  "hs_candidates": ["8703.21-000", "8703.22-000", "8703.23-000", "8703.24-000"],
  "search_terms": ["motor car", "spark-ignition", "passenger"],
  "search_terms_jp": [],
  "confidence": "high",
  "reasoning": "short explanation"
}
"""

# ---------------------------------------------------------------------------
# Data class for structured LLM output
# ---------------------------------------------------------------------------

@dataclass
class LLMClassification:
    """Structured output from the LLM query preprocessor."""
    intent: str = ""
    intent_jp: str = ""
    chapter: list[int] = field(default_factory=list)
    headings: list[str] = field(default_factory=list)
    subheadings: list[str] = field(default_factory=list)
    hs_candidates: list[str] = field(default_factory=list)
    search_terms: list[str] = field(default_factory=list)
    search_terms_jp: list[str] = field(default_factory=list)
    confidence: str = "low"
    reasoning: str = ""
    error: str = ""


# ---------------------------------------------------------------------------
# In-memory cache
# ---------------------------------------------------------------------------
_llm_cache: dict[str, LLMClassification] = {}


def _cache_key(query: str) -> str:
    return hashlib.md5(query.strip().lower().encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# API key validation
# ---------------------------------------------------------------------------

def _validate_api_key() -> tuple[bool, str]:
    """Return (valid, key_or_error_message)."""
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        return False, "OPENAI_API_KEY not found in environment"
    if not key.startswith("sk-"):
        return False, "OPENAI_API_KEY appears invalid (must start with sk-)"
    return True, key


def is_llm_available() -> bool:
    """Check whether LLM search can be used."""
    valid, _ = _validate_api_key()
    return valid


def clear_cache() -> int:
    """Clear LLM response cache.  Returns entries cleared."""
    n = len(_llm_cache)
    _llm_cache.clear()
    return n


# ---------------------------------------------------------------------------
# LLM classifier
# ---------------------------------------------------------------------------

def classify_query(query: str, use_cache: bool = True) -> LLMClassification:
    """
    Send *query* to GPT-4o-mini and return structured HS classification.

    On any failure the returned object has ``.error`` set and all other
    fields at their defaults.
    """
    key = _cache_key(query)
    if use_cache and key in _llm_cache:
        return _llm_cache[key]

    valid, api_key_or_err = _validate_api_key()
    if not valid:
        return LLMClassification(error=api_key_or_err)

    try:
        from openai import OpenAI  # noqa: import only when needed

        client = OpenAI(api_key=api_key_or_err)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": query},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=800,
        )

        data = json.loads(resp.choices[0].message.content)

        result = LLMClassification(
            intent=data.get("intent", ""),
            intent_jp=data.get("intent_jp", ""),
            chapter=data.get("chapter", []),
            headings=data.get("headings", []),
            subheadings=data.get("subheadings", []),
            hs_candidates=data.get("hs_candidates", []),
            search_terms=data.get("search_terms", []),
            search_terms_jp=data.get("search_terms_jp", []),
            confidence=data.get("confidence", "low"),
            reasoning=data.get("reasoning", ""),
        )

        if use_cache:
            _llm_cache[key] = result
        return result

    except json.JSONDecodeError as exc:
        logger.error("LLM returned invalid JSON: %s", exc)
        return LLMClassification(error=f"LLM returned invalid JSON: {exc}")
    except ImportError:
        return LLMClassification(error="openai package is not installed")
    except Exception as exc:  # noqa: broad-except for resilience
        logger.error("LLM classification failed: %s", exc)
        return LLMClassification(error=str(exc))


# ---------------------------------------------------------------------------
# Deterministic lookup engine
# ---------------------------------------------------------------------------

def llm_search(
    query: str,
    scraper,           # JapanTariffScraper instance
    lang: str = "en",
    limit: int = 15,
    use_cache: bool = True,
) -> tuple[list[dict], LLMClassification]:
    """
    LLM-powered search: classify the query then do deterministic lookup.

    Returns ``(results, classification)``.  *results* has the same
    ``list[dict]`` format as ``scraper.search()``.
    """
    classification = classify_query(query, use_cache=use_cache)

    if classification.error:
        # Fallback to keyword search
        return scraper.search(query, lang=lang, limit=limit), classification

    scored: dict[str, tuple[int, dict]] = {}  # code → (score, entry)

    # --- TIER 1: exact 9-digit candidate match (200 pts) ---
    for candidate in classification.hs_candidates:
        from japan.hs_normalizer import normalize
        norm = normalize(candidate)
        entry = scraper.data.get(norm)
        if entry:
            scored[norm] = (200, entry)
        else:
            # prefix match (candidate may be 6-digit-ish)
            prefix = norm[:7]  # "XXXX.XX"
            for code, e in scraper.data.items():
                if code.startswith(prefix):
                    old = scored.get(code, (0, e))[0]
                    scored[code] = (max(old, 150), e)

    # --- TIER 2: subheading prefix match (120 pts) ---
    for sub in classification.subheadings:
        clean = sub.replace(".", "")
        for code, entry in scraper.data.items():
            code_digits = re.sub(r"[^0-9]", "", code)
            if code_digits.startswith(clean):
                old = scored.get(code, (0, entry))[0]
                scored[code] = (max(old, 120), entry)

    # --- TIER 3: heading prefix match (80 pts) ---
    for heading in classification.headings:
        clean = heading.replace(".", "")[:4]
        for code, entry in scraper.data.items():
            code_digits = re.sub(r"[^0-9]", "", code)
            if code_digits[:4] == clean:
                old = scored.get(code, (0, entry))[0]
                scored[code] = (max(old, 80), entry)

    # --- TIER 4: search-term text matching (+10/term) ---
    all_terms = [t.lower() for t in classification.search_terms]
    all_terms += [t for t in classification.search_terms_jp if t]

    if all_terms:
        for code, entry in scraper.data.items():
            desc_en = entry.get("desc_en", "").lower()
            desc_jp = entry.get("desc_jp", "")
            combined = desc_en + " " + desc_jp

            match_count = sum(1 for t in all_terms if t in combined)
            if match_count > 0:
                bonus = match_count * 10
                old_score, _ = scored.get(code, (0, entry))
                scored[code] = (old_score + bonus, entry)

    # --- TIER 5: chapter-level fallback (30 pts) ---
    if len(scored) < 3 and classification.chapter:
        for ch in classification.chapter:
            ch_prefix = f"{ch:02d}"
            for code, entry in scraper.data.items():
                if code[:2] == ch_prefix and code not in scored:
                    desc = entry.get("desc_en", "").lower()
                    if any(t in desc for t in all_terms):
                        scored[code] = (30, entry)

    # --- Scoring adjustments ---
    # Heading description context bonus (+15)
    for code in list(scored):
        heading_key = code[:4]
        h_desc = scraper.headings.get(heading_key, "").lower()
        if h_desc:
            intent_words = [w for w in classification.intent.lower().split() if len(w) > 3]
            if any(w in h_desc for w in intent_words):
                s, e = scored[code]
                scored[code] = (s + 15, e)

    # Child-row penalty (-5)
    for code in list(scored):
        desc = scored[code][1].get("desc_en", "")
        if desc.startswith(("- ", "-- ")):
            s, e = scored[code]
            scored[code] = (s - 5, e)

    # --- Sort, threshold, limit ---
    ranked = sorted(
        scored.values(),
        key=lambda x: (-x[0], x[1].get("statistical_code", "")),
    )

    if ranked:
        top = ranked[0][0]
        threshold = max(top * 0.3, 10)
        ranked = [(s, e) for s, e in ranked if s >= threshold]

    results = [e for _, e in ranked[:limit]]

    # Ultimate fallback: if nothing found, use keyword search
    if not results:
        results = scraper.search(query, lang=lang, limit=limit)

    return results, classification
