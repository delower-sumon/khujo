#!/usr/bin/env python3
"""
expand_lexicon.py - Phase 2: Expand Bangla Lexicon to 1,50,000 Words
======================================================================
Multi-source pipeline. Each source funnels into a single quality-gated
upsert function. Sources run sequentially; progress logged per source.

Sources (in order):
  1. lexicon_preview.csv        - local,  ~14K net-new words, full schema
  2. Wiktionary Bangla XML dump - remote, 35-50K words with bn_definitions
  3. CC-100 Bengali wordlist    - remote, 50K+ high-freq real Bangla words
  4. Bengali Wikipedia titles   - remote, 20K+ real Bangla words from titles

Quality gates (applied to every source before DB insert):
  - Must contain at least one Bangla Unicode character (U+0980-U+09FF)
  - len(bn_word) >= 2
  - Strip HTML tags from all text fields
  - Pipe-split arrays ("|" separator) -> Python list -> Postgres TEXT[]
  - ON CONFLICT (bn_word) DO UPDATE: merge arrays, prefer non-null scalars

Run all:     python crawler/lexicon/expand_lexicon.py
Run subset:  python crawler/lexicon/expand_lexicon.py --sources csv,wiktionary
Log file:    crawler/logs/phase2_expand_lexicon.log
"""

import os
import sys
import csv
import re
import bz2
import time
import logging
import unicodedata
import argparse
from pathlib import Path
from typing import List, Dict, Optional, Iterator, Tuple
from xml.etree import ElementTree as ET

import requests
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

# -- Encoding fix for Windows console ----------------------------------------
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# -- Paths & env -------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / "backend" / ".env")
load_dotenv(BASE_DIR / ".env")

LOG_DIR = BASE_DIR / "crawler" / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_DIR / "phase2_expand_lexicon.log", encoding="utf-8"),
    ]
)
log = logging.getLogger("expand_lexicon")

DB_URL = os.getenv("DATABASE_URL")
BATCH_SIZE = 500
BANGLA_RE = re.compile(r"[\u0980-\u09FF]")
HTML_TAG_RE = re.compile(r"<[^>]+>")

# -- Source file paths -------------------------------------------------------
LEXICON_CSV    = BASE_DIR / "crawler" / "data" / "lexicon_preview.csv"
WIKT_DUMP_URL  = "https://dumps.wikimedia.org/bnwiktionary/latest/bnwiktionary-latest-pages-articles.xml.bz2"
WIKT_DUMP_PATH = BASE_DIR / "crawler" / "data" / "bnwiktionary_dump.xml.bz2"
BWIKI_API      = "https://bn.wikipedia.org/w/api.php"

CC100_WORDLIST_URLS = [
    # tahmid02016 bangla wordlist — verified 200 OK, 454K lines of real Bangla words
    "https://raw.githubusercontent.com/tahmid02016/bangla-wordlist/master/words.txt",
    # BNLP sagorbrur (alternate filename)
    "https://raw.githubusercontent.com/sagorbrur/bnlp/master/bnlp/corpus/data/bangla_word.txt",
    # HuggingFace BNLP model card word data
    "https://huggingface.co/sagorsarker/bangla-bert-base/resolve/main/vocab.txt",
]


# ============================================================================
# QUALITY FILTERS
# ============================================================================

def strip_html(text: str) -> str:
    """Remove HTML tags like <b>word</b> -> word."""
    return HTML_TAG_RE.sub("", text).strip() if text else ""


def split_pipe(value: str) -> List[str]:
    """Split pipe-separated string ('a|b|c') into list."""
    if not value:
        return []
    return [v.strip() for v in value.split("|") if v.strip()]


def normalize_bn(text: str) -> str:
    """Normalize Bangla text: strip zero-width chars, collapse whitespace."""
    if not text:
        return ""
    t = text.replace("\u200c", "").replace("\u200d", "").replace("\ufeff", "")
    t = re.sub(r"\s+", " ", t).strip()
    return t


def is_valid_bn_word(word: str) -> bool:
    """Accept only words with >= 1 Bangla char and length >= 2."""
    if not word or len(word) < 2:
        return False
    return bool(BANGLA_RE.search(word))


def strip_accents(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().strip()


def build_transliterations(bn_word: str, en_word: str, roman_pron: str) -> List[str]:
    results = set()
    if roman_pron:
        clean = strip_accents(roman_pron)
        if clean:
            results.add(clean)
            if clean.endswith("a") and len(clean) > 3:
                results.add(clean[:-1])
    if en_word:
        en = en_word.lower().strip()
        if en and re.match(r"^[a-zA-Z0-9\s\-]+$", en):
            results.add(en)
    return list(results)


# ============================================================================
# DATABASE UPSERT - single shared function for all sources
# ============================================================================

UPSERT_SQL = """
    INSERT INTO core.bangla_lexicon (
        bn_word, en_word, normalised_bn, pos, ipa_pron, roman_pron,
        bn_definition, transliterations, bn_synonyms, en_synonyms,
        bn_antonyms, usage_sentences, source, enrichment_state
    ) VALUES %s
    ON CONFLICT (bn_word) DO UPDATE SET
        en_word       = COALESCE(EXCLUDED.en_word,       core.bangla_lexicon.en_word),
        pos           = COALESCE(EXCLUDED.pos,           core.bangla_lexicon.pos),
        ipa_pron      = COALESCE(EXCLUDED.ipa_pron,      core.bangla_lexicon.ipa_pron),
        roman_pron    = COALESCE(EXCLUDED.roman_pron,    core.bangla_lexicon.roman_pron),
        bn_definition = COALESCE(EXCLUDED.bn_definition, core.bangla_lexicon.bn_definition),
        transliterations = (
            SELECT array_agg(DISTINCT x)
            FROM unnest(core.bangla_lexicon.transliterations || EXCLUDED.transliterations) t(x)
        ),
        bn_synonyms = (
            SELECT array_agg(DISTINCT x)
            FROM unnest(core.bangla_lexicon.bn_synonyms || EXCLUDED.bn_synonyms) t(x)
        ),
        en_synonyms = (
            SELECT array_agg(DISTINCT x)
            FROM unnest(core.bangla_lexicon.en_synonyms || EXCLUDED.en_synonyms) t(x)
        ),
        bn_antonyms = (
            SELECT array_agg(DISTINCT x)
            FROM unnest(core.bangla_lexicon.bn_antonyms || EXCLUDED.bn_antonyms) t(x)
        ),
        usage_sentences = CASE
            WHEN array_length(core.bangla_lexicon.usage_sentences, 1) IS NULL
            THEN EXCLUDED.usage_sentences
            ELSE core.bangla_lexicon.usage_sentences
        END,
        updated_at = now()
"""


def flush_batch(
    conn, cur, batch: List[tuple], source_tag: str, total_so_far: int
) -> Tuple[int, List[tuple]]:
    if not batch:
        return total_so_far, []
    try:
        execute_values(cur, UPSERT_SQL, batch, page_size=BATCH_SIZE)
        conn.commit()
        total_so_far += len(batch)
        log.info(f"[{source_tag}] Committed {total_so_far:,} words so far...")
    except Exception as e:
        conn.rollback()
        log.error(f"[{source_tag}] Batch error: {e}")
        raise
    return total_so_far, []


# ============================================================================
# SOURCE 1 - lexicon_preview.csv (local, same schema as DB)
# ============================================================================

def seed_from_csv(conn, cur) -> int:
    """
    Import crawler/data/lexicon_preview.csv.
    Headers: bn_word, en_word, normalised_bn, pos, ipa_pron, roman_pron,
             bn_definition, bn_synonyms, en_synonyms, bn_antonyms, usage_sentences
    Pipe-separated arrays. HTML tags in sentence fields.
    """
    source_tag = "lexicon_csv"
    if not LEXICON_CSV.exists():
        log.warning(f"[{source_tag}] Not found: {LEXICON_CSV}")
        return 0

    log.info(f"[{source_tag}] Reading {LEXICON_CSV}...")
    batch: List[tuple] = []
    total = 0
    skipped = 0
    seen: set = set()

    with open(LEXICON_CSV, encoding="utf-8-sig", errors="replace", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            bn_word = normalize_bn(row.get("bn_word", ""))
            if not is_valid_bn_word(bn_word):
                skipped += 1
                continue
            if bn_word in seen:
                continue
            seen.add(bn_word)

            en_word    = strip_html(row.get("en_word", "")).strip() or None
            pos        = row.get("pos", "").strip() or None
            ipa_pron   = row.get("ipa_pron", "").strip() or None
            roman_pron = row.get("roman_pron", "").strip() or None
            bn_def     = normalize_bn(strip_html(row.get("bn_definition", ""))) or None
            bn_syns    = [normalize_bn(s) for s in split_pipe(row.get("bn_synonyms", "")) if is_valid_bn_word(normalize_bn(s))]
            en_syns    = [s.strip() for s in split_pipe(row.get("en_synonyms", "")) if s.strip()]
            bn_ants    = [normalize_bn(s) for s in split_pipe(row.get("bn_antonyms", "")) if is_valid_bn_word(normalize_bn(s))]
            sents      = [strip_html(s) for s in split_pipe(row.get("usage_sentences", "")) if s.strip()][:5]
            trans      = build_transliterations(bn_word, en_word or "", roman_pron or "")

            batch.append((
                bn_word, en_word, bn_word.lower(), pos, ipa_pron, roman_pron,
                bn_def, trans, bn_syns, en_syns, bn_ants, sents,
                "lexicon_preview_csv", "raw"
            ))
            if len(batch) >= BATCH_SIZE:
                total, batch = flush_batch(conn, cur, batch, source_tag, total)

    if batch:
        total, batch = flush_batch(conn, cur, batch, source_tag, total)

    log.info(f"[{source_tag}] Done. Processed: {total:,} | Skipped: {skipped:,}")
    return total


# ============================================================================
# SOURCE 2 - Wiktionary Bangla (bnwiktionary) XML Dump
# ============================================================================

# Wikimedia requires a proper User-Agent or returns 403
WIKT_HEADERS = {
    "User-Agent": "Khujo/1.0 (bangla-search-engine; https://khujo.com; contact@khujo.com)"
}


def download_wiktionary_dump() -> bool:
    """Download bnwiktionary bz2 XML dump if not already cached locally."""
    if WIKT_DUMP_PATH.exists() and WIKT_DUMP_PATH.stat().st_size > 1_000_000:
        log.info(f"[wiktionary] Using cached dump ({WIKT_DUMP_PATH.stat().st_size // (1024*1024)}MB)")
        return True

    log.info(f"[wiktionary] Downloading from {WIKT_DUMP_URL}...")
    try:
        with requests.get(WIKT_DUMP_URL, stream=True, timeout=300, headers=WIKT_HEADERS) as r:
            r.raise_for_status()
            total_size = int(r.headers.get("content-length", 0))
            downloaded = 0
            with open(WIKT_DUMP_PATH, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 1024):  # 1MB chunks
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total_size and downloaded % (10 * 1024 * 1024) < 1024 * 1024:
                        pct = downloaded * 100 // total_size
                        log.info(f"[wiktionary] {downloaded//(1024*1024)}MB / {total_size//(1024*1024)}MB ({pct}%)")
        log.info(f"[wiktionary] Download complete.")
        return True
    except Exception as e:
        log.error(f"[wiktionary] Download failed: {e}")
        return False


WIKT_TEMPLATE_RE = re.compile(r"\{\{[^}]+\}\}")
WIKT_LINK_RE     = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
WIKT_HEADER_RE   = re.compile(r"^==+[^=]+==+$", re.MULTILINE)
WIKT_BULLET_RE   = re.compile(r"^[*#:;]+\s*", re.MULTILINE)

SKIP_PREFIXES = (
    "উইকিপিডিয়া:", "টেমপ্লেট:", "সাহায্য:", "বিশেষ:", "চিত্র:", "বিষয়শ্রেণী:",
    "Wikipedia:", "Template:", "Help:", "Special:", "File:", "Category:",
    "MediaWiki:", "Module:", "Wiktionary:",
)


def clean_wikt_markup(raw: str) -> str:
    """Strip wiki markup to plain text for definition extraction."""
    t = WIKT_TEMPLATE_RE.sub("", raw)
    t = WIKT_LINK_RE.sub(r"\1", t)
    t = WIKT_HEADER_RE.sub("", t)
    t = WIKT_BULLET_RE.sub("", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t[:500] if t else ""


def parse_wiktionary_dump(dump_path: Path) -> Iterator[Dict]:
    """
    Stream-parse bz2 XML. Yields {bn_word, bn_definition} dicts.
    Only yields pages with Bangla chars in title. Skips all namespace pages.
    Memory-safe: clears each elem after processing (iterparse pattern).
    """
    log.info("[wiktionary] Parsing XML dump (streaming)...")
    count = 0
    try:
        with bz2.open(dump_path, "rb") as raw_f:
            context = ET.iterparse(raw_f, events=("end",))
            title = None
            for _event, elem in context:
                tag = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag

                if tag == "title":
                    title = (elem.text or "").strip()

                elif tag == "text" and title:
                    # Skip non-article namespaces
                    if any(title.startswith(p) for p in SKIP_PREFIXES):
                        elem.clear()
                        title = None
                        continue
                    # Only Bangla-titled pages
                    if not BANGLA_RE.search(title):
                        elem.clear()
                        title = None
                        continue

                    raw_text = elem.text or ""
                    bn_def = None
                    for line in raw_text.splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        cleaned = clean_wikt_markup(line)
                        if cleaned and BANGLA_RE.search(cleaned) and len(cleaned) > 5:
                            bn_def = cleaned
                            break

                    count += 1
                    if count % 5000 == 0:
                        log.info(f"[wiktionary] Parsed {count:,} entries so far...")

                    yield {"bn_word": normalize_bn(title), "bn_definition": bn_def}
                    elem.clear()
                    title = None

    except Exception as e:
        log.error(f"[wiktionary] Parse error at entry {count}: {e}")


def seed_from_wiktionary(conn, cur) -> int:
    source_tag = "wiktionary"
    if not download_wiktionary_dump():
        log.warning(f"[{source_tag}] Dump unavailable — skipping.")
        return 0

    batch: List[tuple] = []
    total = 0
    skipped = 0
    seen: set = set()  # Dedup within + across batches (Wiktionary XML has duplicates)

    for entry in parse_wiktionary_dump(WIKT_DUMP_PATH):
        bn_word = entry["bn_word"]
        if not is_valid_bn_word(bn_word) or bn_word in seen:
            skipped += 1
            continue
        seen.add(bn_word)

        bn_def = entry.get("bn_definition")
        trans  = build_transliterations(bn_word, "", "")
        state  = "wiktionary_fetched" if bn_def else "raw"

        batch.append((
            bn_word, None, bn_word.lower(), None, None, None,
            bn_def, trans, [], [], [], [],
            "bn_wiktionary", state
        ))
        if len(batch) >= BATCH_SIZE:
            total, batch = flush_batch(conn, cur, batch, source_tag, total)

    if batch:
        total, batch = flush_batch(conn, cur, batch, source_tag, total)

    log.info(f"[{source_tag}] Done. Imported: {total:,} | Skipped (invalid): {skipped:,}")
    return total


# ============================================================================
# SOURCE 3 - CC-100 / Bengali Public Wordlists
# ============================================================================

def seed_from_wordlists(conn, cur) -> int:
    """
    Try each URL in CC100_WORDLIST_URLS, use first successful one.
    Handles both plain-word and 'word<TAB>frequency' formats.
    """
    source_tag = "bengali_wordlist"
    content = None

    for url in CC100_WORDLIST_URLS:
        log.info(f"[{source_tag}] Trying: {url}")
        try:
            r = requests.get(url, timeout=30, headers={"User-Agent": "Khujo/1.0"})
            if r.status_code == 200 and len(r.content) > 1000:
                content = r.text
                log.info(f"[{source_tag}] Success: {len(r.content)//1024}KB from {url}")
                break
            log.warning(f"[{source_tag}] HTTP {r.status_code} — trying next...")
        except Exception as e:
            log.warning(f"[{source_tag}] Failed ({url}): {e}")
        time.sleep(1)

    if not content:
        log.warning(f"[{source_tag}] All sources failed — skipping.")
        return 0

    batch: List[tuple] = []
    total = 0
    skipped = 0
    seen: set = set()

    for line in content.splitlines():
        bn_word = normalize_bn(line.strip())
        if not bn_word:
            continue

        # Handle "word\tfrequency" or "word frequency" formats
        if "\t" in bn_word:
            bn_word = bn_word.split("\t")[0].strip()
        parts = bn_word.split()
        if len(parts) == 2 and parts[1].isdigit():
            bn_word = parts[0]
        # Take only single-token words (avoid phrases from this source)
        if " " in bn_word:
            bn_word = bn_word.split()[0]

        bn_word = normalize_bn(bn_word)
        if not is_valid_bn_word(bn_word) or bn_word in seen:
            skipped += 1
            continue
        seen.add(bn_word)

        trans = build_transliterations(bn_word, "", "")
        batch.append((
            bn_word, None, bn_word.lower(), None, None, None,
            None, trans, [], [], [], [],
            "cc100_wordlist", "raw"
        ))
        if len(batch) >= BATCH_SIZE:
            total, batch = flush_batch(conn, cur, batch, source_tag, total)

    if batch:
        total, batch = flush_batch(conn, cur, batch, source_tag, total)

    log.info(f"[{source_tag}] Done. Imported: {total:,} | Skipped: {skipped:,}")
    return total


# ============================================================================
# SOURCE 4 - Bengali Wikipedia: all article titles -> tokenized words
# ============================================================================

def fetch_bwiki_titles() -> Iterator[str]:
    """
    Paginate bn.wikipedia.org allpages API (500 titles per request).
    Polite: 0.5s delay between requests (2 req/sec max).
    """
    params: Dict = {
        "action": "query",
        "list": "allpages",
        "aplimit": "500",
        "apnamespace": "0",         # main article namespace only
        "apfilterredir": "nonredirects",
        "format": "json",
    }
    headers = {"User-Agent": "Khujo/1.0 (bangla-search-engine; contact@khujo.com)"}
    page_count = 0

    while True:
        try:
            r = requests.get(BWIKI_API, params=params, headers=headers, timeout=30)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            log.warning(f"[bwiki] API error: {e} — stopping pagination")
            break

        pages = data.get("query", {}).get("allpages", [])
        for page in pages:
            yield page.get("title", "")

        cont = data.get("continue", {})
        if "apcontinue" not in cont:
            break  # No more pages

        params["apcontinue"] = cont["apcontinue"]
        page_count += 1
        if page_count % 20 == 0:
            log.info(f"[bwiki] Paginated through {page_count * 500:,} titles...")
        time.sleep(0.5)


def tokenize_bn_title(title: str) -> List[str]:
    """
    'ঢাকা জেলার উপজেলাসমূহ' -> ['ঢাকা', 'জেলার', 'উপজেলাসমূহ']
    Splits on spaces, punctuation, brackets. Keeps only valid Bangla tokens.
    """
    parts = re.split(r"[\s,\-\u2013\u2014/()\[\]]+", title)
    return [normalize_bn(p) for p in parts if is_valid_bn_word(normalize_bn(p))]


def seed_from_bwiki(conn, cur) -> int:
    source_tag = "bn_wikipedia"
    log.info(f"[{source_tag}] Fetching all Bengali Wikipedia article titles...")

    batch: List[tuple] = []
    total = 0
    seen: set = set()

    for title in fetch_bwiki_titles():
        for bn_word in tokenize_bn_title(title):
            if bn_word in seen:
                continue
            seen.add(bn_word)

            trans = build_transliterations(bn_word, "", "")
            batch.append((
                bn_word, None, bn_word.lower(), None, None, None,
                None, trans, [], [], [], [],
                "bn_wikipedia_titles", "raw"
            ))
            if len(batch) >= BATCH_SIZE:
                total, batch = flush_batch(conn, cur, batch, source_tag, total)

    if batch:
        total, batch = flush_batch(conn, cur, batch, source_tag, total)

    log.info(f"[{source_tag}] Done. Unique words extracted: {total:,}")
    return total


# ============================================================================
# DB STATS REPORT
# ============================================================================

def print_db_stats(cur, label: str):
    cur.execute("SELECT COUNT(*) FROM core.bangla_lexicon")
    total = cur.fetchone()[0]
    if total == 0:
        log.info(f"[STATS] {label}: 0 words in DB")
        return

    cur.execute("SELECT COUNT(*) FROM core.bangla_lexicon WHERE ipa_pron IS NOT NULL")
    with_ipa = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM core.bangla_lexicon WHERE bn_definition IS NOT NULL")
    with_def = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM core.bangla_lexicon WHERE array_length(bn_synonyms,1) > 0")
    with_syns = cur.fetchone()[0]
    cur.execute("SELECT source, COUNT(*) FROM core.bangla_lexicon GROUP BY source ORDER BY COUNT(*) DESC")
    by_source = cur.fetchall()

    source_lines = "\n".join(f"    {src}: {cnt:,}" for src, cnt in by_source)
    gap = max(0, 150000 - total)
    log.info(
        f"\n{'='*60}\n"
        f"  {label}\n"
        f"  Total words       : {total:>10,}\n"
        f"  With IPA pron     : {with_ipa:>10,}  ({with_ipa*100//total}%)\n"
        f"  With bn_definition: {with_def:>10,}  ({with_def*100//total}%)\n"
        f"  With bn_synonyms  : {with_syns:>10,}  ({with_syns*100//total}%)\n"
        f"  Gap to 1,50,000   : {gap:>10,}  words remaining\n"
        f"  By source:\n{source_lines}\n"
        f"{'='*60}"
    )


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Phase 2: Expand Bangla Lexicon to 1.5 Lakh")
    parser.add_argument(
        "--sources",
        default="all",
        help="Comma-separated: csv,wiktionary,wordlist,bwiki  (default: all)"
    )
    args = parser.parse_args()

    if args.sources.strip().lower() == "all":
        sources = {"csv", "wiktionary", "wordlist", "bwiki"}
    else:
        sources = {s.strip().lower() for s in args.sources.split(",")}

    if not DB_URL:
        log.error("DATABASE_URL not set in environment!")
        sys.exit(1)

    log.info("Phase 2 starting. Connecting to database...")
    conn = psycopg2.connect(DB_URL)
    conn.autocommit = False
    cur = conn.cursor()

    print_db_stats(cur, "BEFORE Phase 2")

    grand_total = 0
    t_start = time.time()

    # -- Source 1: Local CSV -------------------------------------------------
    if "csv" in sources:
        log.info("\n>>> SOURCE 1: lexicon_preview.csv (local)")
        grand_total += seed_from_csv(conn, cur)
        print_db_stats(cur, "After Source 1: lexicon_preview.csv")

    # -- Source 2: Wiktionary Bangla XML dump --------------------------------
    if "wiktionary" in sources:
        log.info("\n>>> SOURCE 2: Wiktionary Bangla XML Dump")
        grand_total += seed_from_wiktionary(conn, cur)
        print_db_stats(cur, "After Source 2: Wiktionary Bangla")

    # -- Source 3: Bengali public wordlists ----------------------------------
    if "wordlist" in sources:
        log.info("\n>>> SOURCE 3: Bengali Public Wordlists (CC-100 / BNLP)")
        grand_total += seed_from_wordlists(conn, cur)
        print_db_stats(cur, "After Source 3: Bengali Wordlists")

    # -- Source 4: Bengali Wikipedia titles ----------------------------------
    if "bwiki" in sources:
        log.info("\n>>> SOURCE 4: Bengali Wikipedia Article Titles")
        grand_total += seed_from_bwiki(conn, cur)
        print_db_stats(cur, "After Source 4: Bengali Wikipedia")

    elapsed = time.time() - t_start
    log.info(f"\n[PHASE 2 COMPLETE] Rows processed: {grand_total:,} | Time: {elapsed/60:.1f} min")
    print_db_stats(cur, "FINAL STATE — Phase 2 Complete")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
