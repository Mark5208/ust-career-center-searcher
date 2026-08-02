"""Fakeable adapter ports behind Assistant (not the primary test surface)."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class JobBoardSession(Protocol):
    """Playwright-backed Job Board session for User-Attended Login and Crawl."""

    def is_authenticated(self) -> bool:
        """Return whether the Job Board session is ready for a Crawl."""


@runtime_checkable
class MasterCvStore(Protocol):
    """Reads Master CV LaTeX and rebuilds the Candidate Snapshot."""

    def master_cv_path(self) -> str | None:
        """Return the configured Master CV path, if any."""


@runtime_checkable
class LlmJudge(Protocol):
    """LLM port for Relevance and Evidence pairs."""

    def available(self) -> bool:
        """Return whether the judge port can be used."""


@runtime_checkable
class LlmCvTailor(Protocol):
    """LLM port for Gap Report, Tailored CV, and Edit Summary."""

    def available(self) -> bool:
        """Return whether the tailor port can be used."""
