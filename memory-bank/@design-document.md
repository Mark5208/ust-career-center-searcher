# Design document — Job Finding Assistant

Authoritative product language: `CONTEXT.md`. Scope ADRs: `docs/adr/0001`–`0014`. Parent spec: GitHub issue #1.

**Docs vs code:** ADRs 0005–0014 and the current `CONTEXT.md` describe the confirmed assessment and Master CV model. The running code still implements the older structured Preferences + LaTeX Master CV + Relevance-only soft band (issue #3–#5 slices). Do not treat the code as the glossary source until a later implementation pass.

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

Docs ahead of fingerprint / Pending-first implementation:

- Candidate-file “change” = content or path clear (fingerprint on next check); not path-only; no always-on watcher.
- On change: Snapshot now; **all** assessments Pending (Open and Closed); packets Stale; re-judge async/opportunistic.
- Crawl: catalog sync independent of assessment; new/detail-changed → Pending then async re-judge; Crawl does not Stale packets (ADR-0013).
- Unreadable Master CV → no Snapshot, Pending + error; unreadable HC/Prefs path → unknown + path error (not Pending).

### Hard Constraint rubric (ADR-0010)

Docs ahead of freeform Hard Constraint `LlmJudge` implementation:

- Inputs: Hard Constraints file + Job Posting only (never CV, never Preferences).
- Precedence: fail if any clear violation; else unknown if any applicable line unknown; else pass.
- Conservative inference (under-fail); soft “prefer…” misfiled in HC does not fail.
- Short reason always; light HC↔posting Evidence on fail/unknown. Fail/unknown do not block Prepare (fail confirms per ADR-0013).

### Judge rubrics (ADR-0008)

Preference and Relevance band criteria (docs ahead of `LlmJudge` implementation):

- Strict input isolation: Preference never sees the CV; Relevance never sees the Preferences file.
- Preference: coverage of likes/avoids; hierarchy if written; posting silence → unknown (leans Mixed); clear avoid → Weak; short reason output.
- Relevance: required-first; Evidence pairs (~3–7); never invent CV content; conservative adjacency (Mixed ceiling unless core evidenced); vague JD → Mixed.

**Non-goal this version:** A guided chatbot that grills the user to clarify experience before judging. Rubrics assume the user already wrote clear Master CV and Preferences text.

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

## Master CV / Snapshot / Preferences slice (issue #3) — as shipped in code

Through `Assistant` and `/candidate` UI (legacy until migration):

- Set/update Master CV LaTeX path; never overwrite the Master CV file (`DiskMasterCvStore` reads only).
- Rebuild inspectable Candidate Snapshot from Master CV sections (contact, education, experience, projects, skills/tools as written); not hand-editable.
- Persist structured Preferences (languages with optional level, locations, Gap Tolerance) in SQLite; no Crawl Filters on Preferences.

Target after migration: Master CV YAML path; Hard Constraints file path; Preferences file path; Snapshot from RenderCV YAML.

## Crawl slice (issue #4)

Through `Assistant` and `/crawl` UI, with primary tests on a fake `JobBoardSession`:

- User-Attended Login opens the browser; Crawl starts only when authenticated; no board passwords stored (ADR-0004).
- Crawl Filters (seven groups + three checkboxes + optional Deadline Hardline) default to Active Job on; persist separately from Preferences.
- Incremental Crawl and Full Refresh upsert Job Postings from detail fetch; Hardline skips detail/add after list discovery.
- Narrow filters only add/update; Closing-capable (unfiltered or Active-Job-only) completed syncs may mark absent Open postings Closed.
- Auth-loss mid-Crawl → partial success; keep stored work; do not mark untouched postings Closed.
- Live board: Playwright `JobBoardSession` using selectors from `.scratch/job-board-dom.md`.
- `CrawlPacer` random delays before detail fetches and between list pages (tested via recording fake; no real sleep in primary tests).

## Assessment slice (issue #5) — as shipped in code

Through `Assistant` and `/` Assessment Summary UI (legacy soft band until migration):

- Assessment Summary shows title, employer, Listing status, Deadline status, overall Hard Constraint outcome, Relevance, Preparation Packet presence/Stale (packet absent in this slice).
- Default filter: Open + Deadline Upcoming/Unknown; Closed and Deadline Passed toggleable; sort Relevance then sooner deadline; Hard Constraint fail after pass/unknown; Pending last.
- Hard Constraints (language, location, Gap Tolerance) are rule-based with short reasons (`hard_constraints`); pure-rule tests allowed at that seam.
- Relevance Strong/Mixed/Weak (+ Evidence) via `LlmJudge` (fakeable); Match Assessment stays Pending when the judge is unavailable; Prepare unavailable while Pending.
- Rebuild Match Assessments for new/changed Crawl detail, and for Open postings when Master CV path or Preferences change.

Target after migration: show Preference + Relevance; LLM Hard Constraint from freeform file; sort Preference then Relevance (Deadline Unknown last among ties); on Master CV / HC / Preferences change mark **all** assessments Pending then async re-judge (ADR-0014); Crawl Pending-first; judge bands per ADR-0008 (ADR-0005, ADR-0006).
