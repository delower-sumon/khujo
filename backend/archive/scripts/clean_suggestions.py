"""
Phase B.1 Final Step: Clean search.suggestion table
- Delete 748 low-quality crawler-harvested suggestions (nav text like 'Brands', 'Gallery')
- Keep the 16 curated rows
- The GIN trigram index will rebuild small after deletion
"""
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL"), connect_args={"connect_timeout": 30})

with engine.begin() as conn:
    # Delete all crawler-sourced candidate suggestions (low-quality nav text)
    result = conn.execute(text("""
        DELETE FROM search.suggestion 
        WHERE source_kind = 'crawler' AND state = 'candidate'
    """))
    print(f"Deleted {result.rowcount} low-quality crawler suggestions")

# Verify
with engine.connect() as conn:
    count = conn.execute(text("SELECT count(*) FROM search.suggestion")).scalar()
    kinds = conn.execute(text("SELECT source_kind, count(*) FROM search.suggestion GROUP BY source_kind")).fetchall()
    size = conn.execute(text("SELECT pg_size_pretty(pg_total_relation_size('search.suggestion'))")).scalar()
    db_total = conn.execute(text("SELECT pg_size_pretty(pg_database_size(current_database()))")).scalar()
    
    print(f"\nRemaining rows: {count}")
    for r in kinds:
        print(f"  source_kind={r[0]}: {r[1]} rows")
    print(f"\nsearch.suggestion size: {size}")
    print(f"Total DB size: {db_total}")
    
    # Show the 16 curated rows we kept
    curated = conn.execute(text("""
        SELECT phrase, state, priority FROM search.suggestion 
        WHERE source_kind = 'curated'
        ORDER BY priority DESC, phrase
        LIMIT 20
    """)).fetchall()
    print("\nCurated suggestions kept:")
    for r in curated:
        try:
            print(f"  [{r[1]}] prio={r[2]}  {r[0]}")
        except Exception:
            print(f"  [{r[1]}] prio={r[2]}  (bangla phrase)")
