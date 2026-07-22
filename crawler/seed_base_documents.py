"""
KhujoBot v1 — Base Homepage Document Seeder (seed_base_documents.py)
Creates candidate entries in content.document for all Base Platform URLs & News Publishers
(Google, Facebook, YouTube, Instagram, LinkedIn, Prothom Alo, Daily Star, etc.)
so their official Base Homepages can be approved by Admin and indexed on SERP!
"""

import os
import hashlib
import logging
import requests
from bs4 import BeautifulSoup
from sqlalchemy import text
from utils.db import get_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("seed_base_docs")

KHUJO_UA = "KhujoBot/1.0 (+https://khujo.com.bd/bot)"
HEADERS = {"User-Agent": KHUJO_UA}

def seed_base_documents():
    engine = get_engine()

    with engine.connect() as conn:
        sources = conn.execute(text("""
            SELECT source_id, source_name, canonical_domain, homepage_url 
            FROM core.source 
            WHERE homepage_url IS NOT NULL AND is_active = true
        """)).fetchall()

        if not sources:
            log.info("No active sources with homepage URLs found.")
            return

        log.info("Found %d Base Sources to stage as Homepage Documents.", len(sources))

        staged_count = 0

        for row in sources:
            source_id = str(row[0])
            source_name = row[1]
            domain = row[2]
            homepage_url = row[3]

            log.info("\nProcessing Base Homepage: %s (%s)...", source_name, homepage_url)

            # Try fetching homepage for title and description
            title = f"{source_name} — Base Platform Homepage"
            description = f"{source_name} ({domain}) এর অফিশিয়াল ওয়েবাসাইট ও প্ল্যাটফর্ম লিংক।"
            body_text = f"{source_name} ({domain}) বাংলাদেশের জন্য প্রধান প্ল্যাটফর্ম ও তথ্য উৎস। {homepage_url}"

            try:
                resp = requests.get(homepage_url, headers=HEADERS, timeout=10, allow_redirects=True)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.content, "html.parser")
                    
                    title_tag = soup.find("meta", property="og:title") or soup.find("title")
                    if title_tag:
                        fetched_title = title_tag.get("content") or title_tag.get_text()
                        if fetched_title and len(fetched_title.strip()) > 2:
                            title = fetched_title.strip().replace("\n", " ")

                    desc_tag = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "description"})
                    if desc_tag and desc_tag.get("content"):
                        description = desc_tag.get("content").strip()
            except Exception as e:
                log.warning("  Could not fetch live HTML for %s: %s (using curated base fallback)", homepage_url, e)

            content_hash = hashlib.sha256(body_text.encode("utf-8")).hexdigest()

            with engine.begin() as write_conn:
                # 1. Ensure core.source_record exists
                srid = write_conn.execute(text("""
                    SELECT source_record_id FROM core.source_record WHERE canonical_url = :url LIMIT 1
                """), {"url": homepage_url}).scalar()

                if not srid:
                    srid = write_conn.execute(text("""
                        INSERT INTO core.source_record (source_id, canonical_url, title, state)
                        VALUES (:sid, :url, :title, 'candidate')
                        RETURNING source_record_id
                    """), {"sid": source_id, "url": homepage_url, "title": title}).scalar()

                # 2. Check if document already exists
                exists = write_conn.execute(text("""
                    SELECT 1 FROM content.document WHERE canonical_url = :url OR source_record_id = :srid LIMIT 1
                """), {"url": homepage_url, "srid": srid}).scalar()

                if not exists:
                    doc_id = write_conn.execute(text("""
                        INSERT INTO content.document (
                            source_record_id, canonical_url, title, title_normalised, summary,
                            body_text, body_normalised, language_code, content_hash, state, document_kind
                        )
                        VALUES (
                            :srid, :url, :title, lower(:title), :desc,
                            :body, lower(:body), 'bn', :hash, 'candidate', 'listing'
                        )
                        RETURNING document_id
                    """), {
                        "srid": srid,
                        "url": homepage_url,
                        "title": title[:250],
                        "desc": description[:500],
                        "body": body_text[:5000],
                        "hash": content_hash
                    }).scalar()

                    log.info("  ✓ Staged Base Homepage Document ID: %s in Pending Queue", doc_id)
                    staged_count += 1
                else:
                    log.info("  Base Homepage already exists in content.document.")

        log.info("\nBase Homepage Staging Complete: %d new base platform homepages staged in Admin Vault.", staged_count)

if __name__ == "__main__":
    seed_base_documents()
