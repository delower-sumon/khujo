import os
import json
import logging
import requests
from urllib.parse import quote
from sqlalchemy import text
from bs4 import BeautifulSoup
from utils.db import get_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("entity_crawler")

KHUJO_UA = "KhujoBot/1.0 (+https://khujo.com.bd/bot)"
HEADERS = {"User-Agent": KHUJO_UA}

# High-profile, curated list of targets
TARGETS = [
    # BNP
    "খালেদা জিয়া",
    "তারেক রহমান",
    "জিয়াউর রহমান",
    "মির্জা ফখরুল ইসলাম আলমগীর",
    
    # Awami League
    "শেখ হাসিনা",
    "শেখ মুজিবুর রহমান",
    "তাজউদ্দীন আহমদ",
    "সৈয়দ আশরাফুল ইসলাম",
    
    # Historic / Icons
    "মুহাম্মদ ইউনূস",
    "মওলানা আবদুল হামিদ খান ভাসানী",
    "আবুল কাশেম ফজলুল হক",
    "হোসেন শহীদ সোহ্‌রাওয়ার্দী",
    
    # Others
    "হুসেইন মুহাম্মদ এরশাদ",
    "ওবায়দুল কাদের",
    "মির্জা আব্বাস",
    "খন্দকার মোশতাক আহমেদ",
    "ড. কামাল হোসেন",
    "আ. স. ম. আবদুর রব",
    "শাহ এ এম এস কিবরিয়া",
    "বদরুদ্দোজা চৌধুরী",
    "অলি আহমেদ",
    
    # Geography
    "ঢাকা",
    "চট্টগ্রাম",
    "বাংলাদেশ"
]

def fetch_wikipedia_data(title: str):
    """Fetch summary and image from Bengali Wikipedia API."""
    encoded_title = quote(title)
    url = f"https://bn.wikipedia.org/w/api.php?action=query&prop=extracts|pageimages&exchars=800&exintro=1&explaintext=1&titles={encoded_title}&pithumbsize=500&format=json"
    
    try:
        r = requests.get(url, headers=HEADERS)
        r.raise_for_status()
        data = r.json()
        
        pages = data.get("query", {}).get("pages", {})
        for page_id, page_data in pages.items():
            if page_id == "-1":
                log.warning(f"Wikipedia page not found for: {title}")
                return None
            
            summary = page_data.get("extract", "").strip()
            # If summary ends abruptly or needs cleaning, we can do it here.
            
            image_url = None
            if "thumbnail" in page_data:
                image_url = page_data["thumbnail"].get("source")
                
            # Secondary request to parse infobox for Quick Facts
            facts = {}
            try:
                html_url = f"https://bn.wikipedia.org/wiki/{encoded_title}"
                html_r = requests.get(html_url, headers=HEADERS)
                if html_r.status_code == 200:
                    soup = BeautifulSoup(html_r.text, 'html.parser')
                    infobox = soup.find('table', class_='infobox')
                    if infobox:
                        for tr in infobox.find_all('tr'):
                            th = tr.find('th')
                            td = tr.find('td')
                            if th and td and th.text.strip() and td.text.strip():
                                key = th.text.strip()
                                # Clean up td text (remove superscripts like [১])
                                for sup in td.find_all('sup'):
                                    sup.decompose()
                                val = td.text.strip().replace('\n', ', ')
                                if len(val) > 0 and len(val) < 100:  # Only short facts
                                    facts[key] = val
            except Exception as e:
                log.warning(f"Failed to fetch infobox facts for {title}: {e}")
                
            return {
                "title": page_data.get("title", title),
                "summary": summary,
                "image_url": image_url,
                "facts": facts,
                "wikipedia_url": f"https://bn.wikipedia.org/wiki/{encoded_title}"
            }
    except Exception as e:
        log.error(f"Error fetching data for {title}: {e}")
        return None

def insert_entity(engine, data: dict):
    """Insert candidate entity and entity_name into database."""
    with engine.begin() as conn:
        # First, ensure 'person' entity type exists
        res = conn.execute(text("SELECT entity_type_id FROM core.entity_type WHERE slug = 'person'")).first()
        if not res:
            log.error("Person entity type not found!")
            return
        
        entity_type_id = res[0]
        
        # Check if already exists (by exact name)
        res = conn.execute(text("""
            SELECT e.entity_id FROM core.entity e 
            JOIN core.entity_name en ON e.entity_id = en.entity_id 
            WHERE en.name = :name
        """), {"name": data["title"]}).first()
        
        if res:
            log.info(f"Entity already exists, updating: {data['title']}")
            entity_id = res[0]
            # Update summary and metadata
            metadata = {}
            if data["image_url"]:
                metadata["image_url"] = data["image_url"]
            if data["wikipedia_url"]:
                metadata["wikipedia_url"] = data["wikipedia_url"]
            if data.get("facts"):
                metadata["facts"] = data["facts"]
                
            conn.execute(text("""
                UPDATE core.entity SET 
                    summary = :summary,
                    metadata = :metadata
                WHERE entity_id = :entity_id
            """), {
                "summary": data["summary"],
                "metadata": json.dumps(metadata),
                "entity_id": entity_id
            })
            return
            
        # Create new entity
        log.info(f"Inserting new entity: {data['title']}")
        metadata = {}
        if data["image_url"]:
            metadata["image_url"] = data["image_url"]
        if data["wikipedia_url"]:
            metadata["wikipedia_url"] = data["wikipedia_url"]
        if data.get("facts"):
            metadata["facts"] = data["facts"]
            
        res = conn.execute(text("""
            INSERT INTO core.entity (
                entity_type_id, display_name, preferred_language_code, 
                state, visibility, summary, metadata
            ) VALUES (
                :entity_type_id, :display_name, 'bn',
                'candidate', 'public', :summary, :metadata
            ) RETURNING entity_id
        """), {
            "entity_type_id": entity_type_id,
            "display_name": data["title"],
            "summary": data["summary"],
            "metadata": json.dumps(metadata)
        })
        entity_id = res.first()[0]
        
        # Insert entity_name
        conn.execute(text("""
            INSERT INTO core.entity_name (
                entity_id, name, normalised_name, language_code, 
                script, name_kind, is_primary, state
            ) VALUES (
                :entity_id, :name, :name, 'bn',
                'bangla', 'preferred', TRUE, 'candidate'
            )
        """), {
            "entity_id": entity_id,
            "name": data["title"]
        })
        
def main():
    engine = get_engine()
    
    # Note: Added 'metadata' column requirement dynamically for this phase 
    # since we decided to use JSONB without raw migration
    with engine.begin() as conn:
        # ensure metadata column exists (it should, as per schema)
        pass
        
    for target in TARGETS:
        log.info(f"Processing: {target}")
        data = fetch_wikipedia_data(target)
        if data:
            insert_entity(engine, data)

if __name__ == "__main__":
    main()
