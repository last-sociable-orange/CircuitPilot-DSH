#!/usr/bin/env python3
"""lcsc-libs — datasheet, KiCad symbol, footprint and STEP for an LCSC part.

Standard library only. Fetches the EasyEDA record for an LCSC part number, converts
the symbol and footprint to native KiCad 10 files, downloads the STEP model and the
datasheet, and writes a manifest describing exactly what it produced.

    python lcsc_libs.py fetch C25804 --out <project>/WIP
    python lcsc_libs.py fetch C8734 --parts symbol,footprint --json
    python lcsc_libs.py selftest        # offline, no network
    python lcsc_libs.py check
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from easyeda import client as http  # noqa: E402
from libs.bundle import DEFAULT_MODEL_PREFIX, PARTS, Fetcher  # noqa: E402
from libs.cache import DEFAULT_TTL, ResponseCache, default_cache_dir  # noqa: E402

SKILL = SCRIPTS.parent
FIXTURES = SKILL / "tests" / "fixtures"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lcsc_libs.py",
        description="Download datasheet, KiCad symbol, footprint and STEP for an LCSC part.",
    )
    parser.add_argument("--out", default=".", help="output folder (default: current directory)")
    parser.add_argument("--cache-dir", default=None,
                        help=f"response cache folder (default: {default_cache_dir()})")
    parser.add_argument("--cache-ttl", type=float, default=DEFAULT_TTL,
                        help="seconds a cached response stays valid (0 disables caching)")
    parser.add_argument("--interval", type=float, default=http.DEFAULT_INTERVAL,
                        help="minimum seconds between requests (default: 0.35)")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--model-prefix", default=DEFAULT_MODEL_PREFIX,
                        help="path prefix written into the footprint's (model …) block")
    parser.add_argument("--offline", action="store_true",
                        help="use only cached responses; no network requests")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    sub = parser.add_subparsers(dest="command", required=True)

    fetch = sub.add_parser("fetch", help="fetch artefacts for one or more part numbers")
    fetch.add_argument("parts", nargs="+", help="LCSC part numbers, e.g. C25804 C8734")
    fetch.add_argument("--parts", dest="kinds", default=",".join(PARTS),
                       help=f"comma-separated subset of: {', '.join(PARTS)}")

    sub.add_parser("check", help="report interpreter, cache and output layout")
    sub.add_parser("selftest", help="offline checks against bundled fixtures, no network")

    clear = sub.add_parser("clear-cache", help="delete cached responses")
    clear.add_argument("--yes", action="store_true", help="actually delete")
    return parser


def make_client(args) -> http.HttpClient:
    if args.offline:
        return http.HttpClient(interval=0.0, timeout=args.timeout)
    return http.HttpClient(interval=args.interval, timeout=args.timeout)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    cache = ResponseCache(args.cache_dir, ttl=0.0 if args.offline else args.cache_ttl)
    if args.offline:
        cache.ttl = DEFAULT_TTL  # read through, never fetch

    if args.command == "check":
        print(f"python  : {sys.executable}")
        print(f"script  : {SCRIPTS}")
        print(f"cache   : {cache.directory} (ttl {cache.ttl:.0f}s)")
        print(f"fixtures: {FIXTURES if FIXTURES.exists() else 'MISSING'}")
        print(f"output  : {Path(args.out).resolve()}")
        return 0

    if args.command == "selftest":
        from libs.selftest import run_selftest

        return run_selftest(FIXTURES)

    if args.command == "clear-cache":
        if not args.yes:
            print(f"would delete cache in {cache.directory}; pass --yes to confirm")
            return 0
        print(f"removed {cache.clear()} files from {cache.directory}")
        return 0

    kinds = tuple(kind.strip() for kind in str(args.kinds).split(",") if kind.strip())
    unknown = [kind for kind in kinds if kind not in PARTS]
    if unknown:
        print(f"unknown --parts value(s): {', '.join(unknown)}; choose from {', '.join(PARTS)}",
              file=sys.stderr)
        return 2

    client = make_client(args)
    fetcher = Fetcher(client, cache, model_prefix=args.model_prefix)
    out = Path(args.out).expanduser()
    reports = []
    failures = 0
    for part in args.parts:
        try:
            manifest = fetcher.fetch(part, out, kinds)
            reports.append(manifest.as_dict())
            if not args.json:
                print(f"{manifest.part.part}  {manifest.part.mpn}  ({manifest.part.package})")
                for artefact in manifest.artefacts:
                    print(f"  {artefact.kind:9} {artefact.bytes:>10,} B  {artefact.path}")
                if not manifest.artefacts:
                    print("  (nothing produced)")
                for warning in manifest.warnings:
                    print(f"  ! {warning}")
                if args.offline:
                    print("  (offline: cached responses only)")
        except http.LibsError as exc:
            failures += 1
            reports.append({"part": part, "error": str(exc)})
            print(f"{part}: {exc}", file=sys.stderr)

    if args.json:
        print(json.dumps(reports if len(reports) > 1 else reports[0], indent=2,
                         ensure_ascii=False))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
