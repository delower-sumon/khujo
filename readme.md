# Khujo — Bangladesh's Local Search Engine

Khujo (খোঁজো) is an independent, Bangladeshi-first search engine and knowledge graph engine engineered for low-latency Bangla retrieval, morphological stemming, and transparent entity graph discovery.

---

## Architecture Overview

- **Frontend (`public/`)**: High-performance static web application built with Vanilla HTML5, CSS3, and modern JavaScript. Includes Avro phonetic transliteration, Google-style inline & sidebar Knowledge Graph cards, and dynamic perspectives.
- **Backend (`backend/`)**: FastAPI REST service with PostgreSQL (`pg_trgm`, GIN indexes), rule-based Bangla morphological stemming (`backend/app/nlp/bangla_stemmer.py`), tiered entity resolution, and asynchronous search telemetry.
- **Crawler & Pipelines (`crawler/`)**: Multi-stage crawler architecture with polite rate limiting, geo hierarchy harvesting (5,100+ administrative locations), entity extraction, and retention enforcement.
- **Test Harness (`tests/`)**: Automated test suite with security assertions, morphological stemmer tests, golden queries benchmark (`tests/golden_queries.json`), and MRR/P@K evaluation harness (`tests/eval_harness.py`).

---

## Local Development Setup

### 1. Backend Service
```powershell
# Activate Python virtual environment
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Start FastAPI API service (runs on http://localhost:8000)
python backend/main.py
```

### 2. Frontend Development Server
```powershell
# Serve static assets from public/ directory
python -m http.server 8080 --directory public
```
Access the application in your browser at: **http://localhost:8080**

### 3. Running Automated Tests
```powershell
python -m unittest discover tests
```

---

## Repository Structure

```
├── backend/
│   ├── main.py                  # FastAPI REST endpoints & search engine
│   ├── app/
│   │   ├── database.py          # SQLAlchemy NullPool database connection
│   │   └── nlp/
│   │       └── bangla_stemmer.py # Rule-based Bangla morphological stemmer
│   ├── archive/                 # Archived legacy scripts & ORM models
│   ├── ner_script.py            # Optimized entity assertion pipeline
│   ├── r2_media.py              # Cloudflare R2 media vault storage
│   └── sql/                     # PostgreSQL core schemas & migrations
├── crawler/
│   ├── content_crawler.py       # Web content recursive spider
│   ├── entity_crawler.py        # Wikipedia Bengali entity crawler
│   ├── geo_crawler.py           # Administrative geo location crawler
│   ├── seed_sources.py          # Verified Bangladeshi seed targets
│   ├── utils/
│   │   ├── db.py                # Crawler database factory
│   │   ├── r2.py                # Favicon & asset upload helpers
│   │   └── retention.py         # Expired records & query event purger
│   └── worker_01_fetch.py       # Pipeline fetch worker
├── public/
│   ├── index.html               # Home landing page with Avro input
│   ├── search.html              # Search engine results page (SERP)
│   ├── admin.html               # Editorial review dashboard
│   ├── entities.html            # Knowledge entity editor
│   ├── css/khujo.css            # Stylesheets with Bangla font fallbacks
│   └── js/khujo.js              # Vanilla JS SERP & interactive SVG graph
├── docs/                        # Architecture documentation & audit plans
└── tests/                       # Unit tests & evaluation benchmark
```

---

## Security & Admin Gate

Administrative API endpoints require authentication via the `X-Admin-Key` HTTP header.
Candidate web pages and entity assertions are held in candidate state until verified through the admin dashboard at `http://localhost:8080/admin.html`.
