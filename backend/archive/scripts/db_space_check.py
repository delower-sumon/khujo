import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL"))

def check_db_space():
    with engine.connect() as conn:
        print("--- Table Sizes ---")
        result = conn.execute(text("""
            SELECT
                relname as table_name,
                pg_size_pretty(pg_total_relation_size(relid)) as total_size,
                pg_total_relation_size(relid) as size_bytes
            FROM pg_catalog.pg_statio_user_tables
            ORDER BY pg_total_relation_size(relid) DESC;
        """)).fetchall()
        for row in result:
            print(f"{row[0]}: {row[1]} ({row[2]} bytes)")
            
        print("\n--- Row Counts ---")
        tables = ['search.suggestion', 'content.document', 'core.assertion', 'core.entity']
        for t in tables:
            try:
                count = conn.execute(text(f"SELECT count(*) FROM {t}")).scalar()
                print(f"{t}: {count} rows")
            except Exception as e:
                print(f"{t}: error - {e}")

if __name__ == "__main__":
    check_db_space()
