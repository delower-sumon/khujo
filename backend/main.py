from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import or_, func, case, and_
from typing import List, Optional
import os
import re
from app.database import get_db
from app.models.document import Document
from app.models.crawl_queue import CrawlQueue
from app.models.transliteration import TransliterationMap
from app.models.autosuggestion import Autosuggestion

app = FastAPI(title="Khujo API", description="Bangladesh's Own Search Engine API")

# CORS configuration
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
    """
    Search across documents and crawl_queue tables with prioritized ranking.
    Prioritizes base URLs (root domains) and exact title matches over deep links and content matches.
    Supports bilingual search via transliteration expansion.
    """
    try:
        if not q or len(q.strip()) < 1:
            return {"query": q, "results": [], "total": 0}

        # 1. Expand query with transliterations for broader bilingual matching
        search_terms = {q.strip()}
        trans_results = db.query(TransliterationMap).filter(
            or_(
                TransliterationMap.bangla.ilike(f"%{q}%"),
                TransliterationMap.english.ilike(f"%{q}%")
            )
        ).limit(5).all()
        
        for t in trans_results:
            if t.bangla: search_terms.add(t.bangla.strip())
            if t.english: search_terms.add(t.english.strip())

        # 2. Build Filter Conditions for Documents
        filter_conditions = []
        for term in search_terms:
            filter_conditions.append(Document.title.ilike(f"%{term}%"))
            filter_conditions.append(Document.content.ilike(f"%{term}%"))
            filter_conditions.append(Document.url.ilike(f"%{term}%"))

        # 3. Define depth (slash count) as a proxy for 'base' vs 'deep' page
        # Base URLs typically have 2 (http://site.com) or 3 (https://site.com/) slashes
        slash_count = func.char_length(Document.url) - func.char_length(func.replace(Document.url, '/', ''))

        # 4. Search documents with prioritized ranking
        documents = db.query(Document).filter(
            or_(*filter_conditions)
        ).order_by(
            # Rank 1: Exact phrase match in title (Highest priority)
            case((or_(*[Document.title.ilike(term) for term in search_terms]), 0), else_=1),
            
            # Rank 2: Root-level page match (Base URL)
            case((and_(slash_count <= 3, 
                       or_(*[or_(Document.title.ilike(f"%{term}%"), Document.url.ilike(f"%{term}%")) 
                             for term in search_terms])), 0), else_=1),
            
            # Rank 3: Partial title match
            case((or_(*[Document.title.ilike(f"%{term}%") for term in search_terms]), 0), else_=1),
            
            # Rank 4: URL depth (shorter paths first)
            slash_count.asc(),
            
            # Rank 5: Absolute URL length
            func.char_length(Document.url).asc(),
            
            # Rank 6: Most recent
            Document.updated_at.desc()
        ).limit(limit).offset(offset).all()

        # 5. Search in crawl_queue for pending items that match the query
        cq_filters = [CrawlQueue.url.ilike(f"%{term}%") for term in search_terms]
        crawl_items = db.query(CrawlQueue).filter(
            or_(*cq_filters)
        ).order_by(
            func.char_length(CrawlQueue.url).asc()
        ).limit(max(0, limit - len(documents))).offset(offset).all()

        results = []

        # Format document results
        for doc in documents:
            results.append({
                "id": str(doc.id),
                "title": doc.title or "Untitled",
                "snippet": (doc.content[:200] + "...") if doc.content else "No description available",
                "url": doc.url or "",
                "favicon": doc.favicon_url,
                "source": "Documents Database",
                "type": "document"
            })

        # Format crawl queue results
        for item in crawl_items:
            results.append({
                "id": f"crawl_{item.id}",
                "title": item.url.split("//")[-1].split("/")[0] or item.url, # Show domain as title for crawl items
                "snippet": f"Status: {item.status} | Priority: {item.priority} (Crawling in progress...)",
                "url": item.url or "",
                "favicon": None,
                "source": "Crawl Queue",
                "type": "crawl_queue"
            })

        return {
            "query": q,
            "results": results[:limit],
            "total": len(results)
        }
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/v1/suggestions")
async def suggestions(q: str, limit: int = 5, db: Session = Depends(get_db)):
    """
    Get transliteration-based auto suggestions
    Searches transliteration_map for matching Bangla and English terms
    """
    try:
        if not q or len(q.strip()) < 1:
            return []

        # Search in autosuggestions with professional ranking logic (Priority > Weight)
        autosuggest_results = db.query(Autosuggestion).filter(
            or_(
                Autosuggestion.phrase.ilike(f"%{q}%"),
                Autosuggestion.transliteration.ilike(f"%{q}%")
            )
        ).order_by(
            Autosuggestion.priority_level.desc(),
            Autosuggestion.search_volume_weight.desc().nulls_last()
        ).limit(limit * 2).all()

        # Collect and clean suggestions
        final_suggestions = []
        seen = set()

        # 1. Add curated Autosuggestion matches first (Clean phrases)
        for item in autosuggest_results:
            phrase = item.phrase.strip()
            if phrase and phrase.lower() not in seen:
                final_suggestions.append(phrase)
                seen.add(phrase.lower())

        if len(final_suggestions) < limit:
            # Also search documents for matching titles
            doc_results = db.query(Document.title).filter(
                Document.title.ilike(f"%{q}%")
            ).limit(limit * 10).all()

            # 2. Add and clean Document title matches (extract relevant parts)
            doc_suggestions = []
            for doc in doc_results:
                title = doc[0]
                if not title:
                    continue
                
                # Clean title: split by common separators (|, -, :, etc.) used in Bengali/English websites
                parts = re.split(r'[\|\-\:\—\–\•\‧\/\\\]\[]', title)
                for part in parts:
                    cleaned = part.strip()
                    if not cleaned or cleaned.lower() in seen:
                        continue
                    
                    # Store part if it matches query; we'll filter and sort after
                    if q.lower() in cleaned.lower() and len(cleaned) < 60:
                        doc_suggestions.append(cleaned)
                        break

            # Sort document-derived suggestions by length (shortest first)
            doc_suggestions.sort(key=len)
            
            for s in doc_suggestions:
                if s.lower() not in seen:
                    final_suggestions.append(s)
                    seen.add(s.lower())
                if len(final_suggestions) >= limit:
                    break

        return final_suggestions[:limit]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
