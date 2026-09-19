-- =====================================================================
-- KHUJO MIGRATION 0006: Inverted Search Index & BM25 Foundations
-- Replaces rudimentary trigram-based retrieval with an indexed inverted
-- postings list and term-frequency statistics.
-- =====================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'index_field' AND typnamespace = 'search'::regnamespace) THEN
        CREATE TYPE search.index_field AS ENUM ('title', 'body');
    END IF;
END $$;

-- 1. Inverted Postings Table (document_id -> term -> term_freq by field)
CREATE TABLE IF NOT EXISTS search.document_index (
    document_id UUID NOT NULL,
    document_kind content.document_kind NOT NULL,
    term TEXT NOT NULL,
    term_freq INT NOT NULL CHECK (term_freq > 0),
    field search.index_field NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (document_id, field, term)
);

-- Fast exact term lookup index (Primary BM25 retrieval path)
CREATE INDEX IF NOT EXISTS document_index_term_btree_idx ON search.document_index (term, field);
CREATE INDEX IF NOT EXISTS document_index_doc_id_idx ON search.document_index (document_id);

-- GIN trigram index on term for fallback and partial term discovery
CREATE INDEX IF NOT EXISTS document_index_term_gin_idx ON search.document_index USING gin (term gin_trgm_ops);

-- 2. Term Document Frequency Statistics (for BM25 IDF calculation)
CREATE TABLE IF NOT EXISTS search.term_stats (
    term TEXT PRIMARY KEY,
    doc_freq INT NOT NULL DEFAULT 1 CHECK (doc_freq > 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3. Resumable Indexer Checkpoint Table
CREATE TABLE IF NOT EXISTS search.indexer_checkpoint (
    checkpoint_name TEXT PRIMARY KEY,
    last_indexed_at TIMESTAMPTZ NOT NULL DEFAULT '1970-01-01 00:00:00+00',
    documents_indexed INT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Initialize default checkpoint if not present
INSERT INTO search.indexer_checkpoint (checkpoint_name, last_indexed_at, documents_indexed)
VALUES ('default', '1970-01-01 00:00:00+00', 0)
ON CONFLICT (checkpoint_name) DO NOTHING;
