"""Write `kicad_lib/Symbol/**` with LCSC3D's own converter (vendored, byte-identical).

The conversion is **LCSC3D's code**, not a port of it: `vendor/lcsc3d/` holds verbatim copies
of `eda/easyeda_import.py` and `eda/kicad.py` (see `vendor/VENDOR.md` for the audit). This
script only supplies the three things LCSC3D leaves to its application layer â€” the source
document, the file name, and the write.

    # fetch what is missing, then rewrite every symbol the database references
    uv run python tools/export_symbols.py

    # no network at all: fail if a source document is not cached
    uv run python tools/export_symbols.py --offline

    # what would change
    uv run python tools/export_symbols.py --dry-run

The EasyEDA documents are cached under `kicad_lib/source/<part>.json`, so a library can
always be regenerated from committed inputs. Parts whose database row points at
`Standard:*` are left alone: that library is KiCad's own, not EasyEDA's.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "vendor"))

from lcsc3d.eda import easyeda_import, kicad          # noqa: E402  (path set above)
from lcsc3d.core.errors import DownloadError, EdaError  # noqa: E402

API_PRODUCT = "https://easyeda.com/api/products/{part}/components"
USER_AGENT = "schwrite/0.1 (LCSC3D vendored converter)"
HEADERS = {"User-Agent": USER_AGENT, "Accept": "*/*", "Accept-Encoding": "gzip"}
MAX_BYTES = 8 * 1024 * 1024
INTERVAL = 0.35          # the API rejects bursts; LCSC3D is a desktop app, be a good citizen


# -- inputs ----------------------------------------------------------------
def read_targets(dbl: Path) -> list[tuple[str, str, str]]:
    """`[(part, value, symbol_library_id)]` from the database the schematic uses."""
    description = json.loads(dbl.read_text(encoding="utf-8"))
    library = description["libraries"][0]
    connection = (description.get("source") or {}).get("connection_string") or ""
    database = Path(dbl.parent / "components.db")
    if not database.is_file():
        marker = connection.split("Database=")[-1].split(";")[0].strip().strip("{}")
        database = Path(marker.replace("${CWD}", str(dbl.parent)).replace("\\\\", "\\"))
    with sqlite3.connect(f"file:{database}?mode=ro", uri=True) as connection_handle:
        connection_handle.row_factory = sqlite3.Row
        rows = connection_handle.execute(
            f"SELECT {library['key']}, Value, {library['symbols']}, "
            f"DistributorProductNumber FROM {library['table']} ORDER BY 1"
        ).fetchall()
    targets = []
    for row in rows:
        symbol_id = str(row[library["symbols"]] or "")
        part = str(row["DistributorProductNumber"] or "")
        if symbol_id.startswith("Standard:"):
            continue                      # KiCad's own library, not EasyEDA's
        if not symbol_id.startswith("Symbol:") or not part:
            continue
        targets.append((part, str(row["Value"] or ""), symbol_id))
    return targets


def fetch_document(part: str, cache: Path, *, offline: bool) -> dict:
    """The EasyEDA document for one part, from the cache or the API."""
    cached = cache / f"{part}.json"
    if cached.is_file():
        return json.loads(cached.read_text(encoding="utf-8"))
    if offline:
        raise SystemExit(
            f"{part}: no cached source document at {cached}. Run once without --offline, "
            f"or restore kicad_lib/source/."
        )
    request = urllib.request.Request(API_PRODUCT.format(part=part), headers=HEADERS)
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read(MAX_BYTES)
        if response.headers.get("Content-Encoding") == "gzip":
            body = gzip.decompress(body)
    payload = json.loads(body.decode("utf-8"))
    if not payload.get("success") or "result" not in payload:
        raise SystemExit(f"{part}: EasyEDA returned no component document: {payload.get('code')}")
    cache.mkdir(parents=True, exist_ok=True)
    cached.write_text(json.dumps(payload["result"], ensure_ascii=False, indent=1), encoding="utf-8")
    time.sleep(INTERVAL)
    return payload["result"]


# -- conversion (all of it LCSC3D's) --------------------------------------
def convert(part: str, symbol_id: str, document: dict) -> tuple[str, bytes]:
    """`Symbol:<name>` + EasyEDA document â†’ `(<name>, .kicad_sym bytes)`."""
    name = symbol_id.split(":", 1)[1]
    component = easyeda_import.parse_component(document, part, lambda: None, domains=("symbol",))
    if component.symbol is None:
        detail = "; ".join(f"{d.domain}: {d.message}" for d in component.diagnostics) or "no symbol"
        raise DownloadError(f"{part} ({name}): LCSC3D could not build a symbol â€” {detail}")
    definition = kicad.symbol_definition(component, name)
    return name, kicad.symbol_library([definition])


def find_kicad_cli() -> str | None:
    """`kicad-cli` on PATH, or where KiCad installs it on Windows."""
    found = shutil.which("kicad-cli")
    if found:
        return found
    for candidate in (
        r"C:\Program Files\KiCad\10.0\bin\kicad-cli.exe",
        r"C:\Program Files\KiCad\9.0\bin\kicad-cli.exe",
    ):
        if Path(candidate).is_file():
            return candidate
    return None


def upgrade_with_kicad_cli(paths: list[Path], cli: str) -> int:
    """Convert each LCSC3D-format library to the installed KiCad's native syntax.

    LCSC3D writes KiCad 6-era stamps (`version 20211014`, `(id N)`, bare `hide`). KiCad 10
    reads them, but it rewrites them on save, so a page that embeds the old spelling looks
    stale against the library the moment a human opens it. `kicad-cli sym upgrade` is
    KiCad's own converter â€” using it keeps the "no reimplementation" rule that this whole
    tool exists to honour.
    """
    upgraded = 0
    for path in paths:
        temp = path.with_suffix(".upgrading.kicad_sym")
        result = subprocess.run(
            [cli, "sym", "upgrade", "--output", str(temp), str(path)],
            capture_output=True, text=True,
        )
        if result.returncode != 0 or not temp.is_file():
            print(f"FAILED upgrade {path.name}: {(result.stderr or result.stdout).strip()[:200]}",
                  file=sys.stderr)
            temp.unlink(missing_ok=True)
            continue
        os.replace(temp, path)          # KiCad refuses in-place upgrade, so swap it in
        upgraded += 1
    return upgraded


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dbl", default=str(REPO.parent / "kicad_lib" / "components_db_windows.kicad_dbl"))
    parser.add_argument("--libs", default=str(REPO.parent / "kicad_lib"), help="kicad_lib directory")
    parser.add_argument("--source-dir", help="where EasyEDA documents are cached (default <libs>/source)")
    parser.add_argument("--only", help="comma-separated LCSC part numbers")
    parser.add_argument("--offline", action="store_true", help="fail instead of fetching")
    parser.add_argument("--dry-run", action="store_true", help="report, write nothing")
    parser.add_argument("--force", action="store_true", help="rewrite files whose content is unchanged")
    parser.add_argument(
        "--no-upgrade",
        action="store_true",
        help="keep the LCSC3D KiCad 6-era syntax instead of running kicad-cli sym upgrade",
    )
    args = parser.parse_args(argv)

    libs = Path(args.libs).resolve()
    source = Path(args.source_dir).resolve() if args.source_dir else libs / "source"
    targets = read_targets(Path(args.dbl))
    if args.only:
        wanted = {part.strip() for part in args.only.split(",") if part.strip()}
        targets = [row for row in targets if row[0] in wanted]
        missing = wanted - {row[0] for row in targets}
        if missing:
            print(f"not in the database as Symbol:*: {', '.join(sorted(missing))}", file=sys.stderr)

    out_dir = libs / "Symbol" / "Symbol"
    out_dir.mkdir(parents=True, exist_ok=True)
    written = unchanged = failed = 0
    written_paths: list[Path] = []
    for part, value, symbol_id in targets:
        try:
            document = fetch_document(part, source, offline=args.offline)
            name, payload = convert(part, symbol_id, document)
        except (DownloadError, EdaError, OSError, ValueError) as error:
            print(f"FAILED {part} {symbol_id}: {error}", file=sys.stderr)
            failed += 1
            continue
        target = out_dir / f"{name}.kicad_sym"
        previous = target.read_bytes() if target.is_file() else b""
        if payload == previous and not args.force:
            unchanged += 1
            print(f"same    {name}")
            continue
        digest = hashlib.sha256(payload).hexdigest()[:12]
        if args.dry_run:
            print(f"would   {name}  ({len(payload)} bytes, {digest})")
            continue
        target.write_bytes(payload)
        written_paths.append(target)
        written += 1
        print(f"wrote   {name}  ({len(payload)} bytes, {digest})  {value}")

    if written_paths and not args.no_upgrade:
        cli = find_kicad_cli()
        if cli:
            upgraded = upgrade_with_kicad_cli(written_paths, cli)
            print(f"{upgraded} upgraded to KiCad native syntax with {Path(cli).name}")
        else:
            print("kicad-cli not found: libraries keep the LCSC3D KiCad 6-era syntax", file=sys.stderr)

    print(f"\n{written} written, {unchanged} unchanged, {failed} failed, {len(targets)} targets")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
