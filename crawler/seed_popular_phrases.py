"""
Khujo Seeder — Seed Popular Autocomplete Search Phrases (seed_popular_phrases.py)
Seeds popular Bangla, Banglish & English search queries into search.suggestion
so autocomplete immediately offers Google-quality suggestions!
"""

import os
import logging
from sqlalchemy import text
from utils.db import get_engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("seed_phrases")

popular_phrases = [
    ("amar dekha noya chin", "en", 900),
    ("amar dekha noya chin writer", "en", 850),
    ("amar dekha noya chin kar lekha", "en", 840),
    ("amar dekha noya chin book", "en", 820),
    ("আমার দেখা নয়া চীন", "bn", 900),
    ("আমার দেখা নয়া চীন কার লেখা", "bn", 850),
    ("শেখ মুজিবুর রহমান", "bn", 950),
    ("Sheikh Mujibur Rahman", "en", 950),
    ("ঢাকা আবহাওয়া আজ", "bn", 900),
    ("Dhaka weather today", "en", 900),
    ("পদ্মা সেতু আপডেট", "bn", 880),
    ("Padma Bridge updates", "en", 880),
    ("বাংলাদেশ ক্রিকেট খবর", "bn", 920),
    ("Bangladesh Cricket news", "en", 920),
    ("ঢাকা বিশ্ববিদ্যালয় ভর্তি", "bn", 870),
    ("Dhaka University admission", "en", 870),
    ("চট্টগ্রাম বন্দর সংবাদ", "bn", 860),
    ("Chattogram Port news", "en", 860),
    ("প্রথম আলো আজকের পত্রিকা", "bn", 950),
    ("Prothom Alo news today", "en", 950),
    ("ডেইলি স্টার শিরোনাম", "bn", 890),
    ("The Daily Star headlines", "en", 890),
    ("ঢাকা ট্রিব্রিউন খবর", "bn", 880),
    ("Dhaka Tribune news", "en", 880),
    ("জাতীয় সংসদ অধিবেশন", "bn", 870),
    ("Bangladesh Parliament session", "en", 870),
    ("বাংলাদেশ সরকারি সেবাসমূহ", "bn", 860),
    ("Bangladesh Govt Services", "en", 860),
    ("উইকিপিডিয়া মুক্ত বিশ্বকোষ", "bn", 850),
    ("Wikipedia Bangla", "en", 850),
    ("ফেসবুক পেজ সাপোর্ট", "bn", 840),
    ("Facebook Bangladesh", "en", 840),
    ("ইউটিউব বাংলাদেশ চ্যানেল", "bn", 830),
    ("YouTube Bangladesh", "en", 830),
    ("গুগল সার্চ ইঞ্জিন", "bn", 920),
    ("Google Search Engine", "en", 920)
]

def run():
    engine = get_engine()
    with engine.begin() as conn:
        for phrase, lang, score in popular_phrases:
            conn.execute(text("""
                INSERT INTO search.suggestion (phrase, phrase_normalised, language_code, priority, popularity_score)
                VALUES (:phrase, lower(:phrase), :lang, 100, :score)
                ON CONFLICT (phrase_normalised, language_code, entity_id) 
                DO UPDATE SET popularity_score = EXCLUDED.popularity_score
            """), {"phrase": phrase, "lang": lang, "score": score})
            
            # Also insert variant without entity_id conflict if needed
            conn.execute(text("""
                UPDATE search.suggestion SET popularity_score = :score WHERE phrase_normalised = lower(:phrase)
            """), {"phrase": phrase, "score": score})

    log.info("Successfully seeded %d popular autocomplete search phrases!", len(popular_phrases))

if __name__ == "__main__":
    run()
