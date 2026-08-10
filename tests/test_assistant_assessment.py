"""Assistant seam: three-signal assessment, freeform HC/Preferences, freshness."""

import sqlite3
from pathlib import Path

import pytest

from job_finding_assistant.assistant import Assistant
from job_finding_assistant.catalog_store import CatalogStore
from job_finding_assistant.fakes import (
    FakeConstraintFilesStore,
    FakeCrawlPacer,
    FakeJobBoardSession,
    FakeLlmCvTailor,
    FakeLlmJudge,
    FakeMasterCvStore,
)
from job_finding_assistant.job_board import JobListEntry, JobPostingDetail
from job_finding_assistant.match_assessment import EvidencePair, MatchAssessment

_SAMPLE_CV = """\
cv:
  name: Test Candidate
  sections:
    experience:
      - company: Example
        position: Platform engineer
"""


def _write_cv(tmp_path: Path, name: str = "master_CV.yaml", body: str = _SAMPLE_CV) -> Path:
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


def _assistant(
    tmp_path: Path,
    *,
    job_board: FakeJobBoardSession | None = None,
    master_cv: FakeMasterCvStore | None = None,
    llm_judge: FakeLlmJudge | None = None,
    constraint_files: FakeConstraintFilesStore | None = None,
) -> Assistant:
    return Assistant(
        catalog_store=CatalogStore(tmp_path / "catalog.db"),
        job_board=job_board or FakeJobBoardSession(),
        master_cv=master_cv or FakeMasterCvStore(),
        llm_judge=llm_judge or FakeLlmJudge(relevance="Strong"),
        llm_cv_tailor=FakeLlmCvTailor(),
        constraint_files=constraint_files or FakeConstraintFilesStore(),
        crawl_pacer=FakeCrawlPacer(),
    )


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


def _crawl_with_master_cv(
    tmp_path: Path,
    *,
    llm_judge: FakeLlmJudge | None = None,
    constraint_files: FakeConstraintFilesStore | None = None,
    entry: JobListEntry | None = None,
    detail: JobPostingDetail | None = None,
) -> tuple[Assistant, FakeLlmJudge]:
    default_entry, default_detail = _open_posting()
    entry = entry or default_entry
    detail = detail or default_detail
    job_board = FakeJobBoardSession(
        authenticated=True,
        list_entries=[entry],
        details={detail.id: detail},
    )
    judge = llm_judge or FakeLlmJudge(relevance="Strong")
    cv_path = _write_cv(tmp_path)
    master_cv = FakeMasterCvStore()
    assistant = _assistant(
        tmp_path,
        job_board=job_board,
        master_cv=master_cv,
        llm_judge=judge,
        constraint_files=constraint_files,
    )
    assistant.set_master_cv_path(str(cv_path))
    return assistant, judge


def test_crawl_leaves_assessments_pending_until_rejudge(tmp_path: Path) -> None:
    assistant, judge = _crawl_with_master_cv(tmp_path)

    outcome = assistant.run_crawl()

    assert outcome.status == "completed"
    assert outcome.stored_count == 1
    summary = assistant.list_assessment_summaries()[0]
    assert summary.pending is True
    assert judge.judge_calls == 0
    assert assistant.can_prepare(summary.job_posting_id) is False


def test_rejudge_builds_three_signal_assessment_with_empty_constraint_files(
    tmp_path: Path,
) -> None:
    assistant, judge = _crawl_with_master_cv(tmp_path)
    assistant.run_crawl()

    assistant.rejudge_pending_assessments()

    summary = assistant.list_assessment_summaries()[0]
    assert summary.pending is False
    assert summary.hard_constraint_outcome == "unknown"
    assert summary.preference is None
    assert summary.relevance == "Strong"
    assert assistant.can_prepare(summary.job_posting_id) is True
    detail = assistant.get_match_assessment(summary.job_posting_id)
    assert detail is not None
    assert detail.hard_constraint_reason
    assert detail.evidence
    assert len(judge.hard_constraint_calls) == 0
    assert len(judge.preference_calls) == 0
    assert len(judge.relevance_calls) == 1


def test_rejudge_pending_assessments_budgets_one_posting_per_call(tmp_path: Path) -> None:
    entry_a, detail_a = _open_posting(job_id="86534", title="Engineer A")
    entry_b, detail_b = _open_posting(job_id="86535", title="Engineer B", employer="Other")
    job_board = FakeJobBoardSession(
        authenticated=True,
        list_entries=[entry_a, entry_b],
        details={detail_a.id: detail_a, detail_b.id: detail_b},
    )
    judge = FakeLlmJudge(relevance="Strong")
    cv_path = _write_cv(tmp_path)
    master_cv = FakeMasterCvStore()
    assistant = _assistant(
        tmp_path,
        job_board=job_board,
        master_cv=master_cv,
        llm_judge=judge,
    )
    assistant.set_master_cv_path(str(cv_path))
    assistant.run_crawl()

    assistant.rejudge_pending_assessments()

    summaries = {
        row.job_posting_id: row for row in assistant.list_assessment_summaries()
    }
    assert len(summaries) == 2
    pending_count = sum(1 for row in summaries.values() if row.pending)
    assessed_count = sum(1 for row in summaries.values() if not row.pending)
    assert assessed_count == 1
    assert pending_count == 1
    assert judge.judge_calls == 1

    assistant.rejudge_pending_assessments()
    assert all(not row.pending for row in assistant.list_assessment_summaries())
    assert judge.judge_calls == 2


def test_load_assessment_summary_catalog_processes_up_to_five_and_reports_progress(
    tmp_path: Path,
) -> None:
    entries_and_details = [
        _open_posting(
            job_id=str(86534 + i),
            title=f"Engineer {i}",
            employer=f"Employer {i}",
        )
        for i in range(6)
    ]
    job_board = FakeJobBoardSession(
        authenticated=True,
        list_entries=[entry for entry, _ in entries_and_details],
        details={detail.id: detail for _, detail in entries_and_details},
    )
    judge = FakeLlmJudge(relevance="Strong")
    cv_path = _write_cv(tmp_path)
    assistant = _assistant(
        tmp_path,
        job_board=job_board,
        master_cv=FakeMasterCvStore(),
        llm_judge=judge,
    )
    assistant.set_master_cv_path(str(cv_path))
    assistant.run_crawl()

    catalog = assistant.load_assessment_summary_catalog()

    assert catalog.processed_this_load == 5
    assert catalog.pending_remaining == 1
    assert len(catalog.rows) == 6
    assert sum(1 for row in catalog.rows if row.summary.pending) == 1
    assert sum(1 for row in catalog.rows if row.can_prepare) == 5
    assert judge.judge_calls == 5

    caught_up = assistant.load_assessment_summary_catalog()
    assert caught_up.processed_this_load == 1
    assert caught_up.pending_remaining == 0
    assert all(not row.summary.pending for row in caught_up.rows)
    assert all(row.can_prepare for row in caught_up.rows)


def test_load_assessment_summary_catalog_early_stops_on_llm_unavailable(
    tmp_path: Path,
) -> None:
    entries_and_details = [
        _open_posting(
            job_id=str(86534 + i),
            title=f"Engineer {i}",
            employer=f"Employer {i}",
        )
        for i in range(3)
    ]
    job_board = FakeJobBoardSession(
        authenticated=True,
        list_entries=[entry for entry, _ in entries_and_details],
        details={detail.id: detail for _, detail in entries_and_details},
    )
    judge = FakeLlmJudge(available=False)
    cv_path = _write_cv(tmp_path)
    assistant = _assistant(
        tmp_path,
        job_board=job_board,
        master_cv=FakeMasterCvStore(),
        llm_judge=judge,
    )
    assistant.set_master_cv_path(str(cv_path))
    assistant.run_crawl()

    catalog = assistant.load_assessment_summary_catalog()

    assert catalog.processed_this_load == 1
    assert catalog.pending_remaining == 3
    assert catalog.llm_unavailable_reason == "LLM Unavailable: Fake judge disabled"
    assert all(row.summary.pending for row in catalog.rows)
    assert judge.judge_calls == 0


def test_rejudge_does_not_starve_later_pending_when_head_fails(tmp_path: Path) -> None:
    """One failing Pending head must not block later jobs forever (HOL)."""
    entry_a, detail_a = _open_posting(job_id="85904", title="Engineer A")
    entry_b, detail_b = _open_posting(
        job_id="86497", title="Engineer B", employer="Other"
    )
    job_board = FakeJobBoardSession(
        authenticated=True,
        list_entries=[entry_a, entry_b],
        details={detail_a.id: detail_a, detail_b.id: detail_b},
    )
    judge = FakeLlmJudge(
        relevance="Strong",
        fail_for_titles=frozenset({"Engineer A"}),
    )
    cv_path = _write_cv(tmp_path)
    assistant = _assistant(
        tmp_path,
        job_board=job_board,
        master_cv=FakeMasterCvStore(),
        llm_judge=judge,
    )
    assistant.set_master_cv_path(str(cv_path))
    assistant.run_crawl()

    # Budget is one attempt per call; head fails then later Pending must still advance.
    assistant.rejudge_pending_assessments()
    assistant.rejudge_pending_assessments()
    assistant.rejudge_pending_assessments()

    by_id = {row.job_posting_id: row for row in assistant.list_assessment_summaries()}
    assert by_id["85904"].pending is True
    assert assistant.can_prepare("85904") is False
    assert by_id["86497"].pending is False
    assert assistant.can_prepare("86497") is True
    assert assistant.get_match_assessment("86497") is not None
    reason = assistant.get_llm_unavailable_reason()
    assert reason is not None
    assert reason.startswith("LLM Unavailable:")


def test_non_empty_constraint_files_invoke_llm_with_input_isolation(
    tmp_path: Path,
) -> None:
    hc_path = tmp_path / "hard.txt"
    hc_path.write_text("Must be Hong Kong based\n", encoding="utf-8")
    prefs_path = tmp_path / "prefs.txt"
    prefs_path.write_text("Prefer fintech\nAvoid sales-only roles\n", encoding="utf-8")
    constraints = FakeConstraintFilesStore()
    judge = FakeLlmJudge(
        hard_constraint_outcome="pass",
        preference="Strong",
        relevance="Mixed",
    )
    assistant, _ = _crawl_with_master_cv(
        tmp_path, llm_judge=judge, constraint_files=constraints
    )
    assistant.set_hard_constraints_path(str(hc_path))
    assistant.set_preferences_path(str(prefs_path))
    assistant.run_crawl()
    assistant.rejudge_pending_assessments()

    summary = assistant.list_assessment_summaries()[0]
    assert summary.pending is False
    assert summary.hard_constraint_outcome == "pass"
    assert summary.preference == "Strong"
    assert summary.relevance == "Mixed"
    assert len(judge.hard_constraint_calls) == 1
    assert "Hong Kong" in str(judge.hard_constraint_calls[0]["hard_constraints_text"])
    assert "candidate_snapshot" not in judge.hard_constraint_calls[0]
    assert len(judge.preference_calls) == 1
    assert "fintech" in str(judge.preference_calls[0]["preferences_text"])
    assert "candidate_snapshot" not in judge.preference_calls[0]
    assert len(judge.relevance_calls) == 1
    assert judge.relevance_calls[0]["candidate_snapshot"] is not None


def test_rejudge_persists_hard_constraint_and_preference_evidence(
    tmp_path: Path,
) -> None:
    hc_path = tmp_path / "hard.txt"
    hc_path.write_text("Must be Hong Kong based\n", encoding="utf-8")
    prefs_path = tmp_path / "prefs.txt"
    prefs_path.write_text("Prefer fintech\n", encoding="utf-8")
    hc_evidence = [
        EvidencePair(
            job_excerpt="Work Location: Singapore",
            candidate_excerpt="Must be Hong Kong based",
            role="violates Hard Constraint",
        )
    ]
    preference_evidence = [
        EvidencePair(
            job_excerpt="Fintech platform team",
            candidate_excerpt="Prefer fintech",
            role="supports Preference",
        )
    ]
    relevance_evidence = [
        EvidencePair(
            job_excerpt="Build reliable systems in Python.",
            candidate_excerpt="Platform engineer at Example",
            role="supports Relevance",
        )
    ]
    constraints = FakeConstraintFilesStore()
    judge = FakeLlmJudge(
        hard_constraint_outcome="fail",
        hard_constraint_reason="Location outside Hong Kong",
        hard_constraint_evidence=hc_evidence,
        preference="Strong",
        preference_reason="Matches preferred domain",
        preference_evidence=preference_evidence,
        relevance="Strong",
        evidence=relevance_evidence,
    )
    assistant, _ = _crawl_with_master_cv(
        tmp_path, llm_judge=judge, constraint_files=constraints
    )
    assistant.set_hard_constraints_path(str(hc_path))
    assistant.set_preferences_path(str(prefs_path))
    assistant.run_crawl()
    assistant.rejudge_pending_assessments()

    detail = assistant.get_match_assessment("86534")
    assert detail is not None
    assert detail.hard_constraint_evidence == hc_evidence
    assert detail.preference_evidence == preference_evidence
    assert detail.evidence == relevance_evidence


def test_rejudge_keeps_empty_constraint_evidence_when_files_empty(
    tmp_path: Path,
) -> None:
    judge = FakeLlmJudge(
        hard_constraint_outcome="fail",
        hard_constraint_evidence=[
            EvidencePair(
                job_excerpt="should not persist",
                candidate_excerpt="padding",
                role="invented",
            )
        ],
        preference_evidence=[
            EvidencePair(
                job_excerpt="should not persist",
                candidate_excerpt="padding",
                role="invented",
            )
        ],
        relevance="Strong",
    )
    assistant, _ = _crawl_with_master_cv(tmp_path, llm_judge=judge)
    assistant.run_crawl()
    assistant.rejudge_pending_assessments()

    detail = assistant.get_match_assessment("86534")
    assert detail is not None
    assert detail.hard_constraint_outcome == "unknown"
    assert detail.preference is None
    assert detail.hard_constraint_evidence == []
    assert detail.preference_evidence == []
    assert detail.evidence


def test_pre_upgrade_complete_assessment_loads_empty_constraint_evidence(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "catalog.db"
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE match_assessments (
                job_posting_id TEXT PRIMARY KEY,
                hard_constraint_outcome TEXT NOT NULL,
                hard_constraint_reason TEXT NOT NULL,
                preference TEXT,
                preference_reason TEXT NOT NULL,
                relevance TEXT NOT NULL,
                evidence_json TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            INSERT INTO match_assessments (
                job_posting_id,
                hard_constraint_outcome,
                hard_constraint_reason,
                preference,
                preference_reason,
                relevance,
                evidence_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "86534",
                "pass",
                "No hard constraint violations",
                "Mixed",
                "Partial preference fit",
                "Strong",
                '[{"job_excerpt":"Python","candidate_excerpt":"Platform engineer","role":"supports Relevance"}]',
            ),
        )

    store = CatalogStore(db_path)
    loaded = store.get_match_assessment("86534")
    assert loaded is not None
    assert loaded.hard_constraint_evidence == []
    assert loaded.preference_evidence == []
    assert loaded.evidence[0].job_excerpt == "Python"


def test_prepare_available_when_hard_constraint_fails(tmp_path: Path) -> None:
    hc_path = tmp_path / "hard.txt"
    hc_path.write_text("Hong Kong only\n", encoding="utf-8")
    constraints = FakeConstraintFilesStore()
    judge = FakeLlmJudge(hard_constraint_outcome="fail", relevance="Strong")
    assistant, _ = _crawl_with_master_cv(
        tmp_path, llm_judge=judge, constraint_files=constraints
    )
    assistant.set_hard_constraints_path(str(hc_path))
    assistant.run_crawl()
    assistant.rejudge_pending_assessments()

    assert assistant.list_assessment_summaries()[0].hard_constraint_outcome == "fail"
    assert assistant.can_prepare("86534") is True


def test_assessment_stays_pending_when_llm_judge_unavailable(tmp_path: Path) -> None:
    assistant, _ = _crawl_with_master_cv(
        tmp_path, llm_judge=FakeLlmJudge(available=False)
    )
    assistant.run_crawl()
    assistant.rejudge_pending_assessments()

    summary = assistant.list_assessment_summaries()[0]
    assert summary.pending is True
    assert assistant.can_prepare(summary.job_posting_id) is False
    assert assistant.get_llm_unavailable_reason() == "LLM Unavailable: Fake judge disabled"


def test_judge_failure_leaves_pending_without_half_assessment(tmp_path: Path) -> None:
    hc_path = tmp_path / "hard.txt"
    hc_path.write_text("Must be remote\n", encoding="utf-8")
    constraints = FakeConstraintFilesStore()
    judge = FakeLlmJudge(fail_on_call=True)
    assistant, _ = _crawl_with_master_cv(
        tmp_path, llm_judge=judge, constraint_files=constraints
    )
    assistant.set_hard_constraints_path(str(hc_path))
    assistant.run_crawl()
    assistant.rejudge_pending_assessments()

    assert assistant.list_assessment_summaries()[0].pending is True
    assert assistant.get_llm_unavailable_reason() == "LLM Unavailable: Fake judge failed"


def test_assistant_does_not_wrap_bare_judge_errors_as_llm_unavailable(
    tmp_path: Path,
) -> None:
    """Adapters own LlmUnavailableError; Assistant only pass-through-caches .reason."""

    class _BareErrorJudge:
        def available(self) -> bool:
            return True

        def unavailable_reason(self) -> str | None:
            return None

        def judge_hard_constraint(self, **kwargs: object) -> object:
            del kwargs
            raise RuntimeError("raw adapter bug")

        def judge_preference(self, **kwargs: object) -> object:
            del kwargs
            raise RuntimeError("raw adapter bug")

        def judge_relevance(self, **kwargs: object) -> object:
            del kwargs
            raise RuntimeError("raw adapter bug")

    assistant, _ = _crawl_with_master_cv(tmp_path, llm_judge=_BareErrorJudge())  # type: ignore[arg-type]
    assistant.run_crawl()
    with pytest.raises(RuntimeError, match="raw adapter bug"):
        assistant.rejudge_pending_assessments()
    assert assistant.get_llm_unavailable_reason() is None


def test_assistant_does_not_expose_public_refresh_candidate_file_state() -> None:
    """Freshness is an internal Assistant gate (ADR-0014); callers use public reads."""
    assert not hasattr(Assistant, "refresh_candidate_file_state")


def test_fingerprint_change_marks_all_assessments_pending(tmp_path: Path) -> None:
    prefs_path = tmp_path / "prefs.txt"
    prefs_path.write_text("Prefer remote\n", encoding="utf-8")
    constraints = FakeConstraintFilesStore()
    judge = FakeLlmJudge(preference="Strong", relevance="Strong")
    assistant, _ = _crawl_with_master_cv(
        tmp_path, llm_judge=judge, constraint_files=constraints
    )
    assistant.set_preferences_path(str(prefs_path))
    assistant.run_crawl()
    assistant.rejudge_pending_assessments()
    assert assistant.list_assessment_summaries()[0].pending is False

    prefs_path.write_text("Prefer on-site Hong Kong\n", encoding="utf-8")

    assert assistant.list_assessment_summaries()[0].pending is True
    assistant.rejudge_pending_assessments()
    assert assistant.list_assessment_summaries()[0].pending is False
    assert assistant.list_assessment_summaries()[0].preference == "Strong"


def test_master_cv_yaml_content_change_marks_all_assessments_pending(
    tmp_path: Path,
) -> None:
    cv_path = _write_cv(tmp_path)
    assistant, _ = _crawl_with_master_cv(tmp_path)
    assistant.run_crawl()
    assistant.rejudge_pending_assessments()
    assert assistant.list_assessment_summaries()[0].pending is False

    cv_path.write_text(
        _SAMPLE_CV.replace("Platform engineer", "Staff platform engineer"),
        encoding="utf-8",
    )

    assert assistant.list_assessment_summaries()[0].pending is True
    assert "Staff platform engineer" in (
        assistant.get_candidate_snapshot().experience[0]
        if assistant.get_candidate_snapshot()
        else ""
    )


def test_path_clear_marks_all_assessments_pending(tmp_path: Path) -> None:
    prefs_path = tmp_path / "prefs.txt"
    prefs_path.write_text("Prefer remote\n", encoding="utf-8")
    constraints = FakeConstraintFilesStore()
    assistant, _ = _crawl_with_master_cv(
        tmp_path,
        llm_judge=FakeLlmJudge(preference="Mixed", relevance="Strong"),
        constraint_files=constraints,
    )
    assistant.set_preferences_path(str(prefs_path))
    assistant.run_crawl()
    assistant.rejudge_pending_assessments()
    assert assistant.list_assessment_summaries()[0].pending is False

    assistant.clear_preferences_path()

    assert assistant.list_assessment_summaries()[0].pending is True


def test_invalid_master_cv_yaml_keeps_relevance_pending_with_error(
    tmp_path: Path,
) -> None:
    entry, detail = _open_posting()
    job_board = FakeJobBoardSession(
        authenticated=True,
        list_entries=[entry],
        details={detail.id: detail},
    )
    broken = tmp_path / "broken_CV.yaml"
    broken.write_text("cv: [\n  not: valid\n", encoding="utf-8")
    assistant = _assistant(
        tmp_path,
        job_board=job_board,
        master_cv=FakeMasterCvStore(),
        llm_judge=FakeLlmJudge(relevance="Strong"),
    )
    assistant.set_master_cv_path(str(broken))
    assistant.run_crawl()
    assistant.rejudge_pending_assessments()

    summaries = assistant.list_assessment_summaries()
    assert len(summaries) == 1
    assert summaries[0].pending is True
    assert assistant.can_prepare(summaries[0].job_posting_id) is False
    assert assistant.get_candidate_snapshot() is None
    errors = assistant.get_candidate_file_errors()
    assert any("Master CV" in error for error in errors)
    assert broken.read_text(encoding="utf-8").startswith("cv: [")


def test_unreadable_master_cv_keeps_relevance_pending_with_error(tmp_path: Path) -> None:
    entry, detail = _open_posting()
    job_board = FakeJobBoardSession(
        authenticated=True,
        list_entries=[entry],
        details={detail.id: detail},
    )
    missing = tmp_path / "missing_CV.yaml"
    assistant = _assistant(
        tmp_path,
        job_board=job_board,
        master_cv=FakeMasterCvStore(path=str(missing)),
    )
    assistant.set_master_cv_path(str(missing))
    assistant.run_crawl()
    assistant.rejudge_pending_assessments()

    assert assistant.list_assessment_summaries()[0].pending is True
    assert assistant.get_candidate_snapshot() is None
    errors = assistant.get_candidate_file_errors()
    assert any("Master CV" in error for error in errors)


def test_unreadable_hard_constraints_path_is_unknown_not_pending(
    tmp_path: Path,
) -> None:
    constraints = FakeConstraintFilesStore()
    assistant, judge = _crawl_with_master_cv(tmp_path, constraint_files=constraints)
    missing = tmp_path / "gone-hard.txt"
    assistant.set_hard_constraints_path(str(missing))
    assistant.run_crawl()
    assistant.rejudge_pending_assessments()

    summary = assistant.list_assessment_summaries()[0]
    assert summary.pending is False
    assert summary.hard_constraint_outcome == "unknown"
    assert summary.relevance == "Strong"
    assert len(judge.hard_constraint_calls) == 0
    assert any(
        "not found" in error.lower() or "File not found" in error
        for error in assistant.get_candidate_file_errors()
    )


def test_crawl_detail_change_marks_pending_without_staling_packets(
    tmp_path: Path,
) -> None:
    entry, detail = _open_posting()
    job_board = FakeJobBoardSession(
        authenticated=True,
        list_entries=[entry],
        details={detail.id: detail},
    )
    judge = FakeLlmJudge(relevance="Weak")
    cv_path = _write_cv(tmp_path)
    assistant = _assistant(
        tmp_path,
        job_board=job_board,
        master_cv=FakeMasterCvStore(),
        llm_judge=judge,
    )
    assistant.set_master_cv_path(str(cv_path))
    assistant.run_crawl()
    assistant.rejudge_pending_assessments()
    assert assistant.list_assessment_summaries()[0].relevance == "Weak"
    assert assistant.list_assessment_summaries()[0].preparation_packet_stale is False

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
    judge2 = FakeLlmJudge(relevance="Strong")
    assistant = Assistant(
        catalog_store=CatalogStore(tmp_path / "catalog.db"),
        job_board=job_board,
        master_cv=FakeMasterCvStore(path=str(cv_path)),
        llm_judge=judge2,
        llm_cv_tailor=FakeLlmCvTailor(),
        constraint_files=FakeConstraintFilesStore(),
        crawl_pacer=FakeCrawlPacer(),
    )

    assistant.run_crawl()
    summary = assistant.list_assessment_summaries()[0]
    assert summary.title == "Senior System Engineer"
    assert summary.pending is True
    assert summary.preparation_packet_stale is False
    assert judge2.judge_calls == 0

    assistant.rejudge_pending_assessments()
    assert assistant.list_assessment_summaries()[0].relevance == "Strong"


def test_default_filter_hides_closed_and_passed_deadline(tmp_path: Path) -> None:
    job_board = FakeJobBoardSession(
        authenticated=True,
        list_entries=[
            JobListEntry(
                id="open-upcoming",
                title="Open Upcoming",
                employer="Acme",
                application_deadline="2026-12-01",
            ),
            JobListEntry(
                id="open-unknown",
                title="Open Unknown",
                employer="Acme",
                application_deadline=None,
            ),
            JobListEntry(
                id="closed",
                title="Closed Role",
                employer="Acme",
                application_deadline="2026-12-01",
            ),
            JobListEntry(
                id="passed",
                title="Passed Role",
                employer="Acme",
                application_deadline="2026-01-01",
            ),
        ],
    )
    cv_path = _write_cv(tmp_path)
    assistant = _assistant(
        tmp_path,
        job_board=job_board,
        master_cv=FakeMasterCvStore(),
        llm_judge=FakeLlmJudge(available=False),
    )
    assistant.set_master_cv_path(str(cv_path))
    assert assistant.run_crawl().status == "completed"

    job_board.set_list_entries(
        [
            JobListEntry(
                id="open-upcoming",
                title="Open Upcoming",
                employer="Acme",
                application_deadline="2026-12-01",
            ),
            JobListEntry(
                id="open-unknown",
                title="Open Unknown",
                employer="Acme",
                application_deadline=None,
            ),
            JobListEntry(
                id="passed",
                title="Passed Role",
                employer="Acme",
                application_deadline="2026-01-01",
            ),
        ]
    )
    assert assistant.run_crawl().status == "completed"

    default_ids = {row.job_posting_id for row in assistant.list_assessment_summaries()}
    with_closed = {
        row.job_posting_id
        for row in assistant.list_assessment_summaries(include_closed=True)
    }
    with_passed = {
        row.job_posting_id
        for row in assistant.list_assessment_summaries(include_passed_deadlines=True)
    }

    assert default_ids == {"open-upcoming", "open-unknown"}
    assert "closed" in with_closed
    assert "passed" in with_passed


def test_default_sort_preference_then_relevance_deadline_unknown_last(
    tmp_path: Path,
) -> None:
    assessed_entries = [
        JobListEntry(
            id="weak-pref-strong-rel",
            title="weak-pref-strong-rel",
            employer="Acme",
            application_deadline="2026-08-10",
        ),
        JobListEntry(
            id="strong-pref-later",
            title="strong-pref-later",
            employer="Acme",
            application_deadline="2026-10-01",
        ),
        JobListEntry(
            id="strong-pref-soon",
            title="strong-pref-soon",
            employer="Acme",
            application_deadline="2026-09-01",
        ),
        JobListEntry(
            id="strong-pref-unknown-deadline",
            title="strong-pref-unknown-deadline",
            employer="Acme",
            application_deadline=None,
        ),
        JobListEntry(
            id="fail-strong",
            title="fail-strong",
            employer="Acme",
            application_deadline="2026-08-20",
        ),
    ]
    details = {
        item.id: JobPostingDetail(
            id=item.id,
            title=item.title,
            employer=item.employer,
            application_deadline=item.application_deadline,
            fields={"Job Description": item.title},
        )
        for item in assessed_entries
    }
    job_board = FakeJobBoardSession(
        authenticated=True, list_entries=assessed_entries, details=details
    )
    prefs_path = tmp_path / "prefs.txt"
    prefs_path.write_text("Prefer engineering\n", encoding="utf-8")
    hc_path = tmp_path / "hard.txt"
    hc_path.write_text("Must not be sales\n", encoding="utf-8")
    constraints = FakeConstraintFilesStore()
    judge = FakeLlmJudge(
        # rejudge order is by job id, not crawl list order
        preferences=["Strong", "Strong", "Strong", "Strong", "Weak"],
        relevances=["Strong", "Mixed", "Strong", "Strong", "Strong"],
        hard_constraint_outcome="pass",
    )
    cv_path = _write_cv(tmp_path)
    assistant = _assistant(
        tmp_path,
        job_board=job_board,
        master_cv=FakeMasterCvStore(),
        llm_judge=judge,
        constraint_files=constraints,
    )
    assistant.set_master_cv_path(str(cv_path))
    assistant.set_preferences_path(str(prefs_path))
    assistant.set_hard_constraints_path(str(hc_path))
    assert assistant.run_crawl().stored_count == 5
    # Opportunistic rejudge budgets one Pending posting per call.
    for _ in range(5):
        assistant.rejudge_pending_assessments()

    assistant._catalog_store.save_match_assessment(
        MatchAssessment(
            job_posting_id="fail-strong",
            hard_constraint_outcome="fail",
            hard_constraint_reason="sales role",
            preference="Strong",
            preference_reason="ok",
            relevance="Strong",
            evidence=[
                EvidencePair(
                    job_excerpt="x",
                    candidate_excerpt="y",
                    role="supports",
                )
            ],
        )
    )

    pending_entry = JobListEntry(
        id="pending",
        title="pending",
        employer="Acme",
        application_deadline="2026-08-15",
    )
    job_board.set_list_entries([*assessed_entries, pending_entry])
    pending_assistant = _assistant(
        tmp_path,
        job_board=job_board,
        master_cv=FakeMasterCvStore(path=str(cv_path)),
        llm_judge=FakeLlmJudge(available=False),
        constraint_files=constraints,
    )
    assert pending_assistant.run_crawl().stored_count == 1

    ids = [row.job_posting_id for row in pending_assistant.list_assessment_summaries()]

    assert ids == [
        "strong-pref-soon",
        "strong-pref-unknown-deadline",
        "strong-pref-later",
        "weak-pref-strong-rel",
        "fail-strong",
        "pending",
    ]
