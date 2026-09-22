# Khujo — Geo Data Pipeline: Complete Plan to SERP Readiness

## Current State (Honest Audit — Sep 19, 2026)

| What | Count | Coords | Description | Image | Parent |
|---|---|---|---|---|---|
| **Divisions** | 8 | ❌ 0 | ❌ | ❌ | N/A |
| **Districts** | 64 | ✅ 64 | ❌ | ❌ | ✅ |
| **Upazilas** | 494 | ❌ 0 | ❌ | ❌ | ✅ |
| **Unions** | 4,540 | ❌ 0 | ❌ | ❌ | ✅ |
| **Villages/Mouzas/Mahallas** | **0** | — | — | — | — |
| **TOTAL** | **5,106** | **64** | **0** | **0** | 5,106 |

**Bottom line:** We have the skeleton (hierarchy) but nothing is SERP-ready. No location will produce a knowledge card today.

### What's Needed for a SERP-Ready Location Card
Each place needs, at minimum:
1. ✅ **`parent_id`** (hierarchy) — Done for admin levels
2. ❌ **`latitude` / `longitude`** — Missing for Divisions/Upazilas/Unions
3. ❌ **Bengali description** (`bn_description`) — Missing for all
4. ❌ **Image/thumbnail** (`image_url`) — Missing for all
5. ❌ **Population** (`population`) — Missing for all
6. ❌ **Village/Mouza/Mahalla layer** — 0 records collected yet

---

## Why "Outside This Machine" (Critical Constraint)

The `khujo_harvester_v2.py` session was killed by a server restart mid-run. Overpass API OSM queries for Bangladesh-wide village coverage take **20-40 minutes** and Wikipedia enrichment takes **2-4 hours** at safe rate limits. This CANNOT run reliably on a local PC.

**The execution environment:** Google Colab (free, stable, no rate-limit IP blocks, runs while you sleep).

---

## The 4-Step Path to SERP Readiness

### STEP 1 — Run OSM Harvest in Colab (Villages + Coordinates)
**Time:** ~30-60 minutes | **Env:** Google Colab

This collects the Village/Mouza/Mahalla micro-locations AND fills in coordinates for all 5,106 admin rows.

```python
# ══ COLAB CELL 1: Install dependencies ══
!pip install requests shapely

# ══ COLAB CELL 2: Upload base_hierarchy.csv then run ══
# Upload: crawler/geo_pipeline/data/base_hierarchy.csv to Colab

import subprocess
subprocess.run(["git", "clone", "https://github.com/YOUR_REPO/khujo.git"])
# OR manually upload khujo_harvester_v2.py

# ══ COLAB CELL 3: Run the harvester ══
!python khujo_harvester_v2.py \
  --base-hierarchy base_hierarchy.csv \
  --output khujo_locations_master.csv \
  --osm-step 0.5 \
  --osm-pause 2.0 \
  --skip-boundaries

# ══ COLAB CELL 4: Download the result ══
from google.colab import files
files.download('khujo_locations_master.csv')
```

**Expected output:** `khujo_locations_master.csv` with ~10,000–20,000 rows including villages with Bengali names and coordinates.

> [!IMPORTANT]
> Use `--osm-step 0.5` (0.5° tiles instead of 1°) in Colab for denser rural coverage. Colab has better IP reputation with Overpass API than our local machine.

---

### STEP 2 — Run Wikipedia Enrichment in Colab (Descriptions + Images + Population)
**Time:** ~2-4 hours | **Env:** Google Colab (continuation of Step 1 notebook)

```python
# ══ COLAB CELL 5: Enrich with Wikipedia / Wikidata ══
!pip install requests wikipedia-api

import csv, time, requests, json

def get_wiki_bn(place_name_bn, place_name_en=""):
    """Query Bengali Wikipedia API for description + image."""
    base = "https://bn.wikipedia.org/api/rest_v1/page/summary/"
    for name in [place_name_bn, place_name_en]:
        if not name: continue
        try:
            r = requests.get(base + requests.utils.quote(name), timeout=10,
                            headers={"User-Agent": "KhujoBot/1.0"})
            if r.status_code == 200:
                d = r.json()
                return {
                    "description": d.get("extract", "")[:500],
                    "image_url": (d.get("thumbnail") or {}).get("source", ""),
                    "wiki_url": d.get("content_urls", {}).get("desktop", {}).get("page", "")
                }
        except: pass
    return {"description": "", "image_url": "", "wiki_url": ""}

def get_population(place_name_en):
    """Query Wikidata for population."""
    query = f"""
    SELECT ?pop WHERE {{
      ?item wdt:P17 wd:Q902.
      ?item rdfs:label "{place_name_en}"@en.
      ?item wdt:P1082 ?pop.
    }} LIMIT 1
    """
    try:
        r = requests.get("https://query.wikidata.org/sparql",
                        params={"query": query, "format": "json"},
                        headers={"User-Agent": "KhujoBot/1.0"}, timeout=15)
        results = r.json().get("results", {}).get("bindings", [])
        if results:
            return results[0]["pop"]["value"]
    except: pass
    return ""

# Load the master CSV from Step 1
rows = list(csv.DictReader(open("khujo_locations_master.csv", encoding="utf-8")))
enriched = []

ENRICHMENT_FIELDS = ["bn_description", "image_url", "wiki_url", "population"]

for i, row in enumerate(rows):
    result = get_wiki_bn(row.get("name_bn",""), row.get("name_en",""))
    row["bn_description"] = result["description"]
    row["image_url"] = result["image_url"]
    row["wiki_url"] = result["wiki_url"]
    
    # Only fetch population for higher-level admin areas (not villages)
    if row.get("place_type") in ("Division", "District", "Upazila", "Union"):
        row["population"] = get_population(row.get("name_en", ""))
    else:
        row["population"] = ""
    
    enriched.append(row)
    
    if i % 50 == 0:
        print(f"Progress: {i}/{len(rows)} — {row.get('name_bn','')}")
    
    time.sleep(0.3)  # Respect rate limits

# Save enriched CSV
fields = list(rows[0].keys()) + [f for f in ENRICHMENT_FIELDS if f not in rows[0]]
with open("khujo_locations_enriched.csv", "w", encoding="utf-8", newline="") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(enriched)

print(f"Done! {len(enriched)} rows enriched.")
files.download("khujo_locations_enriched.csv")
```

---

### STEP 3 — DB Commit (Staging → Production)
**Time:** ~5 minutes | **Env:** Local machine

After downloading `khujo_locations_enriched.csv`:

```bash
# We need to build worker_04_db_commit.py — it reads the enriched CSV
# and upserts into core.place table via Neon DB
python crawler/geo_pipeline/worker_04_db_commit.py \
  --input khujo_locations_enriched.csv \
  --db-url $NEON_DATABASE_URL
```

> [!NOTE]
> `worker_04_db_commit.py` needs to be built (it maps the CSV fields to the `core.place` schema in our Neon DB). This is the next coding task.

---

### STEP 4 — SERP Integration (Backend + Frontend)
**Time:** ~2-3 hours dev | **Env:** Local machine

Once the data is in DB, connect it to the search engine:

**Backend (`backend/main.py`):**
- Add a `core.place` lookup to the `/api/v1/search` endpoint
- If a query matches a place name (Bangla or English), return a `place_card` in the response
- Place card format: `{name_bn, name_en, place_type, hierarchy_path, description, image_url, population, lat, lon}`

**Frontend (`public/js/khujo.js` + `public/search.html`):**
- Render the place card above the regular search results (like Google's Knowledge Panel)
- Show: Bengali name (large), hierarchy breadcrumb, description, image, population

---

## Confirmed Decisions (Unchanged)
- **Bangla-First**: All UI in Bangla. English only as aliases/metadata.
- **No local machine for crawls**: All scraping in Google Colab or GitHub Actions.
- **Staging table first**: Never write directly to production `core.place`.
- **No DB commit until enriched**: No partial/unenriched data in production.

---

## Remaining Target Data (Still to Collect)

| Entity Type | Target Count | Status |
|---|---|---|
| Mouzas | 58,846 | ❌ Not started |
| Villages (Gram) | 90,049 | ❌ Not started |
| Urban Mahallas | 15,153 | ❌ Not started |
| City Corporations | 12 | ❌ Not started |
| Paurashavas | 330 | ❌ Not started |
| **TOTAL REMAINING** | **~164,000** | ❌ |

OSM coverage of Bangladesh villages is ~15-20% with Bengali names tagged. For the remaining 80%, we need the **Bangladesh Bureau of Statistics (BBS) Geocode Dataset** (the official source). This is the Phase 2 data gap — Colab Step 1 will get what OSM has; BBS will close the gap.

---

## File Status

| File | Status |
|---|---|
| `crawler/geo_pipeline/data/base_hierarchy.csv` | ✅ DONE — 5,106 admin records |
| `crawler/geo_pipeline/khujo_harvester_v2.py` | ✅ READY — run in Colab Step 1 |
| `crawler/geo_pipeline/worker_03_enrich_colab.py` | ✅ READY — run in Colab Step 2 |
| `crawler/geo_pipeline/worker_04_db_commit.py` | ❌ TODO — needs to be built |
| `backend/main.py` — place card endpoint | ❌ TODO — needs to be built |
| `public/search.html` — place card UI | ❌ TODO — needs to be built |

## Next Immediate Actions (In Order)

1. **[Colab]** Run Step 1 OSM harvest with `khujo_harvester_v2.py`
2. **[Colab]** Run Step 2 Wikipedia enrichment (same session)
3. **[Local]** Build `worker_04_db_commit.py`
4. **[Local]** Run DB commit to staging
5. **[Local]** Build SERP place card (backend API + frontend UI)
6. **[Local]** Test: search "ঢাকা", "সিলেট", "ধানমন্ডি" and verify card appears
