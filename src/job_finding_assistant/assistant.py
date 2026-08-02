"""Assistant — the only application surface the UI and tests should call."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime

from job_finding_assistant.candidate_snapshot import CandidateSnapshot
from job_finding_assistant.catalog_store import CatalogStore
from job_finding_assistant.crawl_filters import CrawlFilters
from job_finding_assistant.crawl_pacer import NoOpCrawlPacer
from job_finding_assistant.job_board import AuthLostError, CrawlOutcome, JobListEntry
from job_finding_assistant.ports import (
    CrawlPacer,
    JobBoardSession,
    LlmCvTailor,
    LlmJudge,
    MasterCvStore,
)
from job_finding_assistant.preferences import GapTolerance, LanguagePreference, Preferences

__all__ = [
    "AssessmentSummary",
    "Assistant",
    "CrawlFilters",
    "CrawlOutcome",
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
        crawl_pacer: CrawlPacer | None = None,
    ) -> None:
        self._catalog_store = catalog_store
        self._job_board = job_board
        self._master_cv = master_cv
        self._llm_judge = llm_judge
        self._llm_cv_tailor = llm_cv_tailor
        self._crawl_pacer = crawl_pacer or NoOpCrawlPacer()

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

    def get_crawl_filters(self) -> CrawlFilters:
        """Return Crawl Filters (default Active Job on; Hardline unset)."""
        return self._catalog_store.get_crawl_filters()

    def update_crawl_filters(self, filters: CrawlFilters) -> None:
        """Persist Crawl Filters for the next Crawl."""
        self._catalog_store.save_crawl_filters(filters)

    def start_user_attended_login(self) -> None:
        """Open the Job Board browser; user completes login (including DUO)."""
        self._job_board.open_login()

    def can_start_crawl(self) -> bool:
        """True only after User-Attended Login has left an authenticated session."""
        return self._job_board.is_authenticated()

    def run_crawl(self, *, full_refresh: bool = False) -> CrawlOutcome:
        """Sync Job Board list/detail into the catalog (incremental by default)."""
        if not self._job_board.is_authenticated():
            return CrawlOutcome(status="not_authenticated", stored_count=0)

        filters = self.get_crawl_filters()
        try:
            list_entries = self._job_board.discover_job_list(filters)
        except AuthLostError:
            return CrawlOutcome(status="partial_success", stored_count=0)

        stored_count = 0
        seen_ids = {entry.id for entry in list_entries}
        try:
            for entry in list_entries:
                if _excluded_by_deadline_hardline(entry, filters.deadline_hardline):
                    continue
                fingerprint = _list_fingerprint(entry)
                existing = self._catalog_store.get_job_posting(entry.id)
                if (
                    not full_refresh
                    and existing is not None
                    and existing.get("list_fingerprint") == fingerprint
                ):
                    # Present on the list again → Open even when detail fetch is skipped.
                    if existing.get("listing_status") != "Open":
                        self._catalog_store.set_listing_status(entry.id, "Open")
                    continue
                self._crawl_pacer.pause_before_detail()
                detail = self._job_board.fetch_job_detail(entry.id)
                self._catalog_store.upsert_job_posting(
                    job_posting_id=detail.id,
                    title=detail.title,
                    employer=detail.employer,
                    listing_status="Open",
                    deadline_status=_deadline_status(detail.application_deadline),
                    posting_date=detail.posting_date,
                    application_deadline=detail.application_deadline,
                    detail_json=json.dumps(detail.fields),
                    list_fingerprint=fingerprint,
                )
                stored_count += 1
        except AuthLostError:
            return CrawlOutcome(status="partial_success", stored_count=stored_count)

        if filters.is_closing_capable():
            self._catalog_store.mark_missing_open_postings_closed(seen_ids)
        return CrawlOutcome(status="completed", stored_count=stored_count)


def _list_fingerprint(entry: JobListEntry) -> str:
    return "|".join(
        [
            entry.id,
            entry.title,
            entry.employer,
            entry.posting_date or "",
            entry.application_deadline or "",
        ]
    )


def _excluded_by_deadline_hardline(
    entry: JobListEntry,
    hardline: date | None,
) -> bool:
    if hardline is None or not entry.application_deadline:
        return False
    try:
        deadline = date.fromisoformat(entry.application_deadline)
    except ValueError:
        return False
    return deadline < hardline


def _deadline_status(application_deadline: str | None, *, today: date | None = None) -> str:
    if not application_deadline:
        return "Unknown"
    try:
        deadline = date.fromisoformat(application_deadline)
    except ValueError:
        return "Unknown"
    current = today or datetime.now(tz=UTC).date()
    if deadline < current:
        return "Passed"
    return "Upcoming"
