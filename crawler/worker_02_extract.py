"""
KhujoBot Phase 2: Worker 02 - Extract
Reads raw HTML saved by Worker 01, extracts structured data, and stages documents.
"""
import os
import logging
import re
from bs4 import BeautifulSoup
from sqlalchemy import text
from utils.db import get_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("worker_02_extract")

RAW_HTML_DIR = os.path.join(os.path.dirname(__file__), "data", "raw_html")

def clean_body_text(soup: BeautifulSoup) -> str:
    body_soup = BeautifulSoup(str(soup), "html.parser")
    for tag in body_soup(["script", "style", "nav", "header", "footer", "aside", "form", "iframe", "noscript", "figure", "figcaption"]):
        tag.decompose()

    for class_or_id in ["sidebar", "ads", "advertisement", "comment", "social-share", "related-posts", "footer"]:
        for element in body_soup.find_all(class_=re.compile(class_or_id, re.I)):
            element.decompose()

    main_content = body_soup.find("article") or body_soup.find("main") or body_soup.find("body") or body_soup
    lines = (line.strip() for line in main_content.get_text(separator="\n").splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    cleaned_text = "\n".join(chunk for chunk in chunks if chunk)
    return cleaned_text

def extract_article_data(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    
    canonical_link = soup.find("link", rel="canonical") or soup.find("meta", property="og:url")
    canonical_url = canonical_link.get("href") or canonical_link.get("content") if canonical_link else url

    title_tag = soup.find("meta", property="og:title") or soup.find("title")
    title = title_tag.get("content") or title_tag.get_text() if title_tag else ""
    title = title.strip().replace("\n", " ")

    desc_tag = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "description"})
    description = desc_tag.get("content") if desc_tag else ""

    body_text = clean_body_text(soup)

    pub_tag = soup.find("meta", property="article:published_time") or soup.find("time")
    published_at = pub_tag.get("content") or pub_tag.get("datetime") if pub_tag else None

    return {
        "canonical_url": canonical_url or url,
        "title": title[:250] if title else "Untitled Document",
        "description": description[:500] if description else "",
        "body_text": body_text[:10000] if body_text else "",
        "published_at": published_at
    }

def process_extractions(batch_limit=10):
    engine = get_engine()

    with engine.connect() as conn:
        fetches = conn.execute(text("""
            SELECT f.fetch_id, f.content_hash, f.final_url, u.source_id
            FROM crawl.fetch f
            JOIN crawl.frontier_url u ON f.frontier_url_id = u.frontier_url_id
            WHERE f.parsed_at IS NULL AND f.state = 'success'
            ORDER BY f.created_at ASC
            LIMIT :limit
        """), {"limit": batch_limit}).fetchall()
        
        if not fetches:
            log.info("No unparsed fetches in the queue.")
            return

        log.info(f"Found {len(fetches)} fetched pages to extract.")

        for row in fetches:
            fetch_id = str(row[0])
            content_hash = row[1]
            final_url = row[2]
            source_id = str(row[3]) if row[3] else None
            
            file_path = os.path.join(RAW_HTML_DIR, f"{content_hash}.html")
            
            if not os.path.exists(file_path):
                log.warning(f"Raw HTML file missing for {content_hash}. Skipping extraction.")
                with engine.begin() as wconn:
                    wconn.execute(text("UPDATE crawl.fetch SET parsed_at = now() WHERE fetch_id = :fid"), {"fid": fetch_id})
                continue

            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                html_content = f.read()

            data = extract_article_data(html_content, final_url)
            body_text = data["body_text"]
            
            if not body_text or len(body_text.strip()) < 50:
                log.warning(f"Extracted body too short for {final_url}. Marking as parsed but skipping document insert.")
                with engine.begin() as wconn:
                    wconn.execute(text("UPDATE crawl.fetch SET parsed_at = now() WHERE fetch_id = :fid"), {"fid": fetch_id})
                continue
                
            with engine.begin() as write_conn:
                # Get or Create source_record
                source_record_id = write_conn.execute(text("""
                    SELECT source_record_id FROM core.source_record WHERE canonical_url = :url LIMIT 1
                """), {"url": data["canonical_url"]}).scalar()

                if not source_record_id:
                    source_record_id = write_conn.execute(text("""
                        INSERT INTO core.source_record (source_id, canonical_url, title, state)
                        VALUES (:sid, :url, :title, 'candidate')
                        RETURNING source_record_id
                    """), {"sid": source_id, "url": data["canonical_url"], "title": data["title"]}).scalar()

                # Insert document
                exists = write_conn.execute(text("""
                    SELECT 1 FROM content.document WHERE canonical_url = :url OR content_hash = :hash LIMIT 1
                """), {"url": data["canonical_url"], "hash": content_hash}).scalar()
                
                if not exists:
                    write_conn.execute(text("""
                        INSERT INTO content.document (
                            document_kind, source_record_id, fetch_id, canonical_url, 
                            title, body_text, published_at, content_hash, state
                        ) VALUES (
                            'article', :srid, :fid, :url,
                            :title, :body, :pub, :hash, 'candidate'
                        )
                    """), {
                        "srid": source_record_id,
                        "fid": fetch_id,
                        "url": data["canonical_url"],
                        "title": data["title"],
                        "body": body_text,
                        "pub": data["published_at"],
                        "hash": content_hash
                    })
                    log.info(f"Staged document candidate for {data['canonical_url']}")
                else:
                    log.info(f"Document {data['canonical_url']} already exists.")

                # Mark as parsed
                write_conn.execute(text("""
                    UPDATE crawl.fetch SET parsed_at = now() WHERE fetch_id = :fid
                """), {"fid": fetch_id})

if __name__ == "__main__":
    process_extractions(5)
