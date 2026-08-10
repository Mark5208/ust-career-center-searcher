"""UI route talks only to Assistant for Assessment Summary listing."""

import time
from pathlib import Path

from fastapi.testclient import TestClient

from job_finding_assistant.assistant import (
    AssessmentSummary,
    AssessmentSummaryCatalog,
    AssessmentSummaryCatalogRow,
    Assistant,
    CrawlFilters,
    CrawlOutcome,
    DeleteNeedsConfirm,
    PreparationPacketView,
)
from job_finding_assistant.candidate_snapshot import CandidateSnapshot
from job_finding_assistant.catalog_store import CatalogStore
from job_finding_assistant.constraint_files_store import DiskConstraintFilesStore
from job_finding_assistant.fakes import (
    FakeConstraintFilesStore,
    FakeCrawlPacer,
    FakeJobBoardSession,
    FakeLlmCvTailor,
    FakeLlmJudge,
    FakeMasterCvStore,
)
from job_finding_assistant.job_board import JobListEntry, JobPostingDetail
from job_finding_assistant.master_cv_store import DiskMasterCvStore
from job_finding_assistant.match_assessment import EvidencePair, MatchAssessment
from job_finding_assistant.preparation_packet import (
    EditSummary,
    GapReport,
    PreparationPacket,
)
from job_finding_assistant.web.app import create_app


class _RecordingAssistant:
    """Stand-in that proves the route calls Assistant, not CatalogStore directly."""

    def __init__(self) -> None:
        self.list_calls = 0
        self.list_kwargs: dict[str, bool] = {}
        self.catalog_load_calls = 0
        self.catalog_load_kwargs: dict[str, bool] = {}
        self.summaries: list[AssessmentSummary] = []
        self.can_prepare_calls: list[str] = []
        self.rejudge_calls = 0
        self.processed_this_load = 0
        self.pending_remaining = 0
        self.master_cv_path: str | None = None
        self.snapshot: CandidateSnapshot | None = None
        self.hard_constraints_path: str | None = None
        self.preferences_path: str | None = None
        self.candidate_file_errors: list[str] = []
        self.llm_unavailable_reason: str | None = None
        self.crawl_filters = CrawlFilters()
        self.set_master_cv_calls: list[str] = []
        self.set_hard_constraints_calls: list[str] = []
        self.set_preferences_calls: list[str] = []
        self.clear_hard_constraints_calls = 0
        self.clear_preferences_calls = 0
        self.login_calls = 0
        self.crawl_calls: list[bool] = []
        self._can_start_crawl = False
        self.prepare_calls: list[str] = []
        self.get_packet_calls: list[str] = []
        self.packet_views: dict[str, PreparationPacketView] = {}
        self.delete_calls: list[tuple[str, bool]] = []
        self.delete_needs_confirm = False
        self.delete_confirm_reason = (
            "Delete permanently removes Job Posting 'System Engineer — Example Corp', "
            "Match Assessment, and Preparation Packet. No undo."
        )
        self.match_assessments: dict[str, MatchAssessment] = {}
        self.get_match_assessment_calls: list[str] = []

    def load_assessment_summary_catalog(
        self,
        *,
        include_closed: bool = False,
        include_passed_deadlines: bool = False,
    ) -> AssessmentSummaryCatalog:
        self.catalog_load_calls += 1
        self.catalog_load_kwargs = {
            "include_closed": include_closed,
            "include_passed_deadlines": include_passed_deadlines,
        }
        rows = [
            AssessmentSummaryCatalogRow(
                summary=summary,
                can_prepare=not summary.pending,
            )
            for summary in self.summaries
        ]
        pending = sum(1 for summary in self.summaries if summary.pending)
        return AssessmentSummaryCatalog(
            rows=rows,
            processed_this_load=self.processed_this_load,
            pending_remaining=(
                self.pending_remaining if self.pending_remaining else pending
            ),
            llm_unavailable_reason=self.llm_unavailable_reason,
        )

    def list_assessment_summaries(
        self,
        *,
        include_closed: bool = False,
        include_passed_deadlines: bool = False,
    ) -> list[AssessmentSummary]:
        self.list_calls += 1
        self.list_kwargs = {
            "include_closed": include_closed,
            "include_passed_deadlines": include_passed_deadlines,
        }
        return list(self.summaries)

    def can_prepare(self, job_posting_id: str) -> bool:
        self.can_prepare_calls.append(job_posting_id)
        for row in self.summaries:
            if row.job_posting_id != job_posting_id:
                continue
            return not row.pending
        return False

    def get_match_assessment(self, job_posting_id: str) -> MatchAssessment | None:
        self.get_match_assessment_calls.append(job_posting_id)
        return self.match_assessments.get(job_posting_id)

    def prepare(
        self,
        job_posting_id: str,
        *,
        confirm_hard_constraint_fail: bool = False,
        confirm_overwrite: bool = False,
    ) -> PreparationPacket:
        del confirm_hard_constraint_fail, confirm_overwrite
        self.prepare_calls.append(job_posting_id)
        return PreparationPacket(
            job_posting_id=job_posting_id,
            gap_report=GapReport(),
            edit_summary=EditSummary(),
            tailored_yaml="cv:\n  name: Tailored\n",
            pdf_bytes=b"%PDF",
        )

    def get_preparation_packet(self, job_posting_id: str) -> PreparationPacketView | None:
        self.get_packet_calls.append(job_posting_id)
        return self.packet_views.get(job_posting_id)

    def get_tailored_yaml(self, job_posting_id: str) -> str | None:
        view = self.packet_views.get(job_posting_id)
        return view.packet.tailored_yaml if view else None

    def get_tailored_pdf(self, job_posting_id: str) -> bytes | None:
        view = self.packet_views.get(job_posting_id)
        return view.packet.pdf_bytes if view else None

    def delete(self, job_posting_id: str, *, confirm: bool = False) -> None:
        self.delete_calls.append((job_posting_id, confirm))
        if self.delete_needs_confirm and not confirm:
            raise DeleteNeedsConfirm(self.delete_confirm_reason)
        self.summaries = [
            row for row in self.summaries if row.job_posting_id != job_posting_id
        ]

    def rejudge_pending_assessments(self) -> None:
        self.rejudge_calls += 1

    def get_master_cv_path(self) -> str | None:
        return self.master_cv_path

    def set_master_cv_path(self, path: str) -> None:
        self.set_master_cv_calls.append(path)
        self.master_cv_path = path

    def get_candidate_snapshot(self) -> CandidateSnapshot | None:
        return self.snapshot

    def get_hard_constraints_path(self) -> str | None:
        return self.hard_constraints_path

    def set_hard_constraints_path(self, path: str) -> None:
        self.set_hard_constraints_calls.append(path)
        self.hard_constraints_path = path

    def clear_hard_constraints_path(self) -> None:
        self.clear_hard_constraints_calls += 1
        self.hard_constraints_path = None

    def get_preferences_path(self) -> str | None:
        return self.preferences_path

    def set_preferences_path(self, path: str) -> None:
        self.set_preferences_calls.append(path)
        self.preferences_path = path

    def clear_preferences_path(self) -> None:
        self.clear_preferences_calls += 1
        self.preferences_path = None

    def get_candidate_file_errors(self) -> list[str]:
        return list(self.candidate_file_errors)

    def get_llm_unavailable_reason(self) -> str | None:
        return self.llm_unavailable_reason

    def get_crawl_filters(self) -> CrawlFilters:
        return self.crawl_filters

    def update_crawl_filters(self, filters: CrawlFilters) -> None:
        self.crawl_filters = filters

    def start_user_attended_login(self) -> None:
        self.login_calls += 1
        self._can_start_crawl = True

    def can_start_crawl(self) -> bool:
        return self._can_start_crawl

    def run_crawl(self, *, full_refresh: bool = False) -> CrawlOutcome:
        self.crawl_calls.append(full_refresh)
        return CrawlOutcome(status="completed", stored_count=0)


def test_catalog_page_calls_assistant_and_shows_empty_job_postings_state() -> None:
    assistant = _RecordingAssistant()
    client = TestClient(create_app(assistant))

    response = client.get("/")

    assert response.status_code == 200
    assert assistant.catalog_load_calls == 1
    assert assistant.list_calls == 0
    assert assistant.can_prepare_calls == []
    assert assistant.catalog_load_kwargs == {
        "include_closed": False,
        "include_passed_deadlines": False,
    }
    assert "Assessment Summary" in response.text
    assert "No Job Postings" in response.text


def test_catalog_page_shows_llm_unavailable_reason() -> None:
    assistant = _RecordingAssistant()
    assistant.llm_unavailable_reason = "LLM Unavailable: API key not configured"
    client = TestClient(create_app(assistant))

    response = client.get("/")

    assert response.status_code == 200
    assert "LLM Unavailable: API key not configured" in response.text


def test_catalog_page_shows_assessment_fields_and_prepare_unavailable_when_pending() -> None:
    assistant = _RecordingAssistant()
    assistant.summaries = [
        AssessmentSummary(
            job_posting_id="86534",
            title="System Engineer",
            employer="Example Corp",
            listing_status="Open",
            deadline_status="Upcoming",
            pending=True,
        ),
        AssessmentSummary(
            job_posting_id="86535",
            title="Analyst",
            employer="Example Corp",
            listing_status="Open",
            deadline_status="Upcoming",
            pending=False,
            hard_constraint_outcome="pass",
            preference="Strong",
            relevance="Strong",
        ),
    ]
    client = TestClient(create_app(assistant))

    response = client.get("/")

    assert response.status_code == 200
    assert "System Engineer" in response.text
    assert "Example Corp" in response.text
    assert "Pending" in response.text
    assert "Prepare unavailable" in response.text
    assert "Strong" in response.text
    assert "pass" in response.text
    assert "Preference" in response.text
    assert assistant.catalog_load_calls == 1
    assert assistant.can_prepare_calls == []


def test_catalog_page_shows_rejudge_progress_banner() -> None:
    assistant = _RecordingAssistant()
    assistant.processed_this_load = 1
    assistant.pending_remaining = 7
    assistant.summaries = [
        AssessmentSummary(
            job_posting_id="86534",
            title="System Engineer",
            employer="Example Corp",
            listing_status="Open",
            deadline_status="Upcoming",
            pending=True,
        ),
    ]
    client = TestClient(create_app(assistant))

    response = client.get("/")

    assert response.status_code == 200
    assert "Processed 1 Pending this load" in response.text
    assert "7 still Pending" in response.text
    assert "Refresh to continue" in response.text


def test_catalog_page_passes_closed_and_passed_toggles_to_assistant() -> None:
    assistant = _RecordingAssistant()
    client = TestClient(create_app(assistant))

    response = client.get("/?include_closed=1&include_passed_deadlines=1")

    assert response.status_code == 200
    assert assistant.catalog_load_kwargs == {
        "include_closed": True,
        "include_passed_deadlines": True,
    }
    assert "include_closed" in response.text
    assert "include_passed_deadlines" in response.text


def test_catalog_page_with_wired_assistant_shows_empty_catalog(tmp_path: Path) -> None:
    assistant = Assistant(
        catalog_store=CatalogStore(tmp_path / "catalog.db"),
        job_board=FakeJobBoardSession(),
        master_cv=FakeMasterCvStore(),
        llm_judge=FakeLlmJudge(),
        llm_cv_tailor=FakeLlmCvTailor(),
        constraint_files=FakeConstraintFilesStore(),
    )
    client = TestClient(create_app(assistant))

    response = client.get("/")

    assert response.status_code == 200
    assert "No Job Postings" in response.text


def test_catalog_returns_before_full_rejudge_budget(tmp_path: Path) -> None:
    """Catalog GET must not block on judging every Pending posting (ADR-0015 opportunistic)."""
    cv_path = tmp_path / "master_CV.yaml"
    cv_path.write_text(
        "cv:\n  name: Test\n  sections:\n    experience:\n      - company: X\n        position: Y\n",
        encoding="utf-8",
    )
    entries = [
        JobListEntry(
            id="86534",
            title="Engineer A",
            employer="Corp A",
            posting_date="2026-07-01",
            application_deadline="2026-12-31",
        ),
        JobListEntry(
            id="86535",
            title="Engineer B",
            employer="Corp B",
            posting_date="2026-07-01",
            application_deadline="2026-12-31",
        ),
    ]
    details = {
        entry.id: JobPostingDetail(
            id=entry.id,
            title=entry.title,
            employer=entry.employer,
            posting_date=entry.posting_date,
            application_deadline=entry.application_deadline,
            fields={"Job Description": f"Detail for {entry.title}"},
        )
        for entry in entries
    }
    judge = FakeLlmJudge(relevance="Strong", delay_seconds=2.0)
    master_cv = FakeMasterCvStore()
    assistant = Assistant(
        catalog_store=CatalogStore(tmp_path / "catalog.db"),
        job_board=FakeJobBoardSession(
            authenticated=True,
            list_entries=entries,
            details=details,
        ),
        master_cv=master_cv,
        llm_judge=judge,
        llm_cv_tailor=FakeLlmCvTailor(),
        constraint_files=FakeConstraintFilesStore(),
        crawl_pacer=FakeCrawlPacer(),
    )
    assistant.set_master_cv_path(str(cv_path))
    assistant.run_crawl()
    assert len(assistant.list_assessment_summaries()) == 2
    assert all(row.pending for row in assistant.list_assessment_summaries())

    client = TestClient(create_app(assistant))
    started = time.perf_counter()
    response = client.get("/")
    elapsed = time.perf_counter() - started

    assert response.status_code == 200
    assert elapsed < 3.0
    assert judge.judge_calls == 1
    pending_after = sum(
        1 for row in assistant.list_assessment_summaries() if row.pending
    )
    assert pending_after == 1


def test_candidate_page_calls_assistant_for_snapshot_and_constraint_paths() -> None:
    assistant = _RecordingAssistant()
    assistant.master_cv_path = "/tmp/master_CV.yaml"
    assistant.hard_constraints_path = "/tmp/hard.txt"
    assistant.preferences_path = "/tmp/prefs.txt"
    assistant.snapshot = CandidateSnapshot(
        contact="Alice Example, alice@example.com",
        education=["BEng Computer Science, HKUST, 2024"],
        experience=["Software Intern at Acme Corp"],
        projects=["Campus Event Finder"],
        skills_tools=["Python, YAML, SQLite"],
    )
    client = TestClient(create_app(assistant))

    response = client.get("/candidate")

    assert response.status_code == 200
    assert "Candidate Snapshot" in response.text
    assert "Master CV YAML path" in response.text
    assert "Alice Example, alice@example.com" in response.text
    assert "Hard Constraints file" in response.text
    assert "Preferences file" in response.text
    assert "/tmp/hard.txt" in response.text
    assert "/tmp/prefs.txt" in response.text
    assert 'action="/crawl/filters"' not in response.text
    assert "LaTeX" not in response.text


def test_candidate_page_posts_paths_through_assistant(tmp_path: Path) -> None:
    master_cv_path = tmp_path / "master_CV.yaml"
    master_cv_path.write_text(
        """\
cv:
  name: Alice
  sections:
    skills:
      - label: Languages
        details: Python
""",
        encoding="utf-8",
    )
    hc_path = tmp_path / "hard.txt"
    hc_path.write_text("Hong Kong only\n", encoding="utf-8")
    prefs_path = tmp_path / "prefs.txt"
    prefs_path.write_text("Prefer fintech\n", encoding="utf-8")
    assistant = Assistant(
        catalog_store=CatalogStore(tmp_path / "catalog.db"),
        job_board=FakeJobBoardSession(),
        master_cv=DiskMasterCvStore(tmp_path / "master_cv_state"),
        llm_judge=FakeLlmJudge(),
        llm_cv_tailor=FakeLlmCvTailor(),
        constraint_files=DiskConstraintFilesStore(tmp_path / "constraint_files_state"),
    )
    client = TestClient(create_app(assistant))

    path_response = client.post(
        "/candidate/master-cv",
        data={"master_cv_path": str(master_cv_path)},
        follow_redirects=False,
    )
    hc_response = client.post(
        "/candidate/hard-constraints",
        data={"hard_constraints_path": str(hc_path)},
        follow_redirects=False,
    )
    prefs_response = client.post(
        "/candidate/preferences",
        data={"preferences_path": str(prefs_path)},
        follow_redirects=False,
    )

    assert path_response.status_code == 303
    assert hc_response.status_code == 303
    assert prefs_response.status_code == 303
    assert assistant.get_master_cv_path() == str(master_cv_path.resolve())
    assert assistant.get_hard_constraints_path() == str(hc_path.resolve())
    assert assistant.get_preferences_path() == str(prefs_path.resolve())
    assert "details: Python" in master_cv_path.read_text(encoding="utf-8")
    assert hc_path.read_text(encoding="utf-8") == "Hong Kong only\n"
    page = client.get("/candidate")
    assert "Python" in page.text
    assert str(hc_path.resolve()) in page.text


def test_crawl_page_uses_assistant_for_login_filters_and_run() -> None:
    assistant = _RecordingAssistant()
    client = TestClient(create_app(assistant))

    page = client.get("/crawl")
    assert page.status_code == 200
    assert "User-Attended Login" in page.text
    assert "Crawl Filters" in page.text
    assert "finish DUO" in page.text

    login = client.post("/crawl/login", follow_redirects=False)
    assert login.status_code == 303
    assert assistant.login_calls == 1

    filters = client.post(
        "/crawl/filters",
        data={
            "business_natures": "IT",
            "active_job": "1",
            "deadline_hardline": "2026-09-01",
        },
        follow_redirects=False,
    )
    assert filters.status_code == 303
    assert assistant.crawl_filters.business_natures == ("IT",)
    assert assistant.crawl_filters.active_job is True
    assert assistant.crawl_filters.deadline_hardline is not None
    assert assistant.crawl_filters.deadline_hardline.isoformat() == "2026-09-01"

    run = client.post("/crawl/run", data={"full_refresh": "1"}, follow_redirects=False)
    assert run.status_code == 303
    assert assistant.crawl_calls == [True]
    after = client.get("/crawl")
    assert "Last Crawl: completed" in after.text


def test_catalog_prepare_and_packet_routes_use_assistant() -> None:
    assistant = _RecordingAssistant()
    assistant.summaries = [
        AssessmentSummary(
            job_posting_id="86534",
            title="System Engineer",
            employer="Example Corp",
            listing_status="Open",
            deadline_status="Upcoming",
            pending=False,
            hard_constraint_outcome="pass",
            preference="Strong",
            relevance="Strong",
            has_preparation_packet=False,
        )
    ]
    client = TestClient(create_app(assistant))

    catalog = client.get("/")
    assert catalog.status_code == 200
    assert "Prepare" in catalog.text
    assert "Prepare unavailable" not in catalog.text

    prepare = client.post("/jobs/86534/prepare", follow_redirects=False)
    assert prepare.status_code == 303
    assert prepare.headers["location"] == "/jobs/86534/packet"
    assert assistant.prepare_calls == ["86534"]

    packet = PreparationPacket(
        job_posting_id="86534",
        gap_report=GapReport(),
        edit_summary=EditSummary(omissions=("Dropped unused bullet",)),
        tailored_yaml="cv:\n  name: Tailored\n",
        pdf_bytes=b"%PDF-1.4",
    )
    assistant.packet_views["86534"] = PreparationPacketView(
        packet=packet, match_assessment=None
    )
    assistant.summaries[0] = AssessmentSummary(
        job_posting_id="86534",
        title="System Engineer",
        employer="Example Corp",
        listing_status="Open",
        deadline_status="Upcoming",
        pending=False,
        hard_constraint_outcome="pass",
        preference="Strong",
        relevance="Strong",
        has_preparation_packet=True,
    )

    view = client.get("/jobs/86534/packet")
    assert view.status_code == 200
    assert "Gap Report" in view.text
    assert "Edit Summary" in view.text
    assert "Dropped unused bullet" in view.text
    assert "Download Tailored YAML" in view.text
    assert "Download Tailored PDF" in view.text

    yaml_resp = client.get("/jobs/86534/packet/yaml")
    assert yaml_resp.status_code == 200
    assert "Tailored" in yaml_resp.text
    pdf_resp = client.get("/jobs/86534/packet/pdf")
    assert pdf_resp.status_code == 200
    assert pdf_resp.content.startswith(b"%PDF")


def test_catalog_delete_route_uses_assistant_with_confirm() -> None:
    assistant = _RecordingAssistant()
    assistant.delete_needs_confirm = True
    assistant.summaries = [
        AssessmentSummary(
            job_posting_id="86534",
            title="System Engineer",
            employer="Example Corp",
            listing_status="Open",
            deadline_status="Upcoming",
            pending=False,
            hard_constraint_outcome="pass",
            preference="Strong",
            relevance="Strong",
            has_preparation_packet=True,
        )
    ]
    client = TestClient(create_app(assistant))

    catalog = client.get("/")
    assert catalog.status_code == 200
    assert "Delete" in catalog.text

    needs_confirm = client.post("/jobs/86534/delete", follow_redirects=False)
    assert needs_confirm.status_code == 200
    assert "Confirm Delete" in needs_confirm.text
    assert "System Engineer" in needs_confirm.text
    assert "Match Assessment" in needs_confirm.text
    assert "Preparation Packet" in needs_confirm.text
    assert assistant.delete_calls == [("86534", False)]

    confirmed = client.post(
        "/jobs/86534/delete",
        data={"confirm": "1"},
        follow_redirects=False,
    )
    assert confirmed.status_code == 303
    assert confirmed.headers["location"] == "/"
    assert assistant.delete_calls == [("86534", False), ("86534", True)]


def test_catalog_links_to_match_assessment_detail_page() -> None:
    assistant = _RecordingAssistant()
    assistant.summaries = [
        AssessmentSummary(
            job_posting_id="86534",
            title="System Engineer",
            employer="Example Corp",
            listing_status="Open",
            deadline_status="Upcoming",
            pending=False,
            hard_constraint_outcome="pass",
            preference="Strong",
            relevance="Mixed",
        )
    ]
    client = TestClient(create_app(assistant))

    response = client.get("/")

    assert response.status_code == 200
    assert 'href="/jobs/86534"' in response.text
    assert "Override" not in response.text


def test_match_assessment_detail_page_uses_assistant_and_shows_signals() -> None:
    assistant = _RecordingAssistant()
    assistant.summaries = [
        AssessmentSummary(
            job_posting_id="86534",
            title="System Engineer",
            employer="Example Corp",
            listing_status="Open",
            deadline_status="Upcoming",
            pending=False,
            hard_constraint_outcome="fail",
            preference="Mixed",
            relevance="Strong",
        )
    ]
    assistant.match_assessments["86534"] = MatchAssessment(
        job_posting_id="86534",
        hard_constraint_outcome="fail",
        hard_constraint_reason="Requires relocation outside Hong Kong",
        preference="Mixed",
        preference_reason="Fintech preferred but role is general IT",
        relevance="Strong",
        evidence=[
            EvidencePair(
                job_excerpt="Python platform work",
                candidate_excerpt="Platform engineer at Example",
                role="supports Relevance",
            ),
            EvidencePair(
                job_excerpt="On-call rotation",
                candidate_excerpt="not found",
                role="weakens Relevance",
            ),
        ],
    )
    client = TestClient(create_app(assistant))

    response = client.get("/jobs/86534")

    assert response.status_code == 200
    assert assistant.get_match_assessment_calls == ["86534"]
    assert "Match Assessment" in response.text
    assert "System Engineer" in response.text
    assert "Example Corp" in response.text
    assert "Hard Constraint" in response.text
    assert "fail" in response.text
    assert "Requires relocation outside Hong Kong" in response.text
    assert "Preference" in response.text
    assert "Mixed" in response.text
    assert "Fintech preferred but role is general IT" in response.text
    assert "Relevance" in response.text
    assert "Strong" in response.text
    assert "Python platform work" in response.text
    assert "Platform engineer at Example" in response.text
    assert "supports Relevance" in response.text
    assert "On-call rotation" in response.text
    assert 'action="/jobs/86534/prepare"' in response.text
    assert 'action="/jobs/86534/delete"' in response.text
    assert "Override" not in response.text
    assert "accordion" not in response.text.lower()


def test_match_assessment_detail_pending_blocks_prepare_and_shows_clear_state() -> None:
    assistant = _RecordingAssistant()
    assistant.summaries = [
        AssessmentSummary(
            job_posting_id="86534",
            title="System Engineer",
            employer="Example Corp",
            listing_status="Open",
            deadline_status="Upcoming",
            pending=True,
        )
    ]
    assistant.llm_unavailable_reason = "LLM Unavailable: API key not configured"
    client = TestClient(create_app(assistant))

    response = client.get("/jobs/86534")

    assert response.status_code == 200
    assert assistant.get_match_assessment_calls == ["86534"]
    assert "Pending" in response.text
    assert "Prepare unavailable" in response.text
    assert "LLM Unavailable: API key not configured" in response.text
    assert 'action="/jobs/86534/prepare"' not in response.text
    assert 'action="/jobs/86534/delete"' in response.text


def test_match_assessment_detail_missing_posting_redirects_home() -> None:
    assistant = _RecordingAssistant()
    client = TestClient(create_app(assistant))

    response = client.get("/jobs/missing", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/"


def test_match_assessment_detail_with_wired_assistant_shows_evidence(
    tmp_path: Path,
) -> None:
    cv_path = tmp_path / "master_CV.yaml"
    cv_path.write_text(
        "cv:\n  name: Test\n  sections:\n    experience:\n"
        "      - company: Example\n        position: Platform engineer\n",
        encoding="utf-8",
    )
    hc_path = tmp_path / "hard.txt"
    hc_path.write_text("Hong Kong only\n", encoding="utf-8")
    prefs_path = tmp_path / "prefs.txt"
    prefs_path.write_text("Prefer fintech\n", encoding="utf-8")
    entry = JobListEntry(
        id="86534",
        title="System Engineer",
        employer="Example Corp",
        posting_date="2026-07-01",
        application_deadline="2026-12-31",
    )
    detail = JobPostingDetail(
        id="86534",
        title="System Engineer",
        employer="Example Corp",
        posting_date="2026-07-01",
        application_deadline="2026-12-31",
        fields={"Job Description": "Build reliable systems in Python."},
    )
    evidence = [
        EvidencePair(
            job_excerpt="Build reliable systems in Python.",
            candidate_excerpt="Platform engineer at Example",
            role="supports Relevance",
        )
    ]
    assistant = Assistant(
        catalog_store=CatalogStore(tmp_path / "catalog.db"),
        job_board=FakeJobBoardSession(
            authenticated=True,
            list_entries=[entry],
            details={"86534": detail},
        ),
        master_cv=FakeMasterCvStore(),
        llm_judge=FakeLlmJudge(
            hard_constraint_outcome="pass",
            hard_constraint_reason="No hard constraint violations",
            preference="Strong",
            preference_reason="Matches preferred domain",
            relevance="Strong",
            evidence=evidence,
        ),
        llm_cv_tailor=FakeLlmCvTailor(),
        constraint_files=FakeConstraintFilesStore(),
        crawl_pacer=FakeCrawlPacer(),
    )
    assistant.set_master_cv_path(str(cv_path))
    assistant.set_hard_constraints_path(str(hc_path))
    assistant.set_preferences_path(str(prefs_path))
    assert assistant.run_crawl().stored_count == 1
    assistant.rejudge_pending_assessments()

    client = TestClient(create_app(assistant))
    catalog = client.get("/")
    assert 'href="/jobs/86534"' in catalog.text

    response = client.get("/jobs/86534")
    assert response.status_code == 200
    assert "No hard constraint violations" in response.text
    assert "Matches preferred domain" in response.text
    assert "Build reliable systems in Python." in response.text
    assert "Platform engineer at Example" in response.text
    assert 'action="/jobs/86534/prepare"' in response.text
    assert 'action="/jobs/86534/delete"' in response.text
