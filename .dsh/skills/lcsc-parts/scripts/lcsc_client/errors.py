"""Typed application errors with user-facing messages.

Every error that can reach the GUI carries a message that is safe to show to a
user.  Technical details are kept separately so the GUI can put them behind a
``Details`` button and the logger can record them.  Errors never carry query
strings, cookies or signed datasheet URLs - the code that raises them must not
put those values into a message.
"""

# Vendored from KiCad LibGen LCSC (KicadLibGui-LCSC 1.0.0) at commit 60c89f8.
# Do not edit: refresh with scripts/refresh_client.py.
from __future__ import annotations


class AppError(Exception):
    """Base class for expected, recoverable application errors."""

    default_message = "Something went wrong."

    def __init__(self, message: str | None = None, *, details: str = "",
                 retry_after: int | None = None) -> None:
        self.message = message or self.default_message
        self.details = details
        self.retry_after = retry_after
        super().__init__(self.message)

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.message


class SearchError(AppError):
    """A product search failed for a reason explained by ``message``."""

    default_message = "The LCSC search failed."


class RateLimitError(SearchError):
    """The store asked us to slow down (HTTP 429)."""

    default_message = "LCSC is rate limiting. Wait a moment and retry."


class ServerError(SearchError):
    """The store answered with a 5xx error."""

    default_message = "LCSC is temporarily unavailable. Retry in a moment."


class NetworkError(SearchError):
    """The store host could not be reached."""

    default_message = "Could not reach LCSC. Check your network or proxy."


class ParseError(SearchError):
    """The store answered with data this program does not understand."""

    default_message = "LCSC returned an unexpected response."


class DetailError(SearchError):
    """A product's detail page could not be read."""

    default_message = "The product details are not available right now."


class DatabaseError(AppError):
    """A database operation failed."""

    default_message = "The database operation failed."


class DatabaseLockedError(DatabaseError):
    """SQLite reported ``database is locked``."""

    default_message = (
        "The database is in use (KiCad or another app). Close it and retry."
    )


class SchemaError(DatabaseError):
    """The chosen file is not a compatible components database."""

    default_message = "This file is not a compatible components database."


class BatchError(AppError):
    """A batch import failed before or during the run."""

    default_message = "The batch import failed."
