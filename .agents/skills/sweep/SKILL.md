---
name: sweep
description: After a wayfinder map is done, classify leftovers and janitor spent throwaways.
disable-model-invocation: true
---

Leftover-wayfinder janitor work. A new conversation with this invoke as first speech is a full run. Git and GitHub are the source of truth; this invoke takes no map URL.

Run done-when: a land PR URL or an explicit stop reason; leftover names deleted or left; refuse-gate stop-and-leave reported.

## 1. Fetch and remember

Run [Remember](#remember). Record the current branch name, or the detached SHA if HEAD is detached, before land or janitor, even when the copy set will be empty.

Done when `origin` is fetched and the remembered ref is recorded.

## 2. Classify every leftover object

Classify then act. Apply [Vocabulary](#vocabulary), [Classify](#classify), and [Actions](#actions) to every leftover object. Location prefixes (`docs/`, `cursor/`, `integrate/`, `research/`) are not buckets. Open PRs and in-progress branches of other maps are not leftover. Uncommitted WIP is not a leftover ref. Stash, worktrees, and tags are outside [Command surface](#command-surface). `origin/cursor/*` uses the same content cut as any other leftover.

Done when every leftover object has a bucket, every in-play object is recorded as not leftover, and every never-land untracked path is reported.

## 3. Refuse-gate each product object

For each leftover whose bucket is product — including product mix and `prototype/<name>` that grew product — refuse-gate: report, leave the object, do not spend. Hand off is `/grill-with-docs` then `/to-spec`. Continue every other object in this run.

Done when every product leftover is reported and still present, and non-product leftovers remain eligible for later steps.

## 4. Note-only land

Apply [Cite pointer](#cite-pointer-and-reconstruct) and [Reconstruct](#cite-pointer-and-reconstruct).

**Dirty tree.** If `git status --porcelain` is non-empty: stop this half, report, leave the tree. Later steps still run.

**In-flight.** If an open `integrate/sweep-*` PR already exists: keep it hands-off. Skip opening a second PR and skip pushing onto it. New notes wait. Later steps still run.

**Finish-the-PR.** If any `origin/integrate/sweep-*` has unique note-only and no open PR, that takes priority over a new reconstruct. Open one ready PR from the oldest such name as-is (no reconstruct, no [Land publish](#land-publish)). If several such refs exist, open that one PR and stop this half; the rest wait. Later steps still run.

**Empty.** If the copy set is empty after skips: no branch, no PR. Later steps still run.

**Otherwise reconstruct.** UTC date is `YYYY-MM-DD`. Check out a new branch `integrate/sweep-<UTC-date>` from `origin/main` (`git switch -c integrate/sweep-<UTC-date> origin/main`). If that name is taken locally or on `origin` and it is not a finish-the-PR candidate, use `integrate/sweep-<UTC-date>-<n>`. Reconstruct one new commit on that branch. Message: `Land note-only research notes (sweep <UTC-date>)`.

Land diff: `git diff --name-only origin/main` shows only copied `.scratch/research-*.md` paths and `.scratch/README.md` when the index changed. Every copied path is in the diff. The land gate is that diff check, not pytest.

Gate **before** [Land publish](#land-publish). Gate fail → `git branch -D <land-branch>` locally only, stop this half, report. Later steps still run.

[Land publish](#land-publish), then `gh pr create`: ready, not draft. Title: `Land note-only sweep notes (<UTC-date>)`. Body lists source leftover refs, citing tickets, paths copied / skipped / reported (differ, uncited, denied, refused product objects), and that the diff contains only those research notes plus README when it changed. No `Closes`. No extra issue comments. No required labels.

If [Land publish](#land-publish) does not complete, follow that subsection. Later steps still run.

`gh pr create` fail after a successful push → leave `origin`'s land branch, report the name (next run is finish-the-PR).

Source leftover refs that still hold the copied notes stay unspent this run. Human merges.

Done when there is a ready PR URL or an explicit stop reason (dirty tree, in-flight keep, finish-the-PR opened, empty copy set, gate fail, land push-fail, create-fail-after-push), and source leftover refs that still hold copied notes are still present.

## 5. Restore remembered ref

Check out the remembered branch or detached SHA. The land branch is a ref, not HEAD.

Done when HEAD is the remembered ref, or checkout failed and that failure is reported.

## 6. Blob-link retarget

After fetch, this pass runs even when nothing is left to delete. Paths that exist only on an unmerged land branch opened this run are not due.

A path already on `origin/main` is due when:

- A [cite pointer](#cite-pointer-and-reconstruct) on a **closed** issue uses a git ref other than `main`, and no comment on that issue already contains a `blob/main/` URL to **that exact path**.
- An **open** `wayfinder:map` Decisions-so-far (or equivalent index) line still uses a leftover-branch blob for that path. Skip a line that already uses `blob/main/` or a relative path. Closed maps stay as written. Grilling tickets are not a scrape surface.

Catch-up tickets that already have a `blob/main/` follow-up for that path skip by path-pointer presence.

**Same document.** Compare blob hashes with `git rev-parse <ref>:<path>`. If the leftover blob still exists and its hash differs from `origin/main`: report that path; skip follow-up, map edit, and delete for it. Matching hashes: retarget. Leftover ref already gone and the path is on `main`: retarget with no hash check.

Retarget is per-path. Spent-delete stays per-ref. A mixed leftover that still holds unique files can retarget the copied path and still remain unspent.

**Tickets.** Append one follow-up per due ticket per run, listing every due path:

```
On `main`:

- `<path>` — <blob/main URL>
```

Add `(land PR <url>)` when `gh` or git can name the land PR. A missing `#N` is not failure. Old comments stay as written. A later run may post another comment on the same ticket when a new path is due.

**Maps.** On each due open-map index line, replace the leftover-branch blob with the `blob/main/` URL. Leave the rest of the gist. Leave the Decisions-so-far row set unchanged.

Build `blob/main/` URLs from `git remote get-url origin`.

**Retarget-then-delete gate.** All due writes for a path (follow-ups + map lines) succeed or skip-as-present before this run may spent-delete refs whose only remaining unique files are paths that cleared. A skipped, blocked, or failed delete still keeps comments and index writes that already landed. If any due surface for a path fails: report that path, continue other paths, and leave refs that still protect the failed path.

Done when every due path is retargeted, skipped-as-present, or reported, and no path that exists only on this run's unmerged land branch was retargeted.

## 7. Spent-delete

Apply [Spent-delete commands](#spent-delete-commands) to each leftover name that is spent **and** has cleared the retarget-then-delete gate. Empty leftover names and dump-only leftovers that are spent may delete in this run. Names refuse-gated this run stay. Source leftover refs that still hold notes copied in this run stay. Closed GitHub PRs stay when their head refs go away.

Done when every eligible spent name has had origin `--delete` then local `-D` (skipping missing sides), or is reported as delete-blocked, and other names continued.

## 8. Restore remembered ref

If the remembered ref still exists, check it out. Else stay detached at `origin/main` and report.

Done when HEAD is the remembered ref, or HEAD is detached at `origin/main` and that stay is reported.

## Vocabulary

- **Leftover** — git/disk object that is not live work of an open map (stale `cursor/*`, merged PR heads, untracked dumps, leftover `integrate/*`, diverged local `main`, `research/*` after the map closes).
- **Note-only** — unique **commits** on a leftover ref whose paths a closed ticket already cites as findings, plus the `.scratch/README.md` index those notes need.
- **Product** — unique **commits** on a leftover ref that would change the Job Finding Assistant (code, `CONTEXT.md`, ADRs, in-app behavior, parked v2/Authoring themes, skill rewrite). One product file poisons the whole ref.
- **Never-land** — dumps, `private/`, lockfiles. Leave them off the copy set and off `origin/main`.
- **Primary-source** — `prototype/<name>` capture: throwaway stays on that branch, unlanded; the validated decision is already on `main`.
- **Spent** — leftover whose **preservable** unique content is already on `main`, or there was none → deletable. Stale blob URLs do not keep it alive. Refuse-gate does not spend in the same run.
- **Refuse-gate** — stop and leave the product object; hand off is `/grill-with-docs` → `/to-spec`.

Guidance, not a bucket: land note-only on `origin/main` before opening implementation branches, so product mix stays rare. A feature branch existing does not stop this run.

## Actions

| Object | Bucket | Action |
|---|---|---|
| Cited research notes not on `main` | Note-only | Land. After they are on `main`, the source ref is spent. |
| Same ref + product commits | Product mix | Refuse-gate the whole object. Notes stay with it. |
| Cited notes + never-land commits, no product | Never-land mix | Split — land cited note-only only. After merge, if only never-land remains unique → spent. |
| `prototype/<name>` without unique product | Primary-source | Keep. Never land. Never refuse-gate. Map-close does not spend. Later sweep may spend only after a human/product effort explicitly discards it. |
| `prototype/<name>` with unique product | Product | Refuse-gate. |
| Merged PR head / leftover `integrate/*` with no unique commits | Empty → spent | Spent-delete the leftover name locally and on `origin`. |
| Stale `origin/cursor/*` | Same classifier | Land / refuse-gate / keep / spent-delete as the content cut says. |
| Open PR already landing note-only (`integrate/sweep-*`) | In-flight land | Keep. Not spent until on `main`. |
| Open PR / in-progress branch of another map | Not leftover | Keep. |
| Untracked dumps / `private/` / lockfiles | Never-land | Report. Leave them untracked. |
| Cited path that exists only untracked | Never-land | Report missing from git. Leave it untracked. |
| Leftover ref whose only unique commits are never-land | Spent | Spent-delete the ref. |
| Local `main` | Special | [Local main](#local-main). |
| Uncommitted product / untracked `.agents/skills/*` installs | Live WIP | Not leftover refs. Leave them untracked. Product still refuse-gates when it is unique **commits** on a leftover ref. |
| Stash, worktrees, tags | Out of command surface | Leave them in place. |

## Classify

Inspect local heads (`git branch`) and origin heads (`git branch -r --list 'origin/*'`) after fetch. Inspect untracked dumps / `private/` / lockfiles as never-land reports, not as leftover refs. Other remotes stay out of this inspect.

**In-play** (not leftover): head of an open PR; a branch named on an open `wayfinder:map` or its open children.

Per leftover ref, unique content vs `origin/main`:

```
git log --oneline origin/main..<ref>
git diff --name-only origin/main...<ref>
```

Bucket in this order:

1. Unique paths include any product file → product (whole ref, including `prototype/<name>` that grew product).
2. Else the name is `prototype/<name>` → primary-source (keep; leave unlanded).
3. Else no unique commits → empty → spent.
4. Else unique paths are only never-land → spent.
5. Else cited `.scratch/research-*.md` missing from `origin/main` → note-only (split when never-land is also unique).

File source for land is leftover refs only (local or `origin`). In-play branches are not harvested.

## Cite pointer and reconstruct

**Cite pointer:** a markdown link or GitHub blob/tree URL to `.scratch/research-*.md` on a **closed** issue in this repo (body or comments), or on the Sweep map Decisions-so-far. Bare filenames are not cites. Find them by searching this repo's closed issues and the Sweep map (`wayfinder:map` whose destination is leftover-wayfinder janitor behaviour) Decisions-so-far.

**Copy set:** those cited `research-*.md` files missing from `origin/main`, plus `.scratch/README.md`. Never-land always wins, even if cited. Any other cited path: report, leave it uncopied. Uncited unique `research-*.md`: report, leave it unlanded. A cited path that exists only untracked: report missing from git.

**Reconstruct** (not cherry-pick). One new commit on the land branch. Leftover SHAs stay unreplayed. Compare blob hashes with `git rev-parse <ref>:<path>`. Copy missing bytes with `git show <ref>:<path>`.

| Cited `research-*.md` vs `origin/main` | Action |
|---|---|
| Missing | Copy bytes from the leftover ref |
| Same path, same hash | Skip |
| Same path, different content | Leave `main`'s bytes; report; still land other missing paths |
| Same path on two leftovers, missing from `main`, different content | Leave that path uncopied; report both refs; still land the rest |

**README:** start from `git show origin/main:.scratch/README.md`. Relative filename only. Among citing issues, prefer `wayfinder:research`; if the pointer is a map Decisions-so-far bullet, use the **child ticket that bullet is about**, not the map; else lowest citing number. Title from `gh issue view`. Append under `## Research` (create that heading if missing; leave other sections as they are). Sort the new batch by ticket number; leave old lines in their existing order. Skip a bullet whose filename is already listed. New bullets match the index already on `origin/main`: `- [<filename>](<filename>) — [<title>](<issue-url>)`.

## Local main

Local `main` is never a spent name, never a delete target, never a reset target, and never a publish target.

- Behind-only vs `origin/main`: report.
- Unique product commits: refuse-gate.
- Unique note-only commits: stop this object for a human to move onto a branch. Reconstruct does not copy from local `main`.
- Never-land-only unique commits: report and leave.

## Command surface

### Remember

Once at start: `git fetch origin`, then remember current branch or detached SHA.

### Land publish

After the land-PR gate: `git push origin <land-branch>` (`integrate/sweep-<UTC-date>` or the suffix variant). Finish-the-PR has no publish step.

Does not complete → restore remembered, then `git branch -D <land-branch>` locally only, land-half stop, report. Spent-delete of names already spent that have cleared the retarget-then-delete gate still runs.

### Spent-delete commands

After the retarget-then-delete gate, per spent name (one name per command):

1. `git ls-remote --heads origin <spent-name>` empty → skip origin side; else `git push origin --delete <spent-name>`.
2. `git show-ref --verify --quiet refs/heads/<spent-name>` missing → skip local side; else if HEAD is that name, `git switch --detach origin/main`, then `git branch -D <spent-name>`.

`--delete` / `-D` error → report that name, continue other names. After the cluster: restore remembered if it still exists; else stay detached at `origin/main` and report.

Spent-delete names are leftover branch names on this clone and `origin`.

### Non-completion

Land push-fail or delete-blocked. Those outcomes are the whole account.
