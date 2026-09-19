-- Migration 0005: Bangla Lexicon & Transliteration Layer
-- Implements Phase A of the Bangla Dictionary Plan

BEGIN;

CREATE TABLE IF NOT EXISTS core.bangla_lexicon (
    word_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Core word identity
    bn_word        TEXT NOT NULL,                        -- বাহক (Bangla script)
    en_word        TEXT,                                 -- carrier (English anchor)
    normalised_bn  TEXT NOT NULL,                        -- lowercase, stripped diacritics

    -- Linguistic properties
    pos            TEXT,                                 -- noun/verb/adj/adv etc (filled by enrichment)
    ipa_pron       TEXT,                                 -- ˈkarēər (from pron[0])
    roman_pron     TEXT,                                 -- Bāhaka (from pron[1], raw)

    -- Definitions
    bn_definition  TEXT,                                 -- Bangla-language definition (from Wiktionary)
    en_definition  TEXT,                                 -- English-language definition (optional)

    -- Synonym/Antonym arrays
    bn_synonyms    TEXT[] DEFAULT '{}',                  -- Bangla synonyms array
    en_synonyms    TEXT[] DEFAULT '{}',                  -- English synonyms array
    bn_antonyms    TEXT[] DEFAULT '{}',                  -- Bangla antonyms (enrichment)

    -- Transliterations (Phase B — mBART + rule-based)
    transliterations TEXT[] DEFAULT '{}',               -- ['bahak', 'bahoka', 'bahok']

    -- Example sentences
    usage_sentences TEXT[] DEFAULT '{}',               -- from sents[]

    -- Lifecycle & quality
    source         TEXT NOT NULL DEFAULT 'minhaskamal', -- data lineage tag
    enrichment_state TEXT NOT NULL DEFAULT 'raw'        -- raw → wiktionary_fetched → transliterated → verified
        CHECK (enrichment_state IN ('raw', 'wiktionary_fetched', 'transliterated', 'verified')),
    has_bn_definition BOOLEAN GENERATED ALWAYS AS (bn_definition IS NOT NULL) STORED,

    -- Dedup guard
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (bn_word)  -- primary dedup key on Bangla word
);

-- Indexes
CREATE INDEX IF NOT EXISTS bangla_lexicon_bn_word_trgm   ON core.bangla_lexicon USING gin (bn_word gin_trgm_ops);
CREATE INDEX IF NOT EXISTS bangla_lexicon_norm_idx       ON core.bangla_lexicon (normalised_bn);
CREATE INDEX IF NOT EXISTS bangla_lexicon_enrichment_idx ON core.bangla_lexicon (enrichment_state);
CREATE INDEX IF NOT EXISTS bangla_lexicon_en_word_idx    ON core.bangla_lexicon (en_word);

COMMIT;
