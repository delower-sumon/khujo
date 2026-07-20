"""
Drop the old public.suggestion table (134MB) - separate from search.suggestion (our new table)
"""
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL"), connect_args={"connect_timeout": 30})

def main():
    # First confirm what schema the 'suggestion' table is in
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
            FROM pg_tables 
            WHERE tablename = 'suggestion'
            ORDER BY schemaname
        """)).fetchall()
        print("Found 'suggestion' tables:")
        for r in rows:
            print(f"  schema={r[0]}, table={r[1]}, size={r[2]}")

    # Drop only the public.suggestion (not search.suggestion)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS public.suggestion CASCADE"))
        print("Dropped public.suggestion")

    # Verify search.suggestion is still intact
    with engine.connect() as conn:
        count = conn.execute(text("SELECT count(*) FROM search.suggestion")).scalar()
        print(f"search.suggestion still has {count} rows - intact!")
        
        # Final DB size
        total = conn.execute(text("""
            SELECT pg_size_pretty(sum(pg_total_relation_size(relid))) 
            FROM pg_catalog.pg_statio_user_tables
        """)).scalar()
        print(f"Total DB usage now: {total}")

if __name__ == "__main__":
    main()
