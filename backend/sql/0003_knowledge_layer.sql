-- Migration 0003: Knowledge Layer & Entity Versioning
-- Phase 1 of the Knowledge Core Implementation

BEGIN;

-- 1. Search Dictionary (Highest long-term ROI)
-- Maps search terms across scripts and spellings to canonical entity IDs.
CREATE TYPE core.dictionary_source AS ENUM ('manual', 'harvested', 'log_mining', 'ai_suggested');

CREATE TABLE core.search_dictionary (
    entry_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_term TEXT NOT NULL,
    normalised_term TEXT NOT NULL,
    script core.script_kind NOT NULL,
    language_code TEXT CHECK (language_code IS NULL OR language_code ~ '^[a-z]{2,3}(-[A-Z]{2})?$'),
    entity_id UUID REFERENCES core.entity(entity_id) ON DELETE CASCADE,
    source core.dictionary_source NOT NULL DEFAULT 'manual',
    state core.record_state NOT NULL DEFAULT 'candidate',
    confidence NUMERIC(4,3) NOT NULL DEFAULT 0.500 CHECK (confidence BETWEEN 0 AND 1),
    created_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (normalised_term, language_code, entity_id)
);

CREATE INDEX search_dictionary_normalised_trgm_idx ON core.search_dictionary USING gin (normalised_term gin_trgm_ops);
CREATE INDEX search_dictionary_entity_idx ON core.search_dictionary (entity_id);

-- 2. Entity Versioning (Append-only model)
CREATE TABLE core.entity_revisions (
    revision_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id UUID NOT NULL REFERENCES core.entity(entity_id) ON DELETE CASCADE,
    data JSONB NOT NULL,
    changed_by TEXT NOT NULL,
    change_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX entity_revisions_entity_idx ON core.entity_revisions (entity_id, created_at DESC);

-- Add pointer to latest revision on the main entity table
ALTER TABLE core.entity ADD COLUMN current_revision_id UUID REFERENCES core.entity_revisions(revision_id) ON DELETE SET NULL;

-- 3. Search Boosts (Ranking Override Layer)
CREATE TABLE core.search_boosts (
    entity_id UUID PRIMARY KEY REFERENCES core.entity(entity_id) ON DELETE CASCADE,
    is_verified BOOLEAN NOT NULL DEFAULT FALSE,
    local_authority_rank NUMERIC(5,2) NOT NULL DEFAULT 1.0 CHECK (local_authority_rank > 0),
    pinned_position SMALLINT CHECK (pinned_position > 0),
    updated_by TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 4. Hidden Entities (Suppression list)
CREATE TABLE core.hidden_entities (
    entity_id UUID PRIMARY KEY REFERENCES core.entity(entity_id) ON DELETE CASCADE,
    reason TEXT NOT NULL,
    hidden_by TEXT NOT NULL,
    hidden_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 5. Locality Overrides (Admin geographic corrections)
CREATE TABLE core.locality_overrides (
    entity_id UUID PRIMARY KEY REFERENCES core.entity(entity_id) ON DELETE CASCADE,
    override_parent_place_id UUID NOT NULL REFERENCES core.place(entity_id) ON DELETE CASCADE,
    overridden_by TEXT NOT NULL,
    overridden_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 6. Tag Overrides (Admin semantic categorization corrections)
CREATE TABLE core.tag_overrides (
    entity_id UUID NOT NULL REFERENCES core.entity(entity_id) ON DELETE CASCADE,
    entity_type_id SMALLINT NOT NULL REFERENCES core.entity_type(entity_type_id) ON DELETE CASCADE,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    overridden_by TEXT NOT NULL,
    overridden_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (entity_id, entity_type_id)
);

COMMIT;
