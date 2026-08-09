"""FastAPI bootstrap: Jinja pages call Assistant only."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Protocol

import uvicorn
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from job_finding_assistant.assistant import (
    AssessmentSummary,
    Assistant,
    CrawlFilters,
    CrawlOutcome,
    DeleteNeedsConfirm,
    PreparationPacketView,
    PrepareBlockedError,
    PrepareFailedError,
    PrepareNeedsConfirm,
)
from job_finding_assistant.candidate_snapshot import CandidateSnapshot
from job_finding_assistant.catalog_store import CatalogStore
from job_finding_assistant.constraint_files_store import DiskConstraintFilesStore
from job_finding_assistant.llm_runtime import build_llm_ports, load_llm_runtime_config
from job_finding_assistant.match_assessment import MatchAssessment
from job_finding_assistant.master_cv_store import DiskMasterCvStore
from job_finding_assistant.preparation_packet import PreparationPacket

_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


class SupportsAssistantUi(Protocol):
    def list_assessment_summaries(
        self,
        *,
        include_closed: bool = False,
        include_passed_deadlines: bool = False,
    ) -> list[AssessmentSummary]:
        """Return Assessment Summaries for the catalog page."""

    def can_prepare(self, job_posting_id: str) -> bool:
        """Return whether Prepare is available for the Job Posting."""

    def get_match_assessment(self, job_posting_id: str) -> MatchAssessment | None:
        """Return Match Assessment detail, or None when Pending."""

    def prepare(
        self,
        job_posting_id: str,
        *,
        confirm_hard_constraint_fail: bool = False,
        confirm_overwrite: bool = False,
    ) -> PreparationPacket:
        """Build or overwrite the Preparation Packet."""

    def get_preparation_packet(self, job_posting_id: str) -> PreparationPacketView | None:
        """Return packet view with current Match Assessment."""

    def get_tailored_yaml(self, job_posting_id: str) -> str | None:
        """Return Tailored YAML for download."""

    def get_tailored_pdf(self, job_posting_id: str) -> bytes | None:
        """Return Tailored PDF for download."""

    def delete(self, job_posting_id: str, *, confirm: bool = False) -> None:
        """Hard-remove Job Posting, Match Assessment, and Preparation Packet."""

    def rejudge_pending_assessments(self) -> None:
        """Opportunistically judge Pending Match Assessments."""

    def get_master_cv_path(self) -> str | None:
        """Return the configured Master CV path."""

    def set_master_cv_path(self, path: str) -> None:
        """Set the Master CV path without overwriting the file."""

    def get_candidate_snapshot(self) -> CandidateSnapshot | None:
        """Return the Candidate Snapshot."""

    def get_hard_constraints_path(self) -> str | None:
        """Return the Hard Constraints file path."""

    def set_hard_constraints_path(self, path: str) -> None:
        """Set the Hard Constraints file path."""

    def clear_hard_constraints_path(self) -> None:
        """Clear the Hard Constraints path."""

    def get_preferences_path(self) -> str | None:
        """Return the Preferences file path."""

    def set_preferences_path(self, path: str) -> None:
        """Set the Preferences file path."""

    def clear_preferences_path(self) -> None:
        """Clear the Preferences path."""

    def get_candidate_file_errors(self) -> list[str]:
        """Return path/read errors for candidate files."""

    def get_llm_unavailable_reason(self) -> str | None:
        """Short non-secret LLM Unavailable reason, if any."""

    def get_crawl_filters(self) -> CrawlFilters:
        """Return Crawl Filters."""

    def update_crawl_filters(self, filters: CrawlFilters) -> None:
        """Persist Crawl Filters."""

    def start_user_attended_login(self) -> None:
        """Open the Job Board for User-Attended Login."""

    def can_start_crawl(self) -> bool:
        """Return whether a Crawl may start."""

    def run_crawl(self, *, full_refresh: bool = False) -> CrawlOutcome:
        """Run Incremental Crawl or Full Refresh."""


def _parse_lines(raw: str) -> tuple[str, ...]:
    return tuple(line.strip() for line in raw.splitlines() if line.strip())


def _parse_optional_date(raw: str) -> date | None:
    text = raw.strip()
    if not text:
        return None
    return date.fromisoformat(text)


def create_app(assistant: SupportsAssistantUi) -> FastAPI:
    """Build the local UI app wired to a single Assistant (or test double)."""
    app = FastAPI(title="Job Finding Assistant")
    app.state.assistant = assistant
    app.state.last_crawl_outcome = None
    app.state.prepare_error = None

    @app.get("/", response_class=HTMLResponse)
    def assessment_summaries_page(
        request: Request,
        include_closed: str = "0",
        include_passed_deadlines: str = "0",
    ) -> HTMLResponse:
        show_closed = include_closed == "1"
        show_passed = include_passed_deadlines == "1"
        current = request.app.state.assistant
        current.rejudge_pending_assessments()
        summaries = current.list_assessment_summaries(
            include_closed=show_closed,
            include_passed_deadlines=show_passed,
        )
        rows = [
            {
                "summary": summary,
                "can_prepare": current.can_prepare(summary.job_posting_id),
            }
            for summary in summaries
        ]
        return _TEMPLATES.TemplateResponse(
            request,
            "assessment_summaries.html",
            {
                "rows": rows,
                "include_closed": show_closed,
                "include_passed_deadlines": show_passed,
                "prepare_error": request.app.state.prepare_error,
                "llm_unavailable_reason": current.get_llm_unavailable_reason(),
            },
        )

    @app.get("/jobs/{job_posting_id}", response_class=HTMLResponse)
    def match_assessment_detail_page(
        request: Request, job_posting_id: str
    ) -> Response:
        current = request.app.state.assistant
        summary: AssessmentSummary | None = None
        for row in current.list_assessment_summaries(
            include_closed=True, include_passed_deadlines=True
        ):
            if row.job_posting_id == job_posting_id:
                summary = row
                break
        if summary is None:
            return RedirectResponse(url="/", status_code=303)
        return _TEMPLATES.TemplateResponse(
            request,
            "match_assessment_detail.html",
            {
                "summary": summary,
                "match_assessment": current.get_match_assessment(job_posting_id),
                "can_prepare": current.can_prepare(job_posting_id),
                "llm_unavailable_reason": current.get_llm_unavailable_reason(),
            },
        )

    @app.post("/jobs/{job_posting_id}/prepare")
    def prepare_job(
        request: Request,
        job_posting_id: str,
        confirm_hard_constraint_fail: str = Form("0"),
        confirm_overwrite: str = Form("0"),
    ) -> Response:
        current = request.app.state.assistant
        request.app.state.prepare_error = None
        try:
            current.prepare(
                job_posting_id,
                confirm_hard_constraint_fail=confirm_hard_constraint_fail == "1",
                confirm_overwrite=confirm_overwrite == "1",
            )
        except PrepareBlockedError as exc:
            request.app.state.prepare_error = str(exc)
            return RedirectResponse(url="/", status_code=303)
        except PrepareNeedsConfirm as exc:
            confirm_hc = confirm_hard_constraint_fail == "1"
            confirm_ow = confirm_overwrite == "1"
            if exc.kind == "hard_constraint_fail":
                confirm_hc = True
            if exc.kind == "overwrite":
                confirm_ow = True
            return _TEMPLATES.TemplateResponse(
                request,
                "prepare_confirm.html",
                {
                    "job_posting_id": job_posting_id,
                    "message": exc.reason,
                    "confirm_hard_constraint_fail": confirm_hc,
                    "confirm_overwrite": confirm_ow,
                },
                status_code=200,
            )
        except PrepareFailedError as exc:
            request.app.state.prepare_error = str(exc)
            return RedirectResponse(url="/", status_code=303)
        return RedirectResponse(url=f"/jobs/{job_posting_id}/packet", status_code=303)

    @app.post("/jobs/{job_posting_id}/delete")
    def delete_job(
        request: Request,
        job_posting_id: str,
        confirm: str = Form("0"),
    ) -> Response:
        current = request.app.state.assistant
        try:
            current.delete(job_posting_id, confirm=confirm == "1")
        except DeleteNeedsConfirm as exc:
            return _TEMPLATES.TemplateResponse(
                request,
                "delete_confirm.html",
                {
                    "job_posting_id": job_posting_id,
                    "message": exc.reason,
                },
                status_code=200,
            )
        return RedirectResponse(url="/", status_code=303)

    @app.get("/jobs/{job_posting_id}/packet", response_class=HTMLResponse)
    def packet_page(request: Request, job_posting_id: str) -> Response:
        current = request.app.state.assistant
        view = current.get_preparation_packet(job_posting_id)
        if view is None:
            return RedirectResponse(url="/", status_code=303)
        posting_title = job_posting_id
        posting_employer = ""
        for summary in current.list_assessment_summaries(
            include_closed=True, include_passed_deadlines=True
        ):
            if summary.job_posting_id == job_posting_id:
                posting_title = summary.title
                posting_employer = summary.employer
                break
        return _TEMPLATES.TemplateResponse(
            request,
            "preparation_packet.html",
            {
                "job_posting_id": job_posting_id,
                "title": posting_title,
                "employer": posting_employer,
                "packet": view.packet,
                "match_assessment": view.match_assessment,
            },
        )

    @app.get("/jobs/{job_posting_id}/packet/yaml")
    def download_yaml(job_posting_id: str) -> Response:
        text = app.state.assistant.get_tailored_yaml(job_posting_id)
        if text is None:
            return RedirectResponse(url="/", status_code=303)
        return Response(
            content=text,
            media_type="application/x-yaml",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="tailored-{job_posting_id}.yaml"'
                )
            },
        )

    @app.get("/jobs/{job_posting_id}/packet/pdf")
    def download_pdf(job_posting_id: str) -> Response:
        pdf = app.state.assistant.get_tailored_pdf(job_posting_id)
        if pdf is None:
            return RedirectResponse(url="/", status_code=303)
        return Response(
            content=pdf,
            media_type="application/pdf",
            headers={
                "Content-Disposition": (
                    f'attachment; filename="tailored-{job_posting_id}.pdf"'
                )
            },
        )

    @app.get("/candidate", response_class=HTMLResponse)
    def candidate_page(request: Request) -> HTMLResponse:
        current = request.app.state.assistant
        return _TEMPLATES.TemplateResponse(
            request,
            "candidate.html",
            {
                "master_cv_path": current.get_master_cv_path() or "",
                "snapshot": current.get_candidate_snapshot(),
                "hard_constraints_path": current.get_hard_constraints_path() or "",
                "preferences_path": current.get_preferences_path() or "",
                "candidate_file_errors": current.get_candidate_file_errors(),
            },
        )

    @app.post("/candidate/master-cv")
    def set_master_cv_path(master_cv_path: str = Form(...)) -> RedirectResponse:
        app.state.assistant.set_master_cv_path(master_cv_path.strip())
        return RedirectResponse(url="/candidate", status_code=303)

    @app.post("/candidate/hard-constraints")
    def set_hard_constraints_path(
        hard_constraints_path: str = Form(""),
    ) -> RedirectResponse:
        text = hard_constraints_path.strip()
        if text:
            app.state.assistant.set_hard_constraints_path(text)
        return RedirectResponse(url="/candidate", status_code=303)

    @app.post("/candidate/hard-constraints/clear")
    def clear_hard_constraints_path() -> RedirectResponse:
        app.state.assistant.clear_hard_constraints_path()
        return RedirectResponse(url="/candidate", status_code=303)

    @app.post("/candidate/preferences")
    def set_preferences_path(preferences_path: str = Form("")) -> RedirectResponse:
        text = preferences_path.strip()
        if text:
            app.state.assistant.set_preferences_path(text)
        return RedirectResponse(url="/candidate", status_code=303)

    @app.post("/candidate/preferences/clear")
    def clear_preferences_path() -> RedirectResponse:
        app.state.assistant.clear_preferences_path()
        return RedirectResponse(url="/candidate", status_code=303)

    @app.get("/crawl", response_class=HTMLResponse)
    def crawl_page(request: Request) -> HTMLResponse:
        current = request.app.state.assistant
        filters = current.get_crawl_filters()
        return _TEMPLATES.TemplateResponse(
            request,
            "crawl.html",
            {
                "can_start_crawl": current.can_start_crawl(),
                "business_natures": "\n".join(filters.business_natures),
                "job_natures": "\n".join(filters.job_natures),
                "employment_types": "\n".join(filters.employment_types),
                "working_locations": "\n".join(filters.working_locations),
                "levels_of_qualification": "\n".join(filters.levels_of_qualification),
                "employment_modes": "\n".join(filters.employment_modes),
                "languages": "\n".join(filters.languages),
                "talent_wise_employment_charter": filters.talent_wise_employment_charter,
                "active_job": filters.active_job,
                "non_chinese_speaking_students": filters.non_chinese_speaking_students,
                "deadline_hardline": (
                    filters.deadline_hardline.isoformat()
                    if filters.deadline_hardline is not None
                    else ""
                ),
                "last_outcome": request.app.state.last_crawl_outcome,
            },
        )

    @app.post("/crawl/login")
    def crawl_login() -> RedirectResponse:
        app.state.assistant.start_user_attended_login()
        return RedirectResponse(url="/crawl", status_code=303)

    @app.post("/crawl/filters")
    def crawl_filters(
        business_natures: str = Form(""),
        job_natures: str = Form(""),
        employment_types: str = Form(""),
        working_locations: str = Form(""),
        levels_of_qualification: str = Form(""),
        employment_modes: str = Form(""),
        languages: str = Form(""),
        talent_wise_employment_charter: str | None = Form(None),
        active_job: str | None = Form(None),
        non_chinese_speaking_students: str | None = Form(None),
        deadline_hardline: str = Form(""),
    ) -> RedirectResponse:
        app.state.assistant.update_crawl_filters(
            CrawlFilters(
                business_natures=_parse_lines(business_natures),
                job_natures=_parse_lines(job_natures),
                employment_types=_parse_lines(employment_types),
                working_locations=_parse_lines(working_locations),
                levels_of_qualification=_parse_lines(levels_of_qualification),
                employment_modes=_parse_lines(employment_modes),
                languages=_parse_lines(languages),
                talent_wise_employment_charter=talent_wise_employment_charter == "1",
                active_job=active_job == "1",
                non_chinese_speaking_students=non_chinese_speaking_students == "1",
                deadline_hardline=_parse_optional_date(deadline_hardline),
            )
        )
        return RedirectResponse(url="/crawl", status_code=303)

    @app.post("/crawl/run")
    def crawl_run(full_refresh: str = Form("0")) -> RedirectResponse:
        outcome = app.state.assistant.run_crawl(full_refresh=full_refresh == "1")
        app.state.last_crawl_outcome = outcome
        return RedirectResponse(url="/crawl", status_code=303)

    return app


def build_default_assistant(db_path: Path | None = None) -> Assistant:
    """Wire CatalogStore and ports for local development (Playwright Job Board)."""
    from job_finding_assistant.crawl_pacer import RandomCrawlPacer
    from job_finding_assistant.playwright_job_board import PlaywrightJobBoardSession

    data_dir = Path.home() / ".job_finding_assistant"
    catalog_path = db_path or data_dir / "catalog.db"
    crawl_pacer = RandomCrawlPacer()
    llm_judge, llm_cv_tailor = build_llm_ports(config=load_llm_runtime_config())
    return Assistant(
        catalog_store=CatalogStore(catalog_path),
        job_board=PlaywrightJobBoardSession(headless=False, crawl_pacer=crawl_pacer),
        master_cv=DiskMasterCvStore(data_dir / "master_cv_state"),
        llm_judge=llm_judge,
        llm_cv_tailor=llm_cv_tailor,
        constraint_files=DiskConstraintFilesStore(data_dir / "constraint_files_state"),
        crawl_pacer=crawl_pacer,
        packet_store_dir=data_dir / "packets",
    )


def main() -> None:
    """Start the local server: `job-finding-assistant` or `python -m job_finding_assistant.web.app`."""
    app = create_app(build_default_assistant())
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    main()
