"""SQLite persistence for Job Postings, Preferences, and later assessment metadata."""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

from job_finding_assistant.crawl_filters import CrawlFilters
from job_finding_assistant.preferences import GapTolerance, LanguagePreference, Preferences


class CatalogStore:
    """Local catalog backed by SQLite. Schema may grow; empty catalog is valid."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS job_postings (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    employer TEXT,
                    listing_status TEXT,
                    deadline_status TEXT,
                    posting_date TEXT,
                    application_deadline TEXT,
                    detail_json TEXT,
                    list_fingerprint TEXT
                )
                """
            )
            self._ensure_job_posting_columns(connection)
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS preferences (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    languages_json TEXT NOT NULL,
                    locations_json TEXT NOT NULL,
                    gap_tolerance TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS crawl_filters (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    filters_json TEXT NOT NULL
                )
                """
            )

    def _ensure_job_posting_columns(self, connection: sqlite3.Connection) -> None:
        existing = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(job_postings)").fetchall()
        }
        for column, sql_type in (
            ("posting_date", "TEXT"),
            ("application_deadline", "TEXT"),
            ("detail_json", "TEXT"),
            ("list_fingerprint", "TEXT"),
        ):
            if column not in existing:
                connection.execute(
                    f"ALTER TABLE job_postings ADD COLUMN {column} {sql_type}"
                )

    def list_assessment_summary_rows(self) -> list[dict[str, str]]:
        """Return stored rows used to build Assessment Summaries (empty when none)."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, title, employer, listing_status, deadline_status
                FROM job_postings
                ORDER BY id
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def get_preferences(self) -> Preferences:
        """Return Preferences; missing row means all fields empty/unset."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT languages_json, locations_json, gap_tolerance
                FROM preferences
                WHERE id = 1
                """
            ).fetchone()
        if row is None:
            return Preferences(languages=[], locations=[], gap_tolerance=None)
        languages_raw = json.loads(row["languages_json"])
        locations_raw = json.loads(row["locations_json"])
        gap_raw = row["gap_tolerance"]
        return Preferences(
            languages=[
                LanguagePreference(
                    language=item["language"],
                    level=item.get("level"),
                )
                for item in languages_raw
            ],
            locations=list(locations_raw),
            gap_tolerance=GapTolerance(gap_raw) if gap_raw is not None else None,
        )

    def save_preferences(self, preferences: Preferences) -> None:
        """Persist Preferences as a singleton row (no Crawl Filters)."""
        languages_json = json.dumps(
            [
                {"language": item.language, "level": item.level}
                for item in preferences.languages
            ]
        )
        locations_json = json.dumps(list(preferences.locations))
        gap_tolerance = (
            preferences.gap_tolerance.value if preferences.gap_tolerance is not None else None
        )
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO preferences (id, languages_json, locations_json, gap_tolerance)
                VALUES (1, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    languages_json = excluded.languages_json,
                    locations_json = excluded.locations_json,
                    gap_tolerance = excluded.gap_tolerance
                """,
                (languages_json, locations_json, gap_tolerance),
            )

    def get_job_posting(self, job_posting_id: str) -> dict[str, str | None] | None:
        """Return one stored Job Posting row, or None."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, title, employer, listing_status, deadline_status,
                       posting_date, application_deadline, detail_json, list_fingerprint
                FROM job_postings
                WHERE id = ?
                """,
                (job_posting_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    def upsert_job_posting(
        self,
        *,
        job_posting_id: str,
        title: str,
        employer: str,
        listing_status: str,
        deadline_status: str,
        posting_date: str | None,
        application_deadline: str | None,
        detail_json: str,
        list_fingerprint: str,
    ) -> None:
        """Insert or update a Job Posting from Crawl detail fetch."""
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO job_postings (
                    id, title, employer, listing_status, deadline_status,
                    posting_date, application_deadline, detail_json, list_fingerprint
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    employer = excluded.employer,
                    listing_status = excluded.listing_status,
                    deadline_status = excluded.deadline_status,
                    posting_date = excluded.posting_date,
                    application_deadline = excluded.application_deadline,
                    detail_json = excluded.detail_json,
                    list_fingerprint = excluded.list_fingerprint
                """,
                (
                    job_posting_id,
                    title,
                    employer,
                    listing_status,
                    deadline_status,
                    posting_date,
                    application_deadline,
                    detail_json,
                    list_fingerprint,
                ),
            )

    def set_listing_status(self, job_posting_id: str, listing_status: str) -> None:
        """Update Listing status for one Job Posting."""
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE job_postings
                SET listing_status = ?
                WHERE id = ?
                """,
                (listing_status, job_posting_id),
            )

    def mark_missing_open_postings_closed(self, seen_ids: set[str]) -> None:
        """Mark Open postings absent from a Closing-capable list sync as Closed."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id FROM job_postings
                WHERE listing_status = 'Open'
                """
            ).fetchall()
            for row in rows:
                if row["id"] not in seen_ids:
                    connection.execute(
                        """
                        UPDATE job_postings
                        SET listing_status = 'Closed'
                        WHERE id = ?
                        """,
                        (row["id"],),
                    )

    def get_crawl_filters(self) -> CrawlFilters:
        """Return Crawl Filters; missing row means Active Job default."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT filters_json
                FROM crawl_filters
                WHERE id = 1
                """
            ).fetchone()
        if row is None:
            return CrawlFilters()
        return _crawl_filters_from_json(row["filters_json"])

    def save_crawl_filters(self, filters: CrawlFilters) -> None:
        """Persist Crawl Filters as a singleton row."""
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO crawl_filters (id, filters_json)
                VALUES (1, ?)
                ON CONFLICT(id) DO UPDATE SET filters_json = excluded.filters_json
                """,
                (_crawl_filters_to_json(filters),),
            )


def _crawl_filters_to_json(filters: CrawlFilters) -> str:
    return json.dumps(
        {
            "business_natures": list(filters.business_natures),
            "job_natures": list(filters.job_natures),
            "employment_types": list(filters.employment_types),
            "working_locations": list(filters.working_locations),
            "levels_of_qualification": list(filters.levels_of_qualification),
            "employment_modes": list(filters.employment_modes),
            "languages": list(filters.languages),
            "talent_wise_employment_charter": filters.talent_wise_employment_charter,
            "active_job": filters.active_job,
            "non_chinese_speaking_students": filters.non_chinese_speaking_students,
            "deadline_hardline": (
                filters.deadline_hardline.isoformat()
                if filters.deadline_hardline is not None
                else None
            ),
        }
    )


def _crawl_filters_from_json(raw: str) -> CrawlFilters:
    data = json.loads(raw)
    hardline_raw = data.get("deadline_hardline")
    return CrawlFilters(
        business_natures=tuple(data.get("business_natures", ())),
        job_natures=tuple(data.get("job_natures", ())),
        employment_types=tuple(data.get("employment_types", ())),
        working_locations=tuple(data.get("working_locations", ())),
        levels_of_qualification=tuple(data.get("levels_of_qualification", ())),
        employment_modes=tuple(data.get("employment_modes", ())),
        languages=tuple(data.get("languages", ())),
        talent_wise_employment_charter=bool(
            data.get("talent_wise_employment_charter", False)
        ),
        active_job=bool(data.get("active_job", True)),
        non_chinese_speaking_students=bool(
            data.get("non_chinese_speaking_students", False)
        ),
        deadline_hardline=date.fromisoformat(hardline_raw) if hardline_raw else None,
    )
