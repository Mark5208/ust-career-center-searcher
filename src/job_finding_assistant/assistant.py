"""Assistant — the only application surface the UI and tests should call."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime

from job_finding_assistant.candidate_snapshot import CandidateSnapshot
from job_finding_assistant.catalog_store import CatalogStore
from job_finding_assistant.constraint_files import fingerprint_path
from job_finding_assistant.crawl_filters import CrawlFilters
from job_finding_assistant.crawl_pacer import NoOpCrawlPacer
from job_finding_assistant.job_board import AuthLostError, CrawlOutcome, JobListEntry
from job_finding_assistant.match_assessment import MatchAssessment
from job_finding_assistant.ports import (
    ConstraintFilesStore,
    CrawlPacer,
    JobBoardSession,
    LlmCvTailor,
    LlmJudge,
    MasterCvStore,
)

__all__ = [
    "AssessmentSummary",
    "Assistant",
    "CrawlFilters",
    "CrawlOutcome",
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
    hard_constraint_outcome: str | None = None
    preference: str | None = None
    relevance: str | None = None
    has_preparation_packet: bool = False
    preparation_packet_stale: bool = False
    application_deadline: str | None = None


class Assistant:
    """Application API for the Job Finding Assistant.

    Adapters (Job Board, CatalogStore, LLM ports, Master CV, constraint files) stay
    behind this seam.
    """

    def __init__(
        self,
        *,
        catalog_store: CatalogStore,
        job_board: JobBoardSession,
        master_cv: MasterCvStore,
        llm_judge: LlmJudge,
        llm_cv_tailor: LlmCvTailor,
        constraint_files: ConstraintFilesStore,
        crawl_pacer: CrawlPacer | None = None,
    ) -> None:
        self._catalog_store = catalog_store
        self._job_board = job_board
        self._master_cv = master_cv
        self._llm_judge = llm_judge
        self._llm_cv_tailor = llm_cv_tailor
        self._constraint_files = constraint_files
        self._crawl_pacer = crawl_pacer or NoOpCrawlPacer()
        self._candidate_file_errors: list[str] = []

    def list_assessment_summaries(
        self,
        *,
        include_closed: bool = False,
        include_passed_deadlines: bool = False,
    ) -> list[AssessmentSummary]:
        """Return Assessment Summaries with default filter/sort (glossary)."""
        self.refresh_candidate_file_state()
        summaries = [
            AssessmentSummary(
                job_posting_id=row["id"] or "",
                title=row["title"] or "",
                employer=row["employer"] or "",
                listing_status=row["listing_status"] or "Open",
                deadline_status=row["deadline_status"] or "Unknown",
                pending=row.get("relevance") is None,
                hard_constraint_outcome=row.get("hard_constraint_outcome"),
                preference=row.get("preference"),
                relevance=row.get("relevance"),
                has_preparation_packet=False,
                preparation_packet_stale=False,
                application_deadline=row.get("application_deadline"),
            )
            for row in self._catalog_store.list_assessment_summary_rows()
        ]
        filtered = [
            summary
            for summary in summaries
            if _passes_default_filter(
                summary,
                include_closed=include_closed,
                include_passed_deadlines=include_passed_deadlines,
            )
        ]
        return sorted(filtered, key=_summary_sort_key)

    def can_prepare(self, job_posting_id: str) -> bool:
        """Prepare is unavailable only while Pending (Hard Constraint fail does not block)."""
        return self._catalog_store.get_match_assessment(job_posting_id) is not None

    def get_match_assessment(self, job_posting_id: str) -> MatchAssessment | None:
        """Return the Match Assessment detail, or None when Pending."""
        self.refresh_candidate_file_state()
        return self._catalog_store.get_match_assessment(job_posting_id)

    def set_master_cv_path(self, path: str) -> None:
        """Point at a Master CV LaTeX file; never overwrites that file."""
        self._master_cv.set_master_cv_path(path)
        self.refresh_candidate_file_state()

    def get_master_cv_path(self) -> str | None:
        """Return the configured Master CV path, if any."""
        return self._master_cv.master_cv_path()

    def get_candidate_snapshot(self) -> CandidateSnapshot | None:
        """Return the inspectable Candidate Snapshot (not hand-editable)."""
        return self._master_cv.candidate_snapshot()

    def get_hard_constraints_path(self) -> str | None:
        """Return the configured Hard Constraints file path, if any."""
        return self._constraint_files.hard_constraints_path()

    def set_hard_constraints_path(self, path: str) -> None:
        """Point at a Hard Constraints plain-text file; never overwrites that file."""
        self._constraint_files.set_hard_constraints_path(path)
        self.refresh_candidate_file_state()

    def clear_hard_constraints_path(self) -> None:
        """Clear the Hard Constraints path (counts as a candidate-file change)."""
        self._constraint_files.clear_hard_constraints_path()
        self.refresh_candidate_file_state()

    def get_preferences_path(self) -> str | None:
        """Return the configured Preferences file path, if any."""
        return self._constraint_files.preferences_path()

    def set_preferences_path(self, path: str) -> None:
        """Point at a Preferences plain-text file; never overwrites that file."""
        self._constraint_files.set_preferences_path(path)
        self.refresh_candidate_file_state()

    def clear_preferences_path(self) -> None:
        """Clear the Preferences path (counts as a candidate-file change)."""
        self._constraint_files.clear_preferences_path()
        self.refresh_candidate_file_state()

    def get_candidate_file_errors(self) -> list[str]:
        """Return path/read errors for Master CV / Hard Constraints / Preferences."""
        self.refresh_candidate_file_state()
        return list(self._candidate_file_errors)

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
        """Sync Job Board list/detail into the catalog (incremental by default).

        New or detail-changed postings start Pending. Crawl success means catalog sync
        succeeded, not that Match Assessments finished — call
        ``rejudge_pending_assessments`` afterward (opportunistic).
        """
        self.refresh_candidate_file_state()
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
                # New or detail-changed → Pending; do not assess inside Crawl.
                self._catalog_store.clear_match_assessment(detail.id)
                stored_count += 1
        except AuthLostError:
            return CrawlOutcome(status="partial_success", stored_count=stored_count)

        if filters.is_closing_capable():
            self._catalog_store.mark_missing_open_postings_closed(seen_ids)
        return CrawlOutcome(status="completed", stored_count=stored_count)

    def rejudge_pending_assessments(self) -> None:
        """Opportunistically judge Pending Match Assessments (after Crawl / file change)."""
        self.refresh_candidate_file_state()
        for job_posting_id in self._catalog_store.list_pending_job_posting_ids():
            self._assess_job_posting(job_posting_id)

    def refresh_candidate_file_state(self) -> None:
        """Detect Master CV / HC / Preferences content or path-clear changes.

        On change: rebuild Snapshot (via Master CV store), mark **all** assessments
        Pending, and record path/read errors. Does not auto-rejudge.
        """
        errors: list[str] = []
        master_path = self._master_cv.master_cv_path()
        master_fp = fingerprint_path(master_path)
        snapshot = self._master_cv.candidate_snapshot()
        if master_path and master_fp is None:
            errors.append(f"Master CV unreadable or missing: {master_path}")
        elif master_path and snapshot is None:
            errors.append(f"Master CV invalid or unreadable content: {master_path}")

        hc_read = self._constraint_files.read_hard_constraints()
        prefs_read = self._constraint_files.read_preferences()
        if hc_read.error:
            errors.append(hc_read.error)
        if prefs_read.error:
            errors.append(prefs_read.error)
        self._candidate_file_errors = errors

        current = {
            "master_cv_fingerprint": master_fp,
            "hard_constraints_fingerprint": hc_read.fingerprint,
            "preferences_fingerprint": prefs_read.fingerprint,
        }
        # Path clear: fingerprint becomes None. Treat first-ever None/None as no change
        # only when no prior fingerprints row existed with a non-None value.
        previous = self._catalog_store.get_candidate_fingerprints()
        changed = (
            previous["master_cv_fingerprint"] != current["master_cv_fingerprint"]
            or previous["hard_constraints_fingerprint"]
            != current["hard_constraints_fingerprint"]
            or previous["preferences_fingerprint"] != current["preferences_fingerprint"]
        )
        # Avoid treating initial empty state as a change that clears nothing useful —
        # still update stored fingerprints; only Pending-all when there was a prior
        # non-null fingerprint or a real path/content transition after assessments exist.
        had_prior = any(value is not None for value in previous.values())
        if changed and had_prior:
            self._catalog_store.clear_all_match_assessments()
        if changed or not had_prior:
            self._catalog_store.save_candidate_fingerprints(**current)

    def _assess_job_posting(self, job_posting_id: str) -> None:
        posting = self._catalog_store.get_job_posting(job_posting_id)
        if posting is None or not posting.get("detail_json"):
            return
        detail_fields = json.loads(posting["detail_json"] or "{}")
        title = posting.get("title") or ""
        employer = posting.get("employer") or ""
        job_fields = {
            **detail_fields,
            "title": title,
            "employer": employer,
        }

        snapshot = self.get_candidate_snapshot()
        if snapshot is None:
            # Relevance requires a usable Master CV / Snapshot → stay Pending.
            return

        hc_read = self._constraint_files.read_hard_constraints()
        prefs_read = self._constraint_files.read_preferences()

        # Unreadable HC/Prefs → unknown for that signal (not Pending on that alone).
        needs_hc_judge = hc_read.non_empty
        needs_prefs_judge = prefs_read.non_empty
        # Relevance always required when Snapshot exists; HC/Prefs when non-empty.
        if not self._llm_judge.available():
            return

        try:
            if needs_hc_judge:
                hc = self._llm_judge.judge_hard_constraint(
                    hard_constraints_text=hc_read.text,
                    job_detail_fields=job_fields,
                )
                hc_outcome = hc.outcome
                hc_reason = hc.reason
            elif hc_read.error:
                hc_outcome = "unknown"
                hc_reason = hc_read.error
            else:
                hc_outcome = "unknown"
                hc_reason = "No Hard Constraints file or file is empty"

            if needs_prefs_judge:
                pref = self._llm_judge.judge_preference(
                    preferences_text=prefs_read.text,
                    job_detail_fields=job_fields,
                )
                preference = pref.preference
                preference_reason = pref.reason
            elif prefs_read.error:
                preference = None
                preference_reason = prefs_read.error
            else:
                preference = None
                preference_reason = "No Preferences file or file is empty"

            relevance_result = self._llm_judge.judge_relevance(
                job_detail_fields=job_fields,
                candidate_snapshot=snapshot,
            )
        except Exception:  # noqa: BLE001 — any judge failure leaves Pending
            # Judge failure → leave Pending (do not persist a half-assessed row).
            return

        assessment = MatchAssessment(
            job_posting_id=job_posting_id,
            hard_constraint_outcome=hc_outcome,
            hard_constraint_reason=hc_reason,
            preference=preference,
            preference_reason=preference_reason,
            relevance=relevance_result.relevance,
            evidence=list(relevance_result.evidence),
        )
        self._catalog_store.save_match_assessment(assessment)


def _passes_default_filter(
    summary: AssessmentSummary,
    *,
    include_closed: bool,
    include_passed_deadlines: bool,
) -> bool:
    closed_ok = summary.listing_status != "Closed" or include_closed
    passed_ok = summary.deadline_status != "Passed" or include_passed_deadlines
    return closed_ok and passed_ok


def _summary_sort_key(
    summary: AssessmentSummary,
) -> tuple[int, int, int, int, str, str, str]:
    # Pending last; Hard Constraint fail after pass/unknown;
    # Preference Strong → Mixed → Weak (unknown ties); Relevance Strong → Mixed → Weak;
    # sooner deadline (known Upcoming sooner-first; Deadline Unknown last among ties).
    pending_rank = 1 if summary.pending else 0
    hc_rank = 1 if summary.hard_constraint_outcome == "fail" else 0
    # Unknown Preference ties with other unknowns (does not share Mixed's band).
    preference_rank = {
        "Strong": 0,
        "Mixed": 1,
        "Weak": 2,
        None: 3,
    }.get(summary.preference, 3)
    relevance_rank = {
        "Strong": 0,
        "Mixed": 1,
        "Weak": 2,
        None: 3,
    }.get(summary.relevance, 3)
    if summary.deadline_status == "Unknown":
        deadline_group = "1"
        deadline_key = "9999-99-99"
    else:
        deadline_group = "0"
        deadline_key = summary.application_deadline or "9999-99-99"
    return (
        pending_rank,
        hc_rank,
        preference_rank,
        relevance_rank,
        deadline_group,
        deadline_key,
        summary.job_posting_id,
    )


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
