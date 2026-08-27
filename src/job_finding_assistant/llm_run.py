"""Process-local Assessment Summary LLM Run orchestration.

Catalog assess and Bulk Prepare are internal engines behind start / stop / status.
Callers (Assistant) supply product work via ``LlmRunPorts``; this module does not
import Assistant. ``PendingClaimQueue`` stays the catalog-assess claim seam.
"""

from __future__ import annotations

import threading
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Literal, Protocol

from job_finding_assistant.catalog_assess import PendingClaimQueue, load_max_concurrency

__all__ = [
    "BulkPrepareResult",
    "LlmRunAlreadyInFlight",
    "LlmRunPosting",
    "LlmRunStatus",
]


class LlmRunAlreadyInFlight(Exception):
    """At most one Assessment Summary LLM Run may be active."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class BulkPrepareResult:
    """Outcome of a Bulk Prepare run (prepared / skipped / failed / stopped)."""

    prepared: list[str]
    skipped: list[str]
    failed: list[tuple[str, str]]
    stopped: list[str]
    message: str | None = None


@dataclass(frozen=True)
class LlmRunPosting:
    """One Job Posting identity currently in flight in an LLM Run."""

    job_posting_id: str
    title: str
    employer: str


@dataclass(frozen=True)
class LlmRunStatus:
    """Process-local Assessment Summary LLM Run activity (poll + Stop).

    Judging can hold several postings at once: ``in_flight`` lists them all and
    ``current_index`` counts only postings that fully finished. Preparing keeps one
    identity in ``job_posting_id`` / ``title`` / ``employer``, counts the in-flight
    posting toward ``current_index``, and leaves ``in_flight`` empty.
    """

    active: bool
    phase: Literal["Judging", "Preparing"] | None = None
    job_posting_id: str | None = None
    title: str | None = None
    employer: str | None = None
    current_index: int | None = None
    total: int | None = None
    stop_requested: bool = False
    message: str | None = None
    bulk_prepare_result: BulkPrepareResult | None = None
    in_flight: tuple[LlmRunPosting, ...] = ()


@dataclass(frozen=True)
class PrepareOneOutcome:
    """One Bulk Prepare attempt as seen by the LLM Run engine."""

    status: Literal["prepared", "failed", "unavailable"]
    reason: str = ""


class LlmRunPorts(Protocol):
    """Product work the LLM Run engines call; implemented by Assistant."""

    def list_pending_ids(self) -> list[str]:
        """Return current Pending Job Posting ids."""

    def assess(self, job_id: str) -> Literal["saved", "skipped", "llm_failed"]:
        """Judge one Pending Job Posting."""

    def prepare_one(self, job_id: str) -> PrepareOneOutcome:
        """Prepare one eligible Job Posting."""

    def refresh_candidate_files(self) -> bool:
        """Run the candidate-file freshness gate; True if assessments were cleared."""

    def posting_identity(self, job_id: str) -> LlmRunPosting:
        """Title and employer for an in-flight Job Posting."""

    def clear_all_match_assessments(self) -> None:
        """Pending-all after a fingerprint change mid catalog assess."""

    def clear_judge_error(self) -> None:
        """Drop a cached LLM Unavailable reason after a successful save in this run."""


@dataclass
class _LlmRunState:
    """Mutable process-local LLM Run fields guarded by LlmRun._lock."""

    active: bool = False
    phase: Literal["Judging", "Preparing"] | None = None
    job_posting_id: str | None = None
    title: str | None = None
    employer: str | None = None
    current_index: int | None = None
    total: int | None = None
    stop_requested: bool = False
    message: str | None = None
    bulk_prepare_result: BulkPrepareResult | None = None
    in_flight: tuple[LlmRunPosting, ...] = ()
    # Highest queue revision already published; older snapshots are dropped so a
    # slow claimant cannot overwrite a fresher in-flight list.
    published_revision: int = 0


@dataclass
class _CatalogAssessRun:
    """How one catalog assess run went, shared by its claimants.

    The flags only ever move to True and are read once every claimant has finished,
    so they need no lock of their own; ``lock`` serializes the candidate-file
    freshness check so only one claimant can clear assessments.
    """

    saved_any: bool = False
    files_changed: bool = False
    llm_unavailable: bool = False
    lock: threading.Lock = field(default_factory=threading.Lock)


class LlmRun:
    """One-in-flight LLM Run: catalog assess and Bulk Prepare engines + status."""

    def __init__(self, ports: LlmRunPorts) -> None:
        self._ports = ports
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._state = _LlmRunState()

    def status(self) -> LlmRunStatus:
        """Return process-local Assessment Summary LLM Run status for poll UI."""
        with self._lock:
            state = self._state
            return LlmRunStatus(
                active=state.active,
                phase=state.phase,
                job_posting_id=state.job_posting_id,
                title=state.title,
                employer=state.employer,
                current_index=state.current_index,
                total=state.total,
                stop_requested=state.stop_requested,
                message=state.message,
                bulk_prepare_result=state.bulk_prepare_result,
                in_flight=state.in_flight,
            )

    def request_stop(self) -> LlmRunStatus:
        """Request cooperative abort of the in-flight LLM Run."""
        with self._lock:
            if self._state.active:
                self._stop.set()
                self._state.stop_requested = True
        return self.status()

    def record_inactive(
        self,
        *,
        message: str | None,
        bulk_prepare_result: BulkPrepareResult | None = None,
    ) -> LlmRunStatus:
        """Publish an idle status without starting a thread (empty Bulk Prepare)."""
        with self._lock:
            self._state = _LlmRunState(
                active=False,
                message=message,
                bulk_prepare_result=bulk_prepare_result,
            )
        return self.status()

    def start_catalog_assess(self) -> LlmRunStatus:
        """Start an until-empty catalog assess LLM Run."""
        pending_count = len(self._ports.list_pending_ids())
        with self._lock:
            if self._state.active:
                phase = self._state.phase or "Judging"
                raise LlmRunAlreadyInFlight(
                    f"Already {phase.lower()}… stop or wait for the current LLM Run."
                )
            self._stop.clear()
            self._state = _LlmRunState(
                active=True,
                phase="Judging",
                current_index=None,
                total=pending_count or None,
                message=None,
            )
            thread = threading.Thread(
                target=self._run_catalog_assess,
                name="catalog-assess-llm-run",
                daemon=True,
            )
            self._thread = thread
            thread.start()
        return self.status()

    def start_bulk_prepare(
        self, *, eligible: list[str], skipped: list[str]
    ) -> LlmRunStatus:
        """Start a sequential Bulk Prepare LLM Run for already-confirmed ids."""
        with self._lock:
            if self._state.active:
                phase = self._state.phase or "Preparing"
                raise LlmRunAlreadyInFlight(
                    f"Already {phase.lower()}… stop or wait for the current LLM Run."
                )
            self._stop.clear()
            self._state = _LlmRunState(
                active=True,
                phase="Preparing",
                current_index=None,
                total=len(eligible) or None,
                message=None,
            )
            thread = threading.Thread(
                target=self._run_bulk_prepare,
                kwargs={
                    "eligible": list(eligible),
                    "skipped": list(skipped),
                },
                name="bulk-prepare-llm-run",
                daemon=True,
            )
            self._thread = thread
            thread.start()
        return self.status()

    def _run_catalog_assess(self) -> None:
        queue = PendingClaimQueue(self._ports.list_pending_ids)
        run = _CatalogAssessRun()
        try:
            concurrency = load_max_concurrency()
            with ThreadPoolExecutor(
                max_workers=concurrency, thread_name_prefix="catalog-assess"
            ) as pool:
                claimants: list[Future[None]] = [
                    pool.submit(self._claim_and_judge_pending, queue, run)
                    for _ in range(concurrency)
                ]
            # Every in-flight call has finished by now (cooperative Stop / early stop).
            for claimant in claimants:
                claimant.result()
            if run.saved_any and not run.llm_unavailable:
                # A concurrent success must not erase the reason another call hit.
                self._ports.clear_judge_error()
            processed = queue.finished
            files_changed = run.files_changed
            if files_changed:
                # Calls still in flight when the files changed judged against the old
                # Master CV / constraint files and saved after the Pending reset.
                self._ports.clear_all_match_assessments()
                message = (
                    f"Candidate files changed after {processed} Pending "
                    f"{'attempt' if processed == 1 else 'attempts'}; "
                    f"start again to continue."
                )
            elif self._stop.is_set():
                message = (
                    f"Stopped after {processed} Pending "
                    f"{'attempt' if processed == 1 else 'attempts'}."
                )
            elif processed == 0:
                message = "No Pending Job Postings to assess."
            else:
                remaining = len(self._ports.list_pending_ids())
                message = (
                    f"Assessed {processed} Pending "
                    f"{'attempt' if processed == 1 else 'attempts'}; "
                    f"{remaining} still Pending."
                )
            self._finish(message=message)
        except Exception as exc:  # noqa: BLE001 — defensive; never leave the run hung
            self._finish(message=f"LLM Run failed: {exc}")

    def _claim_and_judge_pending(
        self, queue: PendingClaimQueue, run: _CatalogAssessRun
    ) -> None:
        """Judge claimed Pending postings until this run has no more work.

        One of these runs per configured concurrency. Stop, a candidate-file change,
        and LLM Unavailable all end the run cooperatively: the call already in flight
        finishes and applies its normal rules, and no further id is claimed.
        """
        while self._catalog_assess_may_claim(queue, run):
            job_id = queue.claim()
            if job_id is None:
                return
            self._publish_catalog_assess_status(queue)
            outcome: Literal["saved", "skipped", "llm_failed"] | None = None
            try:
                outcome = self._ports.assess(job_id)
                if outcome == "saved":
                    run.saved_any = True
                elif outcome == "llm_failed":
                    run.llm_unavailable = True
                    queue.halt()
            finally:
                if outcome is None:
                    # Unexpected failure: end the run rather than judge on.
                    queue.halt()
                queue.release(job_id, deferred=outcome != "saved")
                self._publish_catalog_assess_status(queue)

    def _catalog_assess_may_claim(
        self, queue: PendingClaimQueue, run: _CatalogAssessRun
    ) -> bool:
        """Stop claiming on Stop or once candidate files changed under this run."""
        if self._stop.is_set():
            return False
        with run.lock:
            if run.files_changed:
                return False
            # The run's own start already refreshed, so only check between postings.
            if queue.finished > 0 and self._ports.refresh_candidate_files():
                run.files_changed = True
                queue.halt()
                with self._lock:
                    if self._state.active:
                        self._stop.set()
                        self._state.stop_requested = True
                return False
        return True

    def _publish_catalog_assess_status(self, queue: PendingClaimQueue) -> None:
        progress = queue.progress()
        in_flight = tuple(
            self._ports.posting_identity(job_id) for job_id in progress.in_flight
        )
        total = progress.finished + len(self._ports.list_pending_ids())
        with self._lock:
            state = self._state
            if not state.active or progress.revision <= state.published_revision:
                return
            leader = in_flight[0] if in_flight else None
            state.published_revision = progress.revision
            state.phase = "Judging"
            state.in_flight = in_flight
            state.job_posting_id = leader.job_posting_id if leader else None
            state.title = leader.title if leader else None
            state.employer = leader.employer if leader else None
            state.current_index = progress.finished
            state.total = total

    def _run_bulk_prepare(self, *, eligible: list[str], skipped: list[str]) -> None:
        prepared: list[str] = []
        failed: list[tuple[str, str]] = []
        stopped: list[str] = []
        try:
            for index, job_id in enumerate(eligible):
                if self._stop.is_set():
                    stopped.extend(eligible[index:])
                    break
                self._set_preparing_current(
                    job_posting_id=job_id,
                    current_index=index + 1,
                    total=len(eligible),
                )
                outcome = self._ports.prepare_one(job_id)
                if outcome.status == "unavailable":
                    failed.append((job_id, outcome.reason))
                    stopped.extend(eligible[index + 1 :])
                    break
                if outcome.status == "failed":
                    failed.append((job_id, outcome.reason))
                    continue
                prepared.append(job_id)
            result = BulkPrepareResult(
                prepared=prepared,
                skipped=skipped,
                failed=failed,
                stopped=stopped,
            )
            message = (
                f"Bulk Prepare: prepared {len(prepared)}; "
                f"skipped {len(skipped)}; failed {len(failed)}; "
                f"stopped {len(stopped)}."
            )
            if self._stop.is_set() and not failed:
                message = (
                    f"Stopped Bulk Prepare after {len(prepared)} prepared; "
                    f"{len(stopped)} not started."
                )
            self._finish(message=message, bulk_prepare_result=result)
        except Exception as exc:  # noqa: BLE001 — defensive; never leave the run hung
            self._finish(message=f"LLM Run failed: {exc}")

    def _set_preparing_current(
        self,
        *,
        job_posting_id: str,
        current_index: int,
        total: int,
    ) -> None:
        posting = self._ports.posting_identity(job_posting_id)
        with self._lock:
            self._state.phase = "Preparing"
            self._state.job_posting_id = posting.job_posting_id
            self._state.title = posting.title
            self._state.employer = posting.employer
            self._state.current_index = current_index
            self._state.total = total

    def _finish(
        self,
        *,
        message: str | None,
        bulk_prepare_result: BulkPrepareResult | None = None,
    ) -> None:
        with self._lock:
            self._state.active = False
            self._state.phase = None
            self._state.job_posting_id = None
            self._state.title = None
            self._state.employer = None
            self._state.current_index = None
            self._state.total = None
            self._state.in_flight = ()
            self._state.message = message
            self._state.bulk_prepare_result = bulk_prepare_result
            # Keep stop_requested visible briefly only while active; clear when done.
            self._state.stop_requested = False
            self._thread = None
