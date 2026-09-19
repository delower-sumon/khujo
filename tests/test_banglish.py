import unittest
from backend.app.nlp.banglish import transliterate_banglish, expand_query_with_banglish, is_mostly_latin

class TestBanglishTransliteration(unittest.TestCase):
    def test_is_mostly_latin(self):
        self.assertTrue(is_mostly_latin("ami banglay gaan gai"))
        self.assertTrue(is_mostly_latin("dhaka shohor"))
        self.assertFalse(is_mostly_latin("আমি বাংলায় গান গাই"))
        self.assertFalse(is_mostly_latin(""))

    def test_ami_banglay_gaan_gai(self):
        primary, variants = transliterate_banglish("ami banglay gaan gai")
        self.assertIsNotNone(primary)
        self.assertEqual(primary, "আমি বাংলায় গান গাই")
        self.assertIn("আমি বাংলায় গান গাই", variants)

    def test_dhaka_shohor(self):
        primary, variants = transliterate_banglish("dhaka shohor")
        self.assertEqual(primary, "ঢাকা শহর")

    def test_query_expansion_keeps_both(self):
        expanded = expand_query_with_banglish("ami banglay gaan gai", ["ami banglay gaan gai"])
        self.assertIn("ami banglay gaan gai", expanded)
        self.assertIn("আমি বাংলায় গান গাই", expanded)

    def test_pure_bengali_untouched(self):
        primary, variants = transliterate_banglish("কিশোরগঞ্জ")
        self.assertIsNone(primary)
        self.assertEqual(variants, [])

if __name__ == "__main__":
    unittest.main()
