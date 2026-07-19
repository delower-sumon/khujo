import os
import json
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL"))

def dump_and_clean():
    with engine.connect() as conn:
        print("Fetching URLs from documents...")
        result = conn.execute(text("SELECT url FROM documents WHERE url IS NOT NULL")).fetchall()
        urls = [r[0] for r in result]
        
        print(f"Exporting {len(urls)} URLs...")
        with open("legacy_urls.json", "w") as f:
            json.dump(urls, f)
            
        print("Dropping legacy documents table to free up space...")
        # Drop the table to immediately reclaim space
        conn.execute(text("DROP TABLE IF EXISTS documents CASCADE;"))
        conn.commit()
        print("Dropped 'documents' table successfully. This should free up the 512MB limit.")

if __name__ == "__main__":
    dump_and_clean()
