# Grill outcome — Master CV Enrichment

**Date:** 2026-08-11  
**Promoted from:** [#17](https://github.com/Mark5208/ust-career-center-searcher/issues/17) (parking lot; not the parent)  
**Parent issue:** [#20](https://github.com/Mark5208/ust-career-center-searcher/issues/20) (`ready-for-agent`)

## Domain lock (morning)

| # | Decision | Answer |
|---|----------|--------|
| 1 | Scope | Not finer pins; theme is **Master CV Enrichment** (content depth) |
| 2 | Authorship | Tool proposes; user confirms write; never silent mid-Prepare enrich |
| 3 | Master CV role | Full **source dossier** (may be long); apply-sized output is Tailored CV only |
| 4 | When | Standalone user-started flow; not inside Prepare/Crawl |
| 5 | JD coupling | Job-agnostic dimensional interview; JD shaping stays in Tailored CV / Gap Report |
| 6 | Storage | Confirmed facts → ordinary entry highlights in Master CV YAML (one source of truth) |
| 7 | Tailored omit | Working rule: **aggressive select-from-dossier**; record prior ADR-0009 **omit lightly** for revisit after real Prepare volume |
| 8 | Entry scope | Experience + projects (+ education if chosen); skills lists not grilled |
| 9 | Interview shape | Fixed dimensions + short follow-ups → draft → editable full highlights list → confirm |
| 10 | Name | **Master CV Enrichment** |
| 11 | Write rule | Master CV write allowed **only** on Enrichment confirm; Prepare/tailor never write Master CV |
| 12 | Pins theme | Stay parked on #17 as “Entry/bullet pins (ADR-0009)” — separate from Enrichment |
| 13 | First capture | Docs/tracker only |

## Implementation lock (afternoon)

| # | Decision | Answer |
|---|----------|--------|
| 14 | UI home | Dedicated Enrichment UI linked from Candidate files; Candidate keeps Snapshot inspect (no YAML editor / Master PDF viewer in this parent) |
| 15 | Start | Freeform description first — not limited to a pre-picked enrichable-entry list |
| 16 | Placement | LLM **suggests** target (existing entry or new under existing section); user **must confirm** placement before dimension steps |
| 17 | New entries | Allowed under an existing section only; user confirms identity (employer/title/dates or project name/dates); no new section types |
| 18 | Dimension UX | Short **step flow** (one step per fixed dimension + optional follow-up), not open chat |
| 19 | Session durability | Ephemeral for active server/browser session only; no durable resume across restarts; leave mid-flow may discard |
| 20 | Conflict | Fingerprint Master CV at session start; on confirm if changed → **refuse write**, restart Enrichment |
| 21 | Session cardinality | One session = one confirmed placement = one Master CV write |
| 22 | LLM Unavailable | Block Enrichment LLM steps with short non-secret reason; keep ephemeral answers for retry; no heuristic draft |
| 23 | LLM port | Separate **`LlmCvEnricher`** (same env client/model as ADR-0015); do not overload `LlmCvTailor` |
| 24 | Write patch | Atomic temp→replace; patch **only** target entry highlights (+ identity if new); leave design / pins / other entries untouched |

**Fixed dimensions:** problem/context; technical work; collaboration/leadership; domain/impact; outcomes/metrics. Skip empty; at most one clarifying follow-up per dimension.

**Docs:** `CONTEXT.md`; ADR-0017; ADR-0009 (select-from-dossier; omit lightly for revisit); ADR-0007 write-rule note.
