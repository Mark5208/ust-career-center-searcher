"""SQLite persistence for Job Postings, Preferences, and later assessment metadata."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

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
                    deadline_status TEXT
                )
                """
            )
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
