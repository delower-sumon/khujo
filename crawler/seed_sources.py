"""
KhujoBot v1 — Phase 0: Base URLs & Platform Sources Seeder (seed_sources.py)
Seeds major web platforms (Google, FB, YT, Insta, LinkedIn) and news publishers
into core.entity, core.source, media.asset (via R2 favicons), and crawl.frontier_url.
"""

import os
import hashlib
import logging
from sqlalchemy import text
from utils.db import get_engine
from utils.r2 import fetch_and_upload_favicon

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("seed_sources")

BASE_SOURCES = [
    # Major Web Platforms
    {
        "name": "Google",
        "domain": "google.com",
        "url": "https://www.google.com/",
        "kind": "business",
        "trust_tier": 5,
        "summary": "গুগল বিশ্বের সর্ববৃহৎ মার্কিন প্রযুক্তি কোম্পানি ও ইন্টারনেট অনুসন্ধান ইঞ্জিন।"
    },
    {
        "name": "Facebook",
        "domain": "facebook.com",
        "url": "https://www.facebook.com/",
        "kind": "community",
        "trust_tier": 4,
        "summary": "ফেসবুক মেটা প্ল্যাটফর্মসের জনপ্রিয় সামাজিক যোগাযোগ মাধ্যম।"
    },
    {
        "name": "YouTube",
        "domain": "youtube.com",
        "url": "https://www.youtube.com/",
        "kind": "community",
        "trust_tier": 4,
        "summary": "ইউটিউব অনলাইন ভিডিও শেয়ারিং প্ল্যাটফর্ম ও সার্চ সেবা।"
    },
    {
        "name": "Instagram",
        "domain": "instagram.com",
        "url": "https://www.instagram.com/",
        "kind": "community",
        "trust_tier": 3,
        "summary": "ইনস্টাগ্রাম ছবি ও ভিডিও শেয়ারিং সামাজিক নেটওয়ার্ক।"
    },
    {
        "name": "LinkedIn",
        "domain": "linkedin.com",
        "url": "https://www.linkedin.com/",
        "kind": "business",
        "trust_tier": 4,
        "summary": "লিঙ্কডইন পেশাদার ও ব্যবসা ভিত্তিক সংযোগ এবং জব প্ল্যাটফর্ম।"
    },

    # Major News & Knowledge Publishers
    {
        "name": "Prothom Alo",
        "domain": "prothomalo.com",
        "url": "https://www.prothomalo.com/",
        "kind": "publisher",
        "trust_tier": 4,
        "summary": "প্রথম আলো বাংলাদেশের অন্যতম শীর্ষ দৈনিক বাংলা সংবাদপত্র।"
    },
    {
        "name": "The Daily Star",
        "domain": "thedailystar.net",
        "url": "https://www.thedailystar.net/",
        "kind": "publisher",
        "trust_tier": 4,
        "summary": "দ্য ডেইলি স্টার বাংলাদেশের বৃহত্তম ইংরেজি দৈনিক সংবাদপত্র।"
    },
    {
        "name": "Dhaka Tribune",
        "domain": "dhakatribune.com",
        "url": "https://www.dhakatribune.com/",
        "kind": "publisher",
        "trust_tier": 4,
        "summary": "ঢাকা ট্রিবিউন বাংলাদেশের অন্যতম প্রধান জাতীয় ইংরেজি পত্রিকা।"
    },
    {
        "name": "Bonik Barta",
        "domain": "bonikbarta.com",
        "url": "https://bonikbarta.com/",
        "kind": "publisher",
        "trust_tier": 3,
        "summary": "বণিক বার্তা বাংলাদেশের প্রথম দৈনিক অর্থনৈতিক সংবাদপত্র।"
    },
    {
        "name": "Kaler Kantho",
        "domain": "kalerkantho.com",
        "url": "https://www.kalerkantho.com/",
        "kind": "publisher",
        "trust_tier": 3,
        "summary": "কালের কণ্ঠ বাংলাদেশের জনপ্রিয় একটি দৈনিক বাংলা সংবাদপত্র।"
    },
    {
        "name": "Jugantor",
        "domain": "jugantor.com",
        "url": "https://www.jugantor.com/",
        "kind": "publisher",
        "trust_tier": 3,
        "summary": "দৈনিক যুগান্তর বাংলাদেশের বহুল প্রচারিত সংবাদপত্র।"
    },
    {
        "name": "Bengali Wikipedia",
        "domain": "bn.wikipedia.org",
        "url": "https://bn.wikipedia.org/",
        "kind": "institution",
        "trust_tier": 5,
        "summary": "বাংলা উইকিপিডিয়া মুক্ত বিশ্বকোষের বাংলা ভাষার মুক্ত সংস্করণ।"
    },
    {
        "name": "Bangladesh Parliament",
        "domain": "parliament.gov.bd",
        "url": "http://www.parliament.gov.bd/",
        "kind": "government",
        "trust_tier": 5,
        "summary": "জাতীয় সংসদ ভবন ও বাংলাদেশের এক কক্ষবিশিষ্ট আইনসভা।"
    }
]

def compute_url_hash(url: str) -> str:
    return hashlib.md5(url.strip().lower().encode("utf-8")).hexdigest()[:32]

def seed_sources():
    engine = get_engine()

    with engine.begin() as conn:
        org_type_id = conn.execute(text("""
            SELECT entity_type_id FROM core.entity_type WHERE slug = 'organization' LIMIT 1
        """)).scalar()

        if not org_type_id:
            log.error("entity_type with slug 'organization' not found!")
            return

        log.info("Using entity_type_id: %s for organization", org_type_id)

        seeded_sources = 0

        for src in BASE_SOURCES:
            name = src["name"]
            domain = src["domain"]
            url = src["url"]
            kind = src["kind"]
            trust_tier = src["trust_tier"]
            summary = src["summary"]
            url_hash = compute_url_hash(url)

            log.info("Seeding source: %s (%s)...", name, domain)

            # Check or create entity
            entity_id = conn.execute(text("""
                SELECT e.entity_id FROM core.entity e
                JOIN core.entity_name n ON e.entity_id = n.entity_id
                WHERE n.normalised_name = lower(:name)
                LIMIT 1
            """), {"name": name}).scalar()

            if not entity_id:
                entity_id = conn.execute(text("""
                    INSERT INTO core.entity (entity_type_id, display_name, summary, preferred_language_code, state)
                    VALUES (:etid, :name, :summary, 'en', 'verified')
                    RETURNING entity_id
                """), {"etid": org_type_id, "name": name, "summary": summary}).scalar()

                # Names
                conn.execute(text("""
                    INSERT INTO core.entity_name (entity_id, language_code, script, name_kind, name, normalised_name, is_primary, state)
                    VALUES (:eid, 'en', 'latin', 'official', :name, lower(:name), true, 'verified')
                    ON CONFLICT DO NOTHING
                """), {"eid": entity_id, "name": name})

            # Check or create source
            source_id = conn.execute(text("""
                SELECT source_id FROM core.source WHERE canonical_domain = :domain LIMIT 1
            """), {"domain": domain}).scalar()

            if not source_id:
                source_id = conn.execute(text("""
                    INSERT INTO core.source (source_name, source_kind, canonical_domain, homepage_url, trust_tier, is_active)
                    VALUES (:name, :kind, :domain, :url, :tier, true)
                    RETURNING source_id
                """), {"name": name, "kind": kind, "domain": domain, "url": url, "tier": trust_tier}).scalar()

            # Upload Favicon to Cloudflare R2
            try:
                r2_favicon_url = fetch_and_upload_favicon(url)
                if r2_favicon_url:
                    log.info("  Favicon uploaded to R2: %s", r2_favicon_url)

                    # Store in media.asset
                    conn.execute(text("""
                        INSERT INTO media.asset (media_kind, object_url, original_url, state)
                        VALUES ('image', :cdn, :orig, 'verified')
                        ON CONFLICT DO NOTHING
                    """), {"cdn": r2_favicon_url, "orig": url})
            except Exception as e:
                log.warning("  Could not fetch/upload favicon for %s: %s", domain, e)

            # Queue Base URL in crawl.frontier_url
            exists_in_frontier = conn.execute(text("""
                SELECT 1 FROM crawl.frontier_url WHERE canonical_url = :url LIMIT 1
            """), {"url": url}).scalar()

            if not exists_in_frontier:
                conn.execute(text("""
                    INSERT INTO crawl.frontier_url (source_id, canonical_url, original_url, host, url_hash, priority, state)
                    VALUES (:sid, :url, :url, :domain, :hash, 10, 'queued')
                """), {"sid": source_id, "url": url, "domain": domain, "hash": url_hash})
                log.info("  Queued base URL in frontier queue: %s", url)

            seeded_sources += 1

        log.info("\nBase Sources & Platforms Seeding Complete: %d sources seeded.", seeded_sources)

if __name__ == "__main__":
    seed_sources()
