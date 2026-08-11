"""CatalogStore seam: typed Job Posting get/upsert (detail_json stays adapter-private)."""

from pathlib import Path

from job_finding_assistant.catalog_store import CatalogStore, JobPosting


def test_upsert_and_get_job_posting_round_trips_typed_fields(tmp_path: Path) -> None:
    store = CatalogStore(tmp_path / "catalog.db")
    posting = JobPosting(
        id="86534",
        title="System Engineer",
        employer="Example Corp",
        listing_status="Open",
        deadline_status="Upcoming",
        posting_date="2026-07-01",
        application_deadline="2026-12-31",
        detail_fields={"Job Description": "Build reliable systems in Python."},
        list_fingerprint="fp-1",
    )

    store.upsert_job_posting(posting)
    loaded = store.get_job_posting("86534")

    assert loaded == posting
    assert loaded.fields_for_llm() == {
        "Job Description": "Build reliable systems in Python.",
        "title": "System Engineer",
        "employer": "Example Corp",
    }


def test_get_job_posting_unknown_returns_none(tmp_path: Path) -> None:
    store = CatalogStore(tmp_path / "catalog.db")

    assert store.get_job_posting("missing") is None


def test_apply_crawl_list_presence_unchanged_ensures_open(tmp_path: Path) -> None:
    store = CatalogStore(tmp_path / "catalog.db")
    store.upsert_job_posting(
        JobPosting(
            id="86534",
            title="System Engineer",
            employer="Example Corp",
            listing_status="Closed",
            deadline_status="Upcoming",
            posting_date="2026-07-01",
            application_deadline="2026-12-31",
            detail_fields={"Job Description": "x"},
            list_fingerprint="fp-1",
        )
    )

    outcome = store.apply_crawl_list_presence(
        "86534", list_fingerprint="fp-1", full_refresh=False
    )

    assert outcome == "unchanged"
    loaded = store.get_job_posting("86534")
    assert loaded is not None
    assert loaded.listing_status == "Open"


def test_apply_crawl_list_presence_needs_detail_when_fingerprint_changes(
    tmp_path: Path,
) -> None:
    store = CatalogStore(tmp_path / "catalog.db")
    store.upsert_job_posting(
        JobPosting(
            id="86534",
            title="System Engineer",
            employer="Example Corp",
            listing_status="Open",
            deadline_status="Upcoming",
            posting_date="2026-07-01",
            application_deadline="2026-12-31",
            detail_fields={"Job Description": "x"},
            list_fingerprint="fp-1",
        )
    )

    assert (
        store.apply_crawl_list_presence(
            "86534", list_fingerprint="fp-2", full_refresh=False
        )
        == "needs_detail"
    )
    assert (
        store.apply_crawl_list_presence(
            "86534", list_fingerprint="fp-1", full_refresh=True
        )
        == "needs_detail"
    )
    assert (
        store.apply_crawl_list_presence(
            "missing", list_fingerprint="fp-1", full_refresh=False
        )
        == "needs_detail"
    )


def test_commit_crawl_detail_upserts_and_clears_assessment(tmp_path: Path) -> None:
    store = CatalogStore(tmp_path / "catalog.db")
    from job_finding_assistant.match_assessment import MatchAssessment

    store.upsert_job_posting(
        JobPosting(
            id="86534",
            title="Old",
            employer="Old Co",
            listing_status="Open",
            deadline_status="Upcoming",
            posting_date=None,
            application_deadline=None,
            detail_fields={"Job Description": "old"},
            list_fingerprint="fp-old",
        )
    )
    store.save_match_assessment(
        MatchAssessment(
            job_posting_id="86534",
            hard_constraint_outcome="pass",
            hard_constraint_reason="ok",
            preference="Strong",
            preference_reason="ok",
            relevance="Strong",
            evidence=[],
        )
    )

    store.commit_crawl_detail(
        JobPosting(
            id="86534",
            title="System Engineer",
            employer="Example Corp",
            listing_status="Open",
            deadline_status="Upcoming",
            posting_date="2026-07-01",
            application_deadline="2026-12-31",
            detail_fields={"Job Description": "new"},
            list_fingerprint="fp-new",
        )
    )

    loaded = store.get_job_posting("86534")
    assert loaded is not None
    assert loaded.title == "System Engineer"
    assert loaded.list_fingerprint == "fp-new"
    assert store.get_match_assessment("86534") is None
