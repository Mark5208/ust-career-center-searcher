"""Fakeable adapter ports behind Assistant (not the primary test surface)."""

from typing import Protocol, runtime_checkable

from job_finding_assistant.candidate_snapshot import CandidateSnapshot
from job_finding_assistant.constraint_files import ConstraintFileRead
from job_finding_assistant.crawl_filters import CrawlFilters
from job_finding_assistant.job_board import JobListEntry, JobPostingDetail
from job_finding_assistant.match_assessment import (
    HardConstraintJudgment,
    PreferenceJudgment,
    RelevanceJudgment,
)


@runtime_checkable
class JobBoardSession(Protocol):
    """Playwright-backed Job Board session for User-Attended Login and Crawl."""

    def open_login(self) -> None:
        """Open the browser for User-Attended Login (no passwords stored)."""

    def is_authenticated(self) -> bool:
        """Return whether the Job Board session is ready for a Crawl."""

    def discover_job_list(self, filters: CrawlFilters) -> list[JobListEntry]:
        """Apply Crawl Filters on the board and return list rows (paginated)."""

    def fetch_job_detail(self, job_posting_id: str) -> JobPostingDetail:
        """Fetch one Job Posting detail page for catalog storage."""


@runtime_checkable
class CrawlPacer(Protocol):
    """Time boundary for human-like pauses during Crawl (no real sleep in tests)."""

    def pause_before_detail(self) -> None:
        """Pause before fetching one Job Posting detail page."""

    def pause_before_next_page(self) -> None:
        """Pause before advancing to the next Job Board list page."""


@runtime_checkable
class MasterCvStore(Protocol):
    """Reads Master CV LaTeX and rebuilds the Candidate Snapshot."""

    def master_cv_path(self) -> str | None:
        """Return the configured Master CV path, if any."""

    def set_master_cv_path(self, path: str) -> None:
        """Set the Master CV LaTeX path without modifying that file."""

    def candidate_snapshot(self) -> CandidateSnapshot | None:
        """Return the Candidate Snapshot rebuilt from the Master CV, if any."""


@runtime_checkable
class ConstraintFilesStore(Protocol):
    """Reads Hard Constraints and Preferences file paths (never writes those files)."""

    def hard_constraints_path(self) -> str | None:
        """Return the configured Hard Constraints path, if any."""

    def preferences_path(self) -> str | None:
        """Return the configured Preferences path, if any."""

    def set_hard_constraints_path(self, path: str) -> None:
        """Set the Hard Constraints file path without modifying that file."""

    def clear_hard_constraints_path(self) -> None:
        """Clear the Hard Constraints path."""

    def set_preferences_path(self, path: str) -> None:
        """Set the Preferences file path without modifying that file."""

    def clear_preferences_path(self) -> None:
        """Clear the Preferences path."""

    def read_hard_constraints(self) -> ConstraintFileRead:
        """Read the Hard Constraints file (read-only)."""

    def read_preferences(self) -> ConstraintFileRead:
        """Read the Preferences file (read-only)."""


@runtime_checkable
class LlmJudge(Protocol):
    """LLM port for Hard Constraint, Preference, and Relevance judgments."""

    def available(self) -> bool:
        """Return whether the judge port can be used."""

    def judge_hard_constraint(
        self,
        *,
        hard_constraints_text: str,
        job_detail_fields: dict[str, str],
    ) -> HardConstraintJudgment:
        """Judge Hard Constraints against the Job Posting only (never CV / Preferences)."""

    def judge_preference(
        self,
        *,
        preferences_text: str,
        job_detail_fields: dict[str, str],
    ) -> PreferenceJudgment:
        """Judge Preferences against the Job Posting only (never CV)."""

    def judge_relevance(
        self,
        *,
        job_detail_fields: dict[str, str],
        candidate_snapshot: CandidateSnapshot,
    ) -> RelevanceJudgment:
        """Judge Relevance from Snapshot/CV vs Job Posting only (never Preferences)."""


@runtime_checkable
class LlmCvTailor(Protocol):
    """LLM port for Gap Report, Tailored CV, and Edit Summary."""

    def available(self) -> bool:
        """Return whether the tailor port can be used."""
