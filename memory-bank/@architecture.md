# Architecture — Job Finding Assistant

Authoritative product language: `CONTEXT.md`. Decided assessment/CV model: ADRs 0005–0014; LLM runtime: ADR-0015; HC/Preference Evidence: ADR-0016. This file describes the **current running code**.

## Runtime shape

- **UI:** FastAPI + Jinja, single-user local server (`job_finding_assistant.web.app`).
- **Application seam:** `Assistant` — the only surface the UI and automated tests call.
- **Persistence:** SQLite via `CatalogStore` (Job Postings, Crawl Filters, Match Assessments, candidate-file fingerprints).
- **Preparation Packets:** tool-managed filesystem store (`PacketStore`) keyed by Job Posting id (Gap Report, Edit Summary, Tailored YAML, optional PDF); Stale flagged in packet meta on Master CV / HC / Preferences change. Assessment Summary listing uses `presence_flags` (exists + Stale only); full `get` remains for Prepare / packet page / Delete / downloads.
- **Master CV:** RenderCV YAML on disk via `DiskMasterCvStore` (path + Candidate Snapshot rebuild; never overwrites the YAML file). Python ≥3.12; `rendercv` dependency present. Public reads of paths / Snapshot / path-read errors go through `Assistant.get_candidate_files()` → `CandidateFilesView`; mutations stay named set/clear methods (no Master CV clear).
- **Hard Constraints / Preferences:** plain-text file paths via `DiskConstraintFilesStore` (tool reads only; empty/missing → unknown without judge). Included in `CandidateFilesView` with Master CV.
- **Job Board:** Playwright `JobBoardSession` (User-Attended Login + Crawl); faked in tests. Live adapter marshals all sync Playwright calls onto one dedicated worker thread (FastAPI’s sync threadpool would otherwise raise `greenlet.error` on later `/crawl` loads).
- **Crawl pacing:** `CrawlPacer` lives on `JobBoardSession` only — random delays before detail fetches (1–3s) and between list pages (0.5–1.5s); faked/no-op in tests. `Assistant` does not take a pacer.
- **Crawl catalog sync:** `CatalogStore.apply_crawl_list_presence` / `commit_crawl_detail` own fingerprint skip, reopen-as-Open, upsert, and Pending clear. `Assistant.run_crawl` keeps auth, Hardline, board I/O, `AuthLostError` → partial success, and Closing-capable `mark_missing_open_postings_closed` after a completed loop.
- **LLM ports:** `LlmJudge` (Hard Constraint / Preference / Relevance with input isolation); `LlmCvTailor` (Gap Report / Tailored CV / Edit Summary). Normal app path: OpenAI-compatible live client from env (`JOB_FINDING_ASSISTANT_LLM_API_KEY`, optional base URL / model; ADR-0015). Missing key → unavailable adapters (not Fake). Fake stays for tests only. Judge/tailor adapters own **LLM Unavailable** reasons end-to-end: preflight via `unavailable_reason()`, call failures only as `LlmUnavailableError` (provider/parse/timeout/unexpected → short safe `.reason`; Fake matches that contract). `Assistant` caches the adapter `.reason` unchanged for `get_llm_unavailable_reason()` / catalog. Catalog load via `load_assessment_summary_catalog` budgets up to five Pending postings per call (sequential; early-stop that load on LLM Unavailable; refresh continues); `rejudge_pending_assessments` stays one Pending per call (Crawl / file-change). On `llm_failed`/`skipped`, that id is deferred for the process so later Pending Job Postings still advance (retry deferred heads after a full pass); live HTTP timeout 30s → LLM Unavailable. Compatible hosts (e.g. DeepSeek) need matching `JOB_FINDING_ASSISTANT_LLM_MODEL`, not the OpenAI default.
- **PDF:** `PdfRenderer` (`RenderCvPdfRenderer` via RenderCV CLI; `FakePdfRenderer` in tests). PDF-only failure leaves packet without PDF.

```
Browser → FastAPI/Jinja → Assistant → CatalogStore (SQLite)
                              ├→ PacketStore (tool-managed files)
                              ├→ JobBoardSession (Playwright live / Fake in tests; owns CrawlPacer)
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
    evidence_json TEXT NOT NULL,
    hard_constraint_evidence_json TEXT NOT NULL DEFAULT '[]',
    preference_evidence_json TEXT NOT NULL DEFAULT '[]'
);
```

`listing_status` and `deadline_status` follow glossary values (Open/Closed; Upcoming/Passed/Unknown).
`list_fingerprint` supports incremental Crawl skip when list row facts are unchanged.
`detail_json` stores structured detail fields (including Evidence-rich text) from the detail page — codec is private to `CatalogStore`; callers use typed `JobPosting` (`detail_fields` + `fields_for_llm()`).
`preference` is Strong/Mixed/Weak, or SQL NULL for unknown Preference.
`evidence_json` is Relevance Evidence; `hard_constraint_evidence_json` / `preference_evidence_json` are Hard Constraint Evidence / Preference Evidence (ADR-0016). Pre-upgrade rows migrate to empty HC/Preference lists until a natural rejudge.
`candidate_fingerprints` detects Master CV / HC / Preferences content or path-clear changes (ADR-0014).
`match_assessments` absence means Pending. On candidate-file fingerprint change, all assessment rows are cleared (Pending) and all Preparation Packets are marked Stale; Crawl new/detail-changed postings clear that posting’s assessment only (packets are not Staled by Crawl). Candidate-file freshness is an internal `Assistant` gate (same call sites as before; not a public method); out-of-band disk edits are observed on the next public use. Re-judge is opportunistic: Assessment Summary `GET /` uses `load_assessment_summary_catalog`; Crawl / file-change paths may call `rejudge_pending_assessments`.

Preparation Packet artifacts live under the tool-managed `PacketStore` directory (not SQLite): per Job Posting `gap_report.json`, `edit_summary.json`, `tailored.yaml`, optional `tailored.pdf`, and `meta.json` (`stale`).

## Package layout

```
src/job_finding_assistant/
  assistant.py              # Assistant + AssessmentSummary + page loads + CandidateFilesView + Prepare + CrawlOutcome
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
  catalog_store.py          # SQLite CatalogStore + JobPosting + AssessmentSummaryRow
  ports.py                  # Protocols for adapters
  llm_runtime.py            # OpenAI-compatible LlmJudge / LlmCvTailor + Unavailable (ADR-0015)
  fakes.py                  # Test fakes (never wired into build_default_assistant)
  web/
    app.py                  # create_app(assistant), main()
    templates/              # catalog + match assessment detail + candidate + crawl + packet + prepare/delete confirm
tests/                      # Behavior through Assistant (+ UI→Assistant)
```

Assessment Summary projection: typed `AssessmentSummaryRow` from catalog + `PacketStore.presence_flags`; map/filter/sort stay behind `Assistant.list_assessment_summaries`.

## Candidate / Crawl / Assessment / Prepare UI

- `/` — Assessment Summary list via `Assistant.load_assessment_summary_catalog` (default Open + Upcoming/Unknown; Closed/Passed toggles; links to Match Assessment detail; Prepare / Re-Prepare; Delete; packet presence/Stale; one refresh + at most five Pending rejudge attempts per load with early-stop on LLM Unavailable; progress banner for `processed_this_load` / `pending_remaining`; short non-secret LLM Unavailable reason when judge/tailor cannot run)
- `/jobs/{id}` — Match Assessment detail via `Assistant.load_match_assessment_page` (summary + Match Assessment + can_prepare + LLM Unavailable; no opportunistic rejudge; HC + reason + Hard Constraint Evidence, Preference + reason + Preference Evidence, Relevance + Relevance Evidence; signal-specific counterpart labels; Prepare / Delete; Pending / LLM Unavailable clear; no accordion / Override)
- `/jobs/{id}/prepare` (POST) — Prepare with confirm pages for HC fail / overwrite
- `/jobs/{id}/delete` (POST) — Delete with confirm naming posting / assessment / packet (if any)
- `/jobs/{id}/packet` — Preparation Packet via `Assistant.load_preparation_packet_page` (title/employer + Gap Report → Edit Summary → Tailored downloads + compact current Match Assessment; no opportunistic rejudge; link to detail for full Evidence lists)
- `/jobs/{id}/packet/yaml` / `/jobs/{id}/packet/pdf` — downloads
- `/candidate` — set Master CV / Hard Constraints / Preferences paths; inspect Candidate Snapshot; path/read errors (page reads `get_candidate_files()`)
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
- Accordion / richer Match Assessment navigation chrome remains out of v1; Hard Constraint / Preference Evidence lists are stored and shown on Match Assessment detail (ADR-0016), not on Assessment Summary or duplicated into the packet path.
