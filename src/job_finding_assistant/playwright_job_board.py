"""Playwright JobBoardSession adapter for User-Attended Login and Crawl.

Selectors follow `.scratch/job-board-dom.md` research for the live board only.
Primary automated tests use FakeJobBoardSession instead.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs, urlparse

from job_finding_assistant.crawl_filters import CrawlFilters
from job_finding_assistant.crawl_pacer import NoOpCrawlPacer
from job_finding_assistant.job_board import AuthLostError, JobListEntry, JobPostingDetail
from job_finding_assistant.ports import CrawlPacer

JOB_BOARD_URL = "https://career.hkust.edu.hk/web/job.php"
JOB_DETAIL_URL = "https://career.hkust.edu.hk/web/job_detail.php"

_FILTER_SELECTS: tuple[tuple[str, str], ...] = (
    ("business_natures", "BN[]"),
    ("job_natures", "JN[]"),
    ("employment_types", "EMT[]"),
    ("working_locations", "WL[]"),
    ("levels_of_qualification", "awards[]"),
    ("employment_modes", "EM[]"),
    ("languages", "L[]"),
)

_JP_RE = re.compile(r"[?&]jp=(\d+)")


class PlaywrightJobBoardSession:
    """Live HKUST Job Board session driven by Playwright (headed by default)."""

    def __init__(
        self,
        *,
        headless: bool = False,
        crawl_pacer: CrawlPacer | None = None,
    ) -> None:
        self._headless = headless
        self._crawl_pacer = crawl_pacer or NoOpCrawlPacer()
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None
        self._page: Any = None

    def open_login(self) -> None:
        """Open a headed browser on the Job Board for User-Attended Login."""
        self._ensure_browser()
        assert self._page is not None
        self._page.goto(JOB_BOARD_URL, wait_until="domcontentloaded")

    def is_authenticated(self) -> bool:
        """True when User-Attended Login left a welcome marker on the Job Board."""
        if self._page is None:
            return False
        try:
            welcome = self._page.locator(".career-user-welcome")
            return bool(welcome.count() > 0)
        except RuntimeError:
            return False

    def discover_job_list(self, filters: CrawlFilters) -> list[JobListEntry]:
        """Apply Crawl Filters, paginate, and return list rows."""
        self._require_page()
        assert self._page is not None
        if not self.is_authenticated():
            raise AuthLostError("Job Board session is not authenticated")
        self._page.goto(JOB_BOARD_URL, wait_until="domcontentloaded")
        self._apply_filters(filters)
        entries: list[JobListEntry] = []
        while True:
            self._page.wait_for_selector("#job-list", state="attached")
            entries.extend(self._read_list_page())
            next_link = self._page.locator("ul.pagination li.next a")
            if next_link.count() == 0:
                break
            self._crawl_pacer.pause_before_next_page()
            next_link.first.click()
            self._page.wait_for_selector("#job-list", state="attached")
        return entries

    def fetch_job_detail(self, job_posting_id: str) -> JobPostingDetail:
        """Open the detail page in a tab, read structured fields, then close it."""
        self._require_page()
        assert self._context is not None
        if not self.is_authenticated():
            raise AuthLostError("Job Board session is not authenticated")
        detail = self._context.new_page()
        try:
            detail.goto(
                f"{JOB_DETAIL_URL}?jp={job_posting_id}",
                wait_until="domcontentloaded",
            )
            if detail.locator(".career-content").count() == 0:
                raise AuthLostError("Job Board session lost during detail fetch")
            return _read_detail_page(detail, job_posting_id)
        finally:
            detail.close()

    def close(self) -> None:
        """Release browser resources."""
        if self._browser is not None:
            self._browser.close()
        if self._playwright is not None:
            self._playwright.stop()
        self._browser = None
        self._playwright = None
        self._context = None
        self._page = None

    def _ensure_browser(self) -> None:
        if self._page is not None:
            return
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:  # pragma: no cover - optional runtime dep
            raise RuntimeError(
                "Playwright is required for live Job Board access. "
                "Install with: pip install playwright && playwright install chromium"
            ) from exc
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=self._headless)
        self._context = self._browser.new_context()
        self._page = self._context.new_page()

    def _require_page(self) -> None:
        if self._page is None:
            raise AuthLostError("Job Board browser is not open; start User-Attended Login first")

    def _apply_filters(self, filters: CrawlFilters) -> None:
        assert self._page is not None
        panel = self._page.locator("#search-panel")
        if panel.count() and not panel.first.is_visible():
            toggle = self._page.locator("#showSearchPanel")
            if toggle.count():
                toggle.first.click()
        for attr, select_name in _FILTER_SELECTS:
            values = getattr(filters, attr)
            _set_multi_select(self._page, select_name, values)
        self._page.locator("#TEC").set_checked(filters.talent_wise_employment_charter)
        self._page.locator("#AJOB").set_checked(filters.active_job)
        self._page.locator("#NCHI").set_checked(filters.non_chinese_speaking_students)
        self._page.locator(".search-option button.btn-default[type='submit']").filter(
            has_text="Search"
        ).click()
        self._page.wait_for_selector("#job-list", state="attached")

    def _read_list_page(self) -> list[JobListEntry]:
        assert self._page is not None
        rows = self._page.locator("#job-list tr.job-item")
        entries: list[JobListEntry] = []
        for index in range(rows.count()):
            row = rows.nth(index)
            link = row.locator("a.job-post").first
            href = link.get_attribute("href") or ""
            job_id = _job_id_from_href(href)
            if job_id is None:
                continue
            cells = row.locator("td.detail-text.large-view")
            employer = _cell_text(cells, 0)
            title = _cell_text(cells, 1).split("\n")[0].strip()
            posting_date = _optional_date(_cell_text(cells, 2))
            deadline = _optional_date(_cell_text(cells, 3))
            entries.append(
                JobListEntry(
                    id=job_id,
                    title=title or str(link.inner_text()).strip(),
                    employer=employer,
                    posting_date=posting_date,
                    application_deadline=deadline,
                )
            )
        return entries


def _set_multi_select(page: Any, name: str, values: tuple[str, ...]) -> None:
    select = page.locator(f'select[name="{name}"]')
    if select.count() == 0:
        return
    if values:
        select.select_option(list(values))
        return
    select.evaluate(
        """(el) => {
            Array.from(el.options).forEach((option) => { option.selected = false; });
            el.dispatchEvent(new Event('change', { bubbles: true }));
        }"""
    )


def _job_id_from_href(href: str) -> str | None:
    match = _JP_RE.search(href)
    if match:
        return match.group(1)
    query = parse_qs(urlparse(href).query)
    values = query.get("jp")
    if values:
        return values[0]
    return None


def _cell_text(cells: Any, index: int) -> str:
    if cells.count() <= index:
        return ""
    return str(cells.nth(index).inner_text()).strip()


def _optional_date(raw: str) -> str | None:
    text = raw.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return text
    return None


def _read_detail_page(page: Any, job_posting_id: str) -> JobPostingDetail:
    fields: dict[str, str] = {}
    headers = page.locator(".career-content .detail-header")
    for index in range(headers.count()):
        header = headers.nth(index)
        label = str(header.inner_text()).strip().rstrip(":")
        if not label:
            continue
        value_locator = header.locator(
            "xpath=following-sibling::*[contains(@class,'detail-text')][1]"
        )
        if value_locator.count() == 0:
            parent = header.locator("xpath=..")
            value_locator = parent.locator(".detail-text").first
        text = str(value_locator.inner_text()).strip() if value_locator.count() else ""
        if label and text:
            fields[label] = text

    title = fields.get("Job Title") or fields.get("Position Offered") or ""
    if not title:
        # List-style summary strip: Job Title / Job Nature combined cell.
        for key, value in fields.items():
            if "Job Title" in key:
                title = value.split("\n")[0].strip()
                break
    employer = fields.get("Company / Organization") or fields.get("Company") or ""
    posting_date = _optional_date(fields.get("Posting Date", ""))
    deadline = _optional_date(fields.get("Application Deadline", ""))
    return JobPostingDetail(
        id=job_posting_id,
        title=title,
        employer=employer,
        posting_date=posting_date,
        application_deadline=deadline,
        fields=fields,
    )
