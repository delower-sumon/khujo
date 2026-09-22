"""
Khujo Database Ingestion Script
Ingests:
1. 194 Universities from universities_enriched_full.csv
2. 48 Political Parties from political_parties_with_news.csv
3. 188 Political Party News Articles from political_parties_news_docs.json
4. Registers entity types ('university', 'political_party')
5. Populates core.entity, core.entity_name, core.entity_identifier, core.place, search.suggestion
6. Populates content.document for news and updates search.document_index via crawler.indexer
"""

import os
import sys
import json
import re
import csv
import logging
import hashlib
from typing import List, Dict, Any, Optional

# Reconfigure stdout for UTF-8
sys.stdout.reconfigure(encoding='utf-8')

# Ensure repo root is in python path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from crawler.utils.db import get_engine
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("ingest_specialized")

RAW_DIR = os.path.join(os.path.dirname(__file__), "data", "raw", "enriched")
UNIS_CSV = os.path.join(RAW_DIR, "universities_enriched_full.csv")
PARTIES_CSV = os.path.join(RAW_DIR, "political_parties_with_news.csv")
NEWS_JSON = os.path.join(RAW_DIR, "political_parties_news_docs.json")

def parse_acronym(acronym_str: str):
    """
    Parses acronym string like 'ঢাবি (DU)' or 'BUET' into Bangla and English tokens.
    """
    if not acronym_str:
        return [], []
    bn_tokens = []
    en_tokens = []
    # Match bangla words
    bn_matches = re.findall(r'[\u0980-\u09FF]+', acronym_str)
    # Match english words
    en_matches = re.findall(r'[A-Za-z0-9]+', acronym_str)
    for b in bn_matches:
        if len(b) >= 2:
            bn_tokens.append(b.strip())
    for e in en_matches:
        if len(e) >= 2:
            en_tokens.append(e.strip())
    return bn_tokens, en_tokens

def generate_university_aliases(name_bn: str, name_en: str):
    """
    Generates common alias variations.
    e.g. 'University of Dhaka' -> 'Dhaka University'
    """
    aliases = []
    if name_en:
        if name_en.startswith("University of "):
            city_part = name_en.replace("University of ", "").strip()
            aliases.append((f"{city_part} University", "en", "latin", "alias"))
        elif " University" in name_en:
            city_part = name_en.replace(" University", "").strip()
            aliases.append((f"University of {city_part}", "en", "latin", "alias"))
            
    return aliases

def generate_party_aliases(name_bn: str, name_en: str, acronym: str):
    """
    Generates popular aliases for political parties.
    """
    aliases = []
    # Strip 'বাংলাদেশ' prefix for conversational queries
    if name_bn.startswith("বাংলাদেশ "):
        short_bn = name_bn.replace("বাংলাদেশ ", "").strip()
        aliases.append((short_bn, "bn", "bangla", "alias"))
    if name_en.startswith("Bangladesh "):
        short_en = name_en.replace("Bangladesh ", "").strip()
        aliases.append((short_en, "en", "latin", "alias"))
        
    # Popular known shorthands
    if "আওয়ামী লীগ" in name_bn:
        aliases.append(("আওয়ামী লীগ", "bn", "bangla", "alias"))
        aliases.append(("Awami League", "en", "latin", "alias"))
    if "জাতীয়তাবাদী দল" in name_bn or "বিএনপি" in acronym:
        aliases.append(("বিএনপি", "bn", "bangla", "abbreviation"))
        aliases.append(("BNP", "en", "latin", "abbreviation"))
        aliases.append(("জাতীয়তাবাদী দল", "bn", "bangla", "alias"))
    if "জাতীয় পার্টি" in name_bn:
        aliases.append(("জাতীয় পার্টি", "bn", "bangla", "alias"))
        aliases.append(("Jatiya Party", "en", "latin", "alias"))
    if "জামায়াত" in name_bn:
        aliases.append(("জামায়াত", "bn", "bangla", "alias"))
        aliases.append(("জামায়াতে ইসলামী", "bn", "bangla", "alias"))
        aliases.append(("Jamaat-e-Islami", "en", "latin", "alias"))
        aliases.append(("Jamaat", "en", "latin", "alias"))
        
    return aliases

def run_ingestion():
    engine = get_engine()
    
    with engine.begin() as conn:
        log.info("--- Step 1: Ensure Entity Types ---")
        # Ensure 'university' (parent 12: education_institution)
        conn.execute(text("""
            INSERT INTO core.entity_type (slug, label_en, label_bn, parent_entity_type_id, is_abstract, description)
            VALUES ('university', 'University', 'বিশ্ববিদ্যালয়', 12, FALSE, 'Higher education and degree granting university')
            ON CONFLICT (slug) DO UPDATE SET label_bn = EXCLUDED.label_bn;
        """))
        uni_type_id = conn.execute(text("SELECT entity_type_id FROM core.entity_type WHERE slug = 'university';")).scalar()
        
        # Ensure 'political_party' (parent 10: organization)
        conn.execute(text("""
            INSERT INTO core.entity_type (slug, label_en, label_bn, parent_entity_type_id, is_abstract, description)
            VALUES ('political_party', 'Political Party', 'রাজনৈতিক দল', 10, FALSE, 'Registered political party or political movement')
            ON CONFLICT (slug) DO UPDATE SET label_bn = EXCLUDED.label_bn;
        """))
        party_type_id = conn.execute(text("SELECT entity_type_id FROM core.entity_type WHERE slug = 'political_party';")).scalar()
        log.info("Entity Types verified: university=%s, political_party=%s", uni_type_id, party_type_id)

        log.info("--- Step 2: Ingest Universities ---")
        if not os.path.exists(UNIS_CSV):
            raise FileNotFoundError(f"Universities file not found: {UNIS_CSV}")
            
        with open(UNIS_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            uni_count = 0
            for row in reader:
                name_bn = row.get("name_bn", "").strip()
                name_en = row.get("name_en", "").strip()
                acronym = row.get("acronym", "").strip()
                summary_bn = row.get("summary_bn", "").strip()
                official_website = row.get("official_website", "").strip()
                images_json_str = row.get("images_json", "[]").strip()
                sitelinks_json_str = row.get("sitelinks_json", "[]").strip()
                lat_str = row.get("latitude", "").strip()
                lon_str = row.get("longitude", "").strip()
                
                if not name_bn:
                    continue
                    
                images = []
                try:
                    images = json.loads(images_json_str) if images_json_str else []
                except Exception:
                    images = []
                    
                sitelinks = []
                try:
                    sitelinks = json.loads(sitelinks_json_str) if sitelinks_json_str else []
                except Exception:
                    sitelinks = []
                    
                primary_image = images[0] if images else None
                
                lat = float(lat_str) if lat_str and lat_str != "None" else None
                lon = float(lon_str) if lon_str and lon_str != "None" else None
                
                # Facts dict for Knowledge Panel
                facts = {
                    "ধরন": "বিশ্ববিদ্যালয়",
                    "ওয়েবসাইট": official_website or "তথ্য নেই",
                    "সংক্ষিপ্ত রূপ": acronym or "তথ্য নেই"
                }
                if lat and lon:
                    facts["স্থানাঙ্ক"] = f"{lat:.4f}, {lon:.4f}"
                    
                meta = {
                    "image_url": primary_image,
                    "images": images,
                    "facts": facts,
                    "official_website": official_website,
                    "sitelinks": sitelinks,
                    "latitude": lat,
                    "longitude": lon,
                    "category": "Universities"
                }
                
                # Check if entity already exists by display_name or primary English name
                entity_id = conn.execute(text("""
                    SELECT entity_id FROM core.entity WHERE display_name = :name LIMIT 1
                """), {"name": name_bn}).scalar()
                
                if not entity_id:
                    entity_id = conn.execute(text("""
                        INSERT INTO core.entity (entity_type_id, display_name, preferred_language_code, state, visibility, summary, metadata)
                        VALUES (:tid, :name, 'bn', 'verified', 'public', :summary, CAST(:meta AS jsonb))
                        RETURNING entity_id
                    """), {
                        "tid": uni_type_id,
                        "name": name_bn,
                        "summary": summary_bn,
                        "meta": json.dumps(meta, ensure_ascii=False)
                    }).scalar()
                else:
                    conn.execute(text("""
                        UPDATE core.entity
                        SET entity_type_id = :tid,
                            summary = :summary,
                            metadata = CAST(:meta AS jsonb),
                            state = 'verified',
                            visibility = 'public',
                            updated_at = now()
                        WHERE entity_id = :eid
                    """), {
                        "tid": uni_type_id,
                        "summary": summary_bn,
                        "meta": json.dumps(meta, ensure_ascii=False),
                        "eid": entity_id
                    })
                    
                # Names insertion
                # 1. Primary Bangla Name
                conn.execute(text("""
                    INSERT INTO core.entity_name (entity_id, language_code, script, name_kind, name, normalised_name, is_primary, state)
                    VALUES (:eid, 'bn', 'bangla', 'preferred', :name, lower(:name), TRUE, 'verified')
                    ON CONFLICT (entity_id, normalised_name, language_code, name_kind) 
                    DO UPDATE SET is_primary = TRUE, state = 'verified';
                """), {"eid": entity_id, "name": name_bn})
                
                # 2. Primary English Name
                if name_en:
                    conn.execute(text("""
                        INSERT INTO core.entity_name (entity_id, language_code, script, name_kind, name, normalised_name, is_primary, state)
                        VALUES (:eid, 'en', 'latin', 'official', :name, lower(:name), TRUE, 'verified')
                        ON CONFLICT (entity_id, normalised_name, language_code, name_kind)
                        DO UPDATE SET is_primary = TRUE, state = 'verified';
                    """), {"eid": entity_id, "name": name_en})
                    
                # 3. Acronyms & aliases
                bn_acrs, en_acrs = parse_acronym(acronym)
                for bacr in bn_acrs:
                    conn.execute(text("""
                        INSERT INTO core.entity_name (entity_id, language_code, script, name_kind, name, normalised_name, is_primary, state)
                        VALUES (:eid, 'bn', 'bangla', 'abbreviation', :name, lower(:name), FALSE, 'verified')
                        ON CONFLICT (entity_id, normalised_name, language_code, name_kind) DO NOTHING;
                    """), {"eid": entity_id, "name": bacr})
                    
                for eacr in en_acrs:
                    conn.execute(text("""
                        INSERT INTO core.entity_name (entity_id, language_code, script, name_kind, name, normalised_name, is_primary, state)
                        VALUES (:eid, 'en', 'latin', 'abbreviation', :name, lower(:name), FALSE, 'verified')
                        ON CONFLICT (entity_id, normalised_name, language_code, name_kind) DO NOTHING;
                    """), {"eid": entity_id, "name": eacr})
                    
                # Generated Aliases
                gen_aliases = generate_university_aliases(name_bn, name_en)
                for aname, alang, ascript, akind in gen_aliases:
                    conn.execute(text("""
                        INSERT INTO core.entity_name (entity_id, language_code, script, name_kind, name, normalised_name, is_primary, state)
                        VALUES (:eid, :lang, :script, :kind, :name, lower(:name), FALSE, 'verified')
                        ON CONFLICT (entity_id, normalised_name, language_code, name_kind) DO NOTHING;
                    """), {"eid": entity_id, "lang": alang, "script": ascript, "kind": akind, "name": aname})
                    
                # Place coords
                if lat and lon:
                    conn.execute(text("""
                        INSERT INTO core.place (entity_id, latitude, longitude)
                        VALUES (:eid, :lat, :lon)
                        ON CONFLICT (entity_id) DO UPDATE SET latitude = EXCLUDED.latitude, longitude = EXCLUDED.longitude;
                    """), {"eid": entity_id, "lat": lat, "lon": lon})
                    
                # Official website identifier
                if official_website:
                    conn.execute(text("""
                        INSERT INTO core.entity_identifier (entity_id, identifier_scheme, identifier_value, state)
                        VALUES (:eid, 'url', :url, 'verified')
                        ON CONFLICT (identifier_scheme, identifier_value) DO NOTHING;
                    """), {"eid": entity_id, "url": official_website})
                    
                # Search Suggestions
                for term in [name_bn, name_en] + bn_acrs + en_acrs:
                    if term and len(term) >= 2:
                        conn.execute(text("""
                            INSERT INTO search.suggestion (phrase, phrase_normalised, language_code, priority, popularity_score)
                            VALUES (:p, lower(:p), CASE WHEN :p ~ '[\u0980-\u09FF]' THEN 'bn' ELSE 'en' END, 120, 100)
                            ON CONFLICT DO NOTHING;
                        """), {"p": term})
                        
                uni_count += 1
                
        log.info("✓ Successfully committed %d universities to core.entity & core.entity_name", uni_count)

        log.info("--- Step 3: Ingest Political Parties ---")
        if not os.path.exists(PARTIES_CSV):
            raise FileNotFoundError(f"Political parties file not found: {PARTIES_CSV}")
            
        with open(PARTIES_CSV, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            party_count = 0
            for row in reader:
                name_bn = row.get("name_bn", "").strip()
                name_en = row.get("name_en", "").strip()
                acronym = row.get("acronym", "").strip()
                founded_year = row.get("founded_year", "").strip()
                current_head_bn = row.get("current_head_bn", "").strip()
                ideology_summary_bn = row.get("ideology_summary_bn", "").strip()
                official_website = row.get("official_website", "").strip()
                images_json_str = row.get("images_json", "[]").strip()
                
                if not name_bn:
                    continue
                    
                images = []
                try:
                    images = json.loads(images_json_str) if images_json_str else []
                except Exception:
                    images = []
                    
                primary_image = images[0] if images else None
                
                facts = {
                    "ধরন": "রাজনৈতিক দল",
                    "প্রতিষ্ঠিত": founded_year or "তথ্য নেই",
                    "বর্তমান প্রধান": current_head_bn or "তথ্য নেই",
                    "ওয়েবসাইট": official_website or "তথ্য নেই",
                    "সংক্ষিপ্ত রূপ": acronym or "তথ্য নেই"
                }
                
                meta = {
                    "image_url": primary_image,
                    "images": images,
                    "facts": facts,
                    "official_website": official_website,
                    "founded_year": founded_year,
                    "current_head": current_head_bn,
                    "category": "Political Parties"
                }
                
                entity_id = conn.execute(text("""
                    SELECT entity_id FROM core.entity WHERE display_name = :name LIMIT 1
                """), {"name": name_bn}).scalar()
                
                if not entity_id:
                    entity_id = conn.execute(text("""
                        INSERT INTO core.entity (entity_type_id, display_name, preferred_language_code, state, visibility, summary, metadata)
                        VALUES (:tid, :name, 'bn', 'verified', 'public', :summary, CAST(:meta AS jsonb))
                        RETURNING entity_id
                    """), {
                        "tid": party_type_id,
                        "name": name_bn,
                        "summary": ideology_summary_bn,
                        "meta": json.dumps(meta, ensure_ascii=False)
                    }).scalar()
                else:
                    conn.execute(text("""
                        UPDATE core.entity
                        SET entity_type_id = :tid,
                            summary = :summary,
                            metadata = CAST(:meta AS jsonb),
                            state = 'verified',
                            visibility = 'public',
                            updated_at = now()
                        WHERE entity_id = :eid
                    """), {
                        "tid": party_type_id,
                        "summary": ideology_summary_bn,
                        "meta": json.dumps(meta, ensure_ascii=False),
                        "eid": entity_id
                    })
                    
                # Names insertion
                # 1. Primary Bangla Name
                conn.execute(text("""
                    INSERT INTO core.entity_name (entity_id, language_code, script, name_kind, name, normalised_name, is_primary, state)
                    VALUES (:eid, 'bn', 'bangla', 'preferred', :name, lower(:name), TRUE, 'verified')
                    ON CONFLICT (entity_id, normalised_name, language_code, name_kind)
                    DO UPDATE SET is_primary = TRUE, state = 'verified';
                """), {"eid": entity_id, "name": name_bn})
                
                # 2. Primary English Name
                if name_en:
                    conn.execute(text("""
                        INSERT INTO core.entity_name (entity_id, language_code, script, name_kind, name, normalised_name, is_primary, state)
                        VALUES (:eid, 'en', 'latin', 'official', :name, lower(:name), TRUE, 'verified')
                        ON CONFLICT (entity_id, normalised_name, language_code, name_kind)
                        DO UPDATE SET is_primary = TRUE, state = 'verified';
                    """), {"eid": entity_id, "name": name_en})
                    
                # 3. Acronym
                if acronym:
                    acronym_script = 'bangla' if re.search(r'[\u0980-\u09FF]', acronym) else 'latin'
                    acronym_lang = 'bn' if acronym_script == 'bangla' else 'en'
                    conn.execute(text("""
                        INSERT INTO core.entity_name (entity_id, language_code, script, name_kind, name, normalised_name, is_primary, state)
                        VALUES (:eid, :lang, :script, 'abbreviation', :name, lower(:name), FALSE, 'verified')
                        ON CONFLICT (entity_id, normalised_name, language_code, name_kind) DO NOTHING;
                    """), {"eid": entity_id, "lang": acronym_lang, "script": acronym_script, "name": acronym})
                    
                # 4. Aliases
                party_aliases = generate_party_aliases(name_bn, name_en, acronym)
                for aname, alang, ascript, akind in party_aliases:
                    conn.execute(text("""
                        INSERT INTO core.entity_name (entity_id, language_code, script, name_kind, name, normalised_name, is_primary, state)
                        VALUES (:eid, :lang, :script, :kind, :name, lower(:name), FALSE, 'verified')
                        ON CONFLICT (entity_id, normalised_name, language_code, name_kind) DO NOTHING;
                    """), {"eid": entity_id, "lang": alang, "script": ascript, "kind": akind, "name": aname})
                    
                # Official website identifier
                if official_website:
                    conn.execute(text("""
                        INSERT INTO core.entity_identifier (entity_id, identifier_scheme, identifier_value, state)
                        VALUES (:eid, 'url', :url, 'verified')
                        ON CONFLICT (identifier_scheme, identifier_value) DO NOTHING;
                    """), {"eid": entity_id, "url": official_website})
                    
                # Search Suggestions
                for term in [name_bn, name_en, acronym] + [a[0] for a in party_aliases]:
                    if term and len(term) >= 2:
                        conn.execute(text("""
                            INSERT INTO search.suggestion (phrase, phrase_normalised, language_code, priority, popularity_score)
                            VALUES (:p, lower(:p), CASE WHEN :p ~ '[\u0980-\u09FF]' THEN 'bn' ELSE 'en' END, 120, 100)
                            ON CONFLICT DO NOTHING;
                        """), {"p": term})
                        
                party_count += 1
                
        log.info("✓ Successfully committed %d political parties to core.entity & core.entity_name", party_count)

        log.info("--- Step 4: Ingest Political Party News Articles into content.document ---")
        if os.path.exists(NEWS_JSON):
            with open(NEWS_JSON, "r", encoding="utf-8") as f:
                news_docs = json.load(f)
                
            # Ensure a news source exists
            news_source_id = conn.execute(text("""
                SELECT source_id FROM core.source WHERE canonical_domain = 'news.google.com' LIMIT 1
            """)).scalar()
            
            if not news_source_id:
                news_source_id = conn.execute(text("""
                    INSERT INTO core.source (source_name, source_kind, canonical_domain, homepage_url, trust_tier, access_method)
                    VALUES ('Bangladesh News Media', 'publisher', 'news.google.com', 'https://news.google.com', 4, 'manual_import')
                    RETURNING source_id
                """)).scalar()
                
            news_inserted = 0
            for doc in news_docs:
                url = doc.get("url")
                title = doc.get("title", "").strip()
                publisher = doc.get("source", "")
                party_bn = doc.get("party_name_bn", "")
                
                if not url or not title:
                    continue
                    
                content_hash = hashlib.sha256((url + title).encode("utf-8")).hexdigest()
                
                # 1. Source record
                srid = conn.execute(text("""
                    SELECT source_record_id FROM core.source_record WHERE canonical_url = :url LIMIT 1
                """), {"url": url}).scalar()
                
                if not srid:
                    srid = conn.execute(text("""
                        INSERT INTO core.source_record (source_id, canonical_url, title, state, metadata)
                        VALUES (:sid, :url, :title, 'verified', CAST(:meta AS jsonb))
                        RETURNING source_record_id
                    """), {
                        "sid": news_source_id,
                        "url": url,
                        "title": title[:250],
                        "meta": json.dumps({"source": publisher, "entity": party_bn}, ensure_ascii=False)
                    }).scalar()
                    
                # 2. Document
                doc_exists = conn.execute(text("""
                    SELECT 1 FROM content.document WHERE canonical_url = :url OR source_record_id = :srid LIMIT 1
                """), {"url": url, "srid": srid}).scalar()
                
                if not doc_exists:
                    conn.execute(text("""
                        INSERT INTO content.document (
                            source_record_id, canonical_url, title, title_normalised, summary,
                            body_text, body_normalised, language_code, content_hash, state, document_kind, metadata
                        )
                        VALUES (
                            :srid, :url, :title, lower(:title), :summary,
                            :body, lower(:body), 'bn', :hash, 'verified', 'news', CAST(:meta AS jsonb)
                        )
                    """), {
                        "srid": srid,
                        "url": url,
                        "title": title[:250],
                        "summary": f"{party_bn} সম্পর্কিত সংবাদ: {title}",
                        "body": f"{title} - প্রকাশিত হয়েছে {publisher} এ। {party_bn} সম্পর্কিত সাম্প্রতিক তথ্য ও রাজনৈতিক সংবাদ।",
                        "hash": content_hash,
                        "meta": json.dumps({"source": publisher, "entity": party_bn}, ensure_ascii=False)
                    })
                    news_inserted += 1
                    
            log.info("✓ Committed %d news articles to content.document (state='verified')", news_inserted)

    log.info("--- Ingestion Complete! Running Incremental BM25 Indexer ---")
    try:
        from crawler.indexer import index_documents
        num_indexed = index_documents(batch_size=500)
        log.info("✓ BM25 Indexer successfully indexed %d documents into search.document_index", num_indexed)
    except Exception as e:
        log.warning("Indexer note: %s", e)

if __name__ == "__main__":
    run_ingestion()
