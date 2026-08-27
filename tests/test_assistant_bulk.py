"""Assistant seam: Bulk Prepare and Bulk Delete on Assessment Summary selection."""

import time
from pathlib import Path

import pytest

from job_finding_assistant.assistant import (
    Assistant,
    BulkDeleteNeedsConfirm,
    BulkPrepareNeedsConfirm,
    BulkPrepareResult,
    LlmRunStatus,
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
    GapItem,
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

_INVALID_MISSING_POSITION_CV = """\
cv:
  name: Test Candidate
  sections:
    experience:
      - company: Example
        highlights:
          - Built Python services
"""


def _write_cv(tmp_path: Path, name: str = "master_CV.yaml", body: str = _SAMPLE_CV) -> Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


def _posting(
    job_id: str,
    title: str,
    employer: str = "Example Corp",
    *,
    deadline: str = "2026-12-31",
) -> tuple[JobListEntry, JobPostingDetail]:
    entry = JobListEntry(
        id=job_id,
        title=title,
        employer=employer,
        posting_date="2026-07-01",
        application_deadline=deadline,
    )
    detail = JobPostingDetail(
        id=job_id,
        title=title,
        employer=employer,
        posting_date="2026-07-01",
        application_deadline=deadline,
        fields={
            "Job Description": "Build reliable systems in Python.",
            "Work Location": "Hong Kong",
        },
    )
    return entry, detail


def _assistant(
    tmp_path: Path,
    entries: list[tuple[JobListEntry, JobPostingDetail]],
    *,
    llm_cv_tailor: FakeLlmCvTailor | None = None,
    llm_judge: FakeLlmJudge | None = None,
    constraint_files: FakeConstraintFilesStore | None = None,
    rejudge_count: int | None = None,
) -> tuple[Assistant, FakeLlmCvTailor]:
    list_entries = [entry for entry, _ in entries]
    details = {detail.id: detail for _, detail in entries}
    job_board = FakeJobBoardSession(
        authenticated=True,
        list_entries=list_entries,
        details=details,
    )
    tailor = llm_cv_tailor or FakeLlmCvTailor(
        result=TailorResult(
            gap_report=GapReport(
                items=(
                    GapItem(
                        requirement="Production Kubernetes experience",
                        status="missing",
                        evidence="not found",
                        suggestion="Learn K8s basics",
                    ),
                )
            ),
            edit_summary=EditSummary(
                material_rephrases=("Example — rephrased highlight",)
            ),
            tailored_yaml=_SAMPLE_CV.replace(
                "Built Python services", "Built Python platform services"
            ),
        )
    )
    assistant = Assistant(
        catalog_store=CatalogStore(tmp_path / "catalog.db"),
        job_board=job_board,
        master_cv=FakeMasterCvStore(),
        llm_judge=llm_judge or FakeLlmJudge(relevance="Strong"),
        llm_cv_tailor=tailor,
        constraint_files=constraint_files or FakeConstraintFilesStore(),
        packet_store_dir=tmp_path / "packets",
        pdf_renderer=FakePdfRenderer(pdf_bytes=b"%PDF-1.4 fake"),
    )
    assistant.set_master_cv_path(str(_write_cv(tmp_path)))
    assistant.run_crawl()
    target = len(entries) if rejudge_count is None else rejudge_count
    for _ in range(target):
        assistant.rejudge_pending_assessments()
    return assistant, tailor


def _wait_llm_run_idle(assistant: Assistant, *, timeout: float = 5.0) -> LlmRunStatus:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = assistant.get_llm_run_status()
        if not status.active:
            return status
        time.sleep(0.01)
    raise TimeoutError("LLM Run did not finish")


def _run_bulk_prepare(
    assistant: Assistant,
    job_posting_ids: list[str],
    *,
    confirm: bool = False,
) -> BulkPrepareResult:
    status = assistant.start_bulk_prepare_llm_run(job_posting_ids, confirm=confirm)
    if status.active:
        status = _wait_llm_run_idle(assistant)
    return status.bulk_prepare_result or BulkPrepareResult(
        prepared=[],
        skipped=[],
        failed=[],
        stopped=[],
        message=status.message,
    )


def test_bulk_prepare_skips_pending_and_runs_eligible_immediately(
    tmp_path: Path,
) -> None:
    assistant, tailor = _assistant(
        tmp_path,
        [
            _posting("86534", "System Engineer"),
            _posting("86535", "Analyst"),
            _posting("86536", "Intern"),
        ],
        rejudge_count=2,
    )
    assessed_a = assistant.load_match_assessment_page("86534")
    assessed_b = assistant.load_match_assessment_page("86535")
    pending = assistant.load_match_assessment_page("86536")
    assert assessed_a is not None and assessed_a.match_assessment is not None
    assert assessed_b is not None and assessed_b.match_assessment is not None
    assert pending is not None and pending.match_assessment is None

    result = _run_bulk_prepare(assistant, ["86534", "86535", "86536"])

    assert result.prepared == ["86534", "86535"]
    assert result.skipped == ["86536"]
    assert result.failed == []
    assert result.stopped == []
    assert tailor.tailor_calls == 2
    assert assistant.load_preparation_packet_page("86534") is not None
    assert assistant.load_preparation_packet_page("86535") is not None


def test_bulk_prepare_empty_selection_is_noop_with_message(tmp_path: Path) -> None:
    assistant, tailor = _assistant(tmp_path, [_posting("86534", "System Engineer")])

    result = _run_bulk_prepare(assistant, [])

    assert result.message == "No Job Postings selected for Bulk Prepare."
    assert result.prepared == []
    assert tailor.tailor_calls == 0


def test_bulk_prepare_combined_confirm_for_hc_fail_and_overwrite(
    tmp_path: Path,
) -> None:
    hc_path = tmp_path / "hard.txt"
    hc_path.write_text("Hong Kong only\n", encoding="utf-8")
    constraints = FakeConstraintFilesStore()
    judge = FakeLlmJudge(
        hard_constraint_outcome="fail",
        hard_constraint_reason="Work location is remote-only",
        relevance="Strong",
    )
    assistant, tailor = _assistant(
        tmp_path,
        [
            _posting("86534", "System Engineer"),
            _posting("86535", "Analyst"),
        ],
        llm_judge=judge,
        constraint_files=constraints,
    )
    assistant.set_hard_constraints_path(str(hc_path))
    assistant.rejudge_pending_assessments()
    assistant.rejudge_pending_assessments()
    assistant.prepare("86535", confirm_hard_constraint_fail=True)
    assert tailor.tailor_calls == 1

    with pytest.raises(BulkPrepareNeedsConfirm) as pending:
        _run_bulk_prepare(assistant, ["86534", "86535", "86536"])
    # 86536 is unknown / not can_prepare → skipped, still listed in selection.
    kinds = {(item.job_posting_id, item.kind) for item in pending.value.items}
    assert ("86534", "hard_constraint_fail") in kinds
    assert ("86535", "overwrite") in kinds
    assert ("86535", "hard_constraint_fail") in kinds
    assert "remote-only" in " ".join(item.reason for item in pending.value.items)
    assert pending.value.selected_ids == ["86534", "86535", "86536"]
    assert pending.value.eligible_ids == ["86534", "86535"]
    assert pending.value.skipped_ids == ["86536"]

    result = _run_bulk_prepare(
        assistant, pending.value.selected_ids, confirm=True
    )

    assert result.prepared == ["86534", "86535"]
    assert result.skipped == ["86536"]
    assert tailor.tailor_calls == 3
    assert assistant.load_preparation_packet_page("86534") is not None


def test_bulk_prepare_stops_remaining_on_llm_unavailable(tmp_path: Path) -> None:
    tailor = FakeLlmCvTailor(
        result=TailorResult(
            gap_report=GapReport(),
            edit_summary=EditSummary(),
            tailored_yaml=_SAMPLE_CV,
        )
    )
    assistant, tailor = _assistant(
        tmp_path,
        [
            _posting("86534", "System Engineer"),
            _posting("86535", "Analyst"),
            _posting("86536", "Intern"),
        ],
        llm_cv_tailor=tailor,
    )

    original_tailor = tailor.tailor

    def _fail_after_first(**kwargs: object) -> TailorResult:
        if tailor.tailor_calls >= 1:
            tailor._fail_on_call = True
        return original_tailor(**kwargs)

    tailor.tailor = _fail_after_first  # type: ignore[method-assign]

    result = _run_bulk_prepare(assistant, ["86534", "86535", "86536"])

    assert result.prepared == ["86534"]
    assert result.failed[0][0] == "86535"
    assert "LLM Unavailable" in result.failed[0][1]
    assert result.stopped == ["86536"]
    assert assistant.load_preparation_packet_page("86534") is not None
    assert assistant.load_preparation_packet_page("86535") is None
    assert assistant.load_preparation_packet_page("86536") is None


def test_bulk_prepare_continues_after_non_llm_prepare_failure(tmp_path: Path) -> None:
    assistant, tailor = _assistant(
        tmp_path,
        [
            _posting("86534", "System Engineer"),
            _posting("86535", "Analyst"),
        ],
    )
    # Leave assessment so can_prepare is True, but strip detail so prepare fails.
    assistant._catalog_store.upsert_job_posting(
        JobPosting(
            id="86534",
            title="System Engineer",
            employer="Example Corp",
            listing_status="Open",
            deadline_status="Upcoming",
            posting_date="2026-07-01",
            application_deadline="2026-12-31",
            detail_fields={},
            list_fingerprint="x",
        )
    )
    page = assistant.load_match_assessment_page("86534")
    assert page is not None
    assert page.can_prepare
    assert assistant._catalog_store.get_job_posting("86534") is not None

    result = _run_bulk_prepare(assistant, ["86534", "86535"])

    assert result.prepared == ["86535"]
    assert result.failed[0][0] == "86534"
    assert "detail" in result.failed[0][1].lower()
    assert result.stopped == []
    assert tailor.tailor_calls == 1
    assert assistant.load_preparation_packet_page("86535") is not None


def test_bulk_prepare_retries_tailor_once_per_posting_when_schema_invalid(
    tmp_path: Path,
) -> None:
    """Tailored YAML validation retry (ADR-0013 revisit) applies per-posting inside
    Bulk Prepare's LLM Run loop, not just single Prepare."""
    invalid_result = TailorResult(
        gap_report=GapReport(),
        edit_summary=EditSummary(),
        tailored_yaml=_INVALID_MISSING_POSITION_CV,
    )
    valid_result = TailorResult(
        gap_report=GapReport(),
        edit_summary=EditSummary(),
        tailored_yaml=_SAMPLE_CV,
    )
    tailor = FakeLlmCvTailor(results=[invalid_result, valid_result])
    assistant, tailor = _assistant(
        tmp_path,
        [_posting("86534", "System Engineer")],
        llm_cv_tailor=tailor,
    )

    result = _run_bulk_prepare(assistant, ["86534"])

    assert result.prepared == ["86534"]
    assert result.failed == []
    assert tailor.tailor_calls == 2
    page = assistant.load_preparation_packet_page("86534")
    assert page is not None
    assert page.packet.pdf_missing is False
    assert page.packet.pdf_missing_reasons == ()
    assert page.packet.tailored_yaml == _SAMPLE_CV


def test_bulk_delete_requires_confirm_listing_selection(tmp_path: Path) -> None:
    assistant, _ = _assistant(
        tmp_path,
        [
            _posting("86534", "System Engineer"),
            _posting("86535", "Analyst"),
        ],
        rejudge_count=1,
    )
    assistant.prepare("86534")
    pending_page = assistant.load_match_assessment_page("86535")
    assert pending_page is not None
    assert pending_page.match_assessment is None

    with pytest.raises(BulkDeleteNeedsConfirm) as pending:
        assistant.bulk_delete(["86534", "86535"])
    by_id = {item.job_posting_id: item for item in pending.value.items}
    assert by_id["86534"].title == "System Engineer"
    assert by_id["86534"].has_match_assessment is True
    assert by_id["86534"].has_preparation_packet is True
    assert by_id["86535"].has_match_assessment is False
    assert by_id["86535"].has_preparation_packet is False

    result = assistant.bulk_delete(["86534", "86535"], confirm=True)

    assert result.deleted == ["86534", "86535"]
    assert (
        assistant.load_assessment_summary_catalog(
            include_closed=True, include_passed_deadlines=True
        ).rows
        == []
    )
    assert assistant.load_preparation_packet_page("86534") is None


def test_bulk_delete_empty_selection_is_noop_with_message(tmp_path: Path) -> None:
    assistant, _ = _assistant(tmp_path, [_posting("86534", "System Engineer")])

    result = assistant.bulk_delete([])

    assert result.message == "No Job Postings selected for Bulk Delete."
    assert result.deleted == []
    remaining = assistant.load_match_assessment_page("86534")
    assert remaining is not None
    assert remaining.match_assessment is not None
