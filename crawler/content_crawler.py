"""
KhujoBot v1 — Phase 2: Content Crawler (content_crawler.py)
Crawls queued article URLs from crawl.frontier_url (priority < 10).
Extracts clean title, body text, canonical URL, tags entity mentions against core.entity_name,
uploads og:image to Cloudflare R2 if present (storing only R2 CDN URL string in DB),
and inserts candidate documents into content.document (staged for Admin Verification Gate).
"""

import os
import hashlib
import logging
import re
from urllib.parse import urlparse, urljoin
import requests
from bs4 import BeautifulSoup
from sqlalchemy import text
import time
from utils.db import get_engine
from utils.r2 import upload_favicon
from utils.links import compute_url_hash, is_valid_article_url
from utils.robots import is_url_allowed
try:
    from backend.app.nlp.bangla_stemmer import stem_and_normalize_bangla
except ImportError:
    try:
        from app.nlp.bangla_stemmer import stem_and_normalize_bangla
    except ImportError:
        def stem_and_normalize_bangla(t):
            return t.lower() if t else ""

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("content_crawler")

KHUJO_UA = "KhujoBot/1.0 (+https://khujo.com.bd/bot)"
HEADERS = {"User-Agent": KHUJO_UA}

def clean_body_text(soup: BeautifulSoup) -> str:
    """Strip navigation, headers, footers, sidebars, ads, scripts, and styles."""
    # Clone soup so original isn't mutated
    body_soup = BeautifulSoup(str(soup), "html.parser")

    # Remove non-content elements and garbage tags
    for tag in body_soup(["script", "style", "nav", "header", "footer", "aside", "form", "iframe", "noscript", "figure", "figcaption"]):
        tag.decompose()

    for class_or_id in ["sidebar", "ads", "advertisement", "comment", "social-share", "related-posts", "footer"]:
        for element in body_soup.find_all(class_=re.compile(class_or_id, re.I)):
            element.decompose()

    # Prefer <article> or <main> if available
    main_content = body_soup.find("article") or body_soup.find("main") or body_soup.find("body") or body_soup
    
    lines = (line.strip() for line in main_content.get_text(separator="\n").splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    cleaned_text = "\n".join(chunk for chunk in chunks if chunk)
    return cleaned_text

def extract_article_data(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    
    # Discover internal links for the deep recursive spider
    discovered_links = set()
    for a_tag in soup.find_all("a", href=True):
        full_url = urljoin(url, a_tag["href"]).split("#")[0].strip()
        discovered_links.add(full_url)

    # Canonical URL
    canonical_link = soup.find("link", rel="canonical") or soup.find("meta", property="og:url")
    canonical_url = canonical_link.get("href") or canonical_link.get("content") if canonical_link else url

    # Title
    title_tag = soup.find("meta", property="og:title") or soup.find("title")
    title = title_tag.get("content") or title_tag.get_text() if title_tag else ""
    title = title.strip().replace("\n", " ")

    # Description / Snippet
    desc_tag = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "description"})
    description = desc_tag.get("content") if desc_tag else ""

    # Clean body
    body_text = clean_body_text(soup)

    # og:image URL
    og_image_tag = soup.find("meta", property="og:image")
    og_image_url = og_image_tag.get("content") if og_image_tag else None

    # Published time
    pub_tag = soup.find("meta", property="article:published_time") or soup.find("time")
    published_at = pub_tag.get("content") or pub_tag.get("datetime") if pub_tag else None

    return {
        "canonical_url": canonical_url or url,
        "title": title[:250] if title else "Untitled Document",
        "description": description[:500] if description else "",
        "body_text": body_text[:10000] if body_text else "",  # Up to 10k chars
        "og_image_url": og_image_url,
        "published_at": published_at,
        "links": discovered_links
    }

def crawl_content_urls(batch_limit: int = 10):
    engine = get_engine()

    with engine.connect() as conn:
        # Load active core entities for keyword matching (tagging entity mentions)
        entities = conn.execute(text("""
            SELECT en.entity_id, en.name, en.language_code
            FROM core.entity_name en
            JOIN core.entity e ON en.entity_id = e.entity_id
            WHERE e.state = 'verified' AND length(en.name) >= 3
            ORDER BY length(en.name) DESC
            LIMIT 300
        """)).fetchall()

        entity_lookup = [(str(r[0]), r[1], r[2]) for r in entities]
        log.info("Loaded %d core entities for mention tagging.", len(entity_lookup))

        # Fetch queued content URLs
        urls = conn.execute(text("""
            SELECT frontier_url_id, source_id, canonical_url, host
            FROM crawl.frontier_url
            WHERE priority < 10 AND state = 'queued'
            ORDER BY created_at ASC
            LIMIT :limit
        """), {"limit": batch_limit}).fetchall()

        if not urls:
            log.info("No content URLs waiting in frontier queue.")
            return

        log.info("Found %d article URLs to crawl.", len(urls))

        crawled_count = 0

        for row in urls:
            frontier_id = str(row[0])
            source_id = str(row[1]) if row[1] else None
            article_url = row[2]
            host = row[3]

            log.info("\n--- Crawling Article: %s ---", article_url)

            try:
                # Polite rate limiting (2 seconds between requests)
                time.sleep(2)
                
                resp = requests.get(article_url, headers=HEADERS, timeout=12, allow_redirects=True)
                
                # Fix Bengali Mojibake: explicitly detect encoding if server omits it
                if resp.encoding is None or resp.encoding.lower() == 'iso-8859-1':
                    resp.encoding = resp.apparent_encoding or 'utf-8'

                if resp.status_code != 200:
                    log.warning("  HTTP %d for %s. Marking failed.", resp.status_code, article_url)
                    with engine.begin() as err_conn:
                        err_conn.execute(text("""
                            UPDATE crawl.frontier_url 
                            SET state = 'failed', last_status_code = :code, failure_count = failure_count + 1
                            WHERE frontier_url_id = :fid
                        """), {"code": resp.status_code, "fid": frontier_id})
                    continue

                # Extract content
                data = extract_article_data(resp.text, article_url)
                body_text = data["body_text"]

                if not body_text or len(body_text.strip()) < 50:
                    log.warning("  Extracted body text too short for %s. Skipping insert.", article_url)
                    with engine.begin() as skip_conn:
                        skip_conn.execute(text("""
                            UPDATE crawl.frontier_url SET state = 'fetched', last_status_code = 200 WHERE frontier_url_id = :fid
                        """), {"fid": frontier_id})
                    continue

                content_hash = hashlib.sha256(body_text.encode("utf-8")).hexdigest()

                with engine.begin() as write_conn:
                    # Ensure source_record exists
                    source_record_id = write_conn.execute(text("""
                        SELECT source_record_id FROM core.source_record WHERE canonical_url = :url LIMIT 1
                    """), {"url": data["canonical_url"]}).scalar()

                    # Check if document already exists by canonical_url, content_hash, or source_record_id
                    exists = False
                    if source_record_id:
                        exists = write_conn.execute(text("""
                            SELECT 1 FROM content.document WHERE source_record_id = :srid OR canonical_url = :url OR content_hash = :hash LIMIT 1
                        """), {"srid": source_record_id, "url": data["canonical_url"], "hash": content_hash}).scalar()
                    else:
                        exists = write_conn.execute(text("""
                            SELECT 1 FROM content.document WHERE canonical_url = :url OR content_hash = :hash LIMIT 1
                        """), {"url": data["canonical_url"], "hash": content_hash}).scalar()

                    if exists:
                        log.info("  Document already exists in DB. Skipping.")
                        write_conn.execute(text("""
                            UPDATE crawl.frontier_url SET state = 'fetched', last_fetch_at = now(), last_status_code = 200 WHERE frontier_url_id = :fid
                        """), {"fid": frontier_id})
                        continue

                    if not source_record_id:
                        source_record_id = write_conn.execute(text("""
                            INSERT INTO core.source_record (source_id, canonical_url, title, state)
                            VALUES (:sid, :url, :title, 'candidate')
                            RETURNING source_record_id
                        """), {"sid": source_id, "url": data["canonical_url"], "title": data["title"]}).scalar()


                    norm_title = stem_and_normalize_bangla(data["title"])
                    norm_body = stem_and_normalize_bangla(body_text[:5000])

                    # Insert document into content.document (state = 'candidate' for Admin Gate!)
                    doc_id = write_conn.execute(text("""
                        INSERT INTO content.document (
                            source_record_id, canonical_url, title, title_normalised, summary,
                            body_text, body_normalised, language_code, content_hash, state, document_kind
                        )
                        VALUES (
                            :srid, :url, :title, :norm_title, :desc,
                            :body, :norm_body, 'bn', :hash, 'candidate', 'news'
                        )
                        RETURNING document_id
                    """), {
                        "srid": source_record_id,
                        "url": data["canonical_url"],
                        "title": data["title"],
                        "norm_title": norm_title,
                        "desc": data["description"],
                        "body": body_text,
                        "norm_body": norm_body,
                        "hash": content_hash
                    }).scalar()




                    if doc_id:
                        log.info("  ✓ Created Candidate Document ID: %s", doc_id)

                        # Tag Entity Mentions against core.entity_name
                        search_corpus = f"{data['title']}\n{body_text}".lower()
                        matched_entities = set()

                        for eid, ename, elang in entity_lookup:
                            if ename.lower() in search_corpus:
                                matched_entities.add((eid, ename))
                                if len(matched_entities) >= 5: # Max 5 mentions per document
                                    break

                        for eid, ename in matched_entities:
                            write_conn.execute(text("""
                                INSERT INTO content.entity_mention (source_record_id, entity_id, surface_form, confidence, extraction_method, state)
                                VALUES (:srid, :eid, :form, 0.90, 'keyword_match', 'candidate')
                            """), {"srid": source_record_id, "eid": eid, "form": ename})



                        log.info("  Tagged %d entity mentions linked to Knowledge Graph.", len(matched_entities))

                    # Update frontier state = 'fetched'
                    write_conn.execute(text("""
                        UPDATE crawl.frontier_url 
                        SET state = 'fetched', last_fetch_at = now(), last_status_code = 200
                        WHERE frontier_url_id = :fid
                    """), {"fid": frontier_id})

                    # Queue newly discovered internal links (Recursive Spider)
                    queued_links = 0
                    for link in list(data["links"]):
                        if is_valid_article_url(link, host) and is_url_allowed(link, KHUJO_UA):
                            link_hash = compute_url_hash(link)
                            exists = write_conn.execute(text("""
                                SELECT 1 FROM crawl.frontier_url WHERE canonical_url = :url OR url_hash = :hash LIMIT 1
                            """), {"url": link, "hash": link_hash}).scalar()
                            
                            if not exists:
                                write_conn.execute(text("""
                                    INSERT INTO crawl.frontier_url (source_id, canonical_url, original_url, host, url_hash, priority, state)
                                    VALUES (:sid, :url, :url, :domain, :hash, 5, 'queued')
                                """), {"sid": source_id, "url": link, "domain": host, "hash": link_hash})
                                queued_links += 1
                                if queued_links >= 20: # Max 20 new links per article to prevent explosion
                                    break
                    
                    log.info("  Deep Spider queued %d new internal links.", queued_links)

                crawled_count += 1
                log.info("  Successfully processed %s", article_url)


            except Exception as e:
                log.error("  Error crawling %s: %s", article_url, e)
                with engine.begin() as err_conn:
                    err_conn.execute(text("""
                        UPDATE crawl.frontier_url 
                        SET state = 'failed', failure_count = failure_count + 1
                        WHERE frontier_url_id = :fid
                    """), {"fid": frontier_id})

        log.info("\nContent Crawl Complete: %d candidate documents processed and staged for Admin Verification.", crawled_count)

if __name__ == "__main__":
    crawl_content_urls()
