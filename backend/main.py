from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import or_, func
from typing import List, Optional
import os
from app.database import get_db
from app.models.document import Document
from app.models.crawl_queue import CrawlQueue
from app.models.transliteration import TransliterationMap

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
    Search across documents and crawl_queue tables
    """
    try:
        # Search in documents table
        documents = db.query(Document).filter(
            or_(
                Document.title.ilike(f"%{q}%"),
                Document.content.ilike(f"%{q}%"),
                Document.url.ilike(f"%{q}%")
            )
        ).limit(limit).offset(offset).all()

        # Search in crawl_queue table
        crawl_items = db.query(CrawlQueue).filter(
            or_(
                CrawlQueue.url.ilike(f"%{q}%")
            )
        ).limit(limit - len(documents)).offset(offset).all()

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
                "title": item.url.split("/")[-1] or item.url,
                "snippet": f"Status: {item.status} | Priority: {item.priority}",
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

        # Search in transliteration map for both Bangla and English matches
        translit_results = db.query(TransliterationMap).filter(
            or_(
                TransliterationMap.bangla.ilike(f"%{q}%"),
                TransliterationMap.english.ilike(f"%{q}%")
            )
        ).limit(limit * 2).all()

        # Also search documents for matching titles
        doc_results = db.query(Document.title).filter(
            Document.title.ilike(f"%{q}%")
        ).limit(limit).all()

        suggestions_set = set()

        # Add transliteration suggestions
        for item in translit_results:
            if item.bangla:
                suggestions_set.add(item.bangla)
            if item.english:
                suggestions_set.add(item.english)

        # Add document title suggestions
        for doc in doc_results:
            if doc[0]:
                suggestions_set.add(doc[0])

        return list(suggestions_set)[:limit]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
