"""
Patch script to add missing aliases for political parties.
Ensures lowercase acronyms and common misspellings (e.g., bmp, বিএমপি) are added.
"""
import os
import sys
import logging

# Ensure repo root is in python path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from crawler.utils.db import get_engine
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("patch_party_synonyms")

def run_patch():
    engine = get_engine()
    
    with engine.begin() as conn:
        log.info("--- Patching Political Party Synonyms ---")
        
        # 1. For all existing abbreviations, add lowercase versions if they don't exist
        res = conn.execute(text("""
            INSERT INTO core.entity_name (entity_id, language_code, script, name_kind, name, normalised_name, is_primary, state)
            SELECT n.entity_id, n.language_code, n.script, n.name_kind, lower(n.name), lower(n.name), FALSE, 'verified'
            FROM core.entity_name n
            JOIN core.entity e USING (entity_id)
            JOIN core.entity_type t USING (entity_type_id)
            WHERE t.slug = 'political_party'
              AND n.name_kind = 'abbreviation'
              AND lower(n.name) != n.name
            ON CONFLICT (entity_id, normalised_name, language_code, name_kind) DO NOTHING;
        """))
        log.info(f"Inserted lowercase variants: {res.rowcount}")

        # 2. Add specific aliases for 'বাংলাদেশ জাতীয়তাবাদী দল'
        bnp_id = conn.execute(text("""
            SELECT entity_id FROM core.entity WHERE display_name = 'বাংলাদেশ জাতীয়তাবাদী দল' LIMIT 1
        """)).scalar()
        
        if bnp_id:
            aliases = [
                ('bnp', 'en', 'latin', 'alias'),
                ('বিএনপি', 'bn', 'bangla', 'abbreviation'),
                ('bmp', 'en', 'latin', 'alias'),
                ('বিএমপি', 'bn', 'bangla', 'alias')
            ]
            count = 0
            for name, lang, script, kind in aliases:
                res = conn.execute(text("""
                    INSERT INTO core.entity_name (entity_id, language_code, script, name_kind, name, normalised_name, is_primary, state)
                    VALUES (:eid, :lang, :script, :kind, :name, lower(:name), FALSE, 'verified')
                    ON CONFLICT (entity_id, normalised_name, language_code, name_kind) DO NOTHING;
                """), {"eid": bnp_id, "lang": lang, "script": script, "kind": kind, "name": name})
                count += res.rowcount
            log.info(f"Inserted explicit BNP aliases: {count}")
        else:
            log.warning("Could not find entity 'বাংলাদেশ জাতীয়তাবাদী দল'")

if __name__ == "__main__":
    run_patch()
