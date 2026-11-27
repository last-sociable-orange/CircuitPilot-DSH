"""Test support: import path and a writable temporary folder.

``pytest``'s ``tmp_path`` creates directories with 0700 ACLs that this sandbox cannot
delete, so scratch folders live under the skill's own ``.tmp`` tree instead.
"""

from __future__ import annotations

import itertools
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

TMP_ROOT = Path(__file__).resolve().parent.parent / ".tmp" / "tests"
_counter = itertools.count(1)


@pytest.fixture
def workdir() -> Path:
    """A fresh, deletable scratch directory."""
    path = TMP_ROOT / f"case-{next(_counter)}"
    path.mkdir(parents=True, exist_ok=True)
    return path
