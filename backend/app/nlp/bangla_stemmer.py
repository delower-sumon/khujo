"""
Khujo NLP — Bangla Suffix Stripper & Morphological Normalizer
Remediates Defect D5 from khujo_code_audit.md.

Solves the asymmetric inflection problem where inflected forms
(e.g., 'ঢাকার', 'ঢাকায়', 'ঢাকাটি') fail silently against root entities ('ঢাকা').
"""

import re
from typing import Set, List, Optional

# Protected Bangla root words that end in characters common to suffixes (e.g. র, য়, ট, ইত্যাদি)
# These MUST NOT be stripped.
PROTECTED_ROOTS: Set[str] = {
    # Common geographical & administrative names
    "ঢাকা", "দিনাজপুর", "রংপুর", "শেরপুর", "মাদারীপুর", "পিরোজপুর", "মেহেরপুর", "ফরিদপুর",
    "চাঁদপুর", "জয়পুরহাট", "বান্দরবান", "কক্সবাজার", "ব্রাহ্মণবাড়িয়া", "ময়মনসিংহ",
    "চট্টগ্রাম", "রাজশাহী", "খুলনা", "বরিশাল", "সিলেট", "কুমিল্লা", "গাজীপুর",
    # Common nouns ending in র, য়, ইত্যাদি
    "শহর", "খবর", "খাবার", "সুন্দর", "উত্তর", "অন্তর", "নজর", "পাহাড়", "সাগর", "সমুদ্র",
    "সময়", "বিষয়", "আশয়", "বিশ্ববিদ্যালয়", "মহাবিদ্যালয়", "বিদ্যালয়", "কার্যালয়",
    "উপায়", "সহায়", "নিয়ম", "বাজার", "দরবার", "সরকার", "দরকার", "ঘর", "দ্বার",
    "অধিকার", "ব্যবহার", "বিচার", "প্রচার", "আকার", "প্রকার",
    "পানি", "মাটি", "বাড়ি", "গাড়ি", "দাড়ি", "নারী", "ভারী", "দেরি", "পাখি", "হাতি"
}

# Suffix rules ordered by length (longest to shortest) to prevent partial sub-stripping
INFLECTION_SUFFIXES = [
    # Plural + case compounds
    "গুলোর", "গুলির", "গুলোতে", "গুলিতে", "গুলোয়", "গুলোরে", "গুলোকে",
    # Plural markers
    "গুলো", "গুলি", "সমূহ", "বর্গ", "গণ", "দের", "দিগের",
    # Definite article + case compounds
    "টির", "টার", "টিতে", "টাতে", "টিকে", "টাকে",
    # Definite article / classifier
    "টি", "টা", "খানি", "খানা",
    # Case markers (locative, possessive, dative)
    "থেকে", "হতে", "দিয়ে", "দ্বারা",
    # Dependent vowel combinations (cons + e-kar + ra / e-kar locative)
    "\u09C7\u09B0",            # -ের (dependent e-kar + ra, e.g. মানুষের -> মানুষ)
    "\u09DF\u09C7\u09B0",      # -য়ের
    "\u09AF\u09BC\u09C7\u09B0", # -য়ের with nukta
    "য়ের", "এর",
    "তে", "কে", "রে",
    "\u09DF\u09C7",            # -য়ে
    "\u09AF\u09BC\u09C7",      # -য়ে with nukta
    "য়ে",
    "\u09C7",                 # -এ (dependent e-kar, e.g. সিলেটে -> সিলেট)
    "র",                      # -র (e.g. ঢাকার -> ঢাকা)
    "য়", "\u09DF", "\u09AF\u09BC" # -য় (e.g. ঢাকায় -> ঢাকা)
]

def clean_bangla_text(text: str) -> str:
    """Strip extraneous punctuation and zero-width characters."""
    if not text:
        return ""
    # Remove Zero-Width Non-Joiner (ZWNJ \u200C) and Joiner (ZWJ \u200D) if isolated
    cleaned = text.replace('\u200c', '').replace('\u200d', '')
    # Strip non-alphanumeric except space and Bangla unicode range
    cleaned = re.sub(r'[^\w\s\u0980-\u09FF]', '', cleaned)
    return cleaned.strip()

def strip_bangla_suffix(token: str) -> str:
    """
    Strips case inflections and plural markers from a single Bengali token.
    Returns the root stem if stripped, or original token if protected/too short.
    """
    token = token.strip()
    if len(token) < 3 or token in PROTECTED_ROOTS:
        return token

    for suffix in INFLECTION_SUFFIXES:
        if token.endswith(suffix):
            stem = token[:-len(suffix)]
            # Guard against over-stemming: root must be at least 2 Bangla characters
            if len(stem) >= 2 and stem not in ["", " "]:
                # Avoid leaving dangling hasant or broken vowel sign
                if stem.endswith('\u09CD'): # Bengali sign virama (hasant)
                    stem = stem[:-1]
                return stem

    return token

def expand_bangla_stems(query: str) -> List[str]:
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
        stem = strip_bangla_suffix(token)
        if stem != token:
            expanded_terms.add(stem)
            stemmed_tokens.append(stem)
            has_stemmed = True
        else:
            stemmed_tokens.append(token)

    if has_stemmed:
        expanded_terms.add(" ".join(stemmed_tokens))

    return list(expanded_terms)
