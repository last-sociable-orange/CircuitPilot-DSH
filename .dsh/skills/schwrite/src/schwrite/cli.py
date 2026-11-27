"""Command line (Â§10).

M2 implements `build` only â€” the gates (`verify`, `lint`, `pages`) arrive in M4. What is
already true here: one atomic write, a JSON report on stdout, and stable exit codes.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path

from . import context as ctx
from . import dblib, erc, kicad_cli, layout, libtables, netlist, parts, symbols, verify
from .emit import writer
from .errors import DbError, EmitError, NetlistError, PartError, SchwriteError
from .ids import UuidSource
from .page import build_page_model

EXIT_OK = 0
EXIT_NETLIST = 2
EXIT_BUILD = 3
EXIT_LINT = 4
EXIT_ERC = 5
EXIT_VERIFY = 6

ENGINE = "schwrite/0.1"


def _default_libs(out_path: Path) -> Path:
    """`<out>/../kicad_lib`, which is where a KiCad project keeps its libraries."""
    candidate = out_path.parent.parent / "kicad_lib"
    if candidate.is_dir():
        return candidate
    return candidate


def _default_db(libs: Path) -> Path:
    return dblib.default_dbl_path(libs.parent)


def cmd_build(args: argparse.Namespace) -> int:
    started = time.perf_counter()
    out_path = Path(args.out).resolve()
    libs = Path(args.libs).resolve() if args.libs else _default_libs(out_path)
    dbl = Path(args.db).resolve() if args.db else _default_db(libs)

    report: dict = {
        "page": None,
        "out": str(out_path),
        "engine": ENGINE,
        "verdict": "fail",
        "gates": {"netlist": "skipped", "erc": "skipped", "lint": "skipped"},
    }

    try:
        loaded = netlist.load(Path(args.netlist))
        db = dblib.ComponentDb(dbl)
        library = symbols.SymbolLibrary(libs)
        resolved = parts.resolve_parts(loaded, db, library)

        instance_context = None
        if args.sheet_path:
            instance_context = ctx.context_from_path(
                args.sheet_path, args.project or out_path.parent.name
            )
        else:
            root_page = (
                Path(args.root_page).resolve()
                if args.root_page
                else ctx.find_root_page(out_path.parent)
            )
            if root_page is not None:
                instance_context = ctx.read_context(root_page, out_path.name)
                if args.project:
                    instance_context = ctx.InstanceContext(
                        project=args.project,
                        path=instance_context.path,
                        sheet_uuid=instance_context.sheet_uuid,
                        root_page=instance_context.root_page,
                    )

        uuids = UuidSource(args.uuid_seed)
        paper = args.paper.upper()
        if paper == "AUTO":
            found = layout.smallest_fitting_page(resolved)
            if found is None:
                raise EmitError(
                    f"{loaded.subsystem}: the page does not fit any sheet up to A0 at the "
                    f"split the netlist, or pick a larger --paper"
                )
            paper = found[0]
        model = build_page_model(
            netlist=loaded,
            resolved=resolved,
            page=loaded.subsystem or out_path.stem,
            paper=paper,
            context=instance_context,
            uuids=uuids,
        )
        if not model.layout["fits"]:
            fits = layout.smallest_fitting_page(resolved)
            needed = f"{model.layout['width_mm']}x{model.layout['height_mm']} mm"
            usable = model.layout["usable_mm"]
            where = (
                f"smallest sheet that holds it: {fits[0]} "
                f"({fits[1]['width_mm']}x{fits[1]['height_mm']} mm) — pass --paper {fits[0]} "
                f"or --paper auto"
                if fits
                else "no sheet up to A0 holds it; split the netlist"
            )
            raise EmitError(
                f"{model.page} does not fit {paper}: the plan needs {needed}, "
                f"{paper} has {usable[0]:g}x{usable[1]:g} mm of drawing area. {where}"
            )
        symbol_set = parts.symbols_for(resolved, library)
        text = writer.render_page(model, symbol_set, uuids)

        out_path.parent.mkdir(parents=True, exist_ok=True)
        handle, temp_name = tempfile.mkstemp(
            dir=str(out_path.parent), prefix=f".{out_path.name}.", suffix=".tmp"
        )
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        os.replace(temp_name, out_path)          # S8: never a half-written page

        tables = []
        if not args.no_sym_lib_table:
            # Verified against the project, never imposed from a constant list: what the
            # page needs is discovered from its parts and the database rows.
            tables = libtables.check(
                out_path.parent, libtables.needs(resolved, db, libs, dbl), repair=True
            )
            blocking = [line for table in tables if table.fatal for line in table.unresolved]
            if blocking:
                raise EmitError("\n".join(blocking))

        report.update(
            {
                "page": model.page,
                "parts": len(model.parts),
                "project": model.project,
                "path": model.path,
                "paper": model.paper,
                "paper_requested": args.paper,
                "symbols": len(symbol_set),
                "lib_tables": libtables.summary(tables),
                "layout": model.layout,
                "unconnected": [
                    {"ref": ref, "pin": pin, "reason": "unused"}
                    for ref, pin in model.unconnected
                ],
                "timings_ms": {"build": round((time.perf_counter() - started) * 1000)},
                "verdict": "pass",
            }
        )
        _emit_report(report, args.json)
        return EXIT_OK

    except NetlistError as error:
        report["error"] = {"kind": "netlist", "detail": str(error)}
        _emit_report(report, args.json)
        return EXIT_NETLIST
    except (PartError, DbError, EmitError, SchwriteError) as error:
        report["error"] = {"kind": "build", "detail": str(error)}
        _emit_report(report, args.json)
        return EXIT_BUILD


def cmd_verify(args: argparse.Namespace) -> int:
    """Gate S3: KiCad's read-back must hold exactly the parts the netlist asked for."""
    report: dict = {"command": "verify", "page": args.page, "verdict": "pass"}
    started = time.perf_counter()
    try:
        page = Path(args.page)
        out_dir = page.parent
        libs = Path(args.libs) if args.libs else _default_libs(out_dir)
        dbl = Path(args.db) if args.db else _default_db(libs)
        database = dblib.ComponentDb(dbl)
        library = symbols.SymbolLibrary(libs)

        loaded = netlist.load(args.netlist)
        expected = verify.expected_from_parts(parts.resolve_parts(loaded, database, library))
        actual = verify.readback(page)
        comparison = verify.compare(expected, actual)

        report.update(
            {
                "components_expected": len(expected),
                "components_read_back": len(actual),
                "missing": comparison.missing,
                "extra": comparison.extra,
                "wrong_value": [list(item) for item in comparison.wrong_value],
                "wrong_footprint": [list(item) for item in comparison.wrong_footprint],
                "timings_ms": {"verify": round((time.perf_counter() - started) * 1000)},
            }
        )
        if not comparison.ok:
            report["verdict"] = "fail"
            report["problems"] = comparison.problems()
            _emit_report(report, args.json)
            return EXIT_VERIFY
        _emit_report(report, args.json)
        return EXIT_OK
    except (kicad_cli.ToolError, NetlistError, EmitError) as error:
        report["verdict"] = "error"
        report["error"] = {"kind": "verify", "detail": str(error)}
        _emit_report(report, args.json)
        return EXIT_VERIFY


def cmd_erc(args: argparse.Namespace) -> int:
    """Gate S4: only the violation classes a placement-only page may have."""
    report: dict = {"command": "erc", "page": args.page, "verdict": "pass"}
    started = time.perf_counter()
    try:
        result = erc.run(args.page)
        report.update(
            {
                "checked": result.checked,
                "mode": result.mode,
                "counts": result.counts,
                "expected_classes": sorted(erc.EXPECTED),
                "unexpected": len(result.unexpected),
                "timings_ms": {"erc": round((time.perf_counter() - started) * 1000)},
            }
        )
        if not result.ok:
            report["verdict"] = "fail"
            report["problems"] = result.problems()
            _emit_report(report, args.json)
            return EXIT_ERC
        _emit_report(report, args.json)
        return EXIT_OK
    except kicad_cli.ToolError as error:
        report["verdict"] = "error"
        report["error"] = {"kind": "erc", "detail": str(error)}
        _emit_report(report, args.json)
        return EXIT_ERC


def _emit_report(report: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return
    if report.get("verdict") == "pass":
        command = report.get("command", "build")
        if command == "verify":
            print(
                f"{report['page']}: {report['components_read_back']} components read back, "
                f"all {report['components_expected']} expected present and correct"
            )
        elif command == "erc":
            counts = report.get("counts") or {}
            detail = ", ".join(f"{k} {v}" for k, v in sorted(counts.items())) or "none"
            print(f"{report['page']}: no unexpected ERC classes ({detail})")
        else:
            layout_info = report.get("layout") or {}
            print(
                f"{report['page']}: {report['parts']} parts, "
                f"{layout_info.get('width_mm')}x{layout_info.get('height_mm')} mm, "
                f"{layout_info.get('columns')} column(s), {report['paper']} -> {report['out']}"
            )
        return
    if report.get("problems"):
        for line in report["problems"]:
            print(f"  {line}", file=sys.stderr)
        return
    error = report.get("error") or {}
    print(f"FAILED ({error.get('kind', '?')}): {error.get('detail', '')}", file=sys.stderr)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="schwrite", description="Netlist-driven KiCad schematic page generator"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="write one page from one netlist")
    build.add_argument("--netlist", required=True, help="netlist JSON for this page")
    build.add_argument("--out", required=True, help="page to write (.kicad_sch)")
    build.add_argument("--libs", help="kicad_lib directory (default: <out>/../kicad_lib)")
    build.add_argument("--db", help=".kicad_dbl (default: components_db_<os> in kicad_lib)")
    build.add_argument(
        "--paper",
        default="A4",
        help="paper size (default A4; 'auto' picks the smallest sheet that fits)",
    )
    build.add_argument("--project", help="project name for instance data")
    build.add_argument("--root-page", help="root .kicad_sch to take the sheet path from")
    build.add_argument("--sheet-path", help='instance path, e.g. "/<root-uuid>/<sheet-uuid>"')
    build.add_argument("--uuid-seed", help="deterministic uuids (for golden tests)")
    build.add_argument("--json", action="store_true", help="JSON report on stdout")
    build.add_argument(
        "--no-sym-lib-table",
        action="store_true",
        help="do not write/refresh the sym-lib-table beside the page",
    )

    verify_cmd = sub.add_parser(
        "verify", help="read a page back with KiCad and compare it with its netlist"
    )
    verify_cmd.add_argument("--page", required=True, help="page to check (.kicad_sch)")
    verify_cmd.add_argument("--netlist", required=True, help="netlist JSON it was built from")
    verify_cmd.add_argument("--libs", help="kicad_lib directory (default: <page>/../kicad_lib)")
    verify_cmd.add_argument("--db", help=".kicad_dbl (default: components_db_<os> in kicad_lib)")
    verify_cmd.add_argument("--json", action="store_true", help="JSON report on stdout")

    erc_cmd = sub.add_parser("erc", help="ERC a page, failing on unexpected violation classes")
    erc_cmd.add_argument("--page", required=True, help="page to check (.kicad_sch)")
    erc_cmd.add_argument("--json", action="store_true", help="JSON report on stdout")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "build":
        return cmd_build(args)
    if args.command == "verify":
        return cmd_verify(args)
    if args.command == "erc":
        return cmd_erc(args)
    parser.error(f"unknown command {args.command}")
    return EXIT_BUILD


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
