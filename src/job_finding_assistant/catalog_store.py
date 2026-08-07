"""SQLite persistence for Job Postings, fingerprints, and Match Assessments."""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path
from typing import cast

from job_finding_assistant.crawl_filters import CrawlFilters
from job_finding_assistant.match_assessment import (
    ConstraintOutcome,
    EvidencePair,
    MatchAssessment,
    PreferenceBand,
    RelevanceBand,
)


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
                CREATE TABLE IF NOT EXISTS crawl_filters (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    filters_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS candidate_fingerprints (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    master_cv_fingerprint TEXT,
                    hard_constraints_fingerprint TEXT,
                    preferences_fingerprint TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS match_assessments (
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
            self._migrate_match_assessments(connection)

    def _migrate_match_assessments(self, connection: sqlite3.Connection) -> None:
        """Upgrade legacy named-constraint schema to freeform three-signal rows."""
        existing = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(match_assessments)").fetchall()
        }
        if not existing:
            return
        if "preference" in existing and "hard_constraint_reason" in existing:
            return
        connection.execute("DROP TABLE IF EXISTS match_assessments")
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

    def list_assessment_summary_rows(self) -> list[dict[str, str | None]]:
        """Return Job Posting rows joined with Match Assessment fields when present."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    p.id,
                    p.title,
                    p.employer,
                    p.listing_status,
                    p.deadline_status,
                    p.application_deadline,
                    a.hard_constraint_outcome,
                    a.preference,
                    a.relevance
                FROM job_postings AS p
                LEFT JOIN match_assessments AS a ON a.job_posting_id = p.id
                ORDER BY p.id
                """
            ).fetchall()
        return [dict(row) for row in rows]

    def list_all_job_posting_ids(self) -> list[str]:
        """Return ids of all Job Postings (Open and Closed)."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id FROM job_postings
                ORDER BY id
                """
            ).fetchall()
        return [row["id"] for row in rows]

    def list_pending_job_posting_ids(self) -> list[str]:
        """Return Job Posting ids that have detail but no Match Assessment yet."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT p.id
                FROM job_postings AS p
                LEFT JOIN match_assessments AS a ON a.job_posting_id = p.id
                WHERE p.detail_json IS NOT NULL
                  AND p.detail_json != ''
                  AND a.job_posting_id IS NULL
                ORDER BY p.id
                """
            ).fetchall()
        return [row["id"] for row in rows]

    def clear_all_match_assessments(self) -> None:
        """Mark every Match Assessment Pending by deleting stored rows."""
        with self._connect() as connection:
            connection.execute("DELETE FROM match_assessments")

    def clear_match_assessment(self, job_posting_id: str) -> None:
        """Mark one Match Assessment Pending by deleting its stored row."""
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM match_assessments WHERE job_posting_id = ?",
                (job_posting_id,),
            )

    def save_match_assessment(self, assessment: MatchAssessment) -> None:
        """Insert or replace the Match Assessment for one Job Posting."""
        evidence_json = json.dumps(
            [
                {
                    "job_excerpt": item.job_excerpt,
                    "candidate_excerpt": item.candidate_excerpt,
                    "role": item.role,
                }
                for item in assessment.evidence
            ]
        )
        with self._connect() as connection:
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
                ON CONFLICT(job_posting_id) DO UPDATE SET
                    hard_constraint_outcome = excluded.hard_constraint_outcome,
                    hard_constraint_reason = excluded.hard_constraint_reason,
                    preference = excluded.preference,
                    preference_reason = excluded.preference_reason,
                    relevance = excluded.relevance,
                    evidence_json = excluded.evidence_json
                """,
                (
                    assessment.job_posting_id,
                    assessment.hard_constraint_outcome,
                    assessment.hard_constraint_reason,
                    assessment.preference,
                    assessment.preference_reason,
                    assessment.relevance,
                    evidence_json,
                ),
            )

    def get_match_assessment(self, job_posting_id: str) -> MatchAssessment | None:
        """Return the stored Match Assessment, or None when Pending."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    job_posting_id,
                    hard_constraint_outcome,
                    hard_constraint_reason,
                    preference,
                    preference_reason,
                    relevance,
                    evidence_json
                FROM match_assessments
                WHERE job_posting_id = ?
                """,
                (job_posting_id,),
            ).fetchone()
        if row is None:
            return None
        evidence_raw = json.loads(row["evidence_json"])
        preference_raw = row["preference"]
        return MatchAssessment(
            job_posting_id=row["job_posting_id"],
            hard_constraint_outcome=cast(
                ConstraintOutcome, row["hard_constraint_outcome"]
            ),
            hard_constraint_reason=row["hard_constraint_reason"],
            preference=cast(PreferenceBand, preference_raw) if preference_raw else None,
            preference_reason=row["preference_reason"],
            relevance=cast(RelevanceBand, row["relevance"]),
            evidence=[
                EvidencePair(
                    job_excerpt=item["job_excerpt"],
                    candidate_excerpt=item["candidate_excerpt"],
                    role=item["role"],
                )
                for item in evidence_raw
            ],
        )

    def get_candidate_fingerprints(self) -> dict[str, str | None]:
        """Return last-seen Master CV / HC / Preferences content fingerprints."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    master_cv_fingerprint,
                    hard_constraints_fingerprint,
                    preferences_fingerprint
                FROM candidate_fingerprints
                WHERE id = 1
                """
            ).fetchone()
        if row is None:
            return {
                "master_cv_fingerprint": None,
                "hard_constraints_fingerprint": None,
                "preferences_fingerprint": None,
            }
        return dict(row)

    def save_candidate_fingerprints(
        self,
        *,
        master_cv_fingerprint: str | None,
        hard_constraints_fingerprint: str | None,
        preferences_fingerprint: str | None,
    ) -> None:
        """Persist last-seen candidate-file fingerprints."""
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO candidate_fingerprints (
                    id,
                    master_cv_fingerprint,
                    hard_constraints_fingerprint,
                    preferences_fingerprint
                )
                VALUES (1, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    master_cv_fingerprint = excluded.master_cv_fingerprint,
                    hard_constraints_fingerprint = excluded.hard_constraints_fingerprint,
                    preferences_fingerprint = excluded.preferences_fingerprint
                """,
                (
                    master_cv_fingerprint,
                    hard_constraints_fingerprint,
                    preferences_fingerprint,
                ),
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
