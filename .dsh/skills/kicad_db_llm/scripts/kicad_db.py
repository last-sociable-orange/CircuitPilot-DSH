#!/usr/bin/env python3
"""kicad_db — fill a KiCad database-library SQLite file from LCSC parts.

    python scripts/kicad_db.py check
    python scripts/kicad_db.py plan    bom.csv --detail-json parts.json
    python scripts/kicad_db.py apply   bom.csv --detail-json parts.json
    python scripts/kicad_db.py add     C25804 --value 10k
    python scripts/kicad_db.py stage   C8734 --bundle WIP/lcsc-libs-out
    python scripts/kicad_db.py verify

``plan``, ``check``, ``catalog``, ``verify``, ``show`` and ``selftest`` never
write anything. ``apply``, ``add`` and ``stage`` write, and take ``--dry-run`` to
show exactly what they would do first. Standard library only — no packages.
"""

from __future__ import annotations

import argparse
import contextlib
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from dbcore import config as config_mod  # noqa: E402
from dbcore import report, runner, schema  # noqa: E402
from dbcore.lcsc import Lookup, LookupProblem, StorefrontRefused  # noqa: E402
from dbcore.libraries import LibraryProblem, LibrarySet  # noqa: E402
from dbcore.mapping import MODES, decide  # noqa: E402
from dbcore.parts import BomLine, load_bom  # noqa: E402
from dbcore.stage import read_bundle, stage  # noqa: E402

PROG = "kicad_db.py"


def _common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--libs-root", help="the kicad_lib folder (default: auto-detected)")
    parser.add_argument("--db", help="the SQLite file (default: <libs-root>/components.db)")
    parser.add_argument("--config", help="extra JSON config to merge")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--lang", default=None, choices=["en_US", "zh_CN"],
                        help="storefront for part lookups (default: config, en_US)")
    parser.add_argument("--detail-json", action="append", default=[], metavar="FILE",
                        help="pre-captured 'lcsc-parts detail --json' output (repeatable)")
    parser.add_argument("--offline", action="store_true",
                        help="use only --detail-json data; never call the storefront")
    parser.add_argument("--mode", default="auto", choices=list(MODES),
                        help="auto: standard symbols for passives only (default); "
                             "all: also try standard for actives; off: always use downloads")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=PROG, description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="report configuration, library tree and database")
    _common(check)

    catalog = sub.add_parser("catalog", help="list the standard library and the mapping table")
    _common(catalog)

    plan = sub.add_parser("plan", help="decide every BOM line; writes nothing")
    _common(plan)
    _bom_arguments(plan)

    apply_cmd = sub.add_parser("apply", help="decide and write the rows")
    _common(apply_cmd)
    _bom_arguments(apply_cmd)
    _write_arguments(apply_cmd)

    add = sub.add_parser("add", help="one part, from the command line")
    _common(add)
    add.add_argument("part", help="LCSC part number (C…) or manufacturer part number")
    add.add_argument("--value", default="", help="schematic value (default: the store's)")
    add.add_argument("--name", default="", help="library name for the downloaded files")
    add.add_argument("--type", dest="product_type", default="", help="product-type prefix (IC, CON, …)")
    add.add_argument("--symbol", default="", help="explicit KicadSymbolLibrary value")
    add.add_argument("--footprint", default="", help="explicit KicadFootprintLibrary value")
    add.add_argument("--keywords", default="", help="Keywords column")
    add.add_argument("--bundle", default="", help="lcsc-libs output folder for this part")
    _write_arguments(add)

    stage_cmd = sub.add_parser("stage", help="copy an lcsc-libs bundle into the library tree")
    _common(stage_cmd)
    stage_cmd.add_argument("part", help="LCSC part number in the bundle")
    stage_cmd.add_argument("--bundle", required=True, help="lcsc-libs output folder")
    stage_cmd.add_argument("--name", default="", help="target library name")
    stage_cmd.add_argument("--type", dest="product_type", default="", help="product-type prefix")
    stage_cmd.add_argument("--dry-run", action="store_true",
                           help="show what would be copied, copy nothing")

    verify = sub.add_parser("verify", help="check every row against the library tree")
    _common(verify)

    show = sub.add_parser("show", help="print one row")
    _common(show)
    show.add_argument("part", help="MPN or LCSC part number")

    selftest = sub.add_parser("selftest", help="offline checks; needs no network and no database")
    _common(selftest)
    selftest.add_argument("--workdir", default="", help="scratch folder for the fixture tree")

    return parser


def _bom_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("bom", help="BOM file (.csv or .json)")
    parser.add_argument("--bundle", default="", help="lcsc-libs output folder holding the parts")
    parser.add_argument("--report", default="", help="also write a Markdown report here")
    parser.add_argument("--show-evidence", action="store_true",
                        help="print every evidence line, not just problems")


def _write_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--dry-run", action="store_true",
                        help="print the plan and write nothing")
    parser.add_argument("--on-exist", default="skip", choices=["skip", "update", "fail"],
                        help="what to do when the MPN is already in the database (default: skip)")
    parser.add_argument("--auto-stage", action="store_true",
                        help="stage the bundle files first when they are not in the library yet")


# -- helpers ---------------------------------------------------------------


def _config(args) -> config_mod.Config:
    return config_mod.load(
        config_path=args.config,
        libs_root=args.libs_root,
        database=args.db,
        language=getattr(args, "lang", None),
    )


def _lookup(args, config: config_mod.Config) -> Lookup:
    lookup = Lookup(config)
    for path in args.detail_json:
        loaded = lookup.load_json(path)
        if not args.json:
            print(f"loaded {loaded} part(s) from {path}")
    return lookup


def _bundle_index(args) -> dict:
    if not getattr(args, "bundle", ""):
        return {}
    try:
        return read_bundle(args.bundle)
    except LibraryProblem as exc:
        print(f"warning: {exc}", file=sys.stderr)
        return {}


def _existing_rows(config: config_mod.Config):
    """Cached MPN lookup against the configured database (``None`` if absent)."""
    return runner.existing_lookup(config)

def _write_report_file(path: str, text: str) -> None:
    target = Path(path).expanduser()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    print(f"report written to {target}")


def _finish_write(args, config, outcomes, *, title: str) -> int:
    dry_run = getattr(args, "dry_run", False)
    if dry_run:
        if args.json:
            print(report.dumps({"outcomes": report.plan_json(outcomes), "written": False}))
        else:
            print(report.plan_text(outcomes, show_evidence=getattr(args, "show_evidence", False)))
            print("")
            print("dry run: nothing written. Run the same command without --dry-run to write.")
        return 0

    summary = runner.commit(config, outcomes, on_exist=args.on_exist)
    if args.json:
        print(report.dumps({"outcomes": report.plan_json(outcomes), "summary": vars(summary)}))
    else:
        print(report.plan_text(outcomes, show_evidence=getattr(args, "show_evidence", False)))
        print("")
        print(
            f"database {config.database}: inserted {summary.inserted}, "
            f"updated {summary.updated}, skipped {summary.skipped}, "
            f"not written {summary.failed}"
        )
        for label, columns in summary.changed_fields.items():
            print(f"  {label}: changed {', '.join(columns)}")
        for error in summary.errors:
            print(f"  ! {error}")
    if args.report:
        _write_report_file(args.report, report.plan_markdown(outcomes, config=config,
                                                             summary=summary, title=title))
    return 1 if summary.failed else 0


# -- commands --------------------------------------------------------------


def command_check(args) -> int:
    try:
        config = _config(args)
        libs = LibrarySet(config)
        rows = libs.layout_report()
    except (config_mod.ConfigProblem, LibraryProblem) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    payload = {
        "python": sys.version.split()[0],
        "executable": sys.executable,
        "config_sources": config.sources,
        "libs_root": str(config.libs_root),
        "database": str(config.database),
        "database_exists": config.database.is_file(),
        "standard_symbol_file": str(config.standard_symbol.path),
        "lcsc_parts_cli": str(config.lcsc_parts_cli),
        "lcsc_parts_cli_exists": config.lcsc_parts_cli.is_file(),
        "language": config.language,
        "layout": [{"section": a, "value": b, "state": c} for a, b, c in rows],
    }
    if args.json:
        print(report.dumps(payload))
        return 0
    print(f"python      : {payload['python']}  ({payload['executable']})")
    for source in config.sources:
        print(f"config      : {source}")
    print(f"libs root   : {config.libs_root}")
    print(f"database    : {config.database} ({'found' if config.database.is_file() else 'will be created'})")
    print(f"lcsc-parts  : {config.lcsc_parts_cli} "
          f"({'found' if config.lcsc_parts_cli.is_file() else 'MISSING'})")
    print(f"language    : {config.language}")
    print("")
    print(report.layout_text(rows))
    return 0


def command_catalog(args) -> int:
    from dbcore import classify

    config = _config(args)
    libs = LibrarySet(config)
    standard = libs.standard_symbols()
    footprints = libs.standard_footprints()
    table = []
    for code, names in classify.STANDARD_SYMBOLS.items():
        cls = classify.CLASSES[code]
        present = [name for name in names if name in standard]
        missing = [name for name in names if name not in standard]
        table.append(
            {
                "class": code,
                "product_type": cls.product_type,
                "passive": cls.passive,
                "symbols_in_library": present,
                "symbols_configured_but_missing": missing,
            }
        )
    payload = {
        "standard_symbols": sorted(standard),
        "standard_footprints": sorted(footprints),
        "class_table": table,
    }
    if args.json:
        print(report.dumps(payload))
        return 0
    print(f"standard symbols ({len(standard)}) in {config.standard_symbol.path}:")
    print("  " + ", ".join(sorted(standard)))
    print("")
    print(f"standard footprints ({len(footprints)}) in {config.standard_footprints.path}:")
    print("  " + ", ".join(sorted(footprints)))
    print("")
    rows = [
        [item["class"], item["product_type"], "yes" if item["passive"] else "no",
         ", ".join(item["symbols_in_library"]) or "-",
         ", ".join(item["symbols_configured_but_missing"]) or "-"]
        for item in table
    ]
    print(report._table(["class", "prefix", "passive", "symbols present", "configured but absent"],
                        rows, limits=[20, 7, 8, 40, 40]))
    return 0


def command_plan(args) -> int:
    return _run_bom(args, write=False)


def command_apply(args) -> int:
    return _run_bom(args, write=True)


def _run_bom(args, *, write: bool) -> int:
    config = _config(args)
    libs = LibrarySet(config)
    lookup = _lookup(args, config)
    try:
        lines = load_bom(args.bom)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if not lines:
        print(f"error: {args.bom} has no lines with a part number", file=sys.stderr)
        return 2
    bundles = _bundle_index(args)

    if getattr(args, "auto_stage", False) and write and bundles:
        if not _auto_stage(args, config, lookup, bundles):
            return 1

    try:
        outcomes = runner.plan(
            lines, libs, lookup, mode=args.mode, find_existing=_existing_rows(config),
            bundles=bundles,
        )
    except StorefrontRefused as exc:
        # One line, one exit code: the batch stops instead of replaying the refusal
        # on every remaining BOM line.
        print(f"error: {exc}", file=sys.stderr)
        return 3
    if not write:
        if args.json:
            print(report.dumps(report.plan_json(outcomes)))
        else:
            print(report.plan_text(outcomes, show_evidence=args.show_evidence))
            print("")
            print(report.bom_summary_text(outcomes))
            print("read-only: nothing written. Use 'apply' to write these rows.")
        if args.report:
            _write_report_file(args.report, report.plan_markdown(outcomes, config=config,
                                                                 title="Component database plan"))
        return 0 if all(item.action != "error" for item in outcomes) else 1
    return _finish_write(args, config, outcomes, title="Component database update")


def _auto_stage(args, config, lookup: Lookup, bundles: dict) -> bool:
    """Stage every bundled part that is about to be written."""
    wanted = [key for key in bundles if lookup.get(key) is None]
    if wanted:
        try:
            lookup.fetch(list(bundles))
        except LookupProblem as exc:
            print(f"warning: {exc}", file=sys.stderr)
    results = []
    libs = LibrarySet(config)
    for key, bundle in bundles.items():
        part = lookup.get(key)
        if part is None:
            continue
        line = BomLine(lcsc=part.lcsc, mpn=part.mpn)
        mapping = decide(part, line, libs, mode=args.mode,
                         bundle_symbol=bundle.symbol, bundle_footprint=bundle.footprint)
        if mapping.uses_standard_symbol and mapping.uses_standard_footprint:
            continue  # the standard library already covers this part
        results.append(stage(config, mapping.name, bundle, apply=True))
    print(report.stages_text(results))
    return all(result.ok for result in results)


def command_add(args) -> int:
    config = _config(args)
    libs = LibrarySet(config)
    lookup = _lookup(args, config)
    try:
        part = lookup.get(args.part) or lookup.fetch([args.part])[args.part.upper()]
    except (LookupProblem, KeyError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    line = BomLine(
        lcsc=part.lcsc,
        mpn=part.mpn,
        value=args.value,
        symbol=args.symbol,
        footprint=args.footprint,
        name=args.name,
        product_type=args.product_type,
        keywords=args.keywords,
        row=1,
    )
    bundles = {}
    if args.bundle:
        try:
            bundles = read_bundle(args.bundle)
        except LibraryProblem as exc:
            print(f"warning: {exc}", file=sys.stderr)
    outcomes = runner.plan([line], libs, lookup, mode=args.mode,
                           find_existing=_existing_rows(config), bundles=bundles)
    return _finish_write(args, config, outcomes, title=f"Component database — {part.identity}")


def command_stage(args) -> int:
    config = _config(args)
    libs = LibrarySet(config)
    lookup = _lookup(args, config)
    try:
        bundles = read_bundle(args.bundle)
    except LibraryProblem as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    key = args.part.strip().upper()
    bundle = bundles.get(key)
    if bundle is None:
        print(f"error: {args.bundle} has no bundle for {args.part}", file=sys.stderr)
        print(f"       bundles present: {', '.join(sorted(bundles)) or 'none'}", file=sys.stderr)
        return 2
    try:
        part = lookup.get(key)
        if part is None and not args.name:
            part = lookup.fetch([key])[key]
    except LookupProblem as exc:
        if not args.name:
            print(f"error: cannot name the library entry: {exc}", file=sys.stderr)
            return 2
        part = None

    if part is not None:
        line = BomLine(lcsc=part.lcsc, mpn=part.mpn, product_type=args.product_type,
                       name=args.name, symbol="", footprint="")
        mapping = decide(part, line, libs, mode=args.mode,
                         bundle_symbol=bundle.symbol, bundle_footprint=bundle.footprint)
        name = mapping.name
        if mapping.uses_standard_symbol and mapping.uses_standard_footprint:
            print(
                f"{part.identity} is covered by the standard library "
                f"({mapping.symbol} + {mapping.footprint}); staging is not required."
            )
            print("Nothing copied. Use --name to stage the downloaded files anyway.")
            return 0
    else:
        name = args.name

    dry_run = args.dry_run
    result = stage(config, name, bundle, apply=not dry_run)
    print(report.stages_text([result]))
    if dry_run:
        print("")
        print("dry run: nothing copied. Run the same command without --dry-run to copy.")
    if not result.ok:
        return 1
    if not dry_run:
        print("")
        print(f"staged as {name}. Next: run 'apply' so the row points at it.")
    return 0


def command_verify(args) -> int:
    config = _config(args)
    libs = LibrarySet(config)
    try:
        result = runner.verify(config, libs)
    except schema.DatabaseProblem as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.json:
        print(report.dumps(report.verify_json(result)))
    else:
        print(report.verify_text(result))
    return 1 if result.problems else 0


def command_show(args) -> int:
    config = _config(args)
    connection = schema.open_database(config.database, create=False)
    try:
        record = schema.find_by_mpn(connection, args.part)
        if record is None:
            rows = connection.execute(
                f'SELECT * FROM "{schema.TABLE_NAME}" WHERE DistributorProductNumber = ? '
                "ORDER BY rowid LIMIT 1",
                (args.part.strip().upper(),),
            ).fetchall()
            record = schema.record_from_row(rows[0]) if rows else None
    finally:
        connection.close()
    if record is None:
        print(f"error: no row for {args.part}", file=sys.stderr)
        return 2
    if args.json:
        print(report.dumps(record.row_dict()))
        return 0
    for name, value in record.row_dict().items():
        if name.startswith(("Param", "Value")) and value == schema.UNUSED:
            continue
        if value:
            print(f"{name:32} {value}")
    return 0


def command_selftest(args) -> int:
    from dbcore.selftest import run

    return run(args.workdir or None)


COMMANDS = {
    "check": command_check,
    "catalog": command_catalog,
    "plan": command_plan,
    "apply": command_apply,
    "add": command_add,
    "stage": command_stage,
    "verify": command_verify,
    "show": command_show,
    "selftest": command_selftest,
}


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, ValueError):  # non-standard stream
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    args = build_parser().parse_args(argv)
    handler = COMMANDS[args.command]
    try:
        return handler(args)
    except (config_mod.ConfigProblem, LibraryProblem, schema.DatabaseProblem) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
