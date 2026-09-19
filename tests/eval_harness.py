import os
import sys
import json
import time
import urllib.request
import urllib.parse
from typing import List, Dict, Any

def score_query_result(query_item: Dict[str, Any], search_results: List[Dict[str, Any]], kg: Any) -> Dict[str, Any]:
    expected = [kw.lower() for kw in query_item.get("expected_keywords", [])]
    ranks = []
    
    # Check if entity matched in Knowledge Graph
    kg_matched = False
    if kg and kg.get("title"):
        kg_title = kg.get("title", "").lower()
        if any(kw in kg_title for kw in expected):
            kg_matched = True

    # Check ranks of matched documents
    for rank, doc in enumerate(search_results, start=1):
        text_corpus = f"{doc.get('title', '')} {doc.get('summary', '')} {doc.get('body', '')} {doc.get('url', '')}".lower()
        if any(kw in text_corpus for kw in expected):
            ranks.append(rank)

    reciprocal_rank = 1.0 / ranks[0] if ranks else (1.0 if kg_matched else 0.0)
    p_at_1 = 1.0 if (ranks and ranks[0] == 1) else (1.0 if kg_matched else 0.0)
    p_at_3 = (len([r for r in ranks if r <= 3]) + (1 if kg_matched else 0)) / 3.0
    p_at_5 = (len([r for r in ranks if r <= 5]) + (1 if kg_matched else 0)) / 5.0

    return {
        "id": query_item.get("id"),
        "query": query_item.get("query"),
        "category": query_item.get("category"),
        "reciprocal_rank": reciprocal_rank,
        "kg_matched": kg_matched,
        "p@1": min(1.0, p_at_1),
        "p@3": min(1.0, p_at_3),
        "p@5": min(1.0, p_at_5),
        "num_results": len(search_results)
    }

def run_evaluation(golden_queries_path: str = None, api_base: str = "http://localhost:8000", save_baseline: bool = True) -> Dict[str, Any]:
    if golden_queries_path is None:
        golden_queries_path = os.path.join(os.path.dirname(__file__), "golden_queries.json")
        
    with open(golden_queries_path, "r", encoding="utf-8") as f:
        queries = json.load(f)

    print(f"Loaded {len(queries)} evaluation queries from {golden_queries_path}")
    
    results = []
    category_scores = {}

    for q_item in queries:
        query_str = q_item.get("query", "")
        cat = q_item.get("category", "general")
        if cat not in category_scores:
            category_scores[cat] = {"count": 0, "mrr_sum": 0.0, "p1_sum": 0.0}

        search_results = []
        kg_data = None

        # Query live API
        try:
            url = f"{api_base}/api/v1/search?q={urllib.parse.quote(query_str)}&limit=10"
            req = urllib.request.Request(url, headers={"User-Agent": "KhujoEvalHarness/1.0"})
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                if resp.status == 200:
                    payload = json.loads(resp.read().decode("utf-8"))
                    search_results = payload.get("results", [])
                    kg_data = payload.get("knowledge_graph")
        except Exception:
            # Fallback to empty if offline
            pass

        scored = score_query_result(q_item, search_results, kg_data)
        results.append(scored)

        category_scores[cat]["count"] += 1
        category_scores[cat]["mrr_sum"] += scored["reciprocal_rank"]
        category_scores[cat]["p1_sum"] += scored["p@1"]

    total = len(results) or 1
    mrr = sum(r["reciprocal_rank"] for r in results) / total
    mean_p1 = sum(r["p@1"] for r in results) / total
    mean_p3 = sum(r["p@3"] for r in results) / total
    mean_p5 = sum(r["p@5"] for r in results) / total
    kg_rate = sum(1 for r in results if r["kg_matched"]) / total

    breakdown = {}
    for cat, stats in category_scores.items():
        cnt = stats["count"] or 1
        breakdown[cat] = {
            "count": stats["count"],
            "mrr": round(stats["mrr_sum"] / cnt, 4),
            "p@1": round(stats["p1_sum"] / cnt, 4)
        }

    metrics = {
        "total_queries": len(queries),
        "mrr": round(mrr, 4),
        "mean_p@1": round(mean_p1, 4),
        "mean_p@3": round(mean_p3, 4),
        "mean_p@5": round(mean_p5, 4),
        "kg_resolution_rate": round(kg_rate, 4),
        "category_breakdown": breakdown
    }

    print("\n============================================================")
    print("KHUJO RETRIEVAL EVALUATION RESULTS")
    print("============================================================")
    print(f"Total Queries Evaluated : {metrics['total_queries']}")
    print(f"Mean Reciprocal Rank (MRR): {metrics['mrr']:.4f}")
    print(f"Precision@1 (P@1)       : {metrics['mean_p@1']:.4f}")
    print(f"Precision@3 (P@3)       : {metrics['mean_p@3']:.4f}")
    print(f"Precision@5 (P@5)       : {metrics['mean_p@5']:.4f}")
    print(f"KG Resolution Rate      : {metrics['kg_resolution_rate'] * 100:.1f}%")
    print("------------------------------------------------------------")
    print("Category Breakdown:")
    for c, s in breakdown.items():
        print(f"  * {c:<16}: MRR={s['mrr']:.4f} | P@1={s['p@1']:.4f} (n={s['count']})")
    print("============================================================\n")

    if save_baseline:
        baseline_file = os.path.join(os.path.dirname(__file__), "baseline.json")
        with open(baseline_file, "w", encoding="utf-8") as f:
            json.dump(metrics, f, ensure_ascii=False, indent=2)
        print(f"Saved baseline metrics to {baseline_file}")

    return metrics

if __name__ == "__main__":
    run_evaluation()

