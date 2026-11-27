#!/usr/bin/env python3
"""Tests for the storefront transport policy (net_policy.py).

The batch case is modelled on LCSC3D's own regression test
(``app/tests/test_resource_network.py``: *batches cross 29 items and recover each rate
limit window*): a storefront that accepts 29 requests and then answers 429 with
``Retry-After: 1`` must not lose any part of a 60-part batch.

    python tests/test_net_policy.py
"""

from __future__ import annotations

import json
import sys
import threading
import time
import unittest
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import net_policy  # noqa: E402
from net_policy import COOLDOWNS, AuthRequired, ResilientSession  # noqa: E402

JSON_BODY = json.dumps({"success": True, "result": {"lcsc": "C1"}}).encode()
LOGIN_PAGE = (
    "<!DOCTYPE html><html><head><title>嘉立创集团用户登录</title></head>"
    "<body>请登录</body></html>"
).encode()
THROTTLE_PAGE = b"<!DOCTYPE html><html><body>Slow down</body></html>"


class _Handler(BaseHTTPRequestHandler):
    responder = None  # set per test

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        status, headers, body = self.responder(self.path)
        self.send_response(status)
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:  # keep the test output clean
        pass


@contextmanager
def serve(responder):
    """Run a local storefront stand-in; yields (base_url, request_counter)."""
    hits = {"n": 0}

    def wrapped(path):
        hits["n"] += 1
        return responder(path)

    handler = type("_Bound", (_Handler,), {"responder": staticmethod(wrapped)})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}", hits
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class TransportPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        COOLDOWNS.deadlines.clear()
        COOLDOWNS.spent = 0.0
        COOLDOWNS.budget = net_policy.RESOURCE_MAX_TOTAL_WAIT
        self._backoff = net_policy.RESOURCE_RETRY_BACKOFF
        # Keep the arithmetic identical but not the wall-clock: 5s -> 5ms.
        net_policy.RESOURCE_RETRY_BACKOFF = 0.005

    def tearDown(self) -> None:
        net_policy.RESOURCE_RETRY_BACKOFF = self._backoff
        COOLDOWNS.deadlines.clear()
        COOLDOWNS.spent = 0.0
        COOLDOWNS.budget = net_policy.RESOURCE_MAX_TOTAL_WAIT

    def session(self, **kwargs) -> ResilientSession:
        return ResilientSession(timeout=5.0, min_interval=0, **kwargs)

    def test_batch_recovers_each_rate_limit_window(self):
        """29 accepted, then 429 + Retry-After: 1 — a 60-part batch must finish."""
        state = {"accepted": 0, "window": 29, "until": None, "limited": 0}

        def respond(path):
            if state["accepted"] == state["window"]:
                if state["until"] is None:
                    state["until"] = time.monotonic() + 1
                if time.monotonic() < state["until"]:
                    state["limited"] += 1
                    return 429, {"Retry-After": "1"}, b"too many requests"
                state["window"] += 29
                state["until"] = None
            state["accepted"] += 1
            return 200, {}, JSON_BODY

        with serve(respond) as (base, hits):
            session = self.session()
            for index in range(60):
                payload = session.get_json(f"{base}/component/C{index + 1}")
                self.assertTrue(payload["success"])
            self.assertEqual(state["accepted"], 60)
            self.assertGreater(state["limited"], 0, "the fixture never throttled")
            self.assertGreater(hits["n"], 60)

    def test_login_page_is_not_retried(self):
        """A sign-in wall raises immediately; retrying it only wastes the run."""
        with serve(lambda path: (200, {}, LOGIN_PAGE)) as (base, hits):
            with self.assertRaises(AuthRequired) as caught:
                self.session().get_json(f"{base}/component/C404")
            self.assertIn("sign-in", str(caught.exception))
            self.assertEqual(hits["n"], 1, "a login wall must not be retried")

    def test_throttle_page_is_retried_then_reported(self):
        """Plain HTML (no login markers) is a throttle: bounded retries, then a clear message."""
        with serve(lambda path: (200, {}, THROTTLE_PAGE)) as (base, hits):
            with self.assertRaises(net_policy.ParseError) as caught:
                self.session().get_json(f"{base}/component/C1")
            self.assertIn("refused the request", str(caught.exception))
            self.assertIn("rate limiter", str(caught.exception))
            self.assertEqual(hits["n"], net_policy.RESOURCE_REQUEST_ATTEMPTS)

    def test_long_retry_after_fails_fast(self):
        """Retry-After: 3600 must not park the run for an hour."""
        with serve(lambda path: (429, {"Retry-After": "3600"}, b"busy")) as (base, hits):
            with self.assertRaises(net_policy.RateLimitError) as caught:
                self.session().get_json(f"{base}/component/C1")
            self.assertIn("long pause", str(caught.exception))
            self.assertEqual(hits["n"], 1)

    def test_total_wait_budget_stops_a_hopeless_call(self):
        """A CLI must not sit through 5 attempts x long cooldowns: it gets a budget."""
        def respond(path):
            return 429, {"Retry-After": "30"}, b"busy"

        with serve(respond) as (base, hits):
            session = ResilientSession(timeout=5.0, min_interval=0, max_total_wait=5.0)
            with self.assertRaises(net_policy.RateLimitError) as caught:
                session.get_json(f"{base}/component/C1")
            self.assertIn("budget", str(caught.exception))
            self.assertEqual(hits["n"], 1, "the budget must stop before the first long wait")

    def test_interval_floor_only_applies_when_pacing_is_on(self):
        self.assertEqual(self.session().min_interval, 0.0)
        self.assertEqual(ResilientSession(timeout=5.0, min_interval=0.1).min_interval,
                         net_policy.MIN_INTERVAL_FLOOR)
        self.assertEqual(ResilientSession(timeout=5.0, min_interval=3).min_interval, 3.0)

    def test_response_cache_serves_a_repeat_lookup(self):
        """A second identical request must not reach the storefront again."""
        import tempfile

        from lcsc_client.cache import ResponseCache

        with tempfile.TemporaryDirectory() as folder, \
                serve(lambda path: (200, {}, JSON_BODY)) as (base, hits):
            cache = ResponseCache(folder, ttl=3600)
            session = ResilientSession(timeout=5.0, min_interval=0, cache=cache)
            url = f"{base}/component/C1"
            first = session.get_json(url, cache_ttl=3600)
            second = session.get_json(url, cache_ttl=3600)
            self.assertEqual(first, second)
            self.assertEqual(hits["n"], 1, "the cached request still hit the network")


if __name__ == "__main__":
    unittest.main(verbosity=2)
