#!/usr/bin/env python3
"""Tests for the batch policy in ``kicad_db``: prefetch once, stop on a refusal.

    python tests/test_batch_policy.py
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS))

from dbcore import runner  # noqa: E402
from dbcore.lcsc import LookupProblem, StorefrontRefused, is_refusal  # noqa: E402


class _CountingLookup:
    """Records how many child calls the prefetch makes, and with which identifiers."""

    def __init__(self, failure: Exception | None = None) -> None:
        self.calls: list[list[str]] = []
        self.failure = failure

    def get(self, identifier: str):
        return None

    def fetch(self, identifiers: list[str]):
        self.calls.append(list(identifiers))
        if self.failure is not None:
            raise self.failure
        return {}


class BatchPolicyTests(unittest.TestCase):
    def test_prefetch_asks_once_for_the_whole_batch(self):
        """One call for N identifiers, not N calls — the storefront counts requests."""
        lookup = _CountingLookup(LookupProblem("no data for: C3"))
        runner._prefetch(lookup, ["C1", "C2", "C3", "C1"])
        self.assertEqual(lookup.calls, [["C1", "C2", "C3"]])

    def test_prefetch_does_nothing_when_everything_is_cached(self):
        class Cached(_CountingLookup):
            def get(self, identifier):
                return object()

        lookup = Cached()
        runner._prefetch(lookup, ["C1", "C2"])
        self.assertEqual(lookup.calls, [])

    def test_a_refusal_stops_the_batch_and_is_not_swallowed(self):
        lookup = _CountingLookup(StorefrontRefused("the storefront refused the batch"))
        with self.assertRaises(StorefrontRefused):
            runner._prefetch(lookup, ["C1", "C2", "C3"])
        self.assertEqual(len(lookup.calls), 1, "must not retry per identifier")

    def test_a_missing_part_does_not_stop_the_batch(self):
        """A single unknown part stays a per-line error; only a refusal stops the run."""
        lookup = _CountingLookup(LookupProblem("no data for: C2"))
        runner._prefetch(lookup, ["C1", "C2"])   # must not raise
        self.assertEqual(len(lookup.calls), 1)

    def test_refusal_classification(self):
        self.assertTrue(is_refusal(
            "lcsc_client.errors.ParseError: LCSC refused the request: the storefront "
            "answered with an HTML page instead of JSON"))
        self.assertTrue(is_refusal("... answered with a sign-in page, so no data came back"))
        self.assertTrue(is_refusal("The storefront asked for a long pause (3600s)"))
        self.assertTrue(is_refusal("LCSC is rate limiting requests (HTTP 429)"))
        self.assertFalse(is_refusal("lcsc-parts failed (1): No part C999999 on lcsc.com."))
        self.assertFalse(is_refusal("lcsc-parts returned non-JSON output: Expecting value"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
