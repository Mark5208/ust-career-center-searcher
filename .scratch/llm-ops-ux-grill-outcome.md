# Grill outcome — LLM Run activity UX

**Date:** 2026-08-11  
**Promoted from:** [#17](https://github.com/Mark5208/ust-career-center-searcher/issues/17) (parking lot; not the parent)  
**Parent issue:** [#23](https://github.com/Mark5208/ust-career-center-searcher/issues/23) (`ready-for-agent`)  
**Kind:** Product / LLM ops UX — in-flight activity, not spend or key UI

| # | Decision | Answer |
|---|----------|--------|
| 1 | Theme | In-flight activity — not spend, not idle health/settings |
| 2 | Signal | In-flight activity (phase + what) |
| 3 | Flows (this ship) | Catalog Pending assess + Bulk Prepare |
| 4 | Delivery | Progressive on the same user-triggered run (not background unattended rejudge) |
| 5 | Grain | Job Posting identity + phase (`Judging` / `Preparing`) |
| 6 | Leave/refresh | Abort rest; keep successes; no auto-resume |
| 7 | Stop | Explicit Stop; same abort semantics |
| 8 | Concurrency | One LLM Run at a time; parallel judging parked for later |
| 9 | Position | `k of n` for this run |
| 10 | Term | **LLM Run** |
| 11 | UI surface | Assessment Summary only |
| 12 | Catalog trigger | Explicit start (not `GET /`) |
| 13 | Catalog size | Up to 5 Pending attempts per catalog LLM Run |
| 14 | Crawl / file-change | Stay 1 opportunistic; no LLM Run banner |
| 15 | Mechanism | Process-local run + status poll + Stop flag |
| 16 | Stop mid-call | Cooperative: finish current posting; don’t start next |
| 17 | Out of scope | Key/model UI; multi-provider; spend meter; parallel; Prepare/Enrichment progressive UI |
| 18 | Docs/tracker | CONTEXT + amend ADR-0015 + scratch outcome + new parent from #17 |

## Out of scope (still parked on #17 where noted)

- API key / model / settings UI (env-only)
- Multi-provider SDK surface
- Spend / cost meter
- Parallel judging (future theme)
- Progressive LLM Run UI on Match Assessment single Prepare / Master CV Enrichment (thin reuse later OK)

**Docs:** `CONTEXT.md` (**LLM Run**); ADR-0015 amended.
