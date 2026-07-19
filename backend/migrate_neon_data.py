import os
import json
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not set in .env")

engine = create_engine(DATABASE_URL)

def migrate_data():
    with engine.connect() as conn:
        with conn.begin():
            print("Migrating transliteration_map to search.suggestion...")
            if os.path.exists("legacy_transliteration.json"):
                with open("legacy_transliteration.json", "r") as f:
                    legacy_trans = json.load(f)
                
                for t in legacy_trans:
                    if t.get('bangla'):
                        conn.execute(text("""
                            INSERT INTO search.suggestion (phrase, phrase_normalised, language_code, source_kind, priority)
                            VALUES (:bangla, :bangla, 'bn', 'curated', 2)
                            ON CONFLICT DO NOTHING;
                        """), {"bangla": t['bangla']})
                    if t.get('english'):
                        conn.execute(text("""
                            INSERT INTO search.suggestion (phrase, phrase_normalised, language_code, source_kind, priority)
                            VALUES (:english, :english, 'en', 'curated', 2)
                            ON CONFLICT DO NOTHING;
                        """), {"english": t['english']})
            
            print("Migrating autosuggestions to search.suggestion...")
            if os.path.exists("legacy_autosuggestions.json"):
                with open("legacy_autosuggestions.json", "r") as f:
                    legacy_auto = json.load(f)
                
                for a in legacy_auto:
                    if not a.get('phrase'): continue
                    conn.execute(text("""
                        INSERT INTO search.suggestion (phrase, phrase_normalised, language_code, intent, vertical, source_kind, priority, popularity_score)
                        VALUES (:phrase, :phrase, :lang, :intent, :vertical, :source_kind, :priority, :pop)
                        ON CONFLICT DO NOTHING;
                    """), {
                        "phrase": a['phrase'],
                        "lang": a.get('language_code') or 'bn',
                        "intent": a.get('intent'),
                        "vertical": a.get('category'),
                        "source_kind": a.get('source_type') or 'curated',
                        "priority": a.get('priority_level') or 1,
                        "pop": a.get('search_volume_weight') or 0
                    })

            print("Extracting document URLs to crawl.frontier_url...")
            # Needs a source to associate with. Create a dummy source first for legacy import.
            source_id = conn.execute(text("SELECT source_id FROM core.source WHERE canonical_domain = 'legacy.khujo.com.bd'")).scalar()
            if not source_id:
                source_id = conn.execute(text("""
                    INSERT INTO core.source (source_name, source_kind, canonical_domain, access_method)
                    VALUES ('Legacy Import', 'other', 'legacy.khujo.com.bd', 'api')
                    RETURNING source_id;
                """)).scalar()

            with open("legacy_urls.json", "r") as f:
                legacy_urls = json.load(f)
            
            for url in legacy_urls:
                conn.execute(text(f"""
                    INSERT INTO crawl.frontier_url (source_id, host, original_url, canonical_url, url_hash, state)
                    SELECT '{source_id}', split_part(split_part(:url, '://', 2), '/', 1), :url, :url, encode(digest(:url, 'sha256'), 'hex'), 'queued'
                    ON CONFLICT (canonical_url) DO NOTHING;
                """), {"url": url})

            print("Seeding core geographic entities...")
            # Need to get entity_type_id for 'administrative_area'
            admin_type_id = conn.execute(text("SELECT entity_type_id FROM core.entity_type WHERE slug = 'administrative_area'")).scalar()
            if admin_type_id:
                districts = [
                    ('ঢাকা', 'bn'), ('Dhaka', 'en'),
                    ('চট্টগ্রাম', 'bn'), ('Chattogram', 'en'),
                    ('সিলেট', 'bn'), ('Sylhet', 'en'),
                    ('খুলনা', 'bn'), ('Khulna', 'en'),
                    ('বরিশাল', 'bn'), ('Barishal', 'en'),
                    ('রাজশাহী', 'bn'), ('Rajshahi', 'en'),
                    ('রংপুর', 'bn'), ('Rangpur', 'en'),
                    ('ময়মনসিংহ', 'bn'), ('Mymensingh', 'en')
                ]
                for name, lang in districts:
                    # Insert entity
                    entity_id = conn.execute(text(f"""
                        INSERT INTO core.entity (entity_type_id, display_name, preferred_language_code, state, visibility)
                        VALUES ({admin_type_id}, :name, :lang, 'verified', 'public')
                        RETURNING entity_id;
                    """), {"name": name, "lang": lang}).scalar()
                    
                    # Insert entity_name
                    conn.execute(text(f"""
                        INSERT INTO core.entity_name (entity_id, name, normalised_name, language_code, script, name_kind, is_primary)
                        VALUES (:eid, :name, :name, :lang, 'bangla', 'preferred', TRUE)
                    """), {"eid": entity_id, "name": name, "lang": lang})
                    
                    # Also insert as a suggestion
                    conn.execute(text(f"""
                        INSERT INTO search.suggestion (phrase, phrase_normalised, language_code, entity_id, source_kind, priority)
                        VALUES (:name, :name, :lang, :eid, 'curated', 10)
                        ON CONFLICT DO NOTHING;
                    """), {"name": name, "lang": lang, "eid": entity_id})

    print("Migration and seeding complete.")

if __name__ == "__main__":
    migrate_data()
