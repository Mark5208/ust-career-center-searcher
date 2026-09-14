# Architecture — Job Finding Assistant

Authoritative product language: `CONTEXT.md`. Decided assessment/CV model: ADRs 0005–0014; LLM runtime: ADR-0015; HC/Preference Evidence: ADR-0016; Master CV Enrichment: ADR-0017; Master CV Authoring: ADR-0018. This file describes the **current running code**.

## Runtime shape

- **UI:** FastAPI + Jinja, single-user local server (`job_finding_assistant.web.app`).
- **Application seam:** `Assistant` — the only surface the UI and automated tests call.
- **Persistence:** SQLite via `CatalogStore` (Job Postings, Crawl Filters, Match Assessments, candidate-file fingerprints).
- **Preparation Packets:** tool-managed filesystem store (`PacketStore`) keyed by Job Posting id (Gap Report, Edit Summary, Tailored YAML, optional PDF, `pdf_missing_reasons`); Stale flagged in packet meta on Master CV / HC / Preferences change (meta read-modify-write preserves other fields). Assessment Summary listing uses `presence_flags` (exists + Stale only); full `get` remains for Prepare / packet page / Delete / downloads.
- **Master CV:** RenderCV YAML on disk via `DiskMasterCvStore` (path + Candidate Snapshot rebuild; path setters do not overwrite YAML). **Master CV Enrichment** may atomically patch one target entry on explicit confirm (`enrichment.patch_master_cv_entry` + `atomic_write_text`). Public reads of paths / Snapshot / path-read errors go through `Assistant.get_candidate_files()` → `CandidateFilesView`; mutations stay named set/clear methods (no Master CV clear) plus Enrichment session methods.
- **Master CV Authoring:** `.agents/skills/master-cv-*` plus `.agents/skills/master-cv-write-protocol.md` (ADR-0018). The router (`master-cv-authoring`) classifies `cv` vs design/pins vs both and hints the leaf `/name`(s); it never interviews, writes, or fires the leaves, and it does not hint Holistic Slice vs Detailed Slice. Hint then stop is a complete write-less Sitting. `master-cv-content-interview` classifies Holistic Slice vs Detailed Slice from speech after the user types the leaf, walks Facets on a Holistic Slice (pre-existing YAML is not dump-filled), and still fills named holes as a Detailed Slice (Sitting C Sitting met: Languages + headline, no Facet walk). Existing Holistic Slice writes replace the full `highlights` list (keep bullets that remain true plus new Capability bullets). **Gate met** is held: a name-only greenfield Holistic Slice was Sitting met and the dossier bar held, and a separate Sitting met holistically deepened an existing experience entry. In-app Enrichment remains until a later retirement ticket. Assistant does not write the Master CV except Enrichment.
- **Hard Constraints / Preferences:** plain-text file paths via `DiskConstraintFilesStore` (tool reads only; empty/missing → unknown without judge). Included in `CandidateFilesView` with Master CV.
- **Job Board:** Playwright `JobBoardSession` (User-Attended Login + Crawl); faked in tests. Live adapter marshals all sync Playwright calls onto one dedicated worker thread (FastAPI’s sync threadpool would otherwise raise `greenlet.error` on later `/crawl` loads).
- **Crawl pacing:** `CrawlPacer` lives on `JobBoardSession` only — random delays before detail fetches (1–3s) and between list pages (0.5–1.5s); faked/no-op in tests. `Assistant` does not take a pacer.
- **Crawl catalog sync:** `CatalogStore.apply_crawl_list_presence` / `commit_crawl_detail` own fingerprint skip, reopen-as-Open, upsert, and Pending clear. `Assistant.run_crawl` keeps auth, Hardline, board I/O, `AuthLostError` → partial success, and Closing-capable `mark_missing_open_postings_closed` after a completed loop.
- **LLM ports:** `LlmJudge` (Hard Constraint / Preference / Relevance with input isolation); `LlmCvTailor` (Gap Report / Tailored CV / Edit Summary); `LlmCvEnricher` (placement / follow-up / highlights draft). Normal app path: OpenAI-compatible live client from env (`JOB_FINDING_ASSISTANT_LLM_API_KEY`, optional base URL / model; ADR-0015). Missing key → unavailable adapters (not Fake). Fake stays for tests only. Adapters own **LLM Unavailable** reasons end-to-end. `Assistant` caches the adapter `.reason` unchanged for `get_llm_unavailable_reason()` / catalog / Enrichment. Catalog load via `load_assessment_summary_catalog` is fast (refresh + rows; no Pending judge batch). Catalog assess and Bulk Prepare are process-local **LLM Run**s: public start/stop/status stay on `Assistant`; orchestration (thread, Stop, one-in-flight, both engines, `k of n` publish) lives in `llm_run.py`. `start_catalog_assess_llm_run` drains until Pending empty with live `k of n`; `start_bulk_prepare_llm_run` is uncapped and sequential; `get_llm_run_status` / `stop_llm_run`; at most one in flight; early-stop on LLM Unavailable; cooperative Stop; candidate-file fingerprint clear mid-assess aborts the rest. Catalog assess judges several postings at once: a `ThreadPoolExecutor` sized by `JOB_FINDING_ASSISTANT_CATALOG_ASSESS_MAX_CONCURRENCY` (default 3, clamped 1–10, silent fallback) feeds from one shared `PendingClaimQueue` (`catalog_assess.py`) that tops up from the catalog so Crawl-added Pending joins the same run, defers skipped/failed ids so they cannot starve the rest, and gives deferred ids one retry pass per saved posting (so a run where nothing can succeed ends instead of spinning). While Judging, `LlmRunStatus.in_flight` lists every in-flight identity and `current_index` counts finished postings only; Bulk Prepare keeps its single identity and still counts its in-flight posting. Concurrent `save_match_assessment` calls serialize behind a dedicated app-level lock (distinct from the run-state lock in `llm_run.py`); reads are unaffected. `rejudge_pending_assessments` stays one Pending per call (Crawl / file-change) with no LLM Run banner and no concurrency. On `llm_failed`/`skipped`, that id is deferred for the process so later Pending Job Postings still advance (retry deferred heads after a full pass); live HTTP timeout 30s → LLM Unavailable. Compatible hosts (e.g. DeepSeek) need matching `JOB_FINDING_ASSISTANT_LLM_MODEL`, not the OpenAI default.
- **PDF:** `PdfRenderer` (`RenderCvPdfRenderer` via RenderCV CLI; `FakePdfRenderer` in tests). Before ever rendering, `Assistant.prepare` validates the Tailored YAML against RenderCV's real schema (`rendercv_validation.validate_tailored_yaml`, wrapping `rendercv.schema.rendercv_model_builder.build_rendercv_dictionary_and_model`); `strip_assistant_metadata` (shared by the validator and `RenderCvPdfRenderer`) drops `assistant.*` metadata first so a legitimate `pinned_section_order` is never mistaken for a schema error. On the first validation failure, `prepare` retries `LlmCvTailor.tailor(..., prior_attempt_errors=...)` once with the formatted errors, keeping whichever attempt's Gap Report + Edit Summary + Tailored YAML together (never mixed). A still-invalid retry, or any other `PdfRenderError`, keeps the packet with the PDF missing and `pdf_missing_reasons` populated (one line per schema problem, or the renderer's own message) instead of a bare missing-PDF notice; this applies uniformly inside Bulk Prepare's per-posting loop too.
- **Research notes:** indexed in `.scratch/README.md` (`research-*.md`).

```
Browser → FastAPI/Jinja → Assistant → CatalogStore (SQLite)
                              ├→ PacketStore (tool-managed files)
                              ├→ JobBoardSession (Playwright live / Fake in tests; owns CrawlPacer)
                              ├→ MasterCvStore (DiskMasterCvStore)
                              ├→ ConstraintFilesStore (DiskConstraintFilesStore)
                              ├→ LlmJudge (OpenAI-compatible live / Unavailable / Fake in tests)
                              ├→ LlmCvTailor (same client+model as judge / Unavailable / Fake in tests)
                              ├→ LlmCvEnricher (same client+model / Unavailable / Fake in tests)
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
`match_assessments` absence means Pending. On candidate-file fingerprint change, all assessment rows are cleared (Pending) and all Preparation Packets are marked Stale; Crawl new/detail-changed postings clear that posting’s assessment only (packets are not Staled by Crawl). Candidate-file freshness is an internal `Assistant` gate (same call sites as before; not a public method); out-of-band disk edits are observed on the next public use. Re-judge: Assessment Summary catalog assess is an explicit LLM Run; Crawl / file-change paths may call `rejudge_pending_assessments` (one Pending, no LLM Run banner).

Preparation Packet artifacts live under the tool-managed `PacketStore` directory (not SQLite): per Job Posting `gap_report.json`, `edit_summary.json`, `tailored.yaml`, optional `tailored.pdf`, and `meta.json` (`stale`).

## Package layout

```
src/job_finding_assistant/
  assistant.py              # Assistant + AssessmentSummary + page loads + CandidateFilesView + Enrichment + Prepare/Bulk Delete + LLM Run start/stop/status + CrawlOutcome
  llm_run.py                # LLM Run orchestration (catalog assess + Bulk Prepare engines; types re-exported from assistant)
  catalog_assess.py         # Catalog assess concurrency knob + shared PendingClaimQueue
  enrichment.py             # Enrichment types + Master CV entry patch / atomic write (ADR-0017)
  preparation_packet.py     # GapReport, EditSummary, TailorResult, PreparationPacket
  packet_store.py           # Tool-managed PacketStore (filesystem)
  pdf_renderer.py           # RenderCvPdfRenderer + PdfRenderError
  rendercv_validation.py    # Tailored YAML vs RenderCV real schema + strip_assistant_metadata
  crawl_filters.py          # CrawlFilters (+ Closing-capable check)
  crawl_pacer.py            # RandomCrawlPacer / NoOpCrawlPacer delay ranges
  constraint_files.py       # Read-only HC/Preferences file + fingerprint helpers
  constraint_files_store.py # DiskConstraintFilesStore (paths; read-only on files)
  match_assessment.py       # MatchAssessment, judgments, EvidencePair
  job_board.py              # JobListEntry, JobPostingDetail, AuthLostError, CrawlOutcome
  playwright_job_board.py   # Live Playwright JobBoardSession
  candidate_snapshot.py     # CandidateSnapshot + RenderCV YAML section parse
  master_cv_store.py        # DiskMasterCvStore (path state; Snapshot rebuild)
  catalog_store.py          # SQLite CatalogStore + JobPosting + AssessmentSummaryRow
  ports.py                  # Protocols for adapters
  llm_runtime.py            # OpenAI-compatible LlmJudge / LlmCvTailor / LlmCvEnricher + Unavailable
  fakes.py                  # Test fakes (never wired into build_default_assistant)
  web/
    app.py                  # create_app(assistant), main()
    templates/              # catalog + match assessment + candidate + enrichment + crawl + packet + confirms
tests/                      # Behavior through Assistant (+ UI→Assistant)
```

Assessment Summary projection: typed `AssessmentSummaryRow` from catalog + `PacketStore.presence_flags`; map/filter/sort stay behind `Assistant._list_assessment_summaries_after_refresh`. Public reads are page loads (`load_assessment_summary_catalog` / `load_match_assessment_page` / `load_preparation_packet_page`); `can_prepare` / `get_preparation_packet` are `_` implementation; public `list_assessment_summaries` / `get_match_assessment` are gone. `rejudge_pending_assessments` stays public for opportunistic one-Pending rejudge.

## Candidate / Crawl / Assessment / Prepare UI

- `/` — Assessment Summary list via `Assistant.load_assessment_summary_catalog` (default Open + Upcoming/Unknown; Closed/Passed toggles; links to Match Assessment detail; per-row checkboxes + select-all; **Bulk Prepare** / **Bulk Delete**; explicit **Assess Pending** LLM Run; packet presence/Stale; fast load with no Pending judge batch; live LLM Run status via poll + Stop, listing every in-flight identity while Judging; short non-secret LLM Unavailable reason when judge/tailor cannot run)
- POST `/llm-run/assess` / GET `/llm-run/status` / POST `/llm-run/stop` — start catalog assess LLM Run, poll status, cooperative Stop
- POST `/bulk/prepare` / `/bulk/delete` — catalog bulk actions with combined confirm pages; Bulk Prepare starts an LLM Run; Bulk Delete result counts flash on Assessment Summary
- `/jobs/{id}` — Match Assessment detail via `Assistant.load_match_assessment_page` (summary + Match Assessment + can_prepare + LLM Unavailable; no opportunistic rejudge; non-sticky **Signal Summary** with in-page anchors; independently collapsible **Signal Sections** (`details`/`summary`, all open on first load) for HC + reason + Hard Constraint Evidence, Preference + reason + Preference Evidence, Relevance + Relevance Evidence; signal-specific counterpart labels; Prepare / Delete after sections; Pending / LLM Unavailable clear without empty Signal Sections; no exclusive accordion / Override)
- `/jobs/{id}/prepare` (POST) — Prepare with confirm pages for HC fail / overwrite
- `/jobs/{id}/delete` (POST) — Delete with confirm naming posting / assessment / packet (if any)
- `/jobs/{id}/packet` — Preparation Packet via `Assistant.load_preparation_packet_page` (title/employer + Gap Report → Edit Summary → Tailored downloads + compact current Match Assessment; no opportunistic rejudge; link to detail for full Evidence lists)
- `/jobs/{id}/packet/yaml` / `/jobs/{id}/packet/pdf` — downloads
- `/candidate` — set Master CV / Hard Constraints / Preferences paths; inspect Candidate Snapshot; link to Master CV Enrichment; path/read errors (page reads `get_candidate_files()`)
- `/candidate/enrichment` — Master CV Enrichment step UI (freeform → placement → dimensions → highlights → confirm write) via `Assistant` Enrichment session
- `/crawl` — User-Attended Login, Crawl Filters, Incremental Crawl / Full Refresh
- POST `/candidate/master-cv`, `/candidate/hard-constraints`, `/candidate/preferences` (+ clear) — mutate only via Assistant
- POST `/candidate/enrichment/*` — Enrichment freeform / placement / dimension / highlights / confirm
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
- Hard Constraint / Preference Evidence lists are stored and shown on Match Assessment detail (ADR-0016) with Signal Summary + independently collapsible Signal Sections (#21), not on Assessment Summary or duplicated into the packet path. Exclusive one-open accordion chrome remains out of v1.
