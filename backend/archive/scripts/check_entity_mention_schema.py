import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv("backend/.env")
engine = create_engine(os.getenv("DATABASE_URL"))

with engine.connect() as conn:
    cols = conn.execute(text("""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_schema = 'content' AND table_name = 'entity_mention'
        ORDER BY ordinal_position
    """)).fetchall()
    print("--- content.entity_mention columns ---")
    for c in cols:
        print(f"  {c[0]} ({c[1]})")
