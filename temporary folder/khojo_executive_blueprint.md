# KHOJO — EXECUTIVE ARCHITECTURE BLUEPRINT
### National Bangla Search Engine | Locked Architecture v1.0

**Prepared by:** CTO (Claude) → **For:** Founder (Sumon)
**Status:** ✅ LOCKED — Ready for build
**Target Scale:** Thousands → Millions of local users, staged growth

---

## 1. EXECUTIVE SUMMARY

Khojo runs on three physically separate systems, each doing one job:

| System | Job | Where | Cost |
|---|---|---|---|
| **Serving Core** | Answer search queries fast | Hetzner VPS | $4-8/mo |
| **Crawl Fleet** | Discover & index Bangla content | GitHub Actions + Oracle Free + Colab | $0 |
| **Media Vault** | Store/serve images, video, favicons | Cloudflare R2 + Images/Stream | $0-5/mo |

**Principle:** The serving core never crawls. The crawl fleet never serves traffic. Media never touches the VPS disk. This separation is what lets a $4/mo box serve a national engine — each system scales independently, on its own schedule, on its own bill.

---

## 2. ARCHITECTURAL BLUEPRINT (Full System Diagram)

```
                              ┌───────────────────────────────┐
                              │        END USERS (BD)        │
                              │   Mobile-first, thousands→M   │
                              └───────────────┬───────────────┘
                                              │ HTTPS
                                              ▼
                              ┌───────────────────────────────┐
                              │      CLOUDFLARE (Free)        │
                              │  CDN + DNS + DDoS shield       │
                              │  + Cache static/API responses  │
                              └───────────────┬───────────────┘
                                              │
                                              ▼
                    ┌─────────────────────────────────────────────┐
                    │           HETZNER VPS (Serving Core)          │
                    │           1-2 vCPU / 2GB RAM / 40GB SSD       │
                    │                                                │
                    │  ┌──────────┐   ┌──────────────┐             │
                    │  │  Nginx   │──▶│ FastAPI (1x   │             │
                    │  │ (static  │   │  uvicorn      │             │
                    │  │ + proxy  │   │  worker)      │             │
                    │  │ + cache) │   └──────┬───────┘             │
                    │  └──────────┘          │                     │
                    │                        ▼                     │
                    │            ┌──────────────────────┐          │
                    │            │  PostgreSQL 16        │          │
                    │            │  (self-hosted)        │          │
                    │            │  ┌──────────────────┐ │          │
                    │            │  │ PERMANENT LAYER  │ │          │
                    │            │  │ (entities, trans- │ │          │
                    │            │  │ literations,      │ │          │
                    │            │  │ suggestions)       │ │          │
                    │            │  └──────────────────┘ │          │
                    │            │  ┌──────────────────┐ │          │
                    │            │  │ TEMPORARY LAYER  │ │          │
                    │            │  │ (fresh content,   │ │          │
                    │            │  │ queue, logs —      │ │          │
                    │            │  │ auto-expiring)     │ │          │
                    │            │  └──────────────────┘ │          │
                    │            └──────────┬───────────┘          │
                    └───────────────────────┼──────────────────────┘
                                             │
                       SSL-only, IP-allowlisted, read/write from crawler
                                             │
              ┌──────────────────────────────┼──────────────────────────────┐
              ▼                              ▼                              ▼
  ┌───────────────────────┐     ┌───────────────────────┐    ┌───────────────────────┐
  │  CRAWL FLEET (Free)     │     │  MEDIA VAULT           │    │  ANALYTICS (Later)     │
  │                         │     │  (Cloudflare)           │    │                        │
  │  GitHub Actions         │     │                         │    │  Plausible/self-hosted │
  │   → scheduled runs      │     │  R2: images, thumbnails │    │  (privacy-first,       │
  │   → 100/segment/run     │     │  Images: resize/serve   │    │  lightweight)          │
  │                         │     │  Stream: video (later)  │    │                        │
  │  Oracle Free Tier       │     │                         │    │                        │
  │   → persistent crawler  │     │  VPS stores ONLY URLs   │    │                        │
  │   → heavier jobs         │     │  to Cloudflare assets   │    │                        │
  │                         │     │                         │    │                        │
  │  Colab (interim/manual) │     │                         │    │                        │
  └───────────────────────┘     └───────────────────────┘    └───────────────────────┘
```

---

## 3. WHY THIS SPLIT (The Non-Negotiables)

**Serving core stays lean forever.** Every byte of RAM on the VPS is reserved for *answering queries*. Crawling, image processing, and video handling are RAM/CPU spikes that would starve search responses on a 2GB box — so they're structurally forbidden from running there, not just "discouraged."

**Crawl fleet is disposable and parallel.** GitHub Actions gives you ~2,000 free minutes/month — enough for scheduled, segmented crawl runs. Oracle's Always-Free ARM tier (4 vCPU/24GB) is a zero-cost fallback for heavier, longer-running crawl jobs once volume grows. Neither costs money, neither touches the serving box except to write finished records over SSL.

**Media never touches the 40GB disk.** A national engine will accumulate millions of image/video references. Storing binaries on the VPS would exhaust the disk in weeks. Cloudflare R2 (10GB free, then $0.015/GB) + Images/Stream keeps this off your infrastructure bill entirely until you're at serious scale.

---

## 4. MULTILAYERED CATEGORY PLACEMENT (SERP Performance Design)

This is the core of how Khojo returns fast, relevant Bangla results without needing Elasticsearch. Content is placed into **tiers by retrieval frequency**, not just by type — the goal is that the *hottest* 5% of data is what most queries touch.

### Tier 0 — Hot Path (queried on almost every keystroke)
- Transliteration lookups (Bangla ⇄ Banglish ⇄ English)
- Search suggestions / autocomplete
- Top trending entities (materialized view, refreshed hourly)

→ Kept small, heavily indexed (GIN/trgm), fully cached by Nginx micro-cache (1-5s TTL absorbs repeat keystrokes across users).

### Tier 1 — Permanent Entities (queried on most searches)
- People, places, businesses, organizations, products
- Rarely change, so indexed aggressively; this is what most "who/what/where" Bangla queries resolve against first

### Tier 2 — Fresh Content, Segmented by Type
- **News** (30-day retention) — highest query volume, freshest data, ranked by recency + relevance
- **Blog/Long-form** (90-day retention)
- **Forum/Community** (180-day retention)
- **Social snippets** (7-day retention) — most disposable, least indexed

Segmenting by type means a query like "আজকের খবর" (today's news) only scans the news partition, not the entire content table — this is what keeps queries fast without Elasticsearch at this scale.

### Tier 3 — Media References (Cloudflare-backed)
- Image/video/favicon **URLs only**, joined at render time
- Never part of the text search index — retrieved after a document already matched

### Tier 4 — Cold/Archival
- Expired-but-valuable content (e.g., historical news beyond 30 days) can be exported to cheap object storage (R2) as compressed JSON before deletion, rather than lost — cheap insurance, zero ongoing DB cost

**Why this matters for SERP performance at thousands of users:** most search engines die not from total data volume but from every query scanning irrelevant partitions. Segmenting by tier + type means a typical query touches Tier 0 + Tier 1 + one Tier 2 segment — a small, well-indexed slice — never the whole database.

---

## 5. OPERATIONS PIPELINE (End-to-End Flow)

```
1. DISCOVER
   Crawl Fleet (GitHub Actions, scheduled) pulls 100 pending URLs
   per segment (news / image / video / link) from crawl_queue
        ↓
2. FETCH & PARSE
   Scrape content, extract: title, body, favicon URL, og:image URL,
   published date, author, language
        ↓
3. CLASSIFY
   Auto-tag content_type + assign retention tier (news=30d, blog=90d...)
        ↓
4. MEDIA OFFLOAD
   Any image/video found → uploaded to Cloudflare R2/Images
   → only the resulting Cloudflare URL is kept, original never touches VPS
        ↓
5. WRITE
   Crawler connects to Hetzner Postgres over SSL (allowlisted IP)
   → inserts into correct tier/segment table
   → expires_at auto-set by trigger based on content_type
        ↓
6. SERVE
   User query → Nginx cache check → FastAPI → Postgres
   (Tier 0/1 always warm, Tier 2 segment-scoped, Tier 3 joined last)
        ↓
7. CLEAN
   Nightly job (pg_cron) deletes expired Tier 2/3 rows,
   optionally archives to R2 first
        ↓
8. LEARN
   Search logs feed back into search_suggestions popularity scoring
   → Tier 0 gets smarter over time
```

---

## 6. LOCKED TECH DECISIONS

| Layer | Choice | Status |
|---|---|---|
| VPS Provider | Hetzner (Singapore) | 🔒 Locked |
| Serving DB | Self-hosted PostgreSQL 16 | 🔒 Locked |
| Search method | Postgres FTS + pg_trgm (no ES) | 🔒 Locked |
| Frontend serving | Static build via Nginx (no Node runtime in prod) | 🔒 Locked |
| Crawler location | GitHub Actions + Oracle Free + Colab (off-engine) | 🔒 Locked |
| Media storage | Cloudflare R2 + Images/Stream | 🔒 Locked |
| DB layering | Permanent (stable) + Temporary (auto-expiring, tiered by type) | 🔒 Locked, schema TBD |
| Cache | Nginx micro-cache (Redis deferred until traffic demands it) | 🔒 Locked |

---

## 7. SCALING TRIGGERS (Unchanged Principle, Reconfirmed)

| Signal | Next Action |
|---|---|
| CPU >70% sustained | Upgrade VPS tier (same Hetzner box, vertical) |
| Disk >70% (28GB) | Archive Tier 2 to R2 more aggressively, or upgrade |
| p95 query >300ms | Introduce Redis for Tier 0 cache |
| >100K daily searches | Split DB (read replica) or migrate to managed Postgres |
| Media >10GB | Cloudflare R2 paid tier kicks in automatically ($0.015/GB) — negligible |

---

## 8. WHAT HAPPENS NEXT (When You Return to Khojo)

Nothing here needs to be built today — this is the **locked reference blueprint** to build against whenever DekhaHok frees up time. When you're ready to resume:

1. Provision Hetzner box (15 min)
2. Deploy Tier 0/1 schema first (transliterations + entities + suggestions) — this alone gives you a working autocomplete/lookup engine
3. Wire one crawl segment (news) end-to-end before adding others
4. Add Cloudflare R2 only once the crawler actually finds its first image

Building in that order means you have a *demoable* Khojo after step 2, before the crawler even runs.

---

*This blueprint is the single source of truth for Khojo's architecture. Schemas will be detailed per-tier when build resumes, following the placement logic locked in Section 4.*
