import os, sys
sys.stdout.reconfigure(encoding='utf-8')
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
load_dotenv('backend/.env')
engine = create_engine(os.getenv('DATABASE_URL'))
with engine.connect() as conn:
    events = conn.execute(text('SELECT normalised_query, result_count, occurred_at FROM search.query_event ORDER BY occurred_at DESC LIMIT 10')).fetchall()
    print('=== Live Search Query Analytics Log (search.query_event) ===')
    for ev in events:
        print(f"  • Query: '{ev[0]}' | Results: {ev[1]} | Time: {ev[2]}")
