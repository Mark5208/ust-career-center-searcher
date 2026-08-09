# V1 finish checklist

Grill outcome for closing parent [#1](https://github.com/Mark5208/ust-career-center-searcher/issues/1). Glossary: `CONTEXT.md`. Scope: ADRs 0001–0015.

## Resolved decisions

1. **Definition of done:** v1 is finished only when (a) automated suite is green, (b) human live-path smoke passes, (c) parent #1 + memory-bank docs tell the truth about shipped code, (d) Out of Scope stays frozen. Ticket-complete alone is not enough.
2. **Acceptance gate:** one short human smoke covering Crawl → assess → Match Assessment detail → Prepare/PDF → Stale → Delete (details below).
3. **Doc truth blocks close:** yes — stale “remaining work” / “PDF still ahead” language must be corrected before close.
4. **Scope freeze:** no last-minute features; do not reopen accordion, Override, Fake-as-live, cost meter, offline scorer, LaTeX Master CV, multi-board, auto-apply, or other Out of Scope items. Re-grill domain only if live prompts expose a rubric conflict with ADRs 0008–0012.

## Prerequisites

- Python ≥3.12, `pip install -e ".[dev]"`, `playwright install chromium`
- RenderCV CLI available for PDF (same environment as the app)
- Env in the launch shell (see `docs/llm-api-key-security.md`):
  - `JOB_FINDING_ASSISTANT_LLM_API_KEY`
  - optional `JOB_FINDING_ASSISTANT_LLM_BASE_URL` / `JOB_FINDING_ASSISTANT_LLM_MODEL` (required pair when not using OpenAI)
- Real Master CV (RenderCV YAML), Hard Constraints file, Preferences file

---

## Step 1 — Automated regression

Run the primary suite (Fake LLM / Fake board; no live credentials required).

**Test:** `pytest` exits 0.

---

## Step 2 — Doc truth sync

Correct any remaining “still ahead” / “remaining: live LLM + detail page” claims so they match shipped code:

- Parent [#1](https://github.com/Mark5208/ust-career-center-searcher/issues/1) **Docs vs code** + Implementation Decisions “Remaining” lines
- [`memory-bank/@design-document.md`](../memory-bank/@design-document.md) Master CV / PDF line
- Spot-check [`memory-bank/@architecture.md`](../memory-bank/@architecture.md) still matches runtime (live LLM, `/jobs/{id}`, PDF renderer)

**Test:** Searching the repo for `Still ahead: live LLM` and `PDF via RenderCV at Prepare (still ahead)` returns no hits in issue #1 body or memory-bank. Architecture still describes `RenderCvPdfRenderer` and `llm_runtime`.

---

## Step 3 — Live smoke: launch + candidate files

1. Export LLM env (same shell), start `job-finding-assistant`
2. Open `/candidate`; set Master CV, Hard Constraints, Preferences paths
3. Confirm Candidate Snapshot is inspectable; no path/read errors for readable files

**Test:** Catalog does **not** show `LLM Unavailable: API key not configured`. Snapshot sections appear from the Master CV. Empty HC/Prefs yield unknown (not Pending) for those signals once assessed.

---

## Step 4 — Live smoke: User-Attended Login + Crawl

1. Open `/crawl`; run User-Attended Login; complete DUO in the opened browser
2. Keep default Crawl Filters (Active Job on) or a known-narrow filter
3. Run incremental Crawl; wait for completion

**Test:** Assessment Summary (`/`) shows at least one Open Job Posting from the board. Crawl success is reported even if rows are still Pending. No board password is stored in the app.

---

## Step 5 — Live smoke: assessment + detail

1. Refresh `/` until at least one row leaves Pending (one Pending posting per load per ADR-0015)
2. Open `/jobs/{id}` for an assessed posting

**Test:** Detail shows Hard Constraint + reason, Preference + reason, Relevance, Relevance Evidence (about 3–7 pairs), Prepare and Delete. No accordion / Override. Pending rows cannot Prepare.

---

## Step 6 — Live smoke: Prepare packet

1. Prepare one non-Pending posting (confirm if Hard Constraint fail or re-Prepare)
2. Open packet view; review Gap Report → Edit Summary → downloads
3. Download Tailored YAML and PDF

**Test:** Packet has Gap Report, Edit Summary, Tailored YAML. PDF downloads when RenderCV succeeds; if PDF-only failure, YAML/Gap/Edit remain and UI says PDF missing. Master CV file on disk is unchanged. No fabricated employers/dates/titles/skills in a spot-check of Tailored YAML vs Master CV.

---

## Step 7 — Live smoke: Stale + Delete

1. Edit Master CV content (or clear/reset a constraint path per ADR-0014); return to catalog
2. Confirm assessments go Pending and the packet shows Stale (readable under banner)
3. Delete one posting via confirm that names posting / assessment / packet

**Test:** Stale banner present; packet still readable; Crawl was not required to Stale. After Delete, posting, assessment, and packet are gone with no undo.

---

## Step 8 — Close v1

Only after Steps 1–7 pass:

1. Comment on #1 with smoke date + any residual notes (prompt quirks that did **not** change glossary/ADRs)
2. Close #1
3. Leave Out of Scope items for a future milestone; do not open “finish” tickets for them

**Test:** `gh issue list --state open` shows no open Part-of-#1 children; #1 is closed. No new issue filed that contradicts #1 Out of Scope under the guise of finishing v1.

---

## Explicitly not required to finish v1

- Accordion / richer Match Assessment nav
- Separate stored Hard Constraint / Preference Evidence lists
- LLM cost meter, batch pacing, confirm-before-rejudge
- Offline / local-model / heuristic scorers; Fake in the normal app path
- Multi-provider LLM UI or keys in SQLite/UI
- Auto-apply, multi-board, LaTeX Master CV, bulk export, Reveal-in-Finder
- Always-on file watcher for candidate files
