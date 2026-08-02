"""Preferences — Hard Constraint sidecar inputs (not Crawl Filters)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class GapTolerance(str, Enum):
    """How much study interruption the user will accept."""

    NONE = "None"
    SEMESTER = "Semester"
    YEAR = "Year"
    ANY = "Any"


@dataclass(frozen=True)
class LanguagePreference:
    """A language spoken, with an optional proficiency level."""

    language: str
    level: str | None = None


@dataclass(frozen=True)
class Preferences:
    """Hard Constraint inputs only — empty fields leave related checks unknown later."""

    languages: list[LanguagePreference]
    locations: list[str]
    gap_tolerance: GapTolerance | None = None
