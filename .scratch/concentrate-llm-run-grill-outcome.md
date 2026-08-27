# Grill outcome — Concentrate LLM Run

**Date:** 2026-08-22  
**Promoted from:** `/improve-codebase-architecture` review `architecture-review-20260822-092200.html` (top recommendation: Concentrate LLM Run)  
**Kind:** Architecture deepen only — not a product/v2 theme  
**Glossary:** No new `CONTEXT.md` terms (**LLM Run** / **Bulk Prepare** / **Pending** already defined; ADR-0015 product rules unchanged, including the two `k` meanings)

| # | Decision | Answer |
|---|----------|--------|
| 1 | Kind of work | Architecture deepen only; ADR-0015 / parallel-judging product rules stay (one-in-flight, cooperative Stop, fingerprint abort, until-empty Judging, sequential Bulk Prepare, concurrency env, opportunistic one-Pending is not an LLM Run) |
| 2 | Scope vs siblings | This deepen only. Delete public `bulk_prepare` wait-loop; retarget bulk tests at start + poll. Park leftover page-load method collapse (`list`/`get`/`can_prepare`). Park extracting `_assess_job_posting`. Park opportunistic `rejudge_pending_assessments` / `_rejudge_skip_ids` |
| 3 | Two `k` meanings | Keep: Judging `k` = fully finished only; Preparing `k` = includes the in-flight posting. Concentrate publishing in one implementation. Do not reopen parallel-judging Q7/Q15. Do not collapse `LlmRunStatus` leader fields vs `in_flight` in this sitting |
| 4 | Where it lives | New internal `llm_run.py`. Public start/stop/status stay on `Assistant`. Do not split Assistant’s external seam. Do not expand `catalog_assess.py` to own Bulk Prepare. Do not privatize engines in place on `Assistant` |
| 5 | Module vs Assistant | Orchestration-only module: thread, lock, Stop, one-in-flight, run state, both engine loops, `k of n` publish, finish messages. Collaborators via a small protocol/callbacks (`assess`, `prepare`, list Pending, refresh fingerprints, posting identity, clear assessments). `llm_run.py` does **not** import `Assistant`. Assistant wrappers keep refresh, Bulk Prepare eligibility/confirm (`BulkPrepareNeedsConfirm`), and empty-selection short-circuit. `catalog_assess.py` stays `PendingClaimQueue` + concurrency knob; the catalog-assess **engine** moves to `llm_run.py` and imports the queue. `_assess_job_posting` and `_save_assessment_lock` stay on `Assistant` |
| 6 | Public types | Define `LlmRunStatus`, `LlmRunPosting`, `LlmRunAlreadyInFlight` in `llm_run.py`; re-export from `assistant` so UI/tests keep importing from `assistant` |
| 7 | Test surface | LLM Run behavior tests stay on `Assistant` start/stop/status (`test_assistant_llm_run.py`; retarget `test_assistant_bulk.py` to start + poll `bulk_prepare_result`). Drop `bulk_prepare` from `SupportsAssistantUi` and the UI Fake. Keep `test_catalog_assess_queue.py`. No new `llm_run.py` tests with a fake ports object. No `Assistant.wait_for_llm_run` helper |
| 8 | Docs | Sync `memory-bank/@architecture.md` (package layout: `llm_run.py`; drop public `bulk_prepare`). Soft-edit `@design-document.md` to drop `bulk_prepare` as a shipped entry point. No ADR-0015 edit. No `CONTEXT.md` change |
| 9 | Build path | Single-session `/implement` (TDD at the `Assistant` LLM Run seam, then move implementation behind it). No `/to-tickets` |
| 10 | Circular types | Define `BulkPrepareResult` in `llm_run.py` next to `LlmRunStatus` (re-export from `assistant`). Leave `PrepareFailedError` on `Assistant`. Prepare callback returns prepared / failed / unavailable — `llm_run.py` never imports or catches `PrepareFailedError`. Confirm types stay on `Assistant` |

## Out of scope

- Reopening ADR-0015 product rules (unify `k`, parallel Bulk Prepare, fold opportunistic rejudge into an LLM Run, hard-cancel)
- Collapsing leftover Assistant page-load methods (`list_assessment_summaries` / `get_match_assessment` / `can_prepare` / `get_preparation_packet`)
- Extracting `_assess_job_posting` into a judging module (review candidate “Deepen Pending → Match Assessment”)
- Merging `_rejudge_skip_ids` with `PendingClaimQueue`
- Splitting LLM Run off `Assistant`’s external seam
- Expanding `catalog_assess.py` to own both phases
- New `CONTEXT.md` term for the code module
- New ADR / ADR-0015 rewrite
- Direct tests of `llm_run.py` past the `Assistant` seam
- Collapsing `LlmRunStatus` so callers cannot see both leader fields and `in_flight`

## Build path

Single-session `/implement` (TDD at `Assistant` start/stop/status): delete `bulk_prepare` → retarget Protocol/Fake/bulk tests → extract orchestration into `llm_run.py` with callbacks → re-export types → memory-bank sync. No `/to-tickets` breakdown.
