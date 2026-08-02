"""SQLite persistence for Job Postings, Match Assessments, and Preparation Packet metadata."""

from __future__ import annotations

import sqlite3
from pathlib import Path


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
                    deadline_status TEXT
                )
                """
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
