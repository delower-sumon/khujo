# Khujo Master Plan: Node/React to Vanilla JS & DB Core Migration

This master plan tracks the fundamental architectural shift of the Khujo search engine from a heavy React/Node.js stack to a lightning-fast Vanilla JS and Python FastAPI stack, backed by a robust PostgreSQL (Neon) database.

---

## 1. Architecture Transition
- [x] **Frontend Migration**: Replaced the heavy React setup with a lightning-fast, zero-build Vanilla JS frontend.
- [x] **Backend Migration**: Replaced the Node.js backend with a lean Python FastAPI backend.
- [x] **Database Schema**: Established a robust PostgreSQL (Neon) core schema with `content.document`, `core.entity`, and `search.suggestion` tables.

## 2. Core Search Engine implementation
- [x] **Scoring Algorithm**: Implemented a Multi-Signal Scoring Engine utilizing:
  - Domain Match (+100)
  - Title Match (+80)
  - Trigram Similarity (+20)
  - Homepage Boost (+15)
- [x] **Knowledge Graph Integration**: Added entity resolution directly into the search pipeline to trigger sidebar Knowledge Graph cards for people, places, and organizations.

## 3. UI and Autosuggestions
- [x] **Self-Learning Suggestions**: Built a self-learning autosuggestion system that tracks user queries and extracts short, clean suggestions from verified document titles.
- [x] **Dropdown Alignment**: Recreated the seamless Google-style dropdown UI using sub-pixel perfect native CSS positioning (removing buggy Javascript coordinate calculations).
- [x] **Aesthetics**: Polished the UI with vibrant Dark Mode support, responsive design, and smooth transitions.
- [x] **Brand Cleanup**: Removed stray taglines ("স্থানীয় জ্ঞানের খোঁজ", "বাংলার খোঁজ") from the search interface to keep it minimal and clean.

## 4. Admin Curation Vault
- [x] **Verification Dashboard**: Created `admin.html` for reviewing and approving candidate documents before they are permitted to hit the live SERP.
- [x] **Entity Promotion**: Built logic so that when an admin approves a document, its associated Entity Mentions are promoted to the live Knowledge Graph.

## 5. Upcoming Major Epics
- [ ] **KhujoBot Crawler Maturation**: Evolve the crawler to scrape entities directly (people, businesses, sports). *(See khujobot_v1_plan.md for details)*
- [ ] **Native Bangla Stemming (Post-VPS)**: Integrate a custom Bengali stemming dictionary into PostgreSQL or transition the ranking core to Semantic Vector Embeddings (AI-based search) to achieve true grammatical understanding (e.g., treating "বাংলাদেশের" and "বাংলাদেশে" as the root "বাংলাদেশ").
- [ ] **SERP Enhancements**: Add image results and rich snippets.
- [ ] **Analytics Dashboard**: Build an interface to visualize popular searches and user behavior.
