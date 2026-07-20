"""
Definitive DB state check: queries pg_database for actual live size.
"""
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL"), connect_args={"connect_timeout": 30})

with engine.connect() as conn:
    # Actual database size from pg_database (authoritative)
    db_size = conn.execute(text("SELECT pg_size_pretty(pg_database_size(current_database()))")).scalar()
    print(f"Actual Neon DB size: {db_size}")

    # List all tables by schema
    print("\n--- All tables by schema ---")
    rows = conn.execute(text("""
        SELECT schemaname, tablename,
               pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size
        FROM pg_tables
        WHERE schemaname NOT IN ('information_schema', 'pg_catalog', 'tiger', 'tiger_data', 'topology')
        ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
        LIMIT 30
    """)).fetchall()
    for r in rows:
        print(f"  {r[0]}.{r[1]}: {r[2]}")

    # Specifically check: is public.suggestion still there?
    print("\n--- public schema tables ---")
    pub = conn.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename")).fetchall()
    if pub:
        for r in pub:
            print(f"  public.{r[0]}")
    else:
        print("  (none - public schema is clean)")

    # New schema row counts
    print("\n--- New schema row counts ---")
    for t in ["search.suggestion", "core.entity", "core.entity_type", "content.document"]:
        try:
            n = conn.execute(text(f"SELECT count(*) FROM {t}")).scalar()
            print(f"  {t}: {n} rows")
        except Exception as e:
            print(f"  {t}: ERROR - {e}")
