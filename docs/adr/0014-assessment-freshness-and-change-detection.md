# Assessment freshness and change detection

How the tool detects Master CV / Hard Constraints / Preferences “change,” when Match Assessments become Pending, how re-judge relates to Crawl success, unreadable-file and judge-failure outcomes, and why packets are not Stale on Crawl detail updates. Stale packet rules remain in [0013-prepare-flow.md](0013-prepare-flow.md).

**Status:** accepted

## What counts as a candidate-file change

A change to the Master CV, Hard Constraints file, or Preferences file means **content** change or **path clear/unset**, not merely re-setting the same path. Detect via a file fingerprint on the next rebuild/Stale check (e.g. app use, Crawl complete, Prepare, or explicit refresh). No always-on file watcher in v1.

**Rejected:** Path-only change detection (edits in another editor would never refresh Snapshot, assessments, or Stale).

## Pending-first, then async re-judge

On such a change: rebuild the Candidate Snapshot immediately (when the Master CV changed); mark **all** existing Match Assessments **Pending** (Open and Closed); mark existing Preparation Packets **Stale**. Re-judge asynchronously or opportunistically — do not block the catalog UI on a full synchronous sweep.

**Rejected:** Blocking eager re-judge of the whole catalog before the list is usable. **Rejected:** Rebuilding only Open assessments (Closed/Passed rows could show outdated signals while Prepare remains allowed).

## Crawl vs assessment completion

Crawl persists/updates Job Postings immediately. New or detail-changed postings start **Pending** (keep the prior assessment only when detail did not change). Re-judge async afterward. Crawl success means catalog sync succeeded, not that every Match Assessment finished.

Crawl detail updates do **not** auto-Stale or auto-regenerate Preparation Packets ([0013-prepare-flow.md](0013-prepare-flow.md)). JD drift is visible via the refreshed assessment; re-Prepare stays deliberate.

**Rejected:** Stale-on-Crawl (noisy board edits would nag). **Rejected:** Treating “Crawl finished” as “all assessments finished.”

## Unreadable or invalid files

- **Master CV** unreadable or invalid → no usable Candidate Snapshot; Relevance stays **Pending**; surface a clear error; do not invent Snapshot content.
- **Hard Constraints / Preferences** path set but file missing or unreadable → that signal is **unknown** without a judge call (not Pending on that signal alone); surface a path/read error. Empty-but-readable files remain quiet unknown.

## Judge failure

If the LLM judge fails or is unavailable, required missing judgments are **Pending**. Do not persist a half-assessed row as final: keep the previous complete assessment (if any) or leave/mark Pending until a full successful pass for all required signals. Never invent bands or outcomes. Prepare stays blocked while Pending.
