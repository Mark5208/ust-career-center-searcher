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


def test_stop_llm_run_finishes_current_and_does_not_start_next(tmp_path: Path) -> None:
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
    tmp_path: Path,
) -> None:
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


def test_rejudge_pending_assessments_stays_one_and_is_not_llm_run(
    tmp_path: Path,
) -> None:
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
    assert assistant.get_preparation_packet("86534") is not None


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
