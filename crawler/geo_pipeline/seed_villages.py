#!/usr/bin/env python3
"""
seed_villages.py - Phase 4: Ingestion of 91,456 Bangladesh Villages & Micro-Locations.

Reads bangladesh_villages_master.csv (91,456 clean, grammatically-normalized village records)
and seeds them into:
  1. core.entity (entity_type_id=4 for Settlement/Village)
  2. core.place (linked to parent Union via parent_place_id)
  3. core.entity_name (Bangla official name + English transliteration)

Features:
  - High-performance chunked bulk inserts (execute_values with batch_size=2500)
  - Accurate parent union resolution using Phase 3 hierarchy scaffold
  - Reconnection resilience for Neon Postgres serverless
  - --dry-run (default) and --commit flags
"""

import os
import sys
import csv
import json
import uuid
import logging
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Any, Optional

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
log = logging.getLogger("seed_villages")

DB_URL = os.getenv("DATABASE_URL")
CSV_PATH = BASE_DIR / "crawler" / "geo_pipeline" / "data" / "bangladesh_villages_master.csv"


def get_db_connection():
    if not DB_URL:
        raise ValueError("DATABASE_URL not found in environment!")
    return psycopg2.connect(DB_URL)


def load_parent_unions(conn) -> Tuple[Dict[Tuple[str, str], str], Dict[str, str], str]:
    """
    Load all Unions from DB to map (union_name_bn, upazila_name_bn) -> entity_id.
    Fallback: union_name_bn -> entity_id.
    Root: Bangladesh entity_id.
    """
    cur = conn.cursor()
    
    # 1. Fetch Bangladesh root
    cur.execute("""
        SELECT e.entity_id FROM core.entity e
        JOIN core.place p ON e.entity_id = p.entity_id
        WHERE p.parent_place_id IS NULL AND (p.official_code = 'BD' OR e.display_name = 'বাংলাদেশ')
        LIMIT 1;
    """)
    root_row = cur.fetchone()
    bd_eid = str(root_row[0]) if root_row else "d26fa3f6-2272-41a4-8c9b-6e7feb8d38c5"

    # 2. Fetch all Unions (entity_type_id=3 with metadata->>'place_type'='Union')
    # and join with their parent Upazila
    cur.execute("""
        SELECT u.entity_id, u.display_name, upz.display_name as upazila_name
        FROM core.entity u
        JOIN core.place pu ON u.entity_id = pu.entity_id
        LEFT JOIN core.entity upz ON pu.parent_place_id = upz.entity_id
        WHERE u.entity_type_id = 3;
    """)
    rows = cur.fetchall()
    
    union_upz_map = {}
    union_simple_map = {}

    for eid, u_name, upz_name in rows:
        eid_str = str(eid)
        u_clean = u_name.strip()
        upz_clean = upz_name.strip() if upz_name else ""

        union_upz_map[(u_clean, upz_clean)] = eid_str
        if u_clean not in union_simple_map:
            union_simple_map[u_clean] = eid_str

    cur.close()
    log.info(f"Loaded {len(union_upz_map):,} union lookup mappings from database.")
    return union_upz_map, union_simple_map, bd_eid


def run_seeder(commit: bool = False, batch_size: int = 5000, limit: Optional[int] = None):
    if not CSV_PATH.exists():
        log.error(f"File not found: {CSV_PATH}")
        sys.exit(1)

    log.info(f"Reading {CSV_PATH.name}...")
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if limit:
        rows = rows[:limit]

    total_rows = len(rows)
    log.info(f"Total village records to process: {total_rows:,}")

    conn = get_db_connection()
    union_upz_map, union_simple_map, bd_eid = load_parent_unions(conn)

    # Resolution test & preview
    resolved_count = 0
    fallback_count = 0
    sample_preview = []

    for idx, r in enumerate(rows):
        u_bn = r.get("union_name_bn", "").strip()
        upz_bn = r.get("upazila_name_bn", "").strip()

        parent_eid = union_upz_map.get((u_bn, upz_bn))
        if not parent_eid:
            parent_eid = union_simple_map.get(u_bn)

        if parent_eid:
            resolved_count += 1
        else:
            fallback_count += 1

        if idx < 5:
            sample_preview.append((r["name_bn"], r["name_en"], u_bn, upz_bn, parent_eid or bd_eid))

    print("=" * 70)
    print(" KHUJO SEARCH ENGINE - PHASE 4 VILLAGE SEEDER REPORT")
    print("=" * 70)
    print(f"Mode: {'COMMITTED TO DATABASE' if commit else 'DRY RUN (NO CHANGES APPLIED)'}")
    print(f"Total Villages in Dataset: {total_rows:,}")
    print(f"Successfully Resolved to Parent Union: {resolved_count:,} ({resolved_count/total_rows*100:.1f}%)")
    print(f"Fallback to Upazila/Root:              {fallback_count:,} ({fallback_count/total_rows*100:.1f}%)")
    print("-" * 70)
    print("Sample Village -> Union Mapping Preview:")
    for v_bn, v_en, u_bn, upz_bn, p_eid in sample_preview:
        print(f"  • {v_bn} ({v_en}) -> Union: {u_bn}, Upazila: {upz_bn} | Parent ID: {p_eid}")
    print("=" * 70)

    if not commit:
        print("\n[DRY RUN COMPLETE] Zero changes written to database.")
        print("To commit all 91,456 villages to Neon PostgreSQL, rerun with: --commit\n")
        conn.close()
        return

    # ------------------ COMMIT PHASE ------------------
    log.info(f"Starting multi-batch insertion of {total_rows:,} villages (batch_size={batch_size})...")

    insert_entity_sql = """
        INSERT INTO core.entity (
            entity_id, entity_type_id, display_name, preferred_language_code,
            state, visibility, summary, metadata
        ) VALUES %s
        ON CONFLICT (entity_id) DO NOTHING;
    """

    insert_place_sql = """
        INSERT INTO core.place (
            entity_id, parent_place_id, official_code_scheme, official_code,
            latitude, longitude
        ) VALUES %s
        ON CONFLICT (entity_id) DO NOTHING;
    """

    insert_name_sql = """
        INSERT INTO core.entity_name (
            entity_name_id, entity_id, name, normalised_name,
            language_code, script, name_kind, is_primary, state
        ) VALUES %s
        ON CONFLICT (entity_id, normalised_name, language_code, name_kind) DO NOTHING;
    """

    total_inserted = 0
    cur = conn.cursor()

    for i in range(0, total_rows, batch_size):
        chunk = rows[i:i + batch_size]
        
        entities_batch = []
        places_batch = []
        names_batch = []

        for r in chunk:
            n_eid = str(uuid.uuid4())
            name_bn = r.get("name_bn", "").strip()
            name_en = r.get("name_en", "").strip()
            u_bn = r.get("union_name_bn", "").strip()
            upz_bn = r.get("upazila_name_bn", "").strip()
            dist_bn = r.get("district_name_bn", "").strip()
            div_bn = r.get("division_name_bn", "").strip()
            mauza = r.get("mauza", "").strip()
            bbs_code = r.get("bbs_code", "").strip()

            lat = float(r["latitude"]) if r.get("latitude") else None
            lon = float(r["longitude"]) if r.get("longitude") else None
            pop = int(r["population"]) if r.get("population") and r["population"].isdigit() else None
            hh = int(r["households"]) if r.get("households") and r["households"].isdigit() else None

            # Resolve parent union
            parent_eid = union_upz_map.get((u_bn, upz_bn)) or union_simple_map.get(u_bn) or bd_eid

            # Summary
            loc_parts = [p for p in [u_bn + " ইউনিয়ন" if u_bn else "", upz_bn + " উপজেলা" if upz_bn else "", dist_bn + " জেলা" if dist_bn else ""] if p]
            loc_str = " ".join(loc_parts)
            summary = f"{name_bn} বাংলাদেশের {loc_str}-এর একটি গ্রাম।" if loc_str else f"{name_bn} বাংলাদেশের একটি গ্রাম।"

            meta = {
                "country": "Bangladesh",
                "place_type": "Village",
                "mauza": mauza or None,
                "union": u_bn or None,
                "upazila": upz_bn or None,
                "district": dist_bn or None,
                "division": div_bn or None,
                "bbs_code": bbs_code or None,
                "population": pop,
                "households": hh,
                "latitude": lat,
                "longitude": lon,
            }

            # 1. Entity
            entities_batch.append((
                n_eid,
                4,  # Settlement / Village
                name_bn if name_bn else name_en,
                "bn",
                "verified",
                "public",
                summary,
                json.dumps(meta, ensure_ascii=False)
            ))

            # 2. Place
            places_batch.append((
                n_eid,
                parent_eid,
                "bbs_phc_2022",
                bbs_code or r.get("internal_id"),
                lat,
                lon
            ))

            # 3. Bangla Name
            if name_bn:
                names_batch.append((
                    str(uuid.uuid4()),
                    n_eid,
                    name_bn,
                    name_bn.lower().strip(),
                    "bn",
                    "bangla",
                    "official",
                    True,
                    "verified"
                ))

            # 4. English Name
            if name_en:
                names_batch.append((
                    str(uuid.uuid4()),
                    n_eid,
                    name_en,
                    name_en.lower().strip(),
                    "en",
                    "latin",
                    "transliteration",
                    False if name_bn else True,
                    "verified"
                ))

        # Execute chunk
        try:
            execute_values(cur, insert_entity_sql, entities_batch, page_size=1000)
            execute_values(cur, insert_place_sql, places_batch, page_size=1000)
            execute_values(cur, insert_name_sql, names_batch, page_size=1000)
            conn.commit()
            total_inserted += len(chunk)
            log.info(f"Committed {total_inserted:,} / {total_rows:,} villages ({total_inserted/total_rows*100:.1f}%)...")
        except Exception as e:
            log.error(f"Error in batch {i} to {i+len(chunk)}: {e}")
            conn.rollback()
            # Try to reconnect if connection lost
            try:
                conn.close()
            except Exception:
                pass
            conn = get_db_connection()
            cur = conn.cursor()
            raise e

    cur.close()
    conn.close()
    log.info(f"[SUCCESS] Phase 4 complete! Ingested {total_inserted:,} Bangladesh villages into core.entity and core.place.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 4: Bangladesh Village Seeder")
    parser.add_argument("--commit", action="store_true", help="Commit village records to database")
    parser.add_argument("--batch-size", type=int, default=5000, help="Batch size for inserts")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of records to process")
    args = parser.parse_args()

    run_seeder(commit=args.commit, batch_size=args.batch_size, limit=args.limit)
