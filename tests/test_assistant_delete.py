"""Assistant seam: Delete Job Posting with assessment and packet cascade."""

from pathlib import Path

import pytest

from job_finding_assistant.assistant import Assistant, DeleteNeedsConfirm
from job_finding_assistant.catalog_store import CatalogStore
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


def _ready_assistant(tmp_path: Path) -> Assistant:
    entry, detail = _open_posting()
    job_board = FakeJobBoardSession(
        authenticated=True,
        list_entries=[entry],
        details={detail.id: detail},
    )
    tailor = FakeLlmCvTailor(
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
        llm_judge=FakeLlmJudge(relevance="Strong"),
        llm_cv_tailor=tailor,
        constraint_files=FakeConstraintFilesStore(),
        packet_store_dir=tmp_path / "packets",
        pdf_renderer=FakePdfRenderer(pdf_bytes=b"%PDF-1.4 fake"),
    )
    assistant.set_master_cv_path(str(_write_cv(tmp_path)))
    assistant.run_crawl()
    assistant.rejudge_pending_assessments()
    return assistant


def test_delete_requires_confirm_naming_posting_assessment_and_packet(
    tmp_path: Path,
) -> None:
    assistant = _ready_assistant(tmp_path)
    assistant.prepare("86534")

    with pytest.raises(DeleteNeedsConfirm) as exc_info:
        assistant.delete("86534")

    reason = exc_info.value.reason
    assert "System Engineer" in reason
    assert "Example Corp" in reason
    assert "Match Assessment" in reason
    assert "Preparation Packet" in reason


def test_delete_confirm_hard_removes_posting_assessment_and_packet(
    tmp_path: Path,
) -> None:
    assistant = _ready_assistant(tmp_path)
    assistant.prepare("86534")
    assert assistant.get_preparation_packet("86534") is not None
    assert assistant.get_match_assessment("86534") is not None

    assistant.delete("86534", confirm=True)

    assert assistant.list_assessment_summaries() == []
    assert assistant.get_match_assessment("86534") is None
    assert assistant.get_preparation_packet("86534") is None
    assert assistant.get_tailored_yaml("86534") is None


def test_delete_without_packet_omits_packet_from_confirm_and_removes_posting(
    tmp_path: Path,
) -> None:
    assistant = _ready_assistant(tmp_path)
    assert assistant.get_preparation_packet("86534") is None

    with pytest.raises(DeleteNeedsConfirm) as exc_info:
        assistant.delete("86534")
    assert "Match Assessment" in exc_info.value.reason
    assert "Preparation Packet" not in exc_info.value.reason

    assistant.delete("86534", confirm=True)

    assert assistant.list_assessment_summaries() == []
    assert assistant.get_match_assessment("86534") is None


def test_delete_while_pending_removes_posting(tmp_path: Path) -> None:
    entry, detail = _open_posting()
    job_board = FakeJobBoardSession(
        authenticated=True,
        list_entries=[entry],
        details={detail.id: detail},
    )
    assistant = Assistant(
        catalog_store=CatalogStore(tmp_path / "catalog.db"),
        job_board=job_board,
        master_cv=FakeMasterCvStore(),
        llm_judge=FakeLlmJudge(available=False),
        llm_cv_tailor=FakeLlmCvTailor(),
        constraint_files=FakeConstraintFilesStore(),
        packet_store_dir=tmp_path / "packets",
        pdf_renderer=FakePdfRenderer(),
    )
    assistant.set_master_cv_path(str(_write_cv(tmp_path)))
    assistant.run_crawl()
    assert assistant.get_match_assessment("86534") is None

    with pytest.raises(DeleteNeedsConfirm) as exc_info:
        assistant.delete("86534")
    assert "Match Assessment" in exc_info.value.reason
    assert "Preparation Packet" not in exc_info.value.reason

    assistant.delete("86534", confirm=True)
    assert assistant.list_assessment_summaries(
        include_closed=True, include_passed_deadlines=True
    ) == []
