-- Migration 0004: Pipeline Queues
-- Phase 2 of the Knowledge Core Implementation

BEGIN;

-- Add tracking columns for decoupled pipeline queues

-- 1. Track which fetches have been extracted
ALTER TABLE crawl.fetch ADD COLUMN parsed_at TIMESTAMPTZ;
CREATE INDEX fetch_parsed_at_idx ON crawl.fetch (created_at ASC) WHERE parsed_at IS NULL AND state = 'success';

-- 2. Track which documents have gone through NER / Knowledge extraction
ALTER TABLE content.document ADD COLUMN entities_extracted_at TIMESTAMPTZ;
CREATE INDEX document_entities_extracted_idx ON content.document (discovered_at ASC) WHERE entities_extracted_at IS NULL AND state = 'candidate';

COMMIT;
