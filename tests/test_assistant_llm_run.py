"""Assistant seam: Assessment Summary LLM Run (catalog assess + Bulk Prepare)."""

from __future__ import annotations

import threading
import time
from pathlib import Path

import pytest

from job_finding_assistant.assistant import (
    Assistant,
    BulkPrepareNeedsConfirm,
    LlmRunAlreadyInFlight,
    LlmRunStatus,
)
from job_finding_assistant.catalog_assess import (
    ENV_MAX_CONCURRENCY,
    load_max_concurrency,
)
from job_finding_assistant.catalog_store import CatalogStore, JobPosting
from job_finding_assistant.fakes import (
    FakeConstraintFilesStore,
    FakeJobBoardSession,
    FakeLlmCvTailor,
    FakeLlmJudge,
    FakeMasterCvStore,
    FakePdfRenderer,
)
from job_finding_assistant.job_board import JobListEntry, JobPostingDetail
from job_finding_assistant.llm_runtime import LlmUnavailableError
from job_finding_assistant.preparation_packet import (
    EditSummary,
    GapReport,
    TailorResult,
)

_SAMPLE_CV = """\
cv:
  name: Test Candidate
  sections:
    experience:
      - company: Example
        position: Platform engineer
        highlights:
          - Built Python services
"""


@pytest.fixture(autouse=True)
def _unset_catalog_assess_concurrency(monkeypatch: pytest.MonkeyPatch) -> None:
    """Start every test from the unset default so a shell env var cannot skew runs."""
    monkeypatch.delenv(ENV_MAX_CONCURRENCY, raising=False)


def _write_cv(tmp_path: Path, name: str = "master_CV.yaml", body: str = _SAMPLE_CV) -> Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


def _open_posting(
    *,
    job_id: str,
    title: str,
    employer: str = "Example Corp",
) -> tuple[JobListEntry, JobPostingDetail]:
    entry = JobListEntry(
        id=job_id,
        title=title,
        employer=employer,
        posting_date="2026-07-01",
        application_deadline="2026-12-31",
    )
    detail = JobPostingDetail(
        id=job_id,
        title=title,
        employer=employer,
        posting_date="2026-07-01",
        application_deadline="2026-12-31",
        fields={
            "Job Description": "Build reliable systems in Python.",
            "Work Location": "Hong Kong",
        },
    )
    return entry, detail


def _assistant(
    tmp_path: Path,
    *,
    entries: list[tuple[JobListEntry, JobPostingDetail]],
    llm_judge: FakeLlmJudge | None = None,
    llm_cv_tailor: FakeLlmCvTailor | None = None,
    rejudge_count: int = 0,
    with_master_cv: bool = True,
) -> tuple[Assistant, FakeLlmJudge, FakeLlmCvTailor]:
    list_entries = [entry for entry, _ in entries]
    details = {detail.id: detail for _, detail in entries}
    job_board = FakeJobBoardSession(
        authenticated=True,
        list_entries=list_entries,
        details=details,
    )
    judge = llm_judge or FakeLlmJudge(relevance="Strong")
    tailor = llm_cv_tailor or FakeLlmCvTailor(
        result=TailorResult(
            gap_report=GapReport(),
            edit_summary=EditSummary(),
            tailored_yaml=_SAMPLE_CV,
        )
    )
    assistant = Assistant(
        catalog_store=CatalogStore(tmp_path / "catalog.db"),
        job_board=job_board,
        master_cv=FakeMasterCvStore(),
        llm_judge=judge,
        llm_cv_tailor=tailor,
        constraint_files=FakeConstraintFilesStore(),
        packet_store_dir=tmp_path / "packets",
        pdf_renderer=FakePdfRenderer(pdf_bytes=b"%PDF-1.4 fake"),
    )
    if with_master_cv:
        assistant.set_master_cv_path(str(_write_cv(tmp_path)))
    assistant.run_crawl()
    for _ in range(rejudge_count):
        assistant.rejudge_pending_assessments()
    return assistant, judge, tailor


def _wait_llm_run_idle(assistant: Assistant, *, timeout: float = 5.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = assistant.get_llm_run_status()
        if not status.active:
            return status
        time.sleep(0.01)
    raise TimeoutError("LLM Run did not finish")


def _wait_for_in_flight(
    assistant: Assistant, *, count: int, timeout: float = 5.0
) -> LlmRunStatus:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = assistant.get_llm_run_status()
        if len(status.in_flight) == count:
            return status
        time.sleep(0.01)
    raise TimeoutError(f"LLM Run never reported {count} in-flight Job Postings")


class _BlockingRelevanceJudge(FakeLlmJudge):
    """Blocks inside Relevance so Stop / single-flight can be observed mid-call."""

    def __init__(self) -> None:
        super().__init__(relevance="Strong")
        self.entered = threading.Event()
        self.release = threading.Event()

    def judge_relevance(self, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        self.entered.set()
        assert self.release.wait(timeout=5), "release not signaled"
        return super().judge_relevance(*args, **kwargs)


class _PeakConcurrencyJudge(FakeLlmJudge):
    """Records the highest number of judge calls that overlapped inside the judge.

    With ``rendezvous`` set, each call also waits for that many calls to be inside at
    once: a run that judges fewer postings at a time breaks the barrier instead of
    quietly passing, so overlap is proven rather than inferred from timing.
    """

    def __init__(
        self,
        *,
        overlap_delay: float = 0.0,
        rendezvous: int | None = None,
    ) -> None:
        super().__init__(relevance="Strong")
        self._overlap_delay = overlap_delay
        self._barrier = threading.Barrier(rendezvous) if rendezvous else None
        self._counter_lock = threading.Lock()
        self._in_call = 0
        self.max_concurrent = 0

    def judge_relevance(self, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        with self._counter_lock:
            self._in_call += 1
            self.max_concurrent = max(self.max_concurrent, self._in_call)
        try:
            if self._barrier is not None:
                self._barrier.wait(timeout=5)
            if self._overlap_delay:
                time.sleep(self._overlap_delay)
        finally:
            with self._counter_lock:
                self._in_call -= 1
        return super().judge_relevance(*args, **kwargs)


class _UnavailableWhileOthersInFlightJudge(FakeLlmJudge):
    """Raises LLM Unavailable for one posting while the other in-flight calls run."""

    def __init__(self, *, fail_title: str, in_flight: int) -> None:
        super().__init__(relevance="Strong")
        self._fail_title = fail_title
        self._all_in_flight = threading.Barrier(in_flight)
        self.failed = threading.Event()

    def judge_relevance(self, *args: object, **kwargs: object):  # type: ignore[no-untyped-def]
        fields = kwargs["job_detail_fields"]
        assert isinstance(fields, dict)
        title = str(fields.get("title", ""))
        self._all_in_flight.wait(timeout=5)
        if title == self._fail_title:
            self.failed.set()
            raise LlmUnavailableError("Fake judge failed")
        assert self.failed.wait(timeout=5), "failure not signaled"
        return super().judge_relevance(*args, **kwargs)


class _BlockingCvTailor(FakeLlmCvTailor):
    """Blocks inside tailor so Bulk Prepare's in-flight status can be observed."""

    def __init__(self) -> None:
        super().__init__(
            result=TailorResult(
                gap_report=GapReport(),
                edit_summary=EditSummary(),
                tailored_yaml=_SAMPLE_CV,
            )
        )
        self.entered = threading.Event()
        self.release = threading.Event()
        self._counter_lock = threading.Lock()
        self._in_call = 0
        self.max_concurrent = 0

    def tailor(self, **kwargs: object):  # type: ignore[no-untyped-def, override]
        with self._counter_lock:
            self._in_call += 1
            self.max_concurrent = max(self.max_concurrent, self._in_call)
        self.entered.set()
        try:
            assert self.release.wait(timeout=5), "release not signaled"
        finally:
            with self._counter_lock:
                self._in_call -= 1
        return super().tailor(**kwargs)  # type: ignore[arg-type]


def test_start_catalog_assess_llm_run_drains_until_pending_empty(
    tmp_path: Path,
) -> None:
    entries = [
        _open_posting(job_id=str(86534 + i), title=f"Engineer {i}", employer=f"E{i}")
        for i in range(6)
    ]
    assistant, judge, _ = _assistant(tmp_path, entries=entries)

    status = assistant.start_catalog_assess_llm_run()
    assert status.active
    assert status.phase == "Judging"
    finished = _wait_llm_run_idle(assistant)

    assert not finished.active
    assert judge.judge_calls == 6
    catalog = assistant.load_assessment_summary_catalog()
    assert catalog.pending_remaining == 0
    assert all(not row.summary.pending for row in catalog.rows)
    assert finished.message is not None
    assert "6" in finished.message
    assert "0 still Pending" in finished.message or "none left" in finished.message.lower()


def test_catalog_assess_llm_run_early_stops_on_llm_unavailable(tmp_path: Path) -> None:
    entries = [
        _open_posting(job_id=str(86534 + i), title=f"Engineer {i}", employer=f"E{i}")
        for i in range(3)
    ]
    judge = FakeLlmJudge(available=False)
    assistant, judge, _ = _assistant(tmp_path, entries=entries, llm_judge=judge)

    assistant.start_catalog_assess_llm_run()
    finished = _wait_llm_run_idle(assistant)

    assert not finished.active
    assert judge.judge_calls == 0
    assert assistant.get_llm_unavailable_reason() == "LLM Unavailable: Fake judge disabled"
    assert assistant.load_assessment_summary_catalog().pending_remaining == 3


def test_second_llm_run_start_refused_while_active(tmp_path: Path) -> None:
    entries = [_open_posting(job_id="86534", title="Engineer A")]
    judge = _BlockingRelevanceJudge()
    assistant, _, _ = _assistant(tmp_path, entries=entries, llm_judge=judge)

    assistant.start_catalog_assess_llm_run()
    assert judge.entered.wait(timeout=5)

    with pytest.raises(LlmRunAlreadyInFlight) as pending:
        assistant.start_catalog_assess_llm_run()
    assert "already" in str(pending.value).lower()

    judge.release.set()
    _wait_llm_run_idle(assistant)


def test_stop_llm_run_finishes_current_and_does_not_start_next(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ENV_MAX_CONCURRENCY, "1")
    entries = [
        _open_posting(job_id="86534", title="Engineer A"),
        _open_posting(job_id="86535", title="Engineer B", employer="Other"),
    ]
    judge = _BlockingRelevanceJudge()
    assistant, _, _ = _assistant(tmp_path, entries=entries, llm_judge=judge)

    assistant.start_catalog_assess_llm_run()
    assert judge.entered.wait(timeout=5)
    stopped = assistant.stop_llm_run()
    assert stopped.active
    assert stopped.stop_requested

    judge.release.set()
    finished = _wait_llm_run_idle(assistant)

    assert not finished.active
    assert judge.judge_calls == 1
    assert assistant.load_assessment_summary_catalog().pending_remaining == 1
    assert finished.message is not None
    assert "Stopped" in finished.message


def test_catalog_assess_llm_run_aborts_when_candidate_files_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ENV_MAX_CONCURRENCY, "1")
    entries = [
        _open_posting(job_id="86534", title="Engineer A"),
        _open_posting(job_id="86535", title="Engineer B", employer="Other"),
        _open_posting(job_id="86536", title="Engineer C", employer="Third"),
    ]
    judge = _BlockingRelevanceJudge()
    assistant, _, _ = _assistant(tmp_path, entries=entries, llm_judge=judge)
    cv_path = tmp_path / "master_CV.yaml"

    assistant.start_catalog_assess_llm_run()
    assert judge.entered.wait(timeout=5)
    cv_path.write_text(
        _SAMPLE_CV.replace("Platform engineer", "Staff platform engineer"),
        encoding="utf-8",
    )
    judge.release.set()
    finished = _wait_llm_run_idle(assistant)

    assert not finished.active
    assert judge.judge_calls == 1
    assert assistant.load_assessment_summary_catalog().pending_remaining > 0
    assert finished.message is not None
    assert "files changed" in finished.message.lower()
    assert "start again" in finished.message.lower()
    assert not assistant.get_llm_run_status().active


def test_catalog_assess_llm_run_keeps_no_assessment_saved_after_files_change(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ENV_MAX_CONCURRENCY, "2")
    entries = [
        _open_posting(job_id="86534", title="Engineer A"),
        _open_posting(job_id="86535", title="Engineer B", employer="Other"),
        _open_posting(job_id="86536", title="Engineer C", employer="Third"),
    ]
    judge = _BlockingRelevanceJudge()
    assistant, _, _ = _assistant(tmp_path, entries=entries, llm_judge=judge)
    cv_path = tmp_path / "master_CV.yaml"

    assistant.start_catalog_assess_llm_run()
    _wait_for_in_flight(assistant, count=2)
    cv_path.write_text(
        _SAMPLE_CV.replace("Platform engineer", "Staff platform engineer"),
        encoding="utf-8",
    )
    judge.release.set()
    finished = _wait_llm_run_idle(assistant)

    # Both in-flight judgments were made against the old Master CV: none may survive
    # the Pending reset, whichever side of it they were saved on.
    assert assistant.load_assessment_summary_catalog().pending_remaining == 3
    assert finished.message is not None
    assert "files changed" in finished.message.lower()


def test_catalog_assess_llm_run_judges_pending_added_mid_run(
    tmp_path: Path,
) -> None:
    entries = [
        _open_posting(job_id="86534", title="Engineer A"),
        _open_posting(job_id="86535", title="Engineer B", employer="Other"),
    ]
    judge = _BlockingRelevanceJudge()
    assistant, _, _ = _assistant(tmp_path, entries=entries, llm_judge=judge)

    assistant.start_catalog_assess_llm_run()
    assert judge.entered.wait(timeout=5)
    assistant._catalog_store.commit_crawl_detail(
        JobPosting(
            id="86599",
            title="Engineer Joined",
            employer="Crawl Corp",
            listing_status="Open",
            deadline_status="Upcoming",
            posting_date="2026-07-01",
            application_deadline="2026-12-31",
            detail_fields={
                "Job Description": "Build reliable systems in Python.",
                "Work Location": "Hong Kong",
            },
            list_fingerprint="joined-mid-run",
        )
    )
    judge.release.set()
    finished = _wait_llm_run_idle(assistant)

    assert not finished.active
    assert judge.judge_calls == 3
    catalog = assistant.load_assessment_summary_catalog()
    assert catalog.pending_remaining == 0
    assert {row.summary.job_posting_id for row in catalog.rows} >= {
        "86534",
        "86535",
        "86599",
    }
    assert all(not row.summary.pending for row in catalog.rows)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (None, 3),
        ("", 3),
        ("   ", 3),
        ("three", 3),
        ("2.5", 3),
        ("1", 1),
        ("7", 7),
        ("0", 1),
        ("-4", 1),
        ("99", 10),
    ],
)
def test_catalog_assess_max_concurrency_defaults_clamps_and_falls_back(
    raw: str | None, expected: int
) -> None:
    environ = {} if raw is None else {ENV_MAX_CONCURRENCY: raw}

    assert load_max_concurrency(environ) == expected


def test_catalog_assess_llm_run_judges_several_postings_at_once(tmp_path: Path) -> None:
    entries = [
        _open_posting(job_id=str(86534 + i), title=f"Engineer {i}", employer=f"E{i}")
        for i in range(6)
    ]
    judge = _PeakConcurrencyJudge(rendezvous=3)
    assistant, _, _ = _assistant(tmp_path, entries=entries, llm_judge=judge)

    assistant.start_catalog_assess_llm_run()
    finished = _wait_llm_run_idle(assistant, timeout=10)

    assert not finished.active
    assert judge.max_concurrent == 3
    assert judge.judge_calls == 6
    assert assistant.load_assessment_summary_catalog().pending_remaining == 0


def test_catalog_assess_llm_run_with_concurrency_one_judges_one_at_a_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ENV_MAX_CONCURRENCY, "1")
    entries = [
        _open_posting(job_id=str(86534 + i), title=f"Engineer {i}", employer=f"E{i}")
        for i in range(4)
    ]
    judge = _PeakConcurrencyJudge(overlap_delay=0.02)
    assistant, _, _ = _assistant(tmp_path, entries=entries, llm_judge=judge)

    assistant.start_catalog_assess_llm_run()
    finished = _wait_llm_run_idle(assistant, timeout=10)

    assert judge.max_concurrent == 1
    assert judge.judge_calls == 4
    assert assistant.load_assessment_summary_catalog().pending_remaining == 0
    assert finished.message == "Assessed 4 Pending attempts; 0 still Pending."


def test_catalog_assess_llm_run_status_lists_in_flight_and_counts_only_finished(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ENV_MAX_CONCURRENCY, "2")
    entries = [
        _open_posting(job_id="86534", title="Engineer A"),
        _open_posting(job_id="86535", title="Engineer B", employer="Other"),
        _open_posting(job_id="86536", title="Engineer C", employer="Third"),
    ]
    judge = _BlockingRelevanceJudge()
    assistant, _, _ = _assistant(tmp_path, entries=entries, llm_judge=judge)

    assistant.start_catalog_assess_llm_run()
    status = _wait_for_in_flight(assistant, count=2)

    assert status.phase == "Judging"
    assert [posting.job_posting_id for posting in status.in_flight] == ["86534", "86535"]
    assert [posting.title for posting in status.in_flight] == ["Engineer A", "Engineer B"]
    assert [posting.employer for posting in status.in_flight] == ["Example Corp", "Other"]
    # k counts fully finished postings only — never one still in flight.
    assert status.current_index == 0
    assert status.total == 3

    judge.release.set()
    finished = _wait_llm_run_idle(assistant)

    assert finished.in_flight == ()
    assert judge.judge_calls == 3
    assert assistant.load_assessment_summary_catalog().pending_remaining == 0


def test_stop_llm_run_waits_for_every_in_flight_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ENV_MAX_CONCURRENCY, "3")
    entries = [
        _open_posting(job_id=str(86534 + i), title=f"Engineer {i}", employer=f"E{i}")
        for i in range(5)
    ]
    judge = _BlockingRelevanceJudge()
    assistant, _, _ = _assistant(tmp_path, entries=entries, llm_judge=judge)

    assistant.start_catalog_assess_llm_run()
    _wait_for_in_flight(assistant, count=3)
    stopped = assistant.stop_llm_run()
    assert stopped.active
    assert stopped.stop_requested

    judge.release.set()
    finished = _wait_llm_run_idle(assistant)

    assert judge.judge_calls == 3
    for i in range(3):
        page = assistant.load_match_assessment_page(str(86534 + i))
        assert page is not None
        assert page.match_assessment is not None
    assert assistant.load_assessment_summary_catalog().pending_remaining == 2
    assert finished.message == "Stopped after 3 Pending attempts."


def test_catalog_assess_llm_run_early_stops_whole_run_when_one_call_is_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ENV_MAX_CONCURRENCY, "3")
    entries = [
        _open_posting(job_id=str(86534 + i), title=f"Engineer {i}", employer=f"E{i}")
        for i in range(6)
    ]
    judge = _UnavailableWhileOthersInFlightJudge(fail_title="Engineer 0", in_flight=3)
    assistant, _, _ = _assistant(tmp_path, entries=entries, llm_judge=judge)

    assistant.start_catalog_assess_llm_run()
    finished = _wait_llm_run_idle(assistant, timeout=10)

    assert not finished.active
    assert judge.failed.is_set()
    # The two calls in flight alongside the failure still finished and saved.
    saved_a = assistant.load_match_assessment_page("86535")
    saved_b = assistant.load_match_assessment_page("86536")
    failed = assistant.load_match_assessment_page("86534")
    assert saved_a is not None and saved_a.match_assessment is not None
    assert saved_b is not None and saved_b.match_assessment is not None
    assert failed is not None and failed.match_assessment is None
    assert assistant.load_assessment_summary_catalog().pending_remaining == 4
    assert assistant.get_llm_unavailable_reason() == "LLM Unavailable: Fake judge failed"


def test_catalog_assess_llm_run_saves_concurrent_judgments_without_lock_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ENV_MAX_CONCURRENCY, "10")
    entries = [
        _open_posting(job_id=str(86534 + i), title=f"Engineer {i}", employer=f"E{i}")
        for i in range(12)
    ]
    judge = _PeakConcurrencyJudge(overlap_delay=0.01)
    assistant, _, _ = _assistant(tmp_path, entries=entries, llm_judge=judge)

    assistant.start_catalog_assess_llm_run()
    finished = _wait_llm_run_idle(assistant, timeout=15)

    assert judge.max_concurrent > 1
    assert judge.judge_calls == 12
    assert assistant.load_assessment_summary_catalog().pending_remaining == 0
    assert finished.message == "Assessed 12 Pending attempts; 0 still Pending."


def test_catalog_assess_llm_run_ends_when_every_pending_posting_is_skipped(
    tmp_path: Path,
) -> None:
    entries = [
        _open_posting(job_id=str(86534 + i), title=f"Engineer {i}", employer=f"E{i}")
        for i in range(4)
    ]
    # No Master CV means no Candidate Snapshot: every Pending posting skips.
    assistant, judge, _ = _assistant(tmp_path, entries=entries, with_master_cv=False)

    assistant.start_catalog_assess_llm_run()
    finished = _wait_llm_run_idle(assistant, timeout=10)

    assert not finished.active
    assert judge.judge_calls == 0
    assert assistant.load_assessment_summary_catalog().pending_remaining == 4
    assert finished.message is not None
    assert "4 still Pending" in finished.message


def test_rejudge_pending_assessments_stays_one_and_is_not_llm_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(ENV_MAX_CONCURRENCY, "10")
    entries = [
        _open_posting(job_id="86534", title="Engineer A"),
        _open_posting(job_id="86535", title="Engineer B", employer="Other"),
    ]
    assistant, judge, _ = _assistant(tmp_path, entries=entries)

    processed = assistant.rejudge_pending_assessments()

    assert processed == 1
    assert judge.judge_calls == 1
    status = assistant.get_llm_run_status()
    assert not status.active
    assert status.phase is None
    assert assistant.load_assessment_summary_catalog().pending_remaining == 1


def test_start_bulk_prepare_llm_run_updates_status_and_result(tmp_path: Path) -> None:
    entries = [
        _open_posting(job_id="86534", title="System Engineer"),
        _open_posting(job_id="86535", title="Analyst"),
        _open_posting(job_id="86536", title="Intern"),
    ]
    assistant, _, tailor = _assistant(tmp_path, entries=entries, rejudge_count=2)

    status = assistant.start_bulk_prepare_llm_run(["86534", "86535", "86536"])
    assert status.active
    assert status.phase == "Preparing"
    finished = _wait_llm_run_idle(assistant)

    assert not finished.active
    assert finished.bulk_prepare_result is not None
    assert finished.bulk_prepare_result.prepared == ["86534", "86535"]
    assert finished.bulk_prepare_result.skipped == ["86536"]
    assert tailor.tailor_calls == 2
    assert assistant.load_preparation_packet_page("86534") is not None


def test_bulk_prepare_llm_run_keeps_single_identity_status_and_stays_sequential(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The catalog assess knob must not leak into Bulk Prepare.
    monkeypatch.setenv(ENV_MAX_CONCURRENCY, "10")
    entries = [
        _open_posting(job_id="86534", title="System Engineer"),
        _open_posting(job_id="86535", title="Analyst", employer="Other"),
    ]
    tailor = _BlockingCvTailor()
    assistant, _, _ = _assistant(
        tmp_path, entries=entries, llm_cv_tailor=tailor, rejudge_count=2
    )

    assistant.start_bulk_prepare_llm_run(["86534", "86535"])
    assert tailor.entered.wait(timeout=5)
    status = assistant.get_llm_run_status()

    assert status.phase == "Preparing"
    assert status.in_flight == ()
    assert status.job_posting_id == "86534"
    assert status.title == "System Engineer"
    # Preparing keeps counting the in-flight posting toward k, exactly as before.
    assert status.current_index == 1
    assert status.total == 2

    tailor.release.set()
    finished = _wait_llm_run_idle(assistant)

    assert tailor.max_concurrent == 1
    assert finished.bulk_prepare_result is not None
    assert finished.bulk_prepare_result.prepared == ["86534", "86535"]


def test_start_bulk_prepare_llm_run_still_needs_confirm(tmp_path: Path) -> None:
    entries = [_open_posting(job_id="86534", title="System Engineer")]
    assistant, _, _ = _assistant(tmp_path, entries=entries, rejudge_count=1)
    assistant.prepare("86534")

    with pytest.raises(BulkPrepareNeedsConfirm):
        assistant.start_bulk_prepare_llm_run(["86534"])

    assert not assistant.get_llm_run_status().active
    assistant.start_bulk_prepare_llm_run(["86534"], confirm=True)
    finished = _wait_llm_run_idle(assistant)
    assert finished.bulk_prepare_result is not None
    assert finished.bulk_prepare_result.prepared == ["86534"]
