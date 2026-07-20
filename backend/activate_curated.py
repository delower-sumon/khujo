import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv("DATABASE_URL"), connect_args={"connect_timeout": 30})

with engine.begin() as conn:
    n = conn.execute(text("UPDATE search.suggestion SET state = 'active' WHERE source_kind = 'curated'")).rowcount
    print(f"Activated {n} curated suggestions")

with engine.connect() as conn:
    total = conn.execute(text("SELECT pg_size_pretty(pg_database_size(current_database()))")).scalar()
    active = conn.execute(text("SELECT count(*) FROM search.suggestion WHERE state = 'active'")).scalar()
    print(f"Active suggestions: {active}")
    print(f"Final DB size: {total}")
