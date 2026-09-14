# Design document — Job Finding Assistant

Authoritative product language: `CONTEXT.md`. Scope ADRs: `docs/adr/0001`–`0018`. Parent spec: GitHub issue #1.

**Docs vs code:** ADRs 0005–0017 Prepare/assessment/CV/LLM/Enrichment slices through `Assistant` are implemented for Assessment Summary (row checkboxes + **Bulk Prepare** / **Bulk Delete** + **LLM Run** activity UX: explicit catalog assess / Bulk Prepare as process-local run with status poll + Stop), Match Assessment detail (`/jobs/{id}` with **Signal Summary** + collapsible **Signal Sections** for Hard Constraint / Preference / Relevance Evidence + short reasons), Master CV Snapshot + **Master CV Enrichment** (`/candidate/enrichment`), constraint files, Crawl, Preparation Packets (Gap Report / Edit Summary / Tailored YAML / PDF / Stale), Delete cascade, and live OpenAI-compatible `LlmJudge` / `LlmCvTailor` / `LlmCvEnricher` (env key; Unavailable when missing; Fake only in tests). Master CV Authoring is the skill family on disk (ADR-0018), not an Assistant slice. Glossary and ADR-0018 name Holistic Slice / Gate met; `master-cv-content-interview` classifies Holistic Slice and Detailed Slice (named-hole Detailed Slice Sitting C is Sitting met). Mixed Sitting last-named-leaf Sitting M is Sitting met. **Gate met** is held (greenfield Holistic Slice Sitting met and dossier bar held; separate existing-entry Holistic Slice Sitting met). In-app Enrichment remains until a later retirement ticket.

## Primary seam

`Assistant` is the application API. UI routes and tests call only `Assistant`. Adapters behind it (`CatalogStore`, `JobBoardSession`, `MasterCvStore`, `LlmJudge`, `LlmCvTailor`, later constraint-file stores / RenderCV renderer) are not the primary test surface except pure rules that remain until freeform Hard Constraints land.

## Decided assessment model (ADR-0005, ADR-0006)

Three signals on each Match Assessment:

- **Hard Constraint** — freeform Hard Constraints file; LLM pass / fail / unknown + reason; empty/missing → unknown (no judge); deal-breaker signal (not a gate); fail never blocks Prepare (confirm with reason). Override removed (ADR-0013).
- **Preference** — separate freeform Preferences file; ordinal Strong / Mixed / Weak (desire); empty/missing → unknown (no judge); Weak does not block Prepare; unknown Preference does not affect sort.
- **Relevance** — ordinal Strong / Mixed / Weak for Master CV / Snapshot vs JD (capability); not an ATS score; not Preference.

Sort: Pending last → Hard Constraint fail after pass/unknown → Preference → Relevance → sooner deadline (known Upcoming sooner-first; Deadline Unknown last among ties).

Pending when a required judgment is missing (non-empty readable HC file, non-empty readable Preferences file, or Relevance). Empty constraint files count as resolved unknown. Judge failure/unavailable → Pending (or keep prior complete assessment). Invalid Master CV → Pending Relevance.

Structured languages / locations / Gap Tolerance Preferences form is superseded (ADR-0002 → ADR-0005). Crawl Filters stay separate.

### Assessment freshness (ADR-0014)

Implemented through an internal `Assistant` candidate-file freshness gate (fingerprint Pending/Stale side effects) plus opportunistic rejudge (`rejudge_pending_assessments` after Crawl / file change; catalog assess via explicit `start_catalog_assess_llm_run`). Out-of-band disk edits are observed on the next public Assistant use — there is no public refresh method:

- Candidate-file “change” = content or path clear (fingerprint on next check); not path-only; no always-on watcher.
- On change: Snapshot now; **all** assessments Pending (Open and Closed); re-judge opportunistic (Crawl / file-change one Pending; catalog assess is an explicit LLM Run).
- Crawl: catalog sync independent of assessment; new/detail-changed → Pending then opportunistic re-judge; Crawl does not Stale packets (ADR-0013; packets still absent).
- Unreadable Master CV → no Snapshot, Pending + error; unreadable HC/Prefs path → unknown + path error (not Pending).
- Judge failure → leave Pending (never half-assessed final row).

### Hard Constraint rubric (ADR-0010)

Implemented at the `LlmJudge.judge_hard_constraint` call site (live OpenAI-compatible prompts; Fake in tests):

- Inputs: Hard Constraints file + Job Posting only (never CV, never Preferences).
- Empty/missing file → unknown without judge; unreadable path → unknown + error.
- Precedence / conservative inference in the live judge prompt (ADR-0010); Fake scripts outcomes.

### Judge rubrics (ADR-0008)

Preference and Relevance call sites enforce input isolation (`judge_preference` never sees CV; `judge_relevance` never sees Preferences). Band criteria live in the live judge prompt; Fake scripts bands for tests.

### Hard Constraint / Preference Evidence on Match Assessment (ADR-0016)

Implemented through `Assistant` / `MatchAssessment` / `CatalogStore` (persisted on save; UI reads stored lists only):

- Hard Constraint Evidence and Preference Evidence lists on Match Assessment detail with signal-specific counterpart labels; empty lists allowed (no padding from short reasons).
- Assessment Summary stays bands-only; Preparation Packet keeps a compact strip (bands + short reasons) with a link to Match Assessment for full lists.
- Pre-upgrade complete rows load empty HC/Preference Evidence until a natural rejudge. Parent: GitHub #19 (closed). Nav/Signal Sections: GitHub #21 (shipped).

### LLM runtime (ADR-0015)

`build_default_assistant` wires `llm_runtime.build_llm_ports` from env (`JOB_FINDING_ASSISTANT_LLM_API_KEY`, optional base URL / one model for judge + tailor + enricher). Missing key → `UnavailableLlmJudge` / `UnavailableLlmCvTailor` / `UnavailableLlmCvEnricher` (not Fake). Judge/tailor/enricher adapters own short non-secret **LLM Unavailable** reasons (`unavailable_reason()` + `LlmUnavailableError.reason`); `Assistant` only pass-through-caches them for the catalog / Prepare / Enrichment error. Provider/parse/timeout/unexpected failures → Pending or keep prior assessment; Prepare tailor failures stay atomic. Assessment Summary `GET /` uses `load_assessment_summary_catalog` (fast refresh + rows; no Pending judge batch). Catalog assess and Bulk Prepare are process-local **LLM Run**s (`start_catalog_assess_llm_run` / `start_bulk_prepare_llm_run` + `get_llm_run_status` / `stop_llm_run`; at most one in flight; catalog assess until Pending empty with live `k of n`; early-stop on LLM Unavailable; cooperative Stop; fingerprint clear mid-assess aborts). Catalog assess judges up to `JOB_FINDING_ASSISTANT_CATALOG_ASSESS_MAX_CONCURRENCY` postings at once (default 3, clamped 1–10, silent fallback; parent #25) over one shared claim queue, reporting every in-flight identity with finished-only `k`; Stop and LLM Unavailable stay cooperative across all in-flight calls, and assessment saves serialize behind a dedicated lock. Bulk Prepare stays sequential with its single-identity status unchanged. `rejudge_pending_assessments` stays one Pending per call for Crawl / file-change with no LLM Run banner. Failed/skipped heads are deferred so later Pending ids are not starved. No offline/heuristic fallback; no cost meter; no confirm-before-batch; no per-signal parallelism; no backoff/adaptive rate limiting.

## Decided Master CV format (ADR-0007) — as shipped in code

- Master CV is RenderCV YAML on disk; Prepare/tailor never overwrite it; Candidate Snapshot rebuilds from YAML.
- Tailored YAML is rendered to PDF via RenderCV at Prepare (`RenderCvPdfRenderer`; PDF-only failure may leave packet without PDF); ADR-0003 no-fabrication rules still apply with YAML structure preservation.
- Python ≥3.12 required for RenderCV; LaTeX Master CV not retained for v1.

### Master CV Enrichment (ADR-0017)

Implemented through `Assistant` Enrichment session + `LlmCvEnricher` + `/candidate/enrichment` UI (parent #20):

- Freeform → placement suggest/confirm → fixed dimension step flow → editable highlights → confirm write.
- Atomic target-entry patch only; fingerprint refuse if Master CV changed mid-session; ephemeral session.
- Prepare/tailor never write Master CV; Fake enricher tests-only; same env client/model as judge/tailor.

### Tailored CV formatting (ADR-0009)

Implemented at the `LlmCvTailor.tailor` call site (live OpenAI-compatible prompts; Fake scripts results in tests):

- “Higher on the page” = earlier RenderCV YAML order after render; no pixel layout.
- Operation priority and pin rules in the live tailor prompt (ADR-0009); Fake returns scripted YAML + Edit Summary. Docs now prefer reorder + select/omit for apply length from a rich dossier Master; live prompt may lag until Enrichment ships.
- Optional `assistant.pinned_section_order` is stripped before PDF render.

### Gap Report (ADR-0011)

Implemented as part of `Assistant.prepare()` via `LlmCvTailor.tailor` (Fake scripts Gap Report items):

- Built only at Prepare; inputs JD + Snapshot/Master CV + Relevance Evidence (+ HC failures when HC failed); Preferences are not passed to the tailor.
- Empty Gap Report OK; one Prepare: Gap Report then tailor artifacts then PDF attempt.

### Edit Summary (ADR-0012)

Implemented as a first-class packet peer from the same tailor pass (Fake scripts grouped disclosures):

- Review order after Prepare: Gap Report → Edit Summary → Tailored CV / PDF.
- Best-effort checklist shape; Prepare does not fail on incomplete disclosures.

### Prepare flow (ADR-0013)

Implemented through `Assistant.prepare` / `load_preparation_packet_page` / downloads:

- Prepare blocked only while Pending; Closed / Deadline Passed allowed; Override removed.
- HC fail → confirm with reason; re-Prepare → overwrite confirm; otherwise one-click.
- Success packet: Gap Report + Edit Summary + Tailored YAML + PDF at Prepare; assessment not frozen-copied.
- PDF-only failure may leave packet without PDF; tailor/LLM mid-run failure is atomic (prior packet untouched).
- **Tailored YAML validation against RenderCV's schema** (`rendercv_validation.py`, parent #24): before ever rendering, `prepare` validates Tailored YAML against RenderCV's own schema (not a hand-rolled parser), on the metadata-stripped view the renderer also uses. On the first schema failure, one bounded retry: `LlmCvTailor.tailor(..., prior_attempt_errors=...)` with the formatted errors, requesting a corrected Gap Report + Edit Summary + Tailored YAML together. A still-invalid retry follows the same PDF-only-failure carve-out (packet kept, PDF missing) — never a full Prepare failure. `PreparationPacket.pdf_missing_reasons` carries one line per schema problem, or the renderer's own failure message for a generic `PdfRenderError` (no longer discarded). Applies uniformly inside Bulk Prepare's per-posting loop.
- Stale only when Master CV / HC file / Preferences file change; Stale packets stay readable with banner; Crawl detail does not Stale.
- Tool-managed packet store (keyed by Job Posting); download PDF/YAML; Gap Report / Edit Summary UI-only in v1.
- Delete confirms then hard-removes posting + assessment + packet (no trash/undo).
- **Bulk Prepare / Bulk Delete** (catalog checkboxes): shipped via `Assistant.start_bulk_prepare_llm_run` / `bulk_delete` + Assessment Summary UI (parents #22 / #23). Skips Pending / not-`can_prepare` with counts; one combined HC-fail + overwrite confirm (or immediate); Bulk Prepare runs as an LLM Run (sequential — untouched by catalog assess concurrency; stop rest on LLM Unavailable; continue after other Prepare failures). Bulk Delete one confirm listing assessment/packet presence, then sequential cascade. Single-item Prepare/Delete remain on Match Assessment detail.
- **LLM Run** (Assessment Summary): shipped via `Assistant.start_catalog_assess_llm_run` / `start_bulk_prepare_llm_run` / `get_llm_run_status` / `stop_llm_run` + thin poll/Stop UI (parent #23); catalog assess drains until Pending empty (until-empty revisit of ADR-0015) and judges several postings at once (parallel revisit of ADR-0015, parent #25).

## Scaffold slice (issue #2)

Deliver a runnable local shell: FastAPI + Jinja, SQLite `CatalogStore` (minimal schema), fakeable ports, and an empty-catalog Assessment Summary path proven through `Assistant` without Playwright or a real LLM.

## Master CV / Snapshot / constraint files slice (issues #3, #11, #12)

Through `Assistant` and `/candidate` UI:

- Set/update Master CV RenderCV YAML path; never overwrite the Master CV file (`DiskMasterCvStore` reads only).
- Rebuild inspectable Candidate Snapshot from YAML (contact from header fields; education / experience / projects / skills/tools sections as written); not hand-editable.
- Invalid or unreadable YAML → no Snapshot, Relevance stays Pending, clear path/content error (ADR-0014).
- Set Hard Constraints and Preferences plain-text file paths (`DiskConstraintFilesStore`); tool reads only; empty/missing → unknown without judge.
- Public reads use `get_candidate_files()` → `CandidateFilesView` (paths + Snapshot + errors); mutations stay named set/clear (no Master CV clear).
- Structured languages / locations / Gap Tolerance Preferences form removed (ADR-0005).
- LaTeX Master CV is not a supported v1 format.
- Python ≥3.12; `rendercv` + PyYAML dependencies (PDF render is a Prepare concern, shipped with packets).

## Crawl slice (issue #4)

Through `Assistant` and `/crawl` UI, with primary tests on a fake `JobBoardSession`:

- User-Attended Login opens the browser; Crawl starts only when authenticated; no board passwords stored (ADR-0004).
- Crawl Filters (seven groups + three checkboxes + optional Deadline Hardline) default to Active Job on; persist separately from Preferences.
- Incremental Crawl and Full Refresh upsert Job Postings from detail fetch; Hardline skips detail/add after list discovery.
- Narrow filters only add/update; Closing-capable (unfiltered or Active-Job-only) completed syncs may mark absent Open postings Closed.
- Auth-loss mid-Crawl → partial success; keep stored work; do not mark untouched postings Closed.
- Live board: Playwright `JobBoardSession` using selectors from `.scratch/job-board-dom.md`.
- `CrawlPacer` random delays before detail fetches and between list pages, injected into `JobBoardSession` only (tested via recording fake on the board; no real sleep in primary tests).

## Assessment slice (issue #11) — as shipped in code

Through `Assistant` and `/` Assessment Summary UI:

- Assessment Summary shows title, employer, Listing status, Deadline status, Hard Constraint, Preference, Relevance, Preparation Packet presence/Stale (packet absent in this slice).
- Default filter: Open + Deadline Upcoming/Unknown; Closed and Deadline Passed toggleable; sort Pending last, Hard Constraint fail after pass/unknown, Preference then Relevance, sooner deadline (Deadline Unknown last among ties).
- Hard Constraint / Preference / Relevance via fakeable `LlmJudge` with input isolation; empty HC/Prefs → unknown without judge; Prepare unavailable only while Pending (HC fail does not block).
- Fingerprint change (content or path clear) marks **all** assessments Pending; Crawl new/detail-changed starts Pending (Crawl success ≠ assessments done); opportunistic rejudge via `rejudge_pending_assessments` (one Pending); catalog assess via explicit LLM Run.

Prepare / packets / Delete shipped in #13–#14.
