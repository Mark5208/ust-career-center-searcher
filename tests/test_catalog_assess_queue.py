"""Claim rules behind a catalog assess LLM Run (pure queue, no judge)."""

from __future__ import annotations

from job_finding_assistant.catalog_assess import PendingClaimQueue


def _queue(pending: list[str]) -> tuple[PendingClaimQueue, list[str]]:
    """Return a queue over a Pending list the test can still change."""
    return PendingClaimQueue(lambda: list(pending)), pending


def test_claimants_take_different_ids_in_catalog_order() -> None:
    queue, _ = _queue(["86534", "86535"])

    assert queue.claim() == "86534"
    assert queue.claim() == "86535"
    assert queue.claim() is None


def test_deferred_head_does_not_starve_the_rest() -> None:
    queue, _ = _queue(["86534", "86535", "86536"])

    head = queue.claim()
    assert head == "86534"
    queue.release(head, deferred=True)

    # The failed head steps aside instead of being handed out again.
    assert queue.claim() == "86535"
    assert queue.claim() == "86536"


def test_deferred_ids_get_one_retry_pass_once_the_queue_drains() -> None:
    queue, pending = _queue(["86534", "86535"])
    for _ in range(2):
        job_id = queue.claim()
        assert job_id is not None
        queue.release(job_id, deferred=True)

    # Drained with both still Pending: one retry pass, then the run ends.
    retried = [queue.claim(), queue.claim()]
    assert retried == ["86534", "86535"]
    for job_id in retried:
        assert job_id is not None
        queue.release(job_id, deferred=True)

    assert queue.claim() is None
    assert pending == ["86534", "86535"]


def test_retry_pass_waits_until_nothing_is_in_flight() -> None:
    queue, pending = _queue(["86534", "86535"])
    deferred_head = queue.claim()
    assert deferred_head is not None
    still_running = queue.claim()
    assert still_running is not None
    queue.release(deferred_head, deferred=True)

    # A claimant idling while another call is still in flight waits it out.
    assert queue.claim() is None

    pending.remove(still_running)  # saved: no longer Pending in the catalog
    queue.release(still_running, deferred=False)

    assert queue.claim() == deferred_head


def test_queue_tops_up_with_postings_added_mid_run() -> None:
    queue, pending = _queue(["86534"])
    first = queue.claim()
    assert first is not None
    queue.release(first, deferred=False)

    pending.remove("86534")
    pending.append("86599")

    assert queue.claim() == "86599"


def test_halt_stops_handing_out_further_claims() -> None:
    queue, _ = _queue(["86534", "86535"])

    queue.halt()

    assert queue.claim() is None


def test_progress_reports_finished_count_and_in_flight_claim_order() -> None:
    queue, _ = _queue(["86534", "86535", "86536"])
    first = queue.claim()
    assert first is not None
    second = queue.claim()
    assert second is not None

    in_progress = queue.progress()
    assert in_progress.finished == 0
    assert in_progress.in_flight == ("86534", "86535")

    queue.release(first, deferred=False)
    after_one = queue.progress()

    assert after_one.finished == 1
    assert after_one.in_flight == ("86535",)
    assert after_one.revision > in_progress.revision
