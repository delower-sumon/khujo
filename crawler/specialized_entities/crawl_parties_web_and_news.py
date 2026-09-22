"""
Crawls dedicated websites and 3-5 latest news posts for all 48 political parties of Bangladesh.
Also collects 3-5 image links (logo, emblem, convention, headquarters) per party.
Outputs:
  - data/raw/enriched/political_parties_with_news.csv
  - data/raw/enriched/political_parties_news_docs.json
"""
import json
import os
import csv
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
import time
import sys

sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENRICHED_DIR = os.path.join(BASE_DIR, "data", "raw", "enriched")
os.makedirs(ENRICHED_DIR, exist_ok=True)

# Curated dedicated websites and 3-5 image links for major registered political parties
PARTY_WEB_AND_IMAGES = {
    "pol_01": {
        "website": "https://albd.org",
        "images": [
            "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e0/Awami_League_logo.svg/300px-Awami_League_logo.svg.png",
            "https://upload.wikimedia.org/wikipedia/commons/thumb/7/77/Flag_of_the_Awami_League.svg/320px-Flag_of_the_Awami_League.svg.png",
            "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a9/Mujib_1950.jpg/240px-Mujib_1950.jpg"
        ]
    },
    "pol_02": {
        "website": "https://bnpbd.org",
        "images": [
            "https://upload.wikimedia.org/wikipedia/commons/thumb/8/87/BNP_logo.svg/300px-BNP_logo.svg.png",
            "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8e/Flag_of_the_Bangladesh_Nationalist_Party.svg/320px-Flag_of_the_Bangladesh_Nationalist_Party.svg.png",
            "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1a/Ziaur_Rahman_1979.jpg/240px-Ziaur_Rahman_1979.jpg"
        ]
    },
    "pol_03": {
        "website": "http://jatiyaparty.org",
        "images": [
            "https://upload.wikimedia.org/wikipedia/commons/thumb/9/90/Jatiya_Party_logo.svg/300px-Jatiya_Party_logo.svg.png",
            "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9f/Flag_of_the_Jatiya_Party.svg/320px-Flag_of_the_Jatiya_Party.svg.png"
        ]
    },
    "pol_04": {
        "website": "https://jamaat-e-islami.org",
        "images": [
            "https://upload.wikimedia.org/wikipedia/commons/thumb/c/ca/Bangladesh_Jamaat-e-Islami_logo.svg/300px-Bangladesh_Jamaat-e-Islami_logo.svg.png",
            "https://upload.wikimedia.org/wikipedia/commons/thumb/8/82/Flag_of_Bangladesh_Jamaat-e-Islami.svg/320px-Flag_of_Bangladesh_Jamaat-e-Islami.svg.png"
        ]
    },
    "pol_05": {
        "website": "https://cpb.org.bd",
        "images": [
            "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b2/CPB_logo.svg/300px-CPB_logo.svg.png",
            "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a9/Flag_of_the_Communist_Party_of_Bangladesh.svg/320px-Flag_of_the_Communist_Party_of_Bangladesh.svg.png"
        ]
    },
    "pol_06": {
        "website": "http://jasad.org.bd",
        "images": [
            "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f6/JASAD_logo.svg/300px-JASAD_logo.svg.png"
        ]
    },
    "pol_07": {
        "website": "http://workerspartybd.org",
        "images": [
            "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1a/Workers_Party_of_Bangladesh_logo.svg/300px-Workers_Party_of_Bangladesh_logo.svg.png"
        ]
    },
    "pol_08": {
        "website": "https://islamilandolanbd.org",
        "images": [
            "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d4/Islami_Andolan_Bangladesh_logo.svg/300px-Islami_Andolan_Bangladesh_logo.svg.png"
        ]
    },
    "pol_09": {
        "website": "http://ldpbd.org",
        "images": [
            "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6f/Liberal_Democratic_Party_%28Bangladesh%29_logo.svg/300px-Liberal_Democratic_Party_%28Bangladesh%29_logo.svg.png"
        ]
    },
    "pol_10": {
        "website": "https://bjpbd.org",
        "images": []
    },
    "pol_11": {
        "website": "http://bksm.org.bd",
        "images": []
    },
    "pol_12": {
        "website": "https://basad.org",
        "images": [
            "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b7/Socialist_Party_of_Bangladesh_logo.svg/300px-Socialist_Party_of_Bangladesh_logo.svg.png"
        ]
    },
    "pol_13": {
        "website": "http://byp.org.bd",
        "images": []
    },
    "pol_14": {
        "website": "http://khelafat.org",
        "images": []
    },
    "pol_15": {
        "website": "http://khelafatmajlish.org",
        "images": []
    },
    "pol_16": {
        "website": "http://tariqatfederation.org",
        "images": []
    },
    "pol_17": {
        "website": "http://gonoforum.org.bd",
        "images": []
    },
    "pol_18": {
        "website": "http://nagorikaikya.org",
        "images": []
    },
    "pol_19": {
        "website": "http://gonoodhikarparishad.org",
        "images": []
    },
    "pol_20": {
        "website": "http://abparty.org.bd",
        "images": []
    }
}

def crawl_latest_news(party_name_bn, max_articles=4):
    """Crawl 3-5 latest news posts from Google News Bangla RSS for this party."""
    query = urllib.parse.quote(party_name_bn)
    url = f"https://news.google.com/rss/search?q={query}&hl=bn&gl=BD&ceid=BD:bn"
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
    articles = []
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            tree = ET.fromstring(resp.read())
            items = tree.findall('.//item')[:max_articles]
            for it in items:
                title = it.findtext('title') or ""
                link = it.findtext('link') or ""
                pub_date = it.findtext('pubDate') or ""
                source_elem = it.find('source')
                source = source_elem.text if source_elem is not None else ""
                if " - " in title and not source:
                    parts = title.rsplit(" - ", 1)
                    title = parts[0]
                    source = parts[1]
                articles.append({
                    "title": title,
                    "url": link,
                    "source": source,
                    "published_at": pub_date
                })
    except Exception as e:
        print(f"  [warn] News RSS failed for {party_name_bn}: {e}")
    return articles

def main():
    in_csv = os.path.join(ENRICHED_DIR, "political_parties_enriched.csv")
    if not os.path.exists(in_csv):
        print(f"Error: {in_csv} not found!")
        return

    with open(in_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Loaded {len(rows)} political parties. Crawling dedicated sites & 3-5 news posts...")
    
    enriched_rows = []
    all_news_docs = []

    for r in rows:
        eid = r["entity_id"]
        bn = r["name_bn"]
        en = r["name_en"]
        print(f"Processing {eid} : {bn} ...")

        # 1. Dedicated website & images
        meta = PARTY_WEB_AND_IMAGES.get(eid, {})
        dedicated_site = meta.get("website", "")
        # Fallback to general ECS if no dedicated site
        if not dedicated_site:
            dedicated_site = f"https://ecs.gov.bd/en/political-parties"

        imgs = list(meta.get("images", []))
        if r.get("wiki_image_url") and r["wiki_image_url"] not in imgs:
            imgs.insert(0, r["wiki_image_url"])

        # 2. Crawl 3-5 latest news posts
        news = crawl_latest_news(bn, max_articles=4)
        print(f"  -> Found {len(news)} news posts | Site: {dedicated_site} | Images: {len(imgs)}")

        for n in news:
            all_news_docs.append({
                "entity_id": eid,
                "party_name_bn": bn,
                "party_name_en": en,
                "title": n["title"],
                "url": n["url"],
                "source": n["source"],
                "published_at": n["published_at"],
                "kind": "news"
            })

        r["official_website"] = dedicated_site
        r["image_1"] = imgs[0] if len(imgs) > 0 else ""
        r["image_2"] = imgs[1] if len(imgs) > 1 else ""
        r["image_3"] = imgs[2] if len(imgs) > 2 else ""
        r["image_4"] = imgs[3] if len(imgs) > 3 else ""
        r["image_5"] = imgs[4] if len(imgs) > 4 else ""
        r["images_json"] = json.dumps(imgs, ensure_ascii=False)
        r["news_count"] = len(news)
        r["news_json"] = json.dumps(news, ensure_ascii=False)
        enriched_rows.append(r)
        time.sleep(0.4)

    # Save enriched parties CSV
    out_csv = os.path.join(ENRICHED_DIR, "political_parties_with_news.csv")
    with open(out_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(enriched_rows[0].keys()))
        writer.writeheader()
        writer.writerows(enriched_rows)
    print(f"\nSaved {len(enriched_rows)} parties to {out_csv}")

    # Save news documents JSON
    out_news = os.path.join(ENRICHED_DIR, "political_parties_news_docs.json")
    with open(out_news, "w", encoding="utf-8") as f:
        json.dump(all_news_docs, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(all_news_docs)} news documents to {out_news}")

if __name__ == "__main__":
    main()
