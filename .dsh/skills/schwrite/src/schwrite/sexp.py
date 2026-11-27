"""String-aware scanning of KiCad S-expression text.

KiCad's writer quotes strings and honours backslash escapes, so a regular expression
cannot find node boundaries safely — a net named `A(B` or a value containing `)` breaks
it. Everything here works on the character stream (SW-PLAN-SCHWRITE-001 §8.1 step 2).

Nothing in this module interprets KiCad semantics; that belongs in `symbols.py`.
"""

from __future__ import annotations

from collections.abc import Iterator

try:                                            # normal install
    import sexpdata
except ModuleNotFoundError:                     # standalone copy: the vendored single file
    import sys
    from pathlib import Path as _Path

    sys.path.insert(0, str(_Path(__file__).resolve().parent / "_vendor"))
    import sexpdata


def iter_top_level(text: str) -> Iterator[tuple[str, int, int]]:
    """Yield `(name, start, end)` for each direct child of the root node.

    `end` is exclusive. The root's own parentheses are not yielded.
    """
    i, n = 0, len(text)
    while i < n and text[i] != "(":
        i += 1
    if i >= n:
        return
    depth = 0
    start: int | None = None
    name_start = 0
    in_string = False
    while i < n:
        ch = text[i]
        if in_string:
            if ch == "\\":
                i += 2
                continue
            if ch == '"':
                in_string = False
        elif ch == '"':
            in_string = True
        elif ch == "(":
            depth += 1
            if depth == 2:
                start = i
                name_start = i + 1
        elif ch == ")":
            depth -= 1
            if depth == 1 and start is not None:
                j = name_start
                while j < n and (text[j].isalnum() or text[j] == "_"):
                    j += 1
                yield text[name_start:j], start, i + 1
                start = None
        i += 1


def top_level_nodes(text: str) -> list[tuple[str, str]]:
    """Every direct child of the root as `(name, raw_text)`."""
    return [(name, text[s:e]) for name, s, e in iter_top_level(text)]


def find_top_level(text: str, name: str, index: int = 0) -> str | None:
    """The `index`-th direct child called `name`, as raw text, or None."""
    seen = 0
    for node_name, start, end in iter_top_level(text):
        if node_name != name:
            continue
        if seen == index:
            return text[start:end]
        seen += 1
    return None


def count_top_level(text: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for name, _, _ in iter_top_level(text):
        counts[name] = counts.get(name, 0) + 1
    return counts


def node_name(node: list) -> str:
    """The head symbol of a parsed node, e.g. 'symbol' for `(symbol ...)`."""
    if isinstance(node, list) and node and isinstance(node[0], sexpdata.Symbol):
        return node[0].value()
    return ""


def parse(text: str) -> list:
    """Parse to a sexpdata tree. Use for comparison, not for editing."""
    return sexpdata.loads(text)


def unquote(value) -> str:
    """sexpdata keeps quotes in string atoms in some versions; normalise them away."""
    if isinstance(value, sexpdata.Symbol):
        return value.value()
    if isinstance(value, str):
        return value
    if isinstance(value, sexpdata.Quoted):
        return unquote(value.value())
    return str(value)


def normalise(node):
    """Canonical comparable form: quoted strings and bare symbols both become str.

    Two files that KiCad would read identically compare equal through this, even if one
    quotes a token the other does not — which is exactly the drift we want to *see*, so
    comparison tests should use raw `parse` equality and this only for reporting.
    """
    if isinstance(node, sexpdata.Quoted):
        return normalise(node.value())
    if isinstance(node, sexpdata.Symbol):
        return node.value()
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return [normalise(child) for child in node]
    return node
