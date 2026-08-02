"""FastAPI bootstrap: Jinja pages call Assistant only."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from job_finding_assistant.assistant import AssessmentSummary, Assistant
from job_finding_assistant.catalog_store import CatalogStore
from job_finding_assistant.fakes import (
    FakeJobBoardSession,
    FakeLlmCvTailor,
    FakeLlmJudge,
    FakeMasterCvStore,
)

_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


class SupportsListAssessmentSummaries(Protocol):
    def list_assessment_summaries(self) -> list[AssessmentSummary]:
        """Return Assessment Summaries for the catalog page."""


def create_app(assistant: SupportsListAssessmentSummaries) -> FastAPI:
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

    return app


def build_default_assistant(db_path: Path | None = None) -> Assistant:
    """Wire CatalogStore and fakeable ports for local development."""
    catalog_path = db_path or Path.home() / ".job_finding_assistant" / "catalog.db"
    return Assistant(
        catalog_store=CatalogStore(catalog_path),
        job_board=FakeJobBoardSession(),
        master_cv=FakeMasterCvStore(),
        llm_judge=FakeLlmJudge(),
        llm_cv_tailor=FakeLlmCvTailor(),
    )


def main() -> None:
    """Start the local server: `job-finding-assistant` or `python -m job_finding_assistant.web.app`."""
    app = create_app(build_default_assistant())
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
