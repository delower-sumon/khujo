#!/usr/bin/env python3
"""
fix_village_spellings.py - Fix systematic transliteration & orthographic errors in Bangladesh village master data.

Addresses the 5 core linguistic rules identified in BBS English-to-Bangla transliteration:
  1. Word-initial ড় / ঢ় prohibition: No Bangla word begins with ড় or ঢ়.
     (e.g., ড়াজাপুর -> রাজাপুর, ড়াঘুনাথপুর -> রঘুনাথপুর, ঢপাখালি -> ধোপাখালী).
  2. Word-initial মূর্ধন্য-ণ prohibition: No Bangla word begins with ণ.
     (e.g., ণাতুন -> নতুন, ণালধা -> নলধা, ণালুয়া -> নলুয়া, ণয়াপাড়া -> নয়াপাড়া, ণলবুনিয়া -> নলবুনিয়া).
  3. Toponymic Suffix standardization:
     - ...পারা -> ...পাড়া (বারুইপারা -> বারুইপাড়া, কান্দাপারা -> কান্দাপাড়া)
     - ...দাঙ্গা -> ...ডাঙ্গা (বালিয়াডাঙ্গা, মাঝিডাঙ্গা, সোনাডাঙ্গা, নোনাডাঙ্গা)
     - ...কাতি / ...কাথি -> ...কাঠি (দত্তকাঠি, আতাইকাঠি, গোপালকাঠি, চুলকাঠি)
     - ...নাগার -> ...নগর (রামনগর, কৃষ্ণনগর, আখাইনগর)
     - ...গাছহি -> ...গাছি (জয়গাছি, সাতগাছিয়া)
     - ...খালি -> ...খালী (গোয়ালখালী, ধোপাখালী, কাটাখালী, বেতখালী, বাদখালী)
     - ...বারি -> ...বাড়ি (কালাবাড়ি, ফুলবাড়ি)
  4. Compound prefixes & common phonetic distortions:
     - ছহতা -> ছোট (ছহতা ড়াঘুনাথপুর -> ছোট রঘুনাথপুর)
     - বারা / বাড়া (when en='Bara ...') -> বড় (বড় বাঁশবাড়িয়া, বড় চাঁদপুর, বড় পাইকপাড়া)
     - ছাক -> চক (চক বড় নলবুনিয়া)
     - ছার -> চর
     - উততার -> উত্তর, ডাক্খিন -> দক্ষিণ, পুর্বা -> পূর্ব, পাসছিম -> পশ্চিম
     - বিশ্নুপুর -> বিষ্ণুপুর, গবিন্দাপুর -> গোবিন্দপুর, শুলতানপুর -> সুলতানপুর
     - ফাতেপুর -> ফতেপুর, কিস্মাত -> কিসমত, হালিশাহার -> হালিশহর
     - ডাতটাকাতি -> দত্তকাঠি, কন্দালা -> কোন্দলা, ডাশ্মিন্সা -> দাশমিন্সা
     - ঢুমকালিপুর -> ধুমকালীপুর, ছাপার্কউল -> চাপারকুল, করামারা -> কোড়ামারা
     - শাহাস্পুর -> সাহসপুর, শাজখালি -> সাজোখালী, মউযারদাঙ্গা -> মৌজারডাঙ্গা
  5. Union Name Crosswalk:
     Maps union_name_bn against authentic 4,540 unions from base_hierarchy.csv
     (e.g., 'Rakhalgachi Union' -> 'রাখালগাছি', 'Bamorta' -> 'বেমরতা').
"""

import os
import re
import csv
import sys
from pathlib import Path
from typing import Dict, Tuple

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

BASE_DIR = Path(__file__).resolve().parent.parent.parent
MASTER_CSV = BASE_DIR / "crawler" / "geo_pipeline" / "data" / "bangladesh_villages_master.csv"
BASE_HIERARCHY_CSV = BASE_DIR / "crawler" / "geo_pipeline" / "data" / "base_hierarchy.csv"
BACKUP_CSV = BASE_DIR / "crawler" / "geo_pipeline" / "data" / "bangladesh_villages_master.backup.csv"

# Load authentic unions from base_hierarchy.csv
def load_union_crosswalk() -> Dict[str, str]:
    union_map = {}
    if not BASE_HIERARCHY_CSV.exists():
        return union_map
    with open(BASE_HIERARCHY_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            if r.get("place_type") == "Union":
                name_en = r.get("name_en", "").strip().lower()
                name_bn = r.get("name_bn", "").strip()
                if name_en and name_bn:
                    # Clean english key
                    clean_en = re.sub(r"\b(union|up|sadar)\b", "", name_en).strip()
                    clean_en = re.sub(r"[^a-z0-9]", "", clean_en)
                    union_map[clean_en] = name_bn
                    # Also raw key
                    raw_clean = re.sub(r"[^a-z0-9]", "", name_en)
                    union_map[raw_clean] = name_bn
    return union_map

UNION_MAP = load_union_crosswalk()

# Exact overrides given by the user in prompt
EXACT_NAME_OVERRIDES = {
    "chhota raghunathpur": "ছোট রঘুনাথপুর",
    "chitali": "চিতলী",
    "dattakati": "দত্তকাঠি",
    "dhanaganti": "ধানাগান্তি",
    "fatepur": "ফতেপুর",
    "joygachhi": "জয়গাছি",
    "kalabari": "কালাবাড়ি",
    "kapali bandar": "কাপালী বন্দর",
    "khalkulia": "খালকুলিয়া",
    "khara sambal": "খারা সাম্বল",
    "khasbati": "খাসবাটি",
    "kondala": "কোন্দলা",
    "mouzardanga": "মৌজারডাঙ্গা",
    "rajapur": "রাজাপুর",
    "ramchandrapur": "রামচন্দ্রপুর",
    "ramnagar satgachhia": "রামনগর সাতগাছিয়া",
    "sultanpur": "সুলতানপুর",
    "kuliadair": "কুলিয়াডাইর",
    "bishnupur": "বিষ্ণুপুর",
    "dashminsa": "দাশমিন্সা",
    "gobindapur": "গোবিন্দপুর",
    "halishahar": "হালিশহর",
    "khalishpur": "খালিশপুর",
    "dhumkalipur": "ধুমকালীপুর",
    "kismat halishahar": "কিসমত হালিশহর",
    "chaparkul": "চাপারকুল",
    "koramara": "কোড়ামারা",
    "par koramara": "পার কোড়ামারা",
    "sahaspur": "সাহসপুর",
    "beshargati": "বেশারগাতি",
    "koyekha": "কয়েখা",
    "sajokhali": "সাজোখালী",
    "dingsaipara": "ডিংসাইপাড়া",
    "ko bishnupur": "ক বিষ্ণুপুর",
    "ko koramara": "ক কোড়ামারা",
    "mandra": "মান্দ্রা",
    "mulghar": "মূলঘর",
    "shekhra": "শেখড়া",
    "nagarmandra": "নগরমান্দ্রা",
    "badokhali": "বাদখালী",
    "paikpara": "পাইকপাড়া",
    "bara singa": "বড় শিংগা",
    "chhota singa": "ছোট শিংগা",
    "abdul rasulpur": "আব্দুল রসুলপুর",
    "baliadanga": "বালিয়াডাঙ্গা",
    "bara banshbaria": "বড় বাঁশবাড়িয়া",
    "bara chandpur": "বড় চাঁদপুর",
    "basurabad": "বাসুড়াবাদ",
    "chak bara nalbunia": "চক বড় নলবুনিয়া",
    "chak chhota nalbunia": "চক ছোট নলবুনিয়া",
    "chak narasingha datterber": "চক নরসিংহ দত্তেরবেড়",
    "chak panchamalarber": "চক পঞ্চামলারবেড়",
    "pc dema": "পিসি ডেমা",
    "dema": "ডেমা",
    "hedayetpur": "হেদায়েতপুর",
    "kalia": "কালিয়া",
    "kashimpur": "কাশিমপুর",
    "khegraghat": "খেগড়াঘাট",
    "mostafapur": "মোস্তফাপুর",
    "sarkardanga": "সরকারডাঙ্গা",
    "alukdia": "আলুকদিয়া",
    "ataikathi": "আতাইকাঠি",
    "baniaganti": "বানিয়াগান্তি",
    "betkhali": "বেতখালী",
    "bhatchhala": "ভাতছালা",
    "pashchim depara": "পশ্চিম ডেপাড়া",
    "purba depara": "পূর্ব ডেপাড়া",
    "gabarkhali": "গাবরখালী",
    "gaokhali": "গাওখালী",
    "gopalkati": "গোপালকাঠি",
    "gotapara": "গোটাপাড়া",
    "kaldia": "কালদিয়া",
    "keshabpur": "কেশবপুর",
    "kananpur": "কাননপুর",
    "kandapara": "কান্দাপাড়া",
    "mukkhait": "মুক্ষাইত",
    "nataikhali": "নাতাইখালী",
    "noapara": "নয়াপাড়া",
    "par noapara": "পার নয়াপাড়া",
    "pashchimbhag": "পশ্চিমভাগ",
    "patilakhali": "পাতিলাখালী",
    "afra": "আফ্রা",
    "bajua": "বাজুয়া",
    "raghunathpur": "রঘুনাথপুর",
    "beneganti": "বেনেগান্তি",
    "chanpatala": "চানপাতালা",
    "jatrapur": "যাত্রাপুর",
    "kaitpara": "কাইতপাড়া",
    "khalshi": "খালশি",
    "panchali": "পাঞ্চালী",
    "komarpur": "কোমরপুর",
    "masidpur": "মসজিদপুর",
    "utkul": "উতকুল",
    "bade karapara": "বাদে কারাপাড়া",
    "bagmara": "বাগমারা",
    "dari taluk": "ডারি তালুক",
    "dewanbati": "দেওয়ানবাটি",
    "gobardia": "গোবর্ধনদিয়া",
    "gomati": "গোমতী",
    "gujihati": "গুজিহাটি",
    "karapara": "কারাপাড়া",
    "kathal": "কাঁঠাল",
    "kathi": "কাঠি",
    "katua": "কাটুয়া",
    "krishnanagar": "কৃষ্ণনগর",
    "magra": "মাগরা",
    "majhidanga": "মাঝিডাঙ্গা",
    "mirzapur": "মির্জাপুর",
    "nonadanga": "নোনাডাঙ্গা",
    "patorpara": "পাতরপাড়া",
    "phultala": "ফুলতলা",
    "polghat": "পুলঘাট",
    "putimari": "পুঁটিমারী",
    "radhaballabh": "রাধাবল্লভ",
    "sabekdanga": "সাবেকডাঙ্গা",
    "shingrai": "শিংড়াই",
    "bhatta baliaghata": "ভাট্টা বলিয়াঘাটা",
    "chulkati": "চুলকাঠি",
    "churamani": "চূড়ামণি",
    "dakkhin khanpur": "দক্ষিণ খানপুর",
    "hakimpur": "হাকিমপুর",
    "jugidanga": "জুগীডাঙ্গা",
    "kanakpur": "কনকপুর",
    "kismat bhatta": "কিসমত ভাট্টা",
    "ranajitpur": "রণজিৎপুর",
    "sonadanga": "সোনাডাঙ্গা",
    "uttar khanpur": "উত্তর খানপুর",
    "bara paikpara": "বড় পাইকপাড়া",
    "bhatpara": "ভাটপাড়া",
    "karakhali": "কারাখালি",
    "chhota paikpara": "ছোট পাইকপাড়া",
    "dari rasulpur": "ডারি রসুলপুর",
    "karari": "করারি",
    "khudra chaksree": "ক্ষুদ্র চাকশ্রী",
    "rasulpur": "রসুলপুর",
    "sugandhi": "সুগন্ধী",
    "sunagar": "সুনগর",
    "syedpur": "সৈয়দপুর",
    "badukhali": "বাদুখালী",
    "barakpur": "বরাকপুর",
    "baruidanga": "বারুইডাঙ্গা",
    "chunokhola": "চুনখোলা",
    "fulbari": "ফুলবাড়ি",
    "fulmagra": "ফুলমাগরা",
    "ghugmukhali": "ঘুগমুখালী",
    "katakhali": "কাটাখালী",
}


def clean_union_name(union_en: str, current_bn: str) -> str:
    """Normalize and fix union names against authentic hierarchy registry."""
    if not union_en:
        return current_bn
    key = re.sub(r"\b(union|up|sadar)\b", "", union_en.lower()).strip()
    key = re.sub(r"[^a-z0-9]", "", key)
    if key in UNION_MAP:
        res = UNION_MAP[key]
        return res.replace("বিষ্ণপুর", "বিষ্ণুপুর")
    
    # Fallback to current with grammar fixes
    clean_bn = current_bn
    if clean_bn.endswith(" Union"):
        clean_bn = clean_bn[:-6].strip()
    if clean_bn.endswith("পারা"):
        clean_bn = clean_bn[:-4] + "পাড়া"
    if clean_bn.startswith("ড়"):
        clean_bn = "র" + clean_bn[1:]
    if clean_bn.startswith("ণ"):
        clean_bn = "ন" + clean_bn[1:]
    clean_bn = clean_bn.replace("বিষ্ণপুর", "বিষ্ণুপুর")
    return clean_bn


def normalize_village_name(bn: str, en: str = "") -> str:
    """Apply systematic phonotactic, orthographic and toponymic grammar rules."""
    if not bn:
        return bn

    en_key = en.strip().lower()
    if en_key in EXACT_NAME_OVERRIDES:
        return EXACT_NAME_OVERRIDES[en_key]

    s = bn.strip()
    words = s.split(" ")
    fixed_words = []

    en_words = en.strip().split(" ") if en else []

    for idx, w in enumerate(words):
        en_w = en_words[idx].lower() if idx < len(en_words) else ""

        # -------------------------------------------------------------
        # Rule 1: Initial ড় / ঢ় Prohibition (no word starts with ড়/ঢ়)
        # -------------------------------------------------------------
        if w.startswith("ড়"):
            w = "র" + w[1:]
        elif w.startswith("ঢ়"):
            w = "ধ" + w[1:] if ("খালি" in w or "পারা" in w) else ("ঢ" + w[1:])

        # -------------------------------------------------------------
        # Rule 2: Initial ণ Prohibition (no word starts with ণ)
        # -------------------------------------------------------------
        if w.startswith("ণ"):
            w = "ন" + w[1:]

        # -------------------------------------------------------------
        # Rule 4: Compound Modifiers & BBS Prefixes
        # -------------------------------------------------------------
        if w in ("ছহতা", "ছহতাহ", "ছোটহ"):
            w = "ছোট"
        elif w in ("বারা", "বাড়া") and (en_w.startswith("bara") or en_key.startswith("bara")):
            w = "বড়"
        elif w in ("ছাক", "চাক") and en_w == "chak":
            w = "চক"
        elif w in ("ছার",) and en_w == "char":
            w = "চর"
        elif w == "উততার":
            w = "উত্তর"
        elif w in ("ডাক্খিন", "দাখিন"):
            w = "দক্ষিণ"
        elif w in ("পুর্বা", "পুর্ব"):
            w = "পূর্ব"
        elif w in ("পাসছিম", "পসচিম"):
            w = "পশ্চিম"
        elif w == "মাদধ্যা":
            w = "মধ্য"
        elif w == "বিশ্নুপুর":
            w = "বিষ্ণুপুর"
        elif w == "গবিন্দাপুর":
            w = "গোবিন্দপুর"
        elif w == "শুলতানপুর":
            w = "সুলতানপুর"
        elif w == "ফাতেপুর":
            w = "ফতেপুর"
        elif w == "কিস্মাত":
            w = "কিসমত"
        elif w == "হালিশাহার":
            w = "হালিশহর"
        elif w == "মউযারদাঙ্গা":
            w = "মৌজারডাঙ্গা"
        elif w == "ডাতটাকাতি":
            w = "দত্তকাঠি"
        elif w == "কন্দালা":
            w = "কোন্দলা"
        elif w == "ঢানাগান্তি":
            w = "ধানাগান্তি"
        elif w == "ছাপার্কউল":
            w = "চাপারকুল"
        elif w == "করামারা":
            w = "কোড়ামারা"
        elif w == "ডাশ্মিন্সা":
            w = "দাশমিন্সা"
        elif w == "ঢুমকালিপুর":
            w = "ধুমকালীপুর"
        elif w == "শাহাস্পুর":
            w = "সাহসপুর"
        elif w == "শাজখালি":
            w = "সাজোখালী"
        elif w == "মাশিদপুর":
            w = "মসজিদপুর"
        elif w == "ক্রিশ্নানাগার":
            w = "কৃষ্ণনগর"
        elif w == "ছূরামানি":
            w = "চূড়ামণি"
        elif w == "চুলকাতি":
            w = "চুলকাঠি"

        # -------------------------------------------------------------
        # Rule 3 & 5: Toponymic Suffixes
        # -------------------------------------------------------------
        # ...পারা -> ...পাড়া
        if w.endswith("পারা") and len(w) > 4:
            w = w[:-4] + "পাড়া"
        elif w == "পারা":
            w = "পাড়া"

        # ...দাঙ্গা -> ...ডাঙ্গা
        if w.endswith("দাঙ্গা") and len(w) > 5:
            w = w[:-5] + "ডাঙ্গা"
        elif w == "দাঙ্গা":
            w = "ডাঙ্গা"

        # ...নাগার -> ...নগর
        if w.endswith("নাগার") and len(w) > 5:
            w = w[:-5] + "নগর"

        # ...গাছহি -> ...গাছি
        if w.endswith("গাছহি"):
            w = w[:-5] + "গাছি"
        elif w.endswith("শাতগাছহিয়া"):
            w = w[:-10] + "সাতগাছিয়া"

        # ...কাতি / ...কাথি -> ...কাঠি
        if (w.endswith("কাতি") or w.endswith("কাথি")) and len(w) > 4:
            w = w[:-4] + "কাঠি"

        # ...খালি -> ...খালী
        if w.endswith("খালি") and len(w) > 4:
            w = w[:-4] + "খালী"

        # ...বারি -> ...বাড়ি
        if w.endswith("বারি") and len(w) > 4:
            w = w[:-4] + "বাড়ি"

        fixed_words.append(w)

    res = " ".join(fixed_words)

    # General regex cleanup for any internal missed tokens
    res = re.sub(r"ছহতা", "ছোট", res)
    res = re.sub(r"ছাক", "চক", res)
    res = re.sub(r"\bছার\b", "চর", res)
    res = re.sub(r"\bপারা\b", "পাড়া", res)
    res = re.sub(r"পারা$", "পাড়া", res)
    res = re.sub(r"দাঙ্গা$", "ডাঙ্গা", res)
    res = re.sub(r"নাগার$", "নগর", res)
    res = re.sub(r"বিষ্ণপুর", "বিষ্ণুপুর", res)

    return res


def main():
    if not MASTER_CSV.exists():
        print(f"Error: {MASTER_CSV} not found!")
        return

    print("=" * 75)
    print(" FIXING BANGLADESH VILLAGE SPELLINGS & TOPONYMIC GRAMMAR")
    print("=" * 75)

    with open(MASTER_CSV, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = reader.fieldnames

    print(f"Loaded {len(rows):,} village records.")

    # Create backup first
    if not BACKUP_CSV.exists():
        print(f"Creating safety backup -> {BACKUP_CSV.name} ...")
        with open(BACKUP_CSV, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        print("Backup created.")

    fixed_name_count = 0
    fixed_union_count = 0

    for r in rows:
        old_name = r.get("name_bn", "")
        old_union = r.get("union_name_bn", "")
        name_en = r.get("name_en", "")
        union_en = r.get("union_name_en", "")

        new_name = normalize_village_name(old_name, name_en)
        new_union = clean_union_name(union_en, old_union)

        if new_name != old_name:
            r["name_bn"] = new_name
            fixed_name_count += 1

        if new_union != old_union:
            r["union_name_bn"] = new_union
            fixed_union_count += 1

    # Overwrite master CSV
    with open(MASTER_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nProcessing Complete:")
    print(f"  • Fixed Village Names (name_bn):        {fixed_name_count:,} / {len(rows):,} ({fixed_name_count/len(rows)*100:.1f}%)")
    print(f"  • Fixed Union Names (union_name_bn):     {fixed_union_count:,} / {len(rows):,} ({fixed_union_count/len(rows)*100:.1f}%)")
    print("-" * 75)
    print("Verification of User's Specific Lines (Lines 33 to 50):")
    for r in rows[32:50]:
        print(f"  • {r['name_en']} -> {r['name_bn']} | Union: {r['union_name_bn']}")
    print("=" * 75)


if __name__ == "__main__":
    main()
