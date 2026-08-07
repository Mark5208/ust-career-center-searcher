"""Hard Constraints and Preferences file path helpers (read-only on disk)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ConstraintFileRead:
    """Result of reading a user-authored constraint/preferences file."""

    path: str | None
    text: str
    """File body when readable; empty when missing path, empty file, or unreadable."""

    fingerprint: str | None
    """Content fingerprint when path is set and file is readable (including empty)."""

    non_empty: bool
    """True only when readable text has non-whitespace content (judge required)."""

    error: str | None
    """Path/read error when path is set but the file is missing or unreadable."""


def fingerprint_text(text: str) -> str:
    """Stable fingerprint for file content (empty string included)."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def fingerprint_path(path: str | None) -> str | None:
    """Fingerprint file contents at path, or None when unset/unreadable."""
    if not path:
        return None
    file_path = Path(path)
    if not file_path.is_file():
        return None
    try:
        return fingerprint_text(file_path.read_text(encoding="utf-8"))
    except OSError:
        return None


def read_constraint_file(path: str | None) -> ConstraintFileRead:
    """Read a Hard Constraints or Preferences file without writing to it."""
    if not path:
        return ConstraintFileRead(
            path=None,
            text="",
            fingerprint=None,
            non_empty=False,
            error=None,
        )
    file_path = Path(path)
    if not file_path.is_file():
        return ConstraintFileRead(
            path=path,
            text="",
            fingerprint=None,
            non_empty=False,
            error=f"File not found: {path}",
        )
    try:
        text = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        return ConstraintFileRead(
            path=path,
            text="",
            fingerprint=None,
            non_empty=False,
            error=f"Unreadable file: {path} ({exc})",
        )
    stripped = text.strip()
    return ConstraintFileRead(
        path=path,
        text=text,
        fingerprint=fingerprint_text(text),
        non_empty=bool(stripped),
        error=None,
    )
