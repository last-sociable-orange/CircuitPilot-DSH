"""Shared fixtures: the reference corpus, the netlists and the library tree."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
if str(REPO / "src") not in sys.path:
    sys.path.insert(0, str(REPO / "src"))

FIXTURES = REPO / "tests" / "fixtures"
REFERENCE = FIXTURES / "reference"   # frozen 2026-11-25 corpus: format reference
LIVE = FIXTURES / "live"             # current project pages (includes hand-placed C59)
NETLISTS = FIXTURES / "netlists"
LIBRARIES = FIXTURES / "libraries"
DBL = LIBRARIES / "components_db_windows.kicad_dbl"

#: the seven pages of the 2026-11-25 build, and their expected part counts (Â§Appendix D)
PAGES = {
    "MCU": 30,
    "Power": 49,
    "USB": 12,
    "Channel_1-4": 32,
    "Channel_5-8": 32,
    "Sync": 16,
    "Indicator": 25,
}
