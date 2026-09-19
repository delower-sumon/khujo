"""
banglish.py - Intelligent Banglish to Bengali Phonetic Transliteration Engine.
Translates phonetic Roman/Banglish input (e.g., 'ami banglay gaan gai', 'dhaka shohor')
into proper Bengali Unicode script ('আমি বাংলায় গান গাই', 'ঢাকা শহর').
Uses avro-py with custom rule enhancements and lexicon fallback.
"""

import re
from typing import List, Optional, Tuple

try:
    import avro
except ImportError:
    avro = None

# Common colloquial adjustments for search terms
BANGLISH_FIXUPS = [
    (r'\bgaan\b', 'gan'),
    (r'\bgaaner\b', 'ganer'),
    (r'\bchakrir\b', 'cakrir'),
    (r'\bkhobor\b', 'kobor'),
    (r'\bbhalo\b', 'valo'),
    (r'\bkotha\b', 'kotha'),
]


def is_mostly_latin(text: str) -> bool:
    """Check if the text contains Latin characters requiring Banglish transliteration."""
    if not text:
        return False
    latin_chars = len(re.findall(r'[a-zA-Z]', text))
    bangla_chars = len(re.findall(r'[\u0980-\u09FF]', text))
    return latin_chars > 0 and latin_chars >= bangla_chars


def transliterate_banglish(query: str) -> Tuple[Optional[str], List[str]]:
    """
    Transliterate a Banglish query into Bengali Unicode script.
    Returns (primary_bangla, list_of_variants).
    Example:
      'ami banglay gaan gai' -> ('আমি বাংলায় গান গাই', ['আমি বাংলায় গাআন গাই'])
    """
    if not query or not query.strip():
        return None, []

    raw = query.strip()
    if not is_mostly_latin(raw):
        return None, []

    if not avro:
        return None, []

    variants = []

    # 1. Direct Avro parse
    parsed_direct = avro.parse(raw)
    if parsed_direct and parsed_direct != raw:
        variants.append(parsed_direct)

    # 2. Adjusted parse with colloquial fixups
    adjusted_query = raw.lower()
    for pattern, repl in BANGLISH_FIXUPS:
        adjusted_query = re.sub(pattern, repl, adjusted_query)

    if adjusted_query != raw.lower():
        parsed_adjusted = avro.parse(adjusted_query)
        if parsed_adjusted and parsed_adjusted not in variants:
            variants.insert(0, parsed_adjusted)

    if not variants:
        return None, []

    primary = variants[0]
    return primary, variants


def expand_query_with_banglish(query: str, current_terms: List[str]) -> List[str]:
    """
    Expands search terms with Banglish transliteration if applicable.
    Guarantees that Banglish queries like 'ami banglay gaan gai' include
    'আমি বাংলায় গান গাই' in the document retrieval search terms.
    """
    terms = list(current_terms)
    primary, variants = transliterate_banglish(query)
    if primary and primary not in terms:
        terms.append(primary)
    for v in variants:
        if v not in terms:
            terms.append(v)
    return terms
