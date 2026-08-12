"""In-memory fakes for Job Board / LLM / Master CV / constraint-file ports used in tests."""

import time
from pathlib import Path

from job_finding_assistant.candidate_snapshot import (
    CandidateSnapshot,
    InvalidMasterCvError,
    build_candidate_snapshot,
)
from job_finding_assistant.constraint_files import ConstraintFileRead, read_constraint_file
from job_finding_assistant.crawl_filters import CrawlFilters
from job_finding_assistant.crawl_pacer import NoOpCrawlPacer
from job_finding_assistant.enrichment import PlacementSuggestion
from job_finding_assistant.job_board import AuthLostError, JobListEntry, JobPostingDetail
from job_finding_assistant.ports import CrawlPacer
from job_finding_assistant.llm_runtime import LlmUnavailableError
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
        crawl_pacer: CrawlPacer | None = None,
    ) -> None:
        self._authenticated = authenticated
        self._list_entries = list(list_entries or [])
        self._details = dict(details or {})
        self._auth_lost_after_details = auth_lost_after_details
        self._crawl_pacer = crawl_pacer or NoOpCrawlPacer()
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
        self._crawl_pacer.pause_before_detail()
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
        hard_constraint_evidence: list[EvidencePair] | None = None,
        preference: PreferenceBand = "Mixed",
        preference_reason: str = "Partial preference fit",
        preference_evidence: list[EvidencePair] | None = None,
        preferences: list[PreferenceBand] | None = None,
        relevance: RelevanceBand = "Mixed",
        relevances: list[RelevanceBand] | None = None,
        evidence: list[EvidencePair] | None = None,
        fail_on_call: bool = False,
        fail_for_titles: frozenset[str] | None = None,
        delay_seconds: float = 0.0,
    ) -> None:
        self._available = available
        self._hard_constraint_outcome = hard_constraint_outcome
        self._hard_constraint_reason = hard_constraint_reason
        self._hard_constraint_evidence = list(hard_constraint_evidence or [])
        self._preference = preference
        self._preference_reason = preference_reason
        self._preference_evidence = list(preference_evidence or [])
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
        self._fail_for_titles = set(fail_for_titles or ())
        self._delay_seconds = delay_seconds
        self.judge_calls = 0
        self.hard_constraint_calls: list[dict[str, object]] = []
        self.preference_calls: list[dict[str, object]] = []
        self.relevance_calls: list[dict[str, object]] = []

    def available(self) -> bool:
        return self._available

    def unavailable_reason(self) -> str | None:
        if self._available:
            return None
        return "LLM Unavailable: Fake judge disabled"

    def _maybe_delay(self) -> None:
        if self._delay_seconds > 0:
            time.sleep(self._delay_seconds)

    def _should_fail(self, job_detail_fields: dict[str, str]) -> bool:
        if not self._available or self._fail_on_call:
            return True
        title = str(job_detail_fields.get("title") or "")
        return title in self._fail_for_titles

    def _raise_unavailable(self) -> None:
        if not self._available:
            raise LlmUnavailableError("Fake judge disabled")
        raise LlmUnavailableError("Fake judge failed")

    def judge_hard_constraint(
        self,
        *,
        hard_constraints_text: str,
        job_detail_fields: dict[str, str],
    ) -> HardConstraintJudgment:
        if self._should_fail(job_detail_fields):
            self._raise_unavailable()
        self._maybe_delay()
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
            evidence=list(self._hard_constraint_evidence),
        )

    def judge_preference(
        self,
        *,
        preferences_text: str,
        job_detail_fields: dict[str, str],
    ) -> PreferenceJudgment:
        if self._should_fail(job_detail_fields):
            self._raise_unavailable()
        self._maybe_delay()
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
            evidence=list(self._preference_evidence),
        )

    def judge_relevance(
        self,
        *,
        job_detail_fields: dict[str, str],
        candidate_snapshot: CandidateSnapshot,
    ) -> RelevanceJudgment:
        if self._should_fail(job_detail_fields):
            self._raise_unavailable()
        self._maybe_delay()
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
        results: list[TailorResult] | None = None,
        fail_on_call: bool = False,
    ) -> None:
        self._available = available
        # A scripted `results=` sequence is a strict contract (fails loudly if
        # over-called, e.g. Prepare's one bounded retry regressing to unbounded);
        # a single `result=` is a convenience that repeats for any call count.
        self._strict_sequence = results is not None
        if results is not None:
            self._results = list(results)
        else:
            self._results = [
                result
                or TailorResult(
                    gap_report=GapReport(),
                    edit_summary=EditSummary(),
                    tailored_yaml="cv:\n  name: Tailored\n  sections: {}\n",
                )
            ]
        self._fail_on_call = fail_on_call
        self.tailor_calls = 0
        self.tailor_inputs: list[dict[str, object]] = []

    def available(self) -> bool:
        return self._available

    def unavailable_reason(self) -> str | None:
        if self._available:
            return None
        return "LLM Unavailable: Fake tailor disabled"

    def tailor(
        self,
        *,
        master_cv_yaml: str,
        candidate_snapshot: CandidateSnapshot,
        job_detail_fields: dict[str, str],
        relevance_evidence: list[EvidencePair],
        hard_constraint_outcome: ConstraintOutcome,
        hard_constraint_reason: str,
        prior_attempt_errors: list[str] | None = None,
    ) -> TailorResult:
        if not self._available or self._fail_on_call:
            if not self._available:
                raise LlmUnavailableError("Fake tailor disabled")
            raise LlmUnavailableError("Fake tailor failed")
        if self._strict_sequence and self.tailor_calls >= len(self._results):
            raise AssertionError(
                f"FakeLlmCvTailor.tailor() called {self.tailor_calls + 1} times but "
                f"only {len(self._results)} results were scripted via results="
            )
        self.tailor_inputs.append(
            {
                "master_cv_yaml": master_cv_yaml,
                "candidate_snapshot": candidate_snapshot,
                "job_detail_fields": dict(job_detail_fields),
                "relevance_evidence": list(relevance_evidence),
                "hard_constraint_outcome": hard_constraint_outcome,
                "hard_constraint_reason": hard_constraint_reason,
                "prior_attempt_errors": (
                    list(prior_attempt_errors) if prior_attempt_errors else None
                ),
            }
        )
        index = min(self.tailor_calls, len(self._results) - 1)
        self.tailor_calls += 1
        return self._results[index]


class FakeLlmCvEnricher:
    """Scripted Master CV Enrichment LLM steps for tests."""

    def __init__(
        self,
        *,
        available: bool = True,
        placement: PlacementSuggestion | None = None,
        followup: str | None = None,
        highlights: list[str] | None = None,
        fail_on_call: bool = False,
    ) -> None:
        self._available = available
        self._placement = placement or PlacementSuggestion(
            section="experience",
            mode="existing",
            entry_index=0,
            label="Software Intern at Acme Corp",
        )
        self._followup = followup
        self._highlights = highlights or [
            "Built internal tools",
            "Led cross-team delivery of a reporting dashboard",
        ]
        self._fail_on_call = fail_on_call
        self.suggest_calls = 0
        self.followup_calls = 0
        self.draft_calls = 0

    def available(self) -> bool:
        return self._available

    def unavailable_reason(self) -> str | None:
        if self._available:
            return None
        return "LLM Unavailable: Fake enricher disabled"

    def suggest_placement(
        self,
        *,
        freeform: str,
        master_cv_yaml: str,
    ) -> PlacementSuggestion:
        del freeform, master_cv_yaml
        self._ensure_callable()
        self.suggest_calls += 1
        return self._placement

    def clarifying_followup(
        self,
        *,
        dimension: str,
        answer: str,
        freeform: str,
    ) -> str | None:
        del dimension, answer, freeform
        self._ensure_callable()
        self.followup_calls += 1
        return self._followup

    def draft_highlights(
        self,
        *,
        freeform: str,
        placement: PlacementSuggestion,
        dimension_answers: dict[str, str],
        existing_highlights: list[str],
    ) -> list[str]:
        del freeform, placement, dimension_answers, existing_highlights
        self._ensure_callable()
        self.draft_calls += 1
        return list(self._highlights)

    def _ensure_callable(self) -> None:
        if not self._available or self._fail_on_call:
            if not self._available:
                raise LlmUnavailableError("Fake enricher disabled")
            raise LlmUnavailableError("Fake enricher failed")


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
