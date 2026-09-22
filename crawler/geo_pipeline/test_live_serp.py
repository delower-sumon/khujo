import urllib.request
import urllib.parse
import json

def test_search(query):
    url = f"http://127.0.0.1:8000/api/v1/search?q={urllib.parse.quote(query)}"
    req = urllib.request.Request(url, headers={"User-Agent": "KhujoTester/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(f"==================================================")
            print(f"QUERY: '{query}' (HTTP {resp.status})")
            kg = data.get("knowledge_graph")
            if kg:
                print("  [KNOWLEDGE GRAPH CARD]")
                print(f"    Title: {kg.get('title')}")
                print(f"    Description: {kg.get('description', '')[:120]}...")
                print(f"    Image URL: {kg.get('image_url')}")
                print(f"    Related: {len(kg.get('related_entities', []))} entities")
            else:
                print("  [NO KNOWLEDGE GRAPH CARD]")
            results = data.get("results", [])
            print(f"  Web Results: {len(results)} found")
    except Exception as e:
        print(f"Error querying '{query}': {e}")

def test_suggestion(prefix):
    url = f"http://127.0.0.1:8000/api/v1/suggestions?q={urllib.parse.quote(prefix)}"
    req = urllib.request.Request(url, headers={"User-Agent": "KhujoTester/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(f"\nSUGGESTIONS for '{prefix}': {data}")
    except Exception as e:
        print(f"Error suggestions for '{prefix}': {e}")

if __name__ == "__main__":
    print("--- TESTING LIVE SEARCH ENGINE API ---")
    test_search("মীর দেওহাটা")
    test_search("Mir Deohata")
    test_search("কলেজপাড়া")
    test_search("College para")
    test_search("কুমিল্লা")
    test_search("Debidwar")
    test_search("সুলতানপুর")
    test_search("রাখালগাছি")
    test_search("Debidwar")
    test_search("Bagerhat")

    print("\n--- TESTING AUTOCOMPLETE SUGGESTIONS ---")
    test_suggestion("বাগের")
    test_suggestion("দেবি")
    test_suggestion("খুল")
