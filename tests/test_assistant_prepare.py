"""Assistant seam: Prepare Preparation Packet, Gap Report, Edit Summary, Stale."""

from pathlib import Path

import pytest

from job_finding_assistant.assistant import (
    Assistant,
    PrepareBlockedError,
    PrepareFailedError,
    PrepareNeedsConfirm,
)
from job_finding_assistant.catalog_store import CatalogStore
from job_finding_assistant.fakes import (
    FakeConstraintFilesStore,
    FakeCrawlPacer,
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


def _write_cv(tmp_path: Path, name: str = "master_CV.yaml", body: str = _SAMPLE_CV) -> Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


def _open_posting(
    *,
    job_id: str = "86534",
    title: str = "System Engineer",
    employer: str = "Example Corp",
    deadline: str = "2026-12-31",
    fields: dict[str, str] | None = None,
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
        fields=fields
        or {
            "Job Description": "Build reliable systems in Python.",
            "Work Location": "Hong Kong",
        },
    )
    return entry, detail


def _ready_assistant(
    tmp_path: Path,
    *,
    llm_cv_tailor: FakeLlmCvTailor | None = None,
    pdf_renderer: FakePdfRenderer | None = None,
    llm_judge: FakeLlmJudge | None = None,
    constraint_files: FakeConstraintFilesStore | None = None,
    deadline: str = "2026-12-31",
) -> tuple[Assistant, FakeLlmCvTailor, FakePdfRenderer, FakeJobBoardSession]:
    entry, detail = _open_posting(deadline=deadline)
    job_board = FakeJobBoardSession(
        authenticated=True,
        list_entries=[entry],
        details={detail.id: detail},
    )
    tailor = llm_cv_tailor or FakeLlmCvTailor(
        result=TailorResult(
            gap_report=GapReport(
                items=(
                    GapItem(
                        requirement="Production Kubernetes experience",
                        status="missing",
                        evidence="not found",
                        suggestion="Learn K8s basics or clarify related ops work on the Master CV",
                    ),
                )
            ),
            edit_summary=EditSummary(
                material_rephrases=(
                    'Example / Platform engineer — "Built Python services" → "Built Python platform services"',
                )
            ),
            tailored_yaml=_SAMPLE_CV.replace(
                "Built Python services", "Built Python platform services"
            ),
        )
    )
    renderer = pdf_renderer or FakePdfRenderer(pdf_bytes=b"%PDF-1.4 fake")
    cv_path = _write_cv(tmp_path)
    assistant = Assistant(
        catalog_store=CatalogStore(tmp_path / "catalog.db"),
        job_board=job_board,
        master_cv=FakeMasterCvStore(),
        llm_judge=llm_judge or FakeLlmJudge(relevance="Strong"),
        llm_cv_tailor=tailor,
        constraint_files=constraint_files or FakeConstraintFilesStore(),
        crawl_pacer=FakeCrawlPacer(),
        packet_store_dir=tmp_path / "packets",
        pdf_renderer=renderer,
    )
    assistant.set_master_cv_path(str(cv_path))
    assistant.run_crawl()
    assistant.rejudge_pending_assessments()
    return assistant, tailor, renderer, job_board


def test_prepare_builds_packet_with_gap_report_edit_summary_yaml_and_pdf(
    tmp_path: Path,
) -> None:
    assistant, tailor, renderer, _ = _ready_assistant(tmp_path)

    packet = assistant.prepare("86534")

    assert packet.job_posting_id == "86534"
    assert packet.stale is False
    assert packet.pdf_missing is False
    assert packet.pdf_bytes == b"%PDF-1.4 fake"
    assert len(packet.gap_report.items) == 1
    assert packet.gap_report.items[0].status == "missing"
    assert packet.edit_summary.material_rephrases
    assert "platform services" in packet.tailored_yaml
    assert tailor.tailor_calls == 1
    assert renderer.render_calls == 1
    summary = assistant.list_assessment_summaries()[0]
    assert summary.has_preparation_packet is True
    assert summary.preparation_packet_stale is False
    stored = assistant.get_preparation_packet("86534")
    assert stored is not None
    assert stored.match_assessment is not None
    assert stored.match_assessment.relevance == "Strong"
    assert assistant.get_tailored_yaml("86534") == packet.tailored_yaml
    assert assistant.get_tailored_pdf("86534") == b"%PDF-1.4 fake"


def test_prepare_blocked_while_pending(tmp_path: Path) -> None:
    entry, detail = _open_posting()
    assistant = Assistant(
        catalog_store=CatalogStore(tmp_path / "catalog.db"),
        job_board=FakeJobBoardSession(
            authenticated=True,
            list_entries=[entry],
            details={detail.id: detail},
        ),
        master_cv=FakeMasterCvStore(),
        llm_judge=FakeLlmJudge(relevance="Strong"),
        llm_cv_tailor=FakeLlmCvTailor(),
        constraint_files=FakeConstraintFilesStore(),
        crawl_pacer=FakeCrawlPacer(),
        packet_store_dir=tmp_path / "packets",
        pdf_renderer=FakePdfRenderer(),
    )
    assistant.set_master_cv_path(str(_write_cv(tmp_path)))
    assistant.run_crawl()

    with pytest.raises(PrepareBlockedError):
        assistant.prepare("86534")


def test_prepare_allowed_for_closed_and_deadline_passed(tmp_path: Path) -> None:
    assistant, _, _, job_board = _ready_assistant(tmp_path, deadline="2020-01-01")
    job_board.set_list_entries([])
    assistant.run_crawl()
    closed = assistant.list_assessment_summaries(
        include_closed=True, include_passed_deadlines=True
    )[0]
    assert closed.listing_status == "Closed"
    assert closed.deadline_status == "Passed"

    packet = assistant.prepare("86534")

    assert packet.job_posting_id == "86534"


def test_hard_constraint_fail_requires_confirm_with_reason(tmp_path: Path) -> None:
    hc_path = tmp_path / "hard.txt"
    hc_path.write_text("Hong Kong only\n", encoding="utf-8")
    constraints = FakeConstraintFilesStore()
    judge = FakeLlmJudge(
        hard_constraint_outcome="fail",
        hard_constraint_reason="Work location is remote-only",
        relevance="Strong",
    )
    assistant, _, _, _ = _ready_assistant(
        tmp_path, llm_judge=judge, constraint_files=constraints
    )
    assistant.set_hard_constraints_path(str(hc_path))
    assistant.rejudge_pending_assessments()

    with pytest.raises(PrepareNeedsConfirm) as pending:
        assistant.prepare("86534")
    assert pending.value.kind == "hard_constraint_fail"
    assert "remote-only" in pending.value.reason

    packet = assistant.prepare("86534", confirm_hard_constraint_fail=True)
    assert packet.job_posting_id == "86534"


def test_reprepare_requires_overwrite_confirm(tmp_path: Path) -> None:
    assistant, tailor, _, _ = _ready_assistant(tmp_path)
    first = assistant.prepare("86534")
    assert tailor.tailor_calls == 1

    with pytest.raises(PrepareNeedsConfirm) as pending:
        assistant.prepare("86534")
    assert pending.value.kind == "overwrite"

    second = assistant.prepare("86534", confirm_overwrite=True)
    assert tailor.tailor_calls == 2
    assert second.tailored_yaml == first.tailored_yaml


def test_tailor_failure_leaves_prior_packet_untouched(tmp_path: Path) -> None:
    assistant, tailor, _, _ = _ready_assistant(tmp_path)
    first = assistant.prepare("86534")
    prior_yaml = first.tailored_yaml

    tailor._fail_on_call = True
    with pytest.raises(PrepareFailedError):
        assistant.prepare("86534", confirm_overwrite=True)

    stored = assistant.get_preparation_packet("86534")
    assert stored is not None
    assert stored.packet.tailored_yaml == prior_yaml
    assert stored.packet.stale is False


def test_pdf_only_failure_keeps_packet_without_pdf(tmp_path: Path) -> None:
    assistant, _, _, _ = _ready_assistant(
        tmp_path, pdf_renderer=FakePdfRenderer(fail=True)
    )

    packet = assistant.prepare("86534")

    assert packet.pdf_missing is True
    assert packet.pdf_bytes is None
    assert packet.gap_report.items
    assert packet.tailored_yaml
    assert assistant.get_tailored_pdf("86534") is None
    assert assistant.list_assessment_summaries()[0].has_preparation_packet is True


def test_master_cv_change_marks_packet_stale_but_readable(tmp_path: Path) -> None:
    assistant, _, _, _ = _ready_assistant(tmp_path)
    assistant.prepare("86534")
    assert assistant.list_assessment_summaries()[0].preparation_packet_stale is False

    new_cv = _write_cv(
        tmp_path,
        name="master_CV_v2.yaml",
        body=_SAMPLE_CV + "\n# changed\n",
    )
    assistant.set_master_cv_path(str(new_cv))

    summaries = assistant.list_assessment_summaries()
    assert summaries[0].pending is True
    assert summaries[0].has_preparation_packet is True
    assert summaries[0].preparation_packet_stale is True
    view = assistant.get_preparation_packet("86534")
    assert view is not None
    assert view.packet.stale is True
    assert view.packet.tailored_yaml
    assert view.packet.gap_report.items


def test_hard_constraints_and_preferences_change_mark_packet_stale(
    tmp_path: Path,
) -> None:
    constraints = FakeConstraintFilesStore()
    assistant, _, _, _ = _ready_assistant(tmp_path, constraint_files=constraints)
    assistant.prepare("86534")

    hc_path = tmp_path / "hard.txt"
    hc_path.write_text("Must be Hong Kong based\n", encoding="utf-8")
    assistant.set_hard_constraints_path(str(hc_path))
    view = assistant.get_preparation_packet("86534")
    assert view is not None
    assert view.packet.stale is True

    assistant.rejudge_pending_assessments()
    assistant.prepare("86534", confirm_overwrite=True)
    prefs_path = tmp_path / "prefs.txt"
    prefs_path.write_text("Prefer fintech\n", encoding="utf-8")
    assistant.set_preferences_path(str(prefs_path))
    view = assistant.get_preparation_packet("86534")
    assert view is not None
    assert view.packet.stale is True

    assistant.rejudge_pending_assessments()
    assistant.prepare("86534", confirm_overwrite=True)
    assistant.clear_preferences_path()
    view = assistant.get_preparation_packet("86534")
    assert view is not None
    assert view.packet.stale is True


def test_crawl_detail_change_does_not_stale_packet(tmp_path: Path) -> None:
    entry, detail = _open_posting()
    job_board = FakeJobBoardSession(
        authenticated=True,
        list_entries=[entry],
        details={detail.id: detail},
    )
    tailor = FakeLlmCvTailor(
        result=TailorResult(
            gap_report=GapReport(),
            edit_summary=EditSummary(),
            tailored_yaml=_SAMPLE_CV,
        )
    )
    cv_path = _write_cv(tmp_path)
    assistant = Assistant(
        catalog_store=CatalogStore(tmp_path / "catalog.db"),
        job_board=job_board,
        master_cv=FakeMasterCvStore(),
        llm_judge=FakeLlmJudge(relevance="Strong"),
        llm_cv_tailor=tailor,
        constraint_files=FakeConstraintFilesStore(),
        crawl_pacer=FakeCrawlPacer(),
        packet_store_dir=tmp_path / "packets",
        pdf_renderer=FakePdfRenderer(),
    )
    assistant.set_master_cv_path(str(cv_path))
    assistant.run_crawl()
    assistant.rejudge_pending_assessments()
    assistant.prepare("86534")

    changed_entry = JobListEntry(
        id=entry.id,
        title="Senior System Engineer",
        employer=entry.employer,
        posting_date=entry.posting_date,
        application_deadline=entry.application_deadline,
    )
    changed_detail = JobPostingDetail(
        id=detail.id,
        title="Senior System Engineer",
        employer=detail.employer,
        posting_date=detail.posting_date,
        application_deadline=detail.application_deadline,
        fields={**detail.fields, "Job Description": "Lead platform reliability work."},
    )
    job_board.set_list_entries([changed_entry])
    job_board.set_details({changed_detail.id: changed_detail})

    assistant.run_crawl()
    view = assistant.get_preparation_packet("86534")
    assert view is not None
    assert view.packet.stale is False
    summary = next(
        row
        for row in assistant.list_assessment_summaries(include_closed=True)
        if row.job_posting_id == "86534"
    )
    assert summary.pending is True
    assert summary.has_preparation_packet is True
    assert summary.preparation_packet_stale is False


def test_tailor_does_not_receive_preferences(tmp_path: Path) -> None:
    prefs_path = tmp_path / "prefs.txt"
    prefs_path.write_text("Prefer fintech\n", encoding="utf-8")
    constraints = FakeConstraintFilesStore()
    judge = FakeLlmJudge(preference="Strong", relevance="Strong")
    assistant, tailor, _, _ = _ready_assistant(
        tmp_path, llm_judge=judge, constraint_files=constraints
    )
    assistant.set_preferences_path(str(prefs_path))
    assistant.rejudge_pending_assessments()

    assistant.prepare("86534")

    assert tailor.tailor_calls == 1
    inputs = tailor.tailor_inputs[0]
    assert "preferences" not in str(inputs).lower() or "Prefer fintech" not in str(
        inputs
    )
    assert "Prefer fintech" not in inputs["master_cv_yaml"]
    assert "Prefer fintech" not in str(inputs["job_detail_fields"])
