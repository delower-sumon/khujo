#!/usr/bin/env python3
"""
seed_lexicon.py - High-speed Ingestion of Bengali Dictionary & Transliteration Layer.
Seeds core.bangla_lexicon directly from BengaliDictionary.json with:
- Bengali word (bn_word)
- English equivalent (en_word)
- Pronunciation & Roman Transliterations (transliterations)
- Bengali and English synonyms
- Example usage sentences
"""

import os
import sys
import json
import logging
import re
import unicodedata
from pathlib import Path
from typing import List, Dict, Any, Tuple

import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

# Ensure UTF-8 output on Windows
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Load environment
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / "backend" / ".env")
load_dotenv(BASE_DIR / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("seed_lexicon")

DB_URL = os.getenv("DATABASE_URL")
DATA_FILE = BASE_DIR / "crawler" / "data" / "BengaliDictionary.json"


def strip_accents(text: str) -> str:
    """Strip accents from romanized transliteration (e.g. Gājara -> gajara)."""
    if not text:
        return ""
    nfkd = unicodedata.normalize('NFKD', text)
    stripped = "".join([c for c in nfkd if not unicodedata.combining(c)])
    return stripped.lower().strip()


def normalize_bn(text: str) -> str:
    """Normalize Bengali text."""
    if not text:
        return ""
    # Strip zero-width chars and extra whitespace
    t = text.replace('\u200c', '').replace('\u200d', '').replace('\ufeff', '')
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def generate_transliterations(bn_word: str, en_word: str, roman_pron: str) -> List[str]:
    """Generate search-friendly transliterations and roman tokens."""
    results = set()
    if roman_pron:
        clean_roman = strip_accents(roman_pron)
        if clean_roman:
            results.add(clean_roman)
            # Remove trailing 'a' if common in Indic romanization (gajara -> gajar)
            if clean_roman.endswith('a') and len(clean_roman) > 3:
                results.add(clean_roman[:-1])
    if en_word:
        clean_en = en_word.lower().strip()
        if clean_en and re.match(r'^[a-zA-Z0-9\s-]+$', clean_en):
            results.add(clean_en)
    return list(results)


def seed_dictionary_direct(batch_size: int = 500) -> None:
    """Ingest BengaliDictionary.json in fast batches into core.bangla_lexicon."""
    if not DB_URL:
        log.error("DATABASE_URL not found in environment!")
        sys.exit(1)

    if not DATA_FILE.exists():
        log.error(f"Dictionary file not found at {DATA_FILE}")
        sys.exit(1)

    log.info(f"Loading dictionary from {DATA_FILE}...")
    with open(DATA_FILE, "r", encoding="utf-8-sig") as f:
        data = json.load(f)

    if isinstance(data, dict):
        items = list(data.values())
    else:
        items = data

    total_items = len(items)
    log.info(f"Loaded {total_items:,} items. Connecting to Neon DB...")

    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    insert_sql = """
        INSERT INTO core.bangla_lexicon (
            bn_word, en_word, normalised_bn, pos, ipa_pron, roman_pron,
            transliterations, bn_synonyms, en_synonyms, usage_sentences,
            source, enrichment_state
        ) VALUES %s
        ON CONFLICT (bn_word) DO UPDATE SET
            en_word = EXCLUDED.en_word,
            normalised_bn = EXCLUDED.normalised_bn,
            ipa_pron = COALESCE(EXCLUDED.ipa_pron, core.bangla_lexicon.ipa_pron),
            roman_pron = COALESCE(EXCLUDED.roman_pron, core.bangla_lexicon.roman_pron),
            transliterations = (
                SELECT array_agg(DISTINCT x)
                FROM unnest(core.bangla_lexicon.transliterations || EXCLUDED.transliterations) t(x)
            ),
            bn_synonyms = EXCLUDED.bn_synonyms,
            en_synonyms = EXCLUDED.en_synonyms,
            usage_sentences = EXCLUDED.usage_sentences,
            updated_at = now()
    """

    inserted_count = 0
    batch_records = {}

    for idx, item in enumerate(items, 1):
        bn_word = normalize_bn(item.get("bn", ""))
        if not bn_word:
            continue

        en_word = (item.get("en") or "").strip()
        pron = item.get("pron") or ["", ""]
        ipa_pron = pron[0] if len(pron) > 0 and pron[0] else None
        roman_pron = pron[1] if len(pron) > 1 and pron[1] else None

        transliterations = generate_transliterations(bn_word, en_word, roman_pron or "")
        bn_syns = item.get("bn_syns") or []
        en_syns = item.get("en_syns") or []
        sents = (item.get("sents") or [])[:5]

        # Deduplicate within batch
        if bn_word in batch_records:
            prev = batch_records[bn_word]
            # Merge transliterations and syns
            merged_trans = list(set(prev[6] + transliterations))
            merged_bn_syns = list(set(prev[7] + bn_syns))
            merged_en_syns = list(set(prev[8] + en_syns))
            batch_records[bn_word] = (
                bn_word,
                prev[1] or en_word or None,
                bn_word.lower(),
                None,
                prev[4] or ipa_pron,
                prev[5] or roman_pron,
                merged_trans,
                merged_bn_syns,
                merged_en_syns,
                prev[9] or sents,
                "minhaskamal",
                "raw"
            )
        else:
            batch_records[bn_word] = (
                bn_word,
                en_word or None,
                bn_word.lower(),
                None,  # pos
                ipa_pron,
                roman_pron,
                transliterations,
                bn_syns,
                en_syns,
                sents,
                "minhaskamal",
                "raw"
            )

        if len(batch_records) >= batch_size:
            records = list(batch_records.values())
            execute_values(cur, insert_sql, records, page_size=batch_size)
            conn.commit()
            inserted_count += len(records)
            log.info(f"Progress: {inserted_count:,} words committed ({idx*100//total_items}% of file)")
            batch_records = {}

    if batch_records:
        records = list(batch_records.values())
        execute_values(cur, insert_sql, records, page_size=batch_size)
        conn.commit()
        inserted_count += len(records)

    cur.close()
    conn.close()
    log.info(f"[SUCCESS] Finished seeding! Total unique words seeded: {inserted_count:,}")


if __name__ == "__main__":
    seed_dictionary_direct()
