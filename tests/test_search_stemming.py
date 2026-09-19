import unittest
from backend.app.nlp.bangla_stemmer import strip_bangla_suffix, expand_bangla_stems, clean_bangla_text

class TestSearchStemming(unittest.TestCase):
    def test_single_token_inflections(self):
        """Test suffix stripping on typical inflected Bangla queries."""
        cases = {
            "ঢাকায়": "ঢাকা",
            "ঢাকার": "ঢাকা",
            "সিলেটে": "সিলেট",
            "সিলেটের": "সিলেট",
            "চট্টগ্রামের": "চট্টগ্রাম",
            "রাজশাহীতে": "রাজশাহী",
            "মানুষের": "মানুষ",
            "বইগুলো": "বই",
            "দেশটিকে": "দেশ",
        }
        for inflected, expected_root in cases.items():
            with self.subTest(inflected=inflected):
                self.assertEqual(strip_bangla_suffix(inflected), expected_root)

    def test_multi_word_query_expansion(self):
        """Test query expansion with inflected multi-word queries."""
        query = "ঢাকায় ভালো খাবার"
        expanded = expand_bangla_stems(query)
        self.assertIn("ঢাকা", expanded)
        self.assertIn("ঢাকায়", expanded)
        self.assertIn("খাবার", expanded)
        self.assertIn("ঢাকা ভালো খাবার", expanded)

    def test_protected_roots_not_mutilated(self):
        """Ensure roots ending in common suffix characters are preserved."""
        protected = ["শহর", "খবর", "উত্তর", "সময়", "বিষয়", "পাহাড়", "পানি", "মাটি"]
        for word in protected:
            with self.subTest(word=word):
                self.assertEqual(strip_bangla_suffix(word), word)

    def test_clean_bangla_text(self):
        """Verify ZWNJ/ZWJ and noise stripping."""
        dirty = "ঢাকা\u200cর  "
        self.assertEqual(clean_bangla_text(dirty), "ঢাকার")

if __name__ == "__main__":
    unittest.main()
