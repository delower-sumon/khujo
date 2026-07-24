import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv("backend/.env")
engine = create_engine(os.getenv("DATABASE_URL"))

with engine.connect() as conn:
    enums = conn.execute(text("""
        SELECT t.typname, e.enumlabel 
        FROM pg_type t 
        JOIN pg_enum e ON t.oid = e.enumtypid 
        ORDER BY t.typname, e.enumsortorder
    """)).fetchall()
    print("--- Postgres ENUMs in database ---")
    for r in enums:
        print(f"  {r[0]} -> {r[1]}")
