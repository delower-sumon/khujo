# KhujoBot v1 — Crawl Tracker & Pipeline Status
**Last Updated:** July 2026

This document tracks exactly what has been seeded, crawled, and indexed into the database, alongside our pipeline goals for the independent crawling stage.

---

## 1. What We Have Crawled & Indexed (Current DB State)

### Phase 0: Seeding (Completed ✅)
We have successfully seeded the foundational Knowledge Graph without needing an active crawler. This ensures our core logic has a "ground truth" to map against.
- **Geographic Data:** 8 Divisions, 64 Districts, 495 Upazilas, and 4,554 Unions.
- **Core Entities:** 253 primary entities, 224 specific places, and 373 localized names.
- **Platform Aliases:** 13 major Base Platforms (e.g., Prothom Alo, Google, Facebook) with full English/Bangla/Banglish transliterated aliases.
- **Initial Politicians:** 300+ Members of Parliament seeded as `person` entities from `parliament.gov.bd`.

### Phase 1 & 2: Base Scouting & HTML Spiders (Completed ✅)
- **Base Domains Scouted:** `prothomalo.com`, `thedailystar.net`, `dhakatribune.com`, `bonikbarta.com`, `kalerkantho.com`, `jugantor.com`.
- **Extraction Capabilities:** The spider perfectly extracts UTF-8 Bengali text, cleans out ads/footers/navbars, and strips `<figure>` tags.
- **Entity Tagging:** The crawler automatically scans every article for mentions of our Phase 0 entities and generates candidate links.

---

## 2. What's in the Pipeline (Next Steps)

### Phase 3: Entity Crawling (Current Focus 🚧)
We need to actively crawl web pages that contain *structured data* about people, places, and things to expand our Knowledge Graph beyond Phase 0.
- **Target:** Bengali Wikipedia (`bn.wikipedia.org`) via its API or HTML.
- **Target:** Biographies of famous Bangladeshi actors, writers, and musicians.
- **Target:** Local businesses and specific POIs (Points of Interest).

### Phase 4: Dynamic Platform Polling (Future VPS)
- **Target:** YouTube Data API (for trending Bangladeshi videos).
- **Target:** Facebook Graph API (for verified public pages and news feeds).

---

## 3. How Far Are We From the "Independent Crawling Stage"?

**Status: 80% Ready for Independence.**

Currently, KhujoBot v1 is fully capable of deep recursive crawling. It respects `robots.txt`, avoids rate-limit bans (2-second delay), automatically discovers new internal links, and dumps clean data into the Neon DB. 

**What is missing before we can just let it run on autopilot?**
1. **The Entity Crawler:** Before we unleash the bot, we need to build the Phase 3 Entity Crawler so it can harvest new Entities, not just News Articles. 
2. **VPS / Cloud Deployment:** We need to move `content_crawler.py` and our new `entity_crawler.py` onto a 24/7 VPS (or schedule them via GitHub Actions) so they run without tying up your local machine.

**Conclusion:** Once we build the Phase 3 Entity scraper, we can package the entire fleet, deploy it to a server, and officially declare the crawling stage "Independent".
