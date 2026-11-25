import importlib
import json
import logging
import os
import sys
import unittest
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient


class ApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = patch.dict(os.environ, {"AGENT_API_KEY": "test-secret", "REDIS_URL": ""})
        cls.env.start()
        for name in ("app.config", "app.redis_client", "app.auth", "app.main"):
            sys.modules.pop(name, None)
        cls.main = importlib.import_module("app.main")
        cls.client = TestClient(cls.main.app)

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        cls.env.stop()

    def test_health_is_live_and_ready_reflects_redis(self):
        with patch("app.main.redis_healthy", return_value=False):
            self.assertEqual(self.client.get("/health").status_code, 200)
            self.assertEqual(self.client.get("/ready").status_code, 503)
        with patch("app.main.redis_healthy", return_value=True):
            self.assertEqual(self.client.get("/ready").status_code, 200)

    def test_ask_requires_key_and_returns_answer(self):
        body = {"question": "What is deployment?"}
        self.assertEqual(self.client.post("/ask", json=body).status_code, 401)
        with patch("app.main.check_rate_limit"), patch("app.main.reserve_budget", return_value="r1"), patch(
            "app.main.settle_budget", return_value=0.00001
        ):
            response = self.client.post("/ask", json=body, headers={"X-API-Key": "test-secret"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["question"], body["question"])
        self.assertTrue(response.json()["answer"])

    def test_ask_propagates_rate_and_budget_responses(self):
        body = {"question": "Hello"}
        headers = {"X-API-Key": "test-secret"}
        with patch("app.main.check_rate_limit", side_effect=HTTPException(429, headers={"Retry-After": "60"})):
            limited = self.client.post("/ask", json=body, headers=headers)
        self.assertEqual(limited.status_code, 429)
        self.assertEqual(limited.headers["retry-after"], "60")
        with patch("app.main.check_rate_limit"), patch(
            "app.main.reserve_budget", side_effect=HTTPException(402)
        ):
            exhausted = self.client.post("/ask", json=body, headers=headers)
        self.assertEqual(exhausted.status_code, 402)

    def test_ask_reserves_before_model_and_settles_afterward(self):
        calls = []
        def reserve(input_tokens):
            calls.append(("reserve", input_tokens))
            return "reservation-1"
        def model(question):
            calls.append(("model", question))
            return "answer"
        def settle(reservation_id, input_tokens, output_tokens):
            calls.append(("settle", reservation_id, input_tokens, output_tokens))
        with patch("app.main.check_rate_limit"), patch("app.main.reserve_budget", side_effect=reserve), patch(
            "app.main.llm_ask", side_effect=model
        ), patch("app.main.settle_budget", side_effect=settle):
            response = self.client.post("/ask", json={"question": "abcd"}, headers={"X-API-Key": "test-secret"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual([call[0] for call in calls], ["reserve", "model", "settle"])

    def test_ask_does_not_call_model_if_reservation_is_denied(self):
        with patch("app.main.check_rate_limit"), patch("app.main.reserve_budget", side_effect=HTTPException(402)), patch(
            "app.main.llm_ask"
        ) as model:
            response = self.client.post("/ask", json={"question": "hello"}, headers={"X-API-Key": "test-secret"})
        self.assertEqual(response.status_code, 402)
        model.assert_not_called()

    def test_ask_releases_reservation_on_model_failure(self):
        with patch("app.main.check_rate_limit"), patch("app.main.reserve_budget", return_value="reservation-2"), patch(
            "app.main.llm_ask", side_effect=RuntimeError("model failed")
        ), patch("app.main.release_budget") as release:
            response = TestClient(self.main.app, raise_server_exceptions=False).post(
                "/ask", json={"question": "hello"}, headers={"X-API-Key": "test-secret"}
            )
        self.assertEqual(response.status_code, 500)
        release.assert_called_once_with("reservation-2")

    def test_ask_releases_reservation_when_output_exceeds_cap(self):
        with patch("app.main.check_rate_limit"), patch("app.main.reserve_budget", return_value="reservation-3"), patch(
            "app.main.llm_ask", return_value="x" * 5000
        ), patch("app.main.release_budget") as release:
            response = self.client.post("/ask", json={"question": "hello"}, headers={"X-API-Key": "test-secret"})
        self.assertEqual(response.status_code, 402)
        release.assert_called_once_with("reservation-3")

    def test_application_request_log_is_json(self):
        records = []

        class Capture(logging.Handler):
            def emit(self, record):
                records.append(self.format(record))

        handler = Capture()
        handler.setFormatter(self.main._JsonFormatter())
        self.main.logger.addHandler(handler)
        try:
            with patch("app.main.check_rate_limit"), patch("app.main.reserve_budget", return_value="r4"), patch(
                "app.main.settle_budget", return_value=0.0
            ):
                self.client.post("/ask", json={"question": "Hi"}, headers={"X-API-Key": "test-secret"})
        finally:
            self.main.logger.removeHandler(handler)
        payload = json.loads(records[-1])
        self.assertEqual(payload["event"], "request")
        self.assertEqual(payload["path"], "/ask")
        self.assertIsInstance(payload["status"], int)
        self.assertIsInstance(payload["ms"], (int, float))
        self.assertFalse(payload["event"].startswith("{"))

    def test_lifespan_is_configured_for_graceful_shutdown(self):
        self.assertIsNotNone(self.main.app.router.lifespan_context)


if __name__ == "__main__":
    unittest.main()
