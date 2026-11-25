"""Regression checks for retrieval gaps found by the before-fix eval run."""

import unittest

from utils.mock_llm import retrieve_context


class KnowledgeBaseCoverageTests(unittest.TestCase):
    def test_jwt_question_covers_token_expiry_and_signature(self):
        answer = " ".join(retrieve_context("JWT khác gì API key trong xác thực?")).lower()
        for term in ("token", "hết hạn", "chữ ký"):
            with self.subTest(term=term):
                self.assertIn(term, answer)

    def test_hpa_question_covers_cpu_memory_and_custom_metrics(self):
        answer = " ".join(retrieve_context("Kubernetes HPA scale dựa trên những chỉ số nào?")).lower()
        for term in ("cpu", "memory", "custom metrics"):
            with self.subTest(term=term):
                self.assertIn(term, answer)


if __name__ == "__main__":
    unittest.main()
