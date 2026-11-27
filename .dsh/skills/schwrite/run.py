#!/usr/bin/env python
"""Standalone schwrite launcher — no installation, no third-party packages.

    python run.py build  --netlist Document/Netlist/Sync.json --out Design/Sync.kicad_sch
    python run.py verify --page Design/Sync.kicad_sch --netlist Document/Netlist/Sync.json
    python run.py erc    --page Design/Sync.kicad_sch

Everything it needs is in this folder: the package under `src/` and one vendored
S-expression reader. Any Python 3.10+ works.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "src"))

# Netlist JSON and KiCad paths are UTF-8; the Windows console defaults to the OEM code page.
for stream in (sys.stdout, sys.stderr):
    try:
        stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

from schwrite.cli import main  # noqa: E402  (path set above)

if __name__ == "__main__":
    raise SystemExit(main())
