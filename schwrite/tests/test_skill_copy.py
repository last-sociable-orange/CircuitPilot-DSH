"""The frozen skill copy must be the package it claims to be.

`.dsh/skills/schwrite/` carries the code so the folder can be copied anywhere. That copy rots
silently unless something compares it with the source; this does, and says how to fix it.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
#: Two layouts ship this package: a project's `.dsh/skills/`, a bundle's `dsh/skills/`.
_CANDIDATES = (
    REPO.parent / ".dsh" / "skills" / "schwrite",
    REPO.parent / "dsh" / "skills" / "schwrite",
)
SKILL = next((candidate for candidate in _CANDIDATES if candidate.is_dir()), _CANDIDATES[0])


pytestmark = pytest.mark.skipif(
    not (SKILL / "MANIFEST.json").is_file(), reason="the skill copy is not present"
)


def test_the_copy_is_current() -> None:
    result = subprocess.run(
        [sys.executable, str(REPO / "tools" / "sync_skill.py"), "--check"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_the_copy_carries_a_manifest() -> None:
    manifest = json.loads((SKILL / "MANIFEST.json").read_text(encoding="utf-8"))
    assert manifest["package"] == "schwrite"
    assert manifest["files"], "manifest lists no files"
    for relative in manifest["files"]:
        assert (SKILL / "src" / "schwrite" / relative).is_file(), relative


def test_the_launcher_runs_without_the_environment() -> None:
    """No PYTHONPATH, no installed package: the folder on its own answers --help."""
    result = subprocess.run(
        [sys.executable, "-S", str(SKILL / "run.py"), "--help"],
        capture_output=True, text=True, cwd=SKILL,
    )
    assert result.returncode == 0, result.stderr
    assert "build" in result.stdout and "verify" in result.stdout and "erc" in result.stdout
