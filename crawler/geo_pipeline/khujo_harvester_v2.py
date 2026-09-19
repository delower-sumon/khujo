#!/usr/bin/env python3
"""
khujo_harvester_v2.py — The Ultimate Khujo Bangladesh Geography Harvester
=========================================================================

Replaces worker_01_hierarchy.py and worker_02_micro_locations.py.

5-Stage Pipeline:
    Stage 1: Load existing admin hierarchy (base_hierarchy.csv)
    Stage 2: Fetch OSM micro-locations via 1x1 degree bbox tiling over Bangladesh
    Stage 3: Fetch Union boundary GeoJSON polygons from OSM (admin_level=7)
    Stage 4: Spatial crosswalk -- point-in-polygon assigns parent_id to every micro-location
    Stage 5: Merge, dedupe, write khujo_locations_master.csv

Works in: local PC, GitHub Actions, Google Colab

Install:
    pip install requests shapely

Run (fast smoke-test, no network):
    python khujo_harvester_v2.py --skip-osm

Run (full harvest, CSV only):
    python khujo_harvester_v2.py --base-hierarchy crawler/geo_pipeline/data/base_hierarchy.csv

Run (full harvest + push to Neon staging table):
    python khujo_harvester_v2.py --db-url "$DATABASE_URL"

SAFETY RULES:
  - Never writes to production. All DB output goes to khujo_location_staging.
  - Every row carries source + source_confidence + resolution_status.
  - Existing admin rows (Division/District/Upazila/Union) always win on conflict.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import os
import re
import sys
import time
import unicodedata
import urllib.parse
from collections import defaultdict
from pathlib import Path
from typing import Any

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    import urllib.request
    HAS_REQUESTS = False
    print("[WARN] 'requests' not installed. Using urllib fallback. pip install requests")

try:
    from shapely.geometry import Point, shape
    from shapely.strtree import STRtree
    HAS_SHAPELY = True
except ImportError:
    HAS_SHAPELY = False
    print("[WARN] 'shapely' not installed. Spatial crosswalk will be skipped. pip install shapely")

try:
    import psycopg
    from psycopg import sql as psql
    HAS_PSYCOPG = True
except ImportError:
    HAS_PSYCOPG = False

# ────────────────────────── CONFIG ────────────────────────────────────────

# Bangladesh bounding box (south, north, west, east)
BD_BBOX = (20.35, 26.75, 88.00, 92.70)

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

USER_AGENT = "KhujoHarvesterV2/1.0 (Khujo Bangla Search; research use)"

# OSM place tags -> Khujo taxonomy
OSM_PLACE_TYPES: dict[str, str] = {
    "village":       "Village",
    "hamlet":        "Mouza",
    "suburb":        "Mahalla",
    "neighbourhood": "Mahalla",
    "quarter":       "Mahalla",
    "locality":      "Locality",
}

CSV_FIELDS = [
    "place_type", "internal_id", "parent_id",
    "name_en", "name_bn",
    "latitude", "longitude", "website",
    "source", "source_ref", "source_confidence",
    "resolution_status", "normalized_en", "normalized_bn",
    "aliases_json", "fetched_at",
]

DEFAULT_STAGING_TABLE = "khujo_location_staging"


# ────────────────────────── HELPERS ────────────────────────────────────────

def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def clean(v: Any) -> str:
    if v is None:
        return ""
    return re.sub(r"\s+", " ", str(v).strip())


def normalize(v: Any) -> str:
    """Deterministic normalizer for Bangla+English matching. No transliteration."""
    s = clean(v).casefold()
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("&", " and ")
    s = re.sub(r"[^a-z0-9\u0980-\u09ff]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def stable_id(prefix: str, *parts: Any) -> str:
    """SHA1-based deterministic ID that won't collide across sources."""
    raw = "|".join(normalize(p) for p in parts)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def valid_bd_coord(lat: Any, lon: Any) -> bool:
    try:
        return 20.0 <= float(lat) <= 27.2 and 87.5 <= float(lon) <= 93.2
    except Exception:
        return False


def canonical_row(**kw: Any) -> dict[str, Any]:
    row: dict[str, Any] = {k: "" for k in CSV_FIELDS}
    for k, v in kw.items():
        if k in row:
            row[k] = v
    row["name_en"]           = clean(row["name_en"])
    row["name_bn"]           = clean(row["name_bn"])
    row["normalized_en"]     = normalize(row["name_en"])
    row["normalized_bn"]     = normalize(row["name_bn"])
    row["resolution_status"] = row["resolution_status"] or "candidate"
    row["source_confidence"] = row["source_confidence"] or "medium"
    row["fetched_at"]        = row["fetched_at"] or utc_now()
    row["aliases_json"]      = row["aliases_json"] or "[]"
    return row


def http_post_overpass(url: str, query: str, timeout: int = 150) -> bytes:
    headers = {
        "User-Agent": USER_AGENT,
        "Content-Type": "application/x-www-form-urlencoded",
    }
    if HAS_REQUESTS:
        r = requests.post(url, data={"data": query}, headers=headers, timeout=timeout)
        r.raise_for_status()
        return r.content
    encoded = urllib.parse.urlencode({"data": query}).encode()
    req = urllib.request.Request(url, data=encoded, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def overpass_post(query: str, retries: int = 5, base_delay: float = 4.0) -> dict[str, Any]:
    """POST to Overpass with exponential backoff across multiple endpoints."""
    last_err: Exception | None = None
    for endpoint in OVERPASS_ENDPOINTS:
        for attempt in range(retries):
            try:
                raw = http_post_overpass(endpoint, query)
                data = json.loads(raw.decode("utf-8"))
                if "elements" in data:
                    return data
            except Exception as exc:
                last_err = exc
                wait = base_delay * (2 ** attempt) + (time.time() % 1)  # jitter
                print(f"  [retry {attempt+1}/{retries}] {endpoint}: {exc} -> waiting {wait:.1f}s")
                time.sleep(wait)
    raise RuntimeError(f"All Overpass endpoints failed: {last_err}")


# ────────────────────────── STAGE 1: LOAD EXISTING ────────────────────────

def load_existing(base_path: str, micro_path: str | None = None) -> tuple[list[dict], dict]:
    """Load admin hierarchy and any previously collected micro-locations."""
    rows: list[dict] = []
    by_id: dict[str, dict] = {}

    sources = [(base_path, "khujo_admin_hierarchy", "high", "existing")]
    if micro_path and Path(micro_path).exists():
        sources.append((micro_path, "khujo_micro_osm", "medium", "osm_candidate"))

    for path, source, confidence, status in sources:
        with open(path, encoding="utf-8-sig", newline="") as f:
            for raw in csv.DictReader(f):
                rid = clean(raw.get("internal_id", ""))
                if not rid or rid in by_id:
                    continue
                row = canonical_row(
                    place_type=clean(raw.get("place_type")),
                    internal_id=rid,
                    parent_id=clean(raw.get("parent_id")),
                    name_en=raw.get("name_en"),
                    name_bn=raw.get("name_bn"),
                    latitude=clean(raw.get("latitude")),
                    longitude=clean(raw.get("longitude")),
                    website=clean(raw.get("website")),
                    source=source,
                    source_ref=path,
                    source_confidence=confidence,
                    resolution_status=status,
                )
                by_id[rid] = row
                rows.append(row)

    admin_count = sum(1 for r in rows if r["place_type"] in {"Division", "District", "Upazila", "Union"})
    print(f"  [Stage 1] Loaded {len(rows):,} rows ({admin_count:,} admin hierarchy)")
    return rows, by_id


# ────────────────────────── STAGE 2: OSM BBOX CRAWL ──────────────────────

def bbox_tiles(south: float, north: float, west: float, east: float, step: float = 1.0):
    """Generate 1x1 degree tiles. Avoids admin-tag dependency on OSM."""
    lat = south
    while lat < north:
        lat_n = min(lat + step, north)
        lon = west
        while lon < east:
            lon_e = min(lon + step, east)
            yield (lat, lat_n, lon, lon_e)
            lon = lon_e
        lat = lat_n


def osm_micro_query(s: float, n: float, w: float, e: float) -> str:
    types = "|".join(f"^{t}$" for t in OSM_PLACE_TYPES)
    return f"""[out:json][timeout:90];
(
  node[place~"{types}"]({s},{w},{n},{e});
  way[place~"{types}"]({s},{w},{n},{e});
  relation[place~"{types}"]({s},{w},{n},{e});
);
out center tags;"""


def osm_elements_to_rows(elements: list[dict]) -> list[dict]:
    out = []
    for el in elements:
        tags = el.get("tags") or {}
        place_tag = clean(tags.get("place", "")).lower()
        if place_tag not in OSM_PLACE_TYPES:
            continue

        # Khujo is Bangla-first: skip records without a Bengali name
        name_bn = clean(tags.get("name:bn") or tags.get("name:bn-BD") or tags.get("official_name:bn"))
        name_en = clean(tags.get("name:en") or tags.get("official_name:en") or tags.get("name"))
        if not name_bn:
            continue

        if el.get("type") == "node":
            lat, lon = el.get("lat"), el.get("lon")
        else:
            center = el.get("center") or {}
            lat, lon = center.get("lat"), center.get("lon")

        if not valid_bd_coord(lat, lon):
            continue

        osm_id = f"OSM_{el['type']}_{el['id']}"
        aliases = json.dumps({
            k: tags.get(k, "") for k in ["name", "name:en", "name:bn", "alt_name", "old_name"]
        }, ensure_ascii=False)

        out.append(canonical_row(
            place_type=OSM_PLACE_TYPES[place_tag],
            internal_id=osm_id,
            parent_id="",  # Resolved in Stage 4
            name_en=name_en,
            name_bn=name_bn,
            latitude=str(lat),
            longitude=str(lon),
            website=clean(tags.get("website") or tags.get("contact:website")),
            source="openstreetmap_overpass",
            source_ref="(c) OpenStreetMap contributors",
            source_confidence="medium",
            resolution_status="osm_candidate",
            aliases_json=aliases,
        ))
    return out


def harvest_osm_micros(step: float = 1.0, pause: float = 2.0) -> list[dict]:
    """Tile the Bangladesh bbox and collect all micro-location candidates."""
    rows: list[dict] = []
    seen: set[str] = set()
    tiles = list(bbox_tiles(*BD_BBOX, step=step))
    total = len(tiles)

    for i, tile in enumerate(tiles, 1):
        s, n, w, e = tile
        print(f"  [OSM tile {i}/{total}] bbox({s:.1f},{n:.1f},{w:.1f},{e:.1f})", end=" ", flush=True)
        try:
            data = overpass_post(osm_micro_query(s, n, w, e))
            chunk = osm_elements_to_rows(data.get("elements", []))
            new = 0
            for r in chunk:
                if r["internal_id"] not in seen:
                    seen.add(r["internal_id"])
                    rows.append(r)
                    new += 1
            print(f"-> {new} new rows (total: {len(rows):,})")
        except Exception as exc:
            print(f"-> FAILED: {exc}")
        time.sleep(pause)

    print(f"  [Stage 2] OSM complete: {len(rows):,} Bengali micro-locations")
    return rows


# ────────────────────────── STAGE 3: UNION BOUNDARIES ─────────────────────

def fetch_union_boundaries() -> list[dict]:
    """Fetch Union admin boundary relations from OSM (admin_level=7 = Union in Bangladesh)."""
    if not HAS_SHAPELY:
        print("  [Stage 3] Skipped -- shapely not installed.")
        return []

    query = """[out:json][timeout:300];
area["ISO3166-1"="BD"][admin_level=2]->.bd;
rel[admin_level=7](area.bd);
out geom;"""

    print("  [Stage 3] Fetching Union boundary polygons from OSM (admin_level=7)...")
    try:
        data = overpass_post(query, retries=3)
        elements = data.get("elements", [])
        print(f"  [Stage 3] Retrieved {len(elements):,} Union relations")
        return elements
    except Exception as exc:
        print(f"  [Stage 3] FAILED: {exc}")
        return []


def build_union_spatial_index(
    union_elements: list[dict],
    admin_rows: list[dict],
) -> tuple[Any | None, list[dict] | None]:
    """Build Shapely STRtree from Union polygons, linked to Khujo internal IDs."""
    if not HAS_SHAPELY or not union_elements:
        return None, None

    # Lookup: normalized name -> Khujo UNI_xxx ID
    union_by_name: dict[str, str] = {}
    for row in admin_rows:
        if row["place_type"] == "Union":
            if row["normalized_bn"]:
                union_by_name[row["normalized_bn"]] = row["internal_id"]
            if row["normalized_en"]:
                union_by_name[row["normalized_en"]] = row["internal_id"]

    geoms = []
    meta = []

    for el in union_elements:
        tags = el.get("tags") or {}
        name_bn = clean(tags.get("name:bn") or tags.get("name:local", ""))
        name_en = clean(tags.get("name:en") or tags.get("name", ""))

        try:
            outer_rings = []
            for member in el.get("members", []):
                if member.get("role") == "outer" and member.get("geometry"):
                    ring = [(g["lon"], g["lat"]) for g in member["geometry"]]
                    if ring and ring[0] != ring[-1]:
                        ring.append(ring[0])
                    if len(ring) >= 4:
                        outer_rings.append(ring)

            if not outer_rings:
                continue

            geojson_poly = {"type": "Polygon", "coordinates": outer_rings}
            polygon = shape(geojson_poly)
            if not polygon.is_valid:
                polygon = polygon.buffer(0)

            khujo_id = (
                union_by_name.get(normalize(name_bn))
                or union_by_name.get(normalize(name_en))
                or ""
            )

            geoms.append(polygon)
            meta.append({"name_bn": name_bn, "name_en": name_en,
                          "khujo_id": khujo_id, "osm_id": el.get("id")})
        except Exception:
            continue

    if not geoms:
        print("  [Stage 3] No valid polygons built. Check OSM data coverage.")
        return None, None

    tree = STRtree(geoms)
    linked = sum(1 for m in meta if m["khujo_id"])
    print(f"  [Stage 3] Spatial index: {len(geoms):,} polygons ({linked:,} linked to Khujo Union IDs)")
    return tree, meta


# ────────────────────────── STAGE 4: SPATIAL CROSSWALK ────────────────────

MICRO_TYPES = {"Village", "Mouza", "Mahalla", "Locality", "Hamlet"}


def resolve_parents_spatially(
    rows: list[dict],
    tree: Any,
    union_meta: list[dict],
    geoms: list[Any] | None = None,
) -> None:
    """
    Point-in-polygon crosswalk. Mutates rows in-place.

    Sets resolution_status to:
      - "parent_resolved_spatial"  : matched to a Union polygon
      - "parent_unresolved"        : no polygon match; flag for manual review
    """
    if tree is None:
        print("  [Stage 4] Skipped -- no spatial index.")
        return

    # Get the actual geometry objects from the tree
    tree_geoms = list(tree.geometries)

    resolved = unresolved = 0
    for row in rows:
        if row.get("parent_id") or row["place_type"] not in MICRO_TYPES:
            continue

        try:
            pt = Point(float(row["longitude"]), float(row["latitude"]))
        except Exception:
            row["resolution_status"] = "parent_unresolved"
            unresolved += 1
            continue

        matched_id = ""
        # STRtree.query returns indices of candidate geometries
        for idx in tree.query(pt):
            try:
                if tree_geoms[idx].contains(pt):
                    m = union_meta[idx]
                    matched_id = m.get("khujo_id") or f"OSM_UNION_{m['osm_id']}"
                    break
            except Exception:
                continue

        if matched_id:
            row["parent_id"] = matched_id
            row["resolution_status"] = "parent_resolved_spatial"
            resolved += 1
        else:
            row["resolution_status"] = "parent_unresolved"
            unresolved += 1

    pct = f"{100*resolved/(resolved+unresolved):.1f}%" if (resolved+unresolved) > 0 else "N/A"
    print(f"  [Stage 4] Crosswalk: {resolved:,} resolved ({pct}) | {unresolved:,} unresolved")


# ────────────────────────── STAGE 5: MERGE & DEDUPE ──────────────────────

def merge_all(existing: list[dict], osm_rows: list[dict]) -> list[dict]:
    """
    Merge existing admin rows and new OSM micro-locations.
    Existing rows always win on internal_id conflict.
    Same normalized Bangla name at same rounded coordinate = duplicate.
    """
    result: list[dict] = []
    by_id: dict[str, dict] = {}
    name_coord_idx: dict[tuple, int] = {}

    def coord_key(row: dict) -> tuple | None:
        try:
            return (f"{round(float(row['latitude']), 4):.4f}",
                    f"{round(float(row['longitude']), 4):.4f}")
        except Exception:
            return None

    def add(row: dict) -> None:
        rid = row["internal_id"]
        if rid in by_id:
            return

        nn = row["normalized_bn"] or row["normalized_en"]
        ck = coord_key(row)

        if nn and ck:
            key = (row["place_type"], nn, ck[0])
            if key in name_coord_idx:
                old = result[name_coord_idx[key]]
                # Merge aliases
                try:
                    aliases = set()
                    for src in [old.get("aliases_json", "[]"), row.get("aliases_json", "[]")]:
                        obj = json.loads(src or "[]")
                        if isinstance(obj, list):
                            aliases.update(str(x) for x in obj)
                        elif isinstance(obj, dict):
                            aliases.update(str(v) for v in obj.values() if v)
                    if row.get("name_en"): aliases.add(row["name_en"])
                    if row.get("name_bn"): aliases.add(row["name_bn"])
                    old["aliases_json"] = json.dumps(sorted(x for x in aliases if x), ensure_ascii=False)
                except Exception:
                    pass
                # Promote parent if existing has none
                if not old.get("parent_id") and row.get("parent_id"):
                    old["parent_id"] = row["parent_id"]
                    old["resolution_status"] = row.get("resolution_status", old["resolution_status"])
                return

        idx = len(result)
        result.append(row)
        by_id[rid] = row
        if nn and ck:
            name_coord_idx[(row["place_type"], nn, ck[0])] = idx

    for r in existing:
        add(r)
    for r in osm_rows:
        add(r)

    return result


# ────────────────────────── REPORT ────────────────────────────────────────

def print_report(rows: list[dict]) -> None:
    type_counts: dict[str, int] = defaultdict(int)
    status_counts: dict[str, int] = defaultdict(int)
    coords = no_parent = no_bn = 0

    for r in rows:
        type_counts[r["place_type"]] += 1
        status_counts[r["resolution_status"]] += 1
        if valid_bd_coord(r.get("latitude"), r.get("longitude")):
            coords += 1
        if not r.get("parent_id"):
            no_parent += 1
        if not r.get("name_bn"):
            no_bn += 1

    print("\n" + "=" * 55)
    print("  KHUJO LOCATION HARVEST REPORT")
    print("=" * 55)
    print(f"  Total rows              : {len(rows):,}")
    print(f"  With coordinates        : {coords:,}")
    print(f"  Missing parent_id       : {no_parent:,}  <- target: 0")
    print(f"  Missing Bengali name    : {no_bn:,}  <- target: 0")
    print("\n  By place type:")
    for k, v in sorted(type_counts.items()):
        print(f"    {k:<22} {v:>8,}")
    print("\n  By resolution status:")
    for k, v in sorted(status_counts.items()):
        print(f"    {k:<35} {v:>8,}")
    print("=" * 55 + "\n")


# ────────────────────────── CSV I/O ────────────────────────────────────────

def write_master_csv(path: str, rows: list[dict]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in CSV_FIELDS})
    print(f"  Wrote {len(rows):,} rows -> {path}")


# ────────────────────────── DB IMPORT ──────────────────────────────────────

def import_to_neon(rows: list[dict], db_url: str, table: str, truncate: bool = False) -> None:
    if not HAS_PSYCOPG:
        print("[DB] psycopg not installed. Run: pip install psycopg[binary]")
        return

    def to_float(v: Any) -> float | None:
        try:
            return float(v) if str(v).strip() else None
        except Exception:
            return None

    with psycopg.connect(db_url) as conn:
        ident = psql.Identifier(table)
        conn.execute(psql.SQL("""
            CREATE TABLE IF NOT EXISTS {table} (
                place_type TEXT NOT NULL,
                internal_id TEXT PRIMARY KEY,
                parent_id TEXT,
                name_en TEXT,
                name_bn TEXT,
                latitude DOUBLE PRECISION,
                longitude DOUBLE PRECISION,
                website TEXT,
                source TEXT NOT NULL,
                source_ref TEXT,
                source_confidence TEXT,
                resolution_status TEXT,
                normalized_en TEXT,
                normalized_bn TEXT,
                aliases_json JSONB NOT NULL DEFAULT '[]'::jsonb,
                fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
        """).format(table=ident))

        for suf, col in [("_name", "normalized_bn"), ("_geo", "latitude"), ("_parent", "parent_id")]:
            conn.execute(psql.SQL("CREATE INDEX IF NOT EXISTS {} ON {} ({})").format(
                psql.Identifier(f"{table}{suf}_idx"), ident, psql.Identifier(col)
            ))
        conn.commit()

        if truncate:
            conn.execute(psql.SQL("TRUNCATE {}").format(ident))
            conn.commit()

        stmt = psql.SQL("""
            INSERT INTO {table} (
                place_type, internal_id, parent_id, name_en, name_bn,
                latitude, longitude, website, source, source_ref,
                source_confidence, resolution_status, normalized_en,
                normalized_bn, aliases_json, fetched_at
            ) VALUES (
                %(place_type)s, %(internal_id)s, %(parent_id)s, %(name_en)s, %(name_bn)s,
                %(latitude)s, %(longitude)s, %(website)s, %(source)s, %(source_ref)s,
                %(source_confidence)s, %(resolution_status)s, %(normalized_en)s,
                %(normalized_bn)s, %(aliases_json)s::jsonb, %(fetched_at)s::timestamptz
            )
            ON CONFLICT (internal_id) DO UPDATE SET
                parent_id         = COALESCE(NULLIF(EXCLUDED.parent_id, ''), {table}.parent_id),
                name_bn           = COALESCE(NULLIF(EXCLUDED.name_bn, ''), {table}.name_bn),
                latitude          = COALESCE(EXCLUDED.latitude, {table}.latitude),
                longitude         = COALESCE(EXCLUDED.longitude, {table}.longitude),
                source_confidence = EXCLUDED.source_confidence,
                resolution_status = EXCLUDED.resolution_status,
                aliases_json      = EXCLUDED.aliases_json,
                fetched_at        = EXCLUDED.fetched_at
        """).format(table=ident)

        prepared = [{**r, "latitude": to_float(r.get("latitude")), "longitude": to_float(r.get("longitude"))}
                    for r in rows]

        with conn.cursor() as cur:
            cur.executemany(stmt, prepared)
        conn.commit()
        print(f"[DB] Imported {len(prepared):,} rows into staging table '{table}'")


# ────────────────────────── CLI / MAIN ────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Khujo Bangladesh Geography Harvester v2")
    p.add_argument("--base-hierarchy",
                   default="crawler/geo_pipeline/data/base_hierarchy.csv")
    p.add_argument("--micro-locations", default=None,
                   help="Optional previous micro_locations_raw.csv to include")
    p.add_argument("--output",
                   default="crawler/geo_pipeline/data/khujo_locations_master.csv")
    p.add_argument("--db-url",
                   default=os.getenv("DATABASE_URL") or os.getenv("NEON_DATABASE_URL") or "")
    p.add_argument("--target-table", default=DEFAULT_STAGING_TABLE)
    p.add_argument("--truncate-staging", action="store_true")
    p.add_argument("--skip-osm", action="store_true")
    p.add_argument("--skip-boundaries", action="store_true")
    p.add_argument("--osm-step", type=float, default=1.0,
                   help="Tile size in degrees (0.5 for denser rural coverage)")
    p.add_argument("--osm-pause", type=float, default=2.0)
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    if not Path(args.base_hierarchy).exists():
        print(f"[ERROR] Not found: {args.base_hierarchy}")
        return 1

    print("\n=== Stage 1: Load existing admin hierarchy ===")
    existing, by_id = load_existing(args.base_hierarchy, args.micro_locations)
    admin_rows = [r for r in existing if r["place_type"] in {"Division", "District", "Upazila", "Union"}]

    osm_rows: list[dict] = []
    if not args.skip_osm:
        print("\n=== Stage 2: OSM micro-location harvest (bbox tiling) ===")
        osm_rows = harvest_osm_micros(step=args.osm_step, pause=args.osm_pause)
    else:
        print("\n=== Stage 2: Skipped (--skip-osm) ===")

    tree = None
    union_meta: list[dict] = []
    if not args.skip_boundaries and osm_rows:
        print("\n=== Stage 3: Fetch Union boundary polygons ===")
        union_elements = fetch_union_boundaries()
        if union_elements:
            tree, union_meta = build_union_spatial_index(union_elements, admin_rows)

    if tree is not None:
        print("\n=== Stage 4: Spatial crosswalk (point-in-polygon) ===")
        resolve_parents_spatially(osm_rows, tree, union_meta)
    else:
        print("\n=== Stage 4: Skipped (no spatial index) ===")
        for r in osm_rows:
            if not r.get("parent_id"):
                r["resolution_status"] = "parent_unresolved"

    print("\n=== Stage 5: Merge, dedupe, write master CSV ===")
    merged = merge_all(existing, osm_rows)
    print_report(merged)
    write_master_csv(args.output, merged)

    if args.db_url and not args.dry_run:
        print("\n=== DB: Importing to Neon staging table ===")
        import_to_neon(merged, args.db_url, args.target_table, args.truncate_staging)
    elif args.db_url:
        print("\n[DB] Dry-run -- skipped import")
    else:
        print("\n[DB] No DATABASE_URL -- CSV-only mode")

    print("\nKhujo Harvester v2 complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
