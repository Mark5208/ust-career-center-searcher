# Design document — Job Finding Assistant

Authoritative product language: `CONTEXT.md`. Scope ADRs: `docs/adr/0001`–`0004`. Parent spec: GitHub issue #1.

## Primary seam

`Assistant` is the application API. UI routes and tests call only `Assistant`. Adapters behind it (`CatalogStore`, `JobBoardSession`, `MasterCvStore`, `LlmJudge`, `LlmCvTailor`, later `HardConstraintEvaluator`) are not the primary test surface except pure Hard Constraint rules.

## Scaffold slice (issue #2)

Deliver a runnable local shell: FastAPI + Jinja, SQLite `CatalogStore` (minimal schema), fakeable ports, and an empty-catalog Assessment Summary path proven through `Assistant` without Playwright or a real LLM.

## Master CV / Snapshot / Preferences slice (issue #3)

Through `Assistant` and `/candidate` UI:

- Set/update Master CV LaTeX path; never overwrite the Master CV file (`DiskMasterCvStore` reads only).
- Rebuild inspectable Candidate Snapshot from Master CV sections (contact, education, experience, projects, skills/tools as written); not hand-editable.
- Persist Preferences (languages with optional level, locations, Gap Tolerance None/Semester/Year/Any/unset) in SQLite; no Crawl Filters on Preferences.

## Crawl slice (issue #4)

Through `Assistant` and `/crawl` UI, with primary tests on a fake `JobBoardSession`:

- User-Attended Login opens the browser; Crawl starts only when authenticated; no board passwords stored (ADR-0004).
- Crawl Filters (seven groups + three checkboxes + optional Deadline Hardline) default to Active Job on; persist separately from Preferences.
- Incremental Crawl and Full Refresh upsert Job Postings from detail fetch; Hardline skips detail/add after list discovery.
- Narrow filters only add/update; Closing-capable (unfiltered or Active-Job-only) completed syncs may mark absent Open postings Closed.
- Auth-loss mid-Crawl → partial success; keep stored work; do not mark untouched postings Closed.
- Live board: Playwright `JobBoardSession` using selectors from `.scratch/job-board-dom.md`.
- `CrawlPacer` random delays before detail fetches and between list pages (tested via recording fake; no real sleep in primary tests).
