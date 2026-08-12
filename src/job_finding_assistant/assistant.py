"""Assistant — the only application surface the UI and tests should call."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

from job_finding_assistant.candidate_snapshot import CandidateSnapshot
from job_finding_assistant.catalog_store import CatalogStore, JobPosting
from job_finding_assistant.constraint_files import fingerprint_path
from job_finding_assistant.crawl_filters import CrawlFilters
from job_finding_assistant.enrichment import (
    DIMENSION_PROMPTS,
    ENRICHMENT_DIMENSIONS,
    EnrichmentConflictError,
    EnrichmentError,
    EnrichmentSessionView,
    PlacementSuggestion,
    atomic_write_text,
    existing_highlights,
    patch_master_cv_entry,
)
from job_finding_assistant.job_board import AuthLostError, CrawlOutcome, JobListEntry
from job_finding_assistant.llm_runtime import LlmUnavailableError
from job_finding_assistant.match_assessment import MatchAssessment
from job_finding_assistant.packet_store import PacketStore
from job_finding_assistant.pdf_renderer import PdfRenderError, RenderCvPdfRenderer
from job_finding_assistant.ports import (
    ConstraintFilesStore,
    JobBoardSession,
    LlmCvEnricher,
    LlmCvTailor,
    LlmJudge,
    MasterCvStore,
    PdfRenderer,
)
from job_finding_assistant.preparation_packet import PreparationPacket


__all__ = [
    "AssessmentSummary",
    "AssessmentSummaryCatalog",
    "AssessmentSummaryCatalogRow",
    "Assistant",
    "BulkDeleteConfirmItem",
    "BulkDeleteNeedsConfirm",
    "BulkDeleteResult",
    "BulkPrepareConfirmItem",
    "BulkPrepareNeedsConfirm",
    "BulkPrepareResult",
    "CandidateFilesView",
    "CrawlFilters",
    "CrawlOutcome",
    "DeleteNeedsConfirm",
    "EnrichmentConflictError",
    "EnrichmentError",
    "EnrichmentSessionView",
    "MatchAssessmentPage",
    "PlacementSuggestion",
    "PreparationPacketPage",
    "PreparationPacketView",
    "PrepareBlockedError",
    "PrepareFailedError",
    "PrepareNeedsConfirm",
]


class PrepareBlockedError(Exception):
    """Prepare is unavailable (Pending Match Assessment)."""


class PrepareNeedsConfirm(Exception):
    """Prepare requires an explicit confirm before running."""

    def __init__(self, kind: Literal["hard_constraint_fail", "overwrite"], reason: str) -> None:
        super().__init__(reason)
        self.kind = kind
        self.reason = reason


class PrepareFailedError(Exception):
    """Tailor/LLM failed mid-run; prior packet (if any) was left untouched."""


class DeleteNeedsConfirm(Exception):
    """Delete requires an explicit confirm before hard-removing artifacts."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class BulkPrepareConfirmItem:
    """One eligible posting that needs Hard Constraint fail or overwrite confirm."""

    job_posting_id: str
    title: str
    employer: str
    kind: Literal["hard_constraint_fail", "overwrite"]
    reason: str


class BulkPrepareNeedsConfirm(Exception):
    """Bulk Prepare needs one combined confirm before running the eligible set."""

    def __init__(
        self,
        items: list[BulkPrepareConfirmItem],
        *,
        selected_ids: list[str],
        eligible_ids: list[str],
        skipped_ids: list[str],
    ) -> None:
        super().__init__("Bulk Prepare needs confirm")
        self.items = list(items)
        self.selected_ids = list(selected_ids)
        self.eligible_ids = list(eligible_ids)
        self.skipped_ids = list(skipped_ids)


@dataclass(frozen=True)
class BulkPrepareResult:
    """Outcome of a Bulk Prepare run (prepared / skipped / failed / stopped)."""

    prepared: list[str]
    skipped: list[str]
    failed: list[tuple[str, str]]
    stopped: list[str]
    message: str | None = None


@dataclass(frozen=True)
class BulkDeleteConfirmItem:
    """One selected posting listed on the Bulk Delete confirm page."""

    job_posting_id: str
    title: str
    employer: str
    has_match_assessment: bool
    has_preparation_packet: bool


class BulkDeleteNeedsConfirm(Exception):
    """Bulk Delete needs one confirm listing every selected posting."""

    def __init__(self, items: list[BulkDeleteConfirmItem]) -> None:
        super().__init__("Bulk Delete needs confirm")
        self.items = list(items)


@dataclass(frozen=True)
class BulkDeleteResult:
    """Outcome of a Bulk Delete run."""

    deleted: list[str]
    message: str | None = None


@dataclass(frozen=True)
class PreparationPacketView:
    """Packet artifacts plus the current Match Assessment (not frozen into the packet)."""

    packet: PreparationPacket
    match_assessment: MatchAssessment | None


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


@dataclass(frozen=True)
class MatchAssessmentPage:
    """Match Assessment detail page payload (no opportunistic rejudge)."""

    summary: AssessmentSummary
    match_assessment: MatchAssessment | None
    can_prepare: bool
    llm_unavailable_reason: str | None


@dataclass(frozen=True)
class PreparationPacketPage:
    """Preparation Packet page payload with posting title/employer."""

    title: str
    employer: str
    packet: PreparationPacket
    match_assessment: MatchAssessment | None


@dataclass(frozen=True)
class AssessmentSummaryCatalogRow:
    """One Assessment Summary row for the catalog, with Prepare availability."""

    summary: AssessmentSummary
    can_prepare: bool


@dataclass(frozen=True)
class AssessmentSummaryCatalog:
    """Catalog page payload: rows, Pending rejudge progress, LLM Unavailable."""

    rows: list[AssessmentSummaryCatalogRow]
    processed_this_load: int
    pending_remaining: int
    llm_unavailable_reason: str | None


@dataclass(frozen=True)
class CandidateFilesView:
    """Read model for Master CV / Hard Constraints / Preferences paths + Snapshot."""

    master_cv_path: str | None
    hard_constraints_path: str | None
    preferences_path: str | None
    snapshot: CandidateSnapshot | None
    errors: list[str]


@dataclass
class _EnrichmentSession:
    """Process-local Master CV Enrichment state (ephemeral; not durable)."""

    master_path: str
    session_fingerprint: str
    step: str = "freeform"
    freeform: str = ""
    placement: PlacementSuggestion | None = None
    dimension_index: int = 0
    dimension_answers: dict[str, str] | None = None
    followup_prompt: str | None = None
    highlights: list[str] | None = None
    llm_unavailable_reason: str | None = None
    error: str | None = None

    def __post_init__(self) -> None:
        if self.dimension_answers is None:
            self.dimension_answers = {}


# Assessment Summary GET / may process this many Pending heads per catalog load.
_CATALOG_REJUDGE_BUDGET = 5


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
        packet_store_dir: Path | None = None,
        pdf_renderer: PdfRenderer | None = None,
        llm_cv_enricher: LlmCvEnricher | None = None,
    ) -> None:
        self._catalog_store = catalog_store
        self._job_board = job_board
        self._master_cv = master_cv
        self._llm_judge = llm_judge
        self._llm_cv_tailor = llm_cv_tailor
        self._llm_cv_enricher = llm_cv_enricher
        self._constraint_files = constraint_files
        self._candidate_file_errors: list[str] = []
        self._llm_call_error: str | None = None
        # Process-local: after llm_failed/skipped, do not retry the same Pending head
        # until every other Pending id has been attempted (avoids HOL starvation).
        self._rejudge_skip_ids: set[str] = set()
        store_root = packet_store_dir or catalog_store.db_path.parent / "packets"
        self._packet_store = PacketStore(store_root)
        self._pdf_renderer: PdfRenderer = pdf_renderer or RenderCvPdfRenderer()
        self._enrichment: _EnrichmentSession | None = None

    def list_assessment_summaries(
        self,
        *,
        include_closed: bool = False,
        include_passed_deadlines: bool = False,
    ) -> list[AssessmentSummary]:
        """Return Assessment Summaries with default filter/sort (glossary)."""
        self._refresh_candidate_file_state()
        return self._list_assessment_summaries_after_refresh(
            include_closed=include_closed,
            include_passed_deadlines=include_passed_deadlines,
        )

    def load_assessment_summary_catalog(
        self,
        *,
        include_closed: bool = False,
        include_passed_deadlines: bool = False,
    ) -> AssessmentSummaryCatalog:
        """Load Assessment Summary catalog: one refresh, up to five Pending rejudges, rows + progress.

        Intended for GET / only. Match Assessment detail must not call this (no queue advance).
        On LLM Unavailable for an attempt, stop further attempts for this load (early-stop).
        """
        self._refresh_candidate_file_state()
        processed = self._rejudge_pending_after_refresh(budget=_CATALOG_REJUDGE_BUDGET)
        summaries = self._list_assessment_summaries_after_refresh(
            include_closed=include_closed,
            include_passed_deadlines=include_passed_deadlines,
        )
        pending_remaining = len(self._catalog_store.list_pending_job_posting_ids())
        rows = [
            AssessmentSummaryCatalogRow(
                summary=summary,
                can_prepare=self.can_prepare(summary.job_posting_id),
            )
            for summary in summaries
        ]
        return AssessmentSummaryCatalog(
            rows=rows,
            processed_this_load=processed,
            pending_remaining=pending_remaining,
            llm_unavailable_reason=self.get_llm_unavailable_reason(),
        )

    def can_prepare(self, job_posting_id: str) -> bool:
        """Prepare is unavailable only while Pending (Hard Constraint fail does not block)."""
        return self._catalog_store.get_match_assessment(job_posting_id) is not None

    def get_match_assessment(self, job_posting_id: str) -> MatchAssessment | None:
        """Return the Match Assessment detail, or None when Pending."""
        self._refresh_candidate_file_state()
        return self._catalog_store.get_match_assessment(job_posting_id)

    def load_match_assessment_page(
        self, job_posting_id: str
    ) -> MatchAssessmentPage | None:
        """Load Match Assessment detail page (no opportunistic rejudge).

        Returns None when the Job Posting is unknown. Catalog load remains the
        batch rejudge entry for Assessment Summary.
        """
        self._refresh_candidate_file_state()
        summary: AssessmentSummary | None = None
        for row in self._list_assessment_summaries_after_refresh(
            include_closed=True, include_passed_deadlines=True
        ):
            if row.job_posting_id == job_posting_id:
                summary = row
                break
        if summary is None:
            return None
        return MatchAssessmentPage(
            summary=summary,
            match_assessment=self._catalog_store.get_match_assessment(job_posting_id),
            can_prepare=self.can_prepare(job_posting_id),
            llm_unavailable_reason=self.get_llm_unavailable_reason(),
        )

    def prepare(
        self,
        job_posting_id: str,
        *,
        confirm_hard_constraint_fail: bool = False,
        confirm_overwrite: bool = False,
    ) -> PreparationPacket:
        """Build or overwrite the Preparation Packet for one Job Posting.

        Raises PrepareBlockedError while Pending, PrepareNeedsConfirm for HC fail /
        re-Prepare overwrite, and PrepareFailedError when the tailor fails mid-run
        (prior packet left untouched). PDF-only failure still persists the packet.
        """
        self._refresh_candidate_file_state()
        assessment = self._catalog_store.get_match_assessment(job_posting_id)
        if assessment is None:
            raise PrepareBlockedError(
                "Prepare unavailable while Match Assessment is Pending"
            )

        existing = self._packet_store.get(job_posting_id)
        if existing is not None and not confirm_overwrite:
            raise PrepareNeedsConfirm(
                "overwrite",
                "Re-Prepare will overwrite the current Preparation Packet",
            )
        if (
            assessment.hard_constraint_outcome == "fail"
            and not confirm_hard_constraint_fail
        ):
            raise PrepareNeedsConfirm(
                "hard_constraint_fail",
                assessment.hard_constraint_reason,
            )

        if not self._llm_cv_tailor.available():
            reason = self._llm_cv_tailor.unavailable_reason()
            self._llm_call_error = reason
            raise PrepareFailedError(reason if reason is not None else "LLM Unavailable")

        snapshot = self._master_cv.candidate_snapshot()
        if snapshot is None:
            raise PrepareFailedError(
                "Master CV / Candidate Snapshot is required to Prepare"
            )

        master_path = self._master_cv.master_cv_path()
        if not master_path:
            raise PrepareFailedError("Master CV path is not set")
        try:
            master_cv_yaml = Path(master_path).read_text(encoding="utf-8")
        except OSError as exc:
            raise PrepareFailedError(f"Master CV unreadable: {exc}") from exc

        posting = self._catalog_store.get_job_posting(job_posting_id)
        if posting is None or not posting.has_detail():
            raise PrepareFailedError("Job Posting detail is missing")

        try:
            tailor_result = self._llm_cv_tailor.tailor(
                master_cv_yaml=master_cv_yaml,
                candidate_snapshot=snapshot,
                job_detail_fields=posting.fields_for_llm(),
                relevance_evidence=list(assessment.evidence),
                hard_constraint_outcome=assessment.hard_constraint_outcome,
                hard_constraint_reason=assessment.hard_constraint_reason,
            )
        except LlmUnavailableError as exc:
            self._llm_call_error = exc.reason
            raise PrepareFailedError(exc.reason) from exc
        self._llm_call_error = None

        pdf_bytes: bytes | None
        try:
            pdf_bytes = self._pdf_renderer.render_pdf(tailor_result.tailored_yaml)
        except PdfRenderError:
            pdf_bytes = None

        return self._packet_store.save(
            job_posting_id,
            gap_report=tailor_result.gap_report,
            edit_summary=tailor_result.edit_summary,
            tailored_yaml=tailor_result.tailored_yaml,
            pdf_bytes=pdf_bytes,
            stale=False,
        )

    def get_preparation_packet(self, job_posting_id: str) -> PreparationPacketView | None:
        """Return the Preparation Packet with the current Match Assessment, if any."""
        self._refresh_candidate_file_state()
        packet = self._packet_store.get(job_posting_id)
        if packet is None:
            return None
        return PreparationPacketView(
            packet=packet,
            match_assessment=self._catalog_store.get_match_assessment(job_posting_id),
        )

    def load_preparation_packet_page(
        self, job_posting_id: str
    ) -> PreparationPacketPage | None:
        """Load Preparation Packet page with title/employer (no opportunistic rejudge).

        Returns None when no Preparation Packet exists.
        """
        view = self.get_preparation_packet(job_posting_id)
        if view is None:
            return None
        posting = self._catalog_store.get_job_posting(job_posting_id)
        title = posting.title if posting is not None else job_posting_id
        employer = posting.employer if posting is not None else ""
        return PreparationPacketPage(
            title=title,
            employer=employer,
            packet=view.packet,
            match_assessment=view.match_assessment,
        )

    def get_tailored_yaml(self, job_posting_id: str) -> str | None:
        """Return Tailored CV YAML for download, or None when no packet."""
        packet = self._packet_store.get(job_posting_id)
        return packet.tailored_yaml if packet is not None else None

    def get_tailored_pdf(self, job_posting_id: str) -> bytes | None:
        """Return Tailored PDF bytes for download, or None when missing."""
        packet = self._packet_store.get(job_posting_id)
        if packet is None:
            return None
        return packet.pdf_bytes

    def delete(self, job_posting_id: str, *, confirm: bool = False) -> None:
        """Hard-remove a Job Posting, its Match Assessment, and Preparation Packet.

        Always requires confirm. The confirm reason names the Job Posting, Match
        Assessment, and Preparation Packet (if any). No trash or undo.
        """
        posting = self._catalog_store.get_job_posting(job_posting_id)
        if posting is None:
            return
        title = posting.title or job_posting_id
        employer = posting.employer or ""
        has_packet = self._packet_store.get(job_posting_id) is not None
        if not confirm:
            parts = [f"Job Posting '{title} — {employer}'", "Match Assessment"]
            if has_packet:
                parts.append("Preparation Packet")
            named = ", ".join(parts[:-1]) + f", and {parts[-1]}"
            raise DeleteNeedsConfirm(
                f"Delete permanently removes {named}. No undo."
            )
        self._packet_store.delete(job_posting_id)
        self._catalog_store.delete_job_posting(job_posting_id)

    def bulk_prepare(
        self,
        job_posting_ids: list[str],
        *,
        confirm: bool = False,
    ) -> BulkPrepareResult:
        """Prepare every selected posting that can Prepare (ADR-0013 Bulk Prepare).

        Skips Pending / not-ready rows. Raises BulkPrepareNeedsConfirm when any
        eligible posting needs Hard Constraint fail or overwrite confirm, unless
        ``confirm`` is True. Runs sequentially; stops remaining on LLM Unavailable;
        continues after other Prepare failures.
        """
        selected = list(job_posting_ids)
        if not selected:
            return BulkPrepareResult(
                prepared=[],
                skipped=[],
                failed=[],
                stopped=[],
                message="No Job Postings selected for Bulk Prepare.",
            )

        self._refresh_candidate_file_state()
        eligible: list[str] = []
        skipped: list[str] = []
        for job_id in selected:
            if self.can_prepare(job_id):
                eligible.append(job_id)
            else:
                skipped.append(job_id)

        if not confirm:
            confirm_items = self._bulk_prepare_confirm_items(eligible)
            if confirm_items:
                raise BulkPrepareNeedsConfirm(
                    confirm_items,
                    selected_ids=selected,
                    eligible_ids=eligible,
                    skipped_ids=skipped,
                )

        prepared: list[str] = []
        failed: list[tuple[str, str]] = []
        stopped: list[str] = []
        for index, job_id in enumerate(eligible):
            try:
                self.prepare(
                    job_id,
                    confirm_hard_constraint_fail=True,
                    confirm_overwrite=True,
                )
            except PrepareFailedError as exc:
                if self._is_llm_unavailable_prepare_failure(exc):
                    failed.append((job_id, str(exc)))
                    stopped.extend(eligible[index + 1 :])
                    break
                failed.append((job_id, str(exc)))
                continue
            prepared.append(job_id)
        return BulkPrepareResult(
            prepared=prepared,
            skipped=skipped,
            failed=failed,
            stopped=stopped,
        )

    def _bulk_prepare_confirm_items(
        self, eligible_ids: list[str]
    ) -> list[BulkPrepareConfirmItem]:
        items: list[BulkPrepareConfirmItem] = []
        for job_id in eligible_ids:
            posting = self._catalog_store.get_job_posting(job_id)
            title = posting.title if posting is not None else job_id
            employer = posting.employer if posting is not None else ""
            assessment = self._catalog_store.get_match_assessment(job_id)
            if assessment is None:
                continue
            if self._packet_store.get(job_id) is not None:
                items.append(
                    BulkPrepareConfirmItem(
                        job_posting_id=job_id,
                        title=title,
                        employer=employer,
                        kind="overwrite",
                        reason="Re-Prepare will overwrite the current Preparation Packet",
                    )
                )
            if assessment.hard_constraint_outcome == "fail":
                items.append(
                    BulkPrepareConfirmItem(
                        job_posting_id=job_id,
                        title=title,
                        employer=employer,
                        kind="hard_constraint_fail",
                        reason=assessment.hard_constraint_reason,
                    )
                )
        return items

    def _is_llm_unavailable_prepare_failure(self, exc: PrepareFailedError) -> bool:
        if isinstance(exc.__cause__, LlmUnavailableError):
            return True
        if not self._llm_cv_tailor.available():
            return True
        reason = self.get_llm_unavailable_reason()
        return reason is not None and str(exc) == reason

    def bulk_delete(
        self,
        job_posting_ids: list[str],
        *,
        confirm: bool = False,
    ) -> BulkDeleteResult:
        """Hard-delete every selected posting after one combined confirm (ADR-0013)."""
        selected = list(job_posting_ids)
        if not selected:
            return BulkDeleteResult(
                deleted=[],
                message="No Job Postings selected for Bulk Delete.",
            )

        items: list[BulkDeleteConfirmItem] = []
        for job_id in selected:
            posting = self._catalog_store.get_job_posting(job_id)
            if posting is None:
                continue
            items.append(
                BulkDeleteConfirmItem(
                    job_posting_id=job_id,
                    title=posting.title or job_id,
                    employer=posting.employer or "",
                    has_match_assessment=(
                        self._catalog_store.get_match_assessment(job_id) is not None
                    ),
                    has_preparation_packet=self._packet_store.get(job_id) is not None,
                )
            )
        if not items:
            return BulkDeleteResult(
                deleted=[],
                message="No Job Postings selected for Bulk Delete.",
            )
        if not confirm:
            raise BulkDeleteNeedsConfirm(items)

        deleted: list[str] = []
        for item in items:
            self.delete(item.job_posting_id, confirm=True)
            deleted.append(item.job_posting_id)
        return BulkDeleteResult(deleted=deleted)

    def set_master_cv_path(self, path: str) -> None:
        """Point at a Master CV RenderCV YAML file; never overwrites that file."""
        self._master_cv.set_master_cv_path(path)
        self._refresh_candidate_file_state()

    def get_candidate_files(self) -> CandidateFilesView:
        """Return paths, Candidate Snapshot, and path/read errors for candidate files."""
        self._refresh_candidate_file_state()
        return CandidateFilesView(
            master_cv_path=self._master_cv.master_cv_path(),
            hard_constraints_path=self._constraint_files.hard_constraints_path(),
            preferences_path=self._constraint_files.preferences_path(),
            snapshot=self._master_cv.candidate_snapshot(),
            errors=list(self._candidate_file_errors),
        )

    def set_hard_constraints_path(self, path: str) -> None:
        """Point at a Hard Constraints plain-text file; never overwrites that file."""
        self._constraint_files.set_hard_constraints_path(path)
        self._refresh_candidate_file_state()

    def clear_hard_constraints_path(self) -> None:
        """Clear the Hard Constraints path (counts as a candidate-file change)."""
        self._constraint_files.clear_hard_constraints_path()
        self._refresh_candidate_file_state()

    def set_preferences_path(self, path: str) -> None:
        """Point at a Preferences plain-text file; never overwrites that file."""
        self._constraint_files.set_preferences_path(path)
        self._refresh_candidate_file_state()

    def clear_preferences_path(self) -> None:
        """Clear the Preferences path (counts as a candidate-file change)."""
        self._constraint_files.clear_preferences_path()
        self._refresh_candidate_file_state()

    def get_enrichment_session(self) -> EnrichmentSessionView | None:
        """Return the ephemeral Enrichment session view, if any."""
        if self._enrichment is None:
            return None
        return self._enrichment_view()

    def start_enrichment_session(self) -> EnrichmentSessionView:
        """Begin a new Master CV Enrichment session (discards any prior ephemeral state)."""
        self._refresh_candidate_file_state()
        master_path = self._master_cv.master_cv_path()
        if not master_path:
            raise EnrichmentError("Master CV path is not set")
        if self._master_cv.candidate_snapshot() is None:
            raise EnrichmentError("Master CV / Candidate Snapshot is required")
        session_fp = fingerprint_path(master_path)
        if session_fp is None:
            raise EnrichmentError("Master CV is unreadable")
        self._enrichment = _EnrichmentSession(
            master_path=master_path,
            session_fingerprint=session_fp,
        )
        return self._enrichment_view()

    def submit_enrichment_freeform(self, description: str) -> EnrichmentSessionView:
        """Accept freeform experience text and ask the enricher for placement."""
        text = description.strip()
        if not text:
            raise EnrichmentError("Freeform description is required")
        if self._enrichment is None or self._enrichment.step == "done":
            self.start_enrichment_session()
        assert self._enrichment is not None
        self._enrichment.freeform = text
        self._enrichment.error = None
        enricher = self._require_enricher()
        if enricher is None:
            self._enrichment.step = "freeform"
            return self._enrichment_view()
        try:
            yaml_text = Path(self._enrichment.master_path).read_text(encoding="utf-8")
            suggestion = enricher.suggest_placement(
                freeform=text, master_cv_yaml=yaml_text
            )
        except LlmUnavailableError as exc:
            self._llm_call_error = exc.reason
            self._enrichment.llm_unavailable_reason = exc.reason
            self._enrichment.step = "freeform"
            return self._enrichment_view()
        self._llm_call_error = None
        self._enrichment.llm_unavailable_reason = None
        self._enrichment.placement = suggestion
        self._enrichment.step = "placement"
        return self._enrichment_view()

    def confirm_enrichment_placement(
        self,
        *,
        company: str | None = None,
        position: str | None = None,
        name: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> EnrichmentSessionView:
        """Confirm LLM placement (and new-entry identity) before dimension steps."""
        session = self._require_enrichment()
        if session.step != "placement" or session.placement is None:
            raise EnrichmentError("Placement is not ready to confirm")
        placement = session.placement
        if placement.mode == "new":
            company = (company if company is not None else placement.company) or ""
            position = (position if position is not None else placement.position) or ""
            name = (name if name is not None else placement.name) or ""
            start_date = (
                start_date if start_date is not None else placement.start_date
            ) or None
            end_date = (end_date if end_date is not None else placement.end_date) or None
            if placement.section == "experience" and (
                not company.strip() or not position.strip()
            ):
                raise EnrichmentError(
                    "New experience entries require company and position"
                )
            if placement.section == "projects" and not name.strip():
                raise EnrichmentError("New project entries require a name")
            if placement.section == "education" and not (
                company.strip() or name.strip()
            ):
                raise EnrichmentError("New education entries require an institution")
            if not (start_date and start_date.strip()) and not (
                end_date and end_date.strip()
            ):
                raise EnrichmentError(
                    "New entries require user-confirmed dates (start and/or end)"
                )
            placement = PlacementSuggestion(
                section=placement.section,
                mode="new",
                company=company.strip() or None,
                position=position.strip() or None,
                name=name.strip() or None,
                start_date=start_date,
                end_date=end_date,
                label=placement.label,
            )
            session.placement = placement
        session.step = "dimension"
        session.dimension_index = 0
        session.followup_prompt = None
        return self._enrichment_view()

    def submit_enrichment_dimension(self, answer: str) -> EnrichmentSessionView:
        """Record an answer for the current dimension; optional clarifying follow-up."""
        session = self._require_enrichment()
        if session.step not in ("dimension", "followup"):
            raise EnrichmentError("No active dimension step")
        assert session.placement is not None
        dimension = ENRICHMENT_DIMENSIONS[session.dimension_index]
        text = answer.strip()
        if session.step == "followup":
            if text:
                prior = session.dimension_answers.get(dimension, "")
                session.dimension_answers[dimension] = (
                    f"{prior}\n{text}".strip() if prior else text
                )
            session.followup_prompt = None
            return self._advance_enrichment_dimension()
        if not text:
            raise EnrichmentError("Dimension answer is required (or skip)")
        session.dimension_answers[dimension] = text
        enricher = self._require_enricher()
        if enricher is None:
            return self._enrichment_view()
        try:
            followup = enricher.clarifying_followup(
                dimension=dimension,
                answer=text,
                freeform=session.freeform,
            )
        except LlmUnavailableError as exc:
            self._llm_call_error = exc.reason
            session.llm_unavailable_reason = exc.reason
            return self._enrichment_view()
        self._llm_call_error = None
        session.llm_unavailable_reason = None
        if followup and followup.strip():
            session.step = "followup"
            session.followup_prompt = followup.strip()
            return self._enrichment_view()
        return self._advance_enrichment_dimension()

    def skip_enrichment_dimension(self) -> EnrichmentSessionView:
        """Skip the current dimension (empty) and advance."""
        session = self._require_enrichment()
        if session.step not in ("dimension", "followup"):
            raise EnrichmentError("No active dimension step")
        session.followup_prompt = None
        return self._advance_enrichment_dimension()

    def set_enrichment_highlights(self, highlights: list[str]) -> EnrichmentSessionView:
        """Replace the editable highlights draft before confirm write."""
        session = self._require_enrichment()
        if session.step != "highlights":
            raise EnrichmentError("Highlights are not ready to edit")
        cleaned = [line.strip() for line in highlights if line.strip()]
        session.highlights = cleaned
        return self._enrichment_view()

    def confirm_enrichment_write(self) -> EnrichmentSessionView:
        """Atomically patch the target Master CV entry; refuse if file changed."""
        session = self._require_enrichment()
        if session.step != "highlights" or session.placement is None:
            raise EnrichmentError("Highlights confirm is not ready")
        if session.highlights is None:
            raise EnrichmentError("Highlights draft is missing")
        current_fp = fingerprint_path(session.master_path)
        if current_fp != session.session_fingerprint:
            self._enrichment = None
            raise EnrichmentConflictError(
                "Master CV changed since Enrichment started; restart Enrichment"
            )
        try:
            original = Path(session.master_path).read_text(encoding="utf-8")
        except OSError as exc:
            raise EnrichmentError(f"Master CV unreadable: {exc}") from exc
        patched = patch_master_cv_entry(
            original,
            placement=session.placement,
            highlights=list(session.highlights),
        )
        atomic_write_text(Path(session.master_path), patched)
        session.step = "done"
        self._enrichment = session
        self._refresh_candidate_file_state()
        return self._enrichment_view()

    def _require_enrichment(self) -> _EnrichmentSession:
        if self._enrichment is None:
            raise EnrichmentError("No Enrichment session")
        return self._enrichment

    def _require_enricher(self) -> LlmCvEnricher | None:
        enricher = self._llm_cv_enricher
        if enricher is None:
            reason = "LLM Unavailable: enricher not configured"
            if self._enrichment is not None:
                self._enrichment.llm_unavailable_reason = reason
            self._llm_call_error = reason
            return None
        if not enricher.available():
            reason = enricher.unavailable_reason() or "LLM Unavailable"
            if self._enrichment is not None:
                self._enrichment.llm_unavailable_reason = reason
            self._llm_call_error = reason
            return None
        return enricher

    def _advance_enrichment_dimension(self) -> EnrichmentSessionView:
        session = self._require_enrichment()
        session.dimension_index += 1
        if session.dimension_index >= len(ENRICHMENT_DIMENSIONS):
            return self._draft_enrichment_highlights()
        session.step = "dimension"
        session.followup_prompt = None
        return self._enrichment_view()

    def _draft_enrichment_highlights(self) -> EnrichmentSessionView:
        session = self._require_enrichment()
        assert session.placement is not None
        enricher = self._require_enricher()
        if enricher is None:
            session.step = "dimension"
            session.dimension_index = len(ENRICHMENT_DIMENSIONS) - 1
            return self._enrichment_view()
        try:
            yaml_text = Path(session.master_path).read_text(encoding="utf-8")
            kept: list[str] = []
            if (
                session.placement.mode == "existing"
                and session.placement.entry_index is not None
            ):
                kept = existing_highlights(
                    yaml_text,
                    section=session.placement.section,
                    entry_index=session.placement.entry_index,
                )
            drafted = enricher.draft_highlights(
                freeform=session.freeform,
                placement=session.placement,
                dimension_answers=dict(session.dimension_answers),
                existing_highlights=kept,
            )
        except LlmUnavailableError as exc:
            self._llm_call_error = exc.reason
            session.llm_unavailable_reason = exc.reason
            session.step = "dimension"
            session.dimension_index = len(ENRICHMENT_DIMENSIONS) - 1
            return self._enrichment_view()
        self._llm_call_error = None
        session.llm_unavailable_reason = None
        session.highlights = [line.strip() for line in drafted if str(line).strip()]
        session.step = "highlights"
        return self._enrichment_view()

    def _enrichment_view(self) -> EnrichmentSessionView:
        session = self._require_enrichment()
        dimension = None
        prompt = None
        if session.step in ("dimension", "followup") and session.dimension_index < len(
            ENRICHMENT_DIMENSIONS
        ):
            dimension = ENRICHMENT_DIMENSIONS[session.dimension_index]
            prompt = DIMENSION_PROMPTS[dimension]
        return EnrichmentSessionView(
            step=session.step,
            freeform=session.freeform,
            placement=session.placement,
            current_dimension=dimension,
            dimension_prompt=prompt,
            followup_prompt=session.followup_prompt,
            dimension_answers=dict(session.dimension_answers),
            highlights=None if session.highlights is None else list(session.highlights),
            llm_unavailable_reason=session.llm_unavailable_reason,
            error=session.error,
        )

    def get_llm_unavailable_reason(self) -> str | None:
        """Pass through adapter preflight reason or last call-failure `.reason`."""
        if not self._llm_judge.available():
            return self._llm_judge.unavailable_reason()
        if not self._llm_cv_tailor.available():
            return self._llm_cv_tailor.unavailable_reason()
        if self._llm_cv_enricher is not None and not self._llm_cv_enricher.available():
            return self._llm_cv_enricher.unavailable_reason()
        return self._llm_call_error

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
        self._refresh_candidate_file_state()
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
                presence = self._catalog_store.apply_crawl_list_presence(
                    entry.id,
                    list_fingerprint=fingerprint,
                    full_refresh=full_refresh,
                )
                if presence == "unchanged":
                    continue
                detail = self._job_board.fetch_job_detail(entry.id)
                self._catalog_store.commit_crawl_detail(
                    JobPosting(
                        id=detail.id,
                        title=detail.title,
                        employer=detail.employer,
                        listing_status="Open",
                        deadline_status=_deadline_status(detail.application_deadline),
                        posting_date=detail.posting_date,
                        application_deadline=detail.application_deadline,
                        detail_fields=dict(detail.fields),
                        list_fingerprint=fingerprint,
                    )
                )
                stored_count += 1
        except AuthLostError:
            return CrawlOutcome(status="partial_success", stored_count=stored_count)

        if filters.is_closing_capable():
            self._catalog_store.mark_missing_open_postings_closed(seen_ids)
        return CrawlOutcome(status="completed", stored_count=stored_count)

    def rejudge_pending_assessments(self) -> int:
        """Opportunistically judge Pending Match Assessments (after Crawl / file change).

        Budgets at most one Pending Job Posting per call so Crawl / file-change paths
        are not stacked with a five-call batch (ADR-0015). Refresh again to continue.

        When a posting fails or is skipped, it is deferred for this process so later
        Pending ids can still advance; after a full pass the deferred heads are retried.

        Returns 1 if a Pending posting was processed (budget used), else 0.
        Prefer ``load_assessment_summary_catalog`` for the Assessment Summary page.
        """
        self._refresh_candidate_file_state()
        return self._rejudge_pending_after_refresh(budget=1)

    def _rejudge_pending_after_refresh(self, *, budget: int) -> int:
        """Process up to ``budget`` Pending heads sequentially after refresh.

        Each attempt (saved, skipped, or failure) consumes one unit. On LLM Unavailable
        (``llm_failed``), stop further attempts for this call (early-stop).
        """
        processed = 0
        for _ in range(budget):
            outcome = self._rejudge_one_pending_after_refresh()
            if outcome is None:
                break
            processed += 1
            if outcome == "llm_failed":
                break
        return processed

    def _rejudge_one_pending_after_refresh(
        self,
    ) -> Literal["saved", "skipped", "llm_failed"] | None:
        pending = self._catalog_store.list_pending_job_posting_ids()
        if not pending:
            self._rejudge_skip_ids.clear()
            return None
        candidates = [job_id for job_id in pending if job_id not in self._rejudge_skip_ids]
        if not candidates:
            # Full pass completed with failures still Pending — retry from the head.
            self._rejudge_skip_ids.clear()
            candidates = list(pending)
        job_id = candidates[0]
        outcome = self._assess_job_posting(job_id)
        if outcome == "saved":
            self._llm_call_error = None
            self._rejudge_skip_ids.discard(job_id)
        else:
            # llm_failed / skipped: leave Pending, advance past this id next call.
            self._rejudge_skip_ids.add(job_id)
        return outcome

    def _list_assessment_summaries_after_refresh(
        self,
        *,
        include_closed: bool = False,
        include_passed_deadlines: bool = False,
    ) -> list[AssessmentSummary]:
        rows = self._catalog_store.list_assessment_summary_rows()
        packet_flags = self._packet_store.presence_flags(row.id for row in rows)
        summaries: list[AssessmentSummary] = []
        for row in rows:
            presence = packet_flags.get(row.id)
            has_packet = bool(presence and presence.has_preparation_packet)
            summaries.append(
                AssessmentSummary(
                    job_posting_id=row.id,
                    title=row.title,
                    employer=row.employer,
                    listing_status=row.listing_status,
                    deadline_status=row.deadline_status,
                    pending=row.relevance is None,
                    hard_constraint_outcome=row.hard_constraint_outcome,
                    preference=row.preference,
                    relevance=row.relevance,
                    has_preparation_packet=has_packet,
                    preparation_packet_stale=bool(presence and presence.stale),
                    application_deadline=row.application_deadline,
                )
            )
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

    def _refresh_candidate_file_state(self) -> None:
        """Internal freshness gate: Master CV / HC / Preferences content or path-clear.

        On change: rebuild Snapshot (via Master CV store), mark **all** assessments
        Pending, mark Preparation Packets Stale, and record path/read errors.
        Does not auto-rejudge or auto-regenerate packets. Callers use public
        Assistant methods; out-of-band disk edits are observed on the next use.
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
            self._packet_store.mark_all_stale()
            self._rejudge_skip_ids.clear()
        if changed or not had_prior:
            self._catalog_store.save_candidate_fingerprints(**current)

    def _assess_job_posting(
        self, job_posting_id: str
    ) -> Literal["saved", "skipped", "llm_failed"]:
        posting = self._catalog_store.get_job_posting(job_posting_id)
        if posting is None or not posting.has_detail():
            return "skipped"
        job_fields = posting.fields_for_llm()

        snapshot = self._master_cv.candidate_snapshot()
        if snapshot is None:
            # Relevance requires a usable Master CV / Snapshot → stay Pending.
            return "skipped"

        hc_read = self._constraint_files.read_hard_constraints()
        prefs_read = self._constraint_files.read_preferences()

        # Unreadable HC/Prefs → unknown for that signal (not Pending on that alone).
        needs_hc_judge = hc_read.non_empty
        needs_prefs_judge = prefs_read.non_empty
        # Relevance always required when Snapshot exists; HC/Prefs when non-empty.
        if not self._llm_judge.available():
            self._llm_call_error = self._llm_judge.unavailable_reason()
            return "llm_failed"

        try:
            if needs_hc_judge:
                hc = self._llm_judge.judge_hard_constraint(
                    hard_constraints_text=hc_read.text,
                    job_detail_fields=job_fields,
                )
                hc_outcome = hc.outcome
                hc_reason = hc.reason
                hc_evidence = list(hc.evidence)
            elif hc_read.error:
                hc_outcome = "unknown"
                hc_reason = hc_read.error
                hc_evidence = []
            else:
                hc_outcome = "unknown"
                hc_reason = "No Hard Constraints file or file is empty"
                hc_evidence = []

            if needs_prefs_judge:
                pref = self._llm_judge.judge_preference(
                    preferences_text=prefs_read.text,
                    job_detail_fields=job_fields,
                )
                preference = pref.preference
                preference_reason = pref.reason
                preference_evidence = list(pref.evidence)
            elif prefs_read.error:
                preference = None
                preference_reason = prefs_read.error
                preference_evidence = []
            else:
                preference = None
                preference_reason = "No Preferences file or file is empty"
                preference_evidence = []

            relevance_result = self._llm_judge.judge_relevance(
                job_detail_fields=job_fields,
                candidate_snapshot=snapshot,
            )
        except LlmUnavailableError as exc:
            # Judge failure → leave Pending (do not persist a half-assessed row).
            self._llm_call_error = exc.reason
            return "llm_failed"

        assessment = MatchAssessment(
            job_posting_id=job_posting_id,
            hard_constraint_outcome=hc_outcome,
            hard_constraint_reason=hc_reason,
            preference=preference,
            preference_reason=preference_reason,
            relevance=relevance_result.relevance,
            evidence=list(relevance_result.evidence),
            hard_constraint_evidence=hc_evidence,
            preference_evidence=preference_evidence,
        )
        self._catalog_store.save_match_assessment(assessment)
        return "saved"


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
