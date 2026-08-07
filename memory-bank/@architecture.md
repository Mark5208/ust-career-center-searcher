# Architecture — Job Finding Assistant

Authoritative product language: `CONTEXT.md`. Decided assessment/CV model: ADRs 0005–0014. This file describes the **current running code**; decided-but-unimplemented shape is under [Decided next (docs ahead of code)](#decided-next-docs-ahead-of-code).

## Runtime shape

- **UI:** FastAPI + Jinja, single-user local server (`job_finding_assistant.web.app`).
- **Application seam:** `Assistant` — the only surface the UI and automated tests call.
- **Persistence:** SQLite via `CatalogStore` (Job Postings, Crawl Filters, Match Assessments, candidate-file fingerprints; later Preparation Packet metadata).
- **Master CV:** LaTeX on disk via `DiskMasterCvStore` (path + Candidate Snapshot rebuild; never overwrites the `.tex` file).
- **Hard Constraints / Preferences:** plain-text file paths via `DiskConstraintFilesStore` (tool reads only; empty/missing → unknown without judge).
- **Job Board:** Playwright `JobBoardSession` (User-Attended Login + Crawl); faked in tests.
- **Crawl pacing:** `CrawlPacer` inserts random delays before detail fetches (1–3s) and between list pages (0.5–1.5s); faked/no-op in tests.
- **LLM ports:** `LlmJudge` (Hard Constraint / Preference / Relevance with input isolation); `LlmCvTailor` (Gap Report / Tailored CV / Edit Summary); faked in tests.

```
Browser → FastAPI/Jinja → Assistant → CatalogStore (SQLite)
                              ├→ JobBoardSession (Playwright live / Fake in tests)
                              ├→ CrawlPacer (Random live / Fake or NoOp in tests)
                              ├→ MasterCvStore (DiskMasterCvStore)
                              ├→ ConstraintFilesStore (DiskConstraintFilesStore)
                              ├→ LlmJudge
                              └→ LlmCvTailor
```

## Database schema (CatalogStore)

Empty catalog is valid. Current SQLite schema:

```sql
CREATE TABLE IF NOT EXISTS job_postings (
    id TEXT PRIMARY KEY,
    title TEXT,
    employer TEXT,
    listing_status TEXT,
    deadline_status TEXT,
    posting_date TEXT,
    application_deadline TEXT,
    detail_json TEXT,
    list_fingerprint TEXT
);

CREATE TABLE IF NOT EXISTS crawl_filters (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    filters_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS candidate_fingerprints (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    master_cv_fingerprint TEXT,
    hard_constraints_fingerprint TEXT,
    preferences_fingerprint TEXT
);

CREATE TABLE IF NOT EXISTS match_assessments (
    job_posting_id TEXT PRIMARY KEY,
    hard_constraint_outcome TEXT NOT NULL,
    hard_constraint_reason TEXT NOT NULL,
    preference TEXT,
    preference_reason TEXT NOT NULL,
    relevance TEXT NOT NULL,
    evidence_json TEXT NOT NULL
);
```

`listing_status` and `deadline_status` follow glossary values (Open/Closed; Upcoming/Passed/Unknown).
`list_fingerprint` supports incremental Crawl skip when list row facts are unchanged.
`detail_json` stores structured detail fields (including Evidence-rich text) from the detail page.
`preference` is Strong/Mixed/Weak, or SQL NULL for unknown Preference.
`candidate_fingerprints` detects Master CV / HC / Preferences content or path-clear changes (ADR-0014).
`match_assessments` absence means Pending. On candidate-file fingerprint change, all assessment rows are cleared (Pending); Crawl new/detail-changed postings clear that posting’s assessment. Re-judge is opportunistic via `rejudge_pending_assessments()` (catalog UI calls it on load).
Preparation Packet tables arrive in a later slice (`has_preparation_packet` / Stale remain false for now).

## Package layout

```
src/job_finding_assistant/
  assistant.py              # Assistant + AssessmentSummary + CrawlOutcome
  crawl_filters.py          # CrawlFilters (+ Closing-capable check)
  crawl_pacer.py            # RandomCrawlPacer / NoOpCrawlPacer delay ranges
  constraint_files.py       # Read-only HC/Preferences file + fingerprint helpers
  constraint_files_store.py # DiskConstraintFilesStore (paths; read-only on files)
  match_assessment.py       # MatchAssessment, judgments, EvidencePair
  job_board.py              # JobListEntry, JobPostingDetail, AuthLostError, CrawlOutcome
  playwright_job_board.py   # Live Playwright JobBoardSession
  candidate_snapshot.py     # CandidateSnapshot + LaTeX section parse
  master_cv_store.py        # DiskMasterCvStore (path state; read-only Master CV)
  catalog_store.py          # SQLite CatalogStore
  ports.py                  # Protocols for adapters
  fakes.py                  # Test / local-shell fakes
  web/
    app.py                  # create_app(assistant), main()
    templates/              # Jinja pages (catalog + candidate + crawl)
tests/                      # Behavior through Assistant (+ UI→Assistant)
```

## Candidate / Crawl / Assessment UI

- `/` — Assessment Summary list (default Open + Upcoming/Unknown; Closed/Passed toggles; Prepare gate; opportunistic rejudge on load)
- `/candidate` — set Master CV / Hard Constraints / Preferences paths; inspect Candidate Snapshot; path/read errors
- `/crawl` — User-Attended Login, Crawl Filters, Incremental Crawl / Full Refresh
- POST `/candidate/master-cv`, `/candidate/hard-constraints`, `/candidate/preferences` (+ clear) — mutate only via Assistant
- POST `/crawl/login`, POST `/crawl/filters`, POST `/crawl/run` — mutate only via Assistant

## How to run

```bash
pip install -e ".[dev]"
playwright install chromium   # once, for live Job Board
job-finding-assistant          # http://127.0.0.1:8000
pytest
```

Live Crawls intentionally wait randomly between Job Board list pages and detail fetches to reduce bursty request patterns.

## Decided next (docs ahead of code)

Not implemented yet. Product intent in `CONTEXT.md` and ADRs 0007, 0009, 0011–0013 (and remaining YAML migration):

- Master CV becomes RenderCV YAML (Python ≥3.12); Candidate Snapshot from YAML; Tailored CV YAML → RenderCV PDF at prepare; no LaTeX Master CV in v1.
- Tailored CV formatting rules (reorder-first, pinned section order, omission/rephrase limits) are documented in ADR-0009; still unimplemented in `LlmCvTailor`.
- Gap Report rules (Prepare-time, missing/partial, non-fictional suggestions, tailor must not fill Missing) are documented in ADR-0011; still unimplemented (no `prepare()` yet).
- Edit Summary rules (grouped disclosures, Gap Report boundary, best-effort checklist from the tailor) are documented in ADR-0012; still unimplemented (no `prepare()` yet).
- Prepare flow (gates, confirms, packet contents, tool-managed store, downloads, Delete cascade, Stale, atomic failure) is documented in ADR-0013; still unimplemented (no `prepare()` yet). Stale marking on candidate-file change is reserved for when packets exist.
- Live `LlmJudge` provider (not Fake) implementing ADR-0008 / ADR-0010 rubrics end-to-end.
