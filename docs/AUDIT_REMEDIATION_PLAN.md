# Khujo — Audit Remediation & Retrieval Architecture Master Plan
**Source Audit:** `khujo_code_audit.md` (Sep 19, 2026)  
**Branch:** `feature/corebite`  
**Status:** In Progress / Resumable Master Roadmap

---

## 0. Executive Context & Current State

### What was committed on `feature/corebite` (Commit `ed9e727`):
- `backend/sql/0003_knowledge_layer.sql` — Knowledge layer tables
- `backend/sql/0004_pipeline_queues.sql` — Queue tracking timestamps
- `backend/sql/0005_bangla_lexicon.sql` — Bangla dictionary & morphology tables
- `crawler/geo_pipeline/` — Hierarchy worker (5,106 records), micro-locations, harvester v2
- `crawler/worker_01_fetch.py`, `worker_02_extract.py`, `worker_03_knowledge.py` — Pipeline workers
- `crawler/data/BengaliDictionary.json` & `lexicon_preview.csv` — Full lexicon assets

### The Binding Constraint:
The audit revealed that **search quality is not a data volume problem**; it is an architectural flaw in the retrieval engine:
1. **Unindexable Query:** The search endpoint uses a correlated subquery on `unnest(terms)` with wildcard `ILIKE`, causing a sequential table scan across all partitions on every request (Defect D4).
2. **Broken Ranking:** Binary score buckets (URL=100, Title=80) with no TF-IDF, no BM25, and no document length normalization (Defect D6).
3. **Bangla Inflection Failure:** Asymmetric substring matching causes natural inflected queries (e.g. "ঢাকায়", "ঢাকার") to fail silently against root stems ("ঢাকা") (Defect D5).
4. **Security & Integrity Leaks:** Unauthenticated `/admin` endpoints (D1), autocomplete database poisoning (D2), and sensitive database stack trace exposure (D11).

---

## 1. Master Defect Register (D1 – D24) & Fix Status

| Defect | Severity | Category | File / Line | Problem Summary | Remediation Strategy | Status |
|---|---|---|---|---|---|---|
| **D1** | 🔴 CRITICAL | Security | `backend/main.py:367-450` | `/admin/*` endpoints have no authentication | Add API Key / Bearer Auth dependency (`ADMIN_API_KEY`) | ✅ DONE (Phase 1) |
| **D2** | 🔴 CRITICAL | Data Integrity | `backend/main.py:197-208` | Every search query written directly to live suggestions | Set `state = 'candidate'`, serve only `active`, promote via cron | ✅ DONE (Phase 1) |
| **D3** | 🔴 CRITICAL | Retrieval | `backend/main.py:56-72` | Entity resolved via `ILIKE '%q%' LIMIT 1` by ID | Exact match first, confidence threshold, avoid eager term pollution | ⏳ Planned Phase 4 |
| **D4** | 🔴 CRITICAL | Performance | `backend/main.py:134-162` | Correlated `unnest()` subquery defeats GIN trgm index | Replace with pg_trgm similarity operator `%` or tsvector/BM25 | ⏳ Planned Phase 3 |
| **D5** | 🔴 CRITICAL | Retrieval | `backend/main.py:155` | Bangla case inflections fail silently (`ঢাকায়` misses `ঢাকা`) | Implement suffix-stripping normalizer at index and query time | ⏳ Planned Phase 4 |
| **D6** | 🟠 HIGH | Retrieval | `backend/main.py:133-149` | Arbitrary ranking formula; URL match = 100 dominates | BM25 scoring with title/body weights + authority boost | ⏳ Planned Phase 3 |
| **D7** | 🟠 HIGH | Frontend | `public/js/khujo.js` | Backend returns `knowledge_graph`, frontend never renders it | Implement entity card widget in search results UI | ⏳ Planned Phase 5 |
| **D8** | 🟠 HIGH | Frontend | `public/js/khujo.js:259` | `drawKnowledgeGraph()` draws fake domain nodes | Replace with true entity-relationship graph visualization | ⏳ Planned Phase 5 |
| **D9** | 🟠 HIGH | Security | `backend/main.py:17-18` | `allow_origins=["*"]` + `allow_credentials=True` is invalid/insecure | Specify allowed origins, restrict credentials | ✅ DONE (Phase 1) |
| **D10** | 🟠 HIGH | Pipeline | `backend/ner_script.py:8-52` | Quadratic $O(N \times M)$ substring loop, non-idempotent assertions | Aho-Corasick or Trie string matcher + `ON CONFLICT` | ⏳ Planned Phase 6 |
| **D11** | 🟡 MEDIUM | Security | `backend/main.py:224, 364...` | `HTTPException(500, detail=str(e))` leaks internal SQL | Log traceback server-side, return clean generic JSON message | ✅ DONE (Phase 1) |
| **D12** | 🟡 MEDIUM | Architecture | `backend/main.py:188-212` | `GET /search` executes write transaction & commits | Decouple telemetry to async background task or separate logging | ✅ DONE (Phase 1) |
| **D13** | 🟡 MEDIUM | UX | `public/js/khujo.js:381` | Perspectives panel uses 3 hardcoded static strings | Wire dynamic category or semantic breakdown | ⏳ Planned Phase 5 |
| **D14** | 🟡 MEDIUM | Build | `requirements.txt` | Root requirements mixes pip packages with npm dependencies | Clean `requirements.txt` to pure Python pip dependencies | ⏳ Planned Phase 0 |
| **D15** | 🟡 MEDIUM | Crawler | `crawler/seed_sources.py:20-56` | Google, FB, YT, Insta, LinkedIn seeded as crawl targets | Remove uncrawlable giant platforms; focus on BD news/edu | ⏳ Planned Phase 6 |
| **D16** | 🟡 MEDIUM | Data | `0001_khojo_core.sql:348` | Document expiration computed but never enforced | Align retention policy with corpus targets | ⏳ Planned Phase 6 |
| **D17** | 🟡 MEDIUM | Latency | `backend/main.py:322-350` | Autocomplete does unindexed document title regex splitting | Rely on pre-computed `search.suggestion` table | ✅ DONE (Phase 1) |
| **D18** | 🟢 LOW | Hygiene | `backend/*.py` | 13 one-off emergency Neon cleanup scripts cluttering backend | Move to `backend/archive/scripts/` | ⏳ Planned Phase 0 |
| **D19** | 🟢 LOW | Hygiene | `backend/crawler.py` | Outdated 149-line crawler exists alongside `crawler/` | Archive / remove `backend/crawler.py` | ⏳ Planned Phase 0 |
| **D20** | 🟢 LOW | Hygiene | `backend/app/models/` | Dead ORM models for dropped tables | Clean out unused model files | ⏳ Planned Phase 0 |
| **D21** | 🟢 LOW | Hygiene | `backend/app/models/search.py` | Hardcoded dummy `DATABASE_URL` placeholder | Remove dead file or route to config | ⏳ Planned Phase 0 |
| **D22** | 🟢 LOW | Documentation | `README.md` | References nonexistent React/Vite frontend files | Update README to reflect current vanilla JS architecture | ⏳ Planned Phase 0 |
| **D23** | 🟢 LOW | Tooling | Repository root | No test suite, no CI, no `.env.example` | Create `.env.example`, `pytest` configuration, basic CI test | ⏳ Planned Phase 0 |
| **D24** | 🟢 LOW | Frontend | `public/css/khujo.css:99` | Font stack ends at `sans-serif` without Bangla system fallbacks | Add `Kalpurush`, `Siyam Rupali`, `SolaimanLipi`, `Vrinda` fallback | ⏳ Planned Phase 0 |

---

## 2. Phased Execution Roadmap

### Phase 0: Repository Hygiene & Foundation (Fast Wins)
- [ ] **Task 0.1:** Move 13 dead scripts in `backend/` to `backend/archive/`.
- [ ] **Task 0.2:** Remove `backend/crawler.py` and clean dead models in `backend/app/models/`.
- [ ] **Task 0.3:** Fix root `requirements.txt` by removing the npm package lines.
- [ ] **Task 0.4:** Create `.env.example` documenting all required environment variables.
- [ ] **Task 0.5:** Fix `public/css/khujo.css` Bangla font fallback stack (SolaimanLipi, Kalpurush, etc.).
- [ ] **Task 0.6:** Add test harness with baseline smoke tests.

### Phase 1: Security, Error Masking & Suggestion Gate (COMPLETED ✅)
- [x] **Task 1.1 (D1):** Secure all `/api/v1/admin/*` endpoints with API Key authentication (`X-Admin-Key` header).
- [x] **Task 1.2 (D9):** Fix CORS configuration in `backend/main.py`.
- [x] **Task 1.3 (D11):** Replace raw `str(e)` in 500 error responses with standardized safe error logging.
- [x] **Task 1.4 (D2, D17):** Sanitize `search.suggestion` pipeline: insert new queries as `candidate` state; only serve `active` suggestions; remove unindexed document title scanning from the latency path.
- [x] **Task 1.5 (D12):** Move query event logging out of the synchronous GET request path using FastAPI `BackgroundTasks`.

### Phase 2: Golden Query Evaluation Benchmark
- [ ] **Task 2.1:** Create `tests/golden_queries.json` with 200 representative queries (Bangla, English, Banglish, navigational, factual, ambiguous, inflected).
- [ ] **Task 2.2:** Build `tests/eval_harness.py` to calculate Mean Reciprocal Rank (MRR) and Precision@K baseline.

### Phase 3: Inverted Index & Modern BM25 / pg_trgm Ranking Engine
- [ ] **Task 3.1 (D4):** Rewrite the search SQL query. Eliminate the correlated `unnest()` subquery. Use indexed trigram matching (`title_normalised % :q`) or full-text tsvector search.
- [ ] **Task 3.2 (D6):** Replace the static score formula (`100.0 * url_match + 80.0 * title_match`) with a normalized scoring algorithm incorporating term frequency and document authority.

### Phase 4: Bangla Morphology & Query Understanding
- [ ] **Task 4.1 (D5):** Implement a lightweight rule-based Bangla suffix stripper (`crawler/lexicon/bangla_stemmer.py`):
  - Strip locative/possessive/plural suffixes: `-র`, `-এর`, `-তে`, `-য়ে`, `-য়`, `-গুলো`, `-গুলি`, `-দের`
  - Safeguard words in protected stoplist/dictionary so valid roots are not truncated.
- [ ] **Task 4.2 (D3):** Refactor entity resolution: exact match -> stemmed match -> fuzzy candidate, requiring minimum similarity score before triggering entity alias expansions.

### Phase 5: Knowledge Card & Frontend Experience
- [ ] **Task 5.1 (D7):** Update `public/js/khujo.js` and `public/search.html` to properly render the `knowledge_graph` entity card (title, image, summary, facts table, official links).
- [ ] **Task 5.2 (D8):** Replace dummy domain rectangles in `drawKnowledgeGraph()` with real entity connection nodes.
- [ ] **Task 5.3 (D13):** Replace static perspectives with context-aware query analysis or dynamic topic pills.

### Phase 6: Crawler Hardening & Maintenance
- [ ] **Task 6.1 (D15):** Remove uncrawlable platforms (Google, FB, YT, etc.) from `crawler/seed_sources.py`.
- [ ] **Task 6.2 (D10):** Rewrite `backend/ner_script.py` using Aho-Corasick automaton with word boundaries and `ON CONFLICT DO NOTHING` for assertions.
- [ ] **Task 6.3 (D16):** Update retention policy documentation and scheduling.

---

## 3. How to Resume Work from Any Account
If you start a fresh session or change accounts:
1. Ensure you are on the `feature/corebite` branch (`git checkout feature/corebite`).
2. Open this document: `docs/AUDIT_REMEDIATION_PLAN.md`.
3. Check off tasks as they are implemented and verified.
4. Run tests with `pytest`.
