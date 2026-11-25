import importlib
import os
import sys
import types
import unittest
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from pathlib import Path
from unittest.mock import patch


class ConfigRedisTests(unittest.TestCase):
    def test_settings_load_environment_values(self):
        with patch.dict(
            os.environ,
            {
                "PORT": "9123",
                "ENVIRONMENT": "staging",
                "AGENT_API_KEY": "test-key",
                "REDIS_URL": "redis://cache:6379/1",
                "RATE_LIMIT_PER_MINUTE": "7",
                "DAILY_BUDGET_USD": "2.5",
            },
        ):
            sys.modules.pop("app.config", None)
            config = importlib.import_module("app.config")
            self.assertEqual(config.settings.port, 9123)
            self.assertEqual(config.settings.environment, "staging")
            self.assertEqual(config.settings.agent_api_key, "test-key")
            self.assertEqual(config.settings.redis_url, "redis://cache:6379/1")
            self.assertEqual(config.settings.rate_limit_per_minute, 7)
            self.assertEqual(config.settings.daily_budget_usd, 2.5)

    def test_max_output_tokens_uses_environment_and_default(self):
        with patch.dict(os.environ, {"MAX_OUTPUT_TOKENS": "64"}):
            sys.modules.pop("app.config", None)
            configured = importlib.import_module("app.config")
            self.assertEqual(configured.settings.max_output_tokens, 64)
        with patch.dict(os.environ, {}, clear=True):
            sys.modules.pop("app.config", None)
            defaulted = importlib.import_module("app.config")
            self.assertEqual(defaulted.settings.max_output_tokens, 1024)

    def test_budget_reservations_are_atomic_and_terminal_operations_idempotent(self):
        fake_redis = _FakeReservationRedis()
        with patch.dict(os.environ, {
            "REDIS_URL": "redis://test/0",
            "DAILY_BUDGET_USD": "0.001",
            "MAX_OUTPUT_TOKENS": "1024",
        }):
            fake_module = types.SimpleNamespace(from_url=lambda *_args, **_kwargs: fake_redis)
            with patch.dict(sys.modules, {"redis": fake_module}):
                for module in ("app.config", "app.redis_client", "app.cost_guard"):
                    sys.modules.pop(module, None)
                guard = importlib.import_module("app.cost_guard")
                def reserve():
                    try:
                        return guard.reserve_budget(1)
                    except Exception as exc:
                        return exc
                with ThreadPoolExecutor(max_workers=2) as pool:
                    outcomes = list(pool.map(lambda _: reserve(), range(2)))
                ids = [item for item in outcomes if isinstance(item, str)]
                failures = [item for item in outcomes if not isinstance(item, str)]
                self.assertEqual(len(ids), 1)
                self.assertEqual(len(failures), 1)
                self.assertEqual(failures[0].status_code, 402)
                reservation_id = ids[0]
                actual = guard.settle_budget(reservation_id, 1, 10)
                total_after_settle = float(fake_redis.values[guard._daily_key()])
                self.assertGreater(actual, 0)
                self.assertAlmostEqual(total_after_settle, actual)
                guard.settle_budget(reservation_id, 1, 10)
                self.assertAlmostEqual(float(fake_redis.values[guard._daily_key()]), actual)
                self.assertEqual(guard.release_budget(reservation_id), None)

    def test_budget_reservation_rejects_output_over_limit_and_releases(self):
        fake_redis = _FakeReservationRedis()
        with patch.dict(os.environ, {
            "REDIS_URL": "redis://test/0",
            "DAILY_BUDGET_USD": "1.0",
            "MAX_OUTPUT_TOKENS": "8",
        }):
            fake_module = types.SimpleNamespace(from_url=lambda *_args, **_kwargs: fake_redis)
            with patch.dict(sys.modules, {"redis": fake_module}):
                for module in ("app.config", "app.redis_client", "app.cost_guard"):
                    sys.modules.pop(module, None)
                guard = importlib.import_module("app.cost_guard")
                reservation_id = guard.reserve_budget(1)
                with self.assertRaises(Exception) as over_limit:
                    guard.settle_budget(reservation_id, 1, 9)
                self.assertEqual(over_limit.exception.status_code, 402)
                guard.release_budget(reservation_id)
                self.assertAlmostEqual(float(fake_redis.values[guard._daily_key()]), 0.0)

    def test_redis_errors_return_503_and_rate_keys_hash_api_key(self):
        class BrokenRedis:
            def eval(self, *_args):
                raise ConnectionError("redis offline")
            def get(self, *_args):
                raise ConnectionError("redis offline")
        broken = BrokenRedis()
        with patch.dict(os.environ, {"REDIS_URL": "redis://test/0", "AGENT_API_KEY": "raw-api-secret"}):
            fake_module = types.SimpleNamespace(from_url=lambda *_args, **_kwargs: broken)
            with patch.dict(sys.modules, {"redis": fake_module}):
                for module in ("app.config", "app.redis_client", "app.rate_limiter", "app.cost_guard"):
                    sys.modules.pop(module, None)
                limiter = importlib.import_module("app.rate_limiter")
                guard = importlib.import_module("app.cost_guard")
                with self.assertRaises(Exception) as rate_failure:
                    limiter.check_rate_limit("raw-api-secret")
                self.assertEqual(rate_failure.exception.status_code, 503)
                with self.assertRaises(Exception) as reserve_failure:
                    guard.reserve_budget(1)
                self.assertEqual(reserve_failure.exception.status_code, 503)
                with self.assertRaises(Exception) as settle_failure:
                    guard.settle_budget("reservation-x", 1, 1)
                self.assertEqual(settle_failure.exception.status_code, 503)
                with self.assertRaises(Exception) as release_failure:
                    guard.release_budget("reservation-x")
                self.assertEqual(release_failure.exception.status_code, 503)
        captured = {}
        class KeyRedis:
            def eval(self, _script, _count, key, *_args):
                captured["key"] = key
                return 1
        with patch.object(limiter, "r", KeyRedis()):
            limiter.check_rate_limit("raw-api-secret")
        self.assertEqual(captured["key"], "rate:" + __import__("hashlib").sha256(b"raw-api-secret").hexdigest())
        self.assertNotIn("raw-api-secret", captured["key"])

    def test_redis_client_is_constructed_when_url_is_configured(self):
        calls = []
        fake_module = types.SimpleNamespace(
            from_url=lambda url, **kwargs: (calls.append((url, kwargs)) or _FakeRedis())
        )
        with patch.dict(os.environ, {"REDIS_URL": "redis://cache:6379/0"}):
            with patch.dict(sys.modules, {"redis": fake_module}):
                for module in ("app.config", "app.redis_client"):
                    sys.modules.pop(module, None)
                redis_client = importlib.import_module("app.redis_client")
                self.assertIsNotNone(redis_client.r)
                self.assertEqual(calls, [("redis://cache:6379/0", {"decode_responses": True})])

    def test_part6_container_configuration_contract(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        dockerfile = (root / "Dockerfile").read_text()
        compose = (root / "docker-compose.yml").read_text()
        ignore = (root / ".dockerignore").read_text()
        env_example = (root / ".env.example").read_text()
        railway = (root / "railway.toml").read_text()
        self.assertGreaterEqual(dockerfile.count("FROM "), 2)
        self.assertIn("USER ", dockerfile)
        self.assertIn("HEALTHCHECK", dockerfile)
        self.assertIn("PORT", dockerfile)
        self.assertIn("redis:", compose)
        for entry in (".env", "__pycache__", "venv"):
            self.assertIn(entry, ignore)
        for key in ("PORT", "ENVIRONMENT", "AGENT_API_KEY", "REDIS_URL", "RATE_LIMIT_PER_MINUTE", "DAILY_BUDGET_USD"):
            self.assertIn(key, env_example)
        self.assertIn("builder = \"DOCKERFILE\"", railway)
        self.assertIn('healthcheckPath = "/health"', railway)

    def test_container_image_starts_and_stops_gracefully(self):
        import json
        import socket
        import subprocess
        import time
        from urllib.request import urlopen

        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            port = probe.getsockname()[1]
        root = Path(__file__).resolve().parents[1]
        container = f"day14-contract-{os.getpid()}"
        image = f"day14-contract-image:{os.getpid()}"
        try:
            subprocess.run(
                ["docker", "build", "-t", image, str(root)],
                check=True,
                capture_output=True,
                text=True,
            )
        except subprocess.CalledProcessError as exc:
            if "429 Too Many Requests" in (exc.stderr or ""):
                self.skipTest("Docker Hub rate-limited the base-image metadata request (HTTP 429)")
            raise
        subprocess.run(
            ["docker", "run", "-d", "--name", container, "-p", f"127.0.0.1:{port}:8000", "-e", "PORT=8000", "-e", "AGENT_API_KEY=test", image],
            check=True,
            capture_output=True,
            text=True,
        )
        try:
            deadline = time.time() + 30
            while time.time() < deadline:
                try:
                    with urlopen(f"http://127.0.0.1:{port}/health", timeout=1) as response:
                        if response.status == 200:
                            break
                except Exception:
                    time.sleep(0.25)
            else:
                self.fail("container did not become healthy")
            inspect = subprocess.run(
                ["docker", "inspect", "--format", "{{.Config.User}} {{.Config.Healthcheck.Test}}", container],
                check=True,
                capture_output=True,
                text=True,
            ).stdout
            self.assertIn("appuser", inspect)
            stopped = subprocess.run(
                ["docker", "stop", "-t", "9", container], check=True, capture_output=True, text=True
            )
            self.assertTrue(stopped.stdout.strip())
            state = json.loads(
                subprocess.run(
                    ["docker", "inspect", "--format", "{{json .State}}", container],
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout
            )
            self.assertEqual(state["ExitCode"], 0)
        finally:
            subprocess.run(["docker", "rm", "-f", container], capture_output=True)
            subprocess.run(["docker", "rmi", "-f", image], capture_output=True)

    def test_redis_client_is_created_without_ping_and_health_handles_failure(self):
        calls = []

        class FakeRedis:
            def ping(self):
                calls.append("ping")
                raise ConnectionError("offline")

        fake_module = types.SimpleNamespace(
            from_url=lambda url, **kwargs: (calls.append((url, kwargs)) or FakeRedis())
        )
        with patch.dict(os.environ, {"REDIS_URL": "redis://cache:6379/0"}):
            with patch.dict(sys.modules, {"redis": fake_module}):
                sys.modules.pop("app.config", None)
                sys.modules.pop("app.redis_client", None)
                redis_client = importlib.import_module("app.redis_client")
                self.assertIsNotNone(redis_client.r)
                self.assertEqual(calls, [("redis://cache:6379/0", {"decode_responses": True})])
                self.assertFalse(redis_client.redis_healthy())
                self.assertEqual(calls[-1], "ping")

    def test_auth_rate_limit_and_budget_contracts(self):
        fake_redis = _FakeRedis()
        with patch.dict(
            os.environ,
            {
                "AGENT_API_KEY": "secret",
                "RATE_LIMIT_PER_MINUTE": "1",
                "DAILY_BUDGET_USD": "0.000001",
                "MAX_OUTPUT_TOKENS": "1",
                "REDIS_URL": "redis://test/0",
            },
        ):
            fake_module = types.SimpleNamespace(from_url=lambda *_args, **_kwargs: fake_redis)
            with patch.dict(sys.modules, {"redis": fake_module}):
                for module in ("app.config", "app.redis_client", "app.auth", "app.rate_limiter", "app.cost_guard"):
                    sys.modules.pop(module, None)
                config = importlib.import_module("app.config")
                auth = importlib.import_module("app.auth")
                rate_limiter = importlib.import_module("app.rate_limiter")
                cost_guard = importlib.import_module("app.cost_guard")

                auth.verify_api_key(api_key="secret")
                with self.assertRaises(Exception) as missing:
                    auth.verify_api_key(api_key=None)
                self.assertEqual(missing.exception.status_code, 401)
                with self.assertRaises(Exception) as incorrect:
                    auth.verify_api_key(api_key="wrong")
                self.assertEqual(incorrect.exception.status_code, 401)

                rate_limiter.check_rate_limit("secret")
                with self.assertRaises(Exception) as limited:
                    rate_limiter.check_rate_limit("secret")
                self.assertEqual(limited.exception.status_code, 429)
                self.assertIn("Retry-After", limited.exception.headers)

                reservation = cost_guard.reserve_budget(1)
                cost = cost_guard.settle_budget(reservation, 1, 1)
                self.assertGreater(cost, 0)
                with self.assertRaises(Exception) as exhausted:
                    cost_guard.reserve_budget(1)
                self.assertEqual(exhausted.exception.status_code, 402)
                self.assertEqual(config.settings.agent_api_key, "secret")


class _FakeRedis:
    def __init__(self):
        self.values = {}
        self.sorted_sets = {}

    def eval(self, script, numkeys, *args):
        if "ZREMRANGEBYSCORE" in script:
            key, now, cutoff, member, limit, ttl = args
            members = self.sorted_sets.setdefault(key, {})
            self.sorted_sets[key] = {m: score for m, score in members.items() if score > float(cutoff)}
            members = self.sorted_sets[key]
            if len(members) >= int(limit):
                return 0
            members[member] = float(now)
            return 1
        if "RESERVE_BUDGET" in script:
            day_key, reservation_key, reserve, budget, _ttl = args
            if reservation_key in self.reservations or float(self.values.get(day_key, 0)) + float(reserve) > float(budget):
                return 0
            self.values[day_key] = float(self.values.get(day_key, 0)) + float(reserve)
            self.reservations[reservation_key] = {"day_key": day_key, "reserved": float(reserve), "state": "reserved"}
            return 1
        if "SETTLE_BUDGET" in script:
            reservation_key, actual, _ttl = args
            reservation = self.reservations.get(reservation_key)
            if reservation is None:
                return -1
            if reservation["state"] != "reserved":
                return 2
            if float(actual) > reservation["reserved"]:
                return 0
            self.values[reservation["day_key"]] += float(actual) - reservation["reserved"]
            reservation["state"] = "settled"
            return 1
        if "RELEASE_BUDGET" in script:
            reservation_key, _ttl = args
            reservation = self.reservations.get(reservation_key)
            if reservation and reservation["state"] == "reserved":
                self.values[reservation["day_key"]] -= reservation["reserved"]
                reservation["state"] = "released"
            return 1
        key, limit, cost, ttl = args
        current = float(self.values.get(key, 0))
        if current + float(cost) > float(limit):
            return 0
        self.values[key] = current + float(cost)
        return 1

    def get(self, key):
        return self.values.get(key)

    def incrbyfloat(self, key, amount):
        self.values[key] = float(self.values.get(key, 0)) + float(amount)
        return self.values[key]

    def expire(self, *_args):
        return True

    def ping(self):
        return True

    def __init__(self):
        self.values = {}
        self.sorted_sets = {}
        self.reservations = {}


class _FakeReservationRedis:
    """Thread-safe fake for the reservation Lua contract tests."""

    def __init__(self):
        self.values = {}
        self.reservations = {}
        self.lock = Lock()

    def eval(self, script, _numkeys, *args):
        with self.lock:
            if "RESERVE_BUDGET" in script:
                day_key, reservation_key, reserve, budget, ttl = args
                if reservation_key in self.reservations or float(self.values.get(day_key, 0)) + float(reserve) > float(budget):
                    return 0
                self.values[day_key] = float(self.values.get(day_key, 0)) + float(reserve)
                self.reservations[reservation_key] = {"day_key": day_key, "reserved": float(reserve), "state": "reserved"}
                return 1
            if "SETTLE_BUDGET" in script:
                reservation_key, actual, ttl = args
                reservation = self.reservations.get(reservation_key)
                if reservation is None:
                    return -1
                if reservation["state"] != "reserved":
                    return 1
                if float(actual) > reservation["reserved"]:
                    return 0
                day_key = reservation["day_key"]
                self.values[day_key] = float(self.values[day_key]) - reservation["reserved"] + float(actual)
                reservation["state"] = "settled"
                return 1
            reservation_key, ttl = args
            reservation = self.reservations.get(reservation_key)
            if reservation is not None and reservation["state"] == "reserved":
                self.values[reservation["day_key"]] -= reservation["reserved"]
                reservation["state"] = "released"
            return 1


if __name__ == "__main__":
    unittest.main()
