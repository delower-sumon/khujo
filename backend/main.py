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

        # 2. Lookup documents matching trigrams and only return verified ones
        docs = db.execute(text("""
            SELECT content.document.document_id, content.document.canonical_url, content.document.title, content.document.body_text, content.document.published_at, 
                   core.source.source_name as source
            FROM content.document
            JOIN core.source_record ON content.document.source_record_id = core.source_record.source_record_id
            LEFT JOIN core.source ON core.source_record.source_id = core.source.source_id
            WHERE content.document.state = 'verified'
              AND (content.document.title_normalised % :q OR content.document.body_normalised % :q)
            ORDER BY GREATEST(
                similarity(content.document.title_normalised, :q),
                similarity(content.document.body_normalised, :q)
            ) DESC
            LIMIT :limit OFFSET :offset
        """), {"q": q.strip(), "limit": limit, "offset": offset}).fetchall()

        results = []
        for d in docs:
            results.append({
                "id": str(d[0]),
                "title": d[2] or "Untitled",
                "snippet": (d[3][:200] + "...") if d[3] else "No description available",
                "url": d[1],
                "favicon": None,
                "source": d[5],
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

@app.get("/api/v1/admin/stats")
async def get_admin_stats(db: Session = Depends(get_db)):
    try:
        counts = db.execute(text("""
            SELECT state, count(*) 
            FROM content.document 
            GROUP BY state
        """)).fetchall()
        
        stat_map = {row[0]: row[1] for row in counts}
        
        db_size = db.execute(text("SELECT pg_size_pretty(pg_database_size(current_database()))")).scalar() or "0 B"
        
        return {
            "pending_candidates": stat_map.get("candidate", 0),
            "verified_count": stat_map.get("verified", 0),
            "rejected_count": stat_map.get("rejected", 0),
            "total_documents": sum(stat_map.values()),
            "db_size": db_size
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/admin/candidates")
async def get_candidates(db: Session = Depends(get_db)):
    try:
        docs = db.execute(text("""
            SELECT d.document_id, d.canonical_url, d.title, d.body_text, d.discovered_at, d.document_kind,
                   s.source_name
            FROM content.document d
            LEFT JOIN core.source_record sr ON d.source_record_id = sr.source_record_id
            LEFT JOIN core.source s ON sr.source_id = s.source_id
            WHERE d.state = 'candidate'
            ORDER BY d.discovered_at DESC
            LIMIT 50
        """)).fetchall()
        
        results = []
        for d in docs:
            url = d[1] or ""
            # Extract domain for favicon lookup
            domain = ""
            if "://" in url:
                domain = url.split("://")[1].split("/")[0].replace("www.", "")
            
            results.append({
                "id": str(d[0]),
                "url": url,
                "domain": domain,
                "title": d[2] or "Untitled Document",
                "body": d[3] or "",
                "discovered_at": str(d[4]) if d[4] else None,
                "kind": d[5] or "general",
                "source_name": d[6] or domain
            })
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/admin/verify/{document_id}")
async def verify_document(document_id: str, db: Session = Depends(get_db)):
    try:
        db.execute(text("UPDATE content.document SET state = 'verified' WHERE document_id = :id"), {"id": document_id})
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/admin/reject/{document_id}")
async def reject_document(document_id: str, db: Session = Depends(get_db)):
    try:
        db.execute(text("UPDATE content.document SET state = 'rejected' WHERE document_id = :id"), {"id": document_id})
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/admin/batch_verify")
async def batch_verify(document_ids: List[str], db: Session = Depends(get_db)):
    try:
        if document_ids:
            db.execute(text("UPDATE content.document SET state = 'verified' WHERE document_id = ANY(:ids)"), {"ids": document_ids})
            db.commit()
        return {"success": True, "count": len(document_ids)}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/v1/admin/batch_reject")
async def batch_reject(document_ids: List[str], db: Session = Depends(get_db)):
    try:
        if document_ids:
            db.execute(text("UPDATE content.document SET state = 'rejected' WHERE document_id = ANY(:ids)"), {"ids": document_ids})
            db.commit()
        return {"success": True, "count": len(document_ids)}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
