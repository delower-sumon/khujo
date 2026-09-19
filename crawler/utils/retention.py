"""
Khujo Maintenance — Retention Policy Enforcer (retention.py)
Remediates Defect D16 from khujo_code_audit.md.

Purges expired search query events and retired/rejected documents
in accordance with content.retention_policy definitions.
"""

import os
import logging
from sqlalchemy import text
try:
    from utils.db import get_engine
except ImportError:
    from crawler.utils.db import get_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("retention")

def purge_expired_records():
    engine = get_engine()
    with engine.begin() as conn:
        log.info("Checking expired search query events...")
        query_events_deleted = conn.execute(text("""
            DELETE FROM search.query_event 
            WHERE expires_at < now()
        """)).rowcount
        log.info(f"Purged {query_events_deleted} expired search query events.")

        log.info("Checking expired candidate / retired documents...")
        docs_purged = conn.execute(text("""
            DELETE FROM content.document 
            WHERE expires_at < now() 
              AND state IN ('rejected', 'retired')
        """)).rowcount
        log.info(f"Purged {docs_purged} expired non-active documents.")

        log.info("Checking expired frontier queue leases...")
        leases_reset = conn.execute(text("""
            UPDATE crawl.frontier_url 
            SET state = 'queued', lease_token = NULL, lease_expires_at = NULL 
            WHERE state = 'leased' AND lease_expires_at < now()
        """)).rowcount
        log.info(f"Reset {leases_reset} expired crawler leases.")

    log.info("Retention policy enforcement cycle complete.")

if __name__ == "__main__":
    purge_expired_records()
