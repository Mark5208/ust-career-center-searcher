# Grill outcome — Unify Crawl pacing behind JobBoardSession

**Date:** 2026-08-10  
**Promoted from:** `/improve-codebase-architecture` candidate (“Unify Crawl pacing…”)  
**Kind:** Architecture deepen only — not a product/v2 theme  
**Glossary:** No new `CONTEXT.md` terms (**Crawl** / **Job Board** unchanged; delay ranges and Crawl product policy unchanged)

| # | Decision | Answer |
|---|----------|--------|
| 1 | Focus | Unify Crawl pacing behind `JobBoardSession`; keep current detail/page delay ranges and Crawl product behavior |
| 2 | Where pauses live | Inside `JobBoardSession`: page pause stays in `discover_job_list`; detail pause moves into `fetch_job_detail`; `Assistant` drops `CrawlPacer` entirely |
| 3 | Pacer shape | `CrawlPacer` remains injectable on live + Fake `JobBoardSession` only (not inlined into adapters) |
| 4 | Fake | Optional `crawl_pacer` (default NoOp); call `pause_before_detail` on each `fetch_job_detail`; no Fake multi-page / no Fake next-page pause this deepen; move Assistant detail-pause tests onto board-injected `FakeCrawlPacer` |
| 5 | Docs | Sync `memory-bank/@architecture.md` + `memory-bank/@design-document.md` only; no ADR; no `CONTEXT.md` |
| 6 | Build | Single-session `/implement` (TDD at `JobBoardSession` / Assistant Crawl seam); no tickets |

## Out of scope

- Crawl Filters / Closing-capable / auth-loss product rules
- Changing detail (1–3s) or next-page (0.5–1.5s) delay ranges
- Fake multi-page discovery / Fake `pause_before_next_page`
- New ADR or glossary terms

## Build path

Single-session `/implement` (TDD at `JobBoardSession` / Assistant Crawl seam). No `/to-tickets` breakdown.
