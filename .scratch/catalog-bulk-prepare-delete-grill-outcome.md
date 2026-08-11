# Grill outcome — Catalog bulk Prepare / Delete

**Date:** 2026-08-11  
**Promoted from:** [#17](https://github.com/Mark5208/ust-career-center-searcher/issues/17) (parking lot; not the parent)  
**Parent issue:** [#22](https://github.com/Mark5208/ust-career-center-searcher/issues/22) (`ready-for-agent`)

| # | Decision | Answer |
|---|----------|--------|
| 1 | Scope | Assessment Summary catalog: checkboxes + select-all + **Bulk Prepare** + **Bulk Delete**; not bulk export / Reveal-in-Finder |
| 2 | Selection | All visible rows selectable (incl. Pending); select-all = currently shown under filters/toggles |
| 3 | Bulk Prepare eligibility | Skip Pending / not-`can_prepare`; report counts |
| 4 | Bulk Prepare confirm | One combined confirm listing HC-fail reasons + overwrite warnings; if none need confirm, run immediately |
| 5 | Bulk Delete confirm | One confirm listing every selected posting + whether assessment/packet exist |
| 6 | Mid-batch Prepare | Keep successes; **stop rest** on LLM Unavailable; on other Prepare failures record + **continue**; per-packet atomicity unchanged |
| 7 | Catalog row actions | Remove per-row Prepare/Delete; detail page keeps single Prepare/Delete |
| 8 | Cap | No hard batch-size cap; sequential; no spend meter |
| 9 | Docs | CONTEXT terms + ADR-0013 bulk section; parent `ready-for-agent` |

**Docs:** `CONTEXT.md`; ADR-0013 revised.
