import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL"))

def run_ner():
    with engine.connect() as conn:
        with conn.begin():
            print("Fetching verified geographic entities (Districts)...")
            entities = conn.execute(text("""
                SELECT n.normalised_name, e.entity_id 
                FROM core.entity_name n
                JOIN core.entity e ON n.entity_id = e.entity_id
                WHERE n.language_code = 'bn'
            """)).fetchall()
            
            district_map = {row[0]: row[1] for row in entities}
            
            print("Fetching documents to scan...")
            docs = conn.execute(text("SELECT document_id, source_record_id, title_normalised, body_normalised FROM content.document")).fetchall()
            
            # Relation type ID for 'about'
            relation_id = conn.execute(text("SELECT relation_type_id FROM core.relation_type WHERE slug = 'about'")).scalar()
            if not relation_id:
                print("Warning: relation_type 'about' not found in database.")
                return

            total_mentions = 0
            for doc in docs:
                doc_id, src_id, title, body = doc
                text_to_scan = f"{title or ''} {body or ''}".strip()
                if not text_to_scan:
                    continue

                # O(L) token and bigram lookup instead of quadratic O(N*M) substring search
                words = text_to_scan.split()
                candidate_terms = set(words)
                for i in range(len(words) - 1):
                    candidate_terms.add(f"{words[i]} {words[i+1]}")

                matched_names = candidate_terms.intersection(district_map.keys())

                for district_name in matched_names:
                    entity_id = district_map[district_name]
                    
                    # Idempotent assertion check (Fixes D10 duplicate assertion spam)
                    existing_aid = conn.execute(text("""
                        SELECT assertion_id FROM core.assertion 
                        WHERE subject_entity_id = :entity AND relation_type_id = :rel
                        LIMIT 1
                    """), {"entity": entity_id, "rel": relation_id}).scalar()

                    if not existing_aid:
                        existing_aid = conn.execute(text("""
                            INSERT INTO core.assertion (subject_entity_id, relation_type_id, state)
                            VALUES (:entity, :rel, 'verified')
                            RETURNING assertion_id
                        """), {"entity": entity_id, "rel": relation_id}).scalar()
                    
                    # Add evidence linked to this source record
                    if existing_aid and src_id:
                        conn.execute(text("""
                            INSERT INTO core.assertion_evidence (assertion_id, source_record_id, extraction_method)
                            VALUES (:aid, :sid, 'local_ner')
                            ON CONFLICT DO NOTHING
                        """), {"aid": existing_aid, "sid": src_id})
                        total_mentions += 1
                        
            print(f"NER script complete. Total mentions processed: {total_mentions}")

if __name__ == "__main__":
    run_ner()
