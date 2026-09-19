"""
KhujoBot Phase 2: Worker 01 - Fetch
Downloads raw HTML from the frontier queue and saves it locally.
"""
import os
import time
import hashlib
import logging
import requests
from sqlalchemy import text
from utils.db import get_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("worker_01_fetch")

KHUJO_UA = "KhujoBot/2.0 (+https://khujo.com.bd/bot)"
HEADERS = {"User-Agent": KHUJO_UA}

RAW_HTML_DIR = os.path.join(os.path.dirname(__file__), "data", "raw_html")
os.makedirs(RAW_HTML_DIR, exist_ok=True)

def fetch_queued_urls(batch_limit=10):
    engine = get_engine()
    
    with engine.connect() as conn:
        urls = conn.execute(text("""
            SELECT frontier_url_id, canonical_url 
            FROM crawl.frontier_url
            WHERE state = 'queued' AND priority < 10
            ORDER BY next_fetch_at ASC
            LIMIT :limit
        """), {"limit": batch_limit}).fetchall()
        
        if not urls:
            log.info("No URLs in the frontier queue.")
            return

        log.info(f"Found {len(urls)} URLs to fetch.")
        
        for row in urls:
            frontier_id = str(row[0])
            url = row[1]
            
            log.info(f"Fetching: {url}")
            
            # Polite crawling
            time.sleep(2)
            
            try:
                resp = requests.get(url, headers=HEADERS, timeout=12, allow_redirects=True)
                
                # Fix encoding if missing
                if resp.encoding is None or resp.encoding.lower() == 'iso-8859-1':
                    resp.encoding = resp.apparent_encoding or 'utf-8'
                
                html_content = resp.text
                status_code = resp.status_code
                
                if status_code != 200:
                    log.warning(f"HTTP {status_code} for {url}")
                    with engine.begin() as wconn:
                        wconn.execute(text("""
                            UPDATE crawl.frontier_url 
                            SET state = 'failed', last_status_code = :code, failure_count = failure_count + 1
                            WHERE frontier_url_id = :fid
                        """), {"code": status_code, "fid": frontier_id})
                    continue

                # Hash content
                content_hash = hashlib.sha256(html_content.encode("utf-8")).hexdigest()
                file_path = os.path.join(RAW_HTML_DIR, f"{content_hash}.html")
                
                # Save raw HTML locally
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(html_content)
                
                # Update database
                with engine.begin() as wconn:
                    # 1. Log the fetch
                    wconn.execute(text("""
                        INSERT INTO crawl.fetch (
                            frontier_url_id, state, http_status, final_url, 
                            content_type, content_language, response_bytes, content_hash
                        ) VALUES (
                            :fid, 'success', :status, :final_url,
                            :ctype, :clang, :bytes, :hash
                        )
                    """), {
                        "fid": frontier_id,
                        "status": status_code,
                        "final_url": resp.url,
                        "ctype": resp.headers.get("Content-Type"),
                        "clang": resp.headers.get("Content-Language"),
                        "bytes": len(html_content.encode("utf-8")),
                        "hash": content_hash
                    })
                    
                    # 2. Mark frontier URL as fetched
                    wconn.execute(text("""
                        UPDATE crawl.frontier_url 
                        SET state = 'fetched', last_fetch_at = now(), last_status_code = :status
                        WHERE frontier_url_id = :fid
                    """), {"status": status_code, "fid": frontier_id})
                
                log.info(f"Successfully fetched and saved {content_hash}.html")
                
            except Exception as e:
                log.error(f"Error fetching {url}: {e}")
                with engine.begin() as wconn:
                    wconn.execute(text("""
                        UPDATE crawl.frontier_url 
                        SET state = 'failed', failure_count = failure_count + 1
                        WHERE frontier_url_id = :fid
                    """), {"fid": frontier_id})

if __name__ == "__main__":
    fetch_queued_urls(5)
