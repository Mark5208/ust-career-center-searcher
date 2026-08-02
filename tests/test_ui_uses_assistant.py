"""UI route talks only to Assistant for Assessment Summary listing."""

from pathlib import Path

from fastapi.testclient import TestClient

from job_finding_assistant.assistant import (
    AssessmentSummary,
    Assistant,
    CrawlFilters,
    CrawlOutcome,
    GapTolerance,
    LanguagePreference,
    Preferences,
)
from job_finding_assistant.candidate_snapshot import CandidateSnapshot
from job_finding_assistant.catalog_store import CatalogStore
from job_finding_assistant.fakes import (
    FakeJobBoardSession,
    FakeLlmCvTailor,
    FakeLlmJudge,
    FakeMasterCvStore,
)
from job_finding_assistant.master_cv_store import DiskMasterCvStore
from job_finding_assistant.web.app import create_app


class _RecordingAssistant:
    """Stand-in that proves the route calls Assistant, not CatalogStore directly."""

    def __init__(self) -> None:
        self.list_calls = 0
        self.master_cv_path: str | None = None
        self.snapshot: CandidateSnapshot | None = None
        self.preferences = Preferences(languages=[], locations=[], gap_tolerance=None)
        self.crawl_filters = CrawlFilters()
        self.set_master_cv_calls: list[str] = []
        self.update_preferences_calls: list[Preferences] = []
        self.login_calls = 0
        self.crawl_calls: list[bool] = []
        self._can_start_crawl = False

    def list_assessment_summaries(self) -> list[AssessmentSummary]:
        self.list_calls += 1
        return []

    def get_master_cv_path(self) -> str | None:
        return self.master_cv_path

    def set_master_cv_path(self, path: str) -> None:
        self.set_master_cv_calls.append(path)
        self.master_cv_path = path

    def get_candidate_snapshot(self) -> CandidateSnapshot | None:
        return self.snapshot

    def get_preferences(self) -> Preferences:
        return self.preferences

    def update_preferences(self, preferences: Preferences) -> None:
        self.update_preferences_calls.append(preferences)
        self.preferences = preferences

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
    assert assistant.list_calls == 1
    assert "Assessment Summary" in response.text
    assert "No Job Postings" in response.text


def test_catalog_page_with_wired_assistant_shows_empty_catalog(tmp_path: Path) -> None:
    assistant = Assistant(
        catalog_store=CatalogStore(tmp_path / "catalog.db"),
        job_board=FakeJobBoardSession(),
        master_cv=FakeMasterCvStore(),
        llm_judge=FakeLlmJudge(),
        llm_cv_tailor=FakeLlmCvTailor(),
    )
    client = TestClient(create_app(assistant))

    response = client.get("/")

    assert response.status_code == 200
    assert "No Job Postings" in response.text


def test_candidate_page_calls_assistant_for_snapshot_and_preferences() -> None:
    assistant = _RecordingAssistant()
    assistant.master_cv_path = "/tmp/master.tex"
    assistant.snapshot = CandidateSnapshot(
        contact="Alice Example, alice@example.com",
        education=["BEng Computer Science, HKUST, 2024"],
        experience=["Software Intern at Acme Corp"],
        projects=["Campus Event Finder"],
        skills_tools=["Python, LaTeX, SQLite"],
    )
    assistant.preferences = Preferences(
        languages=[LanguagePreference(language="English", level="Fluent")],
        locations=["Hong Kong"],
        gap_tolerance=GapTolerance.YEAR,
    )
    client = TestClient(create_app(assistant))

    response = client.get("/candidate")

    assert response.status_code == 200
    assert "Candidate Snapshot" in response.text
    assert "Alice Example, alice@example.com" in response.text
    assert "Preferences" in response.text
    assert "English" in response.text
    assert "Hong Kong" in response.text
    assert "Year" in response.text
    assert "Crawl Filters" not in response.text


def test_candidate_page_posts_master_cv_path_and_preferences_through_assistant(
    tmp_path: Path,
) -> None:
    master_cv_path = tmp_path / "master.tex"
    master_cv_path.write_text(
        r"\documentclass{article}\begin{document}"
        r"\section{Skills}Python\end{document}",
        encoding="utf-8",
    )
    assistant = Assistant(
        catalog_store=CatalogStore(tmp_path / "catalog.db"),
        job_board=FakeJobBoardSession(),
        master_cv=DiskMasterCvStore(tmp_path / "master_cv_state"),
        llm_judge=FakeLlmJudge(),
        llm_cv_tailor=FakeLlmCvTailor(),
    )
    client = TestClient(create_app(assistant))

    path_response = client.post(
        "/candidate/master-cv",
        data={"master_cv_path": str(master_cv_path)},
        follow_redirects=False,
    )
    prefs_response = client.post(
        "/candidate/preferences",
        data={
            "languages": "English:Fluent\nCantonese",
            "locations": "Hong Kong\nRemote",
            "gap_tolerance": "Semester",
        },
        follow_redirects=False,
    )

    assert path_response.status_code == 303
    assert prefs_response.status_code == 303
    assert assistant.get_master_cv_path() == str(master_cv_path.resolve())
    assert master_cv_path.read_text(encoding="utf-8").endswith(r"\section{Skills}Python\end{document}")
    preferences = assistant.get_preferences()
    assert preferences.languages == [
        LanguagePreference(language="English", level="Fluent"),
        LanguagePreference(language="Cantonese", level=None),
    ]
    assert preferences.locations == ["Hong Kong", "Remote"]
    assert preferences.gap_tolerance is GapTolerance.SEMESTER
    page = client.get("/candidate")
    assert "Python" in page.text


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
