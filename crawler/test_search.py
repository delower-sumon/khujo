import requests
import sys
sys.stdout.reconfigure(encoding='utf-8')

terms = ["গুগল", "google", "ফেসবুক", "facebook", "ইউটিউব", "youtube", "উইকিপিডিয়া", "wikipedia"]


for term in terms:
    res = requests.get(f"http://localhost:8000/api/v1/search?q={term}").json()
    kg = res.get("knowledge_graph")
    results = res.get("results", [])
    print(f"\n=== Search Query: '{term}' ===")
    print(f"  Knowledge Graph Matched: {kg['title'] if kg else 'None'}")
    print(f"  Total Results: {len(results)}")
    for r in results[:2]:
        print(f"    • Title: {r['title']}")
        print(f"      URL:   {r['url']}")
        print(f"      Favicon: {r['favicon']}")
