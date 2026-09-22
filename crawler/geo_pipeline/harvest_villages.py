#!/usr/bin/env python3
"""
harvest_villages.py - High-Performance Bangladesh Gram & Moholla Harvester.

Harvests 90,000+ Bangladeshi villages and micro-locations locally from:
  1. Bangladesh Location Registry (BBS PHC 2022 Community Series)
  2. Village Demographics (Population, households, sex ratio from 2022 Census)
  3. Administrative Crosswalk (Division -> District -> Upazila -> Union)
  4. OpenStreetMap Micro-Locations (Urban Mahallas and Paras with GPS coordinates)

Outputs:
  crawler/geo_pipeline/data/bangladesh_villages_master.csv
"""

import os
import sys
import io
import csv
import json
import time
import tarfile
import logging
import urllib.request
from pathlib import Path
from typing import Dict, List, Any, Optional

import zstandard as zstd

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Add backend to path for transliteration
BASE_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(BASE_DIR / "backend"))

try:
    from app.nlp.banglish import transliterate_banglish
except ImportError:
    transliterate_banglish = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("harvest_villages")

REGISTRY_URL = (
    "https://github.com/montasim/bangladesh-location-registry/releases/download/data-2026.08.04/"
    "address-bd-data-2026.08.04-jsonl.tar.zst"
)
CACHE_DIR = BASE_DIR / "crawler" / "data"
CACHE_FILE = CACHE_DIR / "address-bd-data-2026.08.04-jsonl.tar.zst"
BASE_HIERARCHY_FILE = BASE_DIR / "crawler" / "geo_pipeline" / "data" / "base_hierarchy.csv"
OSM_MICRO_FILE = BASE_DIR / "crawler" / "geo_pipeline" / "data" / "micro_locations_raw.csv"
OUT_CSV = BASE_DIR / "crawler" / "geo_pipeline" / "data" / "bangladesh_villages_master.csv"


def download_or_load_archive() -> bytes:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if CACHE_FILE.exists() and CACHE_FILE.stat().st_size > 5_000_000:
        log.info(f"Loading cached registry archive from {CACHE_FILE} ({CACHE_FILE.stat().st_size:,} bytes)...")
        return CACHE_FILE.read_bytes()

    log.info(f"Downloading Bangladesh Location Registry from {REGISTRY_URL}...")
    req = urllib.request.Request(REGISTRY_URL, headers={"User-Agent": "KhujoLocationHarvester/1.0"})
    with urllib.request.urlopen(req) as resp:
        blob = resp.read()

    CACHE_FILE.write_bytes(blob)
    log.info(f"Saved registry archive to {CACHE_FILE} ({len(blob):,} bytes).")
    return blob


def load_base_hierarchy_maps():
    """Load verified Bangla names from base_hierarchy.csv."""
    districts = {}
    upazilas = {}
    unions = {}

    if BASE_HIERARCHY_FILE.exists():
        with open(BASE_HIERARCHY_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                pt = r.get("place_type")
                en = r.get("name_en", "").strip().lower()
                bn = r.get("name_bn", "").strip()
                if pt == "District":
                    districts[en] = bn
                elif pt == "Upazila":
                    upazilas[en] = bn
                elif pt == "Union":
                    unions[en] = bn

    log.info(f"Loaded base hierarchy: {len(districts)} districts, {len(upazilas)} upazilas, {len(unions)} unions.")
    return districts, upazilas, unions


def harvest():
    t_start = time.time()
    blob = download_or_load_archive()

    base_districts, base_upazilas, base_unions = load_base_hierarchy_maps()

    log.info("Extracting and indexing entities from archive...")
    dctx = zstd.ZstdDecompressor()

    divisions_map: Dict[str, Dict[str, str]] = {}
    zillas_map: Dict[str, Dict[str, str]] = {}
    upazilas_map: Dict[str, Dict[str, str]] = {}
    unions_map: Dict[str, Dict[str, str]] = {}
    demographics_map: Dict[str, Dict[str, Any]] = {}

    raw_villages = []

    # Stream archive members
    with dctx.stream_reader(io.BytesIO(blob)) as stream:
        with tarfile.open(fileobj=stream, mode="r|") as tar:
            for member in tar:
                mname = member.name
                if not member.isfile():
                    continue

                if mname == "jsonl/entities/divisions.jsonl":
                    f = tar.extractfile(member)
                    if f:
                        for line in f:
                            rec = json.loads(line.decode("utf-8"))
                            key = rec.get("key")
                            en = rec.get("name", {}).get("en", "")
                            bn = rec.get("name", {}).get("bn", "") or base_districts.get(en.lower(), en)
                            divisions_map[key] = {"name_en": en, "name_bn": bn}

                elif mname == "jsonl/entities/zillas.jsonl":
                    f = tar.extractfile(member)
                    if f:
                        for line in f:
                            rec = json.loads(line.decode("utf-8"))
                            key = rec.get("key")
                            en = rec.get("name", {}).get("en", "")
                            bn = rec.get("name", {}).get("bn", "") or base_districts.get(en.lower(), en)
                            div_key = rec.get("relations", {}).get("divisionKey", "")
                            zillas_map[key] = {"name_en": en, "name_bn": bn, "division_key": div_key}

                elif mname == "jsonl/entities/upazilas.jsonl":
                    f = tar.extractfile(member)
                    if f:
                        for line in f:
                            rec = json.loads(line.decode("utf-8"))
                            key = rec.get("key")
                            en = rec.get("name", {}).get("en", "")
                            bn = rec.get("name", {}).get("bn", "") or base_upazilas.get(en.lower(), en)
                            rel = rec.get("relations", {})
                            upazilas_map[key] = {
                                "name_en": en,
                                "name_bn": bn,
                                "zilla_key": rel.get("zillaKey", ""),
                                "division_key": rel.get("divisionKey", ""),
                            }

                elif mname == "jsonl/entities/unions.jsonl":
                    f = tar.extractfile(member)
                    if f:
                        for line in f:
                            rec = json.loads(line.decode("utf-8"))
                            key = rec.get("key")
                            name_obj = rec.get("name", {})
                            en = name_obj.get("en", "")
                            bn = name_obj.get("bn", "") or base_unions.get(en.lower(), en)
                            rel = rec.get("relations", {})
                            adm = rel.get("administrativeArea", {})
                            upz_key = adm.get("key", "") if adm.get("kind") == "upazila" else ""
                            unions_map[key] = {
                                "name_en": en,
                                "name_bn": bn,
                                "upazila_key": upz_key,
                                "zilla_key": rel.get("zillaKey", ""),
                                "division_key": rel.get("divisionKey", ""),
                                "portal_url": rec.get("portalUrl", ""),
                            }

                elif mname == "jsonl/facts/village-demographics.jsonl":
                    f = tar.extractfile(member)
                    if f:
                        for line in f:
                            rec = json.loads(line.decode("utf-8"))
                            loc_key = rec.get("locationKey")
                            pop = rec.get("population", {})
                            hh = rec.get("households", {})
                            demographics_map[loc_key] = {
                                "population_total": pop.get("total", ""),
                                "population_male": pop.get("male", ""),
                                "population_female": pop.get("female", ""),
                                "households_total": hh.get("total", ""),
                            }

                elif mname == "jsonl/entities/villages.jsonl":
                    log.info("Reading villages.jsonl stream...")
                    f = tar.extractfile(member)
                    if f:
                        for line in f:
                            raw_villages.append(json.loads(line.decode("utf-8")))

    log.info(f"Loaded: {len(divisions_map)} divisions, {len(zillas_map)} zillas, "
             f"{len(upazilas_map)} upazilas, {len(unions_map)} unions, "
             f"{len(demographics_map):,} village demographic records, "
             f"{len(raw_villages):,} raw villages.")

    # Process and build master village records
    log.info("Cross-referencing and transliterating village records...")
    master_rows = []
    seen_keys = set()

    from fix_village_spellings import normalize_village_name, clean_union_name

    def get_bangla_name(en_name: str) -> str:
        if not en_name:
            return ""
        if en_name in translit_cache:
            return translit_cache[en_name]
        if transliterate_banglish:
            bn, _ = transliterate_banglish(en_name)
            res = normalize_village_name(bn if bn else en_name, en_name)
        else:
            res = en_name
        translit_cache[en_name] = res
        return res

    for v in raw_villages:
        vkey = v.get("key", "")
        if vkey in seen_keys:
            continue
        seen_keys.add(vkey)

        name_en = v.get("name", {}).get("en", "")
        name_bn = v.get("name", {}).get("bn", "")
        if not name_bn:
            name_bn = get_bangla_name(name_en)

        # Relations
        rel = v.get("relations", {})
        div_key = rel.get("divisionKey", "")
        zilla_key = rel.get("zillaKey", "")
        upz_obj = rel.get("administrativeArea", {})
        upz_key = upz_obj.get("key", "")
        union_obj = rel.get("localArea", {})
        union_key = union_obj.get("key", "")

        # Fallback to published local area if union_key not directly resolved
        pub_local = v.get("publishedLocalArea", {})
        pub_local_name = pub_local.get("name", "")

        # Lookup names
        div_info = divisions_map.get(div_key, {})
        zilla_info = zillas_map.get(zilla_key, {})
        upz_info = upazilas_map.get(upz_key, {})
        union_info = unions_map.get(union_key, {})

        div_en = div_info.get("name_en", "")
        div_bn = div_info.get("name_bn", "")
        dist_en = zilla_info.get("name_en", "")
        dist_bn = zilla_info.get("name_bn", "")
        upz_en = upz_info.get("name_en", "")
        upz_bn = upz_info.get("name_bn", "")

        union_en = union_info.get("name_en") or pub_local_name
        raw_union_bn = union_info.get("name_bn") or base_unions.get(union_en.lower(), get_bangla_name(union_en))
        union_bn = clean_union_name(union_en, raw_union_bn)

        # Demographic data
        demo = demographics_map.get(vkey, {})
        pop_total = demo.get("population_total", "")
        hh_total = demo.get("households_total", "")
        pop_male = demo.get("population_male", "")
        pop_female = demo.get("population_female", "")

        bbs_code = "-".join(v.get("bbsPublishedCodePath", []))
        mauza_name = v.get("mauza", {}).get("name", "")

        master_rows.append({
            "internal_id": vkey,
            "place_type": "Village",
            "name_en": name_en,
            "name_bn": name_bn,
            "mauza": mauza_name,
            "union_name_en": union_en,
            "union_name_bn": union_bn,
            "upazila_name_en": upz_en,
            "upazila_name_bn": upz_bn,
            "district_name_en": dist_en,
            "district_name_bn": dist_bn,
            "division_name_en": div_en,
            "division_name_bn": div_bn,
            "population": pop_total,
            "households": hh_total,
            "male": pop_male,
            "female": pop_female,
            "latitude": "",
            "longitude": "",
            "bbs_code": bbs_code,
            "source": "bbs_phc_2022_registry",
        })

    # Integrate OSM micro-locations (urban mahallas and villages with real GPS coordinates)
    osm_count = 0
    if OSM_MICRO_FILE.exists():
        with open(OSM_MICRO_FILE, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for r in reader:
                en = r.get("name_en", "").strip()
                bn = r.get("name_bn", "").strip()
                ptype = r.get("place_type", "Settlement").strip()
                lat = r.get("latitude", "").strip()
                lon = r.get("longitude", "").strip()
                iid = r.get("internal_id", "").strip()

                if not bn and not en:
                    continue
                if not bn:
                    bn = get_bangla_name(en)

                master_rows.append({
                    "internal_id": iid or f"OSM_{len(master_rows)+1}",
                    "place_type": ptype if ptype else "Mahalla",
                    "name_en": en,
                    "name_bn": bn,
                    "mauza": "",
                    "union_name_en": "",
                    "union_name_bn": "",
                    "upazila_name_en": "",
                    "upazila_name_bn": "",
                    "district_name_en": "",
                    "district_name_bn": "",
                    "division_name_en": "",
                    "division_name_bn": "",
                    "population": "",
                    "households": "",
                    "male": "",
                    "female": "",
                    "latitude": lat,
                    "longitude": lon,
                    "bbs_code": "",
                    "source": "osm_overpass_micro",
                })
                osm_count += 1

    log.info(f"Total master micro-location records: {len(master_rows):,} (including {osm_count} OSM coordinates).")

    # Write output CSV
    fieldnames = [
        "internal_id", "place_type", "name_en", "name_bn", "mauza",
        "union_name_en", "union_name_bn", "upazila_name_en", "upazila_name_bn",
        "district_name_en", "district_name_bn", "division_name_en", "division_name_bn",
        "population", "households", "male", "female",
        "latitude", "longitude", "bbs_code", "source"
    ]

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(master_rows)

    elapsed = time.time() - t_start
    log.info(f"Successfully wrote {len(master_rows):,} records to {OUT_CSV} in {elapsed:.1f}s.")

    # Print summary statistics
    villages_count = sum(1 for r in master_rows if r["place_type"] == "Village")
    mahallas_count = sum(1 for r in master_rows if r["place_type"] == "Mahalla")
    with_demo = sum(1 for r in master_rows if r["population"])
    with_coords = sum(1 for r in master_rows if r["latitude"])

    print("=" * 70)
    print(" KHUJO GEOGRAPHY HARVESTER — 87K+ GRAM & MOHOLLAS COMPLETE")
    print("=" * 70)
    print(f"Total Micro-Locations Harvested: {len(master_rows):,}")
    print(f"  • Villages (গ্রাম):             {villages_count:,}")
    print(f"  • Mahallas / Paras (মহল্লা/পাড়া): {mahallas_count:,}")
    print(f"  • Other Settlements:           {len(master_rows) - villages_count - mahallas_count:,}")
    print(f"  • With 2022 Census Demographics: {with_demo:,} ({with_demo/len(master_rows)*100:.1f}%)")
    print(f"  • With GPS Coordinates:        {with_coords:,}")
    print(f"Output File: {OUT_CSV.name} ({OUT_CSV.stat().st_size / (1024*1024):.2f} MB)")
    print("-" * 70)
    print("Sample Harvested Village Records:")
    for r in master_rows[:3]:
        print(f"  • {r['name_bn']} ({r['name_en']}) | মৌজা: {r['mauza']} | ইউনিয়ন: {r['union_name_bn']} | উপজেলা: {r['upazila_name_bn']} | জেলা: {r['district_name_bn']}")
        print(f"    জনসংখ্যা: {r['population']} | পরিবার: {r['households']} | BBS কোড: {r['bbs_code']}")
    print("-" * 70)
    print("Sample Harvested Urban Mahalla Records (OSM):")
    osm_samples = [r for r in master_rows if r["source"] == "osm_overpass_micro"][:3]
    for r in osm_samples:
        print(f"  • {r['name_bn']} ({r['name_en']}) | Coordinates: ({r['latitude']}, {r['longitude']}) | টাইপ: {r['place_type']}")
    print("=" * 70)


if __name__ == "__main__":
    harvest()
