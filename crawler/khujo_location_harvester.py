#!/usr/bin/env python3
"""
KHUJO Bangladesh Geographic Knowledge Base Harvester
------------------------------------------------------
Purpose
    Build a high-coverage Bangladesh location candidate set for Khujo SERP cards.

Source policy
    1) User's existing base_hierarchy.csv -> current Khujo admin scaffold.
    2) Bangladesh Location Registry (2026.08.04 release) -> bulk village coverage.
       This is an independent derived dataset built from government-published sources;
       keep its provenance and do not silently treat it as a new official source.
    3) OpenStreetMap / Overpass -> discovery of villages, hamlets, suburbs,
       neighbourhoods, quarters and localities, especially informal urban names.

Safety / quality rules
    - Never delete existing rows automatically.
    - Never overwrite a conflicting name/parent silently.
    - Every harvested row gets source + fetched_at + confidence.
    - Production DB import goes to a staging table by default.
    - Existing Khujo rows win on internal_id; source duplicates are merged by
      normalized name + type + approximate coordinate.

Works in
    - Google Colab
    - ordinary Linux/macOS/Windows Python
    - GitHub Actions

Install
    pip install -r requirements-khujo-location.txt

Example
    python khujo_location_harvester.py \
      --base-hierarchy base_hierarchy.csv \
      --micro-locations micro_locations_raw.csv \
      --output khujo_locations_master.csv \
      --db-url "$DATABASE_URL"

For a cheap local smoke test, skip network calls:
    python khujo_location_harvester.py --skip-registry --skip-osm

For GitHub Actions, store DATABASE_URL as a repository secret and run:
    python khujo_location_harvester.py --db-url "$DATABASE_URL"

The script creates/refreshes ONLY its own staging table by default:
    khujo_location_staging

It does not alter your existing production location table unless you explicitly
change TARGET_TABLE / IMPORT_MODE.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import io
import json
import math
import os
import re
import sqlite3
import sys
import tarfile
import time
import unicodedata
import urllib.parse
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

try:
    import requests
except ImportError:
    requests = None

try:
    import psycopg
    from psycopg import sql
except ImportError:
    psycopg = None
    sql = None

try:
    from shapely.geometry import Point, shape
    from shapely.strtree import STRtree
except ImportError:
    Point = shape = STRtree = None

# ----------------------------- CONFIG ---------------------------------

COUNTRY = "Bangladesh"
DEFAULT_BBOX = (20.35, 26.75, 88.00, 92.70)  # south, north, west, east

REGISTRY_REPO_API = (
    "https://api.github.com/repos/montasim/bangladesh-location-registry/releases/latest"
)
REGISTRY_REPO_WEB = "https://github.com/montasim/bangladesh-location-registry"
OSM_OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]
OSM_ATTRIBUTION = "© OpenStreetMap contributors"

# These are deliberately broader than an official administrative ontology.
# Khujo can later decide whether a candidate is promoted to Village/Mahalla.
OSM_PLACE_TYPES = {
    "village": "Village",
    "hamlet": "Hamlet",
    "suburb": "Mahalla",
    "neighbourhood": "Mahalla",
    "quarter": "Mahalla",
    "locality": "Locality",
}

DEFAULT_TARGET_TABLE = "khujo_location_staging"

CSV_FIELDS = [
    "place_type",
    "internal_id",
    "parent_id",
    "name_en",
    "name_bn",
    "latitude",
    "longitude",
    "website",
    "source",
    "source_ref",
    "source_record_id",
    "source_confidence",
    "resolution_status",
    "normalized_en",
    "normalized_bn",
    "aliases_json",
    "fetched_at",
]


# ----------------------------- HELPERS ---------------------------------

def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", str(value).strip())


def normalize_text(value: Any) -> str:
    """Stable fuzzy-ish normalizer for English/Bangla matching.

    We intentionally do not aggressively transliterate here. Transliterations should
    become explicit alias records later because local spelling is part of Khujo's moat.
    """
    s = clean_text(value).casefold()
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("&", " and ")
    s = re.sub(r"[^a-z0-9\u0980-\u09ff]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(normalize_text(p) for p in parts)
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]
    return f"{prefix}_{digest}"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def valid_coord(lat: Any, lon: Any) -> bool:
    try:
        lat = float(lat)
        lon = float(lon)
        return 20.0 <= lat <= 27.2 and 87.5 <= lon <= 93.2
    except Exception:
        return False


def http_get(url: str, *, timeout: int = 60, headers: dict[str, str] | None = None) -> bytes:
    """Use requests when available; urllib fallback keeps Colab/GHA friendly."""
    headers = headers or {"User-Agent": "KhujoLocationHarvester/1.0"}
    if requests is not None:
        r = requests.get(url, timeout=timeout, headers=headers)
        r.raise_for_status()
        return r.content
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def http_json(url: str, *, timeout: int = 60) -> Any:
    return json.loads(http_get(url, timeout=timeout).decode("utf-8"))


def read_csv(path: str) -> list[dict[str, str]]:
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: str, rows: Iterable[dict[str, Any]]) -> None:
    rows = list(rows)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        for row in rows:
            w.writerow({k: row.get(k, "") for k in CSV_FIELDS})


def canonical_row(**kwargs: Any) -> dict[str, Any]:
    row = {k: "" for k in CSV_FIELDS}
    for k, v in kwargs.items():
        if k in row:
            row[k] = v
    row["name_en"] = clean_text(row["name_en"])
    row["name_bn"] = clean_text(row["name_bn"])
    row["normalized_en"] = normalize_text(row["name_en"])
    row["normalized_bn"] = normalize_text(row["name_bn"])
    row["resolution_status"] = row["resolution_status"] or "candidate"
    row["source_confidence"] = row["source_confidence"] or "medium"
    row["fetched_at"] = row["fetched_at"] or utc_now()
    if row["aliases_json"] == "":
        row["aliases_json"] = "[]"
    return row


# ------------------------- EXISTING KHUJO DATA ---------------------------

def load_existing(base_path: str, micro_path: str) -> tuple[list[dict[str, Any]], dict[str, dict[str, Any]]]:
    rows: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}

    for path, default_source, confidence in [
        (base_path, "khujo_existing_admin", "high"),
        (micro_path, "khujo_existing_micro", "medium"),
    ]:
        for raw in read_csv(path):
            rid = clean_text(raw.get("internal_id"))
            if not rid:
                continue
            row = canonical_row(
                place_type=clean_text(raw.get("place_type")),
                internal_id=rid,
                parent_id=clean_text(raw.get("parent_id")),
                name_en=raw.get("name_en"),
                name_bn=raw.get("name_bn"),
                latitude=clean_text(raw.get("latitude")),
                longitude=clean_text(raw.get("longitude")),
                website=clean_text(raw.get("website")),
                source=default_source,
                source_ref=path,
                source_record_id=rid,
                source_confidence=confidence,
                resolution_status="existing",
            )
            if rid not in by_id:
                by_id[rid] = row
                rows.append(row)
    return rows, by_id


# --------------------- GOVERNMENT-DERIVED REGISTRY ----------------------

def find_latest_release_jsonl_asset(meta: dict[str, Any]) -> dict[str, Any] | None:
    assets = meta.get("assets", [])
    # Prefer JSONL for streaming; fallback to SQLite because it is compact and easy to query.
    preferred = [
        lambda n: n.endswith("-jsonl.tar.zst"),
        lambda n: n.endswith("-jsonl.tgz"),
        lambda n: n.endswith("-sqlite.zst"),
        lambda n: n.endswith(".sqlite.zst"),
    ]
    for pred in preferred:
        for a in assets:
            name = a.get("name", "")
            if pred(name):
                return a
    return None


def read_registry_asset() -> tuple[list[dict[str, Any]], str]:
    meta = http_json(REGISTRY_REPO_API)
    asset = find_latest_release_jsonl_asset(meta)
    if not asset:
        raise RuntimeError(
            "No JSONL/SQLite release asset found in the latest Bangladesh Location Registry release."
        )
    name = asset["name"]
    url = asset.get("browser_download_url")
    if not url:
        raise RuntimeError(f"Release asset has no download URL: {name}")

    blob = http_get(url, timeout=180)
    records: list[dict[str, Any]] = []

    if name.endswith("-jsonl.tar.zst") or name.endswith("-sqlite.zst") or name.endswith(".sqlite.zst"):
        try:
            import zstandard as zstd
        except ImportError as e:
            raise RuntimeError("Install zstandard: pip install zstandard") from e

        if name.endswith("-jsonl.tar.zst"):
            dctx = zstd.ZstdDecompressor()
            with dctx.stream_reader(io.BytesIO(blob)) as stream:
                with tarfile.open(fileobj=stream, mode="r|") as tar:
                    for member in tar:
                        if not member.isfile():
                            continue
                        member_name = member.name.lower()
                        if "village" not in member_name:
                            continue
                        extracted = tar.extractfile(member)
                        if extracted is None:
                            continue
                        raw = extracted.read().decode("utf-8", errors="replace")
                        for line in raw.splitlines():
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                obj = json.loads(line)
                            except json.JSONDecodeError:
                                continue
                            if isinstance(obj, dict):
                                rec = obj.get("record", obj)
                                if isinstance(rec, dict):
                                    records.append(rec)
        else:
            # SQLite fallback: discover likely village table dynamically.
            dctx = zstd.ZstdDecompressor()
            decompressed = dctx.decompress(blob)
            tmp = Path(".khujo_registry.sqlite")
            tmp.write_bytes(decompressed)
            try:
                con = sqlite3.connect(tmp)
                tables = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")]
                candidates = [t for t in tables if "villag" in t.lower()]
                for table in candidates:
                    cols = [r[1] for r in con.execute(f'PRAGMA table_info("{table}")')]
                    # Best effort mapping across likely schema variants.
                    q = f'SELECT * FROM "{table}"'
                    for row in con.execute(q):
                        obj = dict(zip(cols, row))
                        records.append(obj)
                con.close()
            finally:
                try:
                    tmp.unlink()
                except FileNotFoundError:
                    pass
    else:
        raise RuntimeError(f"Unsupported registry asset format: {name}")

    return records, name


def registry_records_to_rows(records: list[dict[str, Any]], source_asset: str) -> list[dict[str, Any]]:
    out = []
    for rec in records:
        kind = clean_text(rec.get("kind") or rec.get("entityType") or rec.get("level_name"))
        if kind and "vill" not in kind.lower():
            continue

        name_obj = rec.get("name") if isinstance(rec.get("name"), dict) else {}
        en = clean_text(name_obj.get("en") or rec.get("name_en") or rec.get("name"))
        bn = clean_text(name_obj.get("bn") or name_obj.get("local") or rec.get("name_bn"))

        rel = rec.get("relations") if isinstance(rec.get("relations"), dict) else {}
        admin = rel.get("administrativeArea") if isinstance(rel.get("administrativeArea"), dict) else {}
        union = rel.get("localArea") if isinstance(rel.get("localArea"), dict) else {}

        key = clean_text(rec.get("key") or rec.get("id"))
        parent_key = clean_text(union.get("key") or admin.get("key"))
        source_refs = rec.get("sourceRefs") or rec.get("sources") or []
        source_ref = json.dumps(source_refs, ensure_ascii=False) if not isinstance(source_refs, str) else source_refs

        lat = lon = ""
        geo = rec.get("geo") if isinstance(rec.get("geo"), dict) else {}
        if geo:
            lat = clean_text(geo.get("lat") or geo.get("latitude"))
            lon = clean_text(geo.get("lon") or geo.get("lng") or geo.get("longitude"))

        # Stable internal id is intentionally prefixed; don't collide with OSM IDs.
        internal_id = stable_id("BBS_VILLAGE", key or en, bn)

        out.append(canonical_row(
            place_type="Village",
            internal_id=internal_id,
            parent_id=parent_key,
            name_en=en,
            name_bn=bn,
            latitude=lat,
            longitude=lon,
            source="bbs_derived_registry_2026_08_04",
            source_ref=source_ref or REGISTRY_REPO_WEB,
            source_record_id=key,
            source_confidence="high",
            resolution_status="registry_candidate",
        ))
    return out


# ------------------------------ OSM ------------------------------------

def bbox_tiles(south: float, north: float, west: float, east: float, step: float = 1.0):
    lat = south
    while lat < north:
        n = min(lat + step, north)
        lon = west
        while lon < east:
            e = min(lon + step, east)
            yield (lat, n, lon, e)
            lon = e
        lat = n


def overpass_query(bbox: tuple[float, float, float, float]) -> str:
    s, n, w, e = bbox
    types = "|".join(sorted(OSM_PLACE_TYPES))
    return f"""
    [out:json][timeout:90];
    (
      node[place~\"^({types})$\"]({s},{w},{n},{e});
      way[place~\"^({types})$\"]({s},{w},{n},{e});
      relation[place~\"^({types})$\"]({s},{w},{n},{e});
    );
    out center tags;
    """.strip()


def fetch_overpass(query: str, *, retries: int = 4, delay: float = 2.0) -> dict[str, Any]:
    if requests is None:
        raise RuntimeError("requests is required for Overpass harvesting. pip install requests")
    last_error: Exception | None = None
    for endpoint in OSM_OVERPASS_ENDPOINTS:
        for attempt in range(retries):
            try:
                r = requests.post(
                    endpoint,
                    data={"data": query},
                    timeout=120,
                    headers={"User-Agent": "KhujoLocationHarvester/1.0 (Bangladesh local search research)"},
                )
                r.raise_for_status()
                return r.json()
            except Exception as exc:
                last_error = exc
                time.sleep(delay * (attempt + 1))
    raise RuntimeError(f"All Overpass endpoints failed: {last_error}")


def osm_elements_to_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for el in data.get("elements", []):
        tags = el.get("tags") or {}
        p = clean_text(tags.get("place")).lower()
        if p not in OSM_PLACE_TYPES:
            continue
        kind = OSM_PLACE_TYPES[p]
        name_en = clean_text(tags.get("name:en") or tags.get("official_name:en") or tags.get("name"))
        name_bn = clean_text(tags.get("name:bn") or tags.get("name:bn-BD") or tags.get("official_name:bn"))
        if not name_en and not name_bn:
            continue

        if el.get("type") == "node":
            lat, lon = el.get("lat"), el.get("lon")
        else:
            center = el.get("center") or {}
            lat, lon = center.get("lat"), center.get("lon")
        if not valid_coord(lat, lon):
            continue

        osm_id = f"OSM_{el.get('type','?')}_{el.get('id')}"
        out.append(canonical_row(
            place_type=kind,
            internal_id=osm_id,
            parent_id="",
            name_en=name_en,
            name_bn=name_bn,
            latitude=str(lat),
            longitude=str(lon),
            website=clean_text(tags.get("website") or tags.get("contact:website")),
            source="openstreetmap_overpass",
            source_ref=OSM_ATTRIBUTION,
            source_record_id=osm_id,
            source_confidence="medium",
            resolution_status="osm_candidate",
            aliases_json=json.dumps({
                "name": tags.get("name", ""),
                "name:en": tags.get("name:en", ""),
                "name:bn": tags.get("name:bn", ""),
                "old_name": tags.get("old_name", ""),
                "alt_name": tags.get("alt_name", ""),
            }, ensure_ascii=False),
        ))
    return out


def harvest_osm(step: float = 1.0, pause: float = 1.5) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen = set()
    for idx, tile in enumerate(bbox_tiles(*DEFAULT_BBOX, step=step), start=1):
        print(f"[OSM] tile {idx}: {tile}")
        data = fetch_overpass(overpass_query(tile))
        chunk = osm_elements_to_rows(data)
        for r in chunk:
            # De-dupe exact source IDs across overlapping/tiled results.
            key = r["internal_id"]
            if key not in seen:
                seen.add(key)
                rows.append(r)
        time.sleep(pause)
    return rows


# --------------------------- DEDUPE / MERGE -----------------------------

def coord_key(row: dict[str, Any]) -> tuple[str, str] | None:
    try:
        lat = round(float(row.get("latitude")), 4)
        lon = round(float(row.get("longitude")), 4)
        return (f"{lat:.4f}", f"{lon:.4f}")
    except Exception:
        return None


def merge_candidates(
    existing: list[dict[str, Any]],
    registry_rows: list[dict[str, Any]],
    osm_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}
    by_name_coord: dict[tuple[str, str, str], list[int]] = defaultdict(list)

    def add_or_merge(row: dict[str, Any], priority: int) -> None:
        rid = row["internal_id"]
        if rid in by_id:
            return

        # Existing Khujo data gets precedence for identity. New rows are deduped against it.
        nn_en = row["normalized_en"]
        nn_bn = row["normalized_bn"]
        ck = coord_key(row)
        candidate_indices = []
        # Only use normalized-name matching when we also have a coordinate.
        # Same-name villages/mahallas/unions can legitimately exist in different places.
        if (nn_en or nn_bn) and ck:
            key = (row["place_type"], nn_en or nn_bn, ck[0])
            candidate_indices = by_name_coord.get(key, [])

        merged_into = None
        for i in candidate_indices:
            old = result[i]
            if ck and coord_key(old):
                a = coord_key(old)
                b = ck
                # rounded 4dp is about 11m latitude; same-name records at that point are duplicates.
                if a == b:
                    merged_into = i
                    break
            elif nn_en and nn_en == old["normalized_en"] and not ck and not coord_key(old):
                merged_into = i
                break

        if merged_into is not None:
            old = result[merged_into]
            aliases = set()
            for source in (old.get("aliases_json", "[]"), row.get("aliases_json", "[]")):
                try:
                    obj = json.loads(source)
                    if isinstance(obj, list):
                        aliases.update(map(str, obj))
                    elif isinstance(obj, dict):
                        for k, v in obj.items():
                            if v:
                                aliases.add(str(v))
                except Exception:
                    pass
            if row.get("name_en") and row["name_en"] != old.get("name_en"):
                aliases.add(row["name_en"])
            if row.get("name_bn") and row["name_bn"] != old.get("name_bn"):
                aliases.add(row["name_bn"])
            old["aliases_json"] = json.dumps(sorted(x for x in aliases if x), ensure_ascii=False)
            # Preserve strongest evidence.
            confidence_rank = {"low": 1, "medium": 2, "high": 3}
            if confidence_rank.get(row["source_confidence"], 0) > confidence_rank.get(old["source_confidence"], 0):
                old["source_confidence"] = row["source_confidence"]
            # If existing row has no parent, let a stronger registry parent fill it.
            if not old.get("parent_id") and row.get("parent_id") and row["source_confidence"] in {"high", "medium"}:
                old["parent_id"] = row["parent_id"]
            return

        idx = len(result)
        result.append(row)
        by_id[rid] = row
        if (nn_en or nn_bn) and ck:
            key = (row["place_type"], nn_en or nn_bn, ck[0])
            by_name_coord[key].append(idx)

    for r in existing:
        add_or_merge(r, 100)
    for r in registry_rows:
        add_or_merge(r, 80)
    for r in osm_rows:
        add_or_merge(r, 50)

    return result


# ---------------------- OPTIONAL ADMIN PARENTING -------------------------

def resolve_registry_parent_ids(rows: list[dict[str, Any]], base_rows: list[dict[str, Any]]) -> None:
    """Try to turn external registry administrative keys into Khujo internal union/upazila IDs.

    We do this only for exact normalized name matches under a known parent chain.
    It intentionally avoids guessing from nearest coordinates.
    """
    base_by_type_name = defaultdict(list)
    for r in base_rows:
        base_by_type_name[(r["place_type"], r["normalized_en"], r["normalized_bn"])].append(r)

    # External keys are not guaranteed to be identical to Khujo IDs. Keep the external key
    # in source_record_id and only replace parent_id where we can resolve confidently.
    unions = [r for r in base_rows if r["place_type"] == "Union"]
    union_by_name = defaultdict(list)
    for u in unions:
        union_by_name[u["normalized_en"]].append(u)
        if u["normalized_bn"]:
            union_by_name[u["normalized_bn"]].append(u)

    # The registry currently encodes localArea key, but the key may not be recoverable to our
    # exact internal ID without a code map. Therefore we preserve the external key as parent_id
    # but mark it as external until a deterministic code crosswalk is added.
    for r in rows:
        if r["source"].startswith("bbs_derived_registry") and r["parent_id"]:
            r["resolution_status"] = "parent_external_registry_key"


# ------------------------------ DB -------------------------------------

def ensure_staging_table(conn, table_name: str) -> None:
    if psycopg is None:
        raise RuntimeError("psycopg is required for DB import. pip install psycopg[binary]")
    ident = sql.Identifier(table_name)
    conn.execute(sql.SQL(f"""
        CREATE TABLE IF NOT EXISTS {{table}} (
            place_type TEXT NOT NULL,
            internal_id TEXT PRIMARY KEY,
            parent_id TEXT NULL,
            name_en TEXT,
            name_bn TEXT,
            latitude DOUBLE PRECISION NULL,
            longitude DOUBLE PRECISION NULL,
            website TEXT,
            source TEXT NOT NULL,
            source_ref TEXT,
            source_record_id TEXT,
            source_confidence TEXT,
            resolution_status TEXT,
            normalized_en TEXT,
            normalized_bn TEXT,
            aliases_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
    """).format(table=ident))
    conn.execute(sql.SQL("CREATE INDEX IF NOT EXISTS {} ON {} (place_type, normalized_en)" ).format(
        sql.Identifier(f"{table_name}_name_idx"), ident))
    conn.execute(sql.SQL("CREATE INDEX IF NOT EXISTS {} ON {} (parent_id)" ).format(
        sql.Identifier(f"{table_name}_parent_idx"), ident))
    conn.execute(sql.SQL("CREATE INDEX IF NOT EXISTS {} ON {} (latitude, longitude)" ).format(
        sql.Identifier(f"{table_name}_geo_idx"), ident))
    conn.commit()


def import_to_postgres(rows: list[dict[str, Any]], db_url: str, table_name: str, truncate: bool = False) -> None:
    if psycopg is None:
        raise RuntimeError("psycopg is not installed. Run pip install psycopg[binary]")
    with psycopg.connect(db_url) as conn:
        ensure_staging_table(conn, table_name)
        ident = sql.Identifier(table_name)
        if truncate:
            conn.execute(sql.SQL("TRUNCATE TABLE {}" ).format(ident))
            conn.commit()

        stmt = sql.SQL("""
            INSERT INTO {} (
                place_type, internal_id, parent_id, name_en, name_bn, latitude, longitude, website,
                source, source_ref, source_record_id, source_confidence, resolution_status,
                normalized_en, normalized_bn, aliases_json, fetched_at
            ) VALUES (
                %(place_type)s, %(internal_id)s, %(parent_id)s, %(name_en)s, %(name_bn)s,
                %(latitude)s, %(longitude)s, %(website)s, %(source)s, %(source_ref)s,
                %(source_record_id)s, %(source_confidence)s, %(resolution_status)s,
                %(normalized_en)s, %(normalized_bn)s, %(aliases_json)s::jsonb,
                %(fetched_at)s::timestamptz
            )
            ON CONFLICT (internal_id) DO UPDATE SET
                parent_id = COALESCE(NULLIF(EXCLUDED.parent_id, ''), {}.parent_id),
                name_en = COALESCE(NULLIF(EXCLUDED.name_en, ''), {}.name_en),
                name_bn = COALESCE(NULLIF(EXCLUDED.name_bn, ''), {}.name_bn),
                latitude = COALESCE(EXCLUDED.latitude, {}.latitude),
                longitude = COALESCE(EXCLUDED.longitude, {}.longitude),
                website = COALESCE(NULLIF(EXCLUDED.website, ''), {}.website),
                source = EXCLUDED.source,
                source_ref = EXCLUDED.source_ref,
                source_record_id = EXCLUDED.source_record_id,
                source_confidence = EXCLUDED.source_confidence,
                resolution_status = EXCLUDED.resolution_status,
                normalized_en = EXCLUDED.normalized_en,
                normalized_bn = EXCLUDED.normalized_bn,
                aliases_json = EXCLUDED.aliases_json,
                fetched_at = EXCLUDED.fetched_at
        """).format(table=ident)

        prepared = []
        for r in rows:
            def fnum(x: Any):
                try:
                    return float(x) if clean_text(x) else None
                except Exception:
                    return None
            item = dict(r)
            item["latitude"] = fnum(r.get("latitude"))
            item["longitude"] = fnum(r.get("longitude"))
            prepared.append(item)
        with conn.cursor() as cur:
            cur.executemany(stmt, prepared)
        conn.commit()
        print(f"[DB] imported {len(prepared):,} rows into {table_name}")


# ------------------------------ QA -------------------------------------

def print_report(rows: list[dict[str, Any]]) -> None:
    type_counts = defaultdict(int)
    source_counts = defaultdict(int)
    unresolved_parent = 0
    coords = 0
    for r in rows:
        type_counts[r["place_type"]] += 1
        source_counts[r["source"]] += 1
        if not r["parent_id"]:
            unresolved_parent += 1
        if valid_coord(r["latitude"], r["longitude"]):
            coords += 1

    print("\n=== KHUJO LOCATION HARVEST REPORT ===")
    print(f"Total rows:                 {len(rows):,}")
    print(f"Rows with coordinates:      {coords:,}")
    print(f"Rows without parent_id:     {unresolved_parent:,}")
    print("\nBy place type:")
    for k, v in sorted(type_counts.items()):
        print(f"  {k:18s} {v:>10,}")
    print("\nBy source:")
    for k, v in sorted(source_counts.items()):
        print(f"  {k:38s} {v:>10,}")

    # Collision report: same normalized English name within same type.
    dup = defaultdict(list)
    for r in rows:
        if r["normalized_en"]:
            dup[(r["place_type"], r["normalized_en"])].append(r["internal_id"])
    dup_groups = [(k, v) for k, v in dup.items() if len(v) > 1]
    print(f"\nSame-type normalized English collisions: {len(dup_groups):,} groups")
    if dup_groups[:5]:
        for (typ, name), ids in dup_groups[:5]:
            print(f"  {typ}: {name} -> {len(ids)} records")


# ------------------------------ CLI ------------------------------------

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Harvest/merge Bangladesh locations for Khujo.")
    p.add_argument("--base-hierarchy", default="base_hierarchy.csv")
    p.add_argument("--micro-locations", default="micro_locations_raw.csv")
    p.add_argument("--output", default="khujo_locations_master.csv")
    p.add_argument("--db-url", default=os.getenv("DATABASE_URL", ""))
    p.add_argument("--target-table", default=DEFAULT_TARGET_TABLE)
    p.add_argument("--truncate-staging", action="store_true")
    p.add_argument("--skip-registry", action="store_true")
    p.add_argument("--skip-osm", action="store_true")
    p.add_argument("--osm-step", type=float, default=1.0)
    p.add_argument("--osm-pause", type=float, default=1.5)
    p.add_argument("--dry-run", action="store_true")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    if not Path(args.base_hierarchy).exists():
        raise FileNotFoundError(args.base_hierarchy)
    if not Path(args.micro_locations).exists():
        raise FileNotFoundError(args.micro_locations)

    print("[1/5] Loading existing Khujo data...")
    existing, _ = load_existing(args.base_hierarchy, args.micro_locations)
    base_rows = [r for r in existing if r["place_type"] in {"Division", "District", "Upazila", "Union"}]
    print(f"      existing rows: {len(existing):,}")

    registry_rows: list[dict[str, Any]] = []
    if not args.skip_registry:
        print("[2/5] Fetching latest Bangladesh Location Registry release...")
        raw_records, asset = read_registry_asset()
        registry_rows = registry_records_to_rows(raw_records, asset)
        print(f"      registry village candidates: {len(registry_rows):,} ({asset})")
    else:
        print("[2/5] Registry skipped")

    osm_rows: list[dict[str, Any]] = []
    if not args.skip_osm:
        print("[3/5] Harvesting OSM granular place candidates across Bangladesh...")
        osm_rows = harvest_osm(step=args.osm_step, pause=args.osm_pause)
        print(f"      OSM candidates: {len(osm_rows):,}")
    else:
        print("[3/5] OSM skipped")

    print("[4/5] Merging, deduplicating and preserving provenance...")
    merged = merge_candidates(existing, registry_rows, osm_rows)
    resolve_registry_parent_ids(merged, base_rows)
    print_report(merged)

    print(f"\n[5/5] Writing {args.output}...")
    write_csv(args.output, merged)
    print(f"      wrote {len(merged):,} rows")

    if args.db_url and not args.dry_run:
        print("[DB] Importing into safe staging table...")
        import_to_postgres(merged, args.db_url, args.target_table, truncate=args.truncate_staging)
    elif args.db_url and args.dry_run:
        print("[DB] dry-run: DB import skipped")
    else:
        print("[DB] DATABASE_URL not supplied; CSV-only mode")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        raise SystemExit(130)
