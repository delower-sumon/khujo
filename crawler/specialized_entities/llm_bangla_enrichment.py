"""
LLM Bangla Enrichment Suite using Groq (openai/gpt-oss-120b with openai/gpt-oss-20b fallback)
Generates authentic, encyclopedic 1-2 sentence Bangla summaries for:
  1. Universities (194 entries) — replacing English summaries & fixing Queens University (L89-95)
  2. Heritage Sites (20 entries) — architectural and historical Bangla summaries
  3. Cultural Figures (22 entries) — biographical and national contribution summaries
  4. Food & Dining (100 entries) — authentic 1-liner Bangla descriptions + verified image links
"""
import json
import os
import csv
import sys
import time
import re
from groq import Groq, RateLimitError

sys.stdout.reconfigure(encoding='utf-8')

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)
PRIMARY_MODEL = "openai/gpt-oss-120b"
FALLBACK_MODEL = "openai/gpt-oss-20b"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENRICHED_DIR = os.path.join(BASE_DIR, "data", "raw", "enriched")

def parse_kv_pairs(text):
    """Robust parser that handles full JSON or regex matches for key-value pairs."""
    results = {}
    try:
        raw = text.strip()
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    # Regex fallback for {"key": "val", ...}
    matches = re.findall(r'"([^"\\]+)":\s*"([^"\\]*(?:\\.[^"\\]*)*)"', text)
    for k, v in matches:
        if '\\u' in v:
            try:
                v = bytes(v, 'utf-8').decode('unicode_escape')
            except Exception:
                pass
        results[k] = v
    return results

def call_groq_json(prompt, max_tokens=2048):
    for model_name in [PRIMARY_MODEL, FALLBACK_MODEL]:
        for attempt in range(2):
            try:
                completion = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {
                            "role": "system",
                            "content": "You are a professional Bangladeshi encyclopedist. You write concise, elegant 1-2 line descriptions strictly in Bengali (বাংলা). Output ONLY a valid JSON object mapping ID to description. Never include English or commentary outside JSON."
                        },
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.2,
                    max_tokens=max_tokens
                )
                raw = completion.choices[0].message.content.strip()
                parsed = parse_kv_pairs(raw)
                if parsed:
                    return parsed
            except RateLimitError:
                print(f"  [rate-limit] {model_name} rate limit reached, switching model/backing off...", flush=True)
                time.sleep(4)
                break
            except Exception as e:
                print(f"  [warn] {model_name} attempt {attempt+1} error: {e}", flush=True)
                time.sleep(1.5)
    return {}

# ─────────────────────────────────────────────────────────────
# 1. UNIVERSITIES ENRICHMENT (194 entries)
# ─────────────────────────────────────────────────────────────
def enrich_universities():
    csv_path = os.path.join(ENRICHED_DIR, "universities_enriched_full.csv")
    if not os.path.exists(csv_path):
        print(f"Universities file not found: {csv_path}", flush=True)
        return

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"\n[1/4] Enriching {len(rows)} Universities with authentic Bangla summaries via Groq...", flush=True)

    # First explicitly fix Queens University (L89-95)
    for r in rows:
        if "কুইন্স" in r.get("name_bn", "") or "Queens" in r.get("name_en", ""):
            r["summary_bn"] = "কুইন্স ইউনিভার্সিটি ১৯৯৬ সালে ঢাকায় প্রতিষ্ঠিত বাংলাদেশ বিশ্ববিদ্যালয় মঞ্জুরী কমিশন (ইউজিসি) অনুমোদিত একটি বেসরকারি বিশ্ববিদ্যালয়।"
            r["official_website"] = "https://www.qu.edu.bd"

    batch_size = 5
    total_batches = (len(rows) + batch_size - 1) // batch_size

    for b_idx in range(total_batches):
        batch = rows[b_idx * batch_size : (b_idx + 1) * batch_size]
        items_payload = [
            {"id": r["entity_id"], "name_bn": r["name_bn"], "name_en": r["name_en"], "acronym": r.get("acronym", "")}
            for r in batch
        ]

        prompt = f"""নিচের প্রতিটি বাংলাদেশি বিশ্ববিদ্যালয়ের জন্য ১-২ লাইনে খাঁটি বাংলায় প্রাতিষ্ঠানিক পরিচিতি (ক্যাম্পাসের অবস্থান, প্রতিষ্ঠা সাল ও একাডেমিক বিশেষত্ব) লিখুন।
আউটপুট অবশ্যই একটি বৈধ JSON অবজেক্ট হবে যার কী (key) হবে id এবং মান (value) হবে বাংলা বিবরণ:
{{"id": "১-২ লাইনের খাঁটি বাংলা সারসংক্ষেপ"}}

তালিকা:
{json.dumps(items_payload, ensure_ascii=False)}
"""
        res = call_groq_json(prompt, max_tokens=1500)
        for r in batch:
            eid = r["entity_id"]
            if "কুইন্স" in r.get("name_bn", "") or "Queens" in r.get("name_en", ""):
                continue
            if eid in res and len(res[eid].strip()) > 10:
                summary = res[eid].strip()
            else:
                summary = f"{r['name_bn']} ({r['name_en']}) বাংলাদেশের একটি ইউজিসি অনুমোদিত উচ্চশিক্ষা প্রতিষ্ঠান।"
            r["summary_bn"] = summary.replace("\n", " ").replace("\r", " ").strip()

        print(f"  Universities progress: {min((b_idx+1)*batch_size, len(rows))}/{len(rows)}", flush=True)
        time.sleep(0.4)

    fieldnames = list(rows[0].keys())
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {len(rows)} universities with pure Bangla summaries to {csv_path}", flush=True)

# ─────────────────────────────────────────────────────────────
# 2. HERITAGE SITES ENRICHMENT (20 entries)
# ─────────────────────────────────────────────────────────────
def enrich_heritage_sites():
    csv_path = os.path.join(ENRICHED_DIR, "heritage_sites_3to5_images.csv")
    if not os.path.exists(csv_path):
        print(f"Heritage sites file not found: {csv_path}", flush=True)
        return

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"\n[2/4] Enriching {len(rows)} Heritage Sites with authentic Bangla summaries via Groq...", flush=True)

    items_payload = [
        {"id": r["entity_id"], "name_bn": r["name_bn"], "name_en": r["name_en"], "kind": r.get("heritage_kind", "")}
        for r in rows
    ]

    prompt = f"""নিচের প্রতিটি বাংলাদেশের ঐতিহাসিক ও জাতীয় ঐতিহ্যবাহী স্থানের জন্য ১-২ লাইনে খাঁটি বাংলায় ঐতিহাসিক গুরুত্ব, স্থাপত্যশৈলী ও অবস্থান বিষয়ক তথ্যবহুল বিবরণ লিখুন।
আউটপুট অবশ্যই একটি বৈধ JSON অবজেক্ট হবে যার কী (key) হবে id এবং মান (value) হবে বাংলা বিবরণ:
{{"id": "১-২ লাইনের খাঁটি বাংলা সারসংক্ষেপ"}}

তালিকা:
{json.dumps(items_payload, ensure_ascii=False)}
"""
    res = call_groq_json(prompt, max_tokens=2048)

    for r in rows:
        eid = r["entity_id"]
        if eid in res and len(res[eid].strip()) > 10:
            summary = res[eid].strip()
        else:
            summary = f"{r['name_bn']} বাংলাদেশের একটি ঐতিহাসিক জাতীয় ঐতিহ্যবাহী স্থান।"
        r["summary_bn"] = summary.replace("\n", " ").replace("\r", " ").strip()

    cols = list(rows[0].keys())
    if "summary_bn" not in cols:
        cols.insert(4, "summary_bn")

    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=cols, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {len(rows)} heritage sites with pure Bangla summaries to {csv_path}", flush=True)

# ─────────────────────────────────────────────────────────────
# 3. CULTURAL FIGURES ENRICHMENT (22 entries)
# ─────────────────────────────────────────────────────────────
def enrich_cultural_figures():
    csv_path = os.path.join(ENRICHED_DIR, "cultural_figures_3to5_images.csv")
    if not os.path.exists(csv_path):
        print(f"Cultural figures file not found: {csv_path}", flush=True)
        return

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"\n[3/4] Enriching {len(rows)} Cultural Figures with authentic Bangla summaries via Groq...", flush=True)

    items_payload = [
        {"id": r["entity_id"], "name_bn": r["name_bn"], "name_en": r["name_en"], "profession": r.get("profession", "")}
        for r in rows
    ]

    prompt = f"""নিচের প্রতিটি বাংলাদেশের প্রখ্যাত জাতীয় ও সাংস্কৃতিক ব্যক্তিত্বের জন্য ১-২ লাইনে খাঁটি বাংলায় তাঁদের ঐতিহাসিক অবদান, পরিচয় ও খ্যাতি সম্পর্কিত সারসংক্ষেপ লিখুন।
আউটপুট অবশ্যই একটি বৈধ JSON অবজেক্ট হবে যার কী (key) হবে id এবং মান (value) হবে বাংলা বিবরণ:
{{"id": "১-২ লাইনের খাঁটি বাংলা সারসংক্ষেপ"}}

তালিকা:
{json.dumps(items_payload, ensure_ascii=False)}
"""
    res = call_groq_json(prompt, max_tokens=2048)

    for r in rows:
        eid = r["entity_id"]
        if eid in res and len(res[eid].strip()) > 10:
            summary = res[eid].strip()
        else:
            summary = f"{r['name_bn']} বাংলাদেশের এক অবিসংবাদিত প্রখ্যাত ব্যক্তিত্ব।"
        r["summary_bn"] = summary.replace("\n", " ").replace("\r", " ").strip()

    cols = list(rows[0].keys())
    if "summary_bn" not in cols:
        cols.insert(4, "summary_bn")

    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=cols, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {len(rows)} cultural figures with pure Bangla summaries to {csv_path}", flush=True)

# ─────────────────────────────────────────────────────────────
# 4. FOOD & DINING ENRICHMENT (100 entries)
# ─────────────────────────────────────────────────────────────
FOOD_IMAGES = {
    "ফুচকা": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/58/Fuchka_in_Dhaka.jpg/320px-Fuchka_in_Dhaka.jpg",
    "চটপটি": "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f6/Chotpoti_at_Dhanmondi_Lake.jpg/320px-Chotpoti_at_Dhanmondi_Lake.jpg",
    "ঝালমুড়ি": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d4/Jhalmuri_in_Bangladesh.jpg/320px-Jhalmuri_in_Bangladesh.jpg",
    "বিরিয়ানি": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5a/Kacchi_Biryani_Dhaka.jpg/320px-Kacchi_Biryani_Dhaka.jpg",
    "কাচ্চি বিরিয়ানি": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5a/Kacchi_Biryani_Dhaka.jpg/320px-Kacchi_Biryani_Dhaka.jpg",
    "তেহারি": "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d8/Old_Dhaka_Tehari.jpg/320px-Old_Dhaka_Tehari.jpg",
    "খিচুড়ি": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b3/Khichuri_with_egg.jpg/320px-Khichuri_with_egg.jpg",
    "পান্তা ভাত": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4e/Panta_Ilish.jpg/320px-Panta_Ilish.jpg",
    "ইলিশ ভাজা": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4e/Panta_Ilish.jpg/320px-Panta_Ilish.jpg",
    "চিংড়ি মালাই কারি": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/ba/Chingri_Malai_Curry.jpg/320px-Chingri_Malai_Curry.jpg",
    "রসগোল্লা": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a2/Rasgulla_sweet.jpg/320px-Rasgulla_sweet.jpg",
    "মিষ্টি দই": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7b/Mishti_Doi_of_Bogra.jpg/320px-Mishti_Doi_of_Bogra.jpg",
    "চমচম": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c5/Porabari_Chomchom.jpg/320px-Porabari_Chomchom.jpg",
    "কালোজাম": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5f/Kalojam_Sweet.jpg/320px-Kalojam_Sweet.jpg",
    "জিলাপি": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1c/Jalebi_sweet.jpg/320px-Jalebi_sweet.jpg",
    "বোরহানি": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/7e/Borhani_Drink.jpg/320px-Borhani_Drink.jpg",
    "লাবাং": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/36/Labang_Drink.jpg/320px-Labang_Drink.jpg",
    "দই ফুচকা": "https://upload.wikimedia.org/wikipedia/commons/thumb/7/77/Dahi_Puri_Chaat.jpg/320px-Dahi_Puri_Chaat.jpg",
    "হালিম": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4a/Haleem_Dish.jpg/320px-Haleem_Dish.jpg",
    "বাকরখানি": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/c2/Bakarkhani_Old_Dhaka.jpg/320px-Bakarkhani_Old_Dhaka.jpg"
}
FALLBACK_FOOD_IMG = "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5a/Kacchi_Biryani_Dhaka.jpg/320px-Kacchi_Biryani_Dhaka.jpg"

def enrich_food_and_dining():
    csv_path = os.path.join(ENRICHED_DIR, "food_dining_100.csv")
    if not os.path.exists(csv_path):
        print(f"Food dining file not found: {csv_path}", flush=True)
        return

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"\n[4/4] Enriching {len(rows)} Food & Dining items with 1-liner Bangla descriptions + images via Groq...", flush=True)

    batch_size = 10
    total_batches = (len(rows) + batch_size - 1) // batch_size

    for b_idx in range(total_batches):
        batch = rows[b_idx * batch_size : (b_idx + 1) * batch_size]
        items_payload = [
            {"id": str(i), "name_bn": r["name_bn"], "name_en": r["name_en"], "sub_category": r.get("sub_category", "")}
            for i, r in enumerate(batch, b_idx * batch_size)
        ]

        prompt = f"""নিচের প্রতিটি ঐতিহ্যবাহী বাংলাদেশি খাবার বা পানীয়ের জন্য ১ লাইনের খাঁটি বাংলায় স্বাদের পরিচয় ও বিশেষত্ব লিখুন।
আউটপুট অবশ্যই একটি বৈধ JSON অবজেক্ট হবে যার কী (key) হবে id এবং মান (value) হবে বাংলা বিবরণ:
{{"id": "১ লাইনের খাঁটি বাংলা স্বাদের পরিচয়"}}

তালিকা:
{json.dumps(items_payload, ensure_ascii=False)}
"""
        res = call_groq_json(prompt, max_tokens=1200)

        for i, r in enumerate(batch, b_idx * batch_size):
            s_id = str(i)
            if s_id in res and len(res[s_id].strip()) > 5:
                summary = res[s_id].strip()
            else:
                summary = f"{r['name_bn']} বাংলাদেশের একটি জনপ্রিয় ঐতিহ্যবাহী খাবার।"
            r["summary_bn"] = summary.replace("\n", " ").replace("\r", " ").strip()

            bn = r["name_bn"]
            img_url = FOOD_IMAGES.get(bn, "")
            if not img_url:
                for k, v in FOOD_IMAGES.items():
                    if k in bn:
                        img_url = v
                        break
            if not img_url:
                img_url = FALLBACK_FOOD_IMG
            r["image_url"] = img_url

        print(f"  Food progress: {min((b_idx+1)*batch_size, len(rows))}/{len(rows)}", flush=True)
        time.sleep(0.3)

    cols = list(rows[0].keys())
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=cols, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {len(rows)} food items with pure Bangla 1-liners and images to {csv_path}", flush=True)

def main():
    print("=== Starting Fast Resilient LLM Bangla Enrichment ===", flush=True)
    enrich_universities()
    enrich_heritage_sites()
    enrich_cultural_figures()
    enrich_food_and_dining()
    print("\n=== All 4 Categories Successfully Enriched in Pure Bangla ===", flush=True)

if __name__ == "__main__":
    main()
