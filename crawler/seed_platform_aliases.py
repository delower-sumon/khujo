"""
Khujo Seeder — Seed Bangla & English Platform Aliases (seed_platform_aliases.py)
Seeds Bangla & English names for all 13 Base Entities into core.entity_name and search.suggestion
so searching "গুগল", "ফেসবুক", "ইউটিউব", "উইকিপিডিয়া" returns exact entity matches and verified documents!
"""

import os
import logging
from sqlalchemy import text
from utils.db import get_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("seed_aliases")

aliases = [
    ("google.com", [("গুগল", "bangla"), ("Google", "latin"), ("google", "latin")]),
    ("facebook.com", [("ফেসবুক", "bangla"), ("Facebook", "latin"), ("facebook", "latin")]),
    ("youtube.com", [("ইউটিউব", "bangla"), ("YouTube", "latin"), ("youtube", "latin")]),
    ("instagram.com", [("ইনস্টাগ্রাম", "bangla"), ("Instagram", "latin"), ("instagram", "latin")]),
    ("linkedin.com", [("লিংকডইন", "bangla"), ("LinkedIn", "latin"), ("linkedin", "latin")]),
    ("prothomalo.com", [("প্রথম আলো", "bangla"), ("Prothom Alo", "latin"), ("prothomalo", "latin")]),
    ("thedailystar.net", [("ডেইলি স্টার", "bangla"), ("The Daily Star", "latin"), ("dailystar", "latin")]),
    ("dhakatribune.com", [("ঢাকা ট্রিব্রিউন", "bangla"), ("Dhaka Tribune", "latin"), ("dhakatribune", "latin")]),
    ("bonikbarta.com", [("বণিক বার্তা", "bangla"), ("Bonik Barta", "latin"), ("bonikbarta", "latin")]),
    ("kalerkantho.com", [("কালের কণ্ঠ", "bangla"), ("Kaler Kantho", "latin"), ("kalerkantho", "latin")]),
    ("jugantor.com", [("যুগান্তর", "bangla"), ("Jugantor", "latin"), ("jugantor", "latin")]),
    ("bn.wikipedia.org", [("উইকিপিডিয়া", "bangla"), ("বাংলা উইকিপিডিয়া", "bangla"), ("Wikipedia", "latin")]),
    ("parliament.gov.bd", [("জাতীয় সংসদ", "bangla"), ("বাংলাদেশ সংসদ", "bangla"), ("Parliament", "latin")])
]

def run():
    engine = get_engine()
    with engine.begin() as conn:
        org_type_id = conn.execute(text("SELECT entity_type_id FROM core.entity_type WHERE slug = 'organization' LIMIT 1")).scalar()

        for domain, names in aliases:
            src = conn.execute(text("SELECT source_id, source_name FROM core.source WHERE canonical_domain = :domain"), {"domain": domain}).fetchone()
            if src:
                source_id, source_name = src
                entity_id = conn.execute(text("SELECT entity_id FROM core.entity WHERE display_name = :name LIMIT 1"), {"name": source_name}).scalar()
                
                if not entity_id:
                    entity_id = conn.execute(text("""
                        INSERT INTO core.entity (entity_type_id, display_name, summary, state)
                        VALUES (:tid, :name, :summary, 'verified')
                        RETURNING entity_id
                    """), {"tid": org_type_id, "name": source_name, "summary": f"{source_name} base platform"}).scalar()
                    
                    conn.execute(text("UPDATE core.source SET entity_id = :eid WHERE source_id = :sid"), {"eid": entity_id, "sid": source_id})

                for name, script in names:
                    conn.execute(text("""
                        INSERT INTO core.entity_name (entity_id, name, normalised_name, language_code, script, name_kind, is_primary, state)
                        VALUES (:eid, :name, lower(:name), CASE WHEN :script = 'bangla' THEN 'bn' ELSE 'en' END, :script, 'preferred', false, 'verified')
                        ON CONFLICT DO NOTHING
                    """), {"eid": entity_id, "name": name, "script": script})

                    conn.execute(text("""
                        INSERT INTO search.suggestion (phrase, phrase_normalised, language_code, priority, popularity_score)
                        VALUES (:phrase, lower(:phrase), CASE WHEN :script = 'bangla' THEN 'bn' ELSE 'en' END, 100, 100)
                        ON CONFLICT DO NOTHING
                    """), {"phrase": name, "script": script})

                log.info("  ✓ Linked entity & Bangla/English names for %s (%s)", source_name, domain)

    log.info("Successfully seeded all platform aliases!")

if __name__ == "__main__":
    run()
