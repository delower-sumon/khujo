import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL"))

def clean_db():
    with engine.connect() as conn:
        with conn.begin():
            print("Dropping legacy MVP tables...")
            legacy_tables = [
                'transliteration_map',
                'autosuggestions',
                'documents',
                'crawl_queue',
                'crawl_status',
                'search_logs'
            ]
            for table in legacy_tables:
                try:
                    conn.execute(text(f"DROP TABLE IF EXISTS {table} CASCADE;"))
                    print(f"Dropped {table}")
                except Exception as e:
                    print(f"Failed to drop {table}: {e}")
            
            print("Cleaning up bloated suggestions (keeping only curated ones)...")
            try:
                # We keep 'curated' and 'harvested', drop 'transliteration' if any
                res = conn.execute(text("DELETE FROM search.suggestion WHERE source_type = 'transliteration';"))
                print(f"Deleted {res.rowcount} transliteration rows from search.suggestion.")
            except Exception as e:
                print(f"Failed to clean search.suggestion: {e}")

            # Also the old public schema 'suggestion' table if it exists
            try:
                conn.execute(text("DROP TABLE IF EXISTS suggestion CASCADE;"))
                print("Dropped old public.suggestion")
            except Exception as e:
                pass

    print("DB Cleanup complete.")

if __name__ == "__main__":
    clean_db()
