import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv("backend/.env")
engine = create_engine(os.getenv("DATABASE_URL"))

with engine.connect() as conn:
    for sch, tbl in [("crawl", "frontier_url"), ("media", "asset"), ("search", "suggestion")]:
        cols = conn.execute(text(f"""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_schema = '{sch}' AND table_name = '{tbl}'
            ORDER BY ordinal_position
        """)).fetchall()
        print(f"--- {sch}.{tbl} columns ---")
        for c in cols:
            print(f"  {c[0]} ({c[1]})")
