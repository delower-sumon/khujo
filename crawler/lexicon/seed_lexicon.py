import argparse
import asyncio
import csv
import json
import logging
import os
import re
from pathlib import Path
from urllib.parse import quote
from typing import Dict, Any, List

import httpx
from bs4 import BeautifulSoup
import psycopg2
from psycopg2.extras import execute_values

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("seed_lexicon")

# Constants
CACHE_DIR = Path(__file__).parent.parent / "data" / "wiktionary_cache"
PREVIEW_CSV = Path(__file__).parent.parent / "data" / "lexicon_preview.csv"
DB_URL = os.getenv("DATABASE_URL", "postgresql://khujobot:dummy@localhost/khujo")

# Ensure cache directory exists
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Normalization helper
def normalize_bn(text: str) -> str:
    if not text:
        return ""
    text = text.strip()
    # Basic normalization (remove punctuation, lowercasing won't affect BN but good for mixed)
    text = re.sub(r'[^\w\s\u0980-\u09FF]', '', text)
    return text

async def fetch_wiktionary(client: httpx.AsyncClient, word: str) -> str:
    """Fetch from Wiktionary with caching."""
    cache_path = CACHE_DIR / f"{word}.html"
    if cache_path.exists():
        return cache_path.read_text(encoding="utf-8")

    url = f"https://bn.wiktionary.org/wiki/{quote(word)}"
    try:
        resp = await client.get(url, timeout=10.0)
        if resp.status_code == 200:
            html = resp.text
            cache_path.write_text(html, encoding="utf-8")
            return html
        elif resp.status_code == 404:
            # Cache 404s as empty to avoid refetching
            cache_path.write_text("", encoding="utf-8")
            return ""
    except Exception as e:
        log.warning(f"Error fetching {word}: {e}")
    return ""

def parse_wiktionary(html: str) -> Dict[str, Any]:
    """Parse Wiktionary HTML for definitions and POS."""
    if not html:
        return {"pos": "", "bn_definition": "", "bn_antonyms": []}
    
    soup = BeautifulSoup(html, "html.parser")
    
    # Try to find POS (typically in a span with mw-headline inside an h3 or h4)
    pos = ""
    for tag in ["h3", "h4"]:
        for header in soup.find_all(tag):
            headline = header.find("span", class_="mw-headline")
            if headline and headline.text in ["বিশেষ্য", "বিশেষণ", "ক্রিয়া", "অব্যয়", "সর্বনাম"]:
                pos = headline.text
                break
        if pos: break

    # Try to find definition (typically first <dd> or <ol><li> after POS)
    definition = ""
    # Look for lists 
    ol = soup.find("ol")
    if ol:
        li = ol.find("li")
        if li:
            definition = li.text.strip()
    
    if not definition:
        # Fallback to definition lists
        dl = soup.find("dl")
        if dl:
            dd = dl.find("dd")
            if dd:
                definition = dd.text.strip()

    # Clean up definition (remove citation tags like [1])
    definition = re.sub(r'\[\d+\]', '', definition).strip()

    # Try to find antonyms
    antonyms = []
    anto_header = soup.find(lambda tag: tag.name in ["h3", "h4"] and "বিপরীত শব্দ" in tag.text)
    if anto_header:
        # Look for the next ul/ol
        next_sib = anto_header.find_next_sibling(["ul", "ol", "p"])
        if next_sib and next_sib.name in ["ul", "ol"]:
            for li in next_sib.find_all("li"):
                antonyms.append(li.text.strip())

    return {
        "pos": pos,
        "bn_definition": definition[:1000] if definition else "", # limit length
        "bn_antonyms": antonyms[:5] # keep top 5
    }

async def process_batch(client: httpx.AsyncClient, batch: List[Dict], delay: float = 0.33):
    """Process a batch of words concurrently with a rate limit delay."""
    results = []
    for item in batch:
        # Respect rate limit (approx 3 req/s) if not cached
        cache_path = CACHE_DIR / f"{item['bn']}.html"
        if not cache_path.exists():
            await asyncio.sleep(delay)
            
        html = await fetch_wiktionary(client, item['bn'])
        wik_data = parse_wiktionary(html)
        
        results.append({
            "bn_word": item['bn'],
            "en_word": item.get('en', ''),
            "normalised_bn": normalize_bn(item['bn']),
            "pos": wik_data['pos'],
            "ipa_pron": item.get('pron', ['', ''])[0] if isinstance(item.get('pron'), list) and len(item.get('pron')) > 0 else '',
            "roman_pron": item.get('pron', ['', ''])[1] if isinstance(item.get('pron'), list) and len(item.get('pron')) > 1 else '',
            "bn_definition": wik_data['bn_definition'],
            "bn_synonyms": item.get('bn_syns', []),
            "en_synonyms": item.get('en_syns', []),
            "bn_antonyms": wik_data['bn_antonyms'],
            "usage_sentences": item.get('sents', [])
        })
    return results

async def preview_mode(input_file: str):
    """Phase A1: Parse JSON, Fetch Wiktionary, Write to CSV."""
    log.info(f"Loading dictionary from {input_file}...")
    try:
        with open(input_file, encoding='utf-8-sig') as f:
            data = json.load(f)
    except Exception as e:
        log.error(f"Failed to load JSON: {e}")
        return

    # Convert to list if dict
    items = []
    if isinstance(data, dict):
        # Handle case where it's a dict
        pass # Based on previous inspect, it's a list
    else:
        items = data

    log.info(f"Found {len(items)} entries. Starting enrichment pipeline...")
    
    fields = [
        "bn_word", "en_word", "normalised_bn", "pos", "ipa_pron", "roman_pron",
        "bn_definition", "bn_synonyms", "en_synonyms", "bn_antonyms", "usage_sentences"
    ]
    
    # Resume capability: check if CSV exists and how many lines it has
    start_idx = 0
    mode = 'w'
    if PREVIEW_CSV.exists():
        with open(PREVIEW_CSV, 'r', encoding='utf-8') as f:
            num_lines = sum(1 for line in f)
        if num_lines > 1:
            start_idx = num_lines - 1 # Subtract header
            mode = 'a'
            log.info(f"Resuming from index {start_idx}...")

    # Open CSV
    with open(PREVIEW_CSV, mode, encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        if mode == 'w':
            writer.writeheader()

        batch_size = 50
        headers = {'User-Agent': 'Khujobot/1.0 (https://khujo.com.bd; admin@khujo.com.bd)'}
        async with httpx.AsyncClient(headers=headers) as client:
            for i in range(start_idx, len(items), batch_size):
                batch = items[i:i+batch_size]
                log.info(f"Processing batch {i} to {i+len(batch)} of {len(items)}...")
                enriched_batch = await process_batch(client, batch)
                
                for row in enriched_batch:
                    # Serialize arrays to strings for CSV
                    row['bn_synonyms'] = "|".join(row['bn_synonyms'])
                    row['en_synonyms'] = "|".join(row['en_synonyms'])
                    row['bn_antonyms'] = "|".join(row['bn_antonyms'])
                    row['usage_sentences'] = "|".join(row['usage_sentences'])
                    writer.writerow(row)
                    
                f.flush() # Ensure data is written in case of crash

    log.info(f"Preview generation complete! Check {PREVIEW_CSV}")
    log.info("Run with --commit to insert into database.")

def commit_mode():
    """Phase A2: Read CSV and upsert into database."""
    if not PREVIEW_CSV.exists():
        log.error(f"Preview CSV not found at {PREVIEW_CSV}. Run --preview first.")
        return

    log.info(f"Connecting to database...")
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
    except Exception as e:
        log.error(f"DB connection failed: {e}")
        return

    records = []
    with open(PREVIEW_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            records.append((
                row['bn_word'],
                row['en_word'],
                row['normalised_bn'],
                row['pos'] if row['pos'] else None,
                row['ipa_pron'] if row['ipa_pron'] else None,
                row['roman_pron'] if row['roman_pron'] else None,
                row['bn_definition'] if row['bn_definition'] else None,
                row['bn_synonyms'].split('|') if row['bn_synonyms'] else [],
                row['en_synonyms'].split('|') if row['en_synonyms'] else [],
                row['bn_antonyms'].split('|') if row['bn_antonyms'] else [],
                row['usage_sentences'].split('|') if row['usage_sentences'] else [],
                'wiktionary_fetched' if row['bn_definition'] else 'raw'
            ))

    log.info(f"Upserting {len(records)} records into core.bangla_lexicon...")
    
    insert_query = """
        INSERT INTO core.bangla_lexicon (
            bn_word, en_word, normalised_bn, pos, ipa_pron, roman_pron,
            bn_definition, bn_synonyms, en_synonyms, bn_antonyms, usage_sentences, enrichment_state
        ) VALUES %s
        ON CONFLICT (bn_word) DO UPDATE SET
            en_word = EXCLUDED.en_word,
            pos = COALESCE(EXCLUDED.pos, core.bangla_lexicon.pos),
            bn_definition = COALESCE(EXCLUDED.bn_definition, core.bangla_lexicon.bn_definition),
            bn_synonyms = EXCLUDED.bn_synonyms,
            bn_antonyms = EXCLUDED.bn_antonyms,
            enrichment_state = EXCLUDED.enrichment_state,
            updated_at = now()
    """
    
    try:
        execute_values(cur, insert_query, records, page_size=1000)
        conn.commit()
        log.info("Database commit successful!")
    except Exception as e:
        conn.rollback()
        log.error(f"Error during commit: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed Bangla Lexicon")
    parser.add_argument("--input", type=str, default="../data/BengaliDictionary.json", help="Path to raw JSON")
    parser.add_argument("--preview", action="store_true", help="Run enrichment and output to CSV")
    parser.add_argument("--commit", action="store_true", help="Read CSV and upsert to database")
    
    args = parser.parse_args()
    
    # Adjust relative paths if running from crawler root
    input_path = Path(args.input)
    if not input_path.exists():
        input_path = Path(__file__).parent.parent / "data" / "BengaliDictionary.json"
        
    if args.preview:
        asyncio.run(preview_mode(str(input_path)))
    elif args.commit:
        commit_mode()
    else:
        parser.print_help()
