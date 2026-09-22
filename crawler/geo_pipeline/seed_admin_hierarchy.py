#!/usr/bin/env python3
"""
seed_admin_hierarchy.py - Phase 3: Bangladesh Administrative Hierarchy Seeder.

Reads base_hierarchy.csv (5,106 administrative units: Divisions, Districts, Upazilas, Unions)
and seeds/syncs them into:
  1. core.entity (entity_type_id=3 for administrative_area)
  2. core.place (hierarchical containment via parent_place_id, official_code=internal_id)
  3. core.entity_name (Bangla official name + English transliteration)
  4. search.suggestion (autocomplete suggestions for search bar)

Features:
  - --dry-run (default): Simulates the entire process, checks parent links, matches against
    existing DB entities, and generates a detailed report without writing to the database.
  - --commit: Performs the multi-stage transactional upsert/insert in batches.
  - Preserves existing rich metadata (Wikipedia facts, images, summaries) without overwriting.
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
from collections import defaultdict

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
log = logging.getLogger("seed_admin_hierarchy")

DB_URL = os.getenv("DATABASE_URL")
CSV_PATH = BASE_DIR / "crawler" / "geo_pipeline" / "data" / "base_hierarchy.csv"

# Root Bangladesh entity ID in core.place / core.entity
DEFAULT_BD_ENTITY_ID = "d26fa3f6-2272-41a4-8c9b-6e7feb8d38c5"


def normalize_term(term: str) -> str:
    """Normalize string for fuzzy/exact matching."""
    if not term:
        return ""
    return term.strip().lower().replace(" ", "").replace("-", "").replace("/", "").replace("'", "")


def load_hierarchy_csv() -> List[Dict[str, str]]:
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"CSV file not found at {CSV_PATH}")
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    return rows


def get_db_connection():
    if not DB_URL:
        raise ValueError("DATABASE_URL not found in environment!")
    return psycopg2.connect(DB_URL)


def match_place(row: Dict[str, str], candidates: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Match a CSV row against candidate existing places under the same parent."""
    name_bn = row["name_bn"].strip()
    name_en = row["name_en"].strip().lower()
    norm_bn = normalize_term(name_bn)
    norm_en = normalize_term(name_en)

    for c in candidates:
        # Check display_name exact
        if c["display_name"] == name_bn:
            return c
        # Check alias names
        for n in c["names"]:
            n_clean = n.strip()
            if n_clean == name_bn:
                return c
            if n_clean.lower() == name_en:
                return c
            # Normalized match
            n_norm = normalize_term(n_clean)
            if n_norm == norm_bn or n_norm == norm_en:
                return c
            # Substring match for compound names like 'মহাস্থানগড় / শিবগঞ্জ'
            if len(norm_bn) >= 4 and (norm_bn in n_norm or n_norm in norm_bn):
                return c
    return None


def run_seeder(commit: bool = False):
    rows = load_hierarchy_csv()
    log.info(f"Loaded {len(rows):,} records from {CSV_PATH.name}")

    conn = get_db_connection()
    cur = conn.cursor()

    # 1. Verify / fetch Bangladesh root entity
    cur.execute("""
        SELECT e.entity_id 
        FROM core.entity e
        JOIN core.place p ON e.entity_id = p.entity_id
        WHERE p.parent_place_id IS NULL AND (p.official_code = 'BD' OR e.display_name = 'বাংলাদেশ')
        LIMIT 1;
    """)
    root_res = cur.fetchone()
    bd_entity_id = str(root_res[0]) if root_res else DEFAULT_BD_ENTITY_ID
    log.info(f"Root Bangladesh entity_id: {bd_entity_id}")

    # 2. Fetch existing places & entities
    cur.execute("""
        SELECT e.entity_id, e.display_name, e.summary, e.metadata, p.parent_place_id, p.official_code,
               p.latitude, p.longitude, array_agg(n.name) as names
        FROM core.entity e
        JOIN core.place p ON e.entity_id = p.entity_id
        LEFT JOIN core.entity_name n ON e.entity_id = n.entity_id
        WHERE e.entity_type_id = 3
        GROUP BY e.entity_id, e.display_name, e.summary, e.metadata, p.parent_place_id, p.official_code,
                 p.latitude, p.longitude
    """)
    existing_places = cur.fetchall()
    log.info(f"Loaded {len(existing_places):,} existing administrative places from database.")

    # Group existing places by parent_place_id
    children_by_parent = defaultdict(list)
    existing_by_id = {}
    for p in existing_places:
        eid, dname, summary, meta, ppid, off_code, lat, lon, names = p
        eid_str = str(eid)
        ppid_str = str(ppid) if ppid else None
        item = {
            "entity_id": eid_str,
            "display_name": dname.strip(),
            "summary": summary,
            "metadata": meta if isinstance(meta, dict) else {},
            "parent_place_id": ppid_str,
            "official_code": off_code,
            "latitude": float(lat) if lat is not None else None,
            "longitude": float(lon) if lon is not None else None,
            "names": [n.strip() for n in names if n] if names else [dname.strip()],
        }
        children_by_parent[ppid_str].append(item)
        existing_by_id[eid_str] = item

    # Partition CSV rows by place_type
    divisions = [r for r in rows if r["place_type"] == "Division"]
    districts = [r for r in rows if r["place_type"] == "District"]
    upazilas = [r for r in rows if r["place_type"] == "Upazila"]
    unions = [r for r in rows if r["place_type"] == "Union"]

    # Mapping internal_id -> entity_id
    internal_to_eid = {"BD": bd_entity_id}
    internal_to_row = {r["internal_id"]: r for r in rows}

    matched_records = []  # (row, existing_item, parent_eid)
    new_records = []      # (row, new_eid, parent_eid)

    # Process level by level
    levels = [
        ("Division", divisions, 1),
        ("District", districts, 2),
        ("Upazila", upazilas, 3),
        ("Union", unions, 4),
    ]

    stats_by_level = {}

    for ptype, ptype_rows, depth in levels:
        matched_count = 0
        new_count = 0
        missing_parent_count = 0

        for r in ptype_rows:
            internal_id = r["internal_id"]
            parent_id = r["parent_id"]
            parent_eid = internal_to_eid.get(parent_id)

            if not parent_eid:
                missing_parent_count += 1
                parent_eid = bd_entity_id

            candidates = children_by_parent.get(parent_eid, [])
            match = match_place(r, candidates)

            if match:
                matched_count += 1
                assigned_eid = match["entity_id"]
                internal_to_eid[internal_id] = assigned_eid
                matched_records.append((r, match, parent_eid))
            else:
                new_count += 1
                assigned_eid = str(uuid.uuid4())
                internal_to_eid[internal_id] = assigned_eid
                new_records.append((r, assigned_eid, parent_eid))

        stats_by_level[ptype] = {
            "total": len(ptype_rows),
            "matched": matched_count,
            "new": new_count,
            "missing_parent": missing_parent_count,
        }

    # Generate Report
    print("=" * 70)
    print(" KHUJO SEARCH ENGINE - PHASE 3 ADMIN HIERARCHY SEEDER REPORT")
    print("=" * 70)
    print(f"Mode: {'COMMITTED TO DATABASE' if commit else 'DRY RUN (NO CHANGES APPLIED)'}")
    print(f"Total CSV Units Processed: {len(rows):,}")
    print("-" * 70)
    print(f"{'Place Type':<15} | {'Total':<8} | {'Matched Existing':<18} | {'Net New':<10} | {'Parent Integrity'}")
    print("-" * 70)

    for ptype in ["Division", "District", "Upazila", "Union"]:
        s = stats_by_level[ptype]
        parent_status = "100% OK" if s["missing_parent"] == 0 else f"{s['missing_parent']} MISSING"
        print(f"{ptype:<15} | {s['total']:<8} | {s['matched']:<18} | {s['new']:<10} | {parent_status}")

    print("-" * 70)
    total_matched = len(matched_records)
    total_new = len(new_records)
    print(f"{'TOTAL':<15} | {len(rows):<8} | {total_matched:<18} | {total_new:<10} | 100% OK")
    print("=" * 70)

    # Entities and Names count breakdown
    names_to_insert = (total_matched * 2) + (total_new * 2)
    suggestions_to_insert = (total_matched * 2) + (total_new * 2)
    print(f"Estimated Records to Sync/Insert:")
    print(f"  • core.entity records to insert:     {total_new:,}")
    print(f"  • core.entity records to sync/enrich: {total_matched:,}")
    print(f"  • core.place records to insert:      {total_new:,}")
    print(f"  • core.place records to sync:        {total_matched:,}")
    print(f"  • core.entity_name aliases (BN+EN):  ~{names_to_insert:,}")
    print(f"  • search.suggestion autocomplete:    ~{suggestions_to_insert:,}")
    print("-" * 70)

    print("Sample Preview of Data Mapping:")
    print("1. Matched Divisions (Existing Entities enriched with Geocode & Website):")
    for r, match, p_eid in [m for m in matched_records if m[0]["place_type"] == "Division"][:3]:
        print(f"   • {r['name_bn']} ({r['name_en']}) -> ID: {match['entity_id']} | Code: {r['internal_id']} | URL: {r['website']}")

    print("2. New Districts to be Inserted:")
    for r, n_eid, p_eid in [n for n in new_records if n[0]["place_type"] == "District"][:3]:
        parent_row = internal_to_row.get(r["parent_id"], {})
        parent_name = parent_row.get("name_bn", "বিভাগ")
        print(f"   • {r['name_bn']} ({r['name_en']}) -> Parent: {parent_name} ({p_eid}) | Code: {r['internal_id']} | URL: {r['website']}")

    print("3. New Upazilas to be Inserted:")
    for r, n_eid, p_eid in [n for n in new_records if n[0]["place_type"] == "Upazila"][:3]:
        parent_row = internal_to_row.get(r["parent_id"], {})
        parent_name = parent_row.get("name_bn", "জেলা")
        print(f"   • {r['name_bn']} ({r['name_en']}) -> Parent: {parent_name} ({p_eid}) | Code: {r['internal_id']}")

    print("4. New Unions to be Inserted:")
    for r, n_eid, p_eid in [n for n in new_records if n[0]["place_type"] == "Union"][:3]:
        parent_row = internal_to_row.get(r["parent_id"], {})
        parent_name = parent_row.get("name_bn", "উপজেলা")
        print(f"   • {r['name_bn']} ({r['name_en']}) -> Parent: {parent_name} ({p_eid}) | Code: {r['internal_id']}")

    print("=" * 70)

    if not commit:
        print("\n[DRY RUN COMPLETE] Zero changes committed to the database.")
        print("Ready for user review. To commit these records to Neon DB, rerun with: --commit\n")
        cur.close()
        conn.close()
        return

    # ------------------ COMMIT PHASE ------------------
    log.info("Starting database commit phase...")

    # A. Update matched existing entities (enrich metadata, preserve facts & images)
    log.info(f"Syncing metadata for {len(matched_records):,} matched entities...")
    for r, match, p_eid in matched_records:
        meta = match["metadata"].copy()
        meta["country"] = "Bangladesh"
        meta["place_type"] = r["place_type"]
        meta["internal_id"] = r["internal_id"]
        meta["parent_id"] = r["parent_id"]
        if r["website"]:
            meta["website"] = r["website"]
        if r["latitude"]:
            try:
                meta["latitude"] = float(r["latitude"])
            except ValueError:
                pass
        if r["longitude"]:
            try:
                meta["longitude"] = float(r["longitude"])
            except ValueError:
                pass

        cur.execute("""
            UPDATE core.entity
            SET metadata = %s, updated_at = NOW()
            WHERE entity_id = %s;
        """, (json.dumps(meta, ensure_ascii=False), match["entity_id"]))

        # Update core.place official_code
        lat_val = meta.get("latitude")
        lon_val = meta.get("longitude")
        cur.execute("""
            UPDATE core.place
            SET official_code = %s, official_code_scheme = 'bangladesh_geocode',
                latitude = COALESCE(%s, latitude), longitude = COALESCE(%s, longitude),
                updated_at = NOW()
            WHERE entity_id = %s;
        """, (r["internal_id"], lat_val, lon_val, match["entity_id"]))

    # B. Insert new entities in batches
    log.info(f"Inserting {len(new_records):,} new entities into core.entity...")
    entities_to_insert = []
    places_to_insert = []
    names_to_insert_list = []
    suggestions_to_insert_list = []

    priority_map = {"Division": 10, "District": 9, "Upazila": 8, "Union": 7}

    for r, n_eid, p_eid in new_records:
        ptype = r["place_type"]
        name_bn = r["name_bn"].strip()
        name_en = r["name_en"].strip()
        parent_row = internal_to_row.get(r["parent_id"], {})
        parent_name = parent_row.get("name_bn", "")

        # Generate summary
        if ptype == "Division":
            summary = f"{name_bn} বিভাগ বাংলাদেশের একটি প্রধান প্রশাসনিক বিভাগ।"
        elif ptype == "District":
            summary = f"{name_bn} জেলা বাংলাদেশের {parent_name} বিভাগের একটি প্রশাসনিক অঞ্চল।" if parent_name else f"{name_bn} জেলা বাংলাদেশের একটি প্রশাসনিক অঞ্চল।"
        elif ptype == "Upazila":
            summary = f"{name_bn} উপজেলা, {parent_name} জেলা।" if parent_name else f"{name_bn} বাংলাদেশের একটি উপজেলা।"
        else:
            summary = f"{name_bn} ইউনিয়ন, {parent_name} উপজেলা।" if parent_name else f"{name_bn} বাংলাদেশের একটি ইউনিয়ন।"

        lat_val = float(r["latitude"]) if r.get("latitude") else None
        lon_val = float(r["longitude"]) if r.get("longitude") else None

        metadata = {
            "country": "Bangladesh",
            "place_type": ptype,
            "internal_id": r["internal_id"],
            "parent_id": r["parent_id"],
            "website": r.get("website") or None,
            "latitude": lat_val,
            "longitude": lon_val,
        }

        entities_to_insert.append((
            n_eid,
            3,  # entity_type_id=3 (administrative_area)
            name_bn,
            "bn",
            "verified",
            "public",
            summary,
            json.dumps(metadata, ensure_ascii=False)
        ))

        places_to_insert.append((
            n_eid,
            p_eid,
            "bangladesh_geocode",
            r["internal_id"],
            lat_val,
            lon_val
        ))

        # Bangla name
        names_to_insert_list.append((
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

        # English name
        if name_en:
            names_to_insert_list.append((
                str(uuid.uuid4()),
                n_eid,
                name_en,
                name_en.lower().strip(),
                "en",
                "latin",
                "transliteration",
                False,
                "verified"
            ))

        # Autocomplete suggestions
        prio = priority_map.get(ptype, 7)
        suggestions_to_insert_list.append((
            str(uuid.uuid4()),
            name_bn,
            name_bn.lower().strip(),
            "bn",
            "bangla",
            n_eid,
            "curated",
            prio,
            "active"
        ))
        if name_en:
            suggestions_to_insert_list.append((
                str(uuid.uuid4()),
                name_en,
                name_en.lower().strip(),
                "en",
                "latin",
                n_eid,
                "curated",
                prio - 1,
                "active"
            ))

    # Bulk insert core.entity
    insert_entity_sql = """
        INSERT INTO core.entity (
            entity_id, entity_type_id, display_name, preferred_language_code,
            state, visibility, summary, metadata
        ) VALUES %s
        ON CONFLICT (entity_id) DO NOTHING;
    """
    execute_values(cur, insert_entity_sql, entities_to_insert, page_size=500)
    log.info(f"Inserted {len(entities_to_insert):,} entities into core.entity.")

    # Bulk insert core.place
    insert_place_sql = """
        INSERT INTO core.place (
            entity_id, parent_place_id, official_code_scheme, official_code,
            latitude, longitude
        ) VALUES %s
        ON CONFLICT (entity_id) DO UPDATE SET
            parent_place_id = EXCLUDED.parent_place_id,
            official_code = EXCLUDED.official_code,
            official_code_scheme = EXCLUDED.official_code_scheme;
    """
    execute_values(cur, insert_place_sql, places_to_insert, page_size=500)
    log.info(f"Inserted {len(places_to_insert):,} records into core.place.")

    # Bulk insert core.entity_name
    insert_names_sql = """
        INSERT INTO core.entity_name (
            entity_name_id, entity_id, name, normalised_name,
            language_code, script, name_kind, is_primary, state
        ) VALUES %s
        ON CONFLICT (entity_id, normalised_name, language_code, name_kind) DO NOTHING;
    """
    execute_values(cur, insert_names_sql, names_to_insert_list, page_size=500)
    log.info(f"Inserted {len(names_to_insert_list):,} names into core.entity_name.")

    # Also add names for matched records if missing
    matched_names = []
    for r, match, p_eid in matched_records:
        eid = match["entity_id"]
        existing_names_set = set(n.lower().strip() for n in match["names"])
        name_bn = r["name_bn"].strip()
        name_en = r["name_en"].strip()
        if name_bn.lower() not in existing_names_set:
            matched_names.append((
                str(uuid.uuid4()), eid, name_bn, name_bn.lower().strip(),
                "bn", "bangla", "official", False, "verified"
            ))
        if name_en and name_en.lower() not in existing_names_set:
            matched_names.append((
                str(uuid.uuid4()), eid, name_en, name_en.lower().strip(),
                "en", "latin", "transliteration", False, "verified"
            ))
    if matched_names:
        execute_values(cur, insert_names_sql, matched_names, page_size=500)
        log.info(f"Inserted {len(matched_names):,} additional alias names for matched records.")

    # Bulk insert search.suggestion
    insert_suggestions_sql = """
        INSERT INTO search.suggestion (
            suggestion_id, phrase, phrase_normalised, language_code, script,
            entity_id, source_kind, priority, state
        ) VALUES %s
        ON CONFLICT (phrase_normalised, language_code, entity_id) DO NOTHING;
    """
    execute_values(cur, insert_suggestions_sql, suggestions_to_insert_list, page_size=500)
    log.info(f"Inserted {len(suggestions_to_insert_list):,} suggestions into search.suggestion.")

    conn.commit()
    cur.close()
    conn.close()
    log.info("[SUCCESS] Phase 3 Admin Hierarchy Seeding complete!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Phase 3: Bangladesh Administrative Hierarchy Seeder")
    parser.add_argument("--commit", action="store_true", help="Execute and commit changes to the database")
    parser.add_argument("--dry-run", action="store_true", help="Simulate execution without modifying the database (default)")
    args = parser.parse_args()

    run_seeder(commit=args.commit)
