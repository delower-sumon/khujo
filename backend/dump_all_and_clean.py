import os
import json
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL"))

def dump_and_clean():
    with engine.connect() as conn:
        print("Exporting transliteration_map...")
        try:
            res = conn.execute(text("SELECT bangla, english FROM transliteration_map")).fetchall()
            with open("legacy_transliteration.json", "w") as f:
                json.dump([dict(bangla=r[0], english=r[1]) for r in res], f)
        except Exception as e:
            print("transliteration_map might already be dropped or error:", e)

        print("Exporting autosuggestions...")
        try:
            res = conn.execute(text("SELECT phrase, transliteration, language_code, category, search_volume_weight, intent, priority_level, source_type FROM autosuggestions")).fetchall()
            with open("legacy_autosuggestions.json", "w") as f:
                json.dump([dict(phrase=r[0], transliteration=r[1], language_code=r[2], category=r[3], 
                                search_volume_weight=r[4], intent=r[5], priority_level=r[6], source_type=r[7]) for r in res], f)
        except Exception as e:
            print("autosuggestions might already be dropped or error:", e)

        print("Dropping all legacy tables to free up maximum space...")
        try:
            conn.execute(text("DROP TABLE IF EXISTS documents CASCADE;"))
            conn.execute(text("DROP TABLE IF EXISTS transliteration_map CASCADE;"))
            conn.execute(text("DROP TABLE IF EXISTS autosuggestions CASCADE;"))
            conn.execute(text("DROP TABLE IF EXISTS crawl_queue CASCADE;"))
            conn.commit()
            print("Dropped legacy tables.")
        except Exception as e:
            print("Error dropping tables:", e)

if __name__ == "__main__":
    dump_and_clean()
