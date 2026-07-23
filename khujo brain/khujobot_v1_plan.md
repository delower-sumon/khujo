# Khujo Crawler Plan: KhujoBot v1 & Beyond

This plan tracks the development and execution of Khujo's automated web crawler, designed to build a vast repository of localized Bengali web content and Knowledge Graph entities.

---

## Phase 0: Geographic & Entity Seeder
- [x] **Geographic Seeding**: Pre-seeded Bangladesh Divisions, Districts, Upazilas, and Unions into the core database.
- [x] **Entity Seeding**: Seeded public figures and major platforms as initial entities to bootstrap the Knowledge Graph.

## Phase 1: Site Scout
- [x] **Base Homepage Scouting**: The Scout bot successfully explores base homepages of trusted publishers (Prothom Alo, Daily Star, etc.).
- [x] **Metadata & Favicons**: Extracts domain metadata, verifies `robots.txt` compliance, and automatically uploads favicons to Cloudflare R2.
- [x] **Queue Priming**: Automatically queues the root domain into the frontier queue for deep crawling.

## Phase 2: Deep Recursive Spider (Content Crawler)
- [x] **Centralized Utilities**: Created `utils/links.py` for shared URL hashing and validation across the crawler fleet.
- [x] **Encoding Fix**: Explicitly handled `utf-8` encoding for Bengali text to prevent mojibake (previously caused by `requests` defaulting to `ISO-8859-1`).
- [x] **Aggressive HTML Cleaning**: Optimized `clean_body_text()` to completely strip out garbage HTML like `<figure>`, `<figcaption>`, ads, sidebars, and empty whitespace chunks.
- [x] **Recursive Spider**: Implemented logic to extract internal `<a href>` links from parsed articles.
- [x] **Queue Expansion**: Validates discovered links against `robots.txt` and domain boundaries, then dynamically queues up to 20 new links per article into `crawl.frontier_url`.
- [x] **Polite Crawling**: Introduced a hard 2-second delay between requests to avoid overloading local publisher servers.
- [x] **Entity Tagging**: The crawler cross-references extracted text against the database to tag Knowledge Graph entities inside articles automatically.

## Phase 3: Entity Crawling (PENDING NEXT JOB)
- [ ] **Design Entity Crawler**: Draft a dedicated script (e.g., `entity_crawler.py`) or API integration (like Wikipedia API) to systematically harvest structured data.
- [ ] **People Entities**: Crawl politicians, actors, writers, and public figures.
- [ ] **Business Entities**: Crawl local Bangladeshi businesses, locations, and descriptions.
- [ ] **Cultural Entities**: Crawl sports teams, musicians, and songs to enrich the SERP Knowledge Graph cards.

## Phase 4: Automation & Scale
- [ ] **GitHub Actions**: Move the finalized crawler fleet to a scheduled GitHub Actions workflow for daily automated execution without manual intervention.
- [ ] **Distributed Workers**: Set up parallel crawling workers to handle high-throughput queue draining.
