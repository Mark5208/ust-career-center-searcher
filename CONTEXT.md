# Job Finding Assistant

Personal local tool that crawls the HKUST Job Board, assesses fit against one user's Master CV and Preferences, and prepares a Tailored CV for selected Job Postings.

## Language

### Job catalog

**Job Board**:
The HKUST Career Center job board — the sole source of Job Postings in this context.
_Avoid_: career site, portal, multiple boards

**Job Posting**:
One job listing from the Job Board, stored in the local catalog with its listing and deadline facts.
_Avoid_: job, role, vacancy, opening (when referring to the stored listing)

**Listing status**:
Whether the Job Posting was seen on the last successful crawl: Open or Closed.
_Avoid_: expired, active, live (use Deadline status or Listing status explicitly)

**Deadline status**:
Whether the Job Posting's application deadline is Upcoming, Passed, or Unknown — independent of Listing status.
_Avoid_: expired (alone), overdue

**Deadline Hardline**:
A user-set cutoff date; the crawler does not spend effort on Job Postings whose deadline falls before it.
_Avoid_: filter, max age, crawl window

**Delete**:
The user removes a Job Posting and its related artifacts from the local catalog.
_Avoid_: archive, hide, soft-delete

### Candidate

**Master CV**:
The user's sole authored experience-and-skills document (LaTeX); never overwritten by the tool.
_Avoid_: resume, profile, base CV

**Preferences**:
A small sidecar of hard-constraint facts the Master CV usually omits — languages spoken and acceptable work locations.
_Avoid_: profile, settings, user config

**Candidate Snapshot**:
A structured view derived from the Master CV for matching; not hand-maintained as a second source of truth.
_Avoid_: profile, parsed CV (as a product concept)

### Assessment

**Hard Constraint**:
A pass/fail/unknown check on language or work location, using Preferences against the Job Posting; unknown never counts as fail.
_Avoid_: requirement, filter, must-have (when meaning this check)

**Match Assessment**:
The full fit judgment for one Job Posting: Hard Constraints, Relevance, and Evidence citing the Master CV and the posting.
_Avoid_: score, analysis, match result

**Relevance**:
Coarse fit band for soft factors: Strong, Mixed, or Weak — not a numeric score.
_Avoid_: match score, percentage, ranking score

**Evidence**:
Concrete citations from the Master CV (or Candidate Snapshot) and from the Job Posting that justify the Match Assessment.
_Avoid_: quote, reference, highlight (alone)

**Gap Report**:
Soft gaps between the candidate and the Job Posting, with suggestions — never fabricated experience.
_Avoid_: suggestions list, missing requirements (alone)

### CV artifacts

**Tailored CV**:
A per-Job-Posting LaTeX copy derived from the Master CV by rephrasing, reordering, or emphasizing real content only.
_Avoid_: modified CV, generated resume, customized CV (when meaning this artifact)

**Override**:
An explicit user choice to produce a Tailored CV despite a Hard Constraint failure.
_Avoid_: force, bypass, ignore constraints
