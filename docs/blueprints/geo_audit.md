# Khujo Geography Layer — Engineering Audit & Master Harvester Plan

## Audit Finding: The Parent Problem is Real

Confirmed by audit of `micro_locations_raw.csv`:
- **Total micro-location records:** 1,407  
- **Has coordinates:** 1,407 (100%) ✅  
- **Has Bengali name:** 1,407 (100%) ✅  
- **Has parent_id:** **0 (0%)** ❌  

The engineer's core point is **correct and critical**: every OSM row is a floating point on a map with no administrative home. Before we can commit to the DB, every micro-location must be deterministically placed inside a Union. Guessing is not acceptable.

---

## Audit of `khujo_location_harvester.py` (Proposed by Engineer)

### What is Correct and Should be Adopted

| Feature | Why it's good |
|---|---|
| **Bbox tiling for OSM** | Our division-by-division query fails (Chittagong=0, Barisal=0) because OSM tags those regions differently. A 1°×1° bbox grid covers Bangladesh uniformly regardless of admin tags. |
| **`source` + `source_confidence` + `resolution_status` fields** | Production-grade provenance. Every row knows where it came from and how trusted it is. |
| **`canonical_row()` + `normalize_text()`** | Stable deduplication. Fuzzy Bangla/English normalization without aggressive transliteration. |
| **`stable_id()` using SHA1 on normalized names** | Deterministic IDs that don't collide across sources. |
| **`merge_candidates()` — merging on `internal_id` + name+coord** | Prevents double-counting the same village from Registry + OSM. |
| **Staging table first** (`khujo_location_staging`) | Never touch production. Correct safety model. |
| **Bangladesh Location Registry source** | `montasim/bangladesh-location-registry` is a real, government-derived dataset. Excellent addition. |

### What is Wrong / Incomplete

| Issue | Detail |
|---|---|
| **No spatial crosswalk** | `resolve_registry_parent_ids()` explicitly avoids coordinate-based guessing but provides NO alternative for OSM rows. All OSM rows leave with `parent_id = ""`. Same problem as our worker_02. |
| **Chittagong/Barisal 0 elements** | Our division-query bug — OSM tags it "Chattogram" not "Chittagong". The bbox approach bypasses this entirely. |
| **Registry JSONL format assumption** | Asset picker may fail if the registry uses a different format. Needs graceful fallback. |
| **No exponential backoff** | Linear retry delay. Production crawlers need exponential backoff with jitter. |

### What Needs to Be Built New

**The Union/Ward Boundary Spatial Crosswalk** — the single most important missing piece.

**Problem:** 1,407 coordinate-carrying micro-locations, 0 with a parent. We have 4,540 Unions — but they have no boundary polygons.

**Solution:**
1. Download Union boundary GeoJSON from OSM (admin_level=7 in Bangladesh = Union level).
2. Spatial point-in-polygon test: for each micro-location, check which Union polygon it falls inside.
3. Mark `resolution_status`: `"parent_resolved_spatial"` if matched, `"parent_unresolved"` if outside all polygons.

This converts 0% parent resolution to ~80-90% automatically, deterministically, no guessing.

---

## The Ultimate Khujo Harvester Architecture

### `crawler/geo_pipeline/khujo_harvester_v2.py`

A single production-grade script running 5 stages:

```
Stage 1: Load existing admin hierarchy (base_hierarchy.csv)
Stage 2: Fetch OSM micro-locations via bbox tiling (1°×1° grid over Bangladesh)
Stage 3: Fetch Union boundary GeoJSON polygons from OSM (admin_level=7)
Stage 4: Spatial crosswalk — point-in-polygon to assign parent_id
Stage 5: Merge + dedupe + write khujo_locations_master.csv
```

**Run modes:**
```
python khujo_harvester_v2.py --skip-registry      # CSV only, fast test
python khujo_harvester_v2.py --db-url $NEON_URL   # Full run + DB push
```

---

## Updated Phase Plan

### Phase 1 — COMPLETE
Base Hierarchy: 8 Divisions, 64 Districts, 494 Upazilas, 4,540 Unions in `base_hierarchy.csv`.

### Phase 2 — NEXT ACTION
Run `khujo_harvester_v2.py` to:
- Tile-crawl OSM with bbox grid (fixes Chittagong/Barisal 0 bug)
- Download Union GeoJSON boundaries from OSM
- Spatial crosswalk — assign `parent_id` to every micro-location
- Expected output: `khujo_locations_master.csv` (~7,000–15,000 rows, ~80%+ parent-resolved)

### Phase 3 — Google Colab
Upload `khujo_locations_master.csv`. Run enrichment to fetch Bengali Wikipedia descriptions, thumbnail images, and population data.

### Phase 4 — DB Commit
Only after Phase 3: push fully enriched master into Neon DB via `worker_04_db_commit.py`.

> [!IMPORTANT]
> Do NOT commit to production DB until spatial crosswalk is done. Orphaned records with no parent_id will break the SERP hierarchy display card.

## Files Plan

| File | Action |
|---|---|
| `crawler/geo_pipeline/khujo_harvester_v2.py` | NEW — ultimate harvester (replaces worker_01 + worker_02) |
| `crawler/geo_pipeline/worker_03_enrich_colab.py` | Keep as-is |
| `crawler/geo_pipeline/worker_04_db_commit.py` | NEW — commit enriched master to Neon |
| `crawler/geo_pipeline/worker_01_hierarchy.py` | Archive — superseded by v2 |
| `crawler/geo_pipeline/worker_02_micro_locations.py` | Archive — superseded by v2 |
