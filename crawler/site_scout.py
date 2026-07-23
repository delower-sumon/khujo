import os
import hashlib
import logging
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
import requests
from sqlalchemy import text
from utils.db import get_engine
from utils.r2 import fetch_and_upload_favicon
from utils.robots import is_url_allowed
from utils.links import compute_url_hash, is_valid_article_url


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("site_scout")

KHUJO_UA = "KhujoBot/1.0 (+https://khujo.com.bd/bot)"
HEADERS = {"User-Agent": KHUJO_UA}


def scout_base_urls():
    engine = get_engine()

    with engine.connect() as conn:
        # Fetch base URLs waiting to be scouted
        rows = conn.execute(text("""
            SELECT frontier_url_id, source_id, canonical_url, host
            FROM crawl.frontier_url
            WHERE priority = 10 AND state = 'queued'
            ORDER BY created_at ASC
            LIMIT 10
        """)).fetchall()

        if not rows:
            log.info("No base URLs waiting in frontier queue for scouting.")
            return

        log.info("Found %d base URLs to scout.", len(rows))

        for row in rows:
            frontier_id = str(row[0])
            source_id = str(row[1]) if row[1] else None
            base_url = row[2]
            domain = row[3] or urlparse(base_url).netloc.replace("www.", "")

            log.info("\n--- Scouting Base URL: %s (%s) ---", base_url, domain)

            # 1. Fetch & parse robots.txt using robust utils.robots
            can_crawl = is_url_allowed(base_url, KHUJO_UA)
            log.info("  robots.txt check for %s: allowed=%s", base_url, can_crawl)

            if not can_crawl:
                with engine.begin() as update_conn:
                    update_conn.execute(text("""
                        UPDATE crawl.frontier_url 
                        SET state = 'blocked', last_fetch_at = now()
                        WHERE frontier_url_id = :fid
                    """), {"fid": frontier_id})
                log.warning("  Crawl blocked by robots.txt for %s. Skipping.", base_url)
                continue


            # 2. Fetch Favicon to R2 if source_id exists
            if source_id:
                try:
                    r2_favicon = fetch_and_upload_favicon(base_url)
                    if r2_favicon:
                        with engine.begin() as r2_conn:
                            r2_conn.execute(text("""
                                INSERT INTO media.asset (media_kind, object_url, original_url, state)
                                VALUES ('image', :cdn, :orig, 'verified')
                                ON CONFLICT DO NOTHING
                            """), {"cdn": r2_favicon, "orig": base_url})
                        log.info("  Favicon verified on R2: %s", r2_favicon)
                except Exception as e:
                    log.warning("  Favicon upload failed: %s", e)

            # 3. Fetch homepage HTML to extract base metadata & discover internal article links
            discovered_links = set()
            try:
                resp = requests.get(base_url, headers=HEADERS, timeout=12, allow_redirects=True)
                if resp.status_code == 200:
                    soup = BeautifulSoup(resp.content, "html.parser")
                    
                    # Extract Base Homepage Title & Description for Admin Vault Staging
                    page_title = domain
                    title_tag = soup.find("meta", property="og:title") or soup.find("title")
                    if title_tag:
                        t_text = title_tag.get("content") or title_tag.get_text()
                        if t_text and len(t_text.strip()) > 2:
                            page_title = t_text.strip().replace("\n", " ")

                    page_desc = f"{domain} base website homepage"
                    desc_tag = soup.find("meta", property="og:description") or soup.find("meta", attrs={"name": "description"})
                    if desc_tag and desc_tag.get("content"):
                        page_desc = desc_tag.get("content").strip()

                    # Stage Base Homepage in content.document as candidate if not exists
                    if source_id:
                        with engine.begin() as base_doc_conn:
                            srid = base_doc_conn.execute(text("""
                                SELECT source_record_id FROM core.source_record WHERE canonical_url = :url LIMIT 1
                            """), {"url": base_url}).scalar()

                            if not srid:
                                srid = base_doc_conn.execute(text("""
                                    INSERT INTO core.source_record (source_id, canonical_url, title, state)
                                    VALUES (:sid, :url, :title, 'candidate')
                                    RETURNING source_record_id
                                """), {"sid": source_id, "url": base_url, "title": page_title[:250]}).scalar()

                            doc_exists = base_doc_conn.execute(text("""
                                SELECT 1 FROM content.document WHERE canonical_url = :url OR source_record_id = :srid LIMIT 1
                            """), {"url": base_url, "srid": srid}).scalar()

                            if not doc_exists:
                                content_hash = hashlib.sha256(f"{domain} base homepage {base_url}".encode("utf-8")).hexdigest()
                                base_doc_conn.execute(text("""
                                    INSERT INTO content.document (
                                        source_record_id, canonical_url, title, title_normalised, summary,
                                        body_text, body_normalised, language_code, content_hash, state, document_kind
                                    )
                                    VALUES (
                                        :srid, :url, :title, lower(:title), :desc,
                                        :body, lower(:body), 'bn', :hash, 'candidate', 'listing'
                                    )
                                """), {
                                    "srid": srid, "url": base_url, "title": page_title[:250],
                                    "desc": page_desc[:500], "body": f"{page_title} - {page_desc} {base_url}",
                                    "hash": content_hash
                                })
                                log.info("  ✓ Staged Base Homepage Candidate in Admin Queue: %s", base_url)

                    # Discover internal links
                    for a_tag in soup.find_all("a", href=True):
                        full_url = urljoin(base_url, a_tag["href"]).split("#")[0].strip()
                        if is_valid_article_url(full_url, domain):
                            discovered_links.add(full_url)

                    log.info("  Discovered %d internal candidate article links on homepage.", len(discovered_links))
            except Exception as e:
                log.error("  Homepage fetch failed for %s: %s", base_url, e)



            # 4. Queue discovered links into crawl.frontier_url (priority=5, state='queued')
            queued_count = 0
            with engine.begin() as queue_conn:
                for link in list(discovered_links)[:30]:  # Limit top 30 per base URL scout
                    link_hash = compute_url_hash(link)
                    
                    exists = queue_conn.execute(text("""
                        SELECT 1 FROM crawl.frontier_url WHERE canonical_url = :url OR url_hash = :hash LIMIT 1
                    """), {"url": link, "hash": link_hash}).scalar()

                    if not exists:
                        queue_conn.execute(text("""
                            INSERT INTO crawl.frontier_url (source_id, canonical_url, original_url, host, url_hash, priority, state)
                            VALUES (:sid, :url, :url, :domain, :hash, 5, 'queued')
                        """), {"sid": source_id, "url": link, "domain": domain, "hash": link_hash})
                        queued_count += 1

                # Mark base URL as fetched
                queue_conn.execute(text("""
                    UPDATE crawl.frontier_url 
                    SET state = 'fetched', last_fetch_at = now(), last_status_code = 200
                    WHERE frontier_url_id = :fid
                """), {"fid": frontier_id})

            log.info("  Queued %d new article URLs into frontier queue.", queued_count)

def name_or_url(url: str) -> str:
    return urlparse(url).netloc or url

if __name__ == "__main__":
    scout_base_urls()
