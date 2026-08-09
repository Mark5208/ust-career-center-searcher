"""Playwright sync API must survive FastAPI's threadpool (cross-thread calls)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from job_finding_assistant.playwright_job_board import PlaywrightJobBoardSession


@pytest.fixture
def playwright_session() -> PlaywrightJobBoardSession:
    session = PlaywrightJobBoardSession(headless=True)
    try:
        yield session
    finally:
        session.close()


def test_is_authenticated_safe_when_called_from_another_thread(
    playwright_session: PlaywrightJobBoardSession,
) -> None:
    """GET /crawl after Crawl runs on a different worker thread (Starlette threadpool)."""
    # Start Playwright on the dedicated worker without needing the live Job Board.
    playwright_session._call(playwright_session._ensure_browser)

    with ThreadPoolExecutor(max_workers=1) as pool:
        authenticated = pool.submit(playwright_session.is_authenticated).result(timeout=30)

    assert authenticated is False or authenticated is True
