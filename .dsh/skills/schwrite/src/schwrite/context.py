"""Instance context: which project and which sheet path a page belongs to (M0 finding ②).

A page written by `schwrite` is a **child** of an existing root page. Its symbol instances
must carry the parent's path or KiCad loses the references on the next save, so the build
reads three facts once per run: the project name, the sheet-symbol uuid, and the path that
combines them with the root page's uuid.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import sexp
from .errors import EmitError


@dataclass(frozen=True)
class InstanceContext:
    """What `(instances (project … (path …)))` needs for every symbol on one page."""

    project: str
    path: str                 # "/<root-uuid>/<sheet-uuid>", or "/" for a root page
    sheet_uuid: str = ""      # the parent's sheet-symbol uuid ("" for a root page)
    root_page: Path | None = None

    @property
    def is_root(self) -> bool:
        return self.path == "/"


def find_root_page(page_dir: str | Path) -> Path | None:
    """`<dir>/<project>.kicad_sch` for the `.kicad_pro` sitting beside the pages."""
    page_dir = Path(page_dir)
    for project in sorted(page_dir.glob("*.kicad_pro")):
        candidate = project.with_suffix(".kicad_sch")
        if candidate.is_file():
            return candidate
    return None


def _property(node: list, name: str) -> str:
    for child in node[1:]:
        if isinstance(child, list) and sexp.node_name(child) == "property":
            if len(child) > 2 and sexp.unquote(child[1]) == name:
                return sexp.unquote(child[2])
    return ""


def _uuid_of(node: list) -> str:
    for child in node[1:]:
        if isinstance(child, list) and sexp.node_name(child) == "uuid":
            return sexp.unquote(child[1])
    return ""


def read_context(root_page: str | Path, page_filename: str) -> InstanceContext:
    """Find the sheet symbol in `root_page` whose `Sheetfile` is `page_filename`."""
    root_page = Path(root_page)
    if not root_page.is_file():
        raise EmitError(f"root page not found: {root_page}")
    tree = sexp.parse(root_page.read_text(encoding="utf-8"))
    project = root_page.with_suffix(".kicad_pro")
    project_name = project.stem if project.is_file() else root_page.stem
    root_uuid = ""
    sheets: list[list] = []
    for node in tree[1:]:
        if not isinstance(node, list):
            continue
        name = sexp.node_name(node)
        if name == "uuid":
            root_uuid = sexp.unquote(node[1])
        elif name == "sheet":
            sheets.append(node)

    wanted = Path(page_filename).name.lower()
    for sheet in sheets:
        sheetfile = _property(sheet, "Sheetfile")
        if Path(sheetfile).name.lower() != wanted:
            continue
        sheet_uuid = _uuid_of(sheet)
        if not sheet_uuid:
            raise EmitError(f"{root_page.name}: sheet for {page_filename} has no uuid")
        return InstanceContext(
            project=project_name,
            path=f"/{root_uuid}/{sheet_uuid}",
            sheet_uuid=sheet_uuid,
            root_page=root_page,
        )

    # Not in the sheet tree: this page is meant to stand alone as a root page.
    if not sheets:
        return InstanceContext(project=project_name, path="/", root_page=root_page)
    known = ", ".join(sorted(Path(_property(s, "Sheetfile")).name for s in sheets))
    raise EmitError(
        f"{root_page.name} has no sheet for {page_filename!r}; it places: {known}. "
        f"Add the sheet to the root page, or pass --root-page/--sheet-path explicitly."
    )


def context_from_path(path: str, project: str) -> InstanceContext:
    """`--sheet-path /a/b` and `--project P` given on the command line."""
    if not path.startswith("/"):
        raise EmitError(f"sheet path must start with '/': {path!r}")
    sheet_uuid = path.rstrip("/").rsplit("/", 1)[-1] if path.strip("/") else ""
    return InstanceContext(project=project, path=path, sheet_uuid=sheet_uuid)
