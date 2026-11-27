"""S-expression reading and writing for KiCad symbol and footprint files.

Only what this skill needs: read a file into nested Python lists, walk it, and
rewrite a handful of quoted tokens in place (name changes during staging).
The parser is tolerant — KiCad's own writer is not the only producer of these
files, and a library that the user already has must never be rejected because
this skill dislikes its whitespace.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

Node = list["Node | str"]

_WS = " \t\r\n"

#: A quoted token, e.g. ``"F.Cu"``; **not** used for rewriting, only for scanning.
_QUOTED = re.compile(r'"((?:[^"\\]|\\.)*)"')


class SexprError(ValueError):
    """The file is not a well-formed S-expression."""


def parse(text: str) -> list[Node]:
    """Parse *text* into a list of top-level nodes.

    Raises :class:`SexprError` when parentheses or quotes do not balance, so a
    truncated download is reported instead of silently misread.
    """
    roots: list[Node] = []
    stack: list[Node] = []
    index = 0
    length = len(text)
    while index < length:
        char = text[index]
        if char in _WS:
            index += 1
            continue
        if char == "(":
            node: Node = []
            if stack:
                stack[-1].append(node)
            else:
                roots.append(node)
            stack.append(node)
            index += 1
            continue
        if char == ")":
            if not stack:
                raise SexprError(f"unbalanced ')' at offset {index}")
            stack.pop()
            index += 1
            continue
        if char == '"':
            value, index = _read_quoted(text, index)
            if stack:
                stack[-1].append(value)
            else:
                roots.append(value)  # type: ignore[arg-type]
            continue
        start = index
        while index < length and text[index] not in _WS + '()"':
            index += 1
        token = text[start:index]
        if stack:
            stack[-1].append(token)
        else:
            roots.append(token)  # type: ignore[arg-type]
    if stack:
        raise SexprError(f"{len(stack)} unclosed '(' at end of file")
    return roots


def _read_quoted(text: str, index: int) -> tuple[str, int]:
    index += 1  # opening quote
    out: list[str] = []
    length = len(text)
    while index < length:
        char = text[index]
        if char == "\\" and index + 1 < length:
            out.append(text[index + 1])
            index += 2
            continue
        if char == '"':
            return "".join(out), index + 1
        out.append(char)
        index += 1
    raise SexprError("unterminated quoted string")


def load(path: str | Path) -> list[Node]:
    """Read and parse a file, tolerating a UTF-8 BOM."""
    data = Path(path).read_text(encoding="utf-8-sig", errors="replace")
    return parse(data)


# -- walking ---------------------------------------------------------------


def head(node: Any) -> str:
    """The atom naming a node (``symbol``, ``pad``, ``pin`` …), or ``""``."""
    if isinstance(node, list) and node and isinstance(node[0], str):
        return node[0]
    return ""


def children(node: Node, name: str | None = None) -> Iterable[Node]:
    """Direct child nodes, optionally filtered by head."""
    for item in node[1:]:
        if isinstance(item, list):
            if name is None or head(item) == name:
                yield item


def walk(node: Node, name: str | None = None) -> Iterable[Node]:
    """Every descendant node (depth-first), optionally filtered by head."""
    for item in node[1:]:
        if not isinstance(item, list):
            continue
        if name is None or head(item) == name:
            yield item
        yield from walk(item, name)


def atom(node: Node, index: int, default: str = "") -> str:
    """The *index*-th atom of a node, as text."""
    if index < len(node) and isinstance(node[index], str):
        return node[index]
    return default


def find(node: Node, name: str) -> Node | None:
    """First direct child with head *name*."""
    for item in children(node, name):
        return item
    return None


def find_deep(node: Node, name: str) -> Node | None:
    for item in walk(node, name):
        return item
    return None


# -- rewriting -------------------------------------------------------------


def rename_symbol(text: str, old: str, new: str) -> tuple[str, int]:
    """Rename a top-level symbol and its ``old_unit_style`` child units.

    Only the ``(symbol "…")`` heads are touched, so a property value or a pin
    name that happens to start with the symbol name is left alone. Returns the
    new text and how many declarations changed.
    """
    changed = 0
    pattern = re.compile(r'\(symbol\s+"' + re.escape(old) + r'((?:_[^"]*)?)"')

    def replace(match: re.Match[str]) -> str:
        nonlocal changed
        changed += 1
        return f'(symbol "{new}{match.group(1)}"'

    return pattern.sub(replace, text), changed


def set_footprint_field(text: str, reference: str) -> tuple[str, int]:
    """Set the ``Footprint`` property of the first symbol to *reference*."""
    pattern = re.compile(r'(\(property\s+"Footprint"\s+)"(?:[^"\\]|\\.)*"')

    def replace(match: re.Match[str]) -> str:
        return match.group(1) + '"' + reference + '"'

    new_text, count = pattern.subn(replace, text, count=1)
    return new_text, count


def rename_footprint(text: str, new: str) -> tuple[str, int]:
    """Set ``(footprint "…")`` to *new*; returns text and change count."""
    pattern = re.compile(r'\(footprint\s+"(?:[^"\\]|\\.)*"')

    def replace(_match: re.Match[str]) -> str:
        return f'(footprint "{new}"'

    return pattern.subn(replace, text, count=1)


def set_model_path(text: str, path: str) -> tuple[str, int]:
    """Point the first ``(model "…")`` block at *path*."""
    pattern = re.compile(r'\(model\s+"(?:[^"\\]|\\.)*"')

    def replace(_match: re.Match[str]) -> str:
        return f'(model "{path}"'

    return pattern.subn(replace, text, count=1)
