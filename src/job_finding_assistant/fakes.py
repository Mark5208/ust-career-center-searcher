"""In-memory fakes for Job Board / LLM / Master CV / constraint-file ports used in tests."""

from pathlib import Path

from job_finding_assistant.candidate_snapshot import (
    CandidateSnapshot,
    InvalidMasterCvError,
    build_candidate_snapshot,
)
from job_finding_assistant.constraint_files import ConstraintFileRead, read_constraint_file
from job_finding_assistant.crawl_filters import CrawlFilters
from job_finding_assistant.job_board import AuthLostError, JobListEntry, JobPostingDetail
from job_finding_assistant.match_assessment import (
    ConstraintOutcome,
    EvidencePair,
    HardConstraintJudgment,
    PreferenceBand,
    PreferenceJudgment,
    RelevanceBand,
    RelevanceJudgment,
)
from job_finding_assistant.pdf_renderer import PdfRenderError
from job_finding_assistant.preparation_packet import (
    EditSummary,
    GapReport,
    TailorResult,
)


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
        yaml_path = Path(self._path)
        if not yaml_path.is_file():
            self._snapshot = None
            return
        try:
            self._snapshot = build_candidate_snapshot(
                yaml_path.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError, InvalidMasterCvError):
            self._snapshot = None


class FakeConstraintFilesStore:
    def __init__(
        self,
        *,
        hard_constraints_path: str | None = None,
        preferences_path: str | None = None,
    ) -> None:
        self._hard_constraints_path = hard_constraints_path
        self._preferences_path = preferences_path

    def hard_constraints_path(self) -> str | None:
        return self._hard_constraints_path

    def preferences_path(self) -> str | None:
        return self._preferences_path

    def set_hard_constraints_path(self, path: str) -> None:
        self._hard_constraints_path = str(Path(path).expanduser().resolve())

    def clear_hard_constraints_path(self) -> None:
        self._hard_constraints_path = None

    def set_preferences_path(self, path: str) -> None:
        self._preferences_path = str(Path(path).expanduser().resolve())

    def clear_preferences_path(self) -> None:
        self._preferences_path = None

    def read_hard_constraints(self) -> ConstraintFileRead:
        return read_constraint_file(self._hard_constraints_path)

    def read_preferences(self) -> ConstraintFileRead:
        return read_constraint_file(self._preferences_path)


class FakeLlmJudge:
    """Scripted three-signal judgments; records call inputs for isolation checks."""

    def __init__(
        self,
        *,
        available: bool = True,
        hard_constraint_outcome: ConstraintOutcome = "pass",
        hard_constraint_reason: str = "No hard constraint violations",
        preference: PreferenceBand = "Mixed",
        preference_reason: str = "Partial preference fit",
        preferences: list[PreferenceBand] | None = None,
        relevance: RelevanceBand = "Mixed",
        relevances: list[RelevanceBand] | None = None,
        evidence: list[EvidencePair] | None = None,
        fail_on_call: bool = False,
    ) -> None:
        self._available = available
        self._hard_constraint_outcome = hard_constraint_outcome
        self._hard_constraint_reason = hard_constraint_reason
        self._preference = preference
        self._preference_reason = preference_reason
        self._preferences = list(preferences) if preferences is not None else None
        self._preference_index = 0
        self._relevance = relevance
        self._relevances = list(relevances) if relevances is not None else None
        self._relevance_index = 0
        self._evidence = list(
            evidence
            or [
                EvidencePair(
                    job_excerpt="Job description excerpt",
                    candidate_excerpt="Candidate snapshot excerpt",
                    role="supports Relevance",
                )
            ]
        )
        self._fail_on_call = fail_on_call
        self.judge_calls = 0
        self.hard_constraint_calls: list[dict[str, object]] = []
        self.preference_calls: list[dict[str, object]] = []
        self.relevance_calls: list[dict[str, object]] = []

    def available(self) -> bool:
        return self._available

    def judge_hard_constraint(
        self,
        *,
        hard_constraints_text: str,
        job_detail_fields: dict[str, str],
    ) -> HardConstraintJudgment:
        if not self._available or self._fail_on_call:
            raise RuntimeError("FakeLlmJudge is not available")
        self.judge_calls += 1
        self.hard_constraint_calls.append(
            {
                "hard_constraints_text": hard_constraints_text,
                "job_detail_fields": dict(job_detail_fields),
            }
        )
        return HardConstraintJudgment(
            outcome=self._hard_constraint_outcome,
            reason=self._hard_constraint_reason,
            evidence=[],
        )

    def judge_preference(
        self,
        *,
        preferences_text: str,
        job_detail_fields: dict[str, str],
    ) -> PreferenceJudgment:
        if not self._available or self._fail_on_call:
            raise RuntimeError("FakeLlmJudge is not available")
        self.judge_calls += 1
        self.preference_calls.append(
            {
                "preferences_text": preferences_text,
                "job_detail_fields": dict(job_detail_fields),
            }
        )
        if self._preferences is not None:
            preference = self._preferences[self._preference_index]
            self._preference_index += 1
        else:
            preference = self._preference
        return PreferenceJudgment(
            preference=preference,
            reason=self._preference_reason,
            evidence=[],
        )

    def judge_relevance(
        self,
        *,
        job_detail_fields: dict[str, str],
        candidate_snapshot: CandidateSnapshot,
    ) -> RelevanceJudgment:
        if not self._available or self._fail_on_call:
            raise RuntimeError("FakeLlmJudge is not available")
        self.judge_calls += 1
        self.relevance_calls.append(
            {
                "job_detail_fields": dict(job_detail_fields),
                "candidate_snapshot": candidate_snapshot,
            }
        )
        if self._relevances is not None:
            relevance = self._relevances[self._relevance_index]
            self._relevance_index += 1
        else:
            relevance = self._relevance
        return RelevanceJudgment(relevance=relevance, evidence=list(self._evidence))


class FakeLlmCvTailor:
    """Scripted Gap Report / Tailored YAML / Edit Summary for Prepare tests."""

    def __init__(
        self,
        *,
        available: bool = True,
        result: TailorResult | None = None,
        fail_on_call: bool = False,
    ) -> None:
        self._available = available
        self._result = result or TailorResult(
            gap_report=GapReport(),
            edit_summary=EditSummary(),
            tailored_yaml="cv:\n  name: Tailored\n  sections: {}\n",
        )
        self._fail_on_call = fail_on_call
        self.tailor_calls = 0
        self.tailor_inputs: list[dict[str, object]] = []

    def available(self) -> bool:
        return self._available

    def tailor(
        self,
        *,
        master_cv_yaml: str,
        candidate_snapshot: CandidateSnapshot,
        job_detail_fields: dict[str, str],
        relevance_evidence: list[EvidencePair],
        hard_constraint_outcome: ConstraintOutcome,
        hard_constraint_reason: str,
    ) -> TailorResult:
        if not self._available or self._fail_on_call:
            raise RuntimeError("FakeLlmCvTailor is not available")
        self.tailor_calls += 1
        self.tailor_inputs.append(
            {
                "master_cv_yaml": master_cv_yaml,
                "candidate_snapshot": candidate_snapshot,
                "job_detail_fields": dict(job_detail_fields),
                "relevance_evidence": list(relevance_evidence),
                "hard_constraint_outcome": hard_constraint_outcome,
                "hard_constraint_reason": hard_constraint_reason,
            }
        )
        return self._result


class FakePdfRenderer:
    """Scripted PDF bytes (or failure) for Prepare tests."""

    def __init__(
        self,
        *,
        pdf_bytes: bytes | None = b"%PDF-1.4 fake",
        fail: bool = False,
    ) -> None:
        self._pdf_bytes = pdf_bytes
        self._fail = fail
        self.render_calls = 0

    def render_pdf(self, tailored_yaml: str) -> bytes:
        del tailored_yaml
        self.render_calls += 1
        if self._fail or self._pdf_bytes is None:
            raise PdfRenderError("FakePdfRenderer failed")
        return self._pdf_bytes
