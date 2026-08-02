"""FastAPI bootstrap: Jinja pages call Assistant only."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

import uvicorn
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from job_finding_assistant.assistant import (
    AssessmentSummary,
    Assistant,
    GapTolerance,
    LanguagePreference,
    Preferences,
)
from job_finding_assistant.candidate_snapshot import CandidateSnapshot
from job_finding_assistant.catalog_store import CatalogStore
from job_finding_assistant.fakes import (
    FakeJobBoardSession,
    FakeLlmCvTailor,
    FakeLlmJudge,
)
from job_finding_assistant.master_cv_store import DiskMasterCvStore

_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


class SupportsAssistantUi(Protocol):
    def list_assessment_summaries(self) -> list[AssessmentSummary]:
        """Return Assessment Summaries for the catalog page."""

    def get_master_cv_path(self) -> str | None:
        """Return the configured Master CV path."""

    def set_master_cv_path(self, path: str) -> None:
        """Set the Master CV path without overwriting the file."""

    def get_candidate_snapshot(self) -> CandidateSnapshot | None:
        """Return the Candidate Snapshot."""

    def get_preferences(self) -> Preferences:
        """Return Preferences."""

    def update_preferences(self, preferences: Preferences) -> None:
        """Persist Preferences."""


def _parse_languages(raw: str) -> list[LanguagePreference]:
    languages: list[LanguagePreference] = []
    for line in raw.splitlines():
        text = line.strip()
        if not text:
            continue
        if ":" in text:
            name, level = text.split(":", 1)
            languages.append(
                LanguagePreference(language=name.strip(), level=level.strip() or None)
            )
        else:
            languages.append(LanguagePreference(language=text, level=None))
    return languages


def _parse_locations(raw: str) -> list[str]:
    return [line.strip() for line in raw.splitlines() if line.strip()]


def _parse_gap_tolerance(raw: str) -> GapTolerance | None:
    text = raw.strip()
    if not text or text == "unset":
        return None
    return GapTolerance(text)


def create_app(assistant: SupportsAssistantUi) -> FastAPI:
    """Build the local UI app wired to a single Assistant (or test double)."""
    app = FastAPI(title="Job Finding Assistant")
    app.state.assistant = assistant

    @app.get("/", response_class=HTMLResponse)
    def assessment_summaries_page(request: Request) -> HTMLResponse:
        summaries = request.app.state.assistant.list_assessment_summaries()
        return _TEMPLATES.TemplateResponse(
            request,
            "assessment_summaries.html",
            {"summaries": summaries},
        )

    @app.get("/candidate", response_class=HTMLResponse)
    def candidate_page(request: Request) -> HTMLResponse:
        current = request.app.state.assistant
        preferences = current.get_preferences()
        languages_text = "\n".join(
            f"{item.language}:{item.level}" if item.level else item.language
            for item in preferences.languages
        )
        locations_text = "\n".join(preferences.locations)
        gap_value = (
            preferences.gap_tolerance.value
            if preferences.gap_tolerance is not None
            else "unset"
        )
        return _TEMPLATES.TemplateResponse(
            request,
            "candidate.html",
            {
                "master_cv_path": current.get_master_cv_path() or "",
                "snapshot": current.get_candidate_snapshot(),
                "languages_text": languages_text,
                "locations_text": locations_text,
                "gap_tolerance": gap_value,
            },
        )

    @app.post("/candidate/master-cv")
    def set_master_cv_path(master_cv_path: str = Form(...)) -> RedirectResponse:
        app.state.assistant.set_master_cv_path(master_cv_path.strip())
        return RedirectResponse(url="/candidate", status_code=303)

    @app.post("/candidate/preferences")
    def update_preferences(
        languages: str = Form(""),
        locations: str = Form(""),
        gap_tolerance: str = Form("unset"),
    ) -> RedirectResponse:
        app.state.assistant.update_preferences(
            Preferences(
                languages=_parse_languages(languages),
                locations=_parse_locations(locations),
                gap_tolerance=_parse_gap_tolerance(gap_tolerance),
            )
        )
        return RedirectResponse(url="/candidate", status_code=303)

    return app


def build_default_assistant(db_path: Path | None = None) -> Assistant:
    """Wire CatalogStore and fakeable ports for local development."""
    data_dir = Path.home() / ".job_finding_assistant"
    catalog_path = db_path or data_dir / "catalog.db"
    return Assistant(
        catalog_store=CatalogStore(catalog_path),
        job_board=FakeJobBoardSession(),
        master_cv=DiskMasterCvStore(data_dir / "master_cv_state"),
        llm_judge=FakeLlmJudge(),
        llm_cv_tailor=FakeLlmCvTailor(),
    )


def main() -> None:
    """Start the local server: `job-finding-assistant` or `python -m job_finding_assistant.web.app`."""
    app = create_app(build_default_assistant())
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
