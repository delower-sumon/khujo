"""
KhujoBot Phase 2: Worker 03 - NER & Knowledge
Tags entity mentions in candidate documents using the core.search_dictionary.
"""
import os
import json
import logging
from sqlalchemy import text
from utils.db import get_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("worker_03_knowledge")

def process_knowledge_extraction(batch_limit=10):
    engine = get_engine()

    with engine.connect() as conn:
        # Load the newly created search dictionary for robust NER
        dictionary_entries = conn.execute(text("""
            SELECT normalised_term, entity_id 
            FROM core.search_dictionary 
            WHERE state IN ('candidate', 'active') 
            AND length(normalised_term) >= 3
            ORDER BY length(normalised_term) DESC
        """)).fetchall()

        term_lookup = [(r[0], str(r[1])) for r in dictionary_entries if r[1]]
        
        # Fallback to core.entity_name if dictionary is still empty (bootstrapping phase)
        if not term_lookup:
            log.info("Search dictionary is empty. Falling back to core.entity_name for NER.")
            fallback = conn.execute(text("""
                SELECT normalised_name, entity_id 
                FROM core.entity_name 
                WHERE length(normalised_name) >= 3
                ORDER BY length(normalised_name) DESC
            """)).fetchall()
            term_lookup = [(r[0], str(r[1])) for r in fallback]

        log.info(f"Loaded {len(term_lookup)} terms for mention tagging.")

        # Fetch candidate documents that haven't had entities extracted yet
        docs = conn.execute(text("""
            SELECT document_id, source_record_id, title, body_text
            FROM content.document
            WHERE entities_extracted_at IS NULL AND state = 'candidate'
            ORDER BY discovered_at ASC
            LIMIT :limit
        """), {"limit": batch_limit}).fetchall()

        if not docs:
            log.info("No documents waiting for knowledge extraction.")
            return

        log.info(f"Found {len(docs)} documents for NER tagging.")

        for row in docs:
            doc_id = str(row[0])
            source_record_id = str(row[1])
            title = row[2] or ""
            body = row[3] or ""
            
            search_corpus = f"{title}\n{body}".lower()
            matched_entities = set()

            # Simple string matching NER
            for term, eid in term_lookup:
                if term in search_corpus:
                    matched_entities.add((eid, term))
                    if len(matched_entities) >= 5: # Max 5 per doc to prevent noise
                        break
            
            with engine.begin() as wconn:
                for eid, form in matched_entities:
                    wconn.execute(text("""
                        INSERT INTO content.entity_mention (
                            source_record_id, entity_id, surface_form, 
                            confidence, extraction_method, state
                        ) VALUES (
                            :srid, :eid, :form, 0.90, 'dictionary_match', 'candidate'
                        ) ON CONFLICT DO NOTHING
                    """), {"srid": source_record_id, "eid": eid, "form": form})

                # Mark document as processed
                wconn.execute(text("""
                    UPDATE content.document 
                    SET entities_extracted_at = now() 
                    WHERE document_id = :did
                """), {"did": doc_id})

            log.info(f"Document {doc_id} processed. Tagged {len(matched_entities)} entities.")

if __name__ == "__main__":
    process_knowledge_extraction(5)
