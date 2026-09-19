"""
Khujo Ranking Engine (backend/app/search/rank.py)
Remediates Prompt 2 / Phase 3 from AUDIT_REMEDIATION_PLAN.md.

Implements true inverted-index BM25 retrieval over search.document_index:
- BM25 formula: k1=1.2, b=0.75 with document length normalization.
- Title field boost: 3x.
- Composite ranking signals:
  * BM25 relevance score
  * Authority / official source boost (+15.0)
  * Freshness decay boost for news (+10.0 / +5.0)
  * URL path match (+10.0)
  * Exact title match (+50.0)
- Trigram fallback: pg_trgm (%) triggers ONLY when BM25 returns fewer than 3 results.
"""

import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
try:
    from app.nlp.bangla_stemmer import clean_bangla_text, strip_bangla_suffix
except ImportError:
    from backend.app.nlp.bangla_stemmer import clean_bangla_text, strip_bangla_suffix

logger = logging.getLogger("rank")

def retrieve_ranked_documents(
    db: Session,
    clean_q: str,
    search_terms: List[str],
    limit: int = 10,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    Primary search retrieval using BM25 over the inverted index postings table.
    Falls back to pg_trgm (%) if fewer than 3 results are found.
    """
    if not clean_q:
        return []

    # 1. Normalize and extract query terms
    normalized_terms = set()
    for t in search_terms + clean_q.split():
        t_clean = clean_bangla_text(t).lower().strip()
        if len(t_clean) >= 2:
            stemmed = strip_bangla_suffix(t_clean)
            normalized_terms.add(t_clean)
            if len(stemmed) >= 2:
                normalized_terms.add(stemmed)

    terms_list = list(normalized_terms)
    if not terms_list:
        terms_list = [clean_q.lower()]

    # 2. Get collection metadata for BM25 normalization
    stats_row = db.execute(text("""
        SELECT 
            COUNT(*)::float as total_docs,
            COALESCE(AVG(word_count), 250.0)::float as avg_dl
        FROM content.document
        WHERE state = 'verified'
    """)).fetchone()

    total_docs = stats_row[0] if stats_row and stats_row[0] > 0 else 1.0
    avg_dl = stats_row[1] if stats_row and stats_row[1] > 0 else 250.0

    url_pattern = f"%{clean_q}%"

    # 3. BM25 Query over search.document_index
    bm25_sql = text("""
        WITH query_terms AS (
            SELECT unnest(CAST(:terms AS text[])) as term
        ),
        matched_postings AS (
            SELECT 
                di.document_id,
                di.term,
                di.term_freq,
                di.field,
                COALESCE(ts.doc_freq, 1) as doc_freq,
                CASE WHEN di.field = 'title' THEN 3.0 ELSE 1.0 END as field_weight
            FROM search.document_index di
            JOIN query_terms qt ON di.term = qt.term
            LEFT JOIN search.term_stats ts ON di.term = ts.term
        ),
        doc_scores AS (
            SELECT 
                mp.document_id,
                SUM(
                    mp.field_weight *
                    ln(1.0 + (:total_docs - mp.doc_freq + 0.5) / (mp.doc_freq + 0.5)) *
                    ((mp.term_freq * (1.2 + 1.0)) / (mp.term_freq + 1.2 * (1.0 - 0.75 + 0.75 * (COALESCE(d.word_count, 200)::float / :avg_dl))))
                ) as raw_bm25
            FROM matched_postings mp
            JOIN content.document d ON mp.document_id = d.document_id
            WHERE d.state = 'verified'
              AND (d.expires_at IS NULL OR d.expires_at > now())
            GROUP BY mp.document_id
        )
        SELECT 
            d.document_id,
            d.canonical_url,
            d.title,
            d.summary,
            d.body_text,
            d.published_at,
            s.source_name,
            (
                ds.raw_bm25 +
                (CASE WHEN lower(d.title) = lower(:clean_q) THEN 50.0 ELSE 0.0 END) +
                (CASE WHEN CAST(d.document_kind AS text) IN ('official', 'government', 'listing') THEN 15.0 ELSE 0.0 END) +
                (CASE WHEN d.canonical_url ILIKE :url_pattern THEN 10.0 ELSE 0.0 END) +
                (CASE WHEN d.published_at > now() - interval '7 days' THEN 10.0
                      WHEN d.published_at > now() - interval '30 days' THEN 5.0
                      ELSE 0.0 END)
            ) as final_score
        FROM doc_scores ds
        JOIN content.document d ON ds.document_id = d.document_id
        JOIN core.source_record sr ON d.source_record_id = sr.source_record_id
        LEFT JOIN core.source s ON sr.source_id = s.source_id
        ORDER BY final_score DESC, d.published_at DESC NULLS LAST
        LIMIT :limit OFFSET :offset
    """)

    docs = db.execute(bm25_sql, {
        "terms": terms_list,
        "total_docs": total_docs,
        "avg_dl": avg_dl,
        "clean_q": clean_q,
        "url_pattern": url_pattern,
        "limit": limit,
        "offset": offset
    }).fetchall()

    results = []
    seen_ids = set()

    for d in docs:
        doc_id = str(d[0])
        seen_ids.add(doc_id)
        url = d[1] or ""
        domain = ""
        if "://" in url:
            domain = url.split("://")[1].split("/")[0].replace("www.", "")

        results.append({
            "id": doc_id,
            "url": url,
            "domain": domain,
            "title": d[2] or "Untitled",
            "summary": d[3] or "",
            "body": d[4] or "",
            "published_at": str(d[5]) if d[5] else None,
            "source": d[6] or domain,
            "score": round(float(d[7]), 4) if d[7] is not None else 0.0,
            "retrieval_method": "bm25"
        })

    # 4. Trigram Fallback: survives ONLY when BM25 returns fewer than 3 results
    if len(results) < 3:
        needed = limit - len(results)
        stemmed_root = strip_bangla_suffix(clean_q)
        trgm_sql = text("""
            SELECT content.document.document_id, content.document.canonical_url, content.document.title, 
                   content.document.summary, content.document.body_text, content.document.published_at, 
                   core.source.source_name as source,
                   (
                       (CASE WHEN lower(content.document.title) = lower(:q) THEN 50.0
                             WHEN lower(content.document.title) = lower(:stemmed_q) THEN 30.0
                             ELSE 0.0 END) +
                       (COALESCE(similarity(content.document.title_normalised, :q), 0.0) * 30.0) +
                       (CASE WHEN content.document.body_normalised % :q THEN 10.0 ELSE 0.0 END) +
                       (CASE WHEN content.document.canonical_url ILIKE :url_pattern THEN 5.0 ELSE 0.0 END)
                   ) as final_score
            FROM content.document
            JOIN core.source_record ON content.document.source_record_id = core.source_record.source_record_id
            LEFT JOIN core.source ON core.source_record.source_id = core.source.source_id
            WHERE content.document.state = 'verified'
              AND (content.document.expires_at IS NULL OR content.document.expires_at > now())
              AND content.document.document_id NOT IN (SELECT unnest(CAST(:seen_ids AS uuid[])))
              AND (
                content.document.title_normalised % :q
                OR content.document.title_normalised % :stemmed_q
                OR content.document.body_normalised % :q
              )
            ORDER BY final_score DESC, content.document.published_at DESC NULLS LAST
            LIMIT :needed
        """)

        fallback_docs = db.execute(trgm_sql, {
            "q": clean_q,
            "stemmed_q": stemmed_root,
            "url_pattern": url_pattern,
            "seen_ids": list(seen_ids) if seen_ids else ['00000000-0000-0000-0000-000000000000'],
            "needed": needed
        }).fetchall()

        for d in fallback_docs:
            doc_id = str(d[0])
            url = d[1] or ""
            domain = ""
            if "://" in url:
                domain = url.split("://")[1].split("/")[0].replace("www.", "")

            results.append({
                "id": doc_id,
                "url": url,
                "domain": domain,
                "title": d[2] or "Untitled",
                "summary": d[3] or "",
                "body": d[4] or "",
                "published_at": str(d[5]) if d[5] else None,
                "source": d[6] or domain,
                "score": round(float(d[7]), 4) if d[7] is not None else 0.0,
                "retrieval_method": "trigram_fallback"
            })

    return results
