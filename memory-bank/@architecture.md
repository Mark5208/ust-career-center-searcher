# Architecture — Job Finding Assistant

Authoritative product language: `CONTEXT.md`. Decided assessment/CV model: ADRs 0005–0014; LLM runtime: ADR-0015. This file describes the **current running code**.

## Runtime shape

- **UI:** FastAPI + Jinja, single-user local server (`job_finding_assistant.web.app`).
- **Application seam:** `Assistant` — the only surface the UI and automated tests call.
- **Persistence:** SQLite via `CatalogStore` (Job Postings, Crawl Filters, Match Assessments, candidate-file fingerprints).
- **Preparation Packets:** tool-managed filesystem store (`PacketStore`) keyed by Job Posting id (Gap Report, Edit Summary, Tailored YAML, optional PDF); Stale flagged in packet meta on Master CV / HC / Preferences change.
- **Master CV:** RenderCV YAML on disk via `DiskMasterCvStore` (path + Candidate Snapshot rebuild; never overwrites the YAML file). Python ≥3.12; `rendercv` dependency present.
- **Hard Constraints / Preferences:** plain-text file paths via `DiskConstraintFilesStore` (tool reads only; empty/missing → unknown without judge).
- **Job Board:** Playwright `JobBoardSession` (User-Attended Login + Crawl); faked in tests.
- **Crawl pacing:** `CrawlPacer` inserts random delays before detail fetches (1–3s) and between list pages (0.5–1.5s); faked/no-op in tests.
- **LLM ports:** `LlmJudge` (Hard Constraint / Preference / Relevance with input isolation); `LlmCvTailor` (Gap Report / Tailored CV / Edit Summary). Normal app path: OpenAI-compatible live client from env (`JOB_FINDING_ASSISTANT_LLM_API_KEY`, optional base URL / model; ADR-0015). Missing key → unavailable adapters (not Fake). Fake stays for tests only. Catalog `rejudge_pending_assessments` budgets one Pending posting per call (refresh continues); live HTTP timeout 30s → LLM Unavailable. Compatible hosts (e.g. DeepSeek) need matching `JOB_FINDING_ASSISTANT_LLM_MODEL`, not the OpenAI default.
- **PDF:** `PdfRenderer` (`RenderCvPdfRenderer` via RenderCV CLI; `FakePdfRenderer` in tests). PDF-only failure leaves packet without PDF.

```
Browser → FastAPI/Jinja → Assistant → CatalogStore (SQLite)
                              ├→ PacketStore (tool-managed files)
                              ├→ JobBoardSession (Playwright live / Fake in tests)
                              ├→ CrawlPacer (Random live / Fake or NoOp in tests)
                              ├→ MasterCvStore (DiskMasterCvStore)
                              ├→ ConstraintFilesStore (DiskConstraintFilesStore)
                              ├→ LlmJudge (OpenAI-compatible live / Unavailable / Fake in tests)
                              ├→ LlmCvTailor (same client+model as judge / Unavailable / Fake in tests)
                              └→ PdfRenderer (RenderCV / Fake)
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
`match_assessments` absence means Pending. On candidate-file fingerprint change, all assessment rows are cleared (Pending) and all Preparation Packets are marked Stale; Crawl new/detail-changed postings clear that posting’s assessment only (packets are not Staled by Crawl). Re-judge is opportunistic via `rejudge_pending_assessments()` (catalog UI calls it on load).

Preparation Packet artifacts live under the tool-managed `PacketStore` directory (not SQLite): per Job Posting `gap_report.json`, `edit_summary.json`, `tailored.yaml`, optional `tailored.pdf`, and `meta.json` (`stale`).

## Package layout

```
src/job_finding_assistant/
  assistant.py              # Assistant + AssessmentSummary + Prepare + CrawlOutcome
  preparation_packet.py     # GapReport, EditSummary, TailorResult, PreparationPacket
  packet_store.py           # Tool-managed PacketStore (filesystem)
  pdf_renderer.py           # RenderCvPdfRenderer + PdfRenderError
  crawl_filters.py          # CrawlFilters (+ Closing-capable check)
  crawl_pacer.py            # RandomCrawlPacer / NoOpCrawlPacer delay ranges
  constraint_files.py       # Read-only HC/Preferences file + fingerprint helpers
  constraint_files_store.py # DiskConstraintFilesStore (paths; read-only on files)
  match_assessment.py       # MatchAssessment, judgments, EvidencePair
  job_board.py              # JobListEntry, JobPostingDetail, AuthLostError, CrawlOutcome
  playwright_job_board.py   # Live Playwright JobBoardSession
  candidate_snapshot.py     # CandidateSnapshot + RenderCV YAML section parse
  master_cv_store.py        # DiskMasterCvStore (path state; read-only Master CV YAML)
  catalog_store.py          # SQLite CatalogStore
  ports.py                  # Protocols for adapters
  llm_runtime.py            # OpenAI-compatible LlmJudge / LlmCvTailor + Unavailable (ADR-0015)
  fakes.py                  # Test fakes (never wired into build_default_assistant)
  web/
    app.py                  # create_app(assistant), main()
    templates/              # catalog + match assessment detail + candidate + crawl + packet + prepare/delete confirm
tests/                      # Behavior through Assistant (+ UI→Assistant)
```

## Candidate / Crawl / Assessment / Prepare UI

- `/` — Assessment Summary list (default Open + Upcoming/Unknown; Closed/Passed toggles; links to Match Assessment detail; Prepare / Re-Prepare; Delete; packet presence/Stale; opportunistic rejudge of at most one Pending posting on load; short non-secret LLM Unavailable reason when judge/tailor cannot run)
- `/jobs/{id}` — Match Assessment detail (HC + reason, Preference + reason, Relevance, Relevance Evidence; Prepare / Delete; Pending / LLM Unavailable clear; no accordion / Override)
- `/jobs/{id}/prepare` (POST) — Prepare with confirm pages for HC fail / overwrite
- `/jobs/{id}/delete` (POST) — Delete with confirm naming posting / assessment / packet (if any)
- `/jobs/{id}/packet` — Gap Report → Edit Summary → Tailored downloads + current Match Assessment
- `/jobs/{id}/packet/yaml` / `/jobs/{id}/packet/pdf` — downloads
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

## Notes

- Production PDF uses `RenderCvPdfRenderer` (RenderCV CLI); local shell falls back to missing-PDF signal when the CLI is unavailable. Tests use `FakePdfRenderer`.
- Accordion / richer Match Assessment navigation chrome remains out of v1; HC/Preference show short reasons only (no separate stored Evidence lists).
