import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not set in .env")

engine = create_engine(DATABASE_URL)

def run_sql_file(filepath):
    print(f"Running {filepath}...")
    with open(filepath, 'r', encoding='utf-8') as f:
        sql = f.read()
    
    with engine.connect() as conn:
        # We need to execute statements. Some might fail if they already exist, but our script is fresh.
        # SQLAlchemy handles the transaction, but our script has BEGIN/COMMIT
        # Let's remove the raw BEGIN/COMMIT from the script string to avoid conflicts
        sql = sql.replace("BEGIN;", "").replace("COMMIT;", "")
        # psycopg2 driver supports multiple statements in one execute
        conn.execute(text(sql))
        conn.commit()
    print(f"Successfully executed {filepath}")

if __name__ == "__main__":
    sql_dir = os.path.join(os.path.dirname(__file__), 'sql')
    
    file_1 = os.path.join(sql_dir, '0001_khojo_core.sql')
    file_2 = os.path.join(sql_dir, '0002_nullable_unique_indexes.sql')
    
    run_sql_file(file_1)
    run_sql_file(file_2)
    
    print("Database initialized successfully with new schemas.")
