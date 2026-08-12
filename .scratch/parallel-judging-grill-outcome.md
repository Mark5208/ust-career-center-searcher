# Grill outcome — parallel judging

**Date:** 2026-08-12
**Promoted from:** [#17](https://github.com/Mark5208/ust-career-center-searcher/issues/17) (parking lot; not the parent), parked there as "parallel judging (future; sequential LLM Run shipped/specified in #23)"
**Parent issue:** [#25](https://github.com/Mark5208/ust-career-center-searcher/issues/25) (`ready-for-agent`)
**Kind:** LLM runtime — concurrency for catalog assess only, not Bulk Prepare

| # | Decision | Answer |
|---|----------|--------|
| 1 | Motivation | Backlog throughput — many Pending postings, judge several at once (not per-posting latency) |
| 2 | Scope | Catalog assess (**Judging**) only. Bulk Prepare (**Preparing**) stays sequential — fully untouched, including its status-display mechanics |
| 3 | Concurrency control | New env var `JOB_FINDING_ASSISTANT_CATALOG_ASSESS_MAX_CONCURRENCY`, consistent with ADR-0015's env-only philosophy |
| 4 | Default | 3 when unset |
| 5 | Bounds | Clamp 1–10; unset/invalid/non-numeric silently falls back to 3 (no error surfaced); concurrency=1 gives identical success/failure/early-stop/deferral outcomes to today's sequential engine |
| 6 | Status grain | `LlmRunStatus` reports the **list** of in-flight Job Posting identities (up to N) during catalog assess; Bulk Prepare's status fields stay a single identity, unchanged |
| 7 | k of n | For catalog assess, `k` = postings fully finished (saved/skipped/failed), never in-flight; `n` keeps today's rolling-total meaning (can grow if Crawl adds Pending). Bulk Prepare's `k` keeps counting the in-flight posting as today (unaffected) |
| 8 | Stop | Cooperative for every in-flight call, generalized from today's single-call cooperative Stop; no hard-cancel; worst-case wait bounded by the single 30s HTTP timeout, not multiplied by worker count |
| 9 | LLM Unavailable / rate limits | Unchanged — any provider HTTP error, including 429, still maps to LLM Unavailable and still early-stops the whole run (in-flight calls finish cooperatively first); no new backoff/retry machinery |
| 10 | Queue model | One shared thread-safe Pending queue; idle claimants atomically pop the next non-skipped id; tops up from the DB so Crawl-added Pending still joins mid-run; HOL-avoidance retry once the shared queue has drained, generalizing today's single-cursor `_rejudge_skip_ids` |
| 11 | SQLite writes | `CatalogStore.save_match_assessment` calls serialized behind one new dedicated app-level lock (distinct from `_llm_run_lock`); reads unaffected |
| 12 | Glossary | No new `CONTEXT.md` term — amend the existing **LLM Run** entry's prose only; keep `k`-counting mechanics out of the glossary (implementation detail lives in the ADR); `_Avoid_` line unchanged, no "worker" |
| 13 | Doc strategy | Amend [ADR-0015](../docs/adr/0015-llm-runtime-for-v1.md) in place — third revision of the same LLM Run mechanics ADR (after budget-of-5, then until-empty) |
| 14 | Tracker | Promote now — new `ready-for-agent` parent issue from #17, mirroring #18/#23's shape |
| 15 | *(amended)* k-semantics scope | Cross-referencing the draft against `_set_llm_run_current` in `assistant.py` showed Bulk Prepare's `current_index` already counts the in-flight posting today, for both phases. A universal "k = finished-only" redefinition would silently change Bulk Prepare's display and contradict "unaffected." Resolved: finished-only `k` is scoped to catalog assess only |
| 16 | *(amended)* Env var naming | Initially drafted as `JOB_FINDING_ASSISTANT_LLM_MAX_CONCURRENCY`, matching the `_LLM_API_KEY`/`_LLM_BASE_URL`/`_LLM_MODEL` family — but those apply to every LLM port, while this var only governs catalog-assess concurrency. Renamed to `JOB_FINDING_ASSISTANT_CATALOG_ASSESS_MAX_CONCURRENCY` for scope accuracy |

## Out of scope (recorded, not silently dropped)

- Bulk Prepare concurrency
- Redefining Bulk Prepare's `k` / status-display semantics
- Parallelizing the 3 signal calls (Hard Constraint / Preference / Relevance) within one posting
- Multi-provider / key UI
- Spend meter
- Adaptive / backoff rate-limit handling
- Hard-cancel of the in-flight provider HTTP call
- WAL journal mode (plain app-level lock preferred for now)

**Docs:** `CONTEXT.md` (**LLM Run** prose amended); ADR-0015 amended (third revision).
