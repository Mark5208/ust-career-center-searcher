"""Assistant seam: Assessment Summary, Hard Constraints, Relevance, rebuild rules."""

from pathlib import Path

from job_finding_assistant.assistant import Assistant, Preferences
from job_finding_assistant.catalog_store import CatalogStore
from job_finding_assistant.fakes import (
    FakeCrawlPacer,
    FakeJobBoardSession,
    FakeLlmCvTailor,
    FakeLlmJudge,
    FakeMasterCvStore,
)
from job_finding_assistant.job_board import JobListEntry, JobPostingDetail
from job_finding_assistant.preferences import GapTolerance, LanguagePreference


def _assistant(
    tmp_path: Path,
    *,
    job_board: FakeJobBoardSession | None = None,
    master_cv: FakeMasterCvStore | None = None,
    llm_judge: FakeLlmJudge | None = None,
) -> Assistant:
    return Assistant(
        catalog_store=CatalogStore(tmp_path / "catalog.db"),
        job_board=job_board or FakeJobBoardSession(),
        master_cv=master_cv or FakeMasterCvStore(),
        llm_judge=llm_judge or FakeLlmJudge(relevance="Strong"),
        llm_cv_tailor=FakeLlmCvTailor(),
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
            "Language Requirement (Speaking)": "English required",
            "Language Requirement (Writing)": "English",
            "Employment Period": "3 months",
        },
    )
    return entry, detail


def test_crawl_builds_match_assessment_with_relevance_via_llm_judge(tmp_path: Path) -> None:
    entry, detail = _open_posting()
    job_board = FakeJobBoardSession(
        authenticated=True,
        list_entries=[entry],
        details={detail.id: detail},
    )
    judge = FakeLlmJudge(relevance="Strong")
    assistant = _assistant(tmp_path, job_board=job_board, llm_judge=judge)
    assistant.update_preferences(
        Preferences(
            languages=[LanguagePreference(language="English")],
            locations=["Hong Kong"],
            gap_tolerance=GapTolerance.SEMESTER,
        )
    )

    outcome = assistant.run_crawl()

    assert outcome.status == "completed"
    summaries = assistant.list_assessment_summaries()
    assert len(summaries) == 1
    summary = summaries[0]
    assert summary.pending is False
    assert summary.hard_constraint_outcome == "pass"
    assert summary.relevance == "Strong"
    assert summary.has_preparation_packet is False
    assert judge.judge_calls == 1


def test_assessment_stays_pending_when_llm_judge_unavailable(tmp_path: Path) -> None:
    entry, detail = _open_posting()
    job_board = FakeJobBoardSession(
        authenticated=True,
        list_entries=[entry],
        details={detail.id: detail},
    )
    assistant = _assistant(
        tmp_path,
        job_board=job_board,
        llm_judge=FakeLlmJudge(available=False),
    )

    assistant.run_crawl()

    summary = assistant.list_assessment_summaries()[0]
    assert summary.pending is True
    assert summary.relevance is None
    assert summary.hard_constraint_outcome is None
    assert assistant.can_prepare(summary.job_posting_id) is False


def test_prepare_unavailable_on_pending_and_available_after_assessment(
    tmp_path: Path,
) -> None:
    entry, detail = _open_posting()
    job_board = FakeJobBoardSession(
        authenticated=True,
        list_entries=[entry],
        details={detail.id: detail},
    )
    assistant = _assistant(
        tmp_path,
        job_board=job_board,
        llm_judge=FakeLlmJudge(available=False),
    )
    assistant.run_crawl()
    assert assistant.can_prepare("86534") is False

    # Rebuild becomes possible when a judge is available (new Assistant wiring).
    assistant = Assistant(
        catalog_store=CatalogStore(tmp_path / "catalog.db"),
        job_board=job_board,
        master_cv=FakeMasterCvStore(),
        llm_judge=FakeLlmJudge(relevance="Mixed"),
        llm_cv_tailor=FakeLlmCvTailor(),
        crawl_pacer=FakeCrawlPacer(),
    )
    assistant.update_preferences(
        Preferences(
            languages=[LanguagePreference(language="English")],
            locations=["Hong Kong"],
            gap_tolerance=GapTolerance.SEMESTER,
        )
    )

    assert assistant.list_assessment_summaries()[0].pending is False
    assert assistant.list_assessment_summaries()[0].hard_constraint_outcome == "pass"
    assert assistant.can_prepare("86534") is True


def test_prepare_unavailable_when_hard_constraint_fails(tmp_path: Path) -> None:
    entry, detail = _open_posting(
        fields={
            "Job Description": "Build systems.",
            "Work Location": "Singapore",
            "Language Requirement (Speaking)": "English required",
            "Employment Period": "3 months",
        }
    )
    job_board = FakeJobBoardSession(
        authenticated=True,
        list_entries=[entry],
        details={detail.id: detail},
    )
    assistant = _assistant(tmp_path, job_board=job_board)
    assistant.update_preferences(
        Preferences(
            languages=[LanguagePreference(language="English")],
            locations=["Hong Kong"],
            gap_tolerance=GapTolerance.SEMESTER,
        )
    )
    assistant.run_crawl()

    assert assistant.list_assessment_summaries()[0].hard_constraint_outcome == "fail"
    assert assistant.can_prepare("86534") is False


def test_crawl_detail_change_rebuilds_match_assessment(tmp_path: Path) -> None:
    entry, detail = _open_posting()
    job_board = FakeJobBoardSession(
        authenticated=True,
        list_entries=[entry],
        details={detail.id: detail},
    )
    judge = FakeLlmJudge(relevance="Weak")
    assistant = _assistant(tmp_path, job_board=job_board, llm_judge=judge)
    assistant.run_crawl()
    assert assistant.list_assessment_summaries()[0].relevance == "Weak"

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
        fields={
            **detail.fields,
            "Job Description": "Lead platform reliability work.",
        },
    )
    job_board.set_list_entries([changed_entry])
    job_board.set_details({changed_detail.id: changed_detail})
    judge = FakeLlmJudge(relevance="Strong")
    assistant = Assistant(
        catalog_store=CatalogStore(tmp_path / "catalog.db"),
        job_board=job_board,
        master_cv=FakeMasterCvStore(),
        llm_judge=judge,
        llm_cv_tailor=FakeLlmCvTailor(),
        crawl_pacer=FakeCrawlPacer(),
    )

    assistant.run_crawl()

    summary = assistant.list_assessment_summaries()[0]
    assert summary.title == "Senior System Engineer"
    assert summary.relevance == "Strong"
    assert judge.judge_calls == 1


def test_preferences_change_rebuilds_open_match_assessments(tmp_path: Path) -> None:
    entry, detail = _open_posting(
        fields={
            "Job Description": "Build systems.",
            "Work Location": "Singapore",
            "Language Requirement (Speaking)": "English required",
            "Language Requirement (Writing)": "English",
            "Employment Period": "3 months",
        }
    )
    job_board = FakeJobBoardSession(
        authenticated=True,
        list_entries=[entry],
        details={detail.id: detail},
    )
    assistant = _assistant(tmp_path, job_board=job_board)
    assistant.update_preferences(
        Preferences(
            languages=[LanguagePreference(language="English")],
            locations=["Hong Kong"],
            gap_tolerance=GapTolerance.SEMESTER,
        )
    )
    assistant.run_crawl()
    assert assistant.list_assessment_summaries()[0].hard_constraint_outcome == "fail"

    assistant.update_preferences(
        Preferences(
            languages=[LanguagePreference(language="English")],
            locations=["Singapore"],
            gap_tolerance=GapTolerance.SEMESTER,
        )
    )

    assert assistant.list_assessment_summaries()[0].hard_constraint_outcome == "pass"


def test_master_cv_change_rebuilds_open_match_assessments(tmp_path: Path) -> None:
    entry, detail = _open_posting()
    job_board = FakeJobBoardSession(
        authenticated=True,
        list_entries=[entry],
        details={detail.id: detail},
    )
    judge = FakeLlmJudge(relevance="Mixed")
    master_cv = FakeMasterCvStore()
    assistant = _assistant(
        tmp_path,
        job_board=job_board,
        master_cv=master_cv,
        llm_judge=judge,
    )
    assistant.run_crawl()
    assert judge.judge_calls == 1

    cv_path = tmp_path / "master.tex"
    cv_path.write_text(
        r"\documentclass{article}\begin{document}"
        r"\section{Experience}Platform engineer\end{document}",
        encoding="utf-8",
    )
    assistant.set_master_cv_path(str(cv_path))

    assert judge.judge_calls == 2
    assert assistant.list_assessment_summaries()[0].pending is False


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
    assistant = _assistant(
        tmp_path,
        job_board=job_board,
        llm_judge=FakeLlmJudge(available=False),
    )
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
    assert "open-upcoming" in with_closed
    assert "passed" in with_passed
    assert "open-upcoming" in with_passed


def test_default_sort_relevance_then_deadline_with_fail_and_pending_last(
    tmp_path: Path,
) -> None:
    assessed_entries = [
        JobListEntry(
            id="weak-soon",
            title="weak-soon",
            employer="Acme",
            application_deadline="2026-08-10",
        ),
        JobListEntry(
            id="strong-later",
            title="strong-later",
            employer="Acme",
            application_deadline="2026-10-01",
        ),
        JobListEntry(
            id="strong-soon",
            title="strong-soon",
            employer="Acme",
            application_deadline="2026-09-01",
        ),
        JobListEntry(
            id="fail-strong",
            title="fail-strong",
            employer="Acme",
            application_deadline="2026-08-20",
        ),
    ]
    details = {
        "weak-soon": JobPostingDetail(
            id="weak-soon",
            title="weak-soon",
            employer="Acme",
            application_deadline="2026-08-10",
            fields={"Work Location": "Hong Kong", "Job Description": "A"},
        ),
        "strong-later": JobPostingDetail(
            id="strong-later",
            title="strong-later",
            employer="Acme",
            application_deadline="2026-10-01",
            fields={"Work Location": "Hong Kong", "Job Description": "B"},
        ),
        "strong-soon": JobPostingDetail(
            id="strong-soon",
            title="strong-soon",
            employer="Acme",
            application_deadline="2026-09-01",
            fields={"Work Location": "Hong Kong", "Job Description": "C"},
        ),
        "fail-strong": JobPostingDetail(
            id="fail-strong",
            title="fail-strong",
            employer="Acme",
            application_deadline="2026-08-20",
            fields={"Work Location": "Singapore", "Job Description": "D"},
        ),
    }
    job_board = FakeJobBoardSession(
        authenticated=True, list_entries=assessed_entries, details=details
    )
    # Crawl order follows list order: weak, strong-later, strong-soon, fail.
    judge = FakeLlmJudge(relevances=["Weak", "Strong", "Strong", "Strong"])
    assistant = _assistant(tmp_path, job_board=job_board, llm_judge=judge)
    assistant.update_preferences(
        Preferences(languages=[], locations=["Hong Kong"], gap_tolerance=None)
    )
    assert assistant.run_crawl().stored_count == 4

    pending_entry = JobListEntry(
        id="pending",
        title="pending",
        employer="Acme",
        application_deadline="2026-08-05",
    )
    job_board.set_list_entries([*assessed_entries, pending_entry])
    pending_assistant = _assistant(
        tmp_path,
        job_board=job_board,
        llm_judge=FakeLlmJudge(available=False),
    )
    assert pending_assistant.run_crawl().stored_count == 1

    ids = [row.job_posting_id for row in pending_assistant.list_assessment_summaries()]

    assert ids == [
        "strong-soon",
        "strong-later",
        "weak-soon",
        "fail-strong",
        "pending",
    ]
