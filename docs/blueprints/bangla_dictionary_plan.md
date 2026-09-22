# Khujo — Bangla Lexicon & Transliteration Master Plan

---
## 🔴 Post-Run Audit: What Went Wrong & How to Fix It

### Root Cause Analysis

| Issue | Root Cause |
|---|---|
| `pos` = 100% null | Wiktionary HTML structure uses `<h4>` section headings, not `<span class='mw-headline'>` inside `<h3>`. Parser missed all of them. |
| `bn_antonyms` = 100% null | Wiktionary Bangla antonym sections use `{{বিপরীত শব্দ}}` templates rendered into `<div class='NavContent'>`, not a plain `<ul>`. Parser blind to this. |
| `bn_definition` = 78.59% null | Two causes: (a) HTML scraping is fragile — Wiktionary's markup varies per word. (b) Many words don't exist on bn.wiktionary at all. **Solution: Switch from HTML scraping to Wiktionary Action API.** |
| 5,834 full-row duplicates | Source JSON is English-anchored. Multiple English words map to the same Bangla word (e.g., `carry` + `carriage` both → `বহন`). The script ran each JSON entry independently, creating duplicates. |
| 1,961 English words in `bn_word` | ~12% of source entries have no Bangla translation — the English word is used as the fallback `bn` field. These must be filtered out. |
| Punctuation artifacts | Hyphens, colons and dots from English phrases leaked directly into Bengali word fields during extraction. |

### Fix Strategy

```
Step 1: Clean CSV (offline, no network)         → crawler/lexicon/clean_lexicon.py
Step 2: Re-fetch with Wiktionary API (not HTML) → crawler/lexicon/seed_lexicon_v2.py  
Step 3: Human spot-check cleaned CSV            → crawler/data/lexicon_clean.csv
Step 4: DB commit (upsert, dedup-safe)          → seed_lexicon_v2.py --commit
```

---

## ✅ Phase A-Fix: CSV Remediation (clean_lexicon.py)

**Operations the cleaner will perform:**
1. Filter out rows where `bn_word` is not in Bengali Unicode range (`\u0980-\u09FF`). Removes ~1,961 English-only entries.
2. Deduplicate on `bn_word` — keep the row with the most data (most non-null fields wins). Merges ~5,834 exact dupes + ~9,913 near-dupes intelligently: where one row has a `bn_definition` and the other doesn't, the merged row gets the definition.
3. Normalize punctuation: strip leading/trailing whitespace, collapse hyphen-space patterns (`- ` → `-`), remove trailing colons from `en_word`.
4. Drop rows where `bn_word` == `normalised_bn` difference is a punctuation strip only (cosmetic).
5. Output to `crawler/data/lexicon_clean.csv`.

**Expected result after cleaning:**
- ~11,000 to 13,000 unique, clean Bengali words
- 0 English words in `bn_word`
- 0 exact duplicates
- `bn_definition` coverage: ~34% (from Wiktionary — same data, just for valid Bengali words)

---

## ✅ Phase A-Fix: Wiktionary API Parser (seed_lexicon_v2.py)

**Switch from HTML scraping to MediaWiki Action API:**

```
OLD: GET https://bn.wiktionary.org/wiki/{word}  →  parse HTML  →  fragile
NEW: GET https://bn.wiktionary.org/w/api.php?action=parse&page={word}&prop=wikitext&format=json
     → parse wikitext directly → reliable
```

**Why wikitext is better than HTML:**
- POS sections are explicit: `==বিশেষ্য==`, `==ক্রিয়া==`, etc.
- Antonyms are in `{{বিপরীত শব্দ|word1|word2}}` templates — trivially regex-parseable.
- Definitions are in numbered `#` lines directly — no CSS class guessing.
- Handles 301 redirects automatically.

**Wikitext parsing logic:**
```python
import re, httpx

def parse_wikitext(text: str) -> dict:
    pos_map = {'বিশেষ্য': 'noun', 'ক্রিয়া': 'verb', 'বিশেষণ': 'adjective', 'অব্যয়': 'adverb'}
    pos = next((v for k, v in pos_map.items() if f'=={k}==' in text), '')
    # Extract first definition line (starts with # but not ##)
    definition = next((l[1:].strip() for l in text.splitlines() if l.startswith('#') and not l.startswith('##')), '')
    # Extract antonyms from template
    antonyms = re.findall(r'{{বিপরীত শব্দ\|([^}]+)}}', text)
    antonyms = [a for group in antonyms for a in group.split('|')]
    return {'pos': pos, 'bn_definition': definition, 'bn_antonyms': antonyms}
```

**Expected improvement vs v1:**
- `pos` coverage: 0% → ~40% (many words not in Wiktionary)
- `bn_definition` coverage: 21% → ~40%
- `bn_antonyms` coverage: 0% → ~15%

---

## 🔵 Future-Proof Architecture: Quality-First 100k Word Pipeline

### The Fundamental Shift: Bengali-Anchored, Not English-Anchored

The MinhasKamal source is English-to-Bengali. For a Bangla search engine, we must flip this: our dictionary must be Bengali-word-first, with English as an optional cross-reference.

```
Source Priority (Quality Tier)
──────────────────────────────────────────────────────────────
Tier 1 (Highest Quality): Wiktionary API parsed wikitext
  - Clean POS, definition, antonyms
  - Source tag: 'wiktionary'

Tier 2: MinhasKamal JSON (filtered + deduplicated)
  - Synonyms, pronunciation, usage sentences  
  - Source tag: 'minhaskamal'

Tier 3: Bangla Wikipedia word lists (categories)
  - Proper nouns, places, persons
  - Source tag: 'wikipedia_bn'

Tier 4: mBART transliterations (Phase B)
  - Banglish phonetic variants
  - Source tag: 'mbart'

Tier 5: Manual / crowd corrections (admin panel)
  - Source tag: 'manual'
```

### Scale-Up Execution Plan (GitHub Actions / Colab)

```
Month 1 (Current):  ~13k clean words from MinhasKamal + Wiktionary API
Month 2:            +20k words from Wiktionary bn.wiktionary category crawl
Month 3:            +30k words from Bangla Wikipedia article word extraction
Month 4+:           +40k words from corpus mining of crawled news articles
Total Target:       ~100k unique Bengali words
```

**GitHub Actions Cron Job:**
```yaml
name: Lexicon Enrichment
on:
  schedule:
    - cron: '0 2 * * 0'  # Every Sunday at 2am
jobs:
  enrich:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install httpx beautifulsoup4 psycopg2-binary
      - run: python crawler/lexicon/seed_lexicon_v2.py --enrich-missing 500
        env:
          DATABASE_URL: ${{ secrets.NEON_DATABASE_URL }}
```

**Quality Gates (enforced before any DB commit):**
- `bn_word` MUST be in Bengali Unicode range (reject English fallbacks)
- No duplicate `bn_word` (upsert merges, never blindly inserts)
- `bn_definition` must be < 1000 chars and > 10 chars if present
- `pos` must be one of: noun, verb, adjective, adverb, pronoun, conjunction, interjection, or null

---

## Revised Execution Sequence

- `[x]` Schema created: `backend/sql/0005_bangla_lexicon.sql`
- `[x]` Initial parser run: `crawler/lexicon/seed_lexicon.py --preview` (16,912 words, Wiktionary v1)
- `[x]` Data audit completed (audit findings documented above)
- `[ ]` **Step 1**: Write `crawler/lexicon/clean_lexicon.py` — dedup + filter + normalize the existing CSV
- `[ ]` **Step 2**: Write `crawler/lexicon/seed_lexicon_v2.py` — Wiktionary Action API + wikitext parser
- `[ ]` **Step 3**: Run `clean_lexicon.py` → review `lexicon_clean.csv` (human spot-check ~20 rows)
- `[ ]` **Step 4**: Run `seed_lexicon_v2.py --preview` → re-enrich clean words with API data
- `[ ]` **Step 5**: Run `seed_lexicon_v2.py --commit` → upsert to `core.bangla_lexicon`
- `[ ]` **Step 6**: Add dictionary card detection to `backend/main.py` SERP
- `[ ]` **Step 7 (GitHub Actions)**: Weekly enrichment cron for `--enrich-missing` words
- `[ ]` **Step 8 (Phase B)**: mBART transliterations via Colab endpoint

---


## Data Reality Check

### What BengaliDictionary.json actually contains (16,912 entries)

```json
{
  "pron": ["ˈkarēər", "Bāhaka"],     // [IPA, Romanized Bangla]
  "bn": "বাহক",                       // Bangla word
  "en": "carrier",                    // English word (the KEY)
  "bn_syns": ["বহনকারী", "বাহক"],    // Bangla synonyms ✅
  "en_syns": ["bearer", "conveyor"],  // English synonyms
  "sents": ["Example sentence..."]   // Usage sentences (English)
}
```

**Critical gaps identified:**

| Field | Status |
|---|---|
| Bangla word (`bn`) | ✅ Present |
| English translation (`en`) | ✅ Present |
| Bangla synonyms (`bn_syns`) | ✅ Present (often) |
| Romanized phonetic (`pron[1]`) | ✅ Present (raw, inconsistent) |
| IPA pronunciation (`pron[0]`) | ✅ Present |
| **Bangla definition (বাংলা অর্থ)** | ❌ Missing |
| **Part of Speech (POS)** | ❌ Missing |
| **Antonyms (বিপরীত শব্দ)** | ❌ Missing |
| **Banglish transliteration** | ❌ Missing (to be added Phase B) |

---

## Schema: `core.bangla_lexicon` (New migration: `0005_bangla_lexicon.sql`)

```sql
CREATE TABLE core.bangla_lexicon (
    word_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Core word identity
    bn_word        TEXT NOT NULL,                        -- বাহক (Bangla script)
    en_word        TEXT,                                 -- carrier (English anchor)
    normalised_bn  TEXT NOT NULL,                        -- lowercase, stripped diacritics

    -- Linguistic properties
    pos            TEXT,                                 -- noun/verb/adj/adv etc (filled by enrichment)
    ipa_pron       TEXT,                                 -- ˈkarēər (from pron[0])
    roman_pron     TEXT,                                 -- Bāhaka (from pron[1], raw)

    -- Definitions
    bn_definition  TEXT,                                 -- Bangla-language definition (from Wiktionary)
    en_definition  TEXT,                                 -- English-language definition (optional)

    -- Synonym/Antonym arrays
    bn_synonyms    TEXT[] DEFAULT '{}',                  -- Bangla synonyms array
    en_synonyms    TEXT[] DEFAULT '{}',                  -- English synonyms array
    bn_antonyms    TEXT[] DEFAULT '{}',                  -- Bangla antonyms (enrichment)

    -- Transliterations (Phase B — mBART + rule-based)
    transliterations TEXT[] DEFAULT '{}',               -- ['bahak', 'bahoka', 'bahok']

    -- Example sentences
    usage_sentences TEXT[] DEFAULT '{}',               -- from sents[]

    -- Lifecycle & quality
    source         TEXT NOT NULL DEFAULT 'minhaskamal', -- data lineage tag
    enrichment_state TEXT NOT NULL DEFAULT 'raw'        -- raw → wiktionary_fetched → transliterated → verified
        CHECK (enrichment_state IN ('raw', 'wiktionary_fetched', 'transliterated', 'verified')),
    has_bn_definition BOOLEAN GENERATED ALWAYS AS (bn_definition IS NOT NULL) STORED,

    -- Dedup guard
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (bn_word)  -- primary dedup key on Bangla word
);

-- Indexes
CREATE INDEX bangla_lexicon_bn_word_trgm   ON core.bangla_lexicon USING gin (bn_word gin_trgm_ops);
CREATE INDEX bangla_lexicon_norm_idx       ON core.bangla_lexicon (normalised_bn);
CREATE INDEX bangla_lexicon_enrichment_idx ON core.bangla_lexicon (enrichment_state);
CREATE INDEX bangla_lexicon_en_word_idx    ON core.bangla_lexicon (en_word);
```

> **UNIQUE on `bn_word`**: All future additions (100k total) run `INSERT ... ON CONFLICT (bn_word) DO UPDATE` so duplicates are safely caught at the database level. No word can ever be double-inserted.

---

## Data Flow Architecture (Industry Grade)

```
Step 1: Parse                Step 2: Human Review        Step 3: DB Insert
─────────────────────────────────────────────────────────────────────────
BengaliDictionary.json
        │
        ▼
seed_lexicon.py          →  crawler/data/
   (parser +                lexicon_preview.csv       →  python seed_lexicon.py --commit
  Wiktionary fetch)         (human reads this              (inserts to core.bangla_lexicon
                             before any insert)             via upsert on bn_word)
```

### Phase A: Ingest + Wiktionary Enrich (Immediate)

**Script: `crawler/seed_lexicon.py`**

Flow per word:
1. Parse `BengaliDictionary.json` (16,912 entries, utf-8-sig).
2. For each entry, extract: `bn`, `en`, `pron[0]` (IPA), `pron[1]` (roman), `bn_syns`, `en_syns`, `sents`.
3. Normalize `bn_word`: strip leading/trailing whitespace, Unicode normalize (NFC).
4. **Wiktionary HTTP fetch**: `https://bn.wiktionary.org/wiki/{bn_word}` (async `httpx`, rate-limited to 3 req/s to avoid ban).
5. Parse Wiktionary HTML with BeautifulSoup: extract definition (`#mw-content-text > dl, dd`), POS heading (`==বিশেষ্য==`, `==ক্রিয়া==` etc), antonyms.
6. Build a structured record dict per word.
7. **Write to `crawler/data/lexicon_preview.csv`** — NOT to DB yet.
8. Operator opens the CSV, does a spot check, then runs `--commit` flag.

**Invocation:**
```bash
# Step A: Parse + fetch Wiktionary, write preview CSV
python crawler/seed_lexicon.py --input crawler/data/BengaliDictionary.json --preview

# Step B: Human opens crawler/data/lexicon_preview.csv and spot checks

# Step C: Commit to DB (with upsert, no duplicates)
python crawler/seed_lexicon.py --input crawler/data/BengaliDictionary.json --commit
```

### Phase B: Transliteration Enrichment Worker (Later)

**Script: `crawler/worker_04_transliterate.py`**

Flow:
1. Query `SELECT word_id, bn_word FROM core.bangla_lexicon WHERE transliterations = '{}' LIMIT 500`.
2. For common/short words: Apply rule-based Avro phonetic mapping (deterministic, offline, instant).
3. For complex/colloquial words: Send batches to the mBART model via a Google Colab API endpoint.
4. `UPDATE core.bangla_lexicon SET transliterations = ARRAY[...], enrichment_state = 'transliterated' WHERE word_id = ...`.

---

## Duplicate Management Strategy

| Scenario | How Handled |
|---|---|
| Same Bangla word from BengaliDictionary.json | `UNIQUE(bn_word)` prevents insert |
| Same Bangla word from Wiktionary new words | `ON CONFLICT (bn_word) DO UPDATE` merges |
| Same Bangla word from 100k extended sources | Same upsert — enrichment fields updated, not overwritten |
| Word with different spellings (বানান ভেদ) | Treated as separate entries; linked via `bn_synonyms[]` |

---

## SERP Integration: Single-Word Dictionary Card

When the search API detects `len(words) == 1 AND match in core.bangla_lexicon`:

```json
{
  "dictionary_card": {
    "word": "বাহক",
    "pos": "বিশেষ্য",
    "ipa": "ˈkarēər",
    "bn_definition": "যে বা যা কোনো কিছু বহন করে",
    "synonyms": ["বহনকারী", "সংবাহক", "বরদার"],
    "antonyms": [],
    "transliterations": ["bahak", "bahoka"]
  }
}
```

---

## Execution Sequence

- `[ ]` **Step 1**: Write `backend/sql/0005_bangla_lexicon.sql` migration
- `[ ]` **Step 2**: Build `crawler/seed_lexicon.py` (parser + Wiktionary async fetch + preview CSV output)
- `[ ]` **Step 3**: You review `crawler/data/lexicon_preview.csv` (spot check ~50 rows)
- `[ ]` **Step 4**: Run `--commit` to insert ~16,912 words into Neon
- `[ ]` **Step 5**: Add single-word dictionary card detection to `backend/main.py` search API
- `[ ]` **Step 6 (Later)**: Build `crawler/worker_04_transliterate.py` for Banglish transliterations
- `[ ]` **Step 7 (Later)**: Scale up to 100k words via additional sources (Wiktionary categories, BN Wikipedia word lists)

---

## Audit of Your Approach

| Your Proposal | Assessment |
|---|---|
| Ingest JSON + query Wiktionary together in one pass | ✅ Correct. Doing it in two passes wastes network round trips |
| Preview CSV before DB insert (HITL gate) | ✅ Industry standard. Prevents garbage from entering the production DB |
| Transliterations added later in separate pass | ✅ Right call. mBART is async/heavy, don't block lexicon insertion on it |
| SQL field for transliterations from the start | ✅ Future-proof schema design |
| Separate enrichment worker for 100k scale-up | ✅ Correct architecture — batch queue with resume capability |
| Duplicate check strategy | ✅ Database-level UNIQUE is the right guard (not application-level) |
| Wiktionary rate limiting | ⚠️ Need to add: 3 req/s max, retry with exponential backoff, cache HTML locally |
| SERP single-word dictionary card | ✅ Critical UX feature — detects single-word queries and surfaces it |
