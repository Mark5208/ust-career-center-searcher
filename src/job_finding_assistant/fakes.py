"""In-memory fakes for Job Board / LLM / Master CV ports used in tests."""

from pathlib import Path

from job_finding_assistant.candidate_snapshot import CandidateSnapshot, build_candidate_snapshot
from job_finding_assistant.crawl_filters import CrawlFilters
from job_finding_assistant.job_board import AuthLostError, JobListEntry, JobPostingDetail


class FakeCrawlPacer:
    """Records pause requests without sleeping (time boundary fake)."""

    def __init__(self) -> None:
        self.before_detail_calls = 0
        self.before_detail_ranges: list[tuple[float, float]] = []
        self.before_next_page_calls = 0
        self.before_next_page_ranges: list[tuple[float, float]] = []

    def pause_before_detail(self) -> None:
        from job_finding_assistant.crawl_pacer import DETAIL_PAUSE_RANGE

        self.before_detail_calls += 1
        self.before_detail_ranges.append(DETAIL_PAUSE_RANGE)

    def pause_before_next_page(self) -> None:
        from job_finding_assistant.crawl_pacer import NEXT_PAGE_PAUSE_RANGE

        self.before_next_page_calls += 1
        self.before_next_page_ranges.append(NEXT_PAGE_PAUSE_RANGE)


class FakeJobBoardSession:
    def __init__(
        self,
        *,
        authenticated: bool = False,
        list_entries: list[JobListEntry] | None = None,
        details: dict[str, JobPostingDetail] | None = None,
        auth_lost_after_details: int | None = None,
    ) -> None:
        self._authenticated = authenticated
        self._list_entries = list(list_entries or [])
        self._details = dict(details or {})
        self._auth_lost_after_details = auth_lost_after_details
        self._details_fetched = 0
        self.open_login_calls = 0
        self.discover_calls = 0
        self.fetch_detail_ids: list[str] = []

    def open_login(self) -> None:
        self.open_login_calls += 1
        self._authenticated = True

    def is_authenticated(self) -> bool:
        return self._authenticated

    def set_authenticated(self, value: bool) -> None:
        self._authenticated = value

    def set_list_entries(self, entries: list[JobListEntry]) -> None:
        self._list_entries = list(entries)

    def set_details(self, details: dict[str, JobPostingDetail]) -> None:
        self._details = dict(details)

    def discover_job_list(self, filters: CrawlFilters) -> list[JobListEntry]:
        del filters  # Fake ignores live board filter UI; tests seed list entries.
        self.discover_calls += 1
        if not self._authenticated:
            raise AuthLostError("not authenticated")
        return list(self._list_entries)

    def fetch_job_detail(self, job_posting_id: str) -> JobPostingDetail:
        if not self._authenticated:
            raise AuthLostError("not authenticated")
        if (
            self._auth_lost_after_details is not None
            and self._details_fetched >= self._auth_lost_after_details
        ):
            self._authenticated = False
            raise AuthLostError("auth lost mid-crawl")
        self._details_fetched += 1
        self.fetch_detail_ids.append(job_posting_id)
        if job_posting_id in self._details:
            return self._details[job_posting_id]
        for entry in self._list_entries:
            if entry.id == job_posting_id:
                return JobPostingDetail(
                    id=entry.id,
                    title=entry.title,
                    employer=entry.employer,
                    posting_date=entry.posting_date,
                    application_deadline=entry.application_deadline,
                    fields={"Job Description": f"Detail for {entry.title}"},
                )
        raise KeyError(job_posting_id)


class FakeMasterCvStore:
    def __init__(
        self,
        path: str | None = None,
        snapshot: CandidateSnapshot | None = None,
    ) -> None:
        self._path = path
        self._snapshot = snapshot

    def master_cv_path(self) -> str | None:
        return self._path

    def set_master_cv_path(self, path: str) -> None:
        self._path = path
        self._rebuild_from_path()

    def candidate_snapshot(self) -> CandidateSnapshot | None:
        if self._path is not None and Path(self._path).is_file():
            self._rebuild_from_path()
        return self._snapshot

    def _rebuild_from_path(self) -> None:
        if self._path is None:
            self._snapshot = None
            return
        latex_path = Path(self._path)
        if not latex_path.is_file():
            self._snapshot = None
            return
        self._snapshot = build_candidate_snapshot(latex_path.read_text(encoding="utf-8"))


class FakeLlmJudge:
    def available(self) -> bool:
        return False


class FakeLlmCvTailor:
    def available(self) -> bool:
        return False
