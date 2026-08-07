# Job Finding Assistant

Personal local tool that crawls the HKUST Job Board, assesses fit against one user's Master CV, Hard Constraints, and Preferences, and prepares a Tailored CV for selected Job Postings.

## Language

### Job catalog

**Job Board**:
The HKUST Career Center job board — the sole source of Job Postings in this context.
_Avoid_: career site, portal, multiple boards

**Job Posting**:
One job listing from the Job Board, stored in the local catalog from its detail page (structured fields plus text for Evidence), with listing and deadline facts.
_Avoid_: job, role, vacancy, opening (when referring to the stored listing)

**User-Attended Login**:
The tool opens the browser; the user completes Job Board login (including DUO); the user then starts a Crawl. No board passwords are stored.
_Avoid_: auto-login, credentials file, stored session password

**Crawl Filters**:
User-chosen Job Board search criteria applied during a Crawl: the seven filter groups (Business natures, working locations, languages, job natures, employment types, levels of qualification, employment modes), the three checkboxes (Talent-Wise Employment Charter, Active Job, Non-Chinese speaking students would be considered), and an optional Deadline Hardline. Default is Active Job on, other filters empty, Hardline unset. Narrow filters only add or update matching postings; they never mark Closed.
_Avoid_: search facets, scrape filters, board query

**Crawl**:
A user-started sync of the Job Board into the local catalog: apply Crawl Filters for list discovery, then detail-fetch new or changed postings (skipping add/detail when a Deadline Hardline excludes them). Default is incremental. Narrow filtered Crawls only add or update. A completed list sync with unfiltered or Active-Job-only scope may mark absent postings Closed. If auth is lost mid-Crawl, the run ends as partial success: keep what was stored; do not mark untouched postings Closed.
_Avoid_: scrape run, sync job, harvest

**Full Refresh**:
A Crawl mode that re-fetches detail for every Open Job Posting in scope of the Crawl Filters (and Deadline Hardline if set), not only new or changed ones.
_Avoid_: force sync, rebuild catalog, hard reset

**Listing status**:
Open or Closed for a Job Posting. Closed means absent from a completed Closing-capable list sync (unfiltered or Active-Job-only) — not merely “detail not fetched yet,” and not absence from a narrowly filtered Crawl.
_Avoid_: expired, active, live (use Deadline status or Listing status explicitly)

**Deadline status**:
Whether the Job Posting's application deadline is Upcoming, Passed, or Unknown — independent of Listing status.
_Avoid_: expired (alone), overdue

**Deadline Hardline**:
An optional Crawl Filter cutoff date; after list discovery, the Crawl skips detail fetch and catalog add for postings whose deadline falls before it. Unset means no extra deadline limit (Active Job may still apply).
_Avoid_: filter, max age, crawl window

**Delete**:
The user permanently removes a Job Posting, its Match Assessment, and its Preparation Packet (if any) from the local catalog and tool-managed store, after a confirm that names those artifacts. No trash or undo. Rules: ADR-0013.
_Avoid_: archive, hide, soft-delete

### Candidate

**Master CV**:
The user's sole authored experience-and-skills document as RenderCV YAML on disk; never overwritten by the tool. Typography and PDF output are delegated to RenderCV; the user focuses on content. Unreadable or invalid YAML yields no usable Candidate Snapshot (Relevance stays Pending) with a clear error — rules: ADR-0014.
_Avoid_: resume, profile, base CV, LaTeX Master CV

**Hard Constraints file**:
A user-authored plain-text file of non-negotiable terms (path set like the Master CV; tool reads only). Empty or missing means no Hard Constraints to check. Path set but unreadable yields unknown for that signal plus a path/read error (not Pending) — rules: ADR-0014.
_Avoid_: preferences file (for this), must-haves config, deal-breaker form

**Preferences file**:
A user-authored plain-text file of soft priorities — what the user likes to have but does not require (path set like the Master CV; tool reads only). Empty or missing means no soft priorities to score. Path set but unreadable yields unknown for that signal plus a path/read error (not Pending). Not Crawl Filters and not Hard Constraints — rules: ADR-0014.
_Avoid_: settings, user config, hard constraints file, relevance input (alone)

**Candidate Snapshot**:
A structured view derived from the Master CV for matching: contact if present, education, experience, projects, and skills/tools as written — no inferred skills, and no Hard Constraints or Preferences. Rebuilt when the Master CV changes; inspectable; not hand-edited (fix the Master CV instead). Absent when the Master CV is unreadable or invalid.
_Avoid_: profile, parsed CV (as a product concept), editable profile

### Assessment

**Hard Constraint**:
A pass, fail, or unknown deal-breaker signal for the Job Posting against the Hard Constraints file. Evaluated by the LLM judge when that file is non-empty; empty or missing file yields unknown without a judge call. Unknown never counts as fail. Fail never blocks Prepare; Prepare confirms with the short fail reason. Overall outcome for a posting is this single Hard Constraint judgment (with a short reason). Judge criteria: ADR-0010. Prepare rules: ADR-0013.
_Avoid_: preference, soft want, ATS score, requirement filter (when meaning this check), Override, gate

**Preference**:
An ordinal soft-fit band — Strong, Mixed, or Weak — for how well a Job Posting aligns with the Preferences file (desire, not capability). Evaluated by the LLM judge when that file is non-empty; empty or missing file yields unknown without a judge call. Unknown Preference does not affect Assessment Summary sort. Weak does not block Prepare. Band criteria and judge inputs: ADR-0008.
_Avoid_: Relevance, Preference Score, ATS score, Hard Constraint, numeric preference percentage

**Relevance**:
An ordinal capability-fit band — Strong, Mixed, or Weak — for how well the Master CV / Candidate Snapshot matches the Job Posting description. Not an ATS score and not Preference. Band criteria and judge inputs: ADR-0008.
_Avoid_: match score, percentage, ranking score, ATS score, Preference

**Assessment Summary**:
The browse/list view of fit for one Job Posting: title, employer, Listing status, Deadline status, Hard Constraint outcome, Preference band, Relevance band, and whether a Preparation Packet exists (and if Stale). Default catalog shows Open postings with Deadline Upcoming or Unknown; sorts Pending last, then Hard Constraint fail after pass and unknown, then Preference (Strong, then Mixed, then Weak; unknown Preference ties), then Relevance (Strong, then Mixed, then Weak), then sooner deadline (known Upcoming sooner-first; Deadline Unknown last among otherwise-tied rows); Closed and Deadline Passed are hidden by default but toggleable.
_Avoid_: job card, list row, dashboard row

**Pending**:
Assessment Summary state when a required judgment is missing: Hard Constraint when the Hard Constraints file is non-empty and readable, Preference when the Preferences file is non-empty and readable, or Relevance (needs a usable Master CV / Candidate Snapshot and judge). Also Pending when the judge fails or is unavailable for a required signal, or when the Master CV is unreadable or invalid. Empty Hard Constraints or Preferences files count as resolved unknown, not Pending; a set but unreadable Hard Constraints or Preferences path is unknown for that signal (with a path/read error), not Pending. Prepare is unavailable while Pending; Pending rows sort after assessed ones. Freshness rules: ADR-0014.
_Avoid_: loading, unassessed, not ready (alone)

**Match Assessment**:
The full fit judgment for one Job Posting shown in detail: Hard Constraint with short reason, Preference, Relevance, and Evidence pairs, with actions to Prepare or Delete. On Master CV, Hard Constraints file, or Preferences file change (content or path clear), all assessments go Pending and re-judge asynchronously; new or detail-changed Crawl postings start Pending then re-judge asynchronously (Crawl success does not mean assessments finished). Judge failure leaves Pending or keeps the prior complete assessment — never a half-assessed final row. Otherwise the last Assessment is kept. Rules: ADR-0014.
_Avoid_: score, analysis, match result, ATS score

**Evidence pair**:
One justification unit: a Job Posting excerpt, a Master CV or Candidate Snapshot excerpt (or “not found”), and a one-line role — supports or weakens Relevance, or explains a Hard Constraint or Preference judgment.
_Avoid_: quote pair, citation row

**Evidence**:
The short list of Evidence pairs in a Match Assessment (about three to seven) used to decide Prepare vs skip; deeper gaps belong in the Gap Report after prepare.
_Avoid_: quote, reference, highlight (alone)

**Gap Report**:
Per Job Posting, a list of gaps: each item is a Requirement from the posting, a status (missing or partial), Evidence from the Master CV (or “not found”), and a non-fictional Suggestion. Hard Constraint failures appear when the Hard Constraint failed. Never invents experience. Built at Prepare only. Rules: ADR-0011.
_Avoid_: suggestions list, missing requirements (alone)

### CV artifacts

**Preparation Packet**:
The prepare-to-apply output for one Job Posting, held in a tool-managed store (not a user-chosen packets folder): Gap Report, Edit Summary, Tailored CV (RenderCV YAML), and PDF from RenderCV at Prepare; viewed with the current Match Assessment (not a frozen copy). UI for Gap Report and Edit Summary; download Tailored PDF and YAML. One current packet per posting; re-Prepare overwrites after confirm; mid-run failure leaves the prior packet untouched. Rules: ADR-0013.
_Avoid_: application pack, draft bundle, apply kit, packets folder

**Tailored CV**:
A per-Job-Posting RenderCV YAML copy of the Master CV that may reorder, rephrase, emphasize, or omit real content, and may rewrite an existing summary section only. Never invents employers, dates, titles, or skills; preserves the Master CV’s RenderCV YAML structure. Honors optional Master CV `assistant.pinned_section_order` metadata. Rendered to PDF via RenderCV for the user; the Master CV file is never overwritten. Formatting criteria: ADR-0009.
_Avoid_: modified CV, generated resume, customized CV (when meaning this artifact), LaTeX tailored CV

**Edit Summary**:
A first-class Preparation Packet peer: a grouped human-readable audit of Master CV → Tailored CV edits (omissions, section and cross-role reorders, summary rewrites, pin notes, material rephrases) — never JD gaps (those stay in the Gap Report). Empty material change is “No material edits.” Rules: ADR-0012.
_Avoid_: diff log, changelog, patch notes, Gap Report

**Stale**:
A Preparation Packet that is outdated because the Master CV, Hard Constraints file, or Preferences file changed (content or path clear) after it was produced — not because Crawl updated Job Posting detail. Stale packets stay fully readable with a banner; they are not auto-regenerated; the user re-prepares deliberately. Change detection: ADR-0014. Prepare/Stale rules: ADR-0013.
_Avoid_: outdated draft, invalid, expired packet
