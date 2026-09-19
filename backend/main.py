from fastapi import FastAPI, APIRouter, Depends, HTTPException, BackgroundTasks, Header, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import os
import re
import logging
import hashlib
import uuid
try:
    from app.database import get_db, SessionLocal
except ImportError:
    from backend.app.database import get_db, SessionLocal

try:
    from app.nlp.bangla_stemmer import strip_bangla_suffix, expand_bangla_stems
except ImportError:
    from backend.app.nlp.bangla_stemmer import strip_bangla_suffix, expand_bangla_stems

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("khujo_api")

app = FastAPI(title="Khujo API", description="Bangladesh's Own Search Engine API")

# --- CORS Configuration (Fixes D9) ---
cors_origins_env = os.getenv("ALLOWED_ORIGINS")
if cors_origins_env:
    allowed_origins = [o.strip() for o in cors_origins_env.split(",") if o.strip()]
else:
    allowed_origins = [
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Admin Authentication Dependency (Fixes D1) ---
ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "khujo_admin_secret_2026")

def verify_admin_key(
    x_admin_key: Optional[str] = Header(None, alias="X-Admin-Key"),
    admin_key: Optional[str] = Query(None)
):
    provided = x_admin_key or admin_key
    if not provided or provided != ADMIN_API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Missing or invalid admin API key"
        )
    return provided

# --- Safe Error Handler (Fixes D11) ---
def handle_error(context: str, err: Exception, status_code: int = 500) -> HTTPException:
    logger.error(f"Error in {context}: {err}", exc_info=True)
    return HTTPException(status_code=status_code, detail=f"Operation failed in {context}")

# --- Background Telemetry (Fixes D12 & D2) ---
def record_search_telemetry(clean_q: str, results_count: int):
    """
    Asynchronously logs search events and gates suggestion entries.
    Prevents write transactions and table locks in search GET requests.
    """
    session = SessionLocal()
    try:
        q_fp = hashlib.md5(clean_q.encode("utf-8")).hexdigest()
        session.execute(text("""
            INSERT INTO search.query_event (query_fingerprint, normalised_query, result_count, occurred_at, expires_at)
            VALUES (:fp, lower(:q), :rc, now(), now() + interval '30 days')
        """), {"fp": q_fp, "q": clean_q, "rc": results_count})

        # Update popularity if phrase already exists
        updated_sug = session.execute(text("""
            UPDATE search.suggestion 
            SET popularity_score = popularity_score + 1 
            WHERE phrase_normalised = lower(:q)
        """), {"q": clean_q}).rowcount

        # Gated suggestion: new user queries enter as 'candidate' state, never 'active' immediately
        if updated_sug == 0 and 2 <= len(clean_q) <= 80:
            session.execute(text("""
                INSERT INTO search.suggestion (phrase, phrase_normalised, language_code, priority, popularity_score, state)
                VALUES (:q, lower(:q), 'bn', 10, 1, 'candidate')
            """), {"q": clean_q})

        session.commit()
    except Exception as e:
        session.rollback()
        logger.warning(f"Telemetry logging background task failed: {e}")
    finally:
        session.close()


class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    kind: Optional[str] = None
    state: Optional[str] = None


@app.get("/api")
async def root():
    return {"message": "Welcome to Khujo API - Bangladesh's Own Search Engine"}

@app.get("/graph")
async def serve_graph():
    graph_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "khujo_graph.html"))
    if os.path.exists(graph_path):
        return FileResponse(graph_path, media_type="text/html")
    raise HTTPException(status_code=404, detail="Graph visualization not found")

@app.get("/")
async def serve_index():
    index_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "public", "index.html"))
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html")
    return {"message": "Welcome to Khujo API"}


# --- Public Search Endpoint ---
@app.get("/api/v1/search")
async def search(
    q: str,
    limit: int = 10,
    offset: int = 0,
    background_tasks: BackgroundTasks = BackgroundTasks(),
    db: Session = Depends(get_db)
):
    try:
        clean_q = q.strip()
        if not clean_q:
            return {"query": q, "results": [], "total": 0}

        norm_q = clean_q.lower().replace(" ", "")
        stemmed_root = strip_bangla_suffix(clean_q)
        stemmed_norm = stemmed_root.lower().replace(" ", "")

        # Expand search terms with morphological roots (Fixes D5)
        expanded_stems = expand_bangla_stems(clean_q)
        search_terms = list(dict.fromkeys([clean_q] + expanded_stems))
        
        # 1. Lookup knowledge graph entity & all associated transliteration aliases (Fixes D3 & D5)
        # Tiered precision: Exact name -> Exact normalised -> Stemmed root -> Stemmed normalised -> Substring (min 4 chars)
        allow_substring = len(clean_q) >= 4
        q_like = f"%{clean_q}%" if allow_substring else "___NO_SUBSTRING_MATCH___"

        entity_res = db.execute(text("""
            SELECT e.entity_id, e.display_name, e.summary, e.metadata, e.entity_type_id
            FROM core.entity_name n
            JOIN core.entity e ON n.entity_id = e.entity_id
            WHERE e.state = 'verified'
               AND (lower(n.name) = lower(:q) 
               OR lower(n.normalised_name) = lower(:norm_q)
               OR lower(n.name) = lower(:stemmed_q)
               OR lower(n.normalised_name) = lower(:stemmed_norm)
               OR (:allow_sub = TRUE AND (n.normalised_name ILIKE :q_like OR e.display_name ILIKE :q_like)))
            ORDER BY 
               (CASE WHEN lower(n.name) = lower(:q) THEN 1 
                     WHEN lower(n.normalised_name) = lower(:norm_q) THEN 2 
                     WHEN lower(n.name) = lower(:stemmed_q) THEN 3
                     WHEN lower(n.normalised_name) = lower(:stemmed_norm) THEN 4
                     ELSE 5 END),
               (CASE WHEN e.metadata->>'images' IS NOT NULL OR e.metadata->>'image_url' IS NOT NULL THEN 0 ELSE 1 END),
               n.entity_name_id
            LIMIT 1
        """), {
            "q": clean_q,
            "norm_q": norm_q,
            "stemmed_q": stemmed_root,
            "stemmed_norm": stemmed_norm,
            "allow_sub": allow_substring,
            "q_like": q_like
        }).fetchone()

        knowledge_graph = None
        correction = None

        if entity_res:
            entity_id, display_name, summary, metadata_json, entity_type_id = entity_res
            image_url = metadata_json.get("image_url") if isinstance(metadata_json, dict) else None
            facts = metadata_json.get("facts", {}) if isinstance(metadata_json, dict) else {}
            images = metadata_json.get("images", []) if isinstance(metadata_json, dict) else []
            
            knowledge_graph = {
                "id": str(entity_id),
                "title": display_name,
                "description": summary or f"{display_name} সম্পর্কিত তথ্য",
                "image_url": image_url,
                "images": images,
                "facts": facts,
                "sources": [],
                "related_entities": []
            }

            if clean_q.lower() != display_name.lower():
                correction = {
                    "original_query": clean_q,
                    "target_name": display_name
                }
            
            # Fetch related entities
            related_res = db.execute(text("""
                SELECT entity_id, display_name, metadata
                FROM core.entity
                WHERE entity_type_id = :type_id AND entity_id != :eid AND state = 'verified'
                ORDER BY created_at DESC
                LIMIT 6
            """), {"type_id": entity_type_id, "eid": entity_id}).fetchall()
            
            for r in related_res:
                r_meta = r[2] if isinstance(r[2], dict) else {}
                r_img = r_meta.get("image_url")
                if r_img:
                    knowledge_graph["related_entities"].append({
                        "id": str(r[0]),
                        "title": r[1],
                        "image_url": r_img
                    })

            # Fetch linked names (Bangla, English, Banglish) for this entity
            aliases = db.execute(text("""
                SELECT normalised_name FROM core.entity_name WHERE entity_id = :eid
            """), {"eid": entity_id}).fetchall()
            for a in aliases:
                if a[0] and a[0] not in search_terms:
                    search_terms.append(a[0])

        # 2. Document Search (Fixes D4 & D6)
        # Prepare trigram/ILIKE patterns without correlated unnest subqueries
        search_patterns = [f"%{t}%" for t in search_terms if len(t.strip()) >= 2]
        if not search_patterns:
            search_patterns = [f"%{clean_q}%"]

        docs = db.execute(text("""
            SELECT content.document.document_id, content.document.canonical_url, content.document.title, 
                   content.document.summary, content.document.body_text, content.document.published_at, 
                   core.source.source_name as source,
                   (
                       -- 1. Exact or title token match gets highest priority
                       (CASE WHEN lower(content.document.title) = lower(:q) THEN 100.0
                             WHEN content.document.title_normalised ILIKE ANY(CAST(:patterns AS text[])) THEN 40.0
                             ELSE 0.0 END) +

                       -- 2. Trigram similarity on normalized title (heavy weight)
                       (COALESCE(similarity(content.document.title_normalised, :q), 0.0) * 50.0) +

                       -- 3. Trigram similarity on normalized body (medium weight)
                       (COALESCE(similarity(content.document.body_normalised, :q), 0.0) * 20.0) +

                       -- 4. Substring presence in body
                       (CASE WHEN content.document.body_normalised ILIKE ANY(CAST(:patterns AS text[])) THEN 15.0 ELSE 0.0 END) +

                       -- 5. URL matching (demoted from 100 to 10 so it never dominates over title)
                       (CASE WHEN content.document.canonical_url ILIKE ANY(CAST(:patterns AS text[])) THEN 10.0 ELSE 0.0 END) +

                       -- 6. Official / authoritative source boost
                       (CASE WHEN CAST(content.document.document_kind AS text) IN ('official', 'government', 'listing') THEN 15.0 ELSE 0.0 END) +

                       -- 7. Freshness decay boost
                       (CASE WHEN content.document.published_at > now() - interval '7 days' THEN 10.0
                             WHEN content.document.published_at > now() - interval '30 days' THEN 5.0
                             ELSE 0.0 END)

                   ) as final_score
            FROM content.document
            JOIN core.source_record ON content.document.source_record_id = core.source_record.source_record_id
            LEFT JOIN core.source ON core.source_record.source_id = core.source.source_id
            WHERE content.document.state = 'verified'
              AND (content.document.expires_at IS NULL OR content.document.expires_at > now())
              AND (
                content.document.title_normalised ILIKE ANY(CAST(:patterns AS text[]))
                OR content.document.body_normalised ILIKE ANY(CAST(:patterns AS text[]))
                OR content.document.canonical_url ILIKE ANY(CAST(:patterns AS text[]))
                OR content.document.title_normalised % :q
              )
            ORDER BY final_score DESC, content.document.published_at DESC NULLS LAST
            LIMIT :limit OFFSET :offset
        """), {"q": clean_q, "patterns": search_patterns, "limit": limit, "offset": offset}).fetchall()

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

        # Schedule asynchronous logging outside transaction (Fixes D12)
        background_tasks.add_task(record_search_telemetry, clean_q, len(results))

        return {
            "query": q,
            "correction": correction,
            "results": results,
            "knowledge_graph": knowledge_graph,
            "total": len(results)
        }
    except Exception as e:
        raise handle_error("search", e)


@app.get("/api/v1/search/images")
async def search_images(q: str, limit: int = 20, db: Session = Depends(get_db)):
    try:
        clean_q = q.strip()
        if not clean_q:
            return {"query": q, "results": []}

        docs = db.execute(text("""
            SELECT e.entity_id, e.display_name, e.summary, e.metadata
            FROM core.entity e
            WHERE e.state = 'verified'
              AND (e.metadata->>'image_url' IS NOT NULL OR e.metadata->>'images' IS NOT NULL)
              AND (
                  lower(e.display_name) ILIKE '%' || lower(:q) || '%'
                  OR lower(e.summary) ILIKE '%' || lower(:q) || '%'
              )
            LIMIT :limit
        """), {"q": clean_q, "limit": limit}).fetchall()

        results = []
        seen_urls = set()
        for d in docs:
            meta = d[3] if isinstance(d[3], dict) else {}
            images = meta.get("images", [])
            if not images and meta.get("image_url"):
                images = [meta.get("image_url")]
            
            source_url = meta.get("wikipedia_url")
            
            for img in images:
                if img not in seen_urls:
                    seen_urls.add(img)
                    results.append({
                        "id": str(d[0]),
                        "title": d[1] or "Untitled",
                        "snippet": (d[2][:100] + "...") if d[2] else "",
                        "thumbnail_url": img,
                        "source_url": source_url or img,
                        "type": "image"
                    })

        return {
            "query": q,
            "results": results,
            "total": len(results)
        }
    except Exception as e:
        raise handle_error("search_images", e)


# --- Suggestions Endpoint (Fixes D2 & D17) ---
@app.get("/api/v1/suggestions")
async def suggestions(q: str, limit: int = 8, db: Session = Depends(get_db)):
    try:
        clean_q = q.strip()
        if not clean_q:
            return []

        prefix_like = f"{clean_q}%"
        any_like = f"%{clean_q}%"

        # 1. Fetch from search.suggestion table - ONLY ACTIVE SUGGESTIONS
        sug_rows = db.execute(text("""
            SELECT phrase 
            FROM search.suggestion 
            WHERE (state = 'active' OR state IS NULL)
              AND (phrase_normalised ILIKE :prefix 
                   OR phrase_normalised ILIKE :any 
                   OR phrase_normalised % :q)
            ORDER BY (CASE WHEN phrase_normalised ILIKE :prefix THEN 1 ELSE 2 END), 
                     popularity_score DESC, priority DESC
            LIMIT :limit
        """), {"q": clean_q, "prefix": prefix_like, "any": any_like, "limit": limit}).fetchall()

        suggestions_set = []
        for r in sug_rows:
            if r[0] and ',' not in r[0] and r[0] not in suggestions_set:
                suggestions_set.append(r[0])

        # 2. Enrich from verified core.entity_name if needed
        if len(suggestions_set) < limit:
            entity_rows = db.execute(text("""
                SELECT name 
                FROM core.entity_name 
                WHERE state = 'verified'
                  AND (normalised_name ILIKE :prefix OR normalised_name ILIKE :any)
                LIMIT :limit
            """), {"prefix": prefix_like, "any": any_like, "limit": limit}).fetchall()
            for r in entity_rows:
                if r[0] and ',' not in r[0] and r[0] not in suggestions_set:
                    suggestions_set.append(r[0])

        # Removed D17 runtime unindexed document title regex splitting.
        return suggestions_set[:limit]

    except Exception as e:
        raise handle_error("suggestions", e)


# =====================================================================
# ADMIN ROUTER — Protected with API Key Authentication (Fixes D1)
# =====================================================================
admin_router = APIRouter(prefix="/api/v1/admin", dependencies=[Depends(verify_admin_key)])

@admin_router.get("/stats")
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
        raise handle_error("admin_stats", e)

@admin_router.get("/candidates")
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
        raise handle_error("admin_candidates", e)

@admin_router.put("/document/{document_id}")
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
        raise handle_error("admin_update_document", e)

@admin_router.post("/verify/{document_id}")
async def verify_document(document_id: str, db: Session = Depends(get_db)):
    try:
        db.execute(text("UPDATE content.document SET state = 'verified' WHERE document_id = :id"), {"id": document_id})
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        raise handle_error("admin_verify_document", e)

@admin_router.post("/reject/{document_id}")
async def reject_document(document_id: str, db: Session = Depends(get_db)):
    try:
        db.execute(text("UPDATE content.document SET state = 'rejected' WHERE document_id = :id"), {"id": document_id})
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        raise handle_error("admin_reject_document", e)

@admin_router.post("/restore/{document_id}")
async def restore_document(document_id: str, db: Session = Depends(get_db)):
    try:
        db.execute(text("UPDATE content.document SET state = 'candidate' WHERE document_id = :id"), {"id": document_id})
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        raise handle_error("admin_restore_document", e)

@admin_router.post("/batch_verify")
async def batch_verify(document_ids: List[str], db: Session = Depends(get_db)):
    try:
        if document_ids:
            db.execute(text("UPDATE content.document SET state = 'verified' WHERE document_id = ANY(:ids)"), {"ids": document_ids})
            db.commit()
        return {"success": True, "count": len(document_ids)}
    except Exception as e:
        db.rollback()
        raise handle_error("admin_batch_verify", e)

@admin_router.post("/batch_reject")
async def batch_reject(document_ids: List[str], db: Session = Depends(get_db)):
    try:
        if document_ids:
            db.execute(text("UPDATE content.document SET state = 'rejected' WHERE document_id = ANY(:ids)"), {"ids": document_ids})
            db.commit()
        return {"success": True, "count": len(document_ids)}
    except Exception as e:
        db.rollback()
        raise handle_error("admin_batch_reject", e)

class EntityFactsUpdate(BaseModel):
    facts: dict

@admin_router.get("/entities")
async def get_admin_entities(status: str = "candidate", db: Session = Depends(get_db)):
    try:
        rows = db.execute(text("""
            SELECT entity_id, display_name, summary, metadata, state, created_at 
            FROM core.entity 
            WHERE state = :s
            ORDER BY created_at DESC LIMIT 50
        """), {"s": status}).fetchall()
        
        results = []
        for r in rows:
            meta = r[3] if isinstance(r[3], dict) else {}
            results.append({
                "id": str(r[0]),
                "name": r[1],
                "summary": r[2],
                "image_url": meta.get("image_url"),
                "facts": meta.get("facts", {}),
                "state": r[4],
                "created_at": str(r[5])
            })
        return results
    except Exception as e:
        raise handle_error("admin_entities", e)

@admin_router.put("/entities/{entity_id}/facts")
async def update_entity_facts(entity_id: str, update: EntityFactsUpdate, db: Session = Depends(get_db)):
    try:
        import json
        row = db.execute(text("SELECT metadata FROM core.entity WHERE entity_id = :eid"), {"eid": entity_id}).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Entity not found")
        meta = row[0] if isinstance(row[0], dict) else {}
        meta["facts"] = update.facts
        db.execute(text("UPDATE core.entity SET metadata = :m WHERE entity_id = :eid"), 
                   {"m": json.dumps(meta), "eid": entity_id})
        db.commit()
        return {"status": "updated"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_error("admin_update_entity_facts", e)

@admin_router.post("/entities/{entity_id}/action")
async def action_entity(entity_id: str, action: str, db: Session = Depends(get_db)):
    try:
        if action not in ["approve", "reject"]:
            raise HTTPException(status_code=400, detail="Invalid action")
        target_state = "verified" if action == "approve" else "rejected"
        db.execute(text("UPDATE core.entity SET state = :s WHERE entity_id = :eid"), 
                   {"s": target_state, "eid": entity_id})
        db.commit()
        return {"status": "success", "new_state": target_state}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise handle_error("admin_action_entity", e)

class AliasVerifyPayload(BaseModel):
    entity_name_id: str
    action: str # "approve", "reject", "update"
    name: Optional[str] = None

class AliasCreatePayload(BaseModel):
    entity_id: str
    name: str
    language_code: Optional[str] = "en"

@admin_router.get("/aliases")
async def get_admin_aliases(status: str = "candidate", db: Session = Depends(get_db)):
    try:
        rows = db.execute(text("""
            SELECT n.entity_name_id, n.entity_id, n.name, n.normalised_name, n.language_code, n.script, n.name_kind, n.state, e.display_name
            FROM core.entity_name n
            JOIN core.entity e ON n.entity_id = e.entity_id
            WHERE n.state = :s
            ORDER BY n.created_at DESC LIMIT 100
        """), {"s": status}).fetchall()
        
        results = []
        for r in rows:
            results.append({
                "entity_name_id": str(r[0]),
                "entity_id": str(r[1]),
                "name": r[2],
                "normalised_name": r[3],
                "language_code": r[4],
                "script": str(r[5]),
                "name_kind": str(r[6]),
                "state": str(r[7]),
                "entity_display_name": r[8]
            })
        return results
    except Exception as e:
        raise handle_error("admin_aliases", e)

@admin_router.post("/aliases/verify")
async def verify_admin_alias(payload: AliasVerifyPayload, db: Session = Depends(get_db)):
    try:
        if payload.action == "approve":
            db.execute(text("UPDATE core.entity_name SET state = 'verified' WHERE entity_name_id = :id"), {"id": payload.entity_name_id})
        elif payload.action == "reject":
            db.execute(text("DELETE FROM core.entity_name WHERE entity_name_id = :id"), {"id": payload.entity_name_id})
        elif payload.action == "update":
            if payload.name:
                parts = [p.strip() for p in payload.name.split(',') if p.strip()]
                if parts:
                    first_part = parts[0]
                    norm = first_part.lower().replace(' ', '')
                    db.execute(text("""
                        UPDATE core.entity_name 
                        SET name = :name, normalised_name = :norm, state = 'verified' 
                        WHERE entity_name_id = :id
                    """), {"name": first_part, "norm": norm, "id": payload.entity_name_id})
                    
                    if len(parts) > 1:
                        row = db.execute(text("SELECT entity_id FROM core.entity_name WHERE entity_name_id = :id"), {"id": payload.entity_name_id}).fetchone()
                        if row:
                            eid = row[0]
                            for part in parts[1:]:
                                part_norm = part.lower().replace(' ', '')
                                exists = db.execute(text("SELECT 1 FROM core.entity_name WHERE entity_id = :eid AND lower(name) = lower(:part)"), {"eid": eid, "part": part}).fetchone()
                                if not exists:
                                    is_bn = any('\u0980' <= c <= '\u09FF' for c in part)
                                    lang = 'bn' if is_bn else 'en'
                                    script_val = 'bangla' if is_bn else 'latin'
                                    db.execute(text("""
                                        INSERT INTO core.entity_name 
                                        (entity_name_id, entity_id, name, normalised_name, language_code, script, name_kind, is_primary, state)
                                        VALUES (:id, :eid, :name, :norm, :lang, :script, 'transliteration', false, 'verified')
                                    """), {
                                        "id": str(uuid.uuid4()),
                                        "eid": eid,
                                        "name": part,
                                        "norm": part_norm,
                                        "lang": lang,
                                        "script": script_val
                                    })
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        raise handle_error("admin_verify_alias", e)

@admin_router.post("/aliases/create")
async def create_admin_alias(payload: AliasCreatePayload, db: Session = Depends(get_db)):
    try:
        parts = [p.strip() for p in payload.name.split(',') if p.strip()]
        for part in parts:
            part_norm = part.lower().replace(' ', '')
            exists = db.execute(text("SELECT 1 FROM core.entity_name WHERE entity_id = :eid AND lower(name) = lower(:part)"), {"eid": payload.entity_id, "part": part}).fetchone()
            if not exists:
                is_bn = any('\u0980' <= c <= '\u09FF' for c in part)
                lang = 'bn' if is_bn else (payload.language_code or 'en')
                script_val = 'bangla' if is_bn else 'latin'
                
                db.execute(text("""
                    INSERT INTO core.entity_name 
                    (entity_name_id, entity_id, name, normalised_name, language_code, script, name_kind, is_primary, state)
                    VALUES (:id, :eid, :name, :norm, :lang, :script, 'transliteration', false, 'verified')
                """), {
                    "id": str(uuid.uuid4()),
                    "eid": payload.entity_id,
                    "name": part,
                    "norm": part_norm,
                    "lang": lang,
                    "script": script_val
                })
        db.commit()
        return {"success": True}
    except Exception as e:
        db.rollback()
        raise handle_error("admin_create_alias", e)

# Mount the admin router with authentication dependency
app.include_router(admin_router)

# Mount Static Files
public_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "public"))
if os.path.isdir(public_dir):
    app.mount("/", StaticFiles(directory=public_dir, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
