import sys
import os
import requests
import json
import logging
from bs4 import BeautifulSoup
from urllib.parse import quote

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from crawler.utils.db import get_engine
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("GeoCrawler")

HEADERS = {
    'User-Agent': 'KhujoBot/1.0 (Crawler for local BD search engine)'
}

def fetch_wiki_geo(title):
    encoded_title = quote(title.replace(' ', '_'))
    url = f"https://bn.wikipedia.org/wiki/{encoded_title}"
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return None
        
        soup = BeautifulSoup(r.text, 'html.parser')
        
        summary = ""
        content_div = soup.find('div', class_='mw-parser-output')
        if content_div:
            for p in content_div.find_all('p', recursive=False):
                text_content = p.text.strip()
                if len(text_content) > 50:
                    sentences = text_content.replace('।', '।|').split('|')
                    summary = "".join(sentences[:2]).strip()
                    break
        
        facts = {}
        infobox = soup.find('table', class_='infobox')
        if infobox:
            for tr in infobox.find_all('tr'):
                th = tr.find('th')
                td = tr.find('td')
                if th and td and th.text.strip() and td.text.strip():
                    key = th.text.strip()
                    for sup in td.find_all('sup'):
                        sup.decompose()
                    val = td.text.strip().replace('\n', ', ')
                    if len(val) > 0 and len(val) < 80:
                        facts[key] = val
        
        images = []
        if infobox:
            for img in infobox.find_all('img'):
                width = int(img.get('width', 0) or 0)
                if width > 80:
                    src = img['src']
                    if src.startswith('//'):
                        src = 'https:' + src
                    images.append(src)
        
        for img in soup.find_all('img', class_='thumbimage'):
            if len(images) >= 3:
                break
            width = int(img.get('width', 0) or 0)
            if width > 100:
                src = img['src']
                if src.startswith('//'):
                    src = 'https:' + src
                if src not in images:
                    images.append(src)
        
        images = images[:3]
        
        return {
            "title": title,
            "summary": summary,
            "images": images,
            "facts": facts,
            "wikipedia_url": url
        }
    except Exception as e:
        log.error(f"Error fetching data for {title}: {e}")
        return None

def update_geo_entity(engine, entity_id, data: dict):
    with engine.begin() as conn:
        metadata = {}
        if data["images"]:
            metadata["images"] = data["images"]
            metadata["image_url"] = data["images"][0] 
        if data["wikipedia_url"]:
            metadata["wikipedia_url"] = data["wikipedia_url"]
        if data.get("facts"):
            metadata["facts"] = data["facts"]
            
        conn.execute(text("""
            UPDATE core.entity 
            SET summary = :summary, metadata = metadata || CAST(:metadata AS jsonb)
            WHERE entity_id = :eid
        """), {
            "summary": data["summary"][:500] if data["summary"] else None,
            "metadata": json.dumps(metadata, ensure_ascii=False),
            "eid": entity_id
        })
        log.info(f"Updated entity {entity_id} with {len(data['images'])} images.")

def run():
    engine = get_engine()
    with engine.connect() as conn:
        entities = conn.execute(text("""
            SELECT e.entity_id, e.display_name 
            FROM core.entity e
            JOIN core.entity_type et ON e.entity_type_id = et.entity_type_id
            WHERE et.slug IN ('administrative_area', 'settlement', 'place', 'natural_feature')
              AND (e.summary IS NULL OR e.metadata->>'images' IS NULL)
            LIMIT 50
        """)).fetchall()
        
    log.info(f"Found {len(entities)} geographical entities to crawl.")
    for eid, name in entities:
        log.info(f"Crawling {name}...")
        data = fetch_wiki_geo(name)
        if data and (data["summary"] or data["images"]):
            update_geo_entity(engine, eid, data)
        else:
            log.warning(f"No meaningful data found for {name}.")

if __name__ == "__main__":
    run()
