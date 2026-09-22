import os, psycopg2, json
from dotenv import load_dotenv

load_dotenv('backend/.env')
conn = psycopg2.connect(os.getenv('DATABASE_URL'))
cur = conn.cursor()

# Query an enriched district (Comilla / কুমিল্লা)
cur.execute("""
    SELECT e.entity_id, e.display_name, e.summary, e.metadata, p.official_code
    FROM core.entity e
    JOIN core.place p ON e.entity_id = p.entity_id
    WHERE e.display_name = 'কুমিল্লা'
    LIMIT 1;
""")
comilla = cur.fetchone()
print("=== KNOWLEDGE PANEL TEST: কুমিল্লা (Comilla District) ===")
print("Entity ID:", comilla[0])
print("Display Name:", comilla[1])
print("Code:", comilla[4])
print("Summary:", comilla[2][:160], "...")
meta = comilla[3] if isinstance(comilla[3], dict) else json.loads(comilla[3])
print("Cloudflare R2 Image:", meta.get("r2_image_url"))
print("Wikipedia URL:", meta.get("wikipedia_url"))

# Query an enriched upazila (Debidwar / দেবিদ্বার)
cur.execute("""
    SELECT e.entity_id, e.display_name, e.summary, e.metadata, p.official_code
    FROM core.entity e
    JOIN core.place p ON e.entity_id = p.entity_id
    WHERE e.display_name = 'দেবিদ্বার'
    LIMIT 1;
""")
debidwar = cur.fetchone()
print("\n=== KNOWLEDGE PANEL TEST: দেবিদ্বার (Debidwar Upazila) ===")
print("Entity ID:", debidwar[0])
print("Display Name:", debidwar[1])
print("Code:", debidwar[4])
print("Summary:", debidwar[2][:160], "...")
meta_deb = debidwar[3] if isinstance(debidwar[3], dict) else json.loads(debidwar[3])
print("Cloudflare R2 Image:", meta_deb.get("r2_image_url"))
print("Wikipedia URL:", meta_deb.get("wikipedia_url"))

# Query a seeded village (Sultanpur / সুলতানপুর)
cur.execute("""
    SELECT e.entity_id, e.display_name, e.summary, e.metadata
    FROM core.entity e
    WHERE e.display_name = 'সুলতানপুর'
    LIMIT 1;
""")
sultanpur = cur.fetchone()
print("\n=== VILLAGE CARD TEST: সুলতানপুর (Sultanpur Village) ===")
print("Entity ID:", sultanpur[0])
print("Display Name:", sultanpur[1])
print("Summary:", sultanpur[2])
meta_sul = sultanpur[3] if isinstance(sultanpur[3], dict) else json.loads(sultanpur[3])
print(f"Population: {meta_sul.get('population')} | Households: {meta_sul.get('households')}")
print(f"Parent Hierarchy: {meta_sul.get('union')} -> {meta_sul.get('upazila')} -> {meta_sul.get('district')} -> {meta_sul.get('division')}")

conn.close()
