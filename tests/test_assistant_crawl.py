"""Assistant seam: User-Attended Login, Crawl Filters, and Crawl into catalog."""

from datetime import date
from pathlib import Path

from job_finding_assistant.assistant import Assistant, CrawlFilters
from job_finding_assistant.catalog_store import CatalogStore
from job_finding_assistant.fakes import (
    FakeJobBoardSession,
    FakeLlmCvTailor,
    FakeLlmJudge,
    FakeMasterCvStore,
)


def _assistant(
    tmp_path: Path,
    *,
    job_board: FakeJobBoardSession | None = None,
) -> Assistant:
    return Assistant(
        catalog_store=CatalogStore(tmp_path / "catalog.db"),
        job_board=job_board or FakeJobBoardSession(),
        master_cv=FakeMasterCvStore(),
        llm_judge=FakeLlmJudge(),
        llm_cv_tailor=FakeLlmCvTailor(),
    )


def test_assistant_crawl_filters_default_to_active_job_only(tmp_path: Path) -> None:
    assistant = _assistant(tmp_path)

    filters = assistant.get_crawl_filters()

    assert filters == CrawlFilters(
        business_natures=(),
        job_natures=(),
        employment_types=(),
        working_locations=(),
        levels_of_qualification=(),
        employment_modes=(),
        languages=(),
        talent_wise_employment_charter=False,
        active_job=True,
        non_chinese_speaking_students=False,
        deadline_hardline=None,
    )
    assert filters.is_closing_capable()


def test_assistant_persists_crawl_filters(tmp_path: Path) -> None:
    assistant = _assistant(tmp_path)
    filters = CrawlFilters(
        business_natures=("IT",),
        active_job=True,
        deadline_hardline=date(2026, 9, 1),
    )

    assistant.update_crawl_filters(filters)

    reloaded = _assistant(tmp_path).get_crawl_filters()
    assert reloaded == filters
    assert not reloaded.is_closing_capable()


def test_assistant_refuses_crawl_until_user_attended_login(tmp_path: Path) -> None:
    job_board = FakeJobBoardSession(authenticated=False)
    assistant = _assistant(tmp_path, job_board=job_board)

    assert not assistant.can_start_crawl()
    outcome = assistant.run_crawl()
    assert outcome.status == "not_authenticated"
    assert assistant.list_assessment_summaries() == []
    assert job_board.discover_calls == 0


def test_assistant_user_attended_login_opens_browser_without_storing_passwords(
    tmp_path: Path,
) -> None:
    job_board = FakeJobBoardSession(authenticated=False)
    assistant = _assistant(tmp_path, job_board=job_board)

    assistant.start_user_attended_login()

    assert job_board.open_login_calls == 1
    assert not hasattr(job_board, "password")
    assert not hasattr(assistant, "password")


def test_assistant_incremental_crawl_stores_job_postings_in_catalog(tmp_path: Path) -> None:
    from job_finding_assistant.job_board import JobListEntry, JobPostingDetail

    job_board = FakeJobBoardSession(
        authenticated=True,
        list_entries=[
            JobListEntry(
                id="86534",
                title="System Engineer",
                employer="Example Corp",
                posting_date="2026-07-01",
                application_deadline="2026-12-31",
            )
        ],
        details={
            "86534": JobPostingDetail(
                id="86534",
                title="System Engineer",
                employer="Example Corp",
                posting_date="2026-07-01",
                application_deadline="2026-12-31",
                fields={"Job Description": "Build reliable systems."},
            )
        },
    )
    assistant = _assistant(tmp_path, job_board=job_board)

    outcome = assistant.run_crawl()

    assert outcome.status == "completed"
    assert outcome.stored_count == 1
    summaries = assistant.list_assessment_summaries()
    assert len(summaries) == 1
    assert summaries[0].job_posting_id == "86534"
    assert summaries[0].title == "System Engineer"
    assert summaries[0].employer == "Example Corp"
    assert summaries[0].listing_status == "Open"
    assert summaries[0].deadline_status == "Upcoming"
    assert job_board.fetch_detail_ids == ["86534"]

    # Incremental: unchanged posting is not detail-fetched again.
    job_board.fetch_detail_ids.clear()
    second = assistant.run_crawl()
    assert second.status == "completed"
    assert second.stored_count == 0
    assert job_board.fetch_detail_ids == []


def test_assistant_deadline_hardline_skips_detail_fetch_and_catalog_add(
    tmp_path: Path,
) -> None:
    from job_finding_assistant.job_board import JobListEntry

    job_board = FakeJobBoardSession(
        authenticated=True,
        list_entries=[
            JobListEntry(
                id="old",
                title="Old Role",
                employer="Acme",
                application_deadline="2026-01-01",
            ),
            JobListEntry(
                id="new",
                title="New Role",
                employer="Acme",
                application_deadline="2026-12-01",
            ),
        ],
    )
    assistant = _assistant(tmp_path, job_board=job_board)
    assistant.update_crawl_filters(
        CrawlFilters(active_job=True, deadline_hardline=date(2026, 6, 1))
    )

    outcome = assistant.run_crawl()

    assert outcome.status == "completed"
    assert outcome.stored_count == 1
    assert job_board.fetch_detail_ids == ["new"]
    ids = {row.job_posting_id for row in assistant.list_assessment_summaries()}
    assert ids == {"new"}


def test_assistant_full_refresh_refetches_in_scope_open_postings(tmp_path: Path) -> None:
    from job_finding_assistant.job_board import JobListEntry

    entry = JobListEntry(
        id="86534",
        title="System Engineer",
        employer="Example Corp",
        posting_date="2026-07-01",
        application_deadline="2026-12-31",
    )
    job_board = FakeJobBoardSession(authenticated=True, list_entries=[entry])
    assistant = _assistant(tmp_path, job_board=job_board)
    assert assistant.run_crawl().stored_count == 1
    job_board.fetch_detail_ids.clear()

    outcome = assistant.run_crawl(full_refresh=True)

    assert outcome.status == "completed"
    assert outcome.stored_count == 1
    assert job_board.fetch_detail_ids == ["86534"]


def test_assistant_narrow_filters_do_not_mark_absent_postings_closed(
    tmp_path: Path,
) -> None:
    from job_finding_assistant.job_board import JobListEntry

    job_board = FakeJobBoardSession(
        authenticated=True,
        list_entries=[
            JobListEntry(
                id="keep",
                title="Keep Me",
                employer="Acme",
                application_deadline="2026-12-31",
            ),
            JobListEntry(
                id="gone-from-narrow",
                title="Gone Narrow",
                employer="Acme",
                application_deadline="2026-12-31",
            ),
        ],
    )
    assistant = _assistant(tmp_path, job_board=job_board)
    assert assistant.run_crawl().status == "completed"

    job_board.set_list_entries(
        [
            JobListEntry(
                id="keep",
                title="Keep Me",
                employer="Acme",
                application_deadline="2026-12-31",
            )
        ]
    )
    assistant.update_crawl_filters(CrawlFilters(business_natures=("IT",), active_job=True))
    outcome = assistant.run_crawl()

    assert outcome.status == "completed"
    by_id = {row.job_posting_id: row for row in assistant.list_assessment_summaries()}
    assert by_id["keep"].listing_status == "Open"
    assert by_id["gone-from-narrow"].listing_status == "Open"


def test_assistant_closing_capable_crawl_marks_absent_postings_closed(
    tmp_path: Path,
) -> None:
    from job_finding_assistant.job_board import JobListEntry

    job_board = FakeJobBoardSession(
        authenticated=True,
        list_entries=[
            JobListEntry(
                id="keep",
                title="Keep Me",
                employer="Acme",
                application_deadline="2026-12-31",
            ),
            JobListEntry(
                id="gone",
                title="Gone",
                employer="Acme",
                application_deadline="2026-12-31",
            ),
        ],
    )
    assistant = _assistant(tmp_path, job_board=job_board)
    assert assistant.run_crawl().status == "completed"

    job_board.set_list_entries(
        [
            JobListEntry(
                id="keep",
                title="Keep Me",
                employer="Acme",
                application_deadline="2026-12-31",
            )
        ]
    )
    # Active-Job-only remains Closing-capable.
    assistant.update_crawl_filters(CrawlFilters(active_job=True))
    outcome = assistant.run_crawl()

    assert outcome.status == "completed"
    by_id = {row.job_posting_id: row for row in assistant.list_assessment_summaries()}
    assert by_id["keep"].listing_status == "Open"
    assert by_id["gone"].listing_status == "Closed"


def test_assistant_reopens_closed_posting_when_it_reappears_on_list(
    tmp_path: Path,
) -> None:
    from job_finding_assistant.job_board import JobListEntry

    entry = JobListEntry(
        id="86534",
        title="System Engineer",
        employer="Example Corp",
        posting_date="2026-07-01",
        application_deadline="2026-12-31",
    )
    job_board = FakeJobBoardSession(authenticated=True, list_entries=[entry])
    assistant = _assistant(tmp_path, job_board=job_board)
    assert assistant.run_crawl().status == "completed"

    job_board.set_list_entries([])
    assert assistant.run_crawl().status == "completed"
    assert assistant.list_assessment_summaries()[0].listing_status == "Closed"

    job_board.set_list_entries([entry])
    job_board.fetch_detail_ids.clear()
    outcome = assistant.run_crawl()

    assert outcome.status == "completed"
    assert job_board.fetch_detail_ids == []
    assert assistant.list_assessment_summaries()[0].listing_status == "Open"


def test_assistant_auth_loss_mid_crawl_is_partial_success_without_closing(
    tmp_path: Path,
) -> None:
    from job_finding_assistant.job_board import JobListEntry

    job_board = FakeJobBoardSession(
        authenticated=True,
        list_entries=[
            JobListEntry(
                id="a",
                title="Role A",
                employer="Acme",
                application_deadline="2026-12-31",
            ),
            JobListEntry(
                id="b",
                title="Role B",
                employer="Acme",
                application_deadline="2026-12-31",
            ),
        ],
        auth_lost_after_details=1,
    )
    # Seed an Open posting that is absent from this list; must stay Open on auth loss.
    seed_board = FakeJobBoardSession(
        authenticated=True,
        list_entries=[
            JobListEntry(
                id="untouched",
                title="Untouched",
                employer="Other",
                application_deadline="2026-12-31",
            )
        ],
    )
    seed = _assistant(tmp_path, job_board=seed_board)
    assert seed.run_crawl().stored_count == 1

    assistant = _assistant(tmp_path, job_board=job_board)
    outcome = assistant.run_crawl()

    assert outcome.status == "partial_success"
    assert outcome.stored_count == 1
    by_id = {row.job_posting_id: row for row in assistant.list_assessment_summaries()}
    assert by_id["a"].listing_status == "Open"
    assert "b" not in by_id
    assert by_id["untouched"].listing_status == "Open"
