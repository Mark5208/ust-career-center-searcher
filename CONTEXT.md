# Job Finding Assistant

Personal local tool that crawls the HKUST Job Board, assesses fit against one user's Master CV and Preferences, and prepares a Tailored CV for selected Job Postings.

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

**Crawl**:
A user-started sync of the Job Board into the local catalog: list discovery, then detail fetch for postings within the Deadline Hardline. Default is incremental — detail only for new or changed postings; Listing status becomes Closed only after a completed list sync shows a posting absent. If auth is lost mid-Crawl, the run ends as partial success: keep what was stored; do not mark untouched postings Closed.
_Avoid_: scrape run, sync job, harvest

**Full Refresh**:
A Crawl mode that re-fetches detail for every Open Job Posting within the Deadline Hardline, not only new or changed ones.
_Avoid_: force sync, rebuild catalog, hard reset

**Listing status**:
Open or Closed for a Job Posting. Closed means absent from a completed list sync — not merely “detail not fetched yet.”
_Avoid_: expired, active, live (use Deadline status or Listing status explicitly)

**Deadline status**:
Whether the Job Posting's application deadline is Upcoming, Passed, or Unknown — independent of Listing status.
_Avoid_: expired (alone), overdue

**Deadline Hardline**:
A user-set cutoff date; a Crawl does not spend effort on Job Postings whose deadline falls before it.
_Avoid_: filter, max age, crawl window

**Delete**:
The user removes a Job Posting and its related artifacts from the local catalog.
_Avoid_: archive, hide, soft-delete

### Candidate

**Master CV**:
The user's sole authored experience-and-skills document (LaTeX); never overwritten by the tool.
_Avoid_: resume, profile, base CV

**Preferences**:
A minimal sidecar for Hard Constraint inputs only: languages spoken (optional level) and acceptable work locations. Empty language or location fields leave the related Hard Constraint unknown, never fail.
_Avoid_: profile, settings, user config, visa, GPA

**Candidate Snapshot**:
A structured view derived from the Master CV for matching: contact if present, education, experience, projects, and skills/tools as written — no inferred skills, and no Preferences. Rebuilt when the Master CV changes; inspectable; not hand-edited (fix the Master CV instead).
_Avoid_: profile, parsed CV (as a product concept), editable profile

### Assessment

**Hard Constraint**:
A pass, fail, or unknown check on language or work location using Preferences against the Job Posting. Location passes if the posting’s work location is among acceptable locations, or is clearly remote and remote is accepted; fails on a definite mismatch; unknown if Preferences locations are empty or the posting location is missing/unclear. Language passes if every language the posting requires appears in Preferences; fails if a required language is missing; unknown if Preferences languages are empty or needs are unclear — “preferred” or vague language wording is not a hard require. Unknown never counts as fail.
_Avoid_: requirement, filter, must-have (when meaning this check)

**Match Assessment**:
The full fit judgment for one Job Posting: Hard Constraints, Relevance, and Evidence citing the Master CV and the posting. Rebuilt for postings that are new or whose detail changed in a Crawl; rebuilt for Open postings when the Master CV or Preferences change; otherwise the last Assessment is kept.
_Avoid_: score, analysis, match result

**Relevance**:
Coarse fit band for soft factors: Strong, Mixed, or Weak — not a numeric score.
_Avoid_: match score, percentage, ranking score

**Evidence**:
Concrete citations from the Master CV (or Candidate Snapshot) and from the Job Posting that justify the Match Assessment.
_Avoid_: quote, reference, highlight (alone)

**Gap Report**:
Per Job Posting, a list of gaps: each item is a Requirement from the posting, a status (missing or partial), Evidence from the Master CV (or “not found”), and a non-fictional Suggestion. Hard Constraint failures appear when relevant (especially under Override). Never invents experience.
_Avoid_: suggestions list, missing requirements (alone)

### CV artifacts

**Preparation Packet**:
The prepare-to-apply output for one Job Posting: Match Assessment, Gap Report, Tailored CV, and Edit Summary. One current packet per posting; re-running prepare overwrites it after a warning.
_Avoid_: application pack, draft bundle, apply kit

**Tailored CV**:
A per-Job-Posting LaTeX copy of the Master CV that may reorder, rephrase, emphasize, or omit real content, and may rewrite an existing summary section only. Never invents employers, dates, titles, or skills; preserves the Master CV’s LaTeX structure.
_Avoid_: modified CV, generated resume, customized CV (when meaning this artifact)

**Edit Summary**:
A human-readable list of what the Tailored CV changed versus the Master CV (reorders, omissions, rephrases, summary tweaks) so the user can audit before applying.
_Avoid_: diff log, changelog, patch notes

**Stale**:
A Preparation Packet that is outdated because the Master CV or Preferences changed after it was produced. Stale packets are not auto-regenerated; the user re-prepares deliberately.
_Avoid_: outdated draft, invalid, expired packet

**Override**:
An explicit user choice to produce a Preparation Packet despite a Hard Constraint failure.
_Avoid_: force, bypass, ignore constraints
