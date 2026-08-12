# Grill outcome — Tailored YAML validation against RenderCV's schema

**Date:** 2026-08-12
**Trigger:** `/grill-with-docs` on "how RenderCV can incorporate into our tool in depth"
**Parent issue:** [#24](https://github.com/Mark5208/ust-career-center-searcher/issues/24) (`ready-for-agent`)

| # | Decision | Answer |
|---|----------|--------|
| 1 | Theme | Tailored CV validation against RenderCV's real schema at Prepare time only |
| 2 | Scope vs Master CV parsing | Tailored CV / Prepare only; Candidate Snapshot's lenient parser (`candidate_snapshot.py`) is untouched (separate future decision — touches ADR-0014 Pending/invalid-Master-CV rules) |
| 3 | Validator | RenderCV's own `rendercv.schema.rendercv_model_builder.build_rendercv_dictionary_and_model(yaml_text)` (confirmed present in the pinned `rendercv==2.8`) — not a hand-rolled parser |
| 4 | Where the call sits | Distinct step in `Assistant.prepare()`, right after `LlmCvTailor.tailor()` returns, before `PdfRenderer.render_pdf()` is ever invoked; `PdfRenderer` stays render-only |
| 5 | New module | `rendercv_validation.py` (peer of `pdf_renderer.py` / `candidate_snapshot.py`) wraps the validator, catches `RenderCVUserValidationError`, formats each `RenderCVValidationError` into a short `schema.location.path: message` line |
| 6 | Failure outcome | Same PDF-only-failure carve-out as today (ADR-0013) — keep Gap Report + Edit Summary + Tailored YAML, mark PDF missing; **not** a full Prepare failure |
| 7 | Retry | One automatic retry: `tailor()` called again with the same inputs plus attempt 1's formatted errors, before falling back to the carve-out |
| 8 | Port shape | Reuse `LlmCvTailor.tailor()` with one new optional parameter (e.g. `prior_attempt_errors: list[str] \| None = None`) — no new `repair()` method; Fake and live tailors share one shape |
| 9 | Retry output consistency | Whichever attempt is kept (retry if valid, otherwise the retry's own failed attempt) supplies Gap Report + Edit Summary + Tailored YAML together — never mixed across attempts |
| 10 | Bulk Prepare | Retry applies uniformly everywhere `prepare()` runs, including per-posting inside Bulk Prepare's LLM Run loop — accepted bounded extra cost |
| 11 | Surfaced detail | Full list of validation problems (one line per error), not a collapsed single-line reason; `PreparationPacket` gets a new `pdf_missing_reasons: tuple[str, ...]` field (also used for the existing generic renderer-failure message, previously discarded) |
| 12 | Docs | Amend ADR-0013 (Failure atomicity / What Prepare persists) — no new ADR number, same pattern as ADR-0015's until-empty revisit; light touch to CONTEXT.md's Preparation Packet entry |
| 13 | Build | Not built this session — spec published as a GitHub issue for a later `/implement` session |

**Docs:** ADR-0013 amended (new "Tailored YAML validation against RenderCV's schema" subsection + Considered options); CONTEXT.md Preparation Packet entry amended. No new ADR number.
