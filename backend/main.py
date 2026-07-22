from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
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

class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    kind: Optional[str] = None
    state: Optional[str] = None

@app.get("/")
async def root():
    return {"message": "Welcome to Khujo API - Bangladesh's Own Search Engine"}

@app.get("/api/v1/search")
async def search(q: str, limit: int = 10, offset: int = 0, db: Session = Depends(get_db)):
    try:
        clean_q = q.strip()
        if not clean_q:
            return {"query": q, "results": [], "total": 0}

        # 1. Lookup knowledge graph entity & all associated transliteration aliases
        entity_res = db.execute(text("""
            SELECT e.entity_id, e.display_name, e.summary
            FROM core.entity_name n
            JOIN core.entity e ON n.entity_id = e.entity_id
            WHERE lower(n.name) = lower(:q) 
               OR n.normalised_name ILIKE :q_like 
               OR e.display_name ILIKE :q_like
            ORDER BY (CASE WHEN lower(n.name) = lower(:q) THEN 1 ELSE 2 END), n.entity_name_id
            LIMIT 1
        """), {"q": clean_q, "q_like": f"%{clean_q}%"}).fetchone()

        knowledge_graph = None
        search_terms = [clean_q]

        if entity_res:
            entity_id, display_name, summary = entity_res
            knowledge_graph = {
                "id": str(entity_id),
                "title": display_name,
                "description": summary or f"{display_name} সম্পর্কিত তথ্য",
                "sources": []
            }
            # Fetch all linked names (Bangla, English, Banglish) for this entity
            aliases = db.execute(text("""
                SELECT normalised_name FROM core.entity_name WHERE entity_id = :eid
            """), {"eid": entity_id}).fetchall()
            for a in aliases:
                if a[0] and a[0] not in search_terms:
                    search_terms.append(a[0])

        # 2. Composite Ranking Engine: Multi-signal scoring algorithm
        # Score = Domain Match (100) + Title Match (80) + Title Sim (20) + Body Sim (5) + Homepage Boost (15)
        docs = db.execute(text("""
            SELECT content.document.document_id, content.document.canonical_url, content.document.title, 
                   content.document.summary, content.document.body_text, content.document.published_at, 
                   core.source.source_name as source,
                   (
                       CASE WHEN EXISTS (
                           SELECT 1 FROM unnest(CAST(:terms AS text[])) term 
                           WHERE content.document.canonical_url ILIKE '%' || term || '%'
                       ) THEN 100.0 ELSE 0.0 END +

                       CASE WHEN EXISTS (
                           SELECT 1 FROM unnest(CAST(:terms AS text[])) term 
                           WHERE lower(content.document.title) ILIKE '%' || lower(term) || '%'
                       ) THEN 80.0 ELSE 0.0 END +

                       (similarity(content.document.title_normalised, :q) * 20.0) +
                       (similarity(content.document.body_normalised, :q) * 5.0) +

                       CASE WHEN CAST(content.document.document_kind AS text) IN ('listing', 'official') THEN 15.0 ELSE 0.0 END

                   ) as final_score
            FROM content.document
            JOIN core.source_record ON content.document.source_record_id = core.source_record.source_record_id
            LEFT JOIN core.source ON core.source_record.source_id = core.source.source_id
            WHERE content.document.state = 'verified'
              AND (
                EXISTS (
                    SELECT 1 FROM unnest(CAST(:terms AS text[])) term 
                    WHERE content.document.title_normalised ILIKE '%' || term || '%'
                       OR content.document.canonical_url ILIKE '%' || term || '%'
                       OR content.document.body_normalised ILIKE '%' || term || '%'
                )
              )
            ORDER BY final_score DESC, content.document.published_at DESC NULLS LAST
            LIMIT :limit OFFSET :offset
        """), {"q": clean_q, "terms": search_terms, "limit": limit, "offset": offset}).fetchall()


        results = []
        for d in docs:
            url = d[1] or ""
            domain = ""
            if "://" in url:
                domain = url.split("://")[1].split("/")[0].replace("www.", "")
            
            favicon_url = f"https://www.google.com/s2/favicons?domain={domain}&sz=32" if domain else None
            snippet = d[3] if d[3] and len(d[3].strip()) > 10 else ((d[4][:220] + "...") if d[4] else "No description available")
            
            results.append({
                "id": str(d[0]),
                "title": d[2] or "Untitled",
                "snippet": snippet,
                "url": url,
                "favicon": favicon_url,
                "source": d[6] or domain,
                "type": "document"
            })

        # 3. Log search query event to search.query_event and update suggestion popularity
        try:
            import hashlib
            q_fp = hashlib.md5(clean_q.encode('utf-8')).hexdigest()
            db.execute(text("""
                INSERT INTO search.query_event (query_fingerprint, normalised_query, result_count, occurred_at, expires_at)
                VALUES (:fp, lower(:q), :rc, now(), now() + interval '30 days')
            """), {"fp": q_fp, "q": clean_q, "rc": len(results)})

            # Update popularity if exists, else insert
            updated_sug = db.execute(text("""
                UPDATE search.suggestion 
                SET popularity_score = popularity_score + 1 
                WHERE phrase_normalised = lower(:q)
            """), {"q": clean_q}).rowcount

            if updated_sug == 0:
                db.execute(text("""
                    INSERT INTO search.suggestion (phrase, phrase_normalised, language_code, priority, popularity_score)
                    VALUES (:q, lower(:q), 'bn', 10, 1)
                """), {"q": clean_q})

            db.commit()
        except Exception as log_err:
            db.rollback()
            pass



        return {
            "query": q,
            "results": results,
            "total": len(results),
            "knowledge_graph": knowledge_graph
        }
    except Exception as e:
        import logging
        logging.error("Search error: %s", str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v1/suggestions")
async def suggestions(q: str, limit: int = 8, db: Session = Depends(get_db)):
    try:
        clean_q = q.strip()
        if not clean_q or len(clean_q) < 1:
            return []

        prefix_like = f"{clean_q}%"
        any_like = f"%{clean_q}%"

        # 1. Fetch from search.suggestion table
        sug_rows = db.execute(text("""
            SELECT phrase 
            FROM search.suggestion 
            WHERE phrase_normalised ILIKE :prefix 
               OR phrase_normalised ILIKE :any 
               OR phrase_normalised % :q
            ORDER BY (CASE WHEN phrase_normalised ILIKE :prefix THEN 1 ELSE 2 END), 
                     popularity_score DESC, priority DESC
            LIMIT :limit
        """), {"q": clean_q, "prefix": prefix_like, "any": any_like, "limit": limit}).fetchall()

        suggestions_set = []
        for r in sug_rows:
            if r[0] and r[0] not in suggestions_set:
                suggestions_set.append(r[0])

        # 2. Enrich from core.entity_name if needed
        if len(suggestions_set) < limit:
            entity_rows = db.execute(text("""
                SELECT name 
                FROM core.entity_name 
                WHERE normalised_name ILIKE :prefix OR normalised_name ILIKE :any
                LIMIT :limit
            """), {"prefix": prefix_like, "any": any_like, "limit": limit}).fetchall()
            for r in entity_rows:
                if r[0] and r[0] not in suggestions_set:
                    suggestions_set.append(r[0])

        # 3. Enrich from content.document titles if needed
        if len(suggestions_set) < limit:
            doc_rows = db.execute(text("""
                SELECT title 
                FROM content.document 
                WHERE state = 'verified' AND (title_normalised ILIKE :prefix OR title_normalised ILIKE :any)
                LIMIT :limit
            """), {"prefix": prefix_like, "any": any_like, "limit": limit}).fetchall()
            for r in doc_rows:
                if r[0] and r[0] not in suggestions_set:
                    suggestions_set.append(r[0])

        return suggestions_set[:limit]

    except Exception as e:
        import logging
        logging.error("Suggestions error: %s", str(e))
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
async def get_candidates(status: str = "candidate", limit: int = 50, db: Session = Depends(get_db)):
    try:
        valid_statuses = ["candidate", "verified", "rejected"]
        if status not in valid_statuses:
            status = "candidate"

        docs = db.execute(text("""
            SELECT d.document_id, d.canonical_url, d.title, d.summary, d.body_text, d.discovered_at, d.document_kind,
                   s.source_name, d.state
            FROM content.document d
            LEFT JOIN core.source_record sr ON d.source_record_id = sr.source_record_id
            LEFT JOIN core.source s ON sr.source_id = s.source_id
            WHERE d.state = :status
            ORDER BY d.discovered_at DESC
            LIMIT :limit
        """), {"status": status, "limit": limit}).fetchall()
        
        results = []
        for d in docs:
            url = d[1] or ""
            domain = ""
            if "://" in url:
                domain = url.split("://")[1].split("/")[0].replace("www.", "")
            
            results.append({
                "id": str(d[0]),
                "url": url,
                "domain": domain,
                "title": d[2] or "Untitled Document",
                "description": d[3] or "",
                "body": d[4] or "",
                "discovered_at": str(d[5]) if d[5] else None,
                "kind": d[6] or "news",
                "source_name": d[7] or domain,
                "state": d[8]
            })
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.put("/api/v1/admin/document/{document_id}")
async def update_document(document_id: str, update_data: DocumentUpdate, db: Session = Depends(get_db)):
    try:
        updates = []
        params = {"id": document_id}

        if update_data.title is not None:
            updates.append("title = :title, title_normalised = lower(:title)")
            params["title"] = update_data.title

        if update_data.description is not None:
            updates.append("summary = :description")
            params["description"] = update_data.description

        if update_data.kind is not None:
            updates.append("document_kind = :kind")
            params["kind"] = update_data.kind

        if update_data.state is not None:
            updates.append("state = :state")
            params["state"] = update_data.state

        if updates:
            sql_query = f"UPDATE content.document SET {', '.join(updates)} WHERE document_id = :id"
            db.execute(text(sql_query), params)
            db.commit()

        return {"success": True}
    except Exception as e:
        db.rollback()
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

@app.post("/api/v1/admin/restore/{document_id}")
async def restore_document(document_id: str, db: Session = Depends(get_db)):
    try:
        db.execute(text("UPDATE content.document SET state = 'candidate' WHERE document_id = :id"), {"id": document_id})
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
