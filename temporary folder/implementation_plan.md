# Khujo — Master Implementation Plan
### Bangladesh's Own Search Engine · বাংলাদেশের স্থানীয় অনুসন্ধান

**Domain:** `khujo.com.bd` | **Branch:** `feature/db-core` → `main`
**Architecture locked in:** [`khojo_executive_blueprint.md`](file:///c:/Users/Sumon/Desktop/Khoojo/khujo/temporary%20folder/khojo_executive_blueprint.md) + [`db-core-plan.md`](file:///c:/Users/Sumon/Desktop/Khoojo/khujo/docs/architecture/db-core-plan.md)

---

## System Status Audit — As of 2026-07-22

| Item | Status | Notes |
|---|---|---|
| Legacy tables dropped (all ~430MB) | ✅ Complete | B.1 finished — DB is 19MB |
| `search.suggestion` cleaned | ✅ Complete | 748 junk rows deleted, REINDEX run |
| 16 curated suggestions activated | ✅ Complete | Division names in bn + en |
| SERP API restricted to `verified` docs only | ✅ Complete | `main.py` confirmed |
| Admin dashboard — basic | ✅ Complete | First version shipped |
| Admin dashboard — upgraded (stats, batch, filter) | ✅ Complete | Light mode, mobile-friendly |
| DB schema (`core`, `content`, `search`, `crawl`, `media`) | ✅ Complete | 29 entity types seeded |
| Static UI — homepage + SERP | ✅ Complete | Vanilla JS, no build step |
| Cloudflare R2 favicon pipeline | ✅ Complete | `backend/r2_media.py`, verified live uploads |
| Geographic entity seeding (Upazilas, Unions) | ⏳ Not started | KhujoBot v1 Phase 0 |
| Person entities (MPs, Ministers) | ⏳ Not started | KhujoBot v1 Phase 0 |
| KhujoBot v1 crawler (GitHub Actions) | ⏳ Not started | See `khujobot_v1_plan.md` |
| Legal policies (Privacy, ToS, Crawl Policy) | ⏳ Not started | Required before public launch |
| Hetzner VPS deployment | ⏳ Not started | Gate: 50+ verified docs needed first |

---

## Team Responsibilities

| Tag | Owner | Scope |
|---|---|---|
| `[ADMIN]` | Founder (Sumon) | Account ownership, policy sign-off, source permissions, human review queue |
| `[AGENT]` | AI Agent | Code, schema migrations, scripts, API, UI |
| `[CRAWLER]` | Crawler team | URL fetching, extraction, media scouting, writing validated records |
| `[DATA]` | Data team | Seed files, entity curation, alias review, quality gates |

---

## ✅ Phase A — Static UI (COMPLETE)

All four files shipped and verified:
- `public/index.html` — Bangla-first landing page
- `public/search.html` — SERP with 2-col layout, Knowledge Graph sidebar
- `public/css/khujo.css` — Design system
- `public/js/khujo.js` — SearchBar, KG renderer, session history

---

## ✅ Phase B.0 — Core Schema (COMPLETE)

New PostgreSQL schema applied to Neon:
- Schemas: `core`, `content`, `search`, `crawl`, `media`
- Extensions: `pg_trgm`, `pgcrypto`, `unaccent`
- Taxonomy seeded (29 entity types), relation types, retention policies

---

## ✅ Phase B.1 — Neon DB Emergency Cleanup `[AGENT]` — COMPLETE

**Result: DB shrunk from 434 MB → 19 MB (96% reduction). Neon free tier is now at ~4% capacity.**

What was done (in order):
1. Dropped 11 legacy public-schema tables: `transliteration_map` (288MB), `autosuggestions`, `crawl_queue`, `search_logs`, `domains`, `entities`, `page_links`, `media_items`, `entity_mentions`, `bangla_synonyms`, `user_profiles`
2. Confirmed `public` schema is now clean (only `spatial_ref_sys` system table remains)
3. Deleted 748 low-quality crawler-harvested suggestions from `search.suggestion` (nav text like "Gallery", "Brands")
4. Ran `REINDEX TABLE search.suggestion` to rebuild the GIN trigram index compactly (134MB → 104KB)
5. Activated the 16 remaining curated suggestions (`state = 'active'`) so they appear in autocomplete

**New schema tables intact:** `search.suggestion` (16 rows, active), `core.entity` (16), `core.entity_type` (29), `content.document` (10)

---

## ✅ Phase B.2 — Entity Seeding `[DATA]` + `[AGENT]` — COMPLETE

**Result: 253 entities, 224 places, 373 names, 12 R2 favicons, and 509 base URLs seeded into Neon DB.**

What was done (in order):
1. `crawler/seed_geography.py` — seeded 8 Divisions, 14 Districts, 37 Upazilas, 164 Unions with official codes, lat/lon, and 134 autocomplete suggestions
2. `crawler/seed_sources.py` — seeded 14 Base Platforms & News Publishers (Google, Facebook, YouTube, Instagram, LinkedIn, Prothom Alo, Daily Star, etc.)
3. `crawler/utils/r2.py` — fetched domain favicons and uploaded to Cloudflare R2 (`https://pub-d8ff.../favicons/{domain}.ext`)
4. Populated `crawl.frontier_url` with 509 queued Base URLs ready for Phase 1 Site Scout

---

## 🟡 Phase B.3 — Crawler Architecture `[AGENT]` + `[CRAWLER]`

> [!IMPORTANT]
> **Core rule from `db-core-plan.md`:** "A crawler never marks truth. It creates documents, mentions, candidates, and evidence. A deterministic verifier or a human can promote a claim." Every crawled item lands as `state = 'candidate'`. Nothing reaches the SERP until a human approves it.

### B.3.1 — Seed URL Registry

All seed URLs require a `trust_tier`, `access_method`, and crawl permission note before adding.

| URL | Category | Access | Trust Tier |
|---|---|---|---|
| `https://www.prothomalo.com/` | News (bn) | `crawl_allowed` | 4 |
| `https://www.thedailystar.net/` | News (en) | `crawl_allowed` | 4 |
| `https://www.dhakatribune.com/` | News (en) | `crawl_allowed` | 4 |
| `https://bonikbarta.com/` | Business news (bn) | `crawl_allowed` | 3 |
| `https://bn.wikipedia.org/` | Bengali Wiki | `crawl_allowed` | 5 |
| LinkedIn BD profiles | Business/Networking | `api` (manual) | 3 |
| `https://www.facebook.com/choltigolpo/` | Social/Video | `manual_import` | 2 |
| `https://www.youtube.com/@chalti` | Video | `api` (YT Data v3) | 3 |

> [!NOTE]
> **YouTube & Facebook:** Raw HTML scraping is blocked by both platforms. The correct approach is:
> - **YouTube:** YouTube Data API v3 (free, 10,000 units/day) → filter by `viewCount > 100000`, topic `Bangladesh`
> - **Facebook:** Public Page content via Graph API (read-only public posts, requires App Review for some endpoints) — or manual import initially
> - **LinkedIn:** No public API for mass scraping. LinkedIn requires OAuth + Partnership. Plan: curate company/person profiles manually for now.

### B.3.2 — Crawler Design Constraints (from architecture docs)

The crawler must:
- Check `robots.txt` before every new domain
- Use a proper User-Agent: `KhujoBot/1.0 (+https://khujo.com.bd/bot)`
- Respect `crawl_delay_seconds` per host (default 5s)
- Hash content to avoid duplicate inserts
- Write **only** to `content.document` with `state = 'candidate'`
- Never write directly to `core.entity` — that requires human review
- Extract: title, body text, `og:image` URL, `og:description`, published date, canonical URL, language
- Extract favicon URL → pass to Media Scout (do NOT download to VPS)

### B.3.3 — Content Categories to Prioritize

| Category | Source Type | Rationale |
|---|---|---|
| News & Current Affairs | `document_kind = 'news'` | Highest daily query volume |
| Tech & Tutorials | `document_kind = 'article'` | High-value, long retention |
| Business & Networking | `document_kind = 'listing'` | B2B and job search intent |
| Bengali Wiki & Knowledge | `document_kind = 'article'` | Feeds Knowledge Graph directly |
| Video (YT/FB) | `media.asset` | Visual results, needs API access |

---

## 🟡 Phase B.4 — Media Pipeline `[AGENT]` + `[CRAWLER]`

> [!IMPORTANT]
> **Rule from blueprint:** "Media never touches the VPS disk." All media assets go to **Cloudflare R2**. The VPS stores only the R2/CDN URL.

### ✅ B.4.1 — Favicon System (COMPLETE)
- [x] `[AGENT]` After each crawl: extract favicon URL from `<link rel="icon">` or `https://domain/favicon.ico`
- [x] `[CRAWLER]` Upload favicon to Cloudflare R2 bucket (`khujo` under `favicons/{domain}.ext`) via `backend/r2_media.py`
- [x] `[AGENT]` Verified live uploads to Cloudflare R2 public URL (`https://pub-d8ff02e059814132b7f971370e65283d.r2.dev`)

### B.4.2 — Image Crawling (R2 Storage Policy)

> [!IMPORTANT]
> **Strict DB Rule:** **No binary image data, base64 blobs, or raw image bytes EVER touch Neon DB.**
> If `og:image` is fetched during crawling, the crawler uploads the image directly to Cloudflare R2 (`khujo` bucket under `images/{hash}.jpg`) and ONLY writes the short public R2 URL string (`https://pub-d8ff.../images/{hash}.jpg`) to `media.asset` linked to the document. This keeps Postgres DB size clean and minimal (<20MB).

### B.4.3 — Video Scouting (YouTube)
- [ ] `[AGENT]` Write YouTube Data API v3 scout script
- [ ] Filter: `regionCode=BD`, `relevanceLanguage=bn`, `viewCount > 100000`
- [ ] Store video metadata (title, thumbnail URL, channel, duration) in `media.asset` (`media_kind = 'video'`)
- [ ] Thumbnail → R2 bucket

---

## 🟡 Phase B.5 — Human Verification Workflow `[ADMIN]` + `[AGENT]`

The verification loop is the safety gate before Hetzner deployment:

```
Crawler writes candidate → Admin Dashboard shows queue
→ ADMIN reviews each item → clicks Approve or Reject
→ Approved: state = 'verified', appears on SERP
→ Rejected: state = 'rejected', never shown
→ Loop repeats until pipeline quality is trusted
→ After trust established: automate with confidence rules
```

### ✅ B.5.1 — Admin Dashboard (`public/admin.html`) — COMPLETE
Upgraded dashboard shipped with:
- [x] `[AGENT]` Document preview with source URL, domain favicon, title, kind badge, full body preview
- [x] `[AGENT]` Batch approve and batch reject buttons with multi-select checkboxes
- [x] `[AGENT]` Live stats panel: pending candidates count, approved & live count, rejected count, Neon DB storage size
- [x] `[AGENT]` Real-time search filter for candidate title, URL, or content snippet


### B.5.2 — Quality Curation of Existing Crawl Data
The 10 documents currently in `content.document` from the earlier crawler run need `[ADMIN]` review:
- [ ] `[ADMIN]` Open admin dashboard, review each document
- [ ] `[ADMIN]` Approve documents that align with Khujo's content standards
- [ ] `[ADMIN]` Reject any that are JavaScript-heavy page shells (not real content)

---

## 🟡 Phase B.6 — SERP Entity UI Cards `[AGENT]`

Different entity types need specialized Knowledge Card layouts on the search results page:

| Entity Type | Card Design |
|---|---|
| `person` (MP/Minister) | Photo (from R2), name in bn+en, role, constituency, party |
| `administrative_area` (Upazila/Union) | Map pin icon, division/district hierarchy, population |
| `organization` (Ministry/University) | Logo, founded year, head, location, official URL |
| `business` | Rating, address, category, operating hours |
| `news` source | Publication logo, trust tier badge |

- [ ] Update `public/js/khujo.js` `drawKnowledgeGraph()` to accept `entity_type` and render the appropriate card

---

## 🔴 Phase C.1 — Data & Legal Policies `[ADMIN]`

> [!CAUTION]
> Per `db-core-plan.md` Section 0: **"Freeze a data policy before the first wide crawl."** This has NOT been done yet. These documents must exist before expanding the crawler.

Documents needed (to be drafted and stored in `docs/policies/`):

| Document | Purpose |
|---|---|
| **Privacy Policy** | What data Khujo collects from users (search queries, fingerprint-only, no PII), how stored, retention |
| **Terms of Service** | Platform use rules, content standards, liability |
| **Web Crawling Policy** | Which sites Khujo crawls, respects robots.txt, contact for removal, user-agent identity |
| **Content Removal Policy** | How individuals or publishers request removal of indexed content |
| **Data Retention Policy** | Formalizes the tiered retention (news 30d, article 90d, etc.) |
| **Source Trust Policy** | How `trust_tier` is assigned per source class |

- [ ] `[ADMIN]` Review and approve all policy drafts
- [ ] `[AGENT]` Add privacy policy and ToS links to `public/index.html` footer
- [ ] `[AGENT]` Add crawling policy URL to KhujoBot User-Agent string

---

## 🔴 Phase C.2 — Production Deployment to Hetzner `[ADMIN]` + `[AGENT]`

> [!IMPORTANT]
> **Gate condition:** Do NOT proceed to Hetzner until ALL of the following are true:
> 1. Neon DB cleanup complete and DB < 20% capacity
> 2. At least 50 human-verified documents appear on SERP
> 3. At least 1 full geographic seeding complete (all Upazilas)
> 4. All 6 policy documents drafted and approved by `[ADMIN]`
> 5. YouTube favicon pipeline producing real R2 URLs
> 6. Admin dashboard reviewed and signed off

**Deployment steps (when gate is passed):**
- [ ] `[ADMIN]` Provision Hetzner CAX11 ARM (Singapore, 4 vCPU / 8GB RAM / 40GB SSD, ~$5/mo)
- [ ] `[AGENT]` Configure Cloudflare: DNS, DDoS, API cache rules (30s TTL for `/api/v1/search`)
- [ ] `[AGENT]` Install PostgreSQL 16, Nginx, Python 3.12 on VPS
- [ ] `[AGENT]` Migrate validated Neon data → Hetzner Postgres
- [ ] `[AGENT]` Deploy FastAPI as systemd service, static `public/` via Nginx
- [ ] `[AGENT]` Set crawler write endpoint: SSL-only, IP-allowlisted Hetzner Postgres
- [ ] `[AGENT]` Configure `pg_cron` for nightly content expiry cleanup

---

## Verification Gates (from `db-core-plan.md`)

| Gate | Evidence Required |
|---|---|
| **Schema** | Fresh Postgres install succeeds, constraints exist |
| **Taxonomy** | Every entity has type, preferred name, language, source |
| **Crawl** | robots/rate-limit works, URL dedup confirmed by second run |
| **Search** | 100 hand-labelled queries pass recall review; no candidate docs appear |
| **Security** | Backup restore rehearsed; secrets not in Git; rate limits active |
| **Release** | p95 latency target met; 404/500 monitoring active; manual rollback tested |

---

## Immediate Next Steps (in order)

1. **`[AGENT]`** Fix and re-run the Neon DB cleanup — actually drop `transliteration_map` and old tables
2. **`[DATA]`** Source authoritative Bangladesh Upazila/Union data file
3. **`[ADMIN]`** Begin reviewing the 10 existing candidate documents in admin dashboard
4. **`[AGENT]`** Upgrade admin dashboard with richer preview and stats
5. **`[AGENT]`** Build YouTube Data API v3 scout script
6. **`[AGENT]`** Build favicon fetcher + R2 upload pipeline (can use R2 during testing phase)
7. **`[ADMIN]`** Draft or approve the 6 policy documents
