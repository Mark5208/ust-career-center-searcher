"""Concurrency knob and shared Pending claim queue for catalog assess LLM Runs.

Catalog assess (Judging) may judge several Job Postings at once; Bulk Prepare stays
sequential and does not use anything here (ADR-0015).
"""

from __future__ import annotations

import os
import threading
from collections import deque
from collections.abc import Callable, Mapping
from dataclasses import dataclass

__all__ = [
    "DEFAULT_MAX_CONCURRENCY",
    "ENV_MAX_CONCURRENCY",
    "MAX_CONCURRENCY",
    "MIN_CONCURRENCY",
    "ClaimProgress",
    "PendingClaimQueue",
    "load_max_concurrency",
]


ENV_MAX_CONCURRENCY = "JOB_FINDING_ASSISTANT_CATALOG_ASSESS_MAX_CONCURRENCY"
DEFAULT_MAX_CONCURRENCY = 3
MIN_CONCURRENCY = 1
MAX_CONCURRENCY = 10


def load_max_concurrency(environ: Mapping[str, str] | None = None) -> int:
    """Return how many judge calls one catalog assess LLM Run may run at once.

    The knob is a manual dial, not a validated setting: unset or non-numeric values
    fall back to the default and numeric values are clamped, both silently (ADR-0015).
    """
    env = environ if environ is not None else os.environ
    raw = env.get(ENV_MAX_CONCURRENCY, "").strip()
    try:
        requested = int(raw)
    except ValueError:
        return DEFAULT_MAX_CONCURRENCY
    return max(MIN_CONCURRENCY, min(MAX_CONCURRENCY, requested))


@dataclass(frozen=True)
class ClaimProgress:
    """Point-in-time view of one run's queue for the LLM Run status poll.

    ``revision`` increases on every queue change so a status publisher that lost a
    race cannot overwrite a fresher view.
    """

    revision: int
    finished: int
    in_flight: tuple[str, ...]


class PendingClaimQueue:
    """The shared Pending work queue behind one catalog assess LLM Run.

    Idle claimants atomically pop the next claimable Job Posting id. The queue tops
    up from the catalog whenever it runs dry, so a posting added by Crawl mid-run
    still joins the same run. A skipped or failed id is deferred instead of retried
    immediately, so it cannot starve the rest; deferred ids come back for one retry
    pass once the queue has fully drained — nothing in ready or in flight — and that
    pass happens at most once, so a run where nothing can succeed ends rather than
    spinning on ids that keep failing.
    """

    def __init__(self, list_pending: Callable[[], list[str]]) -> None:
        self._list_pending = list_pending
        self._lock = threading.Lock()
        self._ready: deque[str] = deque()
        self._deferred: set[str] = set()
        # Claim order matters for the status poll, so this is an ordered set.
        self._in_flight: dict[str, None] = {}
        self._finished = 0
        self._revision = 0
        self._retry_available = True
        self._halted = False

    def claim(self) -> str | None:
        """Take the next claimable id, or None when this run has no more work."""
        with self._lock:
            if self._halted:
                return None
            job_id = self._next_ready()
            if job_id is None:
                return None
            self._in_flight[job_id] = None
            self._revision += 1
            return job_id

    def release(self, job_id: str, *, deferred: bool) -> None:
        """Record one finished attempt (saved, skipped, or failed)."""
        with self._lock:
            self._in_flight.pop(job_id, None)
            self._finished += 1
            self._revision += 1
            if deferred:
                self._deferred.add(job_id)
            else:
                self._deferred.discard(job_id)

    def halt(self) -> None:
        """Stop handing out claims (Stop, LLM Unavailable, candidate-file change)."""
        with self._lock:
            self._halted = True

    def progress(self) -> ClaimProgress:
        """Return finished attempts and the ids in flight, in claim order."""
        with self._lock:
            return ClaimProgress(
                revision=self._revision,
                finished=self._finished,
                in_flight=tuple(self._in_flight),
            )

    @property
    def finished(self) -> int:
        """Number of attempts that fully finished (saved, skipped, or failed)."""
        with self._lock:
            return self._finished

    def _next_ready(self) -> str | None:
        if not self._ready:
            self._top_up()
        if not self._ready and not self._in_flight and self._deferred and self._retry_available:
            self._retry_available = False
            self._deferred.clear()
            self._top_up()
        return self._ready.popleft() if self._ready else None

    def _top_up(self) -> None:
        for job_id in self._list_pending():
            if job_id in self._deferred or job_id in self._in_flight:
                continue
            self._ready.append(job_id)
