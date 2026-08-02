"""Assistant — the only application surface the UI and tests should call."""

from __future__ import annotations

from dataclasses import dataclass

from job_finding_assistant.candidate_snapshot import CandidateSnapshot
from job_finding_assistant.catalog_store import CatalogStore
from job_finding_assistant.ports import JobBoardSession, LlmCvTailor, LlmJudge, MasterCvStore
from job_finding_assistant.preferences import GapTolerance, LanguagePreference, Preferences

__all__ = [
    "AssessmentSummary",
    "Assistant",
    "GapTolerance",
    "LanguagePreference",
    "Preferences",
]


@dataclass(frozen=True)
class AssessmentSummary:
    """Browse/list view of fit for one Job Posting (Pending when not yet assessed)."""

    job_posting_id: str
    title: str
    employer: str
    listing_status: str
    deadline_status: str
    pending: bool = True


class Assistant:
    """Application API for the Job Finding Assistant.

    Adapters (Job Board, CatalogStore, LLM ports, Master CV) stay behind this seam.
    """

    def __init__(
        self,
        *,
        catalog_store: CatalogStore,
        job_board: JobBoardSession,
        master_cv: MasterCvStore,
        llm_judge: LlmJudge,
        llm_cv_tailor: LlmCvTailor,
    ) -> None:
        self._catalog_store = catalog_store
        self._job_board = job_board
        self._master_cv = master_cv
        self._llm_judge = llm_judge
        self._llm_cv_tailor = llm_cv_tailor

    def list_assessment_summaries(self) -> list[AssessmentSummary]:
        """Return Assessment Summaries for Job Postings in the local catalog."""
        rows = self._catalog_store.list_assessment_summary_rows()
        return [
            AssessmentSummary(
                job_posting_id=row["id"],
                title=row["title"] or "",
                employer=row["employer"] or "",
                listing_status=row["listing_status"] or "Open",
                deadline_status=row["deadline_status"] or "Unknown",
                pending=True,
            )
            for row in rows
        ]

    def set_master_cv_path(self, path: str) -> None:
        """Point at a Master CV LaTeX file; never overwrites that file."""
        self._master_cv.set_master_cv_path(path)

    def get_master_cv_path(self) -> str | None:
        """Return the configured Master CV path, if any."""
        return self._master_cv.master_cv_path()

    def get_candidate_snapshot(self) -> CandidateSnapshot | None:
        """Return the inspectable Candidate Snapshot (not hand-editable)."""
        return self._master_cv.candidate_snapshot()

    def get_preferences(self) -> Preferences:
        """Return persisted Preferences (empty fields leave Hard Constraints unknown later)."""
        return self._catalog_store.get_preferences()

    def update_preferences(self, preferences: Preferences) -> None:
        """Replace Preferences (languages, locations, Gap Tolerance — not Crawl Filters)."""
        self._catalog_store.save_preferences(preferences)
