#!/usr/bin/env python3
"""
enrich_tier1_wikipedia.py - Wikipedia & Cloudflare R2 Media Enrichment for Tier 1 Places.

Enriches:
  - 64 Districts (জেলা)
  - 494 Upazilas (উপজেলা)
from Bengali Wikipedia API.

For each place:
  1. Resolves canonical Bangla Wikipedia article (e.g., 'ফেনী জেলা', 'দেবিদ্বার উপজেলা').
  2. Extracts introductory summary paragraph (for Knowledge Cards).
  3. Downloads high-res thumbnail image and streams it into Cloudflare R2 Media Vault.
  4. Stores public R2 URL (https://pub-d8ff02e059814132b7f971370e65283d.r2.dev/...)
  5. Saves enriched dataset locally to:
     crawler/geo_pipeline/data/tier1_enriched_places.json
     crawler/geo_pipeline/data/tier1_enriched_places.csv

Does NOT commit to PostgreSQL DB, keeping everything inspectable for user review.
"""

import os
import re
import sys
import json
import time
import csv
import logging
import asyncio
import urllib.parse
from pathlib import Path
from typing import Dict, List, Any, Optional

import httpx
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

sys.path.insert(0, str(BASE_DIR / "backend"))
from r2_media import _get_s3_client, R2_BUCKET, R2_PUBLIC_URL

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("enrich_tier1")

WIKI_API_URL = "https://bn.wikipedia.org/w/api.php"
BASE_HIERARCHY_CSV = BASE_DIR / "crawler" / "geo_pipeline" / "data" / "base_hierarchy.csv"
OUT_JSON = BASE_DIR / "crawler" / "geo_pipeline" / "data" / "tier1_enriched_places.json"
OUT_CSV = BASE_DIR / "crawler" / "geo_pipeline" / "data" / "tier1_enriched_places.csv"

HEADERS = {
    "User-Agent": "KhujoBot/1.0 (https://khujo.com.bd; contact@khujo.com.bd)"
}

# S3 Client singleton
s3_client = _get_s3_client()


def slugify(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", text.strip().lower()).strip("_")
    return s if s else "place"


def upload_image_to_r2(img_bytes: bytes, r2_key: str, content_type: str = "image/jpeg") -> str:
    """Upload image bytes to Cloudflare R2 bucket and return public CDN URL."""
    s3_client.put_object(
        Bucket=R2_BUCKET,
        Key=r2_key,
        Body=img_bytes,
        ContentType=content_type,
        CacheControl="public, max-age=604800",
    )
    return f"{R2_PUBLIC_URL}/{r2_key}"


async def fetch_wiki_page(client: httpx.AsyncClient, title: str) -> Optional[Dict[str, Any]]:
    """Fetch page extracts and thumbnail for a given title from Bengali Wikipedia."""
    params = {
        "action": "query",
        "format": "json",
        "prop": "extracts|pageimages",
        "titles": title,
        "exintro": 1,
        "explaintext": 1,
        "pithumbsize": 800,
        "redirects": 1,
    }
    try:
        resp = await client.get(WIKI_API_URL, params=params, headers=HEADERS, timeout=12.0)
        if resp.status_code != 200:
            return None
        data = resp.json()
        pages = data.get("query", {}).get("pages", {})
        for pid, page in pages.items():
            if pid == "-1":
                return None
            extract = page.get("extract", "").strip()
            thumb = page.get("thumbnail", {}).get("source")
            return {
                "title": page.get("title"),
                "extract": extract,
                "thumbnail": thumb,
                "pageid": pid,
            }
    except Exception:
        return None
    return None


async def enrich_entity(
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    row: Dict[str, str],
    district_map: Dict[str, str],
) -> Dict[str, Any]:
    """Resolve and enrich a single District or Upazila entity."""
    async with sem:
        internal_id = row["internal_id"]
        place_type = row["place_type"]
        name_en = row["name_en"].strip()
        name_bn = row["name_bn"].strip()
        website = row.get("website", "").strip()
        parent_id = row.get("parent_id", "").strip()

        district_name = district_map.get(parent_id, "")

        # Determine candidate search titles
        if place_type == "District":
            candidates = [f"{name_bn} জেলা", name_bn]
        else:  # Upazila
            candidates = [
                f"{name_bn} উপজেলা",
                f"{name_bn} উপজেলা, {district_name}" if district_name else "",
                f"{name_bn}, {district_name}" if district_name else "",
                name_bn,
            ]
            candidates = [c for c in candidates if c]

        wiki_res = None
        matched_title = ""
        for title in candidates:
            wiki_res = await fetch_wiki_page(client, title)
            if wiki_res and wiki_res.get("extract"):
                matched_title = wiki_res.get("title", title)
                break
            await asyncio.sleep(0.05)

        summary = wiki_res.get("extract", "") if wiki_res else ""
        wiki_thumb = wiki_res.get("thumbnail") if wiki_res else None
        wiki_url = f"https://bn.wikipedia.org/wiki/{urllib.parse.quote(matched_title)}" if matched_title else ""

        r2_image_url = ""
        # Download image and upload to Cloudflare R2
        if wiki_thumb:
            slug = f"{slugify(name_en)}_{internal_id.lower()}"
            folder = "districts" if place_type == "District" else "upazilas"
            r2_key = f"places/{folder}/{slug}.jpg"
            try:
                img_resp = await client.get(wiki_thumb, headers=HEADERS, timeout=15.0)
                if img_resp.status_code == 200 and len(img_resp.content) > 1000:
                    c_type = img_resp.headers.get("content-type", "image/jpeg")
                    r2_image_url = upload_image_to_r2(img_resp.content, r2_key, c_type)
            except Exception as e:
                log.warning(f"Failed to upload image to R2 for {name_en} ({internal_id}): {e}")

        # Clean summary for SERP Knowledge Card
        # Cut at ~600 chars or first two paragraphs
        clean_summary = summary
        if len(clean_summary) > 600:
            cut = clean_summary[:600]
            last_period = max(cut.rfind("।"), cut.rfind("."))
            if last_period > 200:
                clean_summary = cut[:last_period + 1]
            else:
                clean_summary = cut + "..."

        return {
            "internal_id": internal_id,
            "place_type": place_type,
            "name_en": name_en,
            "name_bn": name_bn,
            "parent_id": parent_id,
            "parent_name": district_name,
            "website": website,
            "wikipedia_title": matched_title,
            "wikipedia_url": wiki_url,
            "summary": clean_summary,
            "r2_image_url": r2_image_url,
            "original_image_url": wiki_thumb or "",
            "enriched": bool(clean_summary or r2_image_url),
        }


async def main():
    if not BASE_HIERARCHY_CSV.exists():
        log.error(f"File not found: {BASE_HIERARCHY_CSV}")
        return

    with open(BASE_HIERARCHY_CSV, "r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    districts = [r for r in rows if r["place_type"] == "District"]
    upazilas = [r for r in rows if r["place_type"] == "Upazila"]
    tier1_places = districts + upazilas

    log.info(f"Loaded {len(districts)} districts and {len(upazilas)} upazilas (Total Tier 1: {len(tier1_places)}).")

    # Map district internal_id -> district Bangla name
    district_map = {d["internal_id"]: d["name_bn"] for d in districts}

    # Semaphore to stay polite with Wikipedia API and R2 uploads
    sem = asyncio.Semaphore(6)

    t0 = time.time()
    log.info(f"Starting async Wikipedia extraction and R2 media upload for {len(tier1_places)} places...")

    async with httpx.AsyncClient(limits=httpx.Limits(max_keepalive_connections=20, max_connections=30)) as client:
        tasks = [enrich_entity(client, sem, r, district_map) for r in tier1_places]
        enriched_results = await asyncio.gather(*tasks)

    elapsed = time.time() - t0
    log.info(f"Completed enrichment in {elapsed:.1f}s.")

    # Save to JSON
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(enriched_results, f, ensure_ascii=False, indent=2)

    # Save to CSV
    fields = [
        "internal_id", "place_type", "name_en", "name_bn", "parent_name",
        "website", "wikipedia_title", "wikipedia_url", "r2_image_url",
        "original_image_url", "summary", "enriched"
    ]
    with open(OUT_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(enriched_results)

    # Statistics
    total_enriched = sum(1 for r in enriched_results if r["enriched"])
    total_images = sum(1 for r in enriched_results if r["r2_image_url"])
    dist_enriched = sum(1 for r in enriched_results if r["place_type"] == "District" and r["enriched"])
    dist_images = sum(1 for r in enriched_results if r["place_type"] == "District" and r["r2_image_url"])
    upa_enriched = sum(1 for r in enriched_results if r["place_type"] == "Upazila" and r["enriched"])
    upa_images = sum(1 for r in enriched_results if r["place_type"] == "Upazila" and r["r2_image_url"])

    print("=" * 70)
    print(" KHUJO TIER 1 WIKIPEDIA & R2 MEDIA ENRICHMENT COMPLETE")
    print("=" * 70)
    print(f"Total Tier 1 Units Processed: {len(enriched_results)}")
    print(f"  • Successfully Enriched with Wikipedia: {total_enriched} ({total_enriched/len(enriched_results)*100:.1f}%)")
    print(f"  • Images Mirrored to Cloudflare R2:    {total_images} ({total_images/len(enriched_results)*100:.1f}%)")
    print("-" * 70)
    print(f"Districts (64 total):")
    print(f"  • Enriched: {dist_enriched} / 64 ({dist_enriched/64*100:.1f}%)")
    print(f"  • R2 Images: {dist_images} / 64 ({dist_images/64*100:.1f}%)")
    print(f"Upazilas (494 total):")
    print(f"  • Enriched: {upa_enriched} / 494 ({upa_enriched/494*100:.1f}%)")
    print(f"  • R2 Images: {upa_images} / 494 ({upa_images/494*100:.1f}%)")
    print("-" * 70)
    print(f"Output Artifacts (Saved Locally — 0 DB Changes Made):")
    print(f"  1. {OUT_JSON.name} ({OUT_JSON.stat().st_size / 1024:.1f} KB)")
    print(f"  2. {OUT_CSV.name} ({OUT_CSV.stat().st_size / 1024:.1f} KB)")
    print("=" * 70)
    print("Sample Enriched District Preview:")
    for r in [x for x in enriched_results if x["place_type"] == "District" and x["r2_image_url"]][:2]:
        print(f"  • {r['name_bn']} ({r['name_en']})")
        print(f"    R2 Image: {r['r2_image_url']}")
        print(f"    Summary: {r['summary'][:120]}...")
    print("-" * 70)
    print("Sample Enriched Upazila Preview:")
    for r in [x for x in enriched_results if x["place_type"] == "Upazila" and x["r2_image_url"]][:2]:
        print(f"  • {r['name_bn']} ({r['name_en']}) | জেলা: {r['parent_name']}")
        print(f"    R2 Image: {r['r2_image_url']}")
        print(f"    Summary: {r['summary'][:120]}...")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
