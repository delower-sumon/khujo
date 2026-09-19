#!/usr/bin/env python3
"""
seed_micro_locations.py - Ultra-Fast Ingestion of Bangladesh Micro-Locations.
Seeds 1,400+ Bangladeshi Mahallas, Paras, and Villages from micro_locations_raw.csv
into core.entity (entity_type_id=4 for Settlement) and core.entity_name
using execute_values for single round-trip bulk inserts.
"""

import os
import sys
import csv
import json
import logging
import uuid
from pathlib import Path
from typing import Dict, List, Any

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
log = logging.getLogger("seed_micro_locations")

DB_URL = os.getenv("DATABASE_URL")
CSV_PATH = BASE_DIR / "crawler" / "geo_pipeline" / "data" / "micro_locations_raw.csv"


def normalize_term(term: str) -> str:
    """Lowercase and remove whitespace/special characters."""
    if not term:
        return ""
    return term.strip().lower().replace(" ", "").replace("-", "")


def seed_micro_locations():
    if not DB_URL:
        log.error("DATABASE_URL not found!")
        sys.exit(1)

    if not CSV_PATH.exists():
        log.error(f"CSV file not found at {CSV_PATH}")
        sys.exit(1)

    log.info(f"Connecting to database to seed micro-locations from {CSV_PATH}...")
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    # Load existing entity names to avoid duplicate inserts
    cur.execute("SELECT lower(name) FROM core.entity_name;")
    existing_names = set(r[0] for r in cur.fetchall())
    log.info(f"Loaded {len(existing_names):,} existing names from DB.")

    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    log.info(f"Loaded {len(rows):,} rows from micro_locations_raw.csv.")

    batch_entities = []
    batch_names = []

    for row in rows:
        name_bn = (row.get("name_bn") or "").strip()
        name_en = (row.get("name_en") or "").strip()
        place_type = (row.get("place_type") or "Settlement").strip()
        lat = row.get("latitude")
        lon = row.get("longitude")
        website = row.get("website")

        if not name_bn and not name_en:
            continue

        display_name = name_bn if name_bn else name_en

        # Skip duplicates
        if (name_bn and name_bn.lower() in existing_names) or (name_en and name_en.lower() in existing_names):
            continue

        entity_id = str(uuid.uuid4())
        summary = f"{display_name} বাংলাদেশের একটি {place_type}।"
        metadata = {
            "country": "Bangladesh",
            "place_type": place_type,
            "latitude": float(lat) if lat else None,
            "longitude": float(lon) if lon else None,
            "website": website or None,
            "osm_id": row.get("internal_id")
        }

        batch_entities.append((
            entity_id,
            4,  # entity_type_id=4 for settlement
            display_name,
            'ben',
            'verified',
            'public',
            summary,
            json.dumps(metadata, ensure_ascii=False)
        ))

        # Add Bengali name
        if name_bn:
            batch_names.append((
                str(uuid.uuid4()),
                entity_id,
                name_bn,
                normalize_term(name_bn),
                'ben',
                'bangla',
                'preferred',
                True,
                'verified'
            ))
            existing_names.add(name_bn.lower())

        # Add English / Banglish transliteration name
        if name_en:
            batch_names.append((
                str(uuid.uuid4()),
                entity_id,
                name_en,
                normalize_term(name_en),
                'eng',
                'latin',
                'transliteration',
                False if name_bn else True,
                'verified'
            ))
            existing_names.add(name_en.lower())

    if batch_entities:
        insert_entity_sql = """
            INSERT INTO core.entity (
                entity_id, entity_type_id, display_name, preferred_language_code,
                state, visibility, summary, metadata
            ) VALUES %s
        """
        execute_values(cur, insert_entity_sql, batch_entities, page_size=500)
        log.info(f"Inserted {len(batch_entities):,} entities.")

    if batch_names:
        insert_name_sql = """
            INSERT INTO core.entity_name (
                entity_name_id, entity_id, name, normalised_name,
                language_code, script, name_kind, is_primary, state
            ) VALUES %s
        """
        execute_values(cur, insert_name_sql, batch_names, page_size=500)
        log.info(f"Inserted {len(batch_names):,} entity names.")

    conn.commit()
    cur.close()
    conn.close()
    log.info(f"[SUCCESS] Finished seeding micro-locations! Added {len(batch_entities):,} entities and {len(batch_names):,} names.")


if __name__ == "__main__":
    seed_micro_locations()
