"""
Khujo NLP — Bangla Suffix Stripper & Morphological Normalizer
Remediates Defect D5 from khujo_code_audit.md.

Solves the asymmetric inflection problem where inflected forms
(e.g., 'ঢাকার', 'ঢাকায়', 'ঢাকাটি') fail silently against root entities ('ঢাকা').
Includes:
- Common noun protected list (non-geographical nouns)
- Dynamic database entity check against core.entity_name
- Index-time normalization helper for crawler & ingestion pipelines
"""

import re
import logging
from typing import Set, List, Optional

logger = logging.getLogger("bangla_stemmer")

# Protected Bangla common nouns that end in characters common to suffixes (e.g. র, য়, ট, ইত্যাদি)
# These MUST NOT be stripped down to single letters (e.g. ঘরের -> ঘর, never ঘ).
PROTECTED_COMMON_NOUNS: Set[str] = {
    # Common nouns ending in র, য়, ইত্যাদি
    "ঘর", "দ্বার", "শহর", "খবর", "খাবার", "সুন্দর", "উত্তর", "অন্তর", "নজর", "পাহাড়", "সাগর", "সমুদ্র",
    "সময়", "বিষয়", "আশয়", "বিশ্ববিদ্যালয়", "মহাবিদ্যালয়", "বিদ্যালয়", "কার্যালয়",
    "উপায়", "সহায়", "নিয়ম", "বাজার", "দরবার", "সরকার", "দরকার",
    "অধিকার", "ব্যবহার", "বিচার", "প্রচার", "আকার", "প্রকার", "বন্দর", "ঈশ্বর",
    "পানি", "মাটি", "বাড়ি", "গাড়ি", "দাড়ি", "নারী", "ভারী", "দেরি", "পাখি", "হাতি",
    "বন্ধু", "বোন", "ভাই", "মা", "বাবা", "মানুষ", "ছাত্র", "বই", "দেশ", "জিনিস"
}

# Standard Bangladeshi administrative divisions & districts preloaded as fallback entity roots
PRELOADED_ENTITY_ROOTS: Set[str] = {
    "বাংলাদেশ", "ঢাকা", "চট্টগ্রাম", "সিলেট", "খুলনা", "বরিশাল", "রাজশাহী", "রংপুর", "ময়মনসিংহ", "ময়মনসিংহ",
    "কুমিল্লা", "ফেনী", "ব্রাহ্মণবাড়িয়া", "রাঙ্গামাটি", "নোয়াখালী", "চাঁদপুর", "লক্ষ্মীপুর",
    "কক্সবাজার", "খাগড়াছড়ি", "বান্দরবান", "সিরাজগঞ্জ", "পাবনা", "বগুড়া", "জয়পুরহাট",
    "নাটোর", "নওগাঁ", "চাঁপাইনবাবগঞ্জ", "যশোর", "সাতক্ষীরা", "মেহেরপুর", "নড়াইল",
    "চুয়াডাঙ্গা", "কুষ্টিয়া", "মাগুরা", "বাগেরহাট", "ঝিনাইদহ", "ঝালকাঠি", "পটুয়াখালী",
    "পিরোজপুর", "ভোলা", "বরগুনা", "হবিগঞ্জ", "মৌলভীবাজার", "সুনামগঞ্জ", "নরসিংদী",
    "গাজীপুর", "শরীয়তপুর", "নারায়ণগঞ্জ", "টাঙ্গাইল", "কিশোরগঞ্জ", "মানিকগঞ্জ",
    "মুন্সিগঞ্জ", "রাজবাড়ী", "মাদারীপুর", "গোপালগঞ্জ", "ফরিদপুর", "পঞ্চগড়", "দিনাজপুর",
    "লালমনিরহাট", "নীলফামারী", "গাইবান্ধা", "ঠাকুরগাঁও", "কুড়িগ্রাম", "শেরপুর",
    "জামালপুর", "নেত্রকোণা"
}

# Cached database entity names from core.entity_name
_DB_ENTITY_CACHE: Optional[Set[str]] = None

def load_db_entity_names(db_session=None) -> Set[str]:
    """
    Loads and caches distinct lowercased entity names from core.entity_name.
    Gracefully falls back to preloaded roots if DB is unavailable.
    """
    global _DB_ENTITY_CACHE
    if _DB_ENTITY_CACHE is not None:
        return _DB_ENTITY_CACHE

    entity_set = set(PRELOADED_ENTITY_ROOTS)
    try:
        if db_session is None:
            try:
                from backend.app.database import SessionLocal
                session = SessionLocal()
                close_after = True
            except Exception:
                session = None
                close_after = False
        else:
            session = db_session
            close_after = False

        if session:
            try:
                from sqlalchemy import text
                rows = session.execute(text("SELECT DISTINCT lower(name) FROM core.entity_name WHERE state = 'verified'")).fetchall()
                for r in rows:
                    if r[0]:
                        entity_set.add(r[0].strip())
            finally:
                if close_after:
                    session.close()
    except Exception as e:
        logger.debug(f"Could not load entities from database: {e}")

    _DB_ENTITY_CACHE = entity_set
    return _DB_ENTITY_CACHE

def is_protected_root(token: str, db_session=None) -> bool:
    """
    Checks if a token is a protected root word:
    1. Common nouns in PROTECTED_COMMON_NOUNS
    2. Any verified entity in core.entity_name (or PRELOADED_ENTITY_ROOTS)
    """
    cleaned = token.strip().lower()
    if cleaned in PROTECTED_COMMON_NOUNS:
        return True
    
    entity_cache = load_db_entity_names(db_session)
    return cleaned in entity_cache

# Suffix rules ordered to avoid truncating roots ending in 'র' (e.g. সাগরে -> সাগর, not সাগ)
INFLECTION_SUFFIXES = [
    # Plural + case compounds
    "গুলোর", "গুলির", "গুলোতে", "গুলিতে", "গুলোয়", "গুলোরে", "গুলোকে",
    # Plural markers
    "গুলো", "গুলি", "সমূহ", "বর্গ", "গণ", "দের", "দিগের",
    # Definite article + case compounds
    "টির", "টার", "টিতে", "টাতে", "টিকে", "টাকে",
    # Definite article / classifier
    "টি", "টা", "খানি", "খানা",
    # Prepositions / markers
    "থেকে", "হতে", "দিয়ে", "দ্বারা",
    # Dependent vowel combinations
    "\u09C7\u09B0",            # -ের (dependent e-kar + ra, e.g. মানুষের -> মানুষ, ঘরের -> ঘর, রংপুরের -> রংপুর)
    "\u09DF\u09C7\u09B0",      # -য়ের
    "\u09AF\u09BC\u09C7\u09B0", # -য়ের with nukta
    "য়ের", "এর",
    "তে", "কে",
    "\u09DF\u09C7",            # -য়ে
    "\u09AF\u09BC\u09C7",      # -য়ে with nukta
    "য়ে",
    "\u09C7",                 # -ে (dependent e-kar locative, e.g. সাগরে -> সাগর, জামালপুরে -> জামালপুর, সিলেটে -> সিলেট)
    "র",                      # -র (e.g. ঢাকার -> ঢাকা)
    "য়", "\u09DF", "\u09AF\u09BC" # -য় (e.g. ঢাকায় -> ঢাকা)
]

def clean_bangla_text(text: str) -> str:
    """Strip extraneous punctuation and zero-width characters."""
    if not text:
        return ""
    cleaned = text.replace('\u200c', '').replace('\u200d', '')
    cleaned = re.sub(r'[^\w\s\u0980-\u09FF]', '', cleaned)
    return cleaned.strip()

def strip_bangla_suffix(token: str, db_session=None) -> str:
    """
    Strips case inflections and plural markers from a single Bengali token.
    Returns root stem if stripped, or original token if protected by DB/common noun list.
    """
    token = token.strip()
    if len(token) < 3 or is_protected_root(token, db_session):
        return token

    for suffix in INFLECTION_SUFFIXES:
        if token.endswith(suffix):
            stem = token[:-len(suffix)]
            # Guard against over-stemming: root must be at least 2 Bangla characters
            if len(stem) >= 2 and stem not in ["", " "]:
                if stem.endswith('\u09CD'):  # Bengali virama (hasant)
                    stem = stem[:-1]
                return stem

    return token

def expand_bangla_stems(query: str, db_session=None) -> List[str]:
    """
    Takes a query string and returns an expanded list of terms including:
    1. The original clean tokens
    2. The stemmed root forms for each inflected token
    3. The full query with stems replaced (if any word was stemmed)
    """
    if not query:
        return []

    tokens = query.split()
    expanded_terms: Set[str] = set()
    stemmed_tokens = []
    has_stemmed = False

    for token in tokens:
        expanded_terms.add(token)
        stem = strip_bangla_suffix(token, db_session)
        if stem != token:
            expanded_terms.add(stem)
            stemmed_tokens.append(stem)
            has_stemmed = True
        else:
            stemmed_tokens.append(token)

    if has_stemmed:
        expanded_terms.add(" ".join(stemmed_tokens))

    return list(expanded_terms)

def stem_and_normalize_bangla(text_content: str, db_session=None) -> str:
    """
    Index-time and query-time normalizer.
    Cleans punctuation, stems tokens, and produces a normalized representation.
    Ensures symmetric indexing and search matching.
    """
    if not text_content:
        return ""
    cleaned = clean_bangla_text(text_content).lower()
    tokens = cleaned.split()
    normalized_tokens = [strip_bangla_suffix(t, db_session) for t in tokens if t]
    return " ".join(normalized_tokens)

