# KHUJO — OPERATIONAL BLUEPRINT
### Complete System Literacy & Operations Manual
### For: CEO & Chief of Command | 90-Day Window: Sep 4 – Nov 30, 2026
### Classification: LIVING DOCUMENT — Update as system evolves

---

> *This document exists so that the operator (currently: the CEO) can understand exactly what every part of the system does, what healthy looks like, what broken looks like, and what to do in both cases.*
>
> *System literacy is not optional. It is the multiplier on every other effort.*

---

## SECTION 1: THE COMPLETE DATA FLOW

### 1.1 The Full Pipeline — Start to Finish

```
┌─────────────────────────────────────────────────────────┐
│                    DATA SOURCES                         │
│  Bangladeshi News Sites  │  Wikipedia (Bangla)          │
│  Government Portals      │  Manual Admin Input          │
│  Community Submissions   │  AI Suggestions (future)     │
└──────────────┬──────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────┐
│              STAGE 1: FRONTIER QUEUE                    │
│  crawl.frontier_url (state='queued')                    │
│  Contains: URL, source_id, priority, host               │
│  Managed by: seed_sources.py, site_scout.py             │
└──────────────┬──────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────┐
│           STAGE 2: FETCH (worker_01_fetch.py)           │
│  Downloads raw HTML → saves to crawler/data/raw_html/   │
│  Updates: crawl.fetch (state='success'/'failed')        │
│  Updates: crawl.frontier_url (state='fetched'/'failed') │
│  Rate limit: 2 seconds per request                      │
└──────────────┬──────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────┐
│        STAGE 3: EXTRACT (worker_02_extract.py)          │
│  Reads raw HTML from disk                               │
│  Extracts: title, canonical URL, body text              │
│  Writes: core.source_record, content.document           │
│  Document state: 'candidate'                            │
│  Updates: crawl.fetch.parsed_at = now()                 │
└──────────────┬──────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────┐
│        STAGE 4: KNOWLEDGE NER (worker_03_knowledge.py)  │
│  Reads candidate documents                              │
│  Looks up core.search_dictionary for term matching     │
│  Writes: content.entity_mention (state='candidate')    │
│  Updates: content.document.entities_extracted_at       │
└──────────────┬──────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────┐
│         STAGE 5: ADMIN HITL GATE (admin.html)           │
│  Admin reviews candidate documents                      │
│  Approves → state='verified' (enters live SERP)         │
│  Rejects → state='rejected' (excluded forever)          │
│  Edits → corrects title, type, entity links             │
└──────────────┬──────────────────────────────────────────┘
               │
               ▼
┌─────────────────────────────────────────────────────────┐
│         STAGE 6: LIVE SEARCH (FastAPI /api/v1/search)   │
│  Queries verified content.document                      │
│  Queries verified core.entity                           │
│  Applies core.search_boosts, core.search_dictionary     │
│  Logs: search.query_event, search.suggestion            │
└─────────────────────────────────────────────────────────┘
```

### 1.2 Entity Pipeline (Separate from Content Pipeline)

```
entity_crawler.py
  → Fetches from Bengali Wikipedia API
  → Creates/updates core.entity (state='candidate')
  → Creates core.entity_name entries (Bangla + English names)
  → Downloads images → uploads to Cloudflare R2
  → Stores image URL in core.entity.metadata.image_url
  
Admin HITL (entities.html)
  → Reviews candidate entities
  → Approves → state='verified'
  → Adds additional aliases, corrects transliterations
  → Alias changes tracked in core.entity_name
  → All entity edits logged in core.entity_revisions
```

### 1.3 Knowledge Dictionary Pipeline

```
Manual curation
  → Admin adds to core.search_dictionary via UI or SQL
  → source = 'manual', confidence = 1.0

Harvest from query logs
  → Popular queries in search.query_event become candidates
  → source = 'log_mining', confidence = 0.7

AI suggestions (Phase 7)
  → LLM proposes new term pairs during summarisation
  → source = 'ai_suggested', confidence = 0.6
  → Requires admin approval before state = 'active'
```

---

## SECTION 2: CRAWLER FLEET — MANAGEMENT & MAINTENANCE

### 2.1 Crawler Inventory

| Script | Purpose | Run Frequency | Owner DB Table |
|---|---|---|---|
| `worker_01_fetch.py` | Downloads raw HTML | Daily 02:00 AM | `crawl.fetch` |
| `worker_02_extract.py` | Parses HTML → candidates | Daily 03:00 AM | `content.document` |
| `worker_03_knowledge.py` | NER + entity tagging | Daily 04:00 AM | `content.entity_mention` |
| `entity_crawler.py` | Wikipedia entity harvesting | Daily 06:00 AM | `core.entity` |
| `geo_crawler.py` | Geographic data seeding | Weekly | `core.place` |
| `site_scout.py` | Discovers new URLs to crawl | Weekly | `crawl.frontier_url` |
| `seed_sources.py` | Seeds trusted source domains | Once / when adding new sources | `core.source` |
| `seed_geography.py` | Seeds BD geographic hierarchy | Once / on DB reset | `core.place` |
| `seed_popular_phrases.py` | Seeds autocomplete suggestions | Once / quarterly | `search.suggestion` |

### 2.2 Setting Up Daily Automation (Windows Task Scheduler)

```powershell
# Create daily crawler tasks via Task Scheduler
# Run from project root in .venv

# Worker 01 — Fetch (02:00 AM daily)
schtasks /create /tn "Khujo-Fetch" /tr "cmd /c cd /d C:\Users\Sumon\Desktop\Khoojo\khujo && .venv\Scripts\python.exe crawler\worker_01_fetch.py >> logs\fetch.log 2>&1" /sc daily /st 02:00 /f

# Worker 02 — Extract (03:00 AM daily)
schtasks /create /tn "Khujo-Extract" /tr "cmd /c cd /d C:\Users\Sumon\Desktop\Khoojo\khujo && .venv\Scripts\python.exe crawler\worker_02_extract.py >> logs\extract.log 2>&1" /sc daily /st 03:00 /f

# Worker 03 — Knowledge (04:00 AM daily)
schtasks /create /tn "Khujo-Knowledge" /tr "cmd /c cd /d C:\Users\Sumon\Desktop\Khoojo\khujo && .venv\Scripts\python.exe crawler\worker_03_knowledge.py >> logs\knowledge.log 2>&1" /sc daily /st 04:00 /f

# Entity Crawler (06:00 AM daily)
schtasks /create /tn "Khujo-Entities" /tr "cmd /c cd /d C:\Users\Sumon\Desktop\Khoojo\khujo && .venv\Scripts\python.exe crawler\entity_crawler.py >> logs\entities.log 2>&1" /sc daily /st 06:00 /f
```

Create the logs directory:
```powershell
New-Item -ItemType Directory -Force -Path "C:\Users\Sumon\Desktop\Khoojo\khujo\crawler\logs"
```

### 2.3 Crawler Health Monitoring

**What Healthy Looks Like:**

```sql
-- Check fetch queue health (should see fresh fetches each morning)
SELECT state, count(*), max(created_at)
FROM crawl.fetch
GROUP BY state;
-- Expected: state='success' with recent created_at

-- Check extraction queue (should be near-zero unparsed)
SELECT count(*) as unparsed_count
FROM crawl.fetch
WHERE parsed_at IS NULL AND state = 'success';
-- Expected: < 50 unparsed

-- Check document pipeline
SELECT state, count(*)
FROM content.document
GROUP BY state;
-- Expected: steady growth in 'candidate', 'verified'

-- Check entity growth
SELECT state, count(*)
FROM core.entity
GROUP BY state;
-- Expected: growth in 'verified' entities

-- Check dictionary size (our most important metric)
SELECT state, count(*)
FROM core.search_dictionary
GROUP BY state;
-- Target: 1000+ active by end of Month 1
```

**What Broken Looks Like:**
- `crawl.fetch` has no new rows for 24+ hours → scheduler failed, check Task Scheduler
- `crawl.fetch` shows many `state='failed'` → target sites blocking KhujoBot or network issue
- `content.document` candidate count not growing → worker_02 not running
- `entities_extracted_at` never updating → worker_03 not running
- Logs contain `[ERROR]` entries → check `crawler/logs/*.log`

### 2.4 Adding New Crawl Sources

When adding a new Bangladeshi website to the crawler fleet:

**Step 1:** Add the source domain to the database
```sql
INSERT INTO core.source (source_name, base_url, source_type, language_code, state)
VALUES ('Prothom Alo', 'https://www.prothomalo.com', 'news', 'bn', 'verified');
```

**Step 2:** Verify robots.txt compliance
```bash
curl https://www.prothomalo.com/robots.txt | grep -i "khujo\|bot\|crawl"
```

**Step 3:** Seed frontier URLs from the homepage
```python
# Run site_scout.py against the new source
python crawler/site_scout.py --url https://www.prothomalo.com
```

**Step 4:** Monitor the first crawl run for errors in the log

### 2.5 Crawler Ethics (Non-Negotiable)

1. **Always obey robots.txt** — KhujoBot must never crawl disallowed paths
2. **2-second minimum delay** between requests to the same host
3. **Identify as KhujoBot** — User-Agent: `KhujoBot/2.0 (+https://khujo.com.bd/bot)`
4. **Limit to 10 requests per domain per run** during early operation
5. **Back off on HTTP 429 (rate limit) or 503** — mark as failed, retry after 24 hours
6. **Never crawl social media** — Facebook, YouTube, Instagram block scrapers and ban IPs

---

## SECTION 3: DATABASE OPERATIONS

### 3.1 Database Schemas Overview

```
neon.tech — Primary Cluster (Alpha)
├── core.*          # Entities, places, entity names, taxonomy
│   ├── core.entity              # Central entity records
│   ├── core.entity_name         # All names (Bangla/English/Banglish)
│   ├── core.entity_revisions    # Full audit log (never delete)
│   ├── core.place               # Geographic hierarchy (64 districts etc)
│   ├── core.entity_type         # Taxonomy (restaurant, hospital, etc)
│   ├── core.search_dictionary   # Cross-script search alias dictionary
│   ├── core.search_boosts       # Admin ranking overrides
│   ├── core.hidden_entities     # Suppression list
│   ├── core.locality_overrides  # Geographic correction overrides
│   └── core.source, source_record # Provenance chain
│
├── content.*       # Documents and mentions
│   ├── content.document         # Crawled + verified articles
│   └── content.entity_mention   # NER-extracted entity references
│
├── crawl.*         # Pipeline operational data
│   ├── crawl.frontier_url       # URL queue
│   └── crawl.fetch              # Fetch logs + raw HTML index
│
├── search.*        # Search intelligence
│   ├── search.suggestion        # Autocomplete phrases
│   └── search.query_event       # Query logs (expire after 30 days)
│
└── media.*         # Media asset tracking
    └── media.asset              # R2 CDN URLs
```

### 3.2 Critical Queries — Daily Operations

**Morning health check (run every morning):**
```sql
-- Yesterday's crawl summary
SELECT 
    date_trunc('day', created_at) as day,
    count(*) as fetches,
    sum(CASE WHEN state='success' THEN 1 ELSE 0 END) as success,
    sum(CASE WHEN state='failed' THEN 1 ELSE 0 END) as failed
FROM crawl.fetch
WHERE created_at > now() - interval '2 days'
GROUP BY 1 ORDER BY 1 DESC;

-- Admin review queue depth
SELECT count(*) as docs_awaiting_review
FROM content.document WHERE state = 'candidate';

-- Dictionary growth tracker
SELECT count(*) as total_entries,
       count(*) FILTER (WHERE state='active') as active,
       count(*) FILTER (WHERE source='manual') as manual,
       count(*) FILTER (WHERE source='harvested') as harvested
FROM core.search_dictionary;

-- Entity pipeline
SELECT state, count(*) FROM core.entity GROUP BY state;
```

**Weekly review:**
```sql
-- Most searched terms (from query logs)
SELECT normalised_query, count(*) as searches
FROM search.query_event
WHERE occurred_at > now() - interval '7 days'
GROUP BY normalised_query
ORDER BY searches DESC
LIMIT 20;

-- Zero-result queries (these are dictionary seeding opportunities!)
SELECT normalised_query, count(*) as times_searched
FROM search.query_event
WHERE result_count = 0
AND occurred_at > now() - interval '7 days'
GROUP BY normalised_query
ORDER BY times_searched DESC
LIMIT 20;
```

**Zero-result queries are gold.** Every zero-result query is a gap in the dictionary or entity graph. Review this list weekly and seed accordingly.

### 3.3 Database Maintenance

**Archival (Monthly):**
```sql
-- Expire old search query logs (they auto-expire at 30 days but check)
DELETE FROM search.query_event WHERE expires_at < now();

-- Check raw HTML disk usage and clean old files
-- (run from crawler/ directory)
-- Files older than 14 days can be deleted after verification
```

**Backup:**
- Neon provides automatic point-in-time recovery
- Additionally run a monthly SQL dump of `core.*` tables:
```powershell
pg_dump $DATABASE_URL --schema=core > "backups/core_$(Get-Date -Format 'yyyy-MM-dd').sql"
```

### 3.4 When Neon Gets Full — Multi-Cluster Strategy

The multi-cluster migration (Phase 6) activates when:
- Neon storage > 70% of free-tier limit (0.5 GB)
- Or response times consistently > 500ms

**Migration order:**
1. Move `content.document` → Supabase free tier (largest table, safe to migrate)
2. Move `crawl.*` → Railway free PostgreSQL (operational data, can be rebuilt)
3. Move `search.query_event` → Supabase (high-volume, can expire aggressively)
4. Keep `core.*` on Neon Alpha forever — this is the permanent truth layer

```python
# backend/app/database.py will be updated to support multiple connections
CORE_DB_URL = os.getenv("CORE_DATABASE_URL")       # Neon Alpha — core.*
CONTENT_DB_URL = os.getenv("CONTENT_DATABASE_URL") # Supabase Beta — content.*
CRAWL_DB_URL = os.getenv("CRAWL_DATABASE_URL")      # Railway Gamma — crawl.*
```

---

## SECTION 4: SERP OPERATIONS & ADMIN INTERVENTIONS

### 4.1 How the SERP Ranking Works (Full Signal Breakdown)

```
Final Score = 
    URL Match Score (100 pts)       # Query term appears in canonical URL
  + Title Match Score (80 pts)      # Query term appears in document title
  + Title Similarity (20 pts)       # pg_trgm similarity to title_normalised
  + Body Similarity (5 pts)         # pg_trgm similarity to body_normalised
  + Document Kind Bonus (15 pts)    # listing/official documents get bonus
  + Verified Boost (50 pts)         # Phase 4: core.search_boosts.is_verified
  + Authority Rank (variable)       # Phase 4: × local_authority_rank multiplier

Entity (Knowledge Graph) Triggers:
  - Direct entity name match → shows KG card above organic results
  - Dictionary alias match → resolves to entity → shows KG card
  - Search boosts.pinned_position → forces entity to specific slot
```

### 4.2 Admin SERP Intervention Toolkit

**When to intervene:**

| Situation | Action |
|---|---|
| Wrong entity appears for a query | Add dictionary entry redirecting query to correct entity |
| Spam/low-quality result appears at top | Set `core.search_boosts.local_authority_rank = 0.1` for source domain |
| Known-good entity isn't appearing | Verify entity state, add to `core.search_boosts` with `is_verified = true` |
| Misinformation entity | Add to `core.hidden_entities` with reason |
| Entity assigned wrong geography | Add to `core.locality_overrides` |
| Entity miscategorised | Add to `core.tag_overrides` |

**SQL interventions (until admin UI is built in Phase 5):**

```sql
-- Boost a verified entity (e.g., "Dhaka University")
INSERT INTO core.search_boosts (entity_id, is_verified, local_authority_rank)
SELECT entity_id, true, 2.0
FROM core.entity WHERE display_name = 'ঢাকা বিশ্ববিদ্যালয়'
ON CONFLICT (entity_id) DO UPDATE 
SET is_verified = true, local_authority_rank = 2.0;

-- Suppress an entity
INSERT INTO core.hidden_entities (entity_id, reason, hidden_by)
SELECT entity_id, 'Spam/duplicate entity', 'admin'
FROM core.entity WHERE display_name = 'SPAM ENTITY NAME';

-- Add a dictionary entry (Banglish → Bangla)
INSERT INTO core.search_dictionary 
(raw_term, normalised_term, script, language_code, entity_id, source, state, confidence)
SELECT 'Dhaka Univ', 'dhaka univ', 'latin', 'en', entity_id, 'manual', 'active', 1.0
FROM core.entity WHERE display_name = 'ঢাকা বিশ্ববিদ্যালয়';
```

### 4.3 SERP Quality Review Process

**Weekly process (15 minutes):**
1. Open the search engine
2. Run the top 20 zero-result queries from the query log
3. For each zero result, ask: "Is this a missing entity or a missing dictionary entry?"
4. Seed accordingly — entity if it needs a KG card, dictionary entry if it's an alias
5. Run the top 20 most searched queries
6. Verify the top results are correct and relevant
7. If a result is wrong, apply the appropriate intervention from Section 4.2

---

## SECTION 5: OBSERVABILITY & SYSTEM HEALTH

### 5.1 Key Metrics to Track

| Metric | Target | Check Frequency |
|---|---|---|
| Documents crawled per day | > 100 | Daily |
| Documents verified per day (HITL) | > 30 | Daily |
| Zero-result rate | < 40% | Weekly |
| Search dictionary size | Growing 50+/week | Weekly |
| Entity count (verified) | Growing 20+/week | Weekly |
| Neon storage usage | < 70% | Monthly |
| Crawler success rate | > 85% | Daily |
| API response time | < 500ms | Daily (manual test) |

### 5.2 Log Files

```
crawler/logs/
├── fetch.log       # Worker 01 output (URL fetching)
├── extract.log     # Worker 02 output (HTML parsing)
├── knowledge.log   # Worker 03 output (NER results)
├── entities.log    # entity_crawler.py output
└── errors.log      # Any unhandled exceptions
```

**Reading logs effectively:**
```powershell
# Last 50 lines of fetch log
Get-Content crawler\logs\fetch.log -Tail 50

# Count errors in today's fetch log
Select-String "ERROR" crawler\logs\fetch.log | Measure-Object -Line

# Check which URLs failed
Select-String "failed" crawler\logs\fetch.log
```

### 5.3 Quick Health Dashboard (SQL)

Create this as a saved query in any PostgreSQL GUI (pgAdmin, TablePlus, etc.):

```sql
-- KHUJO DAILY HEALTH DASHBOARD
SELECT '=== PIPELINE ===' AS section, '' AS value
UNION ALL
SELECT 'Fetches today', count(*)::text FROM crawl.fetch WHERE created_at > now() - interval '24h'
UNION ALL
SELECT 'Success rate', 
    ROUND(100.0 * count(*) FILTER (WHERE state='success') / NULLIF(count(*),0), 1)::text || '%'
    FROM crawl.fetch WHERE created_at > now() - interval '24h'
UNION ALL
SELECT 'Docs awaiting review', count(*)::text FROM content.document WHERE state = 'candidate'
UNION ALL
SELECT '=== KNOWLEDGE ===' AS section, '' AS value
UNION ALL  
SELECT 'Verified entities', count(*)::text FROM core.entity WHERE state = 'verified'
UNION ALL
SELECT 'Dictionary entries', count(*)::text FROM core.search_dictionary WHERE state = 'active'
UNION ALL
SELECT '=== SEARCH ===' AS section, '' AS value
UNION ALL
SELECT 'Queries (24h)', count(*)::text FROM search.query_event WHERE occurred_at > now() - interval '24h'
UNION ALL
SELECT 'Zero result queries (24h)', count(*)::text FROM search.query_event 
    WHERE occurred_at > now() - interval '24h' AND result_count = 0;
```

---

## SECTION 6: THE 90-DAY OPERATIONAL CALENDAR

### Month 1: September 2026 — "Get Operational"

**Week 1 (Sep 4–10):**
- [ ] Set up Windows Task Scheduler for all 4 crawler workers
- [ ] Create `crawler/logs/` directory
- [ ] Seed 100 dictionary entries (all 64 districts in Bangla + English)
- [ ] Phase 4A: Wire `core.search_dictionary` into search API
- [ ] Phase 4B: Wire `core.search_boosts` into ranking formula
- [ ] Phase 4C: Wire `core.hidden_entities` into entity filter
- [ ] Verify all crawlers are running successfully
- [ ] Test: search "Sylhet" → should return সিলেট entity card

**Week 2 (Sep 11–17):**
- [ ] Seed 300 more dictionary entries (food, universities, services)
- [ ] Expand entity_crawler targets to all 64 districts
- [ ] Add 5 news domains to frontier queue
- [ ] Run manual health check: check zero-result queries
- [ ] Fix any crawl failures from Week 1

**Week 3 (Sep 18–24):**
- [ ] Seed 300 more dictionary entries (public figures, organizations)
- [ ] Begin HITL review session — verify first batch of crawled documents
- [ ] Test SERP for top 10 most popular Bangladeshi searches
- [ ] Begin planning Phase 5 (Admin Knowledge UI)

**Week 4 (Sep 25–30):**
- [ ] Month 1 review: count entities, documents, dictionary entries
- [ ] Identify top 20 zero-result queries → seed as dictionary entries next month
- [ ] Checkpoint: `core.search_dictionary` should have 700+ entries

**September Targets:**
- 700+ dictionary entries
- 100+ verified entities
- 2,000+ candidate documents in pipeline
- All 4 crawlers running automatically

---

### Month 2: October 2026 — "Scale the Data"

**Week 1 (Oct 1–7):**
- [ ] Begin Phase 5: Admin Knowledge UI development
- [ ] Add 10 more news domains to crawl fleet
- [ ] HITL review: verify 30+ documents per day target
- [ ] Seed universities, hospitals, political parties (100+ entities)

**Week 2 (Oct 8–14):**
- [ ] Deploy Phase 5 dictionary manager panel in admin UI
- [ ] Seed 500 more dictionary entries using the new UI
- [ ] Set up second free-tier cluster (Supabase) for future migration

**Week 3 (Oct 15–21):**
- [ ] Phase 5 ranking control panel deployment
- [ ] SERP intervention: run quality review, fix top 10 problematic results
- [ ] Begin seeding all public universities as entities (44 universities)

**Week 4 (Oct 22–31):**
- [ ] Month 2 review
- [ ] `core.search_dictionary` should have 2,000+ entries
- [ ] `core.entity` should have 200+ verified
- [ ] `content.document` should have 5,000+ verified

---

### Month 3: November 2026 — "Quality Gate"

**Focus:** Stop adding raw data. Start improving quality. Prepare for VPS.

**Week 1 (Nov 1–7):**
- [ ] SERP quality review: run all 64 district searches
- [ ] Every district should return a correct Knowledge Graph card
- [ ] Identify and suppress any spam/duplicate entities found

**Week 2 (Nov 8–14):**
- [ ] Architecture review: document what worked, what needs VPS
- [ ] Estimate monthly Neon storage usage trajectory
- [ ] Plan VPS migration procedure for January

**Week 3 (Nov 15–21):**
- [ ] Data quality pass: verify 50 entities manually for accuracy
- [ ] Dictionary quality pass: review low-confidence entries

**Week 4 (Nov 22–30):**
- [ ] 90-Day Review and Report
- [ ] Final metrics snapshot
- [ ] Brief document for VPS procurement decision

**November Targets:**
- 5,000+ dictionary entries
- 500+ verified entities
- 25,000+ verified documents
- SERP returns meaningful results for all 64 districts
- System running unattended for > 30 days without manual intervention

---

## SECTION 7: ADMIN HITL OPERATIONS GUIDE

### 7.1 Daily Admin Session (15-30 minutes)

**Morning routine:**
1. Check health dashboard (Section 5.3)
2. Open `http://localhost:8080/admin.html`
3. Review document queue — verify or reject 20-30 candidate documents
4. Open `http://localhost:8080/entities.html`
5. Review entity queue — verify or reject 5-10 candidate entities
6. Check aliases tab — verify or correct any auto-extracted aliases

**Verification criteria for documents:**
- ✅ Approve if: Bangla or English content, factual, from known BD source, > 200 words
- ❌ Reject if: Mostly English ads, duplicate content, gossip/tabloid, non-Bangladeshi

**Verification criteria for entities:**
- ✅ Approve if: Real entity (person/place/organization), has Bangla name, has summary
- ❌ Reject if: Duplicate of existing entity, fictional, non-Bangladeshi

### 7.2 Weekly Admin Session (1-2 hours)

1. Zero-result query review (Section 4.3)
2. SERP quality spot-check (10 random popular queries)
3. Dictionary additions based on review findings
4. Entity bulk verification if backlog > 50

### 7.3 Admin Interventions Reference

```
ENTITY OPERATIONS
├── Verify entity          → entities.html → Approve button
├── Add entity alias        → entities.html → Aliases tab → Add
├── Correct entity summary  → entities.html → Edit → Summary field
├── Hide/suppress entity    → SQL (Phase 5: UI button)
└── Override locality       → SQL (Phase 5: UI dropdown)

DOCUMENT OPERATIONS
├── Verify document        → admin.html → Approve button
├── Reject document        → admin.html → Reject button
├── Edit document kind     → admin.html → Kind dropdown
└── Link entity to doc     → admin.html → Entity field

SEARCH OPERATIONS
├── Add dictionary entry   → SQL or Phase 5 UI
├── Boost an entity        → SQL (Phase 5: UI slider)
├── Pin entity to pos 1    → SQL (Phase 5: UI input)
└── Suppress entity        → SQL (Phase 5: UI button)
```

---

## SECTION 8: INFRASTRUCTURE & DEPLOYMENT

### 8.1 Current Infrastructure Stack (Sep 2026)

```
Developer Machine (Windows)
├── Backend: FastAPI (localhost:8000) — run manually when testing
├── Frontend: Python HTTP server (localhost:8080)
├── Crawlers: Windows Task Scheduler (automated)
└── Raw HTML: crawler/data/raw_html/ (local disk)

Neon (PostgreSQL Cloud — Free Tier)
├── All 5 schemas (core, content, crawl, search, media)
└── Connection: backend/.env → DATABASE_URL

Cloudflare R2 (Object Storage — Free Tier)
├── Entity images (Wikipedia thumbnails)
└── Future: Bangla voice MP3 audio files

GitHub
└── Source code version control
```

### 8.2 January 2027 — VPS Migration Plan

**Recommended VPS: Hetzner CX31**
- 4 vCPU, 8GB RAM
- 160GB disk
- Location: Singapore (lowest latency to Bangladesh)
- Cost: ~€10/month

**Migration Steps:**
1. Provision VPS, set up Ubuntu 24.04 LTS
2. Install PostgreSQL 16, Python 3.12, Nginx, Caddy (for HTTPS)
3. Dump Neon database: `pg_dump $DATABASE_URL > khujo_full_$(date).sql`
4. Restore to VPS PostgreSQL
5. Migrate crawlers as systemd services (replaces Task Scheduler)
6. Deploy FastAPI with uvicorn behind Nginx
7. Activate domain (`.com.bd` or `.bd`) → point to VPS IP
8. Set up Cloudflare as CDN in front of VPS (free tier, DDoS protection)
9. Test all endpoints
10. Flip DNS

**Post-migration:** Neon remains as backup cluster for read replicas or overflow.

### 8.3 Systemd Services (VPS, January 2027)

```ini
# /etc/systemd/system/khujo-api.service
[Unit]
Description=Khujo FastAPI Backend
After=network.target postgresql.service

[Service]
User=khujo
WorkingDirectory=/opt/khujo
ExecStart=/opt/khujo/.venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000 --workers 2
Restart=always
EnvironmentFile=/opt/khujo/backend/.env

[Install]
WantedBy=multi-user.target
```

```ini
# /etc/systemd/system/khujo-fetch.service (one per worker)
[Unit]
Description=Khujo Fetch Worker
After=network.target

[Service]
User=khujo
WorkingDirectory=/opt/khujo/crawler
ExecStart=/opt/khujo/.venv/bin/python worker_01_fetch.py
Restart=on-failure
EnvironmentFile=/opt/khujo/backend/.env
```

---

## SECTION 9: SYSTEM LITERACY — COMMON SCENARIOS

### "The SERP is returning wrong results"

1. Check if the query has a dictionary entry: `SELECT * FROM core.search_dictionary WHERE normalised_term ILIKE '%query%'`
2. If missing dictionary entry → add one pointing to the correct entity
3. If entity is wrong → verify entity details in entities.html
4. If SERP order is wrong → add search_boosts entry for the correct entity
5. If spam at top → lower its authority rank in search_boosts

### "The crawler isn't running"

1. Check Task Scheduler: `taskschd.msc` → verify tasks are enabled and last run succeeded
2. Check logs: `Get-Content crawler\logs\fetch.log -Tail 20`
3. Check Neon: Open Neon dashboard → verify the project is awake (free tier sleeps after inactivity)
4. Check network: ping the target domain, verify it's reachable
5. Run manually to see errors: `python crawler/worker_01_fetch.py`

### "A new source needs to be added"

See Section 2.4 — Adding New Crawl Sources

### "The search dictionary needs bulk seeding"

1. Create a CSV file: `term,normalised_term,language_code`
2. Use the admin bulk import endpoint (Phase 5) or run SQL INSERT via psql
3. Verify the entries appear in `core.search_dictionary`
4. Test a sample query using the new terms

### "Neon is getting full"

1. Check storage: Neon dashboard → Project → Storage
2. If > 70%: begin Phase 6 migration (move `content.document` to Supabase)
3. Archive `search.query_event` records older than 30 days
4. Review if raw HTML files on disk need cleanup: `du -sh crawler/data/raw_html/`

---

## SECTION 10: THE MISSION STATEMENT (SYSTEM PURPOSE)

*For moments when the operational work feels routine — remember what the system is for.*

**Khujo is Bangladesh's own knowledge engine.**

It is being built by one person, in the background, while managing a job, an MBA, and another product. It is built on free infrastructure, with open-source tools, for a country of 170 million people who deserve to search for information about their own country in their own language.

The architecture is correct. The market is real. The mission is achievable.

Every dictionary entry seeded is a small piece of Bangladesh's knowledge that Google doesn't have. Every entity verified is a real-world piece of the country made searchable. Every document verified is a voice given permanent indexability.

**The 90-day window is not about building code. It is about building Bangladesh's knowledge base.**

When the system can't handle the user loads, that means it worked.

---

*Living operational blueprint. Update as the system evolves.*
*Next review: October 1, 2026 (end of Month 1)*
*Document owner: CEO, Khujo*
