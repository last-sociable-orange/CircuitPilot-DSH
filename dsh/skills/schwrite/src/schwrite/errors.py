"""Exception types.

Every failure carries enough context for an agent to act on it without reading source:
the reference, the file, the reason. `build` turns any of these into exit code 3 (or 2 for
a netlist mismatch) and still writes its report (S8).
"""

from __future__ import annotations


class SchwriteError(Exception):
    """Base class: something the caller can fix by changing input or arguments."""


class NetlistError(SchwriteError):
    """The netlist JSON is structurally unusable (§Appendix A)."""


class PartError(SchwriteError):
    """A part cannot be placed: not in the database, no such symbol, pin unknown."""

    def __init__(self, reference: str, reason: str) -> None:
        super().__init__(f"{reference}: {reason}")
        self.reference = reference
        self.reason = reason


class DbError(SchwriteError):
    """The database library is missing, unreadable or inconsistent."""


class EmitError(SchwriteError):
    """The page could not be rendered or written."""


class VerifyError(SchwriteError):
    """A gate could not be run or a gate failed."""
