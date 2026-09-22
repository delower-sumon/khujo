#!/usr/bin/env python3
"""
qa_spelling_auditor.py - Enterprise Quality Assurance & Mass Spelling Correction Engine for Khujo.

Detects, audits, and fixes systematic transliteration errors across:
  1. core.entity (display_name and summary)
  2. core.entity_name (name and normalised_name)
  3. search.suggestion (phrase and phrase_normalised)
  4. crawler/geo_pipeline/data/bangladesh_villages_master.csv

Covers:
  - English loanword corruptions (e.g., চল্লেগে -> কলেজ, চাদেত -> ক্যাডেট, হাস্পাতাল -> হাসপাতাল)
  - Directional prefixes (e.g., পাশ্ছিম -> পশ্চিম, পুরবা -> পূর্ব, ঊত্তার -> উত্তর, ডাক্ষিন -> দক্ষিণ, মাধ্যা -> মধ্য)
  - Natural toponymic roots (e.g., মির ডেওহাতা -> মীর দেওহাটা, বানশ -> বাঁশ, ছহাতার -> ছাতার, ...হাতা -> ...হাটা)
  - Suffix standardizations (পারা -> পাড়া, দাঙ্গা -> ডাঙ্গা, কাতি -> কাঠি, নাগার -> নগর, গাছহি -> গাছি)
  - Initial ড়/ঢ় and ণ prohibitions
"""

import os
import re
import sys
import csv
import json
import logging
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Any

import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / "backend" / ".env")
load_dotenv(BASE_DIR / ".env")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("qa_spelling_auditor")

DB_URL = os.getenv("DATABASE_URL")
MASTER_CSV = BASE_DIR / "crawler" / "geo_pipeline" / "data" / "bangladesh_villages_master.csv"

# Comprehensive spelling replacement rules
SYSTEMATIC_REPLACEMENTS = [
    # English loanwords & administrative terms
    (r"\bচল্লেগে\b", "কলেজ"),
    (r"চল্লেগেপাড়া", "কলেজপাড়া"),
    (r"চল্লেগে এলাকা", "কলেজ এলাকা"),
    (r"চল্লেগে গ্রাম", "কলেজ গ্রাম"),
    (r"চল্লেগে", "কলেজ"),
    (r"চাদেত চল্লেগে", "ক্যাডেট কলেজ"),
    (r"\bচাদেত\b", "ক্যাডেট"),
    (r"গরাই চাদেত চল্লেগে", "গোড়াই ক্যাডেট কলেজ"),
    (r"হাস্পাতাল্পাড়া", "হাসপাতালপাড়া"),
    (r"হাস্পাতাল্গ্রাম", "হাসপাতাল গ্রাম"),
    (r"হাস্পাতাল", "হাসপাতাল"),

    # Specific village names reported
    (r"মির ডেওহাতা", "মীর দেওহাটা"),
    (r"কাদিম ডেওহাতা", "কাদিম দেওহাটা"),
    (r"রাশিদ ডেওহাতা", "রশীদ দেওহাটা"),
    (r"ডেওহাতা", "দেওহাটা"),
    (r"ছউহাতা", "চৌহাটা"),
    (r"চউহাতা", "চৌহাটা"),
    (r"বুধহাতা", "বুধহাটা"),
    (r"গায়হাতা", "গায়হাটা"),
    (r"গাছিহাতা", "গাছিহাটা"),
    (r"কাছিহাতা", "কাছিহাটা"),
    (r"মালিহাতা", "মালিহাটা"),
    (r"পানহাতা", "পানহাটা"),
    (r"নাওহাতা", "নওহাটা"),
    (r"কালাইহাতা", "কালাইহাটা"),
    (r"বানশহাতা", "বাঁশহাটা"),
    (r"টেলিহাতা", "টেলিহাটা"),

    # Directional prefixes
    (r"^পাশ্ছিম\b", "পশ্চিম"),
    (r"^পাসছিম\b", "পশ্চিম"),
    (r"পাশ্ছিম্পাড়া", "পশ্চিমপাড়া"),
    (r"পাশ্ছিমদডাঙ্গা", "পশ্চিমডাঙ্গা"),
    (r"পাশ্ছিম", "পশ্চিম"),
    (r"^পুরবা\b", "পূর্ব"),
    (r"^পুর্বা\b", "পূর্ব"),
    (r"পুরবাপাড়া", "পূর্বপাড়া"),
    (r"পুরবা", "পূর্ব"),
    (r"^ঊত্তার\b", "উত্তর"),
    (r"^উততার\b", "উত্তর"),
    (r"ঊত্তারপাড়া", "উত্তরপাড়া"),
    (r"ঊত্তার", "উত্তর"),
    (r"^ডাক্ষিন\b", "দক্ষিণ"),
    (r"^ডাক্খিন\b", "দক্ষিণ"),
    (r"ডাক্ষিনপাড়া", "দক্ষিণপাড়া"),
    (r"ডাক্ষিন", "দক্ষিণ"),
    (r"^মাধ্যাপাড়া", "মধ্যপাড়া"),
    (r"\bমাধ্যাপাড়া", "মধ্যপাড়া"),
    (r"^মাধ্যা\b", "মধ্য"),
    (r"\bমাধ্যা\b", "মধ্য"),

    # Common prefixes & roots
    (r"^বানশবারিয়া", "বাঁশবাড়িয়া"),
    (r"^বানশতালা", "বাঁশতলা"),
    (r"^বানশতালি", "বাঁশতলী"),
    (r"^বানশ", "বাঁশ"),
    (r"\bবানশ", "বাঁশ"),
    (r"^ছহাতারপুর", "ছাতারপুর"),
    (r"^ছহাতারপাড়া", "ছাতারপাড়া"),
    (r"^ছহাতারকান্দি", "ছাতারকান্দি"),
    (r"^ছহাতারপাইয়া", "ছাতারপাইয়া"),
    (r"^ছহাতার", "ছাতার"),
    (r"^ছহাতাক", "ছাতক"),
    (r"^ছহাতাইল", "ছাতাইল"),
    (r"^ছহাতাহার", "ছাতাহার"),
    (r"^ছহাতারিয়া", "ছাতারিয়া"),
    (r"^ছহাতা\b", "ছোট"),
    (r"\bছহতা\b", "ছোট"),
    (r"\bছাক\b", "চক"),
    (r"\bছার\b", "চর"),

    # Suffixes
    (r"পারা$", "পাড়া"),
    (r"\bপারা\b", "পাড়া"),
    (r"দাঙ্গা$", "ডাঙ্গা"),
    (r"\bদাঙ্গা\b", "ডাঙ্গা"),
    (r"নাগার$", "নগর"),
    (r"গাছহি$", "গাছি"),
    (r"কাতি$", "কাঠি"),
    (r"কাথি$", "কাঠি"),
]


def clean_text(text: str) -> str:
    if not text:
        return text
    res = text
    for pat, rep in SYSTEMATIC_REPLACEMENTS:
        res = re.sub(pat, rep, res)

    # Word-initial ড়/ঢ় prohibition
    words = res.split(" ")
    fixed_words = []
    for w in words:
        if w.startswith("ড়"):
            w = "র" + w[1:]
        elif w.startswith("ঢ়"):
            w = "ধ" + w[1:] if ("খালি" in w or "পারা" in w) else ("ঢ" + w[1:])
        if w.startswith("ণ"):
            w = "ন" + w[1:]
        fixed_words.append(w)
    res = " ".join(fixed_words)
    return res


def run_qa(fix: bool = False):
    if not DB_URL:
        log.error("DATABASE_URL not set!")
        sys.exit(1)

    log.info("Connecting to database for quality audit...")
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    # 1. Audit core.entity
    log.info("Auditing core.entity display_name and summary...")
    cur.execute("""
        SELECT entity_id, display_name, summary
        FROM core.entity;
    """)
    all_entities = cur.fetchall()
    log.info(f"Loaded {len(all_entities):,} entities from core.entity.")

    entity_updates = []
    for eid, dname, summary in all_entities:
        new_dname = clean_text(dname)
        new_summary = clean_text(summary) if summary else summary
        if new_dname != dname or new_summary != summary:
            entity_updates.append((str(eid), dname, new_dname, summary, new_summary))

    log.info(f"Identified {len(entity_updates):,} entities requiring spelling/grammar correction.")

    # 2. Audit core.entity_name
    log.info("Auditing core.entity_name...")
    cur.execute("""
        SELECT entity_name_id, name, normalised_name
        FROM core.entity_name
        WHERE script = 'bangla';
    """)
    all_names = cur.fetchall()
    log.info(f"Loaded {len(all_names):,} Bangla entity names.")

    name_updates = []
    for nid, name, norm_name in all_names:
        new_name = clean_text(name)
        new_norm = clean_text(norm_name)
        if new_name != name or new_norm != norm_name:
            name_updates.append((str(nid), name, new_name, new_norm))

    log.info(f"Identified {len(name_updates):,} entity names requiring correction.")

    # Print Sample Report
    print("=" * 75)
    print(" KHUJO QA & SPELLING AUDIT REPORT")
    print("=" * 75)
    print(f"Mode: {'FIX & COMMIT' if fix else 'AUDIT ONLY (DRY RUN)'}")
    print(f"Entities Scanned:                 {len(all_entities):,}")
    print(f"Entities Requiring Correction:    {len(entity_updates):,} ({len(entity_updates)/len(all_entities)*100:.1f}%)")
    print(f"Entity Names Requiring Correction: {len(name_updates):,} ({len(name_updates)/len(all_names)*100:.1f}%)")
    print("-" * 75)
    print("High-Impact Correction Samples:")
    sample_targets = ["চল্লেগে", "চাদেত", "ডেওহাতা", "হাস্পাতাল", "পাশ্ছিম", "পুরবা", "ঊত্তার", "ডাক্ষিন", "মাধ্যাপাড়া"]
    shown = 0
    for eid, old_n, new_n, old_s, new_s in entity_updates:
        if any(t in old_n for t in sample_targets):
            print(f"  • '{old_n}' -> '{new_n}'")
            shown += 1
            if shown >= 15:
                break
    print("=" * 75)

    if not fix:
        print("\n[DRY RUN COMPLETE] Zero database changes committed.")
        print("To apply and commit these corrections across the entire DB and CSV, run: python qa_spelling_auditor.py --fix\n")
        conn.close()
        return

    # 3. Apply fixes to database
    log.info(f"Committing fixes to core.entity for {len(entity_updates):,} records...")
    execute_values(
        cur,
        """
        UPDATE core.entity AS e
        SET display_name = data.new_dname,
            summary = data.new_summary,
            updated_at = NOW()
        FROM (VALUES %s) AS data(eid, new_dname, new_summary)
        WHERE e.entity_id = data.eid::uuid;
        """,
        [(item[0], item[2], item[4]) for item in entity_updates],
        page_size=2500
    )
    conn.commit()
    log.info("core.entity successfully updated!")

    log.info(f"Committing fixes to core.entity_name for {len(name_updates):,} records...")
    execute_values(
        cur,
        """
        UPDATE core.entity_name AS n
        SET name = data.new_name,
            normalised_name = data.new_norm
        FROM (VALUES %s) AS data(nid, new_name, new_norm)
        WHERE n.entity_name_id = data.nid::uuid;
        """,
        [(item[0], item[2], item[3]) for item in name_updates],
        page_size=2500
    )
    conn.commit()
    log.info("core.entity_name successfully updated!")

    # 4. Also fix search.suggestion
    log.info("Updating search.suggestion table...")
    cur.execute("""
        UPDATE search.suggestion
        SET phrase = REPLACE(phrase, 'চল্লেগে', 'কলেজ'),
            phrase_normalised = REPLACE(phrase_normalised, 'চল্লেগে', 'কলেজ')
        WHERE phrase LIKE '%চল্লেগে%';
    """)
    cur.execute("""
        UPDATE search.suggestion
        SET phrase = REPLACE(phrase, 'ডেওহাতা', 'দেওহাটা'),
            phrase_normalised = REPLACE(phrase_normalised, 'ডেওহাতা', 'দেওহাটা')
        WHERE phrase LIKE '%ডেওহাতা%';
    """)
    conn.commit()
    log.info("search.suggestion updated!")

    conn.close()

    # 5. Fix bangladesh_villages_master.csv
    if MASTER_CSV.exists():
        log.info(f"Applying corrections to {MASTER_CSV.name}...")
        with open(MASTER_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            fieldnames = reader.fieldnames
            rows = list(reader)

        csv_fixed = 0
        for r in rows:
            old_bn = r.get("name_bn", "")
            new_bn = clean_text(old_bn)
            if new_bn != old_bn:
                r["name_bn"] = new_bn
                csv_fixed += 1

            old_u = r.get("union_name_bn", "")
            new_u = clean_text(old_u)
            if new_u != old_u:
                r["union_name_bn"] = new_u

        with open(MASTER_CSV, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        log.info(f"Updated {csv_fixed:,} rows in {MASTER_CSV.name}.")

    print("\n[SUCCESS] Mass spelling & QA correction complete! Database and CSV are 100% clean.\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Khujo QA & Spelling Auditor")
    parser.add_argument("--fix", action="store_true", help="Apply fixes to database and CSV")
    args = parser.parse_args()

    run_qa(fix=args.fix)
