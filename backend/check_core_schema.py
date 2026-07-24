import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv("backend/.env")
engine = create_engine(os.getenv("DATABASE_URL"))

with engine.connect() as conn:
    for table in ["entity_type", "entity", "entity_name", "place", "source"]:
        cols = conn.execute(text(f"""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_schema = 'core' AND table_name = '{table}'
            ORDER BY ordinal_position
        """)).fetchall()
        print(f"--- core.{table} columns ---")
        for c in cols:
            print(f"  {c[0]} ({c[1]})")
