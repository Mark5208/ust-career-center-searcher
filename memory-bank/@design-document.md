# Design document — Job Finding Assistant

Authoritative product language: `CONTEXT.md`. Scope ADRs: `docs/adr/0001`–`0015`. Parent spec: GitHub issue #1.

**Docs vs code:** ADRs 0005–0015 Prepare/assessment/CV/LLM slices through `Assistant` are implemented for Assessment Summary, Match Assessment detail (`/jobs/{id}` with Relevance Evidence + HC/Preference reasons), Master CV Snapshot, constraint files, Crawl, Preparation Packets (Gap Report / Edit Summary / Tailored YAML / PDF / Stale), Delete cascade, and live OpenAI-compatible `LlmJudge` / `LlmCvTailor` (env key; Unavailable when missing; Fake only in tests). Accordion / richer Match Assessment nav remains out of v1.

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

Implemented through `Assistant.refresh_candidate_file_state` plus opportunistic rejudge (`load_assessment_summary_catalog` on Assessment Summary load; `rejudge_pending_assessments` after Crawl / file change):

- Candidate-file “change” = content or path clear (fingerprint on next check); not path-only; no always-on watcher.
- On change: Snapshot now; **all** assessments Pending (Open and Closed); re-judge opportunistic (catalog UI via `load_assessment_summary_catalog` on load).
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

### LLM runtime (ADR-0015)

`build_default_assistant` wires `llm_runtime.build_llm_ports` from env (`JOB_FINDING_ASSISTANT_LLM_API_KEY`, optional base URL / one model for judge + tailor). Missing key → `UnavailableLlmJudge` / `UnavailableLlmCvTailor` (not Fake). Provider/parse/timeout failures → Pending or keep prior assessment; Prepare tailor failures stay atomic with a short non-secret **LLM Unavailable** reason on the catalog (and Prepare error). Assessment Summary `GET /` uses `load_assessment_summary_catalog` (one refresh + at most five Pending rejudge attempts + progress banner; early-stop that load on LLM Unavailable); `rejudge_pending_assessments` stays one Pending per call for Crawl / file-change. Failed/skipped heads are deferred so later Pending ids are not starved. No offline/heuristic fallback; no cost meter; no confirm-before-batch; no LLM batch pacing beyond sequential in-request calls.

## Decided Master CV format (ADR-0007) — as shipped in code

- Master CV is RenderCV YAML on disk; tool never overwrites it; Candidate Snapshot rebuilds from YAML.
- Tailored YAML is rendered to PDF via RenderCV at Prepare (`RenderCvPdfRenderer`; PDF-only failure may leave packet without PDF); ADR-0003 no-fabrication rules still apply with YAML structure preservation.
- Python ≥3.12 required for RenderCV; LaTeX Master CV not retained for v1.

### Tailored CV formatting (ADR-0009)

Implemented at the `LlmCvTailor.tailor` call site (live OpenAI-compatible prompts; Fake scripts results in tests):

- “Higher on the page” = earlier RenderCV YAML order after render; no pixel layout.
- Operation priority and pin rules in the live tailor prompt (ADR-0009); Fake returns scripted YAML + Edit Summary.
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

Implemented through `Assistant.prepare` / `get_preparation_packet` / downloads:

- Prepare blocked only while Pending; Closed / Deadline Passed allowed; Override removed.
- HC fail → confirm with reason; re-Prepare → overwrite confirm; otherwise one-click.
- Success packet: Gap Report + Edit Summary + Tailored YAML + PDF at Prepare; assessment not frozen-copied.
- PDF-only failure may leave packet without PDF; tailor/LLM mid-run failure is atomic (prior packet untouched).
- Stale only when Master CV / HC file / Preferences file change; Stale packets stay readable with banner; Crawl detail does not Stale.
- Tool-managed packet store (keyed by Job Posting); download PDF/YAML; Gap Report / Edit Summary UI-only in v1.
- Delete confirms then hard-removes posting + assessment + packet (no trash/undo).

## Scaffold slice (issue #2)

Deliver a runnable local shell: FastAPI + Jinja, SQLite `CatalogStore` (minimal schema), fakeable ports, and an empty-catalog Assessment Summary path proven through `Assistant` without Playwright or a real LLM.

## Master CV / Snapshot / constraint files slice (issues #3, #11, #12)

Through `Assistant` and `/candidate` UI:

- Set/update Master CV RenderCV YAML path; never overwrite the Master CV file (`DiskMasterCvStore` reads only).
- Rebuild inspectable Candidate Snapshot from YAML (contact from header fields; education / experience / projects / skills/tools sections as written); not hand-editable.
- Invalid or unreadable YAML → no Snapshot, Relevance stays Pending, clear path/content error (ADR-0014).
- Set Hard Constraints and Preferences plain-text file paths (`DiskConstraintFilesStore`); tool reads only; empty/missing → unknown without judge.
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
- `CrawlPacer` random delays before detail fetches and between list pages (tested via recording fake; no real sleep in primary tests).

## Assessment slice (issue #11) — as shipped in code

Through `Assistant` and `/` Assessment Summary UI:

- Assessment Summary shows title, employer, Listing status, Deadline status, Hard Constraint, Preference, Relevance, Preparation Packet presence/Stale (packet absent in this slice).
- Default filter: Open + Deadline Upcoming/Unknown; Closed and Deadline Passed toggleable; sort Pending last, Hard Constraint fail after pass/unknown, Preference then Relevance, sooner deadline (Deadline Unknown last among ties).
- Hard Constraint / Preference / Relevance via fakeable `LlmJudge` with input isolation; empty HC/Prefs → unknown without judge; Prepare unavailable only while Pending (HC fail does not block).
- Fingerprint change (content or path clear) marks **all** assessments Pending; Crawl new/detail-changed starts Pending (Crawl success ≠ assessments done); opportunistic rejudge via `load_assessment_summary_catalog` / `rejudge_pending_assessments`.

Prepare / packets / Delete shipped in #13–#14.
