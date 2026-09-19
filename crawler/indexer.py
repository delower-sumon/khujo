"""
Khujo Inverted Indexer (crawler/indexer.py)
Remediates Prompt 2 / Phase 3 from AUDIT_REMEDIATION_PLAN.md.

Constructs and incrementally maintains the inverted document index (search.document_index)
and term collection statistics (search.term_stats) for sub-millisecond BM25 ranking.

Features:
- Imports and applies the EXACT same bangla_stemmer used at query time.
- Incremental indexing: processes only documents where updated_at > last indexer checkpoint.
- Recomputes term_stats (doc_freq) after each batch.
- Resumable: safely records checkpoint progress in search.indexer_checkpoint.
- Clean upsert logic with transaction isolation.
"""

import os
import sys
import logging
import argparse
from typing import Dict, List, Set, Tuple
from collections import Counter
from datetime import datetime, timezone
from sqlalchemy import text

# Add repo root to path for imports
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

try:
    from backend.app.database import SessionLocal
except ImportError:
    from app.database import SessionLocal

# Import the SAME normalizer + stemmer used at query time (Do NOT reimplement)
from backend.app.nlp.bangla_stemmer import clean_bangla_text, strip_bangla_suffix

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("indexer")

# Common Bangla stopwords / noise tokens to skip from inverted index
BANGLA_INDEX_STOPWORDS: Set[str] = {
    "ও", "এবং", "বা", "কিন্তু", "অথবা", "যদি", "তবে", "তা", "যে", "সে", "যা", "তা", "কি", "কী",
    "এই", "সেই", "একটি", "এক", "দুই", "হতে", "থেকে", "দ্বারা", "দিয়ে", "নিয়ে", "নিয়ে",
    "হলে", "হলো", "হলো", "হবে", "হয়", "হয়", "ছিল", "করে", "করা", "করতে", "করার"
}

def extract_terms(text_corpus: str) -> Counter:
    """
    Tokenizes and stems text using the canonical bangla_stemmer.
    Returns term frequencies for terms length >= 2.
    """
    if not text_corpus:
        return Counter()

    cleaned = clean_bangla_text(text_corpus).lower()
    tokens = cleaned.split()
    
    terms = []
    for raw_tok in tokens:
        raw_tok = raw_tok.strip()
        if len(raw_tok) < 2 or raw_tok in BANGLA_INDEX_STOPWORDS:
            continue
        stemmed = strip_bangla_suffix(raw_tok)
        if len(stemmed) >= 2 and stemmed not in BANGLA_INDEX_STOPWORDS:
            terms.append(stemmed)

    return Counter(terms)

def index_batch(session, full_reindex: bool = False, batch_size: int = 100) -> int:
    """
    Processes one batch of unindexed or updated verified documents.
    Returns number of documents indexed in this batch.
    """
    # 1. Fetch checkpoint
    if full_reindex:
        last_indexed = datetime(1970, 1, 1, tzinfo=timezone.utc)
        log.info("Full re-index requested: starting from epoch 1970-01-01.")
    else:
        cp_row = session.execute(text("""
            SELECT last_indexed_at FROM search.indexer_checkpoint WHERE checkpoint_name = 'default'
        """)).fetchone()
        last_indexed = cp_row[0] if cp_row else datetime(1970, 1, 1, tzinfo=timezone.utc)

    # 2. Query batch of candidate verified documents
    docs = session.execute(text("""
        SELECT document_id, document_kind, title, body_text,
               COALESCE(updated_at, created_at, discovered_at, now()) as doc_time
        FROM content.document
        WHERE state = 'verified'
          AND COALESCE(updated_at, created_at, discovered_at, now()) > :last_time
        ORDER BY COALESCE(updated_at, created_at, discovered_at, now()) ASC
        LIMIT :limit
    """), {"last_time": last_indexed, "limit": batch_size}).fetchall()

    if not docs:
        return 0

    batch_terms: Set[str] = set()
    postings_to_insert = []
    max_doc_time = last_indexed

    for d in docs:
        doc_id, doc_kind, title, body_text, doc_time = d
        if doc_time > max_doc_time:
            max_doc_time = doc_time

        title_tf = extract_terms(title or "")
        body_tf = extract_terms(body_text or "")

        # Collect terms for stats update
        batch_terms.update(title_tf.keys())
        batch_terms.update(body_tf.keys())

        # Clean prior postings for this document if re-indexing
        session.execute(text("""
            DELETE FROM search.document_index WHERE document_id = :did
        """), {"did": doc_id})

        for term, count in title_tf.items():
            postings_to_insert.append({
                "did": doc_id,
                "dkind": doc_kind,
                "term": term,
                "tf": count,
                "field": "title"
            })

        for term, count in body_tf.items():
            postings_to_insert.append({
                "did": doc_id,
                "dkind": doc_kind,
                "term": term,
                "tf": count,
                "field": "body"
            })

    # 3. Bulk insert postings in chunks of 500 rows for high network throughput
    if postings_to_insert:
        CHUNK_SIZE = 500
        for i in range(0, len(postings_to_insert), CHUNK_SIZE):
            chunk = postings_to_insert[i:i + CHUNK_SIZE]
            val_clauses = []
            params = {}
            for idx, p in enumerate(chunk):
                val_clauses.append(
                    f"(:did_{idx}, :dkind_{idx}, :term_{idx}, :tf_{idx}, CAST(:field_{idx} AS search.index_field))"
                )
                params[f"did_{idx}"] = p["did"]
                params[f"dkind_{idx}"] = p["dkind"]
                params[f"term_{idx}"] = p["term"]
                params[f"tf_{idx}"] = p["tf"]
                params[f"field_{idx}"] = p["field"]

            sql = f"""
                INSERT INTO search.document_index (document_id, document_kind, term, term_freq, field)
                VALUES {', '.join(val_clauses)}
                ON CONFLICT (document_id, field, term) DO UPDATE SET term_freq = EXCLUDED.term_freq
            """
            session.execute(text(sql), params)

    # 4. Recompute term_stats for all terms touched in this batch
    if batch_terms:
        term_list = list(batch_terms)
        session.execute(text("""
            INSERT INTO search.term_stats (term, doc_freq, updated_at)
            SELECT term, COUNT(DISTINCT document_id) as doc_freq, now()
            FROM search.document_index
            WHERE term = ANY(:tlist)
            GROUP BY term
            ON CONFLICT (term) DO UPDATE SET
                doc_freq = EXCLUDED.doc_freq,
                updated_at = now()
        """), {"tlist": term_list})

    # 5. Update Checkpoint
    session.execute(text("""
        INSERT INTO search.indexer_checkpoint (checkpoint_name, last_indexed_at, documents_indexed, updated_at)
        VALUES ('default', :max_time, :cnt, now())
        ON CONFLICT (checkpoint_name) DO UPDATE SET
            last_indexed_at = EXCLUDED.last_indexed_at,
            documents_indexed = search.indexer_checkpoint.documents_indexed + EXCLUDED.documents_indexed,
            updated_at = now()
    """), {"max_time": max_doc_time, "cnt": len(docs)})

    session.commit()
    log.info(f"Successfully indexed {len(docs)} documents ({len(postings_to_insert)} postings, {len(batch_terms)} unique terms).")
    return len(docs)

def run_indexer(full_reindex: bool = False, batch_size: int = 100):
    """
    Main entry point for the indexing worker. Loops until all documents are indexed.
    """
    log.info("Starting Khujo Inverted Indexer...")
    session = SessionLocal()
    total_indexed = 0
    try:
        while True:
            indexed = index_batch(session, full_reindex=full_reindex, batch_size=batch_size)
            total_indexed += indexed
            if full_reindex:
                full_reindex = False  # Only reset epoch on first loop iteration
            if indexed < batch_size:
                break
        log.info(f"Indexing cycle complete. Total documents indexed: {total_indexed}.")
    except Exception as e:
        session.rollback()
        log.error(f"Indexer failed: {e}", exc_info=True)
        raise
    finally:
        session.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Khujo Inverted Indexer Worker")
    parser.add_argument("--full", action="store_true", help="Perform full re-index from epoch")
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size for indexing")
    args = parser.parse_args()

    run_indexer(full_reindex=args.full, batch_size=args.batch_size)
