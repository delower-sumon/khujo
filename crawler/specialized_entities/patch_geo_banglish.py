"""
Patch script to add missing Banglish aliases for Dhanbari (Geo Entity)
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
log = logging.getLogger("patch_geo_banglish")

def run_patch():
    engine = get_engine()
    
    with engine.begin() as conn:
        log.info("--- Patching Geo Entity Synonyms ---")
        
        # Dhanbari aliases
        res = conn.execute(text("""
            INSERT INTO core.entity_name (entity_id, language_code, script, name_kind, name, normalised_name, is_primary, state)
            SELECT e.entity_id, 'en', 'latin', 'alias', alias_name, lower(alias_name), FALSE, 'verified'
            FROM core.entity e
            CROSS JOIN (VALUES ('dhonbari'), ('dhanbari')) AS v(alias_name)
            WHERE e.display_name = 'ধনবাড়ী'
            ON CONFLICT (entity_id, normalised_name, language_code, name_kind) DO NOTHING;
        """))
        
        log.info(f"Inserted Dhanbari aliases: {res.rowcount}")

if __name__ == "__main__":
    run_patch()
