# Architecture — Job Finding Assistant

Authoritative product language: `CONTEXT.md`. Decided assessment/CV model: ADRs 0005–0014. This file describes the **current running code**; decided-but-unimplemented shape is under [Decided next (docs ahead of code)](#decided-next-docs-ahead-of-code).

## Runtime shape

- **UI:** FastAPI + Jinja, single-user local server (`job_finding_assistant.web.app`).
- **Application seam:** `Assistant` — the only surface the UI and automated tests call.
- **Persistence:** SQLite via `CatalogStore` (Job Postings, Preferences, Crawl Filters, Match Assessments; later Preparation Packet metadata).
- **Master CV:** LaTeX on disk via `DiskMasterCvStore` (path + Candidate Snapshot rebuild; never overwrites the `.tex` file).
- **Job Board:** Playwright `JobBoardSession` (User-Attended Login + Crawl); faked in tests.
- **Crawl pacing:** `CrawlPacer` inserts random delays before detail fetches (1–3s) and between list pages (0.5–1.5s); faked/no-op in tests.
- **Hard Constraints:** pure rules in `hard_constraints` (language, location, Gap Tolerance).
- **LLM ports:** `LlmJudge` (Relevance / Evidence), `LlmCvTailor` (Gap Report / Tailored CV / Edit Summary); faked in tests.

```
Browser → FastAPI/Jinja → Assistant → CatalogStore (SQLite)
                              ├→ JobBoardSession (Playwright live / Fake in tests)
                              ├→ CrawlPacer (Random live / Fake or NoOp in tests)
                              ├→ MasterCvStore (DiskMasterCvStore)
                              ├→ hard_constraints (pure rules)
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

CREATE TABLE IF NOT EXISTS preferences (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    languages_json TEXT NOT NULL,
    locations_json TEXT NOT NULL,
    gap_tolerance TEXT
);

CREATE TABLE IF NOT EXISTS crawl_filters (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    filters_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS match_assessments (
    job_posting_id TEXT PRIMARY KEY,
    hard_constraint_outcome TEXT NOT NULL,
    hard_constraints_json TEXT NOT NULL,
    relevance TEXT NOT NULL,
    evidence_json TEXT NOT NULL
);
```

`listing_status` and `deadline_status` follow glossary values (Open/Closed; Upcoming/Passed/Unknown).
`gap_tolerance` is `None` / `Semester` / `Year` / `Any`, or SQL NULL when unset.
`list_fingerprint` supports incremental Crawl skip when list row facts are unchanged.
`detail_json` stores structured detail fields (including Evidence-rich text) from the detail page.
`match_assessments` rows are rebuilt for new/changed Crawl detail and for Open postings when Master CV or Preferences change; absence means Pending.
Preparation Packet tables arrive in a later slice (`has_preparation_packet` / Stale remain false for now).

## Package layout

```
src/job_finding_assistant/
  assistant.py              # Assistant + AssessmentSummary + CrawlOutcome
  crawl_filters.py          # CrawlFilters (+ Closing-capable check)
  crawl_pacer.py            # RandomCrawlPacer / NoOpCrawlPacer delay ranges
  hard_constraints.py       # Language / location / Gap Tolerance rules
  match_assessment.py       # MatchAssessment, EvidencePair, JudgeResult
  job_board.py              # JobListEntry, JobPostingDetail, AuthLostError, CrawlOutcome
  playwright_job_board.py   # Live Playwright JobBoardSession
  preferences.py            # Preferences, LanguagePreference, GapTolerance
  candidate_snapshot.py     # CandidateSnapshot + LaTeX section parse
  master_cv_store.py        # DiskMasterCvStore (path state; read-only Master CV)
  catalog_store.py          # SQLite CatalogStore
  ports.py                  # Protocols for adapters
  fakes.py                  # Test / local-shell fakes
  web/
    app.py                  # create_app(assistant), main()
    templates/              # Jinja pages (catalog + candidate + crawl)
tests/                      # Behavior through Assistant (+ UI→Assistant; HC pure rules)
```

## Candidate / Preferences / Crawl / Assessment UI

- `/` — Assessment Summary list (default Open + Upcoming/Unknown; Closed/Passed toggles; Prepare gate)
- `/candidate` — set Master CV path, inspect Candidate Snapshot, edit Preferences
- `/crawl` — User-Attended Login, Crawl Filters, Incremental Crawl / Full Refresh
- POST `/candidate/master-cv`, POST `/candidate/preferences` — mutate only via Assistant
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

Not implemented yet. Product intent in `CONTEXT.md` and ADRs 0005–0014:

- Replace structured `preferences` + `hard_constraints` rules with two read-only disk paths (Hard Constraints file, Preferences file) and LLM Hard Constraint / Preference / Relevance judgments.
- Assessment Summary shows Preference and Relevance; sort Preference then Relevance (Deadline Unknown last among deadline ties); Pending/Prepare rules per ADR-0006 / ADR-0013 (HC is a non-blocking signal; Override removed).
- Preference and Relevance judge rubrics (input isolation, band criteria, Evidence/reason outputs) are documented in ADR-0008; still unimplemented in `LlmJudge`.
- Hard Constraint judge rubric (isolation, fail/unknown/pass precedence, conservative inference) is documented in ADR-0010; still unimplemented in `LlmJudge` (code still uses rule-based `hard_constraints`).
- `match_assessments` gains a Preference band (and HC becomes freeform-reason oriented rather than three named rule results).
- Master CV becomes RenderCV YAML (Python ≥3.12); Candidate Snapshot from YAML; Tailored CV YAML → RenderCV PDF at prepare; no LaTeX Master CV in v1.
- Tailored CV formatting rules (reorder-first, pinned section order, omission/rephrase limits) are documented in ADR-0009; still unimplemented in `LlmCvTailor`.
- Gap Report rules (Prepare-time, missing/partial, non-fictional suggestions, tailor must not fill Missing) are documented in ADR-0011; still unimplemented (no `prepare()` yet).
- Edit Summary rules (grouped disclosures, Gap Report boundary, best-effort checklist from the tailor) are documented in ADR-0012; still unimplemented (no `prepare()` yet).
- Prepare flow (gates, confirms, packet contents, tool-managed store, downloads, Delete cascade, Stale, atomic failure) is documented in ADR-0013; still unimplemented (no `prepare()` yet).
- Assessment freshness (ADR-0014): content fingerprint (not path-only); on Master CV / HC / Preferences change mark **all** assessments Pending and packets Stale, then async re-judge; Crawl new/detail-changed → Pending (Crawl success ≠ assessments done); Crawl does not Stale packets; unreadable-file and judge-failure Pending rules — still unimplemented.
