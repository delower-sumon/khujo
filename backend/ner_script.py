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
            
            for doc in docs:
                doc_id, src_id, title, body = doc
                text_to_scan = f"{title} {body}"
                
                for district_name, entity_id in district_map.items():
                    if district_name in text_to_scan:
                        # Create an assertion
                        assertion_id = conn.execute(text("""
                            INSERT INTO core.assertion (subject_entity_id, relation_type_id, state)
                            VALUES (:entity, :rel, 'verified')
                            RETURNING assertion_id
                        """), {"entity": entity_id, "rel": relation_id}).scalar()
                        
                        # Add evidence
                        conn.execute(text("""
                            INSERT INTO core.assertion_evidence (assertion_id, source_record_id, extraction_method)
                            VALUES (:aid, :sid, 'local_ner')
                            ON CONFLICT DO NOTHING
                        """), {"aid": assertion_id, "sid": src_id})
                        
                        print(f"Found entity '{district_name}' in document {doc_id}")

    print("NER script complete.")

if __name__ == "__main__":
    run_ner()
