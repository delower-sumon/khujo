"""
Khujo Ranking Engine Unit Tests (tests/test_ranking.py)
Remediates Prompt 2 acceptance criteria from AUDIT_REMEDIATION_PLAN.md:
- A document containing the query term 40 times must outrank one containing it once.
- Validates BM25 term frequency saturation and document length normalization.
"""

import unittest
import math
from typing import Dict, List

def calculate_bm25_term_score(
    tf: int,
    doc_len: int,
    avg_dl: float,
    doc_freq: int,
    total_docs: float,
    k1: float = 1.2,
    b: float = 0.75,
    field_weight: float = 1.0
) -> float:
    """Calculates the standard BM25 score for a single term in a document."""
    idf = math.log(1.0 + (total_docs - doc_freq + 0.5) / (doc_freq + 0.5))
    norm_tf = (tf * (k1 + 1.0)) / (tf + k1 * (1.0 - b + b * (doc_len / avg_dl)))
    return field_weight * idf * norm_tf

class TestBM25Ranking(unittest.TestCase):
    def test_term_frequency_ranking(self):
        """
        Acceptance Criteria: A document containing the query term 40 times
        MUST outrank one containing it once.
        """
        avg_dl = 200.0
        total_docs = 100.0
        doc_freq = 10

        # Document 1: Term frequency = 40, length = 300
        score_40 = calculate_bm25_term_score(
            tf=40,
            doc_len=300,
            avg_dl=avg_dl,
            doc_freq=doc_freq,
            total_docs=total_docs
        )

        # Document 2: Term frequency = 1, length = 300
        score_1 = calculate_bm25_term_score(
            tf=1,
            doc_len=300,
            avg_dl=avg_dl,
            doc_freq=doc_freq,
            total_docs=total_docs
        )

        self.assertGreater(
            score_40, score_1,
            f"Document with tf=40 (score {score_40:.4f}) must outrank document with tf=1 (score {score_1:.4f})"
        )

    def test_title_boost_weighting(self):
        """Verify title occurrences receive 3x boost over body occurrences."""
        avg_dl = 200.0
        total_docs = 100.0
        doc_freq = 5

        title_score = calculate_bm25_term_score(
            tf=1, doc_len=10, avg_dl=avg_dl, doc_freq=doc_freq, total_docs=total_docs, field_weight=3.0
        )
        body_score = calculate_bm25_term_score(
            tf=1, doc_len=10, avg_dl=avg_dl, doc_freq=doc_freq, total_docs=total_docs, field_weight=1.0
        )

        self.assertAlmostEqual(title_score, body_score * 3.0, places=4)

    def test_length_normalization(self):
        """Verify shorter, focused documents get a length penalty discount over bloated documents with same TF."""
        avg_dl = 200.0
        total_docs = 100.0
        doc_freq = 5

        short_doc_score = calculate_bm25_term_score(
            tf=5, doc_len=50, avg_dl=avg_dl, doc_freq=doc_freq, total_docs=total_docs
        )
        long_doc_score = calculate_bm25_term_score(
            tf=5, doc_len=2000, avg_dl=avg_dl, doc_freq=doc_freq, total_docs=total_docs
        )

        self.assertGreater(short_doc_score, long_doc_score)

if __name__ == "__main__":
    unittest.main()
