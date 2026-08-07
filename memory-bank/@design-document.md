# Design document — Job Finding Assistant

Authoritative product language: `CONTEXT.md`. Scope ADRs: `docs/adr/0001`–`0014`. Parent spec: GitHub issue #1.

**Docs vs code:** ADRs 0005–0006, 0008, 0010, and 0014 assessment freshness are implemented through `Assistant` (freeform HC/Preferences paths, three LLM signals, Pending-first rejudge). Master CV remains LaTeX until the YAML ticket. Prepare / Gap Report / Edit Summary / packets (ADRs 0007, 0009, 0011–0013) are still ahead of code.

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

Implemented through `Assistant.refresh_candidate_file_state` + `rejudge_pending_assessments`:

- Candidate-file “change” = content or path clear (fingerprint on next check); not path-only; no always-on watcher.
- On change: Snapshot now; **all** assessments Pending (Open and Closed); re-judge opportunistic (catalog UI on load).
- Crawl: catalog sync independent of assessment; new/detail-changed → Pending then opportunistic re-judge; Crawl does not Stale packets (ADR-0013; packets still absent).
- Unreadable Master CV → no Snapshot, Pending + error; unreadable HC/Prefs path → unknown + path error (not Pending).
- Judge failure → leave Pending (never half-assessed final row).

### Hard Constraint rubric (ADR-0010)

Implemented at the `LlmJudge.judge_hard_constraint` call site (Fake in tests; live provider still thin):

- Inputs: Hard Constraints file + Job Posting only (never CV, never Preferences).
- Empty/missing file → unknown without judge; unreadable path → unknown + error.
- Precedence / conservative inference belong in the live judge prompt (ADR-0010); Fake scripts outcomes.

### Judge rubrics (ADR-0008)

Preference and Relevance call sites enforce input isolation (`judge_preference` never sees CV; `judge_relevance` never sees Preferences). Band criteria live in the live judge prompt; Fake scripts bands for tests.

## Decided Master CV format (ADR-0007)

- Master CV and Tailored CV are RenderCV YAML; tool never overwrites the Master CV.
- Tailored YAML may be rendered to PDF via RenderCV; ADR-0003 no-fabrication rules still apply with YAML structure preservation.
- Python ≥3.12 required for RenderCV; LaTeX Master CV not retained for v1.

### Tailored CV formatting (ADR-0009)

Docs ahead of `LlmCvTailor` / `prepare()` implementation:

- “Higher on the page” = earlier RenderCV YAML order after render; no pixel layout.
- Operation priority: reorder → emphasize/rephrase → omit lightly → summary only if already present.
- Reorder from JD required skills/duties + Relevance Evidence (not Preference); Edit Summary discloses cross-role reorders.
- Optional `assistant.pinned_section_order` in Master CV; pinned section ranks win; absent → LLM decides; metadata not rendered on PDF.
- Entry-level pins (individual entries/bullets) are a v1 non-goal; revisit only if section pins prove insufficient.
- Light omission with timeline honesty; gaps stay in Gap Report; JD vocabulary only when evidenced (no inflation/stuffing).

### Gap Report (ADR-0011)

Docs ahead of `prepare()` implementation:

- Built only at Prepare; inputs JD + Snapshot/Master CV + Relevance Evidence (+ HC failures when HC failed); not Preferences.
- Required-first; missing vs partial; fully met omitted; ~5–10 cap; nice-to-haves skipped by default.
- Suggestions = non-fictional user guidance only; tailor must not fill Missing with fiction.
- One Prepare: Gap Report then tailor; empty Gap Report OK; no auto gap-closure loop.

### Edit Summary (ADR-0012)

Docs ahead of `prepare()` / `LlmCvTailor` implementation:

- First-class packet peer; review order after Prepare: Gap Report → Edit Summary → Tailored CV / PDF.
- Same Prepare-pass tailor LLM, checklist-constrained (not a YAML diff); best-effort — Prepare does not fail on incomplete disclosures.
- Required: exhaustive omissions; section / cross-role reorders; summary rewrites; invalid pin names; material rephrases only.
- Grouped bullets (omit empty groups) or “No material edits”; human labels; material rephrases as short before → after gist.
- Never lists JD gaps or Suggestions (Gap Report boundary); no overall bullet cap.

### Prepare flow (ADR-0013)

Docs ahead of `prepare()` implementation:

- Prepare blocked only while Pending; Closed / Deadline Passed allowed; Override removed.
- HC fail → confirm with reason; re-Prepare → overwrite confirm; otherwise one-click.
- Success packet: Gap Report + Edit Summary + Tailored YAML + PDF at Prepare; assessment not frozen-copied.
- PDF-only failure may leave packet without PDF; tailor/LLM mid-run failure is atomic (prior packet untouched).
- Stale only when Master CV / HC file / Preferences file change (content or path clear per ADR-0014); Stale packets stay readable with banner; Crawl detail does not Stale.
- Tool-managed packet store (keyed by Job Posting); download PDF/YAML; Gap Report / Edit Summary UI-only in v1.
- Delete confirms then hard-removes posting + assessment + packet; no trash/undo.

## Scaffold slice (issue #2)

Deliver a runnable local shell: FastAPI + Jinja, SQLite `CatalogStore` (minimal schema), fakeable ports, and an empty-catalog Assessment Summary path proven through `Assistant` without Playwright or a real LLM.

## Master CV / Snapshot / constraint files slice (issue #3 + #11 migration)

Through `Assistant` and `/candidate` UI:

- Set/update Master CV LaTeX path; never overwrite the Master CV file (`DiskMasterCvStore` reads only).
- Rebuild inspectable Candidate Snapshot from Master CV sections (contact, education, experience, projects, skills/tools as written); not hand-editable.
- Set Hard Constraints and Preferences plain-text file paths (`DiskConstraintFilesStore`); tool reads only; empty/missing → unknown without judge.
- Structured languages / locations / Gap Tolerance Preferences form removed (ADR-0005).

Target after YAML ticket: Master CV YAML path; Snapshot from RenderCV YAML.

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
- Fingerprint change (content or path clear) marks **all** assessments Pending; Crawl new/detail-changed starts Pending (Crawl success ≠ assessments done); opportunistic `rejudge_pending_assessments`.

Prepare / packets / Delete / YAML Master CV remain later tickets (#12–#14).
