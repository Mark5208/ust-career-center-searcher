# Prepare flow

When Prepare is allowed, what a Preparation Packet contains, where it is stored, how Stale and Delete work, and failure behavior. Cross-cuts Gap Report ([0011-gap-report-rules.md](0011-gap-report-rules.md)), Edit Summary ([0012-edit-summary-rules.md](0012-edit-summary-rules.md)), Tailored CV formatting ([0009-tailored-cv-formatting.md](0009-tailored-cv-formatting.md)), and assessment signals ([0006-three-assessment-signals.md](0006-three-assessment-signals.md)).

**Status:** accepted

## Override removed

A separate **Override** action is rejected. Hard Constraint fail is a deal-breaker **signal**, not a Prepare gate. The user’s deliberate Prepare (with confirm when failed) is enough friction for a single-user local tool.

## When Prepare is allowed

- **Blocked** only while **Pending**.
- **Allowed** for Closed and Deadline Passed postings (statuses stay visible on the Match Assessment; no extra confirm for those alone).
- Hard Constraint **fail never blocks** Prepare; it requires a **confirm** that quotes the short fail reason.
- First-time Prepare with pass or unknown Hard Constraint: **no confirm** — one click runs Prepare.
- Re-Prepare (packet already exists, including Stale): **confirm** warns that the current packet will be overwritten.

## What Prepare persists

On success, one current Preparation Packet per Job Posting:

- Gap Report
- Edit Summary
- Tailored CV (RenderCV YAML)
- PDF rendered via RenderCV during Prepare (not lazily on download)

Match Assessment is **not** frozen into the packet; viewing the packet shows the **current** Match Assessment. Review order after Prepare: Gap Report → Edit Summary → Tailored CV / PDF.

If tailor artifacts succeed but PDF rendering fails: keep YAML + Gap Report + Edit Summary, surface that the PDF is missing; do not discard the whole prepare.

## Stale

A packet is Stale only when the **Master CV**, **Hard Constraints file**, or **Preferences file** changes after it was produced. “Change” includes **content** change and **path clear/unset** (fingerprint on the next check — see [0014-assessment-freshness-and-change-detection.md](0014-assessment-freshness-and-change-detection.md)). Crawl updates to Job Posting detail make the Match Assessment Pending for re-judge but do **not** auto-Stale or auto-regenerate the packet.

Stale packets remain **fully readable** (Gap Report, Edit Summary, Tailored YAML, PDF if present) with a clear Stale banner. No auto-regeneration. Re-Prepare is the only refresh path; downloads are not locked.

## Failure atomicity

Prepare replaces the prior packet **atomically**. If the tailor/LLM fails mid-run, leave any previous packet untouched (including if Stale); do not write a half-packet. First-time failure → no packet. Retry is explicit.

## Tool-managed store

Preparation Packets live in a **tool-managed local store** keyed by Job Posting — not beside the Master CV, and not in a user-chosen packets folder. Master CV, Hard Constraints file, and Preferences file remain user-chosen paths; packet outputs are owned by the tool. The UI is the primary way to read Gap Report and Edit Summary.

## Downloads

From the packet view, the user may **download Tailored PDF** and **download Tailored YAML** (the apply artifacts). Gap Report and Edit Summary are first-class in the UI only in v1 (no separate file-download requirement; copying from the page is enough). No bulk “export all packets” and no required Reveal-in-Finder in v1.

## Delete

**Delete** always requires a **confirm** that names the Job Posting, Match Assessment, and Preparation Packet (if any). On confirm, hard-remove all of them from the catalog and tool-managed store. No trash or undo in v1. Match Assessment detail keeps single-item Delete.

## Bulk Prepare and Bulk Delete (Assessment Summary catalog)

Catalog row checkboxes + select-all (every **currently visible** row under active filters/toggles, including Pending). Catalog does **not** show per-row Prepare/Delete; those remain on Match Assessment detail. Empty selection → Bulk actions are no-ops with a short message.

### Bulk Prepare

- Eligible set = selected rows where Prepare is allowed (`can_prepare`); **skip** Pending and other not-ready rows; report prepared / skipped / failed / stopped counts.
- **Confirm:** one combined page listing every eligible posting that needs Hard Constraint fail confirm (quote each short fail reason) and every eligible posting that would overwrite an existing packet. If none of the eligible set needs confirm, run immediately (same spirit as single first-time Prepare).
- Run **sequentially**. Per-posting packet atomicity unchanged (this ADR’s Failure atomicity).
- On **LLM Unavailable** mid-batch: keep successes; **stop** the rest of the batch.
- On other per-posting Prepare failures: keep successes; **record** the failure; **continue** with remaining eligible postings.
- **No hard batch-size cap**; no spend meter.

### Bulk Delete

- One confirm page listing **every** selected posting (identity) and whether each has a Match Assessment / Preparation Packet.
- On confirm, hard-delete the selection **sequentially** with the same cascade as single Delete. No trash or undo.
- **No hard batch-size cap**.
