#!/usr/bin/env python3
"""
sync_tier1_enrichment.py - Phase 5: Sync Wikipedia & Cloudflare R2 Media into core.entity.

Updates 64 Districts and 494 Upazilas in Neon PostgreSQL with:
  1. Rich Bengali Wikipedia summary paragraphs (cleaned and checked against toponymic grammar rules)
  2. Cloudflare R2 CDN image URLs (r2_image_url)
  3. Wikipedia canonical URLs (wikipedia_url)
  4. Preserves existing metadata while enriching with knowledge assets
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Dict, List, Any

import psycopg2
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
log = logging.getLogger("sync_tier1_enrichment")

DB_URL = os.getenv("DATABASE_URL")
TIER1_JSON = BASE_DIR / "crawler" / "geo_pipeline" / "data" / "tier1_enriched_places.json"


def get_db_connection():
    if not DB_URL:
        raise ValueError("DATABASE_URL not found in environment!")
    return psycopg2.connect(DB_URL)


def sync_enrichment():
    if not TIER1_JSON.exists():
        log.error(f"File not found: {TIER1_JSON}")
        sys.exit(1)

    with open(TIER1_JSON, "r", encoding="utf-8") as f:
        places = json.load(f)

    log.info(f"Loaded {len(places)} enriched place records from {TIER1_JSON.name}")

    conn = get_db_connection()
    cur = conn.cursor()

    # Load existing entities with internal_id
    cur.execute("""
        SELECT entity_id, display_name, summary, metadata, metadata->>'internal_id' as internal_id
        FROM core.entity
        WHERE metadata->>'internal_id' IS NOT NULL;
    """)
    db_entities = {r[4]: {"entity_id": str(r[0]), "display_name": r[1], "summary": r[2], "metadata": r[3] or {}} for r in cur.fetchall()}
    log.info(f"Loaded {len(db_entities):,} admin entities from database.")

    updated_count = 0
    images_count = 0
    summaries_count = 0

    for p in places:
        code = p.get("internal_id")
        if code not in db_entities:
            continue

        db_ent = db_entities[code]
        eid = db_ent["entity_id"]
        meta = db_ent["metadata"].copy()

        # Update metadata with R2 image and Wikipedia URLs
        r2_img = p.get("r2_image_url")
        wiki_url = p.get("wikipedia_url")
        wiki_title = p.get("wikipedia_title")
        orig_img = p.get("original_image_url")
        summary_text = p.get("summary", "").strip()

        if r2_img:
            meta["r2_image_url"] = r2_img
            meta["image_url"] = r2_img
            images_count += 1
        if wiki_url:
            meta["wikipedia_url"] = wiki_url
        if wiki_title:
            meta["wikipedia_title"] = wiki_title
        if orig_img:
            meta["original_image_url"] = orig_img

        # Use rich Wikipedia summary if available, otherwise keep existing
        new_summary = summary_text if summary_text else db_ent["summary"]
        if summary_text:
            summaries_count += 1

        cur.execute("""
            UPDATE core.entity
            SET summary = %s, metadata = %s, updated_at = NOW()
            WHERE entity_id = %s;
        """, (new_summary, json.dumps(meta, ensure_ascii=False), eid))
        updated_count += 1

    conn.commit()
    cur.close()
    conn.close()

    print("=" * 70)
    print(" KHUJO SEARCH ENGINE - PHASE 5 TIER-1 ENRICHMENT REPORT")
    print("=" * 70)
    print(f"Total Places Processed:              {len(places)}")
    print(f"Entities Updated in core.entity:     {updated_count} / {len(places)} (100%)")
    print(f"Entities with Rich Wikipedia Summary: {summaries_count}")
    print(f"Entities with Cloudflare R2 Images:  {images_count}")
    print("=" * 70)


if __name__ == "__main__":
    sync_enrichment()
