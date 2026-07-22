"""
KhujoBot v1 — Phase 0: Geographic Entity Seeder (seed_geography.py)
Seeds Bangladesh's administrative hierarchy (Country -> Division -> District -> Upazila -> Union)
into core.entity, core.place, core.entity_name, and search.suggestion.
"""

import os
import json
import logging
from sqlalchemy import text
from utils.db import get_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("seed_geography")

DATA_FILE = os.path.join(os.path.dirname(__file__), "data", "bd_admin_hierarchy.json")

def seed_geography():
    if not os.path.exists(DATA_FILE):
        log.error("Geographic data file not found: %s", DATA_FILE)
        return

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    engine = get_engine()

    with engine.begin() as conn:
        # 1. Get entity_type_id for slug 'administrative_area'
        entity_type_id = conn.execute(text("""
            SELECT entity_type_id FROM core.entity_type WHERE slug = 'administrative_area' LIMIT 1
        """)).scalar()

        if not entity_type_id:
            log.error("entity_type with slug 'administrative_area' not found!")
            return

        log.info("Using entity_type_id: %s for administrative_area", entity_type_id)

        # 2. Seed Country: Bangladesh
        country_entity_id = conn.execute(text("""
            SELECT entity_id FROM core.entity_name WHERE normalised_name = 'bangladesh' LIMIT 1
        """)).scalar()

        if not country_entity_id:
            country_entity_id = conn.execute(text("""
                INSERT INTO core.entity (entity_type_id, display_name, summary, preferred_language_code, state)
                VALUES (:etid, 'বাংলাদেশ', 'বাংলাদেশ দক্ষিণ এশিয়ার একটি স্বাধীন সার্বভৌম রাষ্ট্র।', 'bn', 'verified')
                RETURNING entity_id
            """), {"etid": entity_type_id}).scalar()

            # Names
            for name, lang, script, nkind in [("বাংলাদেশ", "bn", "bangla", "official"), ("Bangladesh", "en", "latin", "preferred"), ("BD", "en", "latin", "abbreviation")]:
                conn.execute(text("""
                    INSERT INTO core.entity_name (entity_id, language_code, script, name_kind, name, normalised_name, is_primary, state)
                    VALUES (:eid, :lang, :script, :nkind, :name, lower(:name), :pref, 'verified')
                    ON CONFLICT DO NOTHING
                """), {"eid": country_entity_id, "lang": lang, "script": script, "nkind": nkind, "name": name, "pref": (lang == "bn")})

            # Place
            conn.execute(text("""
                INSERT INTO core.place (entity_id, latitude, longitude, official_code)
                VALUES (:eid, 23.6850, 90.3563, 'BD')
                ON CONFLICT DO NOTHING
            """), {"eid": country_entity_id})

            country_place_id = country_entity_id
        else:
            country_place_id = country_entity_id

        log.info("Country Bangladesh seeded (entity_id: %s)", country_entity_id)

        # 3. Seed Divisions -> Districts -> Upazilas -> Unions
        division_count = 0
        district_count = 0
        upazila_count = 0
        union_count = 0

        for div in data.get("divisions", []):
            div_name_bn = div["name_bn"]
            div_name_en = div["name_en"]

            # Division entity
            div_entity_id = conn.execute(text("""
                INSERT INTO core.entity (entity_type_id, display_name, summary, preferred_language_code, state)
                VALUES (:etid, :name_bn, :summary, 'bn', 'verified')
                RETURNING entity_id
            """), {"etid": entity_type_id, "name_bn": div_name_bn, "summary": div.get("summary", "")}).scalar()

            # Division names
            for name, lang, script, nkind in [(div_name_bn, "bn", "bangla", "official"), (div_name_en, "en", "latin", "preferred"), (div.get("name_banglish"), "en", "latin", "transliteration")]:
                if name:
                    conn.execute(text("""
                        INSERT INTO core.entity_name (entity_id, language_code, script, name_kind, name, normalised_name, is_primary, state)
                        VALUES (:eid, :lang, :script, :nkind, :name, lower(:name), :pref, 'verified')
                        ON CONFLICT DO NOTHING
                    """), {"eid": div_entity_id, "lang": lang, "script": script, "nkind": nkind, "name": name, "pref": (lang == "bn")})

            # Division place
            conn.execute(text("""
                INSERT INTO core.place (entity_id, parent_place_id, latitude, longitude, official_code)
                VALUES (:eid, :pid, :lat, :lon, :code)
                ON CONFLICT DO NOTHING
            """), {"eid": div_entity_id, "pid": country_place_id, "lat": div.get("lat"), "lon": div.get("lon"), "code": div.get("code")})

            # Autocomplete suggestions
            for phrase in [div_name_bn, div_name_en]:
                conn.execute(text("""
                    INSERT INTO search.suggestion (phrase, phrase_normalised, language_code, source_kind, priority, state)
                    VALUES (:phrase, lower(:phrase), 'bn', 'curated', 10, 'active')
                    ON CONFLICT DO NOTHING
                """), {"phrase": phrase})

            division_count += 1

            # Districts
            for dist in div.get("districts", []):
                dist_name_bn = dist["name_bn"]
                dist_name_en = dist["name_en"]

                dist_entity_id = conn.execute(text("""
                    INSERT INTO core.entity (entity_type_id, display_name, summary, preferred_language_code, state)
                    VALUES (:etid, :name_bn, :summary, 'bn', 'verified')
                    RETURNING entity_id
                """), {"etid": entity_type_id, "name_bn": dist_name_bn, "summary": dist.get("summary", "")}).scalar()

                for name, lang, script, nkind in [(dist_name_bn, "bn", "bangla", "official"), (dist_name_en, "en", "latin", "preferred"), (dist.get("name_banglish"), "en", "latin", "transliteration")]:
                    if name:
                        conn.execute(text("""
                            INSERT INTO core.entity_name (entity_id, language_code, script, name_kind, name, normalised_name, is_primary, state)
                            VALUES (:eid, :lang, :script, :nkind, :name, lower(:name), :pref, 'verified')
                            ON CONFLICT DO NOTHING
                        """), {"eid": dist_entity_id, "lang": lang, "script": script, "nkind": nkind, "name": name, "pref": (lang == "bn")})

                conn.execute(text("""
                    INSERT INTO core.place (entity_id, parent_place_id, latitude, longitude, official_code)
                    VALUES (:eid, :pid, :lat, :lon, :code)
                    ON CONFLICT DO NOTHING
                """), {"eid": dist_entity_id, "pid": div_entity_id, "lat": dist.get("lat"), "lon": dist.get("lon"), "code": dist.get("code")})

                for phrase in [dist_name_bn, dist_name_en]:
                    conn.execute(text("""
                        INSERT INTO search.suggestion (phrase, phrase_normalised, language_code, source_kind, priority, state)
                        VALUES (:phrase, lower(:phrase), 'bn', 'curated', 9, 'active')
                        ON CONFLICT DO NOTHING
                    """), {"phrase": phrase})

                district_count += 1

                # Upazilas
                for upz in dist.get("upazilas", []):
                    upz_name_bn = upz["name_bn"]
                    upz_name_en = upz["name_en"]

                    upz_entity_id = conn.execute(text("""
                        INSERT INTO core.entity (entity_type_id, display_name, summary, preferred_language_code, state)
                        VALUES (:etid, :name_bn, :summary, 'bn', 'verified')
                        RETURNING entity_id
                    """), {"etid": entity_type_id, "name_bn": upz_name_bn, "summary": f"{upz_name_bn} উপজেলা, {dist_name_bn} জেলা"}).scalar()

                    for name, lang, script, nkind in [(upz_name_bn, "bn", "bangla", "official"), (upz_name_en, "en", "latin", "preferred"), (upz.get("name_banglish"), "en", "latin", "transliteration")]:
                        if name:
                            conn.execute(text("""
                                INSERT INTO core.entity_name (entity_id, language_code, script, name_kind, name, normalised_name, is_primary, state)
                                VALUES (:eid, :lang, :script, :nkind, :name, lower(:name), :pref, 'verified')
                                ON CONFLICT DO NOTHING
                            """), {"eid": upz_entity_id, "lang": lang, "script": script, "nkind": nkind, "name": name, "pref": (lang == "bn")})

                    conn.execute(text("""
                        INSERT INTO core.place (entity_id, parent_place_id, latitude, longitude)
                        VALUES (:eid, :pid, :lat, :lon)
                        ON CONFLICT DO NOTHING
                    """), {"eid": upz_entity_id, "pid": dist_entity_id, "lat": upz.get("lat"), "lon": upz.get("lon")})

                    for phrase in [upz_name_bn, upz_name_en]:
                        conn.execute(text("""
                            INSERT INTO search.suggestion (phrase, phrase_normalised, language_code, source_kind, priority, state)
                            VALUES (:phrase, lower(:phrase), 'bn', 'curated', 8, 'active')
                            ON CONFLICT DO NOTHING
                        """), {"phrase": phrase})

                    upazila_count += 1

                    # Unions
                    for union_name in upz.get("unions", []):
                        union_entity_id = conn.execute(text("""
                            INSERT INTO core.entity (entity_type_id, display_name, summary, preferred_language_code, state)
                            VALUES (:etid, :name_bn, :summary, 'bn', 'verified')
                            RETURNING entity_id
                        """), {"etid": entity_type_id, "name_bn": union_name, "summary": f"{union_name} ইউনিয়ন, {upz_name_bn} উপজেলা"}).scalar()

                        conn.execute(text("""
                            INSERT INTO core.entity_name (entity_id, language_code, script, name_kind, name, normalised_name, is_primary, state)
                            VALUES (:eid, 'bn', 'bangla', 'official', :name, lower(:name), true, 'verified')
                            ON CONFLICT DO NOTHING
                        """), {"eid": union_entity_id, "name": union_name})

                        conn.execute(text("""
                            INSERT INTO core.place (entity_id, parent_place_id)
                            VALUES (:eid, :pid)
                            ON CONFLICT DO NOTHING
                        """), {"eid": union_entity_id, "pid": upz_entity_id})

                        union_count += 1

        log.info("Geographic Seeding Summary:")
        log.info("  Divisions seeded:  %d", division_count)
        log.info("  Districts seeded:  %d", district_count)
        log.info("  Upazilas seeded:   %d", upazila_count)
        log.info("  Unions seeded:     %d", union_count)

if __name__ == "__main__":
    seed_geography()
