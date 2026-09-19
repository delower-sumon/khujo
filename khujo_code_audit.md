# **Khujo — Independent Code Audit** 

Repository review against the September 2026 planning documents 

Subject: <mark>khujo-main.zip</mark> ·  63 files, 7,395 lines  ·  snapshot dated 2026-07-24 Audit date: 19 September 2026  ·  Method: full static read of every source file Compared against: <mark>khujo</mark> _ <mark>executive</mark> _ <mark>audit.md</mark> , <mark>khujo</mark> _ <mark>9phase</mark> _ <mark>plan.md , location</mark> _ <mark>pipeline</mark> _ <mark>plan.md</mark> 

_Note on rendering: no Bengali typeface was available in the environment that produced this PDF, so Bangla examples are given in romanised form. This affects presentation only, not the findings._ 

## **1. Verdict** 

**The planning documents describe a system that does not exist in this repository.** Every artefact marked complete for Phase 1 and Phase 2 — the knowledge-layer tables, the three pipeline workers, the entity crawler, the Banglish transliteration layer, the geo pipeline — is absent. Migrations stop at <mark>0002</mark> . The newest file is dated 24 July 2026. 

**What does exist is a well-designed database schema attached to a search endpoint that cannot rank, cannot use its own indexes, and cannot match inflected Bangla.** The schema is genuinely strong. The retrieval layer is not a search engine yet; it is a substring filter sorted by publication date. 

**Nothing found is unrecoverable.** No secrets are committed. The foundations worth keeping are real. But the 90-day plan begins from a starting line roughly two phases behind where the documents place it, and the two highest-severity defects are live security and data-integrity problems, not missing features. 

### **Action required before planning continues** 

Run <mark>git log --oneline -20</mark> and <mark>git status</mark> against the local working copy. If Phase 1/2 work exists uncommitted on the development machine, sections 2 and 8 of this report change materially. If the log ends in July and the tree is clean, the planning documents should be treated as aspirational and rewritten against this audit. 

## **2. Documentation versus repository** 

Each row below was verified by direct search of the full source tree. 

|**CLAIMED COMPLETE IN PLANNING DOCUMENTS**|**FOUND**|**EVIDENCE**|
|---|---|---|
|core.search_dictionary— "schema done"|**No**|Zero occurrences of the string in any file|
|core.entity_revisions (append-only versioning)|**No**|Not in any migration|
|core.search_boosts|**No**|Not in any migration|
|core.hidden_entities|**No**|Not in any migration|
|core.locality_overrides ,<br>core.tag_overrides|**No**|Not in any migration|
|entity.current_revision_id column|**No**|Absent from<br>core.entity DDL|
|worker_01_fetch.py|**No**|File does not exist|
|worker_02_extract.py|**No**|File does not exist|
|worker_03_knowledge.py|**No**|File does not exist|
|0004_pipeline_queues.sql,<br>parsed_at ,<br>entities_extracted_at|**No**|Migrations end at<br>0002|
|entity_crawler.py(~25 Wikipedia targets)|**No**|File does not exist|
|avro-lib.min.js— "Avro transliteration integrated"|**No**|No transliteration code anywhere in<br>public/|
|crawler/geo_pipeline/ +<br>base_hierarchy.csv (5,106 records)|**No**|Directory does not exist|
|khujo_harvester_v2.py — "READY"|**No**|File does not exist|
|worker_03_enrich_colab.py— "READY"|**No**|File does not exist|
|64 districts with coordinates; 494 upazilas; 4,540 unions|**Partial**|bd_admin_hierarchy.jsonholds 8 divisions,**14**districts,**37**upazilas|
|PostgreSQL schema, 5 schemas, entity graph|**Yes**|0001_khojo_core.sql,572 lines — accurate and good|
|Crawl pipeline with robots compliance and R2 upload|**Yes**|crawler/content_crawler.py,<br>site_scout.py,<br>utils/|
|Bangla frontend (lang, translate=no, Hind Siliguri)|**Yes**|Present in<br>index.html and<br>search.html|



The audit document scores the frontend 10/10 for Bangla readiness on the strength of a transliteration layer that is not in the repository. Corrected score, on what is present: roughly 6/10 — correct language metadata and typography, no input transliteration, no Bengali font fallback in CSS ( <mark>public/css/khujo.css:99</mark> ends the stack at <mark>sans-serif )</mark> . 

## **3. What actually exists** 

### **3.1 The schema is the strongest asset** 

- <mark>backend/sql/0001</mark> _ <mark>khojo</mark> _ <mark>core.sql</mark> is 572 lines of disciplined design and should be preserved and extended, not replaced. It establishes: 

- Five schemas ( <mark>core</mark> , <mark>crawl</mark> , <mark>content , search</mark> , <mark>media</mark> ) with clean separation of concerns. 

- Nine domain ENUMs, including <mark>core.script</mark> _ <mark>kind</mark> (bangla / latin / mixed / other) and <mark>core.name</mark> _ <mark>kind</mark> covering aliases, abbreviations, transliterations and misspellings — the right vocabulary for a multilingual entity store. 

- An append-only <mark>core.assertion</mark> + <mark>core.assertion</mark> _ <mark>evidence</mark> model, so every fact carries provenance back to a source record. This is the correct design for a human-verified knowledge base. 

- <mark>content.document</mark> LIST-partitioned across seven partitions by document kind, with trigram GIN indexes on normalised title and body. 

- A <mark>crawl.frontier</mark> _ <mark>url</mark> → <mark>crawl.fetch</mark> lease state machine with proper state ENUMs — restartable crawling done correctly. 

- A retention policy table with a <mark>BEFORE INSERT</mark> trigger computing <mark>expires</mark> _ <mark>at</mark> per document kind. 

<mark>0002</mark> _ <mark>nullable</mark> _ <mark>unique</mark> _ <mark>indexes.sql</mark> is a thoughtful correction converting four unique constraints to partial unique indexes so that absent optional values 

do not collide. This is the work of someone who reads their own schema carefully. 

### **3.2 Working code** 

|**COMPONENT**|**LINES**|**ASSESSMENT**|
|---|---|---|
|crawler/content_crawler.py|290|Real. Robots check, boilerplate stripping, canonical URL resolution, og:image upload to R2,<br>stages candidates for review.|
|crawler/site_scout.py|176|Real. Discovers article URLs from seeded base domains into the frontier.|
|crawler/utils/ (robots, links, r2)|206|Real and correctly factored.|
|crawler/seed_geography.py|213|Works, but limited by the thin data file it reads.|
|public/css/khujo.css|1,060|Hand-written, coherent, no framework. Good.|
|public/js/khujo.js|687|Clean vanilla JS. See defects D10–D12 for what it does not do.|
|public/admin.html|735|Functional review queue UI.|
|backend/r2_media.py|178|Sound R2 client with clear configuration errors.|



### **3.3 Security posture of the repository itself** 

No credentials are committed. All secrets are read through <mark>os.getenv ; .env</mark> is correctly gitignored. The single hardcoded connection string ( <mark>backend/app/models/search.py:7 )</mark> is an obvious placeholder containing no real host. The repository is safe to publish. 

## **4. The search engine: three structural failures** 

This section concerns <mark>backend/main.py:31–167</mark> , the <mark>/api/v1/search</mark> endpoint. It is the product. It has three problems that compound each other. 

### **4.1 The match predicate defeats every index on the table** 

WHERE content.document.state = 'verified' AND EXISTS ( SELECT 1 FROM unnest(CAST(:terms AS text[])) term WHERE content.document.title_normalised ILIKE '%' || term || '%' OR content.document.canonical_url   ILIKE '%' || term || '%' OR content.document.body_normalised ILIKE '%' || term || '%' ) 

The <mark>gin</mark> _ <mark>trgm</mark> _ <mark>ops</mark> indexes created on <mark>title</mark> _ <mark>normalised</mark> and <mark>body</mark> _ <mark>normalised</mark> can serve <mark>ILIKE '%x%'</mark> — that is precisely what pg_trgm exists for. They cannot serve it here, because the pattern is constructed inside a correlated subquery over <mark>unnest() .</mark> The planner has no constant pattern to plan against, so it falls back to a sequential scan of every verified document across all seven partitions, on every query. 

The scoring expression then calls <mark>similarity(body</mark> _ <mark>normalised, :q)</mark> on each surviving row, computing trigram sets over full article bodies at query time. The two effects multiply. At the current corpus size this is invisible; at the 50,000-document target in the plan it is a timeout. The p95 < 400 ms launch criterion cannot be met by this query shape at any corpus size that matters. 

### **4.2 The ranking formula does not rank** 

CASE WHEN url   ILIKE '%term%' THEN 100.0 ELSE 0.0 END + CASE WHEN title ILIKE '%term%' THEN  80.0 ELSE 0.0 END + similarity(title_normalised, :q) * 20.0 + similarity(body_normalised,  :q) *  5.0 + CASE WHEN document_kind IN ('listing','official') THEN 15.0 ELSE 0.0 END 

Four consequences follow directly: 

**URL match outweighs everything.** Any page with the query string anywhere in its URL scores 100 and outranks the authoritative page on the subject. 

This is the single easiest ranking signal in the world to game, and it is weighted highest. 

- **Title matches all tie.** Every document containing the term in its title scores exactly 80. The tiebreak is <mark>published</mark> _ <mark>at DESC</mark> . For the majority of queries this system is a reverse-chronological news feed, not a ranked index. 

- **No term frequency, no inverse document frequency, no length normalisation.** A document mentioning the query once and one mentioning it forty times score identically. A term appearing in every document is weighted the same as a rare, discriminating one. 

- **The body signal is dead weight.** Trigram similarity between a two-word query and a 3,000-word article returns roughly 0.004; multiplied by 5.0 it contributes about 0.02 to a score whose other terms are 80 and 100. It costs a full-table computation and contributes nothing. 

### **4.3 Bangla inflection is matched in one direction only** 

Substring matching creates an asymmetry that is fatal for Bangla specifically. Using _Dhaka_ as the example (Bangla stem _dhaka_ , inflected forms _dhaka-r_ possessive, _dhaka-y_ locative): 

|**USER QUERY**|**DOCUMENT CONTAINS**|**MATCHES?**|**WHY**|
|---|---|---|---|
|dhaka|dhaka|**Yes**|Exact substring|
|dhaka|dhaka-r / dhaka-y|**Yes**|Stem is a substring of the inflected<br>form — works by accident|
|dhaka-r|dhaka|**No**|Inflected form is not a substring of<br>the stem — silent miss|
|dhaka-y|dhaka-r|**No**|Neither is a substring of the other|



Bangla speakers inflect constantly in natural queries. Roughly half of realistic query formulations fall into the failing rows above, and they fail _silently_ — the user sees an empty or thin result page and concludes the index is small. No volume of additional crawling corrects this. It requires a suffix-stripping normaliser applied symmetrically at index time and query time. 

This is the most important single finding in the report, because the planning documents attribute the product's weakness entirely to data volume. It is not a data problem. 

## **5. Defect register** 

Twenty-four defects, ordered by severity. Locations are file and line in the audited snapshot. 

#### **CRITICAL D1 — Every administrative endpoint is unauthenticated** 

backend/main.py:257–404 

Seven endpoints — <mark>/admin/stats</mark> , <mark>/admin/candidates ,</mark> document <mark>PUT</mark> , <mark>verify , reject , restore , batch</mark> _ <mark>verify</mark> , <mark>batch</mark> _ <mark>reject</mark> — carry no authentication, no authorisation and no rate limit. Anyone who reaches the API can mass-verify spam into the live index, reject the entire verified corpus, or rewrite document titles and summaries arbitrarily. Combined with <mark>allow</mark> _ <mark>origins=["*"]</mark> this is reachable from any web page in a visitor's browser. On the January 2027 VPS this is an open door. **Fix before any public deployment:** API key or session auth on an <mark>/admin</mark> router dependency, plus origin restriction. 

#### **<mark>CRITICAL</mark> D2 — The search endpoint poisons its own autocomplete** 

backend/main.py:139–149 

Every query received is written into <mark>search.suggestion</mark> if not already present, with <mark>popularity</mark> _ <mark>score = 1</mark> and no <mark>state</mark> value — despite <mark>search.suggestion</mark> _ <mark>state</mark> existing in the schema as an ENUM for exactly this purpose. Typos, probe strings, garbage and abuse become live autocomplete suggestions immediately, with no review gate. This has already caused damage once: <mark>backend/clean</mark> _ <mark>suggestions.py</mark> exists to delete 748 low-quality rows and <mark>backend/reindex</mark> _ <mark>suggestions.py</mark> to reclaim 134 MB of GIN index bloat caused by them. The symptom was cleaned; the cause is still in the code path. **Fix:** insert as <mark>state = 'candidate'</mark> , serve only <mark>state = 'active'</mark> , promote on a frequency threshold. 

#### **<mark>CRITICAL</mark> D3 — Entity resolution is arbitrary and contaminates the result set** 

backend/main.py:39–48, 62–67 

The knowledge-graph entity is chosen by <mark>ILIKE '%q%'</mark> with <mark>LIMIT 1</mark> , tie-broken on <mark>entity</mark> _ <mark>name</mark> _ <mark>id</mark> — that is, on insertion order. A query for a city may resolve to a university that happens to contain the city name. Every alias of whichever entity won is then injected into the document search with weight equal to the user's actual query. One wrong entity match therefore corrupts the entire result set, not merely the card. **Fix:** exact-normalised match first, scored candidate ranking second, confidence threshold before any expansion. 

#### **<mark>CRITICAL</mark> D4 — Match predicate prevents all index use** 

backend/main.py:96–103 

See section 4.1. Sequential scan across seven partitions on every query, plus per-row trigram computation over full document bodies. **Fix:** the predicate must be rewritten, not tuned. This is the rewrite that the inverted-index work replaces. 

#### **<mark>CRITICAL</mark> D5 — Bangla inflected queries fail silently** 

backend/main.py:96–103 (same predicate) 

See section 4.3. Substring matching is asymmetric with respect to Bangla case suffixes. **Fix:** a suffix-stripping normaliser applied identically at index time and query time, with a stoplist of words that must not be stemmed. 

#### **HIGH D6 — Ranking has no term-frequency, IDF or length normalisation** 

backend/main.py:75–91 

See section 4.2. Binary buckets with a gameable URL signal weighted highest. **Fix:** BM25 over a real postings table, with the verification and authority boosts applied on top rather than instead. 

#### **<mark>HIGH</mark> D7 — The knowledge graph card is never rendered** 

backend/main.py:162 returns it; public/js/khujo.js contains no reference 

The API returns a <mark>knowledge</mark> _ <mark>graph</mark> object. The frontend never reads the key. The entity card — the entire stated differentiator against Google and Bing — is computed server-side and silently discarded before it reaches the user. 

#### **HIGH D8 — What appears to be the knowledge graph is decorative** 

public/js/khujo.js:259, called at :490 with data built at :473 

<mark>drawKnowledgeGraph()</mark> renders an SVG of a gradient rectangle with up to three nodes. Those nodes are the domains of the top three search results, derived from <mark>sourceMap</mark> . They are not entities, not graph relations, and carry no knowledge-layer data. A reader of the codebase, or of the audit document, would reasonably conclude the knowledge graph is implemented. It is a background illustration. 

#### **HIGH D9 — CORS wildcard combined with credentials** 

backend/main.py:13–19 

<mark>allow</mark> _ <mark>origins=["*"]</mark> with <mark>allow</mark> _ <mark>credentials=True</mark> is rejected outright by browsers per the CORS specification, so the configuration is both insecure in intent and non-functional in effect. It signals that authentication has not been considered. **Fix alongside D1.** 

#### **<mark>HIGH</mark> D10 — NER pass is quadratic and non-idempotent** 

backend/ner_script.py:8–52 

The script loads every Bangla entity name and every document into memory, then performs a nested Python loop of substring tests — documents × entity names. For each hit it inserts a new row into <mark>core.assertion</mark> with no uniqueness guard; the evidence insert has <mark>ON CONFLICT DO NOTHING</mark> but the assertion insert does not. Running it twice doubles the assertion table. It also has no word-boundary awareness, so short entity names match inside unrelated words. This is the "Bangla NER" the audit document rates as a high-priority tooling gap; the rating is correct but understated. 

#### **MEDIUM D11 — Internal error detail is returned to clients** 

backend/main.py:167, 254, 278, 319, 351, 362, 372, 382, 393, 404 

Ten handlers raise <mark>HTTPException(status</mark> _ <mark>code=500, detail=str(e))</mark> , returning raw exception text — including SQL fragments, schema names and driver messages — to unauthenticated callers. **Fix:** log the detail server-side, return a generic message and a correlation identifier. 

#### **<mark>MEDIUM</mark> D12 — A GET request performs writes and commits** 

##### backend/main.py:130–151 

<mark>/api/v1/search</mark> inserts a query event, updates or inserts a suggestion, and commits — all inside a <mark>GET .</mark> Beyond the idempotency violation, this makes every search a write transaction against the primary, which removes the option of serving search from a read replica and inflates write load on a free-tier database. The failure path is <mark>except Exception: rollback; pass</mark> , so write failures are invisible. 

#### **<mark>MEDIUM</mark> D13 — Static text is presented as query analysis** 

public/js/khujo.js:381 ( <mark>getPerspectives )</mark> 

The "perspectives" panel returns three hardcoded strings, selected only by whether the query contains any Bangla codepoint. The inline comment is honest — _static until AI is wired_ — but the UI presents it as query-specific insight. 

#### **MEDIUM D14 — The root requirements file is not installable** 

##### requirements.txt 

The file mixes pip requirements with an npm dependency list written in <mark>name: ^version</mark> form (React, Three.js, Tailwind, Vite and twenty-four others). <mark>pip install -r requirements.txt</mark> fails on the first npm line. Those packages belong to a React frontend that the readme says was abandoned and whose files <mark>( src/ , package.json , vite.config.ts</mark> ) are not in the repository. <mark>backend/requirements.txt</mark> is valid but uses CRLF line endings. 

#### **MEDIUM D15 — Crawl seed list includes five uncrawlable domains** 

crawler/seed_sources.py:20–56 

Google, Facebook, YouTube, Instagram and LinkedIn are seeded as sources. All five disallow this crawling in robots.txt and terms of service, none will yield Bangladeshi content, and attempting them risks the crawler's IP reputation. The remaining eight seeds (Prothom Alo, Daily Star, Dhaka Tribune, Bonik Barta, Kaler Kantho, Jugantor, Bengali Wikipedia, Parliament) are the correct targets. 

#### **MEDIUM D16 — Retention policy is computed but never enforced, and contradicts the plan** 

backend/sql/0001_khojo_core.sql:348–364; no consumer in any script 

The trigger sets <mark>expires</mark> _ <mark>at</mark> on insert — 30 days for news, 7 for social — but no job deletes or archives expired rows, and the search query does not filter on <mark>expires</mark> _ <mark>at .</mark> So the mechanism is currently inert. More importantly, whichever way it is resolved conflicts with the plan: the soft-launch criterion of 50,000 verified documents is unreachable if a 30-day news retention is ever enforced, and the retention design is pointless if it is not. This requires a decision, not code. 

#### **<mark>MEDIUM</mark> D17 — Suggestions endpoint mines document titles at request time** 

backend/main.py:209–247 

When fewer than <mark>limit</mark> suggestions are found, the endpoint selects up to <mark>limit × 10</mark> document titles with a leading-wildcard <mark>ILIKE</mark> , then splits and filters them in Python on every keystroke. This is an unindexed scan in the latency-critical path, and it surfaces raw article headline fragments as suggestions. 

**LOW D18–D24 — Dead code, stale references and missing scaffolding D18.** Thirteen of twenty files in <mark>backend/</mark> are one-off scripts from a past Neon storage emergency: <mark>clean</mark> _ <mark>neon</mark> _ <mark>db , phase</mark> _ <mark>b1</mark> _ <mark>cleanup , dump</mark> _ <mark>and</mark> _ <mark>clean</mark> , <mark>dump</mark> _ <mark>all</mark> _ <mark>and</mark> _ <mark>clean , drop</mark> _ <mark>old</mark> _ <mark>suggestion , db</mark> _ <mark>space</mark> _ <mark>check</mark> , <mark>db</mark> _ <mark>final</mark> _ <mark>check , inspect</mark> _ <mark>suggestions</mark> , <mark>reindex</mark> _ <mark>suggestions , clean</mark> _ <mark>suggestions</mark> , <mark>activate</mark> _ <mark>curated , migrate</mark> _ <mark>neon</mark> _ <mark>data</mark> , <mark>init</mark> _ <mark>db</mark> . They are the majority of the backend by file count and several drop tables destructively. **D19.** Two crawlers coexist: <mark>backend/crawler.py</mark> (149 lines, raw <mark>HTMLParser )</mark> is superseded by <mark>crawler/content</mark> _ <mark>crawler.py</mark> but remains in the tree. **D20.** <mark>backend/app/models/</mark> is entirely dead — ORM models for <mark>transliteration</mark> _ <mark>map</mark> and <mark>autosuggestions ,</mark> tables that <mark>phase</mark> _ <mark>b1</mark> _ <mark>cleanup.py</mark> itself dropped. **D21.** <mark>backend/app/models/search.py:7</mark> hardcodes a placeholder <mark>DATABASE</mark> _ <mark>URL .</mark> **D22.** The readme documents <mark>src/ , package.json</mark> and <mark>vite.config.ts</mark> as present-but-legacy; none exist. **D23.** Test coverage is one 10-line file, <mark>crawler/test</mark> _ <mark>suggestions.py</mark> . There is no CI, no lint configuration and no <mark>.env.example .</mark> **D24.** <mark>public/css/khujo.css:99</mark> ends the font stack at <mark>sans-serif</mark> with no Bengali fallback; if Hind Siliguri fails to load, Android rendering is at the mercy of the system default. 

## **6. Data reality check** 

<mark>location</mark> _ <mark>pipeline</mark> _ <mark>plan.md</mark> opens with an "Honest Audit — Sep 19, 2026" asserting 5,106 administrative records already in place. The repository contains a single geographic data file, <mark>crawler/data/bd</mark> _ <mark>admin</mark> _ <mark>hierarchy.json</mark> (282 lines). 

|**LEVEL**|**PLAN CLAIMS**|**IN REPOSITORY**|**COVERAGE**|**NOTES**|
|---|---|---|---|---|
|Divisions|8|8|100%|Complete, with coordinates|
|Districts|64|**14**|22%|All 14 have coordinates|
|Upazilas|494|**37**|7%|All 37 have coordinates|
|Unions|4,540|Nested, sparse|<1%|Present only under the 37 upazilas|
|Villages / Mouzas|0 (acknowledged)|0|—|Correctly deferred|



The plan's coordinate problem is therefore inverted: it reports coordinates as the gap and hierarchy as solved, whereas in the repository the small amount of data present is fully coordinated and it is the _hierarchy_ that is 78% missing. The corrective work is smaller than the plan implies — the full 8/64/495 administrative list is a published, stable, freely available dataset — but it has not been done. 

One recommendation carried from the prior discussion stands reinforced: the 164,000 village, mouza and mahalla records should be cut from the current horizon entirely. There is no query demand to justify them, and the structural defects in section 4 mean they would be unfindable even once loaded. 

## **7. Consolidated severity summary** 

|**SEVERITY**|**COUNT**|**DEFECTS**|
|---|---|---|
|**CRITICAL**|5|D1 open admin API · D2 autocomplete poisoning · D3 arbitrary entity resolution · D4 unindexable predicate · D5 Bangla<br>inflection failure|
|**HIGH**|5|D6 no real ranking · D7 card never rendered · D8 decorative graph · D9 CORS · D10 quadratic NER|
|**MEDIUM**|7|D11 error disclosure · D12 writes on GET · D13 static perspectives · D14 broken requirements · D15 uncrawlable seeds · D16<br>retention contradiction · D17 title mining|
|**LOW**|7|D18–D24 dead code, stale docs, missing scaffolding|



Two of the five criticals (D1, D2) are security and data-integrity defects in running code, independent of any feature work. They should be fixed this week regardless of what is decided about everything else in this report. 

## **8. What this means for the 90-day plan** 

### **8.1 The favourable reading** 

Because the Phase 1 and Phase 2 artefacts were never built, no design decisions are locked in. The knowledge-layer migration can be written once, correctly, as a single coherent unit containing the dictionary, entity attributes, boosts, suppression and the inverted index together — rather than as the four separate phases the plan sequences them into. That is a materially better outcome than having to retrofit an index onto tables already in production. 

### **8.2 The unfavourable reading** 

The plan's central assertion — _"the architecture is ready, it just needs data"_ — is false. Seeding 5,000 dictionary entries into a table that does not exist, to be consumed by a query that cannot use an index and cannot match inflected Bangla, produces no observable improvement. Data volume is not the binding constraint. Retrieval quality is. Every count-based success criterion in the plan can be met while search quality stays flat. 

### **8.3 Revised sequence** 

|**STEP**|**WORK**|**RATIONALE**|
|---|---|---|
|**0**|Repository hygiene — archive the 13 cleanup scripts, delete<br>backend/crawler.py and<br>backend/app/models/,fix<br>requirements.txt,add<br>.env.example ,<br>AGENTS.md,<br>pytest|Half a day. Clears D14, D18–D23 and makes every later step legible.|
|**1**|Authentication on<br>/admin;suggestion state gate; CORS; error<br>masking|Clears D1, D2, D9, D11. Live defects, not features.|
|**2**|Golden query set (200 queries) and offline evaluation harness|Defines "finished". Without it no later step can be judged. Expect a poor first score; that is the<br>baseline.|
|**3**|0003_knowledge_layer.sql — dictionary, entity attributes,<br>boosts, suppression, revisions_and_the postings and term-statistics|Replaces the fictional Phase 1. Designed once against known requirements.|



||tables, in one migration||
|---|---|---|
|**4**|Query understanding module — normalisation, Bangla suffix<br>stripping, transliteration, dictionary expansion, intent<br>classification|Clears D5. Elevated in priority: this is the defect the plan does not know it has.|
|**5**|Indexer and BM25 ranking, replacing the predicate and scoring<br>block entirely|Clears D4, D6. Confirmed as a rewrite, not a modification.|
|**6**|Dictionary generation by reverse transliteration over existing<br>entity names|Produces tens of thousands of rows mechanically instead of by manual entry.|
|**7**|Geography: complete 64 districts and 495 upazilas, then<br>enrichment|Starting point is 14 districts, not 64.|
|**8+**|Wikidata verticals, points of interest, typed result cards, frontend<br>rendering, admin console, operations|Unchanged in substance. Step 8's frontend work clears D7 and D8.|



### **8.4 Items to cut from the current horizon** 

Villages, mouzas and mahallas (~164,000 records); the BBS geocode acquisition; AI summarisation; voice summaries; conversational Bangla AI; the content-marketing blog. None of these affect whether search works, and all of them are downstream of a retrieval layer that does not yet exist. 

## **9. Closing assessment** 

The gap between the planning documents and the repository is the most consequential finding here, and it is worth naming plainly: decisions have been made, resources committed and a 90-day window opened on the basis of a status report that does not describe the codebase. Whether that arose from uncommitted local work or from documents written ahead of implementation, the corrective action is the same — verify status against the repository, not against the last document, before each phase gate. 

Set against that, the underlying engineering judgement visible in the schema is better than the execution record suggests. The partitioning strategy, the evidence-bearing assertion model, the crawl lease state machine and the partial-unique-index correction in <mark>0002</mark> are all decisions that a competent database engineer would defend. The project is not short of design capability. It is short of the two or three specific pieces of retrieval machinery — a normaliser that understands Bangla morphology, an inverted index, and a scoring function — that turn a well-modelled corpus into a search engine. 

Those pieces are perhaps three weeks of focused work. The data-gathering programme that currently occupies the plan is worth beginning only after them. 

Audit conducted by static analysis of the complete source tree. No code was executed and no database was reachable, so runtime row counts, live query plans and measured latencies could not be verified independently; findings concerning performance are derived from query structure and index definitions rather than from measurement. 

