# KHUJO — 9-PHASE IMPLEMENTATION PLAN
### The Road to Becoming Bangladesh's Unavoidable Local Search
### For: CEO & Chief of Command | Updated: September 2026
### 90-Day Commitment Locked: Sep 4 – Nov 30, 2026 → VPS Jan 2027 → Go-Live 2027

---

> *"Start as low as possible. Win big with data. Build the country's knowledge base."*
>
> Each phase is designed to be executable by one person with limited time.
> Phases 1-2 are done. The 90-day window begins now at Phase 3.

---

## PHASE 1 ✅ — KNOWLEDGE CORE
**Status: COMPLETE** | *Executed: August 2026*

**Delivered:**
- `core.search_dictionary` (schema + indexes)
- `core.entity_revisions` (append-only versioning)
- `core.search_boosts`, `core.hidden_entities`, `core.locality_overrides`, `core.tag_overrides`
- `ALTER TABLE core.entity ADD current_revision_id`

**Architectural decision locked:** PostgreSQL stores facts. Knowledge layer stores interpretation. These are two things. This separation is the system's superpower.

---

## PHASE 2 ✅ — EVOLVED PIPELINE
**Status: COMPLETE** | *Executed: August 2026*

**Delivered:**
- `worker_01_fetch.py` — polite HTTP downloader, saves raw HTML to `crawler/data/raw_html/`
- `worker_02_extract.py` — BeautifulSoup parser, stages candidate documents
- `worker_03_knowledge.py` — dictionary-aware NER, tags entity mentions
- `0004_pipeline_queues.sql` — `parsed_at` + `entities_extracted_at` queue markers

**Architectural decision locked:** Each stage is independently restartable. A crashed worker restarts from exactly where it left off, without re-downloading anything.

---

## PHASE 3 🔴 — DICTIONARY & KNOWLEDGE SEEDING
**Status: IN PROGRESS — 90-DAY PRIORITY**
**Window: Sep 2026 – Nov 2026 | Impact: ⭐⭐⭐⭐⭐**

> This is the most important phase in the entire plan. The architecture is ready. It just needs data.

### 3A. Seed `core.search_dictionary` (Bangla ↔ English ↔ Banglish)

Create `crawler/seed_search_dictionary.py` that loads from a JSON seed file into the database.

**Target: 1,000 entries by end of Month 1, 5,000 by end of Month 3**

| Category | Month 1 Target | Examples |
|---|---|---|
| 64 Districts (all spellings) | 128 entries | সিলেট → Sylhet, চট্টগ্রাম → Chittagong/Chattogram |
| Dhaka areas & thanas | 150 entries | গুলশান → Gulshan, মিরপুর → Mirpur |
| Universities | 60 entries | ঢাবি → DU → Dhaka University |
| Food & dining | 100 entries | ফুচকা → Puchka, বিরিয়ানি → Biryani |
| Political parties | 40 entries | আওয়ামী লীগ → AL → Awami League |
| Public figures | 100 entries | প্রধানমন্ত্র → PM |
| Common services | 100 entries | হাসপাতাল → Hospital |
| Casual Banglish | 200 entries | manush → মানুষ, desh → দেশ |
| **Total Month 1** | **~900** | |

**3B. Scale the Entity Crawler to 500+ Entities**

Extend `entity_crawler.py` TARGETS list:
- All 8 divisions (with Bangla names + English names as dictionary entries)
- All 64 districts + divisional HQs
- All public universities (44 universities in Bangladesh)
- Major hospitals (DMCH, BSMMU, SSMCH, CMH)
- All political parties (AL, BNP, JP, Jamaat, etc.)
- Top 100 cultural figures (freedom fighters, writers, musicians, scientists)
- Major mosques, churches, temples (national heritage sites)

**3C. Bulk Content Crawl — Daily Scheduler**

Seed `crawl.frontier_url` with 20 Bangladeshi news + info domains:

```
Priority Tier 1 (run daily):
  prothomalo.com, thedailystar.net, kalerkantho.com

Priority Tier 2 (run 3x/week):
  samakal.com, jugantor.com, bdnews24.com
  ittefaq.com.bd, dailyjanakantha.com

Priority Tier 3 (government portals — run weekly):
  bangladesh.gov.bd, mopa.gov.bd, educationboard.gov.bd
  bbs.gov.bd (Bangladesh Bureau of Statistics)
```

Use Windows Task Scheduler to run workers daily:
```
Task 1: 02:00 AM daily — python crawler/worker_01_fetch.py
Task 2: 03:00 AM daily — python crawler/worker_02_extract.py
Task 3: 04:00 AM daily — python crawler/worker_03_knowledge.py
Task 4: 06:00 AM daily — python crawler/entity_crawler.py
```

### Phase 3 Success Criteria
- `core.search_dictionary` ≥ 1,000 active entries (Month 1), ≥ 5,000 (Month 3)
- `core.entity` ≥ 200 verified (Month 1), ≥ 500 (Month 3)
- `content.document` ≥ 5,000 verified (Month 2), ≥ 25,000 (Month 3)
- Searching "ঢাকা বিশ্ববিদ্যালয়" returns Knowledge Graph card
- Searching "DU" correctly resolves to Dhaka University via dictionary

---

## PHASE 4 🔴 — SEARCH API INTEGRATION
**Status: IMMEDIATE — 2-WEEK SPRINT**
**Timeline: September 2026 | Impact: ⭐⭐⭐⭐⭐**

> Wire the plumbing. Everything built in Phases 1-3 must have a visible effect in the live search results.

### 4A. Wire `core.search_dictionary` into `/api/v1/search`

Modify `backend/main.py` search endpoint:

```python
# BEFORE entity lookup, expand query via dictionary
dict_rows = db.execute(text("""
    SELECT DISTINCT entity_id
    FROM core.search_dictionary
    WHERE normalised_term ILIKE :q
    AND state = 'active'
    AND entity_id IS NOT NULL
"""), {"q": f"%{norm_q}%"}).fetchall()

# Add dictionary-resolved entity IDs to search expansion
resolved_entity_ids = [str(r[0]) for r in dict_rows]
```

### 4B. Wire `core.search_boosts` into ranking formula

Add to the SERP SQL scoring:
```sql
+ (CASE WHEN sb.is_verified = true THEN 50.0 ELSE 0.0 END)
+ COALESCE(sb.local_authority_rank * 10.0, 0.0)
LEFT JOIN core.search_boosts sb ON e.entity_id = sb.entity_id
```

### 4C. Wire `core.hidden_entities` into entity query

```sql
WHERE e.entity_id NOT IN (SELECT entity_id FROM core.hidden_entities)
```

### 4D. Wire search_dictionary into `/api/v1/suggestions`

Suggestions endpoint should also expand via dictionary — if user types "DU", suggest "ঢাকা বিশ্ববিদ্যালয়".

### Phase 4 Success Criteria
- "DU" → Dhaka University Knowledge Graph card appears
- Verified entity ranks above unverified content for same query
- Hidden entity disappears from all SERP results
- Banglish query "Dhaka Univ" resolves to correct entity

---

## PHASE 5 🟡 — ADMIN KNOWLEDGE LAYER UI
**Status: MONTH 2 PRIORITY**
**Timeline: October 2026 | Impact: ⭐⭐⭐⭐**

> The knowledge layer tables are live but locked behind raw SQL. Admins need a UI to curate without engineering.

### 5A. Dictionary Manager Panel in `public/entities.html`

Add a new tab to the existing admin UI:
- **View all entries** in `core.search_dictionary` with filters (state, source, confidence)
- **Add new entry** form (raw_term, normalised_term, entity_id dropdown, source, confidence)
- **Bulk CSV import** endpoint
- **Approve/reject** AI-suggested entries (`source = 'ai_suggested'`)

### 5B. Ranking Control Panel

Per-entity boost panel in `public/admin.html`:
- Toggle `is_verified` status (makes entity rank 50 points higher)
- Set `local_authority_rank` (multiplicative boost, default 1.0)
- Set `pinned_position` (forces entity to specific SERP slot)

### 5C. SERP Intervention System

Critical feature for admin control of search results:
- Admin can search any query and see exact SERP ranking order
- Admin can pin entity to position 1 for specific queries
- Admin can mark entities as hidden (they disappear from all SERPs)
- Admin can add locality overrides (re-parent entity to correct geographic region)

### Phase 5 Success Criteria
- Admin can add a dictionary entry in < 30 seconds without touching SQL
- Admin can verify/boost an entity and see updated SERP immediately
- Admin can suppress a spam entity via UI in < 10 seconds

---

## PHASE 6 🟡 — OPEN SOURCE MAPS INTEGRATION
**Status: POST-LAUNCH (Q1 2027 or later)**
**Timeline: After 3 months of run in 2027 | Impact: ⭐⭐⭐⭐**

> Maps are a high-impact local feature. Correctly deferred until the core engine is stable.

### Approach: OpenStreetMap + Overpass API

- **OpenStreetMap (OSM)** is the world's largest free geographic database, with good Bangladesh coverage
- **Nominatim** (OSM geocoder) provides free place search API
- **Leaflet.js** is a lightweight open-source map renderer (50KB, no license fees)

### Integration Plan

1. Add `latitude`, `longitude`, `osm_id` columns to `core.place`
2. Seed geo-coordinates for all 64 districts from OSM Nominatim
3. When a place entity is displayed in SERP, render an embedded Leaflet map
4. For business entities (`restaurant`, `hospital`, etc.) display location pin on map
5. Add "near me" filter to SERP using browser geolocation

### Phase 6 Success Criteria
- All 64 district Knowledge Graph cards include a map
- Business/POI entities show map pin
- "কাছাকাছি" (nearby) search filter works on mobile

---

## PHASE 7 🟡 — BANGLA AI SUMMARISATION
**Status: Q2 2027 (after stable data base)**
**Timeline: 6+ months | Impact: ⭐⭐⭐⭐⭐**

> Pre-generate summaries once. Serve instantly forever.

### Approach: Offline Batch Generation

Use Qwen 3 4B Instruct (quantised, runs on VPS RAM) to generate Bangla summaries for all verified entities. Store in `core.entity.summary`. Never generate at query time.

```
VPS runs ollama serve
  ↓
crawler/summariser.py batch-processes entities without summaries
  ↓
Bangla summary stored in DB
  ↓
Served as static text in Knowledge Graph card — zero AI latency
```

**Seeding AI-suggested dictionary entries:**
The same LLM run can propose new Bangla/English/Banglish term pairs for admin approval, gradually populating `core.search_dictionary` with `source = 'ai_suggested'`.

### Phase 7 Success Criteria
- ≥ 300 entities have AI-generated Bangla summaries
- Knowledge Graph card shows Bangla summary for all major entities
- Admin can review and approve AI dictionary suggestions

---

## PHASE 8 🟡 — BANGLA VOICE SUMMARY
**Status: Q3 2027 (after Phase 7)**
**Timeline: 3 weeks post-7 | Impact: ⭐⭐⭐⭐⭐**

> The most differentiated public-facing feature. First in class in Bangladesh.

### Approach: TTS → R2 CDN

```
Entity has Bangla summary (Phase 7)
  ↓
gTTS generates MP3 audio file
  ↓
MP3 uploaded to Cloudflare R2 (zero compute per play)
  ↓
🔊 play button added to Knowledge Graph card
  ↓
Audio served from CDN — works offline after first load on mobile
```

Add `voice_summary_url` to `core.entity`. Audio cached on R2 forever.

### Phase 8 Success Criteria
- Every verified entity with summary has playable Bangla audio
- Audio works on Android Chrome (primary BD browser)
- Zero additional server load per play (served from R2 CDN)

---

## PHASE 9 🔵 — PUBLIC LAUNCH & NATIONAL POSITIONING
**Status: 2027 (after stable 3-month production run)**
**Timeline: Ongoing | Impact: ⭐⭐⭐⭐⭐**

### 9A. Domain Activation
- Acquire `.com.bd` or `.bd` domain post trade licence
- Set up Cloudflare DNS (already using R2)
- Move from localhost/dev to production domain
- Deploy on VPS (January 2027 — Hetzner CX31 recommended)

### 9B. Content Marketing — The Marketing IS the Data Pipeline
- Launch Bangla blog: "খুঁজো জানালা" (Khujo Window)
- Weekly "বাংলাদেশের ঐতিহ্য" (Bangladesh Heritage) posts — one entity per week, deeply researched
- Each blog post crawled by KhujoBot and fed into the knowledge base
- The content marketing operation and the crawling operation are the same operation

### 9C. Community Contribution
- "একটি তথ্য দিন" (Submit a Fact) form on the public site
- All submissions route to HITL admin queue
- Public acknowledgement of contributors → early evangelists

### 9D. High-Quality Native Bangla Conversation (Long-Term)
- Integrate Bangla conversational AI as a SERP feature
- "Khujo AI" can answer factual questions about Bangladesh in natural Bangla
- Built on entity graph + summaries already generated in Phase 7
- Voice input (Bangla speech-to-text) as the primary mobile interface

### 9E. Soft Launch Criteria (Before Public Announcement)
- `core.search_dictionary` ≥ 5,000 active entries
- `core.entity` ≥ 2,000 verified entities
- `content.document` ≥ 50,000 verified documents
- Voice summary live for ≥ 500 entities
- SERP response time < 400ms at p95
- Admin processing ≥ 200 documents/week
- Maps integrated for all 64 districts

---

## EXECUTION MATRIX

| Phase | Status | Window | Effort | Impact |
|---|---|---|---|---|
| 1 — Knowledge Core | ✅ Done | Aug 2026 | Medium | Foundation |
| 2 — Evolved Pipeline | ✅ Done | Aug 2026 | Medium | Foundation |
| 3 — Data Seeding | 🔴 Now | Sep–Nov 2026 | High (ongoing) | ⭐⭐⭐⭐⭐ |
| 4 — Search API Wiring | 🔴 Now | Sep 2026 | Low | ⭐⭐⭐⭐⭐ |
| 5 — Admin UI (Knowledge) | 🟡 Next | Oct 2026 | Medium | ⭐⭐⭐⭐ |
| 6 — Open Source Maps | 🟡 Post-launch | Q1 2027 | Medium | ⭐⭐⭐⭐ |
| 7 — Bangla AI Summaries | 🟡 After data | Q2 2027 | High | ⭐⭐⭐⭐⭐ |
| 8 — Bangla Voice | 🟡 After 7 | Q3 2027 | Low-Med | ⭐⭐⭐⭐⭐ |
| 9 — Public Launch | 🔵 2027 | Ongoing | Ongoing | ⭐⭐⭐⭐⭐ |

---

## THE NON-NEGOTIABLES

1. **Never bypass the HITL gate.** At Bangladesh's data quality level, human verification is not a bottleneck — it is the product quality guarantee.
2. **Dictionary first, AI second.** The search dictionary must be populated before AI features make sense.
3. **VPS in January 2027, not before.** Free-tier infrastructure is correct until the architecture is proven.
4. **Domain after trade licence.** Correct sequencing. No shortcuts on legal foundation.
5. **Build data. The code is done.**

---

*Plan locked: September 2026*
*90-day window: Sep 4 – Nov 30, 2026*
*Next milestone review: October 1, 2026*
