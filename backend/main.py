from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional
import os
import re
from app.database import get_db

app = FastAPI(title="Khujo API", description="Bangladesh's Own Search Engine API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Welcome to Khujo API - Bangladesh's Own Search Engine"}

@app.get("/api/v1/search")
async def search(q: str, limit: int = 10, offset: int = 0, db: Session = Depends(get_db)):
    try:
        if not q or len(q.strip()) < 1:
            return {"query": q, "results": [], "total": 0}

        # 1. First, lookup knowledge graph entities (districts, people, etc)
        entity_res = db.execute(text("""
            SELECT e.entity_id, e.display_name, e.summary, n.normalised_name
            FROM core.entity_name n
            JOIN core.entity e ON n.entity_id = e.entity_id
            WHERE n.normalised_name % :q OR n.normalised_name ILIKE :q_like
            ORDER BY similarity(n.normalised_name, :q) DESC
            LIMIT 1
        """), {"q": q.strip(), "q_like": f"%{q.strip()}%"}).fetchone()

        knowledge_graph = None
        if entity_res:
            knowledge_graph = {
                "id": str(entity_res[0]),
                "title": entity_res[1],
                "description": entity_res[2] or f"{entity_res[1]} সম্পর্কিত তথ্য",
                "sources": []
            }

        # 2. Search content.document for web and news results using trigram/ILIKE
        doc_res = db.execute(text("""
            SELECT document_id, canonical_url, title, body_text, document_kind
            FROM content.document
            WHERE title_normalised % :q OR body_normalised % :q OR title_normalised ILIKE :q_like
            ORDER BY similarity(title_normalised, :q) DESC, discovered_at DESC
            LIMIT :limit OFFSET :offset
        """), {"q": q.strip(), "q_like": f"%{q.strip()}%", "limit": limit, "offset": offset}).fetchall()

        results = []
        for d in doc_res:
            results.append({
                "id": str(d[0]),
                "title": d[2] or "Untitled",
                "snippet": (d[3][:200] + "...") if d[3] else "No description available",
                "url": d[1],
                "favicon": None,
                "source": d[4],
                "type": "document"
            })

        return {
            "query": q,
            "results": results,
            "total": len(results),
            "knowledge_graph": knowledge_graph
        }
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/suggestions")
async def suggestions(q: str, limit: int = 5, db: Session = Depends(get_db)):
    try:
        if not q or len(q.strip()) < 1:
            return []

        # Query search.suggestion with pg_trgm similarity
        res = db.execute(text("""
            SELECT phrase 
            FROM search.suggestion 
            WHERE phrase_normalised % :q OR phrase_normalised ILIKE :q_like
            ORDER BY similarity(phrase_normalised, :q) DESC, popularity_score DESC, priority DESC
            LIMIT :limit
        """), {"q": q.strip(), "q_like": f"%{q.strip()}%", "limit": limit}).fetchall()
        
        return [r[0] for r in res]

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
