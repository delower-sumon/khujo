# -*- coding: utf-8 -*-
import unittest
from backend.app.nlp.bangla_stemmer import strip_bangla_suffix, expand_bangla_stems, clean_bangla_text

class TestBanglaStemmer(unittest.TestCase):
    def test_locative_inflections(self):
        """Verify locative suffix stripping (-য়, -তে, -য়ে)."""
        self.assertEqual(strip_bangla_suffix("ঢাকায়"), "ঢাকা")
        self.assertEqual(strip_bangla_suffix("সিলেটে"), "সিলেট")
        self.assertEqual(strip_bangla_suffix("খুলনায়"), "খুলনা")

    def test_possessive_inflections(self):
        """Verify possessive suffix stripping (-র, -এর, -দের)."""
        self.assertEqual(strip_bangla_suffix("ঢাকার"), "ঢাকা")
        self.assertEqual(strip_bangla_suffix("মানুষের"), "মানুষ")
        self.assertEqual(strip_bangla_suffix("ছাত্রদের"), "ছাত্র")

    def test_plural_and_definite_markers(self):
        """Verify plural and definite markers (-গুলো, -গুলি, -টি, -টা)."""
        self.assertEqual(strip_bangla_suffix("বইগুলো"), "বই")
        self.assertEqual(strip_bangla_suffix("দেশটি"), "দেশ")
        self.assertEqual(strip_bangla_suffix("জিনিসটা"), "জিনিস")

    def test_protected_roots(self):
        """Verify words in protected dictionary are not truncated."""
        self.assertEqual(strip_bangla_suffix("ঢাকা"), "ঢাকা")
        self.assertEqual(strip_bangla_suffix("খবর"), "খবর")
        self.assertEqual(strip_bangla_suffix("সুন্দর"), "সুন্দর")
        self.assertEqual(strip_bangla_suffix("সময়"), "সময়")
        self.assertEqual(strip_bangla_suffix("বিশ্ববিদ্যালয়"), "বিশ্ববিদ্যালয়")

    def test_expand_bangla_stems(self):
        """Verify query expansion creates both surface and root forms."""
        expanded = expand_bangla_stems("ঢাকায় বিশ্ববিদ্যালয়")
        self.assertIn("ঢাকায়", expanded)
        self.assertIn("ঢাকা", expanded)
        self.assertIn("বিশ্ববিদ্যালয়", expanded)
        self.assertIn("ঢাকা বিশ্ববিদ্যালয়", expanded)

    def test_audit_remediation_inflections(self):
        """
        Target inflection cases specified in prompt 1 item 4:
        ঘরের → ঘর (not ঘ), রংপুরের → রংপুর, জামালপুরে → জামালপুর,
        কিশোরগঞ্জের → কিশোরগঞ্জ, সাগরে → সাগর, বরিশালের → বরিশাল.
        """
        self.assertEqual(strip_bangla_suffix("ঘরের"), "ঘর")
        self.assertEqual(strip_bangla_suffix("ঘর"), "ঘর")  # Never reduced to ঘ
        self.assertEqual(strip_bangla_suffix("রংপুরের"), "রংপুর")
        self.assertEqual(strip_bangla_suffix("জামালপুরে"), "জামালপুর")
        self.assertEqual(strip_bangla_suffix("কিশোরগঞ্জের"), "কিশোরগঞ্জ")
        self.assertEqual(strip_bangla_suffix("সাগরে"), "সাগর")
        self.assertEqual(strip_bangla_suffix("বরিশালের"), "বরিশাল")

if __name__ == "__main__":
    unittest.main()

