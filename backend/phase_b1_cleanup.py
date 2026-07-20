"""
Phase B.1 — Neon DB Emergency Cleanup
Drops all legacy public-schema MVP tables to reclaim ~430MB of space.
Safe to run: only targets public.* tables, never the new core/search/content/crawl/media schemas.
"""
import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL"), connect_args={"connect_timeout": 30})

# Tables in the public schema that are legacy MVP bloat
LEGACY_PUBLIC_TABLES = [
    "transliteration_map",   # 288 MB — the main offender
    "suggestion",            # 134 MB — old MVP suggestion dump
    "autosuggestions",       # 1.8 MB
    "crawl_queue",           # 1.4 MB
    "documents",             # legacy docs
    "search_logs",           # 40 KB
    "domains",
    "entities",              # old entity table (not core.entity)
    "page_links",
    "media_items",
    "entity_mentions",
    "bangla_synonyms",
    "user_profiles",
]

def get_table_sizes(conn):
    return {
        row[0]: row[1]
        for row in conn.execute(text("""
            SELECT relname, pg_size_pretty(pg_total_relation_size(relid))
            FROM pg_catalog.pg_statio_user_tables
            WHERE schemaname = 'public'
            ORDER BY pg_total_relation_size(relid) DESC
        """)).fetchall()
    }

def get_db_usage(conn):
    """Returns current DB size."""
    row = conn.execute(text("SELECT pg_size_pretty(sum(pg_total_relation_size(relid))) FROM pg_catalog.pg_statio_user_tables")).fetchone()
    return row[0] if row else "unknown"

def main():
    with engine.connect() as conn:
        print("=" * 60)
        print("PHASE B.1 — NEON DB EMERGENCY CLEANUP")
        print("=" * 60)

        # Step 1: Show what exists in public schema before cleanup
        existing = conn.execute(text(
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
        )).fetchall()
        existing_names = {r[0] for r in existing}
        print(f"\nFound {len(existing_names)} tables in public schema: {sorted(existing_names)}")

        sizes_before = get_table_sizes(conn)
        db_before = get_db_usage(conn)
        print(f"\nTotal DB usage before: {db_before}")

        # Step 2: Drop each legacy table individually (autocommit per drop for safety)
        dropped = []
        skipped = []
        failed = []

        for table in LEGACY_PUBLIC_TABLES:
            if table not in existing_names:
                skipped.append(table)
                print(f"  SKIP   {table} (does not exist)")
                continue
            try:
                # Each drop in its own transaction to avoid cascade failures
                with engine.begin() as drop_conn:
                    drop_conn.execute(text(f"DROP TABLE IF EXISTS public.{table} CASCADE"))
                size = sizes_before.get(table, "?")
                dropped.append((table, size))
                print(f"  DROPPED {table} ({size})")
            except Exception as e:
                failed.append((table, str(e)))
                print(f"  FAILED  {table}: {e}")

        # Step 3: Verify results
        print("\n" + "=" * 60)
        print("VERIFICATION")
        print("=" * 60)

        with engine.connect() as vconn:
            remaining = vconn.execute(text(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
            )).fetchall()
            remaining_names = {r[0] for r in remaining}

            db_after = get_db_usage(vconn)
            print(f"\nDropped:  {len(dropped)} tables -> {[t for t, _ in dropped]}")
            print(f"Skipped:  {len(skipped)} tables -> {skipped}")
            print(f"Failed:   {len(failed)} tables -> {[t for t, _ in failed]}")
            print(f"\nRemaining public tables: {sorted(remaining_names)}")
            print(f"\nTotal DB usage after:  {db_after}")

            # Check new schema tables are still intact
            new_schema_counts = {}
            for schema_table in ["search.suggestion", "core.entity", "content.document", "core.entity_type"]:
                try:
                    count = vconn.execute(text(f"SELECT count(*) FROM {schema_table}")).scalar()
                    new_schema_counts[schema_table] = count
                except Exception as e:
                    new_schema_counts[schema_table] = f"ERROR: {e}"

            print("\n--- New schema tables (must be intact) ---")
            for tbl, cnt in new_schema_counts.items():
                print(f"  {tbl}: {cnt} rows")

        if failed:
            print(f"\n⚠️  WARNING: {len(failed)} tables failed to drop. Manual intervention needed.")
        else:
            print("\n✅ Phase B.1 COMPLETE — All legacy tables dropped successfully.")

if __name__ == "__main__":
    main()
