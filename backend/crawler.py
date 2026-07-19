import os
import hashlib
from datetime import datetime
import urllib.request
from html.parser import HTMLParser
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import time

class SimpleHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []
        self.links = []
        self.title = ""
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        if tag == "title":
            self.in_title = True
        elif tag == "a":
            self.links.append("") # placeholder for anchor text

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        self.text.append(data)
        if self.links:
            self.links[-1] += data

def extract_content(html):
    parser = SimpleHTMLParser()
    parser.feed(html)
    return parser.title, ' '.join(parser.text), [l for l in parser.links if 3 < len(l.strip()) < 60]

from dotenv import load_dotenv
import time

load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL"))

HEADERS = {
    'User-Agent': 'Khujobot/0.1 (+https://khujo.com.bd/bot)'
}

def crawl_frontier():
    with engine.connect() as conn:
        # Fetch up to 10 pending URLs
        result = conn.execute(text("""
            SELECT frontier_url_id, canonical_url, source_id
            FROM crawl.frontier_url
            WHERE state = 'queued'
            LIMIT 10
        """)).fetchall()

        if not result:
            print("No URLs in frontier queue.")
            return

        for row in result:
            frontier_id = row[0]
            url = row[1]
            source_id = row[2]
            
            print(f"Fetching {url}...")
            
            # Start fetch
            fetch_id = conn.execute(text("""
                INSERT INTO crawl.fetch (frontier_url_id, state)
                VALUES (:fid, 'success')
                RETURNING fetch_id;
            """), {"fid": frontier_id}).scalar()
            
            try:
                req = urllib.request.Request(url, headers=HEADERS)
                with urllib.request.urlopen(req, timeout=10) as response:
                    html = response.read().decode('utf-8', errors='ignore')
                    status_code = response.getcode()
                
                title, body_text, anchor_links = extract_content(html)
                content_hash = hashlib.sha256(body_text.encode('utf-8')).hexdigest()
                
                # Update fetch record
                conn.execute(text("""
                    UPDATE crawl.fetch 
                    SET http_status = :status, content_hash = :hash, finished_at = now()
                    WHERE fetch_id = :fid
                """), {"status": status_code, "hash": content_hash, "fid": fetch_id})
                
                # Check for existing document hash
                exists = conn.execute(text("SELECT 1 FROM content.document WHERE content_hash = :hash"), {"hash": content_hash}).scalar()
                
                if not exists:
                    # Ensure source_record_id exists
                    source_record_id = conn.execute(text("SELECT source_record_id FROM core.source_record WHERE canonical_url = :url LIMIT 1"), {"url": url}).scalar()
                    if not source_record_id:
                        source_record_id = conn.execute(text("""
                            INSERT INTO core.source_record (source_id, canonical_url, title, state)
                            VALUES (:sid, :url, :title, 'candidate')
                            RETURNING source_record_id;
                        """), {"sid": source_id, "url": url, "title": title[:200]}).scalar()

                    # Insert document
                    conn.execute(text("""
                        INSERT INTO content.document (document_kind, source_record_id, fetch_id, canonical_url, title, title_normalised, body_text, body_normalised, language_code, content_hash)
                        VALUES ('news', :srid, :fid, :url, :title, :title, :body, :body, 'bn', :hash)
                        ON CONFLICT DO NOTHING;
                    """), {"url": url, "srid": source_record_id, "fid": fetch_id, "title": title[:200], "body": body_text[:5000], "hash": content_hash})
                
                # Harvest suggestions (Anchor tags)
                for sugg in set(anchor_links):
                    conn.execute(text("""
                        INSERT INTO search.suggestion (phrase, phrase_normalised, language_code, source_kind, priority, state)
                        VALUES (:phrase, :phrase, 'bn', 'crawler', 1, 'candidate')
                        ON CONFLICT DO NOTHING;
                    """), {"phrase": sugg.strip()})
                
                # Update frontier status
                conn.execute(text("""
                    UPDATE crawl.frontier_url
                    SET state = 'fetched', last_fetch_at = now(), last_status_code = :status
                    WHERE frontier_url_id = :fid
                """), {"status": status_code, "fid": frontier_id})
                
                print(f"Successfully crawled {url}")
            except Exception as e:
                print(f"Failed to crawl {url}")
                conn.execute(text("""
                    UPDATE crawl.fetch 
                    SET state = 'http_error', error_detail = :err, finished_at = now()
                    WHERE fetch_id = :fid
                """), {"err": str(e), "fid": fetch_id})
                
                conn.execute(text("""
                    UPDATE crawl.frontier_url
                    SET state = 'failed', failure_count = failure_count + 1
                    WHERE frontier_url_id = :fid
                """), {"fid": frontier_id})
            
            # Commit after each URL to avoid long transactions
            conn.commit()
            time.sleep(1) # Be polite

if __name__ == "__main__":
    crawl_frontier()
