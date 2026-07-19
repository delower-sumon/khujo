-- Khojo database core, PostgreSQL 16.
--
-- This is a one-time bootstrap migration, not an application startup script.
-- Run it with a migration role in an empty/staging database first. The
-- application role should not have CREATE EXTENSION or CREATE SCHEMA rights.
-- See docs/architecture/db-core-plan.md for the operating model and gates.

BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;

CREATE SCHEMA core;
CREATE SCHEMA crawl;
CREATE SCHEMA content;
CREATE SCHEMA search;
CREATE SCHEMA media;

CREATE TYPE core.record_state AS ENUM ('candidate', 'reviewed', 'verified', 'rejected', 'retired');
CREATE TYPE core.visibility AS ENUM ('public', 'restricted', 'private');
CREATE TYPE core.name_kind AS ENUM ('preferred', 'official', 'alias', 'abbreviation', 'transliteration', 'historical', 'misspelling');
CREATE TYPE core.script_kind AS ENUM ('bangla', 'latin', 'mixed', 'other');
CREATE TYPE core.source_kind AS ENUM ('government', 'institution', 'publisher', 'business', 'community', 'user_submission', 'crawler', 'other');
CREATE TYPE core.fetch_access AS ENUM ('crawl_allowed', 'api', 'manual_import', 'blocked', 'unknown');
CREATE TYPE crawl.frontier_state AS ENUM ('queued', 'leased', 'fetched', 'blocked', 'failed', 'retired');
CREATE TYPE crawl.fetch_state AS ENUM ('success', 'not_modified', 'redirected', 'robots_denied', 'rate_limited', 'http_error', 'network_error', 'parse_error');
CREATE TYPE content.document_kind AS ENUM ('news', 'article', 'community', 'social', 'listing', 'government', 'media');
CREATE TYPE search.suggestion_state AS ENUM ('candidate', 'active', 'suppressed', 'expired');

-- Permanent layer -----------------------------------------------------------

CREATE TABLE core.entity_type (
    entity_type_id SMALLSERIAL PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE CHECK (slug ~ '^[a-z][a-z0-9_]{1,62}$'),
    label_en TEXT NOT NULL,
    label_bn TEXT,
    parent_entity_type_id SMALLINT REFERENCES core.entity_type(entity_type_id),
    is_abstract BOOLEAN NOT NULL DEFAULT FALSE,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE core.relation_type (
    relation_type_id SMALLSERIAL PRIMARY KEY,
    slug TEXT NOT NULL UNIQUE CHECK (slug ~ '^[a-z][a-z0-9_]{1,62}$'),
    label_en TEXT NOT NULL,
    label_bn TEXT,
    inverse_slug TEXT,
    is_symmetric BOOLEAN NOT NULL DEFAULT FALSE,
    subject_type_id SMALLINT REFERENCES core.entity_type(entity_type_id),
    object_type_id SMALLINT REFERENCES core.entity_type(entity_type_id),
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK ((is_symmetric AND inverse_slug IS NULL) OR NOT is_symmetric)
);

CREATE TABLE core.source (
    source_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_name TEXT NOT NULL,
    source_kind core.source_kind NOT NULL,
    canonical_domain TEXT,
    homepage_url TEXT,
    trust_tier SMALLINT NOT NULL DEFAULT 0 CHECK (trust_tier BETWEEN 0 AND 5),
    access_method core.fetch_access NOT NULL DEFAULT 'unknown',
    robots_checked_at TIMESTAMPTZ,
    crawl_delay_seconds SMALLINT CHECK (crawl_delay_seconds BETWEEN 0 AND 86400),
    licence_note TEXT,
    contact_url TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE NULLS NOT DISTINCT (canonical_domain)
);

-- A source record is the stable identity of an URL or imported record. It
-- preserves provenance even when the temporary content body expires.
CREATE TABLE core.source_record (
    source_record_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID REFERENCES core.source(source_id) ON DELETE SET NULL,
    canonical_url TEXT,
    external_id TEXT,
    title TEXT,
    language_code TEXT CHECK (language_code IS NULL OR language_code ~ '^[a-z]{2,3}(-[A-Z]{2})?$'),
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_content_hash CHAR(64),
    state core.record_state NOT NULL DEFAULT 'candidate',
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (canonical_url IS NOT NULL OR external_id IS NOT NULL),
    UNIQUE NULLS NOT DISTINCT (source_id, canonical_url),
    UNIQUE NULLS NOT DISTINCT (source_id, external_id)
);

CREATE INDEX source_record_url_trgm_idx
    ON core.source_record USING gin (canonical_url gin_trgm_ops);

CREATE TABLE core.entity (
    entity_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type_id SMALLINT NOT NULL REFERENCES core.entity_type(entity_type_id),
    display_name TEXT NOT NULL,
    preferred_language_code TEXT NOT NULL DEFAULT 'bn' CHECK (preferred_language_code ~ '^[a-z]{2,3}(-[A-Z]{2})?$'),
    state core.record_state NOT NULL DEFAULT 'candidate',
    visibility core.visibility NOT NULL DEFAULT 'public',
    summary TEXT,
    valid_from DATE,
    valid_to DATE,
    merged_into_entity_id UUID REFERENCES core.entity(entity_id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from),
    CHECK (merged_into_entity_id IS NULL OR merged_into_entity_id <> entity_id)
);

CREATE INDEX entity_type_state_idx ON core.entity (entity_type_id, state, visibility);
CREATE INDEX entity_display_name_trgm_idx ON core.entity USING gin (display_name gin_trgm_ops);

CREATE TABLE core.entity_name (
    entity_name_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id UUID NOT NULL REFERENCES core.entity(entity_id) ON DELETE CASCADE,
    name TEXT NOT NULL CHECK (btrim(name) <> ''),
    normalised_name TEXT NOT NULL CHECK (btrim(normalised_name) <> ''),
    language_code TEXT NOT NULL CHECK (language_code ~ '^[a-z]{2,3}(-[A-Z]{2})?$'),
    script core.script_kind NOT NULL,
    name_kind core.name_kind NOT NULL,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    source_record_id UUID REFERENCES core.source_record(source_record_id) ON DELETE SET NULL,
    state core.record_state NOT NULL DEFAULT 'candidate',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (entity_id, normalised_name, language_code, name_kind)
);

CREATE UNIQUE INDEX entity_name_one_primary_per_language_idx
    ON core.entity_name (entity_id, language_code)
    WHERE is_primary;
CREATE INDEX entity_name_normalised_trgm_idx
    ON core.entity_name USING gin (normalised_name gin_trgm_ops);
CREATE INDEX entity_name_entity_idx ON core.entity_name (entity_id, state);

CREATE TABLE core.entity_identifier (
    entity_identifier_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_id UUID NOT NULL REFERENCES core.entity(entity_id) ON DELETE CASCADE,
    identifier_scheme TEXT NOT NULL,
    identifier_value TEXT NOT NULL,
    source_record_id UUID REFERENCES core.source_record(source_record_id) ON DELETE SET NULL,
    state core.record_state NOT NULL DEFAULT 'candidate',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (identifier_scheme, identifier_value)
);

-- Places are entities so every place has aliases, claims, sources and graph
-- edges. The parent pointer stores the administrative/physical containment tree.
CREATE TABLE core.place (
    entity_id UUID PRIMARY KEY REFERENCES core.entity(entity_id) ON DELETE CASCADE,
    parent_place_id UUID REFERENCES core.place(entity_id),
    official_code_scheme TEXT,
    official_code TEXT,
    latitude NUMERIC(9,6) CHECK (latitude BETWEEN -90 AND 90),
    longitude NUMERIC(9,6) CHECK (longitude BETWEEN -180 AND 180),
    boundary_geojson JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (parent_place_id IS NULL OR parent_place_id <> entity_id),
    UNIQUE NULLS NOT DISTINCT (official_code_scheme, official_code)
);

CREATE INDEX place_parent_idx ON core.place (parent_place_id);

CREATE TABLE core.entity_place (
    entity_id UUID NOT NULL REFERENCES core.entity(entity_id) ON DELETE CASCADE,
    place_id UUID NOT NULL REFERENCES core.place(entity_id) ON DELETE RESTRICT,
    relation TEXT NOT NULL CHECK (relation IN ('located_in', 'serves', 'originates_in', 'headquartered_in', 'operates_in')),
    address_text TEXT,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    valid_from DATE,
    valid_to DATE,
    source_record_id UUID REFERENCES core.source_record(source_record_id) ON DELETE SET NULL,
    state core.record_state NOT NULL DEFAULT 'candidate',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (entity_id, place_id, relation),
    CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from)
);

CREATE UNIQUE INDEX entity_place_one_primary_idx
    ON core.entity_place (entity_id)
    WHERE is_primary;
CREATE INDEX entity_place_place_idx ON core.entity_place (place_id, relation, state);

-- An assertion is a fact-shaped graph edge. It can point to another entity or
-- carry a typed scalar/object value. Evidence makes it auditable and temporal.
CREATE TABLE core.assertion (
    assertion_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_entity_id UUID NOT NULL REFERENCES core.entity(entity_id) ON DELETE CASCADE,
    relation_type_id SMALLINT NOT NULL REFERENCES core.relation_type(relation_type_id),
    object_entity_id UUID REFERENCES core.entity(entity_id) ON DELETE RESTRICT,
    object_value JSONB,
    language_code TEXT CHECK (language_code IS NULL OR language_code ~ '^[a-z]{2,3}(-[A-Z]{2})?$'),
    state core.record_state NOT NULL DEFAULT 'candidate',
    confidence NUMERIC(4,3) NOT NULL DEFAULT 0.500 CHECK (confidence BETWEEN 0 AND 1),
    valid_from DATE,
    valid_to DATE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK ((object_entity_id IS NOT NULL) <> (object_value IS NOT NULL)),
    CHECK (object_entity_id IS NULL OR object_entity_id <> subject_entity_id),
    CHECK (valid_to IS NULL OR valid_from IS NULL OR valid_to >= valid_from)
);

CREATE INDEX assertion_subject_idx ON core.assertion (subject_entity_id, state, relation_type_id);
CREATE INDEX assertion_object_idx ON core.assertion (object_entity_id, state, relation_type_id)
    WHERE object_entity_id IS NOT NULL;
CREATE INDEX assertion_value_idx ON core.assertion USING gin (object_value jsonb_path_ops)
    WHERE object_value IS NOT NULL;

CREATE TABLE core.assertion_evidence (
    assertion_evidence_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    assertion_id UUID NOT NULL REFERENCES core.assertion(assertion_id) ON DELETE CASCADE,
    source_record_id UUID NOT NULL REFERENCES core.source_record(source_record_id) ON DELETE RESTRICT,
    quoted_text TEXT,
    locator JSONB NOT NULL DEFAULT '{}'::jsonb,
    extraction_method TEXT NOT NULL DEFAULT 'manual',
    observed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (assertion_id, source_record_id, extraction_method)
);

CREATE INDEX assertion_evidence_source_idx ON core.assertion_evidence (source_record_id);

CREATE TABLE media.asset (
    asset_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_record_id UUID REFERENCES core.source_record(source_record_id) ON DELETE SET NULL,
    object_url TEXT NOT NULL UNIQUE,
    original_url TEXT,
    media_kind TEXT NOT NULL CHECK (media_kind IN ('image', 'video', 'audio', 'document', 'favicon')),
    content_hash CHAR(64),
    mime_type TEXT,
    width_px INTEGER CHECK (width_px IS NULL OR width_px > 0),
    height_px INTEGER CHECK (height_px IS NULL OR height_px > 0),
    alt_text TEXT,
    state core.record_state NOT NULL DEFAULT 'candidate',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE NULLS NOT DISTINCT (content_hash)
);

CREATE TABLE media.entity_asset (
    entity_id UUID NOT NULL REFERENCES core.entity(entity_id) ON DELETE CASCADE,
    asset_id UUID NOT NULL REFERENCES media.asset(asset_id) ON DELETE CASCADE,
    role TEXT NOT NULL CHECK (role IN ('logo', 'cover', 'thumbnail', 'gallery', 'map', 'other')),
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (entity_id, asset_id, role)
);

CREATE UNIQUE INDEX entity_asset_one_primary_per_role_idx
    ON media.entity_asset (entity_id, role)
    WHERE is_primary;

-- Temporary discovery and content layer ------------------------------------

CREATE TABLE crawl.host_policy (
    host TEXT PRIMARY KEY,
    source_id UUID REFERENCES core.source(source_id) ON DELETE SET NULL,
    access_method core.fetch_access NOT NULL DEFAULT 'unknown',
    crawl_delay_seconds SMALLINT NOT NULL DEFAULT 5 CHECK (crawl_delay_seconds BETWEEN 0 AND 86400),
    max_concurrency SMALLINT NOT NULL DEFAULT 1 CHECK (max_concurrency BETWEEN 1 AND 10),
    robots_url TEXT,
    robots_fetched_at TIMESTAMPTZ,
    robots_text TEXT,
    allow_crawl BOOLEAN NOT NULL DEFAULT FALSE,
    next_allowed_at TIMESTAMPTZ,
    note TEXT,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE crawl.frontier_url (
    frontier_url_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_id UUID REFERENCES core.source(source_id) ON DELETE SET NULL,
    host TEXT NOT NULL,
    original_url TEXT NOT NULL,
    canonical_url TEXT NOT NULL,
    url_hash CHAR(64) NOT NULL UNIQUE,
    discovered_from_source_record_id UUID REFERENCES core.source_record(source_record_id) ON DELETE SET NULL,
    state crawl.frontier_state NOT NULL DEFAULT 'queued',
    priority SMALLINT NOT NULL DEFAULT 0 CHECK (priority BETWEEN -1000 AND 1000),
    depth SMALLINT NOT NULL DEFAULT 0 CHECK (depth BETWEEN 0 AND 100),
    next_fetch_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_fetch_at TIMESTAMPTZ,
    last_status_code SMALLINT,
    failure_count SMALLINT NOT NULL DEFAULT 0 CHECK (failure_count BETWEEN 0 AND 100),
    lease_token UUID,
    lease_expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (canonical_url),
    CHECK ((state = 'leased') = (lease_token IS NOT NULL AND lease_expires_at IS NOT NULL))
);

CREATE INDEX frontier_lease_idx ON crawl.frontier_url (priority DESC, next_fetch_at, created_at)
    WHERE state = 'queued';
CREATE INDEX frontier_host_idx ON crawl.frontier_url (host, state, next_fetch_at);

CREATE TABLE crawl.fetch (
    fetch_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    frontier_url_id UUID NOT NULL REFERENCES crawl.frontier_url(frontier_url_id) ON DELETE CASCADE,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    state crawl.fetch_state NOT NULL,
    http_status SMALLINT,
    final_url TEXT,
    etag TEXT,
    last_modified TEXT,
    content_type TEXT,
    content_language TEXT,
    response_bytes BIGINT CHECK (response_bytes IS NULL OR response_bytes >= 0),
    content_hash CHAR(64),
    object_storage_key TEXT,
    error_code TEXT,
    error_detail TEXT,
    parser_version TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX fetch_frontier_time_idx ON crawl.fetch (frontier_url_id, started_at DESC);
CREATE INDEX fetch_content_hash_idx ON crawl.fetch (content_hash) WHERE content_hash IS NOT NULL;

CREATE TABLE content.retention_policy (
    document_kind content.document_kind PRIMARY KEY,
    retention_interval INTERVAL NOT NULL,
    archive_before_delete BOOLEAN NOT NULL DEFAULT TRUE,
    description TEXT NOT NULL
);

INSERT INTO content.retention_policy (document_kind, retention_interval, archive_before_delete, description) VALUES
    ('news', '30 days', TRUE, 'Time-sensitive reporting'),
    ('article', '90 days', TRUE, 'Long-form editorial content'),
    ('community', '180 days', TRUE, 'Forums and community posts'),
    ('social', '7 days', FALSE, 'Short-lived social snippets'),
    ('listing', '90 days', TRUE, 'Commercial listings and offers'),
    ('government', '365 days', TRUE, 'Government notices and public records'),
    ('media', '90 days', TRUE, 'Media pages and transcripts')
ON CONFLICT (document_kind) DO UPDATE SET
    retention_interval = EXCLUDED.retention_interval,
    archive_before_delete = EXCLUDED.archive_before_delete,
    description = EXCLUDED.description;

CREATE FUNCTION content.apply_retention_policy()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    policy_interval INTERVAL;
BEGIN
    SELECT retention_interval INTO policy_interval
    FROM content.retention_policy
    WHERE document_kind = NEW.document_kind;

    IF NEW.expires_at IS NULL THEN
        NEW.expires_at := COALESCE(NEW.published_at, NEW.discovered_at, now()) + policy_interval;
    END IF;
    RETURN NEW;
END;
$$;

-- List partitions are the retrieval segments. Add a time sub-partition only
-- after measurements show a segment needs it; that avoids operationally fragile
-- empty monthly partitions during the MVP.
CREATE TABLE content.document (
    document_id UUID NOT NULL DEFAULT gen_random_uuid(),
    document_kind content.document_kind NOT NULL,
    source_record_id UUID NOT NULL REFERENCES core.source_record(source_record_id) ON DELETE RESTRICT,
    fetch_id UUID REFERENCES crawl.fetch(fetch_id) ON DELETE SET NULL,
    canonical_url TEXT NOT NULL,
    title TEXT,
    title_normalised TEXT,
    body_text TEXT,
    body_normalised TEXT,
    language_code TEXT CHECK (language_code IS NULL OR language_code ~ '^[a-z]{2,3}(-[A-Z]{2})?$'),
    author_text TEXT,
    published_at TIMESTAMPTZ,
    discovered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at TIMESTAMPTZ,
    content_hash CHAR(64),
    word_count INTEGER CHECK (word_count IS NULL OR word_count >= 0),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    state core.record_state NOT NULL DEFAULT 'candidate',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (document_id, document_kind),
    UNIQUE (source_record_id, document_kind)
) PARTITION BY LIST (document_kind);

CREATE TABLE content.document_news PARTITION OF content.document FOR VALUES IN ('news');
CREATE TABLE content.document_article PARTITION OF content.document FOR VALUES IN ('article');
CREATE TABLE content.document_community PARTITION OF content.document FOR VALUES IN ('community');
CREATE TABLE content.document_social PARTITION OF content.document FOR VALUES IN ('social');
CREATE TABLE content.document_listing PARTITION OF content.document FOR VALUES IN ('listing');
CREATE TABLE content.document_government PARTITION OF content.document FOR VALUES IN ('government');
CREATE TABLE content.document_media PARTITION OF content.document FOR VALUES IN ('media');

CREATE TRIGGER document_apply_retention_policy
BEFORE INSERT ON content.document
FOR EACH ROW EXECUTE FUNCTION content.apply_retention_policy();

CREATE INDEX document_live_by_kind_idx
    ON content.document (document_kind, expires_at, published_at DESC)
    WHERE state IN ('candidate', 'reviewed', 'verified');
CREATE INDEX document_title_trgm_idx ON content.document USING gin (title_normalised gin_trgm_ops);
CREATE INDEX document_body_trgm_idx ON content.document USING gin (body_normalised gin_trgm_ops);

CREATE TABLE content.entity_mention (
    entity_mention_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_record_id UUID NOT NULL REFERENCES core.source_record(source_record_id) ON DELETE CASCADE,
    entity_id UUID NOT NULL REFERENCES core.entity(entity_id) ON DELETE CASCADE,
    surface_form TEXT NOT NULL,
    character_start INTEGER CHECK (character_start IS NULL OR character_start >= 0),
    character_end INTEGER CHECK (character_end IS NULL OR character_end >= character_start),
    confidence NUMERIC(4,3) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    extraction_method TEXT NOT NULL,
    state core.record_state NOT NULL DEFAULT 'candidate',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source_record_id, entity_id, surface_form, character_start)
);

CREATE INDEX entity_mention_entity_idx ON content.entity_mention (entity_id, state);

-- Search layer --------------------------------------------------------------

CREATE TABLE search.suggestion (
    suggestion_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    phrase TEXT NOT NULL,
    phrase_normalised TEXT NOT NULL,
    language_code TEXT NOT NULL DEFAULT 'bn' CHECK (language_code ~ '^[a-z]{2,3}(-[A-Z]{2})?$'),
    script core.script_kind NOT NULL DEFAULT 'bangla',
    entity_id UUID REFERENCES core.entity(entity_id) ON DELETE SET NULL,
    intent TEXT,
    vertical TEXT,
    source_kind TEXT NOT NULL DEFAULT 'curated',
    priority SMALLINT NOT NULL DEFAULT 0 CHECK (priority BETWEEN -1000 AND 1000),
    popularity_score NUMERIC(12,4) NOT NULL DEFAULT 0,
    state search.suggestion_state NOT NULL DEFAULT 'candidate',
    expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (phrase_normalised, language_code, entity_id)
);

CREATE INDEX suggestion_active_prefix_idx
    ON search.suggestion (language_code, priority DESC, popularity_score DESC, phrase_normalised)
    WHERE state = 'active';
CREATE INDEX suggestion_phrase_trgm_idx ON search.suggestion USING gin (phrase_normalised gin_trgm_ops);

-- Store a one-way, rotating-salt query fingerprint instead of a user identity.
-- Retain raw query text only if the user-facing privacy policy explicitly allows
-- it; otherwise use normalised_query = NULL and aggregate outside this table.
CREATE TABLE search.query_event (
    query_event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    occurred_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    query_fingerprint CHAR(64) NOT NULL,
    normalised_query TEXT,
    language_code TEXT,
    inferred_intent TEXT,
    result_count INTEGER CHECK (result_count IS NULL OR result_count >= 0),
    clicked_source_record_id UUID REFERENCES core.source_record(source_record_id) ON DELETE SET NULL,
    clicked_entity_id UUID REFERENCES core.entity(entity_id) ON DELETE SET NULL,
    latency_ms INTEGER CHECK (latency_ms IS NULL OR latency_ms >= 0),
    expires_at TIMESTAMPTZ NOT NULL DEFAULT (now() + INTERVAL '30 days')
);

CREATE INDEX query_event_expiry_idx ON search.query_event (expires_at);
CREATE INDEX query_event_trends_idx ON search.query_event (occurred_at DESC, inferred_intent);

-- Seed taxonomy -------------------------------------------------------------

INSERT INTO core.entity_type (slug, label_en, label_bn, is_abstract, description) VALUES
    ('thing', 'Thing', 'বস্তু', TRUE, 'Root for every permitted graph entity'),
    ('place', 'Place', 'স্থান', TRUE, 'Geographic or addressable place'),
    ('administrative_area', 'Administrative area', 'প্রশাসনিক এলাকা', FALSE, 'Country through ward and local administration'),
    ('settlement', 'Settlement', 'বসতি', FALSE, 'City, town, village, neighbourhood or mohalla'),
    ('address', 'Address', 'ঠিকানা', FALSE, 'Public address, postal area or location'),
    ('natural_feature', 'Natural feature', 'প্রাকৃতিক বৈশিষ্ট্য', FALSE, 'River, wetland, forest, hill or other feature'),
    ('transport_route', 'Transport route or stop', 'পরিবহন পথ বা স্টপ', FALSE, 'Road, rail, launch route, terminal or stop'),
    ('person', 'Person', 'ব্যক্তি', FALSE, 'Publicly indexable person'),
    ('group', 'Group or community', 'গোষ্ঠী বা সম্প্রদায়', FALSE, 'Community, association or informal group'),
    ('organization', 'Organization', 'প্রতিষ্ঠান', TRUE, 'Institution or formal organization'),
    ('government_body', 'Government body', 'সরকারি সংস্থা', FALSE, 'Ministry, agency, local authority or public office'),
    ('education_institution', 'Educational institution', 'শিক্ষা প্রতিষ্ঠান', FALSE, 'School, college, university, madrasa or training centre'),
    ('healthcare_facility', 'Healthcare facility', 'স্বাস্থ্যসেবা প্রতিষ্ঠান', FALSE, 'Hospital, clinic, diagnostic centre or pharmacy'),
    ('nonprofit', 'Nonprofit', 'অলাভজনক প্রতিষ্ঠান', FALSE, 'NGO, foundation or charity'),
    ('company', 'Company', 'কোম্পানি', FALSE, 'Registered company or enterprise'),
    ('business', 'Business', 'ব্যবসা', FALSE, 'Shop, branch, restaurant, market seller or service provider'),
    ('brand', 'Brand', 'ব্র্যান্ড', FALSE, 'Brand or product line'),
    ('product', 'Product', 'পণ্য', FALSE, 'Good, agricultural item or digital product'),
    ('service', 'Service', 'সেবা', FALSE, 'Public, commercial or professional service'),
    ('job', 'Job or occupation', 'চাকরি বা পেশা', FALSE, 'Job listing, occupation or career role'),
    ('facility', 'Facility or infrastructure', 'স্থাপনা বা অবকাঠামো', FALSE, 'Utility, building, bridge, plant, market or public facility'),
    ('event', 'Event', 'ঘটনা বা আয়োজন', FALSE, 'Event, observance, sports fixture, campaign or alert'),
    ('public_program', 'Public programme', 'জনসেবামূলক কর্মসূচি', FALSE, 'Government programme, project, tender or benefit'),
    ('legal_instrument', 'Legal instrument', 'আইনি দলিল', FALSE, 'Law, regulation, policy, notice or licence'),
    ('statistic', 'Statistic or dataset', 'পরিসংখ্যান বা উপাত্ত', FALSE, 'Official statistic, indicator or dataset'),
    ('topic', 'Topic or language term', 'বিষয় বা ভাষার শব্দ', FALSE, 'Concept, subject, Bangla term or named topic'),
    ('creative_work', 'Creative work', 'সৃজনশীল কাজ', FALSE, 'Book, song, film, artwork or software work'),
    ('document', 'Document or page', 'নথি বা পৃষ্ঠা', FALSE, 'Article, report, webpage, form or publication'),
    ('media_item', 'Media item', 'মিডিয়া উপকরণ', FALSE, 'Image, video, audio or media collection')
ON CONFLICT (slug) DO UPDATE SET
    label_en = EXCLUDED.label_en,
    label_bn = EXCLUDED.label_bn,
    is_abstract = EXCLUDED.is_abstract,
    description = EXCLUDED.description;

UPDATE core.entity_type child
SET parent_entity_type_id = parent.entity_type_id
FROM core.entity_type parent
WHERE (child.slug, parent.slug) IN (
    ('place', 'thing'), ('administrative_area', 'place'), ('settlement', 'place'), ('address', 'place'),
    ('natural_feature', 'place'), ('transport_route', 'place'), ('person', 'thing'), ('group', 'thing'),
    ('organization', 'thing'), ('government_body', 'organization'), ('education_institution', 'organization'),
    ('healthcare_facility', 'organization'), ('nonprofit', 'organization'), ('company', 'organization'),
    ('business', 'organization'), ('brand', 'thing'), ('product', 'thing'), ('service', 'thing'),
    ('job', 'thing'), ('facility', 'thing'), ('event', 'thing'), ('public_program', 'thing'),
    ('legal_instrument', 'thing'), ('statistic', 'thing'), ('topic', 'thing'),
    ('creative_work', 'thing'), ('document', 'thing'), ('media_item', 'thing')
);

INSERT INTO core.relation_type (slug, label_en, label_bn, inverse_slug, is_symmetric, description) VALUES
    ('instance_of', 'is an instance of', 'এর উদাহরণ', NULL, FALSE, 'Entity to taxonomy relationship'),
    ('same_as', 'same as', 'একই সত্তা', NULL, TRUE, 'Confirmed identity equivalence'),
    ('located_in', 'located in', 'অবস্থিত', 'contains', FALSE, 'Entity or place containment'),
    ('contains', 'contains', 'ধারণ করে', 'located_in', FALSE, 'Inverse containment'),
    ('part_of', 'part of', 'অংশ', 'has_part', FALSE, 'Component relationship'),
    ('has_part', 'has part', 'অংশ আছে', 'part_of', FALSE, 'Inverse component relationship'),
    ('operated_by', 'operated by', 'পরিচালিত', 'operates', FALSE, 'Operator relationship'),
    ('operates', 'operates', 'পরিচালনা করে', 'operated_by', FALSE, 'Inverse operator relationship'),
    ('owned_by', 'owned by', 'মালিকানাধীন', 'owns', FALSE, 'Ownership relationship'),
    ('owns', 'owns', 'মালিক', 'owned_by', FALSE, 'Inverse ownership relationship'),
    ('member_of', 'member of', 'সদস্য', 'has_member', FALSE, 'Membership relationship'),
    ('has_member', 'has member', 'সদস্য আছে', 'member_of', FALSE, 'Inverse membership relationship'),
    ('employs', 'employs', 'নিয়োগ দেয়', 'employed_by', FALSE, 'Employment relationship'),
    ('employed_by', 'employed by', 'নিযুক্ত', 'employs', FALSE, 'Inverse employment relationship'),
    ('provides', 'provides', 'সেবা দেয়', 'provided_by', FALSE, 'Service relationship'),
    ('provided_by', 'provided by', 'প্রদান করে', 'provides', FALSE, 'Inverse service relationship'),
    ('produces', 'produces', 'উৎপাদন করে', 'produced_by', FALSE, 'Product relationship'),
    ('produced_by', 'produced by', 'উৎপাদক', 'produces', FALSE, 'Inverse product relationship'),
    ('published_by', 'published by', 'প্রকাশিত', 'publishes', FALSE, 'Publication relationship'),
    ('publishes', 'publishes', 'প্রকাশ করে', 'published_by', FALSE, 'Inverse publication relationship'),
    ('authored_by', 'authored by', 'লিখেছেন', 'authors', FALSE, 'Authorship relationship'),
    ('authors', 'authors', 'লেখক', 'authored_by', FALSE, 'Inverse authorship relationship'),
    ('governed_by', 'governed by', 'শাসিত', 'governs', FALSE, 'Administrative relationship'),
    ('governs', 'governs', 'শাসন করে', 'governed_by', FALSE, 'Inverse administrative relationship'),
    ('succeeds', 'succeeds', 'স্থলাভিষিক্ত', 'preceded_by', FALSE, 'Historical succession'),
    ('preceded_by', 'preceded by', 'পূর্বসূরি', 'succeeds', FALSE, 'Historical succession inverse'),
    ('related_to', 'related to', 'সম্পর্কিত', NULL, TRUE, 'Weak, explained association'),
    ('about', 'about', 'সম্পর্কে', NULL, FALSE, 'Document or work topic relationship'),
    ('cites', 'cites', 'উদ্ধৃত করে', 'cited_by', FALSE, 'Citation relationship'),
    ('cited_by', 'cited by', 'উদ্ধৃত হয়েছে', 'cites', FALSE, 'Citation inverse')
ON CONFLICT (slug) DO UPDATE SET
    label_en = EXCLUDED.label_en,
    label_bn = EXCLUDED.label_bn,
    inverse_slug = EXCLUDED.inverse_slug,
    is_symmetric = EXCLUDED.is_symmetric,
    description = EXCLUDED.description;

COMMIT;

-- Operational queries, run by a scheduled worker rather than at request time:
--   DELETE FROM search.query_event WHERE expires_at < now();
--   -- Export archive-eligible content to object storage, then:
--   DELETE FROM content.document WHERE expires_at < now();
--
-- Promotion guard (application or deferred trigger): an assertion may be set to
-- 'verified' only if at least one core.assertion_evidence row exists.
