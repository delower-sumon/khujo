import asyncio
import csv
import logging
import os
import time
import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("worker_02_micro_locations")

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
OUT_FILE = os.path.join(os.path.dirname(__file__), "data", "micro_locations_raw.csv")

# Overpass QL template to fetch villages, hamlets, and neighbourhoods by Division
OVERPASS_QUERY_TEMPLATE = """
[out:json][timeout:300];
area["name:en"="{division} Division"]["admin_level"="4"]->.searchArea;
(
  node["place"~"village|hamlet|neighbourhood|suburb"](area.searchArea);
  way["place"~"village|hamlet|neighbourhood|suburb"](area.searchArea);
);
out center;
"""

DIVISIONS = [
    "Dhaka", "Chittagong", "Rajshahi", "Khulna", 
    "Barisal", "Sylhet", "Rangpur", "Mymensingh"
]

OVERPASS_URLS = [
    "https://overpass-api.de/api/interpreter",
    "https://lz4.overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter"
]

async def fetch_osm_places_for_division(division_name: str):
    log.info(f"Fetching micro-locations for {division_name} Division...")
    query = OVERPASS_QUERY_TEMPLATE.format(division=division_name)
    
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'User-Agent': 'KhujoBot/1.0 (khujo-search-engine)'
    }
    
    async with httpx.AsyncClient(timeout=300.0) as client:
        for url in OVERPASS_URLS:
            try:
                resp = await client.post(
                    url, 
                    content=f"data={query}".encode('utf-8'),
                    headers=headers
                )
                
                if resp.status_code == 429:
                    log.warning("Rate limited. Waiting 30s...")
                    await asyncio.sleep(30)
                    continue
                    
                if resp.status_code != 200:
                    log.warning(f"Endpoint {url} failed with status {resp.status_code}. Skipping to next endpoint.")
                    continue
                
                try:
                    data = resp.json()
                    elements = data.get('elements', [])
                    log.info(f"Success! {division_name}: found {len(elements)} elements.")
                    return elements
                except Exception as e:
                    log.warning(f"Endpoint {url} returned non-JSON for {division_name}.")
                    continue
            except Exception as e:
                log.warning(f"Endpoint {url} encountered an error: {e}")
                continue
                
        log.error(f"Failed to fetch data for {division_name} Division.")
        return []

async def fetch_all_divisions():
    all_elements = []
    for div in DIVISIONS:
        elements = await fetch_osm_places_for_division(div)
        all_elements.extend(elements)
        # Sleep to avoid getting banned
        await asyncio.sleep(5)
    return all_elements

async def main():
    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
    
    elements = await fetch_all_divisions()
    log.info(f"Total retrieved: {len(elements)} raw elements from OSM.")

    rows = []
    for el in elements:
        tags = el.get('tags', {})
        
        # OSM primarily uses 'name:bn' for Bengali names, fallback to 'name'
        name_en = tags.get('name:en') or tags.get('name', '')
        name_bn = tags.get('name:bn', '')
        
        # Skip if there's no Bengali name, as Khujo is a native Bangla search engine
        if not name_bn:
            continue
            
        place_type = tags.get('place', '')
        
        # Map OSM tags to our taxonomy
        khujo_type = "Village"
        if place_type == "neighbourhood" or place_type == "suburb":
            khujo_type = "Mahalla"
        elif place_type == "hamlet":
            khujo_type = "Mouza"

        lat = el.get('lat') or (el.get('center', {}).get('lat'))
        lon = el.get('lon') or (el.get('center', {}).get('lon'))

        rows.append({
            "place_type": khujo_type,
            "internal_id": f"OSM_{el['type']}_{el['id']}",
            "parent_id": "", # To be linked spatially in Colab
            "name_en": name_en,
            "name_bn": name_bn,
            "latitude": lat,
            "longitude": lon,
            "website": tags.get('website', '')
        })

    fields = ["place_type", "internal_id", "parent_id", "name_en", "name_bn", "latitude", "longitude", "website"]
    
    with open(OUT_FILE, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    log.info(f"Successfully collected {len(rows)} Bengali micro-locations into {OUT_FILE}.")
    log.info("Phase 2 Collect complete. Ready for Colab Heavy Enrichment.")

if __name__ == "__main__":
    asyncio.run(main())
