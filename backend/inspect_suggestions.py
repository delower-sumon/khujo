"""
Inspect search.suggestion table and VACUUM to reclaim space.
"""
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL"), connect_args={"connect_timeout": 30})

with engine.connect() as conn:
    # Check breakdown of rows by source_kind
    print("--- search.suggestion breakdown by source_kind ---")
    rows = conn.execute(text("""
        SELECT source_kind, count(*) as cnt
        FROM search.suggestion 
        GROUP BY source_kind 
        ORDER BY cnt DESC
    """)).fetchall()
    for r in rows:
        print(f"  source_kind={repr(r[0]):30s}  count={r[1]}")

    # Check table bloat
    print("\n--- Table bloat analysis ---")
    bloat = conn.execute(text("""
        SELECT pg_size_pretty(pg_total_relation_size('search.suggestion')) as total_size,
               pg_size_pretty(pg_relation_size('search.suggestion')) as table_size,
               pg_size_pretty(pg_indexes_size('search.suggestion')) as index_size
    """)).fetchone()
    print(f"  Total: {bloat[0]}")
    print(f"  Table data: {bloat[1]}")
    print(f"  Indexes: {bloat[2]}")

    # Check how many are 'active' vs 'candidate'
    print("\n--- Rows by state ---")
    states = conn.execute(text("""
        SELECT state, count(*) FROM search.suggestion GROUP BY state
    """)).fetchall()
    for r in states:
        print(f"  {r[0]}: {r[1]}")

    # Sample some rows
    print("\n--- Sample rows (last 10 inserted) ---")
    samples = conn.execute(text("""
        SELECT phrase, source_kind, state, priority, length(phrase) as plen
        FROM search.suggestion 
        ORDER BY created_at DESC 
        LIMIT 10
    """)).fetchall()
    for r in samples:
        print(f"  [{r[1]}] state={r[2]}  prio={r[3]}  len={r[4]}  phrase={repr(r[0])[:60]}")
