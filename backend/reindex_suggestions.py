"""
Reindex and VACUUM search.suggestion to reclaim 134MB of GIN index bloat.
After deleting 748 rows, the GIN index still holds dead pages.
REINDEX rebuilds it from scratch (smallest possible size).
"""
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

# Need isolation_level=AUTOCOMMIT for REINDEX and VACUUM
engine = create_engine(
    os.getenv("DATABASE_URL"),
    connect_args={"connect_timeout": 60},
    isolation_level="AUTOCOMMIT"
)

with engine.connect() as conn:
    print("Before: checking size...")
    size_before = conn.execute(text(
        "SELECT pg_size_pretty(pg_total_relation_size('search.suggestion'))"
    )).scalar()
    print(f"  search.suggestion: {size_before}")

    print("\nRunning REINDEX to rebuild GIN index compactly...")
    conn.execute(text("REINDEX TABLE search.suggestion"))
    print("REINDEX complete.")

    print("\nRunning VACUUM ANALYZE...")
    conn.execute(text("VACUUM ANALYZE search.suggestion"))
    print("VACUUM complete.")

    print("\nAfter: checking size...")
    size_after = conn.execute(text(
        "SELECT pg_size_pretty(pg_total_relation_size('search.suggestion'))"
    )).scalar()
    db_size = conn.execute(text(
        "SELECT pg_size_pretty(pg_database_size(current_database()))"
    )).scalar()
    print(f"  search.suggestion: {size_after}")
    print(f"  Total DB: {db_size}")
