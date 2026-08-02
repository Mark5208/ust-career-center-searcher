"""CrawlPacer — random human-like delays between Job Board actions."""

from __future__ import annotations

import random
import time

DETAIL_PAUSE_RANGE = (1.0, 3.0)
NEXT_PAGE_PAUSE_RANGE = (0.5, 1.5)


class NoOpCrawlPacer:
    """No delays — default for tests that do not assert pacing."""

    def pause_before_detail(self) -> None:
        return None

    def pause_before_next_page(self) -> None:
        return None


class RandomCrawlPacer:
    """Sleep a random duration in a fixed range before board actions."""

    def pause_before_detail(self) -> None:
        lo, hi = DETAIL_PAUSE_RANGE
        time.sleep(random.uniform(lo, hi))

    def pause_before_next_page(self) -> None:
        lo, hi = NEXT_PAGE_PAUSE_RANGE
        time.sleep(random.uniform(lo, hi))
