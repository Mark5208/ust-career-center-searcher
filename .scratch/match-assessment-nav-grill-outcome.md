# Grill outcome — Match Assessment nav / signal sections

**Date:** 2026-08-11  
**Promoted from:** [#17](https://github.com/Mark5208/ust-career-center-searcher/issues/17) (parking lot; not the parent)  
**Parent issue:** [#21](https://github.com/Mark5208/ust-career-center-searcher/issues/21) (`ready-for-agent`)

| # | Decision | Answer |
|---|----------|--------|
| 1 | Problem | In-page organization on Match Assessment detail only (not cross-posting prev/next) |
| 2 | Toggle model | Independently collapsible **signal sections** (not exclusive accordion) |
| 3 | Default | All three sections **expanded** on first load; collapse is opt-in; no persist open/closed |
| 4 | Summary | Non-sticky **signal summary** strip (bands/outcomes + reasons) with anchors to sections |
| 5 | Actions | Prepare / Delete stay after the sections (unchanged placement intent) |
| 6 | Bulk ops | Catalog checkbox multi Prepare/Delete **out of scope** — park separately on #17 |
| 7 | Packet page | Unchanged — compact strip + link to Match Assessment (ADR-0016) |
| 8 | Language | **Signal sections** + **signal summary**; `_Avoid_: accordion` (exclusive implication) |
| 9 | ADR | None — presentation-only; Evidence rules stay ADR-0016 |
| 10 | Capture | Docs/tracker; parent `ready-for-agent` for single UI `/implement` |

**Docs:** `CONTEXT.md` Match Assessment updated. No new ADR.
