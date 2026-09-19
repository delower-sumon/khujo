# Khujo Phase 3 Heavy Enrichment Worker (Google Colab Version)
# INSTRUCTIONS FOR RUNNING IN COLAB:
# 1. Upload `base_hierarchy.csv` and `micro_locations_raw.csv` to your Colab workspace.
# 2. Run: `!pip install httpx pandas bs4 aiohttp nest_asyncio`
# 3. Paste this entire script into a cell and execute it.
# 4. Download `places_enriched_master.csv`.

import asyncio
import nest_asyncio
import pandas as pd
import aiohttp
import json
import logging
from bs4 import BeautifulSoup
import urllib.parse

# Allow async execution inside Colab's event loop
nest_asyncio.apply()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("worker_03_colab")

WIKI_API_URL = "https://bn.wikipedia.org/w/api.php"

async def fetch_wiki_details(session, place_name):
    """Fetch short description and main image URL from Bengali Wikipedia."""
    # Action API to get page extracts and pageimages
    params = {
        "action": "query",
        "format": "json",
        "prop": "extracts|pageimages",
        "titles": place_name,
        "exintro": 1,          # Only the intro paragraph
        "explaintext": 1,      # Plain text instead of HTML
        "pithumbsize": 500,    # 500px width thumbnail
        "redirects": 1         # Follow redirects automatically
    }
    
    try:
        async with session.get(WIKI_API_URL, params=params, timeout=10.0) as resp:
            data = await resp.json()
            pages = data.get("query", {}).get("pages", {})
            for page_id, page_info in pages.items():
                if page_id == "-1":
                    return "", "" # Page not found
                
                extract = page_info.get("extract", "").strip()
                # Limit to first 2-3 sentences for a short SERP detail
                short_desc = extract[:500] + "..." if len(extract) > 500 else extract
                
                image_url = page_info.get("thumbnail", {}).get("source", "")
                return short_desc, image_url
    except Exception as e:
        # log.warning(f"Error fetching {place_name}: {e}")
        return "", ""

async def enrich_batch(session, batch_df):
    """Process a batch of places asynchronously."""
    tasks = []
    for _, row in batch_df.iterrows():
        # Try finding by bn_name
        tasks.append(fetch_wiki_details(session, row['name_bn']))
    
    results = await asyncio.gather(*tasks)
    
    descriptions = []
    images = []
    for desc, img in results:
        descriptions.append(desc)
        images.append(img)
        
    batch_df['bn_description'] = descriptions
    batch_df['image_url'] = images
    return batch_df

async def main():
    log.info("Loading Base Hierarchy and Micro-Locations...")
    try:
        df_base = pd.read_csv("base_hierarchy.csv")
        df_micro = pd.read_csv("micro_locations_raw.csv")
        
        # Combine both datasets for processing
        df_all = pd.concat([df_base, df_micro], ignore_index=True)
        log.info(f"Total entities to process: {len(df_all)}")
    except FileNotFoundError:
        log.error("Please upload base_hierarchy.csv and micro_locations_raw.csv to the Colab environment first.")
        return

    # Add new columns
    df_all['bn_description'] = ""
    df_all['image_url'] = ""
    df_all['population'] = "" # To be populated via BBS/Wikidata integration later

    log.info("Starting Wikipedia Enrichment...")
    batch_size = 50
    enriched_dfs = []
    
    # Optional: For testing, limit to first 200 rows if you just want to verify
    # df_all = df_all.head(200)

    async with aiohttp.ClientSession() as session:
        for i in range(0, len(df_all), batch_size):
            batch = df_all.iloc[i:i+batch_size].copy()
            log.info(f"Enriching batch {i} to {i+len(batch)} of {len(df_all)}...")
            enriched_batch = await enrich_batch(session, batch)
            enriched_dfs.append(enriched_batch)
            
            # Simple rate limiting for Wikimedia servers
            await asyncio.sleep(0.5)

    df_final = pd.concat(enriched_dfs, ignore_index=True)
    
    # Print stats
    desc_count = (df_final['bn_description'] != "").sum()
    img_count = (df_final['image_url'] != "").sum()
    log.info(f"Enrichment Complete!")
    log.info(f"Found {desc_count} descriptions and {img_count} images.")
    
    out_file = "places_enriched_master.csv"
    df_final.to_csv(out_file, index=False, encoding='utf-8')
    log.info(f"Saved to {out_file}. Please download this file and prepare for DB commit.")

if __name__ == "__main__":
    asyncio.run(main())
