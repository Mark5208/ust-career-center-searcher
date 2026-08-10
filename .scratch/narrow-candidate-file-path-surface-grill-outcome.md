# Grill outcome — Narrow candidate-file path surface on Assistant

**Date:** 2026-08-10  
**Promoted from:** `/improve-codebase-architecture` candidate #5 (after freshness concentrate + Crawl pacing unify)  
**Kind:** Architecture deepen only — not a product/v2 theme  
**Glossary:** No new `CONTEXT.md` terms (Master CV / Hard Constraints file / Preferences file / Candidate Snapshot unchanged; ADR-0014 product rules unchanged)

| # | Decision | Answer |
|---|----------|--------|
| 1 | Focus + kind | Narrow candidate-file path surface on Assistant; architecture deepen only; ADR-0014 / product path semantics stay |
| 2 | Target shape | One `get_candidate_files()` → `CandidateFilesView` (three paths + Candidate Snapshot + errors); named set/clear mutations stay (no Master CV clear); store ports unchanged |
| 3 | Old getters | Remove all five public getters from `Assistant` + `SupportsAssistantUi` (`get_master_cv_path`, `get_hard_constraints_path`, `get_preferences_path`, `get_candidate_snapshot`, `get_candidate_file_errors`) |
| 4 | Naming / glossary | Application DTO + method only; no new `CONTEXT.md` term |
| 5 | Docs | Sync `memory-bank/@architecture.md` (+ design-doc if needed); no new ADR; no ADR-0014 rewrite; no `CONTEXT.md` |
| 6 | Build | Single-session `/implement` (TDD at `Assistant` + `SupportsAssistantUi` / `/candidate` seam); no tickets |

## Out of scope

- ADR-0014 change / Pending / Stale / fingerprint product rules
- Collapsing mutations into one configure / kind-based setter
- Adding Master CV clear
- Changing store port shapes (`MasterCvStore` / `ConstraintFilesStore`)
- Changing `/candidate` HTTP route shape beyond reading the view (POSTs stay named set/clear)
- New glossary term for a “Candidate Files” aggregate

## Build path

Single-session `/implement` (TDD at `Assistant` + UI seam). No `/to-tickets` breakdown.
