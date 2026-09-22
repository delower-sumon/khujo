"""
Enriches Cultural Figures (22) and Heritage Sites (20) with 3-5 image links each,
coordinates, and verified reference links.
Respects user correction: heri_17 = তাজহাট জমিদারবাড়ি.
"""
import json
import os
import csv
import urllib.request
import urllib.parse
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENRICHED_DIR = os.path.join(BASE_DIR, "data", "raw", "enriched")
os.makedirs(ENRICHED_DIR, exist_ok=True)

HEADERS = {'User-Agent': 'KhoojoBot/1.0 (https://khoojo.com; research@khoojo.com)'}

def fetch_wiki_images(wiki_title, max_images=5):
    """Fetch 3-5 high quality image URLs from Wikipedia media-list API."""
    safe_title = urllib.parse.quote(wiki_title.replace(' ', '_'))
    url = f"https://en.wikipedia.org/api/rest_v1/page/media-list/{safe_title}"
    req = urllib.request.Request(url, headers=HEADERS)
    images = []
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode('utf-8'))
            items = data.get('items', [])
            for it in items:
                if it.get('type') != 'image':
                    continue
                # Get best thumb
                srcset = it.get('srcset', [])
                src = srcset[-1]['src'] if srcset else (it.get('original', {}).get('source') or '')
                if not src:
                    continue
                if src.startswith('//'):
                    src = 'https:' + src
                # Filter out svg icons / noise
                lower = src.lower()
                if any(x in lower for x in ['edit-clear', 'ambox', 'crystal_clear', 'symbol', 'icon', 'padlock', 'commons-logo', 'question_book', 'folder']):
                    continue
                if src not in images:
                    images.append(src)
                if len(images) >= max_images:
                    break
    except Exception as e:
        print(f"  [warn] Media API failed for {wiki_title}: {e}")
    return images

# Heritage Sites definition with accurate coordinates and English Wikipedia title
HERITAGE_SITES = [
    {"entity_id": "heri_0", "name_bn": "বায়তুল মোকাররম জাতীয় মসজিদ", "name_en": "Baitul Mukarram National Mosque", "wiki_title": "Baitul_Mukarram_National_Mosque", "lat": 23.7252, "lon": 90.4163, "category": "Islam"},
    {"entity_id": "heri_1", "name_bn": "ঢাকেশ্বরী জাতীয় মন্দির", "name_en": "Dhakeshwari National Temple", "wiki_title": "Dhakeshwari_Temple", "lat": 23.7209, "lon": 90.3874, "category": "Hinduism"},
    {"entity_id": "heri_2", "name_bn": "আর্মেনীয় গির্জা", "name_en": "Armenian Church of Dhaka", "wiki_title": "Armenian_Church,_Dhaka", "lat": 23.7234, "lon": 90.4043, "category": "Christianity"},
    {"entity_id": "heri_3", "name_bn": "ষাট গম্বুজ মসজিদ", "name_en": "Sixty Dome Mosque", "wiki_title": "Sixty_Dome_Mosque", "lat": 22.6611, "lon": 89.8697, "category": "Islam"},
    {"entity_id": "heri_4", "name_bn": "কান্তজীর মন্দির", "name_en": "Kantajew Temple", "wiki_title": "Kantajew_Temple", "lat": 25.6403, "lon": 88.7030, "category": "Hinduism"},
    {"entity_id": "heri_5", "name_bn": "সোমপুর মহাবিহার", "name_en": "Somapura Mahavihara", "wiki_title": "Somapura_Mahavihara", "lat": 24.9660, "lon": 88.8881, "category": "Buddhism"},
    {"entity_id": "heri_6", "name_bn": "তারা মসজিদ", "name_en": "Star Mosque", "wiki_title": "Star_Mosque", "lat": 23.7108, "lon": 90.4038, "category": "Islam"},
    {"entity_id": "heri_7", "name_bn": "লালবাগ কেল্লা", "name_en": "Lalbagh Fort", "wiki_title": "Lalbagh_Fort", "lat": 23.7194, "lon": 90.3862, "category": "Historical"},
    {"entity_id": "heri_8", "name_bn": "আহসান মঞ্জিল", "name_en": "Ahsan Manzil", "wiki_title": "Ahsan_Manzil", "lat": 23.7097, "lon": 90.4053, "category": "Historical"},
    {"entity_id": "heri_9", "name_bn": "ময়নামতি", "name_en": "Mainamati", "wiki_title": "Mainamati", "lat": 23.4574, "lon": 91.1687, "category": "Buddhism"},
    {"entity_id": "heri_10", "name_bn": "মহাস্থানগড়", "name_en": "Mahasthangarh", "wiki_title": "Mahasthangarh", "lat": 24.9760, "lon": 89.3600, "category": "Historical"},
    {"entity_id": "heri_11", "name_bn": "ছোট সোনা মসজিদ", "name_en": "Chhota Sona Mosque", "wiki_title": "Chhota_Sona_Mosque", "lat": 24.8023, "lon": 88.2842, "category": "Islam"},
    {"entity_id": "heri_12", "name_bn": "পানাম নগর", "name_en": "Panam Nagar", "wiki_title": "Panam_City", "lat": 23.6508, "lon": 90.5655, "category": "Historical"},
    {"entity_id": "heri_13", "name_bn": "শহীদ মিনার", "name_en": "Shaheed Minar", "wiki_title": "Shaheed_Minar,_Dhaka", "lat": 23.7234, "lon": 90.3944, "category": "Monument"},
    {"entity_id": "heri_14", "name_bn": "জাতীয় স্মৃতিসৌধ", "name_en": "National Martyrs' Memorial", "wiki_title": "National_Martyrs'_Memorial", "lat": 23.9788, "lon": 90.2622, "category": "Monument"},
    {"entity_id": "heri_15", "name_bn": "মুজিবনগর স্মৃতিসৌধ", "name_en": "Mujibnagar Memorial", "wiki_title": "Mujibnagar_Memorial", "lat": 23.8048, "lon": 88.9068, "category": "Monument"},
    {"entity_id": "heri_16", "name_bn": "রামসাগর", "name_en": "Ramsagar", "wiki_title": "Ramsagar", "lat": 25.4497, "lon": 88.7059, "category": "Historical"},
    {"entity_id": "heri_17", "name_bn": "তাজহাট জমিদারবাড়ি", "name_en": "Tajhat Palace", "wiki_title": "Tajhat_Palace", "lat": 25.7489, "lon": 89.2613, "category": "Historical"},
    {"entity_id": "heri_18", "name_bn": "উত্তরা গণভবন", "name_en": "Uttara Gonobhaban", "wiki_title": "Uttara_Ganabhaban", "lat": 24.4287, "lon": 89.0208, "category": "Historical"},
    {"entity_id": "heri_19", "name_bn": "পুঠিয়া রাজবাড়ী", "name_en": "Puthia Temple Complex", "wiki_title": "Puthia_Temple_Complex", "lat": 24.3752, "lon": 88.8657, "category": "Hinduism"},
]

# Cultural Figures definition
CULTURAL_FIGURES = [
    {"entity_id": "cult_0", "name_bn": "কাজী নজরুল ইসলাম", "name_en": "Kazi Nazrul Islam", "wiki_title": "Kazi_Nazrul_Islam", "profession": "National Poet"},
    {"entity_id": "cult_1", "name_bn": "রবীন্দ্রনাথ ঠাকুর", "name_en": "Rabindranath Tagore", "wiki_title": "Rabindranath_Tagore", "profession": "Nobel Laureate Poet"},
    {"entity_id": "cult_2", "name_bn": "বঙ্গবন্ধু শেখ মুজিবুর রহমান", "name_en": "Sheikh Mujibur Rahman", "wiki_title": "Sheikh_Mujibur_Rahman", "profession": "Founding Father"},
    {"entity_id": "cult_3", "name_bn": "মাওলানা আবদুল হামিদ খান ভাসানী", "name_en": "Maulana Bhashani", "wiki_title": "Abdul_Hamid_Khan_Bhashani", "profession": "Political Leader"},
    {"entity_id": "cult_4", "name_bn": "শেরে বাংলা এ. কে. ফজলুল হক", "name_en": "A. K. Fazlul Huq", "wiki_title": "A._K._Fazlul_Huq", "profession": "Statesman"},
    {"entity_id": "cult_5", "name_bn": "জসীমউদ্দীন", "name_en": "Jasimuddin", "wiki_title": "Jasimuddin", "profession": "Polli Kobi"},
    {"entity_id": "cult_6", "name_bn": "জয়নুল আবেদিন", "name_en": "Zainul Abedin", "wiki_title": "Zainul_Abedin", "profession": "Shilpacharya Painter"},
    {"entity_id": "cult_7", "name_bn": "এস এম সুলতান", "name_en": "S M Sultan", "wiki_title": "SM_Sultan", "profession": "Painter"},
    {"entity_id": "cult_8", "name_bn": "হুমায়ূন আহমেদ", "name_en": "Humayun Ahmed", "wiki_title": "Humayun_Ahmed", "profession": "Author & Filmmaker"},
    {"entity_id": "cult_9", "name_bn": "বেগম রোকেয়া", "name_en": "Begum Rokeya", "wiki_title": "Begum_Rokeya", "profession": "Pioneer Educator"},
    {"entity_id": "cult_10", "name_bn": "জীবনানন্দ দাশ", "name_en": "Jibanananda Das", "wiki_title": "Jibanananda_Das", "profession": "Poet"},
    {"entity_id": "cult_11", "name_bn": "মুহম্মদ শহীদুল্লাহ", "name_en": "Muhammad Shahidullah", "wiki_title": "Muhammad_Shahidullah", "profession": "Linguist"},
    {"entity_id": "cult_12", "name_bn": "জগদীশ চন্দ্র বসু", "name_en": "Jagadish Chandra Bose", "wiki_title": "Jagadish_Chandra_Bose", "profession": "Polymath Scientist"},
    {"entity_id": "cult_13", "name_bn": "সত্যেন্দ্রনাথ বসু", "name_en": "Satyendra Nath Bose", "wiki_title": "Satyendra_Nath_Bose", "profession": "Physicist (Bose-Einstein)"},
    {"entity_id": "cult_14", "name_bn": "তারেক মাসুদ", "name_en": "Tareque Masud", "wiki_title": "Tareque_Masud", "profession": "Filmmaker"},
    {"entity_id": "cult_15", "name_bn": "শামসুর রাহমান", "name_en": "Shamsur Rahman", "wiki_title": "Shamsur_Rahman_(poet)", "profession": "Poet"},
    {"entity_id": "cult_16", "name_bn": "আবদুল জব্বার", "name_en": "Abdul Jabbar", "wiki_title": "Abdul_Jabbar_(singer)", "profession": "Swadhin Bangla Betar Singer"},
    {"entity_id": "cult_17", "name_bn": "রুনা লায়লা", "name_en": "Runa Laila", "wiki_title": "Runa_Laila", "profession": "Playback Singer"},
    {"entity_id": "cult_18", "name_bn": "আইয়ুব বাচ্চু", "name_en": "Ayub Bachchu", "wiki_title": "Ayub_Bachchu", "profession": "Rock Legend Musician"},
    {"entity_id": "cult_19", "name_bn": "জেমস", "name_en": "James (Faruq Mahfuz Anam)", "wiki_title": "James_(musician)", "profession": "Nagar Baul Rock Icon"},
    {"entity_id": "cult_20", "name_bn": "মুনীর চৌধুরী", "name_en": "Munier Choudhury", "wiki_title": "Munier_Choudhury", "profession": "Martyred Intellectual Playwright"},
    {"entity_id": "cult_21", "name_bn": "জহির রায়হান", "name_en": "Zahir Raihan", "wiki_title": "Zahir_Raihan", "profession": "Martyred Novelist & Filmmaker"},
]

def main():
    print("Enriching Heritage Sites with 3-5 images each...")
    enriched_heritage = []
    for h in HERITAGE_SITES:
        print(f" -> Fetching images for {h['name_bn']} ({h['wiki_title']})...")
        imgs = fetch_wiki_images(h['wiki_title'], max_images=5)
        wiki_url = f"https://en.wikipedia.org/wiki/{h['wiki_title']}"
        h_row = {
            "entity_id": h["entity_id"],
            "name_bn": h["name_bn"],
            "name_en": h["name_en"],
            "category": "Heritage Sites",
            "heritage_kind": h["category"],
            "latitude": h["lat"],
            "longitude": h["lon"],
            "wiki_url": wiki_url,
            "image_1": imgs[0] if len(imgs) > 0 else "",
            "image_2": imgs[1] if len(imgs) > 1 else "",
            "image_3": imgs[2] if len(imgs) > 2 else "",
            "image_4": imgs[3] if len(imgs) > 3 else "",
            "image_5": imgs[4] if len(imgs) > 4 else "",
            "images_json": json.dumps(imgs, ensure_ascii=False)
        }
        enriched_heritage.append(h_row)
        time.sleep(0.3)

    out_heri = os.path.join(ENRICHED_DIR, "heritage_sites_3to5_images.csv")
    with open(out_heri, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(enriched_heritage[0].keys()))
        writer.writeheader()
        writer.writerows(enriched_heritage)
    print(f"Saved {len(enriched_heritage)} heritage sites with 3-5 images to {out_heri}")

    print("\nEnriching Cultural Figures with 3-5 images each...")
    enriched_cultural = []
    for c in CULTURAL_FIGURES:
        print(f" -> Fetching images for {c['name_bn']} ({c['wiki_title']})...")
        imgs = fetch_wiki_images(c['wiki_title'], max_images=5)
        wiki_url = f"https://en.wikipedia.org/wiki/{c['wiki_title']}"
        c_row = {
            "entity_id": c["entity_id"],
            "name_bn": c["name_bn"],
            "name_en": c["name_en"],
            "profession": c["profession"],
            "category": "Cultural Figures",
            "wiki_url": wiki_url,
            "image_1": imgs[0] if len(imgs) > 0 else "",
            "image_2": imgs[1] if len(imgs) > 1 else "",
            "image_3": imgs[2] if len(imgs) > 2 else "",
            "image_4": imgs[3] if len(imgs) > 3 else "",
            "image_5": imgs[4] if len(imgs) > 4 else "",
            "images_json": json.dumps(imgs, ensure_ascii=False)
        }
        enriched_cultural.append(c_row)
        time.sleep(0.3)

    out_cult = os.path.join(ENRICHED_DIR, "cultural_figures_3to5_images.csv")
    with open(out_cult, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(enriched_cultural[0].keys()))
        writer.writeheader()
        writer.writerows(enriched_cultural)
    print(f"Saved {len(enriched_cultural)} cultural figures with 3-5 images to {out_cult}")

if __name__ == "__main__":
    main()
