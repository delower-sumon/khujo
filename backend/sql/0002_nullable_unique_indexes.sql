-- Follow-up for 0001_khojo_core.sql.
-- PostgreSQL UNIQUE permits multiple NULL values by default. These partial
-- indexes preserve that behaviour while enforcing uniqueness when a value is
-- actually known.

BEGIN;

ALTER TABLE core.source
    DROP CONSTRAINT source_canonical_domain_key;
CREATE UNIQUE INDEX source_canonical_domain_unique_idx
    ON core.source (canonical_domain)
    WHERE canonical_domain IS NOT NULL;

ALTER TABLE core.source_record
    DROP CONSTRAINT source_record_source_id_canonical_url_key,
    DROP CONSTRAINT source_record_source_id_external_id_key;
CREATE UNIQUE INDEX source_record_url_unique_idx
    ON core.source_record (source_id, canonical_url)
    WHERE canonical_url IS NOT NULL;
CREATE UNIQUE INDEX source_record_external_id_unique_idx
    ON core.source_record (source_id, external_id)
    WHERE external_id IS NOT NULL;

ALTER TABLE core.place
    DROP CONSTRAINT place_official_code_scheme_official_code_key;
CREATE UNIQUE INDEX place_official_code_unique_idx
    ON core.place (official_code_scheme, official_code)
    WHERE official_code_scheme IS NOT NULL AND official_code IS NOT NULL;

ALTER TABLE media.asset
    DROP CONSTRAINT asset_content_hash_key;
CREATE UNIQUE INDEX media_asset_content_hash_unique_idx
    ON media.asset (content_hash)
    WHERE content_hash IS NOT NULL;

COMMIT;
