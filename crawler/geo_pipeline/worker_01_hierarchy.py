import argparse
import asyncio
import csv
import logging
import os
from typing import List, Dict

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("worker_01_hierarchy")

BASE_URL = "https://raw.githubusercontent.com/nuhil/bangladesh-geocode/master"
OUT_FILE = os.path.join(os.path.dirname(__file__), "data", "base_hierarchy.csv")

async def fetch_json(client: httpx.AsyncClient, endpoint: str):
    url = f"{BASE_URL}/{endpoint}"
    log.info(f"Fetching {url}...")
    resp = await client.get(url, timeout=15.0)
    resp.raise_for_status()
    # The JSON files in this repo wrap data in a list where the 3rd element is a dict with a 'data' key
    # e.g., [{"type":"header",...}, {"type":"schema",...}, {"type":"table", "data": [...]}]
    try:
        json_data = resp.json()
        for section in json_data:
            if isinstance(section, dict) and section.get('type') == 'table' and 'data' in section:
                return section['data']
        # Fallback if structure is different
        return json_data
    except Exception as e:
        log.error(f"Failed parsing {url}: {e}")
        return []

def extract_entity_id(record: Dict, key: str) -> str:
    """Safely extract ID from record to build reproducible UUIDs or string IDs."""
    return str(record.get(key, ""))

async def collect_data():
    """Phase 1: Run & Collect base hierarchy."""
    async with httpx.AsyncClient() as client:
        divisions_raw, districts_raw, upazilas_raw, unions_raw = await asyncio.gather(
            fetch_json(client, "divisions/divisions.json"),
            fetch_json(client, "districts/districts.json"),
            fetch_json(client, "upazilas/upazilas.json"),
            fetch_json(client, "unions/unions.json")
        )
    
    log.info(f"Fetched {len(divisions_raw)} divisions, {len(districts_raw)} districts, "
             f"{len(upazilas_raw)} upazilas, {len(unions_raw)} unions.")

    rows = []
    
    # Process Divisions
    for d in divisions_raw:
        rows.append({
            "place_type": "Division",
            "internal_id": f"DIV_{d['id']}",
            "parent_id": "BD",  # Top level
            "name_en": d['name'],
            "name_bn": d['bn_name'],
            "latitude": d.get('lat', ''),
            "longitude": d.get('long', ''),
            "website": d.get('url', '')
        })

    # Process Districts
    for d in districts_raw:
        rows.append({
            "place_type": "District",
            "internal_id": f"DIST_{d['id']}",
            "parent_id": f"DIV_{d['division_id']}",
            "name_en": d['name'],
            "name_bn": d['bn_name'],
            "latitude": d.get('lat', ''),
            "longitude": d.get('long', ''),
            "website": d.get('url', '')
        })

    # Process Upazilas
    for d in upazilas_raw:
        rows.append({
            "place_type": "Upazila",
            "internal_id": f"UPA_{d['id']}",
            "parent_id": f"DIST_{d['district_id']}",
            "name_en": d['name'],
            "name_bn": d['bn_name'],
            "latitude": "", # Upazila lat/lon might not be present in this dataset
            "longitude": "",
            "website": d.get('url', '')
        })

    # Process Unions
    for d in unions_raw:
        rows.append({
            "place_type": "Union",
            "internal_id": f"UNI_{d['id']}",
            "parent_id": f"UPA_{d['upazilla_id']}",
            "name_en": d['name'],
            "name_bn": d['bn_name'],
            "latitude": "",
            "longitude": "",
            "website": d.get('url', '')
        })

    # Write to CSV
    fields = ["place_type", "internal_id", "parent_id", "name_en", "name_bn", "latitude", "longitude", "website"]
    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
    with open(OUT_FILE, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    
    log.info(f"Successfully collected {len(rows)} records into {OUT_FILE}.")
    log.info("Phase 1 Collect complete. Run spot-check on the CSV, then execute with --commit to push to DB.")

def commit_to_db():
    """Upsert the collected CSV data into Neon DB using proper place hierarchy."""
    log.info("Commit logic to be implemented. Connecting to Neon DB...")
    # NOTE: To be implemented in next step once we verify the schema mapping.
    log.error("Commit not yet fully implemented. Spot check the CSV first!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Geo Pipeline Worker 1: Base Hierarchy")
    parser.add_argument("--commit", action="store_true", help="Push data to DB")
    args = parser.parse_args()
    
    if args.commit:
        commit_to_db()
    else:
        asyncio.run(collect_data())
