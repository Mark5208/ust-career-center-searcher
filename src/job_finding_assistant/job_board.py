"""Job Board port types shared by Assistant and adapters."""

from __future__ import annotations

from dataclasses import dataclass, field


class AuthLostError(Exception):
    """Raised when the Job Board session loses authentication mid-Crawl."""


@dataclass(frozen=True)
class JobListEntry:
    """One row from Job Board list discovery."""

    id: str
    title: str
    employer: str
    posting_date: str | None = None
    application_deadline: str | None = None


@dataclass(frozen=True)
class JobPostingDetail:
    """Detail-page facts for one Job Posting (structured fields + Evidence text)."""

    id: str
    title: str
    employer: str
    posting_date: str | None = None
    application_deadline: str | None = None
    fields: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CrawlOutcome:
    """Result of a user-started Crawl."""

    status: str  # completed | partial_success | not_authenticated
    stored_count: int = 0
