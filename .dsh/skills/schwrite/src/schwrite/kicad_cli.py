"""Finding and running `kicad-cli`.

Both `verify` and `erc` need KiCad's own tool: the point of the gate is that an independent
program reading our file agrees with us. The path is discovered rather than assumed, and can
be overridden with `SCHWRITE_KICAD_CLI` for a machine with a different install.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

#: Environment variable that overrides discovery.
ENV_VAR = "SCHWRITE_KICAD_CLI"

#: Where KiCad installs it on Windows, newest first.
_WINDOWS_CANDIDATES = (
    r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe",
    r"C:\Program Files\KiCad\9.0\bin\kicad-cli.exe",
    r"C:\Program Files\KiCad\8.0\bin\kicad-cli.exe",
)


class ToolError(RuntimeError):
    """`kicad-cli` is missing or refused to run."""


def find() -> str:
    """Path to `kicad-cli`, or raise `ToolError` saying how to point at it."""
    override = os.environ.get(ENV_VAR)
    if override:
        if not Path(override).is_file():
            raise ToolError(f"{ENV_VAR} points at {override}, which is not a file")
        return override
    found = shutil.which("kicad-cli")
    if found:
        return found
    for candidate in _WINDOWS_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    raise ToolError(
        "kicad-cli not found: install KiCad, or set "
        f"{ENV_VAR} to the kicad-cli executable"
    )


def run(*args: str, timeout: int = 300) -> subprocess.CompletedProcess:
    """Run `kicad-cli <args>` and return the completed process."""
    return subprocess.run(
        [find(), *args], capture_output=True, text=True, timeout=timeout
    )
