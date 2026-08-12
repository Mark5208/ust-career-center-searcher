"""UI route talks only to Assistant for Assessment Summary listing."""

from pathlib import Path

from fastapi.testclient import TestClient

from job_finding_assistant.assistant import (
    AssessmentSummary,
    AssessmentSummaryCatalog,
    AssessmentSummaryCatalogRow,
    Assistant,
    BulkDeleteConfirmItem,
    BulkDeleteNeedsConfirm,
    BulkDeleteResult,
    BulkPrepareConfirmItem,
    BulkPrepareNeedsConfirm,
    BulkPrepareResult,
    CandidateFilesView,
    CrawlFilters,
    CrawlOutcome,
    DeleteNeedsConfirm,
    EnrichmentSessionView,
    LlmRunAlreadyInFlight,
    LlmRunStatus,
    MatchAssessmentPage,
    PreparationPacketPage,
    PreparationPacketView,
)
from job_finding_assistant.candidate_snapshot import CandidateSnapshot
from job_finding_assistant.catalog_store import CatalogStore
from job_finding_assistant.constraint_files_store import DiskConstraintFilesStore
from job_finding_assistant.enrichment import PlacementSuggestion
from job_finding_assistant.fakes import (
    FakeConstraintFilesStore,
    FakeJobBoardSession,
    FakeLlmCvEnricher,
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
        self.catalog_load_calls = 0
        self.catalog_load_kwargs: dict[str, bool] = {}
        self.summaries: list[AssessmentSummary] = []
        self.match_assessment_page_calls: list[str] = []
        self.preparation_packet_page_calls: list[str] = []
        self.rejudge_calls = 0
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
        self.packet_views: dict[str, PreparationPacketView] = {}
        self.delete_calls: list[tuple[str, bool]] = []
        self.delete_needs_confirm = False
        self.delete_confirm_reason = (
            "Delete permanently removes Job Posting 'System Engineer — Example Corp', "
            "Match Assessment, and Preparation Packet. No undo."
        )
        self.bulk_prepare_calls: list[tuple[list[str], bool]] = []
        self.bulk_prepare_llm_run_calls: list[tuple[list[str], bool]] = []
        self.catalog_assess_llm_run_calls = 0
        self.stop_llm_run_calls = 0
        self.bulk_delete_calls: list[tuple[list[str], bool]] = []
        self.bulk_prepare_needs_confirm = False
        self.bulk_delete_needs_confirm = False
        self.bulk_prepare_result = BulkPrepareResult(
            prepared=[], skipped=[], failed=[], stopped=[]
        )
        self.bulk_delete_result = BulkDeleteResult(deleted=[])
        self.match_assessments: dict[str, MatchAssessment] = {}
        self.llm_run_status = LlmRunStatus(active=False)
        self.llm_run_already_in_flight = False

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
            pending_remaining=(
                self.pending_remaining if self.pending_remaining else pending
            ),
            llm_unavailable_reason=self.llm_unavailable_reason,
            llm_run=self.llm_run_status,
        )

    def load_match_assessment_page(
        self, job_posting_id: str
    ) -> MatchAssessmentPage | None:
        self.match_assessment_page_calls.append(job_posting_id)
        for summary in self.summaries:
            if summary.job_posting_id != job_posting_id:
                continue
            return MatchAssessmentPage(
                summary=summary,
                match_assessment=self.match_assessments.get(job_posting_id),
                can_prepare=not summary.pending,
                llm_unavailable_reason=self.llm_unavailable_reason,
            )
        return None

    def load_preparation_packet_page(
        self, job_posting_id: str
    ) -> PreparationPacketPage | None:
        self.preparation_packet_page_calls.append(job_posting_id)
        view = self.packet_views.get(job_posting_id)
        if view is None:
            return None
        title = job_posting_id
        employer = ""
        for summary in self.summaries:
            if summary.job_posting_id == job_posting_id:
                title = summary.title
                employer = summary.employer
                break
        return PreparationPacketPage(
            title=title,
            employer=employer,
            packet=view.packet,
            match_assessment=view.match_assessment,
        )

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

    def bulk_prepare(
        self, job_posting_ids: list[str], *, confirm: bool = False
    ) -> BulkPrepareResult:
        self.bulk_prepare_calls.append((list(job_posting_ids), confirm))
        return self.bulk_prepare_result

    def start_bulk_prepare_llm_run(
        self, job_posting_ids: list[str], *, confirm: bool = False
    ) -> LlmRunStatus:
        self.bulk_prepare_llm_run_calls.append((list(job_posting_ids), confirm))
        if self.llm_run_already_in_flight:
            raise LlmRunAlreadyInFlight(
                "Already judging… stop or wait for the current LLM Run."
            )
        if self.bulk_prepare_needs_confirm and not confirm:
            raise BulkPrepareNeedsConfirm(
                [
                    BulkPrepareConfirmItem(
                        job_posting_id=job_posting_ids[0],
                        title="System Engineer",
                        employer="Example Corp",
                        kind="hard_constraint_fail",
                        reason="Requires relocation outside Hong Kong",
                    )
                ],
                selected_ids=list(job_posting_ids),
                eligible_ids=list(job_posting_ids),
                skipped_ids=[],
            )
        self.llm_run_status = LlmRunStatus(
            active=True,
            phase="Preparing",
            current_index=1,
            total=max(1, len(job_posting_ids)),
        )
        return self.llm_run_status

    def start_catalog_assess_llm_run(self) -> LlmRunStatus:
        self.catalog_assess_llm_run_calls += 1
        if self.llm_run_already_in_flight:
            raise LlmRunAlreadyInFlight(
                "Already judging… stop or wait for the current LLM Run."
            )
        self.llm_run_status = LlmRunStatus(
            active=True,
            phase="Judging",
            job_posting_id="86534",
            title="System Engineer",
            employer="Example Corp",
            current_index=1,
            total=5,
        )
        return self.llm_run_status

    def get_llm_run_status(self) -> LlmRunStatus:
        return self.llm_run_status

    def stop_llm_run(self) -> LlmRunStatus:
        self.stop_llm_run_calls += 1
        self.llm_run_status = LlmRunStatus(
            active=self.llm_run_status.active,
            phase=self.llm_run_status.phase,
            job_posting_id=self.llm_run_status.job_posting_id,
            title=self.llm_run_status.title,
            employer=self.llm_run_status.employer,
            current_index=self.llm_run_status.current_index,
            total=self.llm_run_status.total,
            stop_requested=True,
            message=self.llm_run_status.message,
            bulk_prepare_result=self.llm_run_status.bulk_prepare_result,
        )
        return self.llm_run_status

    def bulk_delete(
        self, job_posting_ids: list[str], *, confirm: bool = False
    ) -> BulkDeleteResult:
        self.bulk_delete_calls.append((list(job_posting_ids), confirm))
        if self.bulk_delete_needs_confirm and not confirm:
            raise BulkDeleteNeedsConfirm(
                [
                    BulkDeleteConfirmItem(
                        job_posting_id=job_id,
                        title="System Engineer",
                        employer="Example Corp",
                        has_match_assessment=True,
                        has_preparation_packet=True,
                    )
                    for job_id in job_posting_ids
                ]
            )
        return self.bulk_delete_result

    def rejudge_pending_assessments(self) -> None:
        self.rejudge_calls += 1

    def get_candidate_files(self) -> CandidateFilesView:
        return CandidateFilesView(
            master_cv_path=self.master_cv_path,
            hard_constraints_path=self.hard_constraints_path,
            preferences_path=self.preferences_path,
            snapshot=self.snapshot,
            errors=list(self.candidate_file_errors),
        )

    def set_master_cv_path(self, path: str) -> None:
        self.set_master_cv_calls.append(path)
        self.master_cv_path = path

    def set_hard_constraints_path(self, path: str) -> None:
        self.set_hard_constraints_calls.append(path)
        self.hard_constraints_path = path

    def clear_hard_constraints_path(self) -> None:
        self.clear_hard_constraints_calls += 1
        self.hard_constraints_path = None

    def set_preferences_path(self, path: str) -> None:
        self.set_preferences_calls.append(path)
        self.preferences_path = path

    def clear_preferences_path(self) -> None:
        self.clear_preferences_calls += 1
        self.preferences_path = None

    def start_enrichment_session(self) -> EnrichmentSessionView:
        self.enrichment_session = EnrichmentSessionView(step="freeform")
        return self.enrichment_session

    def get_enrichment_session(self) -> EnrichmentSessionView | None:
        return getattr(self, "enrichment_session", None)

    def submit_enrichment_freeform(self, description: str) -> EnrichmentSessionView:
        self.enrichment_freeform_calls = getattr(self, "enrichment_freeform_calls", [])
        self.enrichment_freeform_calls.append(description)
        self.enrichment_session = EnrichmentSessionView(
            step="placement",
            freeform=description,
            placement=PlacementSuggestion(
                section="experience",
                mode="existing",
                entry_index=0,
                label="Software Intern at Acme Corp",
            ),
        )
        return self.enrichment_session

    def confirm_enrichment_placement(
        self,
        *,
        company: str | None = None,
        position: str | None = None,
        name: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> EnrichmentSessionView:
        del company, position, name, start_date, end_date
        self.enrichment_session = EnrichmentSessionView(
            step="dimension",
            freeform=self.enrichment_session.freeform if self.enrichment_session else "",
            current_dimension="problem_context",
            dimension_prompt="What problem or context were you working in?",
        )
        return self.enrichment_session

    def submit_enrichment_dimension(self, answer: str) -> EnrichmentSessionView:
        del answer
        return self.enrichment_session or EnrichmentSessionView(step="dimension")

    def skip_enrichment_dimension(self) -> EnrichmentSessionView:
        return self.enrichment_session or EnrichmentSessionView(step="dimension")

    def set_enrichment_highlights(self, highlights: list[str]) -> EnrichmentSessionView:
        self.enrichment_session = EnrichmentSessionView(
            step="highlights", highlights=list(highlights)
        )
        return self.enrichment_session

    def confirm_enrichment_write(self) -> EnrichmentSessionView:
        self.enrichment_session = EnrichmentSessionView(step="done")
        return self.enrichment_session

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
    assert assistant.match_assessment_page_calls == []
    assert assistant.preparation_packet_page_calls == []
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
    assert "Strong" in response.text
    assert "pass" in response.text
    assert "Preference" in response.text
    assert "Bulk Prepare" in response.text
    assert "Bulk Delete" in response.text
    assert 'name="job_posting_ids"' in response.text
    assert 'id="select-all"' in response.text
    assert 'action="/jobs/86534/prepare"' not in response.text
    assert 'action="/jobs/86534/delete"' not in response.text
    assert "Prepare unavailable" not in response.text
    assert assistant.catalog_load_calls == 1
    assert assistant.match_assessment_page_calls == []


def test_catalog_page_shows_llm_run_controls_and_pending_count() -> None:
    assistant = _RecordingAssistant()
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
    assert "7 Pending" in response.text
    assert "Assess Pending" in response.text
    assert 'action="/llm-run/assess"' in response.text
    assert "Processed 1 Pending this load" not in response.text


def test_catalog_page_shows_active_llm_run_status_and_stop() -> None:
    assistant = _RecordingAssistant()
    assistant.pending_remaining = 3
    assistant.llm_run_status = LlmRunStatus(
        active=True,
        phase="Judging",
        job_posting_id="86534",
        title="System Engineer",
        employer="Example Corp",
        current_index=2,
        total=5,
    )
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
    assert "Judging:" in response.text
    assert "System Engineer — Example Corp" in response.text
    assert "2 of 5" in response.text
    assert 'action="/llm-run/stop"' in response.text
    assert "Assess Pending" not in response.text


def test_catalog_llm_run_routes_use_assistant() -> None:
    assistant = _RecordingAssistant()
    client = TestClient(create_app(assistant))

    start = client.post("/llm-run/assess", follow_redirects=False)
    assert start.status_code == 303
    assert assistant.catalog_assess_llm_run_calls == 1

    status = client.get("/llm-run/status")
    assert status.status_code == 200
    assert status.json()["active"] is True
    assert status.json()["phase"] == "Judging"

    stop = client.post(
        "/llm-run/stop",
        headers={"Accept": "application/json"},
    )
    assert stop.status_code == 200
    assert assistant.stop_llm_run_calls == 1
    assert stop.json()["stop_requested"] is True


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


def test_catalog_get_is_fast_and_assess_llm_run_drains_until_empty(
    tmp_path: Path,
) -> None:
    """GET / does not judge; explicit assess LLM Run drains until empty (ADR-0015)."""
    import time

    cv_path = tmp_path / "master_CV.yaml"
    cv_path.write_text(
        "cv:\n  name: Test\n  sections:\n    experience:\n      - company: X\n        position: Y\n",
        encoding="utf-8",
    )
    entries = [
        JobListEntry(
            id=str(86534 + i),
            title=f"Engineer {i}",
            employer=f"Corp {i}",
            posting_date="2026-07-01",
            application_deadline="2026-12-31",
        )
        for i in range(6)
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
    judge = FakeLlmJudge(relevance="Strong")
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
    )
    assistant.set_master_cv_path(str(cv_path))
    assistant.run_crawl()
    assert len(assistant.list_assessment_summaries()) == 6
    assert all(row.pending for row in assistant.list_assessment_summaries())

    client = TestClient(create_app(assistant))
    response = client.get("/")

    assert response.status_code == 200
    assert judge.judge_calls == 0
    assert "6 Pending" in response.text
    assert "Assess Pending" in response.text

    start = client.post("/llm-run/assess", follow_redirects=False)
    assert start.status_code == 303
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and assistant.get_llm_run_status().active:
        time.sleep(0.01)
    assert not assistant.get_llm_run_status().active
    assert judge.judge_calls == 6
    pending_after = sum(
        1 for row in assistant.list_assessment_summaries() if row.pending
    )
    assert pending_after == 0


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
    assert "/candidate/enrichment" in response.text
    assert "Master CV Enrichment" in response.text


def test_enrichment_page_posts_freeform_through_assistant() -> None:
    assistant = _RecordingAssistant()
    assistant.master_cv_path = "/tmp/master_CV.yaml"
    assistant.snapshot = CandidateSnapshot(
        contact="Alice",
        education=[],
        experience=["Software Intern at Acme Corp"],
        projects=[],
        skills_tools=[],
    )
    client = TestClient(create_app(assistant))

    page = client.get("/candidate/enrichment")
    assert page.status_code == 200
    assert "Describe an experience" in page.text

    response = client.post(
        "/candidate/enrichment/freeform",
        data={"description": "Led a reporting dashboard"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert assistant.enrichment_freeform_calls == ["Led a reporting dashboard"]
    placed = client.get("/candidate/enrichment")
    assert "Confirm placement" in placed.text


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
    files = assistant.get_candidate_files()
    assert files.master_cv_path == str(master_cv_path.resolve())
    assert files.hard_constraints_path == str(hc_path.resolve())
    assert files.preferences_path == str(prefs_path.resolve())
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


def test_catalog_bulk_prepare_and_packet_routes_use_assistant() -> None:
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
    assistant.bulk_prepare_result = BulkPrepareResult(
        prepared=["86534"], skipped=[], failed=[], stopped=[]
    )
    client = TestClient(create_app(assistant))

    catalog = client.get("/")
    assert catalog.status_code == 200
    assert "Bulk Prepare" in catalog.text
    assert 'action="/jobs/86534/prepare"' not in catalog.text

    prepare = client.post(
        "/bulk/prepare",
        data={"job_posting_ids": ["86534"]},
        follow_redirects=False,
    )
    assert prepare.status_code == 303
    assert prepare.headers["location"] == "/"
    assert assistant.bulk_prepare_llm_run_calls == [(["86534"], False)]

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


def test_packet_page_shows_pdf_missing_reasons_instead_of_bare_missing() -> None:
    """ADR-0013 revisit: a missing PDF carries short reason lines, not a bare notice."""
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
            has_preparation_packet=True,
        )
    ]
    packet = PreparationPacket(
        job_posting_id="86534",
        gap_report=GapReport(),
        edit_summary=EditSummary(),
        tailored_yaml="cv:\n  name: Tailored\n",
        pdf_bytes=None,
        pdf_missing_reasons=(
            "cv.sections.experience.0.position: This field is required.",
        ),
    )
    assistant.packet_views["86534"] = PreparationPacketView(
        packet=packet, match_assessment=None
    )
    client = TestClient(create_app(assistant))

    view = client.get("/jobs/86534/packet")

    assert view.status_code == 200
    assert "This field is required" in view.text
    assert "Download Tailored PDF" not in view.text


def test_catalog_bulk_prepare_shows_combined_confirm() -> None:
    assistant = _RecordingAssistant()
    assistant.bulk_prepare_needs_confirm = True
    assistant.summaries = [
        AssessmentSummary(
            job_posting_id="86534",
            title="System Engineer",
            employer="Example Corp",
            listing_status="Open",
            deadline_status="Upcoming",
            pending=False,
            hard_constraint_outcome="fail",
            preference="Strong",
            relevance="Strong",
        )
    ]
    client = TestClient(create_app(assistant))

    needs_confirm = client.post(
        "/bulk/prepare",
        data={"job_posting_ids": ["86534"]},
        follow_redirects=False,
    )
    assert needs_confirm.status_code == 200
    assert "Confirm Bulk Prepare" in needs_confirm.text
    assert "Requires relocation outside Hong Kong" in needs_confirm.text
    assert assistant.bulk_prepare_llm_run_calls == [(["86534"], False)]

    confirmed = client.post(
        "/bulk/prepare",
        data={"job_posting_ids": ["86534"], "confirm": "1"},
        follow_redirects=False,
    )
    assert confirmed.status_code == 303
    assert confirmed.headers["location"] == "/"
    assert assistant.bulk_prepare_llm_run_calls == [
        (["86534"], False),
        (["86534"], True),
    ]


def test_catalog_bulk_delete_uses_assistant_with_confirm() -> None:
    assistant = _RecordingAssistant()
    assistant.bulk_delete_needs_confirm = True
    assistant.bulk_delete_result = BulkDeleteResult(deleted=["86534"])
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
    assert "Bulk Delete" in catalog.text
    assert 'action="/jobs/86534/delete"' not in catalog.text

    needs_confirm = client.post(
        "/bulk/delete",
        data={"job_posting_ids": ["86534"]},
        follow_redirects=False,
    )
    assert needs_confirm.status_code == 200
    assert "Confirm Bulk Delete" in needs_confirm.text
    assert "System Engineer" in needs_confirm.text
    assert "Match Assessment" in needs_confirm.text
    assert "Preparation Packet" in needs_confirm.text
    assert assistant.bulk_delete_calls == [(["86534"], False)]

    confirmed = client.post(
        "/bulk/delete",
        data={"job_posting_ids": ["86534"], "confirm": "1"},
        follow_redirects=False,
    )
    assert confirmed.status_code == 303
    assert confirmed.headers["location"] == "/"
    assert assistant.bulk_delete_calls == [(["86534"], False), (["86534"], True)]


def test_match_assessment_detail_keeps_single_prepare_and_delete() -> None:
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
        )
    ]
    assistant.match_assessments["86534"] = MatchAssessment(
        job_posting_id="86534",
        hard_constraint_outcome="pass",
        hard_constraint_reason="No hard constraint violations",
        preference="Strong",
        preference_reason="Fits preferences",
        relevance="Strong",
        evidence=[],
        hard_constraint_evidence=[],
        preference_evidence=[],
    )
    client = TestClient(create_app(assistant))

    detail = client.get("/jobs/86534")
    assert detail.status_code == 200
    assert 'action="/jobs/86534/prepare"' in detail.text
    assert 'action="/jobs/86534/delete"' in detail.text

    prepare = client.post("/jobs/86534/prepare", follow_redirects=False)
    assert prepare.status_code == 303
    assert prepare.headers["location"] == "/jobs/86534/packet"
    assert assistant.prepare_calls == ["86534"]

    needs_confirm = client.post("/jobs/86534/delete", follow_redirects=False)
    assert needs_confirm.status_code == 200
    assert "Confirm Delete" in needs_confirm.text
    assert assistant.delete_calls == [("86534", False)]


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
        hard_constraint_evidence=[
            EvidencePair(
                job_excerpt="Work Location: Singapore",
                candidate_excerpt="Hong Kong only",
                role="violates Hard Constraint",
            )
        ],
        preference_evidence=[
            EvidencePair(
                job_excerpt="General IT support",
                candidate_excerpt="Prefer fintech",
                role="weakens Preference",
            )
        ],
    )
    client = TestClient(create_app(assistant))

    response = client.get("/jobs/86534")

    assert response.status_code == 200
    assert assistant.match_assessment_page_calls == ["86534"]
    assert assistant.catalog_load_calls == 0
    assert "Match Assessment" in response.text
    assert "System Engineer" in response.text
    assert "Example Corp" in response.text
    assert "Hard Constraint" in response.text
    assert "fail" in response.text
    assert "Requires relocation outside Hong Kong" in response.text
    assert "Hard Constraint Evidence" in response.text
    assert "Work Location: Singapore" in response.text
    assert "Hard Constraints file" in response.text
    assert "Hong Kong only" in response.text
    assert "Preference" in response.text
    assert "Mixed" in response.text
    assert "Fintech preferred but role is general IT" in response.text
    assert "Preference Evidence" in response.text
    assert "General IT support" in response.text
    assert "Preferences file" in response.text
    assert "Prefer fintech" in response.text
    assert "Relevance" in response.text
    assert "Strong" in response.text
    assert "Relevance Evidence" in response.text
    assert "Python platform work" in response.text
    assert "Candidate Snapshot" in response.text
    assert "Platform engineer at Example" in response.text
    assert "supports Relevance" in response.text
    assert "On-call rotation" in response.text
    assert 'action="/jobs/86534/prepare"' in response.text
    assert 'action="/jobs/86534/delete"' in response.text
    assert "Override" not in response.text
    assert "accordion" not in response.text.lower()
    assert "Signal Summary" in response.text
    assert 'href="#signal-hard-constraint"' in response.text
    assert 'href="#signal-preference"' in response.text
    assert 'href="#signal-relevance"' in response.text
    assert 'id="signal-hard-constraint"' in response.text
    assert 'id="signal-preference"' in response.text
    assert 'id="signal-relevance"' in response.text
    assert response.text.index("Signal Summary") < response.text.index(
        'id="signal-hard-constraint"'
    )
    assert response.text.index('id="signal-relevance"') < response.text.index(
        'action="/jobs/86534/prepare"'
    )
    assert '<details class="signal-section" id="signal-hard-constraint" open>' in response.text
    assert '<details class="signal-section" id="signal-preference" open>' in response.text
    assert '<details class="signal-section" id="signal-relevance" open>' in response.text
    assert response.text.count("<details ") == 3


def test_match_assessment_detail_shows_empty_evidence_states() -> None:
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
            preference=None,
            relevance="Strong",
        )
    ]
    assistant.match_assessments["86534"] = MatchAssessment(
        job_posting_id="86534",
        hard_constraint_outcome="pass",
        hard_constraint_reason="No hard constraint violations",
        preference=None,
        preference_reason="No Preferences file or file is empty",
        relevance="Strong",
        evidence=[],
        hard_constraint_evidence=[],
        preference_evidence=[],
    )
    client = TestClient(create_app(assistant))

    response = client.get("/jobs/86534")

    assert response.status_code == 200
    assert "No Hard Constraint Evidence pairs." in response.text
    assert "No Preference Evidence pairs." in response.text
    assert "No Relevance Evidence pairs." in response.text


def test_assessment_summary_stays_bands_only_without_evidence_lists() -> None:
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
            )
        ],
        hard_constraint_evidence=[
            EvidencePair(
                job_excerpt="Work Location: Singapore",
                candidate_excerpt="Hong Kong only",
                role="violates Hard Constraint",
            )
        ],
        preference_evidence=[
            EvidencePair(
                job_excerpt="General IT support",
                candidate_excerpt="Prefer fintech",
                role="weakens Preference",
            )
        ],
    )
    client = TestClient(create_app(assistant))

    response = client.get("/")

    assert response.status_code == 200
    assert "Hard Constraint: fail" in response.text
    assert "Preference: Mixed" in response.text
    assert "Relevance: Strong" in response.text
    assert "Hard Constraint Evidence" not in response.text
    assert "Preference Evidence" not in response.text
    assert "Relevance Evidence" not in response.text
    assert "Signal Summary" not in response.text
    assert "Signal Section" not in response.text
    assert "Hard Constraints file" not in response.text
    assert "Preferences file" not in response.text
    assert "Candidate Snapshot" not in response.text
    assert "Work Location: Singapore" not in response.text
    assert "Python platform work" not in response.text
    assert assistant.match_assessment_page_calls == []


def test_preparation_packet_keeps_compact_assessment_strip_with_link() -> None:
    assistant = _RecordingAssistant()
    assessment = MatchAssessment(
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
            )
        ],
        hard_constraint_evidence=[
            EvidencePair(
                job_excerpt="Work Location: Singapore",
                candidate_excerpt="Hong Kong only",
                role="violates Hard Constraint",
            )
        ],
        preference_evidence=[
            EvidencePair(
                job_excerpt="General IT support",
                candidate_excerpt="Prefer fintech",
                role="weakens Preference",
            )
        ],
    )
    assistant.packet_views["86534"] = PreparationPacketView(
        packet=PreparationPacket(
            job_posting_id="86534",
            gap_report=GapReport(),
            edit_summary=EditSummary(),
            tailored_yaml="cv:\n  name: Tailored\n",
            pdf_bytes=b"%PDF-1.4",
        ),
        match_assessment=assessment,
    )
    client = TestClient(create_app(assistant))

    response = client.get("/jobs/86534/packet")

    assert response.status_code == 200
    assert assistant.preparation_packet_page_calls == ["86534"]
    assert "Current Match Assessment" in response.text
    assert "Hard Constraint: fail" in response.text
    assert "Requires relocation outside Hong Kong" in response.text
    assert "Preference: Mixed" in response.text
    assert "Fintech preferred but role is general IT" in response.text
    assert "Relevance: Strong" in response.text
    assert 'href="/jobs/86534"' in response.text
    assert "Hard Constraint Evidence" not in response.text
    assert "Preference Evidence" not in response.text
    assert "Relevance Evidence" not in response.text
    assert "Signal Summary" not in response.text
    assert 'id="signal-hard-constraint"' not in response.text
    assert "Work Location: Singapore" not in response.text
    assert "Python platform work" not in response.text


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
    assert assistant.match_assessment_page_calls == ["86534"]
    assert assistant.catalog_load_calls == 0
    assert "Pending" in response.text
    assert "Prepare unavailable" in response.text
    assert "LLM Unavailable: API key not configured" in response.text
    assert 'action="/jobs/86534/prepare"' not in response.text
    assert 'action="/jobs/86534/delete"' in response.text
    assert "Signal Summary" not in response.text
    assert 'id="signal-hard-constraint"' not in response.text
    assert 'id="signal-preference"' not in response.text
    assert 'id="signal-relevance"' not in response.text
    assert "<details" not in response.text
    assert "Hard Constraint Evidence" not in response.text
    assert "No Hard Constraint Evidence pairs." not in response.text


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
    hc_evidence = [
        EvidencePair(
            job_excerpt="Work Location: Hong Kong",
            candidate_excerpt="Hong Kong only",
            role="supports Hard Constraint",
        )
    ]
    preference_evidence = [
        EvidencePair(
            job_excerpt="Fintech product team",
            candidate_excerpt="Prefer fintech",
            role="supports Preference",
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
            hard_constraint_evidence=hc_evidence,
            preference="Strong",
            preference_reason="Matches preferred domain",
            preference_evidence=preference_evidence,
            relevance="Strong",
            evidence=evidence,
        ),
        llm_cv_tailor=FakeLlmCvTailor(),
        constraint_files=FakeConstraintFilesStore(),
    )
    assistant.set_master_cv_path(str(cv_path))
    assistant.set_hard_constraints_path(str(hc_path))
    assistant.set_preferences_path(str(prefs_path))
    assert assistant.run_crawl().stored_count == 1
    assistant.rejudge_pending_assessments()

    client = TestClient(create_app(assistant))
    catalog = client.get("/")
    assert 'href="/jobs/86534"' in catalog.text
    assert "Hard Constraint Evidence" not in catalog.text
    assert "Preference Evidence" not in catalog.text

    response = client.get("/jobs/86534")
    assert response.status_code == 200
    assert "No hard constraint violations" in response.text
    assert "Matches preferred domain" in response.text
    assert "Hard Constraints file" in response.text
    assert "Hong Kong only" in response.text
    assert "Preferences file" in response.text
    assert "Prefer fintech" in response.text
    assert "Candidate Snapshot" in response.text
    assert "Build reliable systems in Python." in response.text
    assert "Platform engineer at Example" in response.text
    assert 'action="/jobs/86534/prepare"' in response.text
    assert 'action="/jobs/86534/delete"' in response.text
