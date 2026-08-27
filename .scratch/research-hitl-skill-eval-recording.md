# Research: HITL skill eval recording

Question: how are HITL agent-skill evals usually recorded in Cursor, Claude Code, Codex, and adjacent first-party skill docs — a pass/fail Sitting log, pytest-style fixtures, a checklist in the skill, or something else? What can this repo reuse without inventing a test harness? Domain term: a **Sitting** is one conversation of Master CV Authoring (HITL skill family), not Enrichment and not a pytest session.

Primary sources only. Each claim cites the source that owns it.

## Verdict

No first-party product documents a HITL Sitting log. The only first-party *skill* eval recording story is Agent Skills + Claude Code `skill-creator`: AFK prompt → expected output, stored as `evals/evals.json` inside the skill directory, run in isolated subagents, graded to `grading.json` (PASS/FAIL with evidence), aggregated in `benchmark.json`, plus after-the-fact human `feedback.json` from an HTML review viewer. Cursor's skills pages do not describe skill evals; Cursor's evals page is an SDK hook so *your* harness can pass a task and get a transcript. Codex skills docs say to test prompts against the description and optionally run Independent Forward-Testing in a subagent; they do not ship `evals/` schemas. The Agent Skills *specification* does not define evals.

This repo already records HITL judgment as markdown under `.scratch/` (grill-outcome notes, research findings) plus wayfinder GitHub resolution comments. Authoring pytest files test the on-disk package contract, not Sitting behaviour. In-skill "Done when…" lines are agent completion criteria, not a recorder. Reuse without a new harness: keep that markdown + GitHub-comment shape for later Sitting pass/fail; keep package-contract pytest as-is. Copying `evals/evals.json` / `grading.json` into Authoring skills would adopt a vendor *file convention* built for AFK prompt/output, not interview/confirm. Running skill-creator's subagent loop, Cursor SDK scoring, Codex forward-testing, or Slack `make test-eval` as a Sitting runner would be inventing (or importing) a harness this repo does not have.

---

## 1. Cursor — skills docs do not record skill evals

Cursor's Agent Skills reference covers discovery, `SKILL.md` frontmatter, scripts/references/assets, and invocation (`/` and `@`). It has no section on evals, evaluation, grading, rubrics, or skill test cases.

Source: https://cursor.com/docs/skills.md

Cursor Help for skills is the same surface: create with `/create-skill`, invoke with `/` or `@`, skills vs rules. It does not describe recording skill evals.

Source: https://cursor.com/help/customization/skills.md

The built-in `/create-skill` skill walks naming, structure, and saving. Its sample `code-review` skill includes a **Review Checklist** (markdown checkboxes the *agent* ticks while reviewing code) and the step "Ensure tests are adequate". That is in-skill agent steps, not an eval recorder for the skill itself. Grep of `/home/agent/.cursor/skills-cursor/` for `eval`, `evaluation`, `rubric`, and `scorecard` in `*.md`/`*.json` returned no skill-eval recording story.

Sources: `/home/agent/.cursor/skills-cursor/create-skill/SKILL.md` ; `/home/agent/.cursor/skills-cursor/`

### Cursor evals page — agent loop for *your* harness, not skill evals

Cursor's evals doc is titled "Run Cursor in your evals". It tells you to use the Cursor SDK (`@cursor/sdk`) **inside your own eval harness**: pass a task, get a transcript and final state, then "score the working tree with whatever your harness already uses (test runner, judge model, exact-match checker, etc.)". Artifacts named there: typed `SDKMessage` events, `run.stream()` transcript, `RunResult` (`status`, `result`, `durationMs`, git info). Local or cloud VM. `Agent.prompt()` is described as the primitive for **stateless eval tasks**.

The page does not mention Agent Skills, `SKILL.md`, `evals/evals.json`, HITL, interviews, or confirm-before-write.

Source: https://cursor.com/docs/evals

The TypeScript SDK reference confirms a local agent loads workspace **skills** as part of scan/context (alongside rules and `AGENTS.md`). That is load behaviour for an SDK run, not a skill-eval file format.

Source: https://cursor.com/docs/sdk/typescript.md

The built-in `/sdk` skill points at those SDK docs and, on mid-flight failure, says to inspect **transcript**, git state, and tool outputs. It does not define a skill-eval recorder.

Source: `/home/agent/.cursor/skills-cursor/sdk/SKILL.md`

### Cursor CLI — session transcripts, not skill grades

Non-interactive CLI (`-p` / `--print`) can emit `text`, `json`, or `stream-json`. Changelog notes that transcripts persist to disk for tooling and hooks, and that headless transcripts can write Claude Code-compatible JSONL. These are **session** transcripts for scripts, not a documented skill-eval PASS/FAIL log.

Sources: https://cursor.com/docs/cli/using.md ; https://cursor.com/docs/cli/reference/output-format.md ; https://cursor.com/docs/cli/changelog.md

The statusline skill documents a `transcript_path` in the CLI status-line JSON payload (path to the conversation transcript file). That is status-line context, not skill grading.

Source: `/home/agent/.cursor/skills-cursor/statusline/SKILL.md`

### Bugbot / Agent Review — PR review, not skill evals

Bugbot reviews pull-request diffs and leaves comments (or dry-run analytics). Agent Review reviews local changes. Neither page describes recording HITL skill evals.

Sources: https://cursor.com/docs/bugbot.md ; https://cursor.com/docs/agent/agent-review.md

Cursor cloud-agent docs mention run **artifacts** (screenshots, videos, logs) and a **transcript** of the user-agent conversation. That is cloud-run observability, not a skill-eval schema.

Sources: https://cursor.com/docs/cloud-agent.md ; https://cursor.com/docs/cloud-agent/capabilities.md

**Cursor answer:** first-party skills docs do **not** describe recording HITL skill evals. The evals product is "bring your own harness + SDK transcript". There is no Cursor-owned Sitting log, skill `evals/` layout, or in-skill scorecard for skill quality.

---

## 2. Claude Code / Anthropic — `evals/evals.json` + `grading.json` + human `feedback.json`

### Official skills page: evaluate by baseline comparison, automate with skill-creator

Claude Code skills docs have an **"Evaluate and iterate on a skill"** section. Triggering and output quality are measured separately. The check is a **baseline comparison**: a few realistic prompts, each in a **fresh session** with the skill available and again with it disabled.

The [`skill-creator` plugin](https://github.com/anthropics/claude-plugins-official/tree/main/plugins/skill-creator) automates that loop. Official recording artifacts named on the skills page:

| Artifact | What it records |
| --- | --- |
| `evals/evals.json` inside the skill directory | prompts, input files, expected behaviour |
| Isolated subagent runs | clean context per test case; token count and duration |
| `grading.json` | each assertion checked against output; pass or fail with evidence |
| `benchmark.json` | pass rate, time, and tokens for with-skill vs without-skill |
| Version comparison | blind A/B between two skill versions |
| Description tuning | should-trigger / should-not-trigger prompts and hit rate |
| HTML review viewer | inspect each output; record qualitative feedback for the next iteration |

The same page points at agentskills.io for the eval file format and iteration workflow.

Sources: https://code.claude.com/docs/en/skills.md ; https://docs.anthropic.com/en/docs/claude-code/skills

There is **no** documented `claude eval` CLI subcommand for skills on those pages. Evaluation is invoked by asking Claude to evaluate a skill with skill-creator (example: `evaluate my summarize-changes skill with skill-creator`).

Source: https://code.claude.com/docs/en/skills.md

### skill-creator (anthropics/skills) — the schema owners

`skill-creator` saves test cases to `evals/evals.json`. First pass: prompts and `expected_output` only; assertions later. Results go in a sibling `*-workspace/` with `iteration-N/eval-<name>/with_skill/` and `without_skill/` (or `old_skill/` when improving). Per-run files: `outputs/`, `timing.json`, `grading.json`, `eval_metadata.json`. After grading, `benchmark.json` / `benchmark.md`. Human review is `eval-viewer/generate_review.py`; "Submit All Reviews" writes `feedback.json`.

`references/schemas.md` owns the JSON shapes. `evals.json` fields: `skill_name`, `evals[].id`, `prompt`, `expected_output`, optional `files`, `expectations` (verifiable statements). `grading.json` fields: `expectations[]` with `text`, `passed`, `evidence`; `summary` pass/fail counts and `pass_rate`; optional `execution_metrics` (including `transcript_chars`), `timing`, `claims`, `user_notes_summary`, `eval_feedback`. `benchmark.json` aggregates with-skill vs without-skill. `comparison.json` is blind A/B with a `rubric` (numeric scores) plus `expectation_results`. `history.json` tracks Improve-mode versions.

Sources: https://raw.githubusercontent.com/anthropics/skills/main/skills/skill-creator/SKILL.md ; https://raw.githubusercontent.com/anthropics/skills/main/skills/skill-creator/references/schemas.md

skill-creator's own wording on *when not to force numbers*: "Skills with objectively verifiable outputs (file transforms, data extraction, code generation, fixed workflow steps) benefit from test cases. Skills with subjective outputs (writing style, art) often don't need them." And: "Subjective skills (writing style, design quality) are better evaluated qualitatively — don't force assertions onto things that need human judgment."

The run itself is AFK: spawn subagents with the eval prompt; the human reviews **outputs after the run** in the viewer. Claude.ai fallback without subagents: run prompts yourself, present results **in the conversation**, ask "How does this look?"

Source: https://raw.githubusercontent.com/anthropics/skills/main/skills/skill-creator/SKILL.md

GitHub code search for `evals/evals.json` in `anthropics/skills` hits skill-creator's `SKILL.md` (the authoring instructions), not example production skills shipping filled `evals/` folders.

Source: GitHub code search on `repo:anthropics/skills evals/evals.json`

anthropics/skills README tells readers to "Always test skills thoroughly in your own environment"; it does not add a second recording format.

Source: https://raw.githubusercontent.com/anthropics/skills/main/README.md

### `/goal` — session completion in the transcript, not skill evals

Claude Code `/goal` sets a completion condition. A small fast model judges the conversation after each turn and records **Met** / **Impossible** as an achieved or failed entry **in the transcript**. The evaluator does not run commands or read files independently. This is session-goal evaluation, not a skill-eval harness.

Source: https://docs.anthropic.com/en/docs/claude-code/goal

Usage monitoring can log `skill_name` on Skill-tool events when `OTEL_LOG_TOOL_DETAILS` is on. That is telemetry, not a grade.

Source: https://docs.anthropic.com/en/docs/claude-code/monitoring-usage

**Claude Code answer:** yes — first-party skill eval recording is `evals/evals.json` + per-run `grading.json` (PASS/FAIL + evidence) + `benchmark.json` + human `feedback.json`. It is AFK prompt/output (plus after-the-fact human review). The skills docs do not describe evaluating an interview or confirm-before-write Sitting.

---

## 3. Codex / OpenAI — trigger-test prose + optional Independent Forward-Testing; no `evals/` schema

Official Codex skills docs: a skill is `SKILL.md` plus optional `scripts/`, `references/`, `assets/`, `agents/openai.yaml`. Best-practices bullet: **"Test prompts against the skill description to confirm the right trigger behavior."** The page does not name `evals/evals.json`, `grading.json`, a Sitting log, pytest fixtures for skills, or HITL scorecards.

Source: https://developers.openai.com/codex/skills.md

"Save workflows as skills": after creating a skill, use it, then if it uses the wrong test command, misses a review rule, skips a runbook step, or writes a draft you would not send, **ask Codex to add that correction to the skill**. Recording is iterative chat correction, not a stored eval suite.

Source: https://developers.openai.com/codex/use-cases/reusable-codex-skills.md

Bundled Codex `skill-creator` (`codex-rs/skills/.../samples/skill-creator/SKILL.md`): `scripts/quick_validate.py` checks frontmatter, naming, and unfinished scaffold placeholders; **"it does not prove that the skill makes good decisions."** "When testing is warranted, verify observable behavior or meaningful invariants. Avoid tests that merely match generated wording."

**Independent Forward-Testing** (when the skill is complex/risky and delegation is available): give an independent subagent a realistic user request, the skill, and minimum raw artifacts; isolated temporary workspace; review the actual outcome and artifacts. No JSON schema, no PASS/FAIL file, no HITL interview protocol.

Source: https://raw.githubusercontent.com/openai/codex/main/codex-rs/skills/src/assets/samples/skill-creator/SKILL.md

openai/codex `docs/skills.md` only redirects to the developers.openai.com skills page.

Source: https://raw.githubusercontent.com/openai/codex/main/docs/skills.md

Codex use-case **"Add evals to your AI application"** is Promptfoo (`$promptfoo-evals`) against an **AI application** path (`promptfooconfig.yaml`, `evals/` directory, `npm run evals`). It is not pointed at from the skills page as how *skills* are evaluated.

Source: https://developers.openai.com/codex/use-cases/ai-app-evals (fetched via search index; full page timed out once, then the skills page was confirmed not to link this as skill eval)

**Codex answer:** first-party skill docs do **not** describe a HITL skill-eval recorder. Closest documented practices: manual trigger prompts against `description`; `quick_validate.py` for package shape; optional Independent Forward-Testing (subagent + artifacts, no schema).

---

## 4. Agent Skills open standard — evals are a creation guide, not the spec

The specification's optional directories are `scripts/`, `references/`, and `assets/`. Frontmatter: `name`, `description`, optional `license`, `compatibility`, `metadata`, `allowed-tools`. Validation is `skills-ref validate` for frontmatter/naming. **No evals field, no `evals/` directory, no grading format.**

Source: https://agentskills.io/specification

The companion skill page (`skill.md`) *does* describe evaluation as a creator workflow: ~20 trigger eval queries; 2–3 output test cases in `evals/evals.json`; with-skill vs without-skill; assertions; PASS/FAIL with evidence; human review. That is the same loop as §2, documented at agentskills.io rather than in the format spec.

Sources: https://agentskills.io/skill.md ; https://agentskills.io/skill-creation/evaluating-skills ; https://agentskills.io/skill-creation/optimizing-descriptions

**Evaluating skill output quality** owns the recording layout:

- Author: `evals/evals.json` (`prompt`, `expected_output`, optional `files`, later `assertions`).
- Workspace sibling: `iteration-N/eval-<name>/with_skill|without_skill/{outputs,timing.json,grading.json}`.
- `grading.json`: each assertion `passed` true/false plus `evidence`.
- `benchmark.json`: aggregated pass_rate / time / tokens and delta.
- Human review: `feedback.json` keyed by eval name (actionable comments; empty = looked fine).
- Execution **transcripts** are named as a third signal (with failed assertions and human feedback) when iterating the skill.

The guide says some qualities "are hard to decompose into pass/fail checks" and "are better caught during human review." It does not mention HITL interviews, confirm-before-write, or a Sitting.

Source: https://agentskills.io/skill-creation/evaluating-skills

**Optimizing skill descriptions** records trigger evals as JSON arrays of `{ "query", "should_trigger" }`, run repeatedly for a **trigger rate**, pass if rate is above/below 0.5. Example detection uses `claude -p` JSON output looking for a Skill tool call. "Most agent clients provide some form of observability — execution logs, tool call histories, or verbose output."

Source: https://agentskills.io/skill-creation/optimizing-descriptions

Best-practices: in-skill **checklists** for multi-step workflows (agent progress, not an eval log); "Refine with real execution"; pointer to evaluating-skills for structured evals. Index (`llms.txt`) lists evaluating-skills as a creation guide, not as part of the specification.

Sources: https://agentskills.io/skill-creation/best-practices ; https://agentskills.io/llms.txt

**Spec answer:** the open format does **not** specify evals. The official creation guides specify `evals/evals.json` + workspace `grading.json` / `benchmark.json` / `feedback.json` for AFK output quality, and query JSON for trigger tests.

---

## 5. Adjacent first-party skill packages — common pattern

### Pattern across owners that actually document skill evals

| Pattern | Who documents it | HITL Sitting? |
| --- | --- | --- |
| `evals/evals.json` prompts + expected output + assertions; `grading.json` PASS/FAIL + evidence; `benchmark.json`; `feedback.json` | Agent Skills evaluating-skills; Claude Code skills page; anthropics `skill-creator` | No — AFK runs; human reviews outputs after |
| Trigger query JSON + trigger rate | Agent Skills optimizing-descriptions; skill-creator description loop | No |
| In-skill markdown checklist / "Done when" | Agent Skills best-practices; Cursor create-skill sample; this repo Authoring skills | Agent steps, not a recorder |
| pytest (or equivalent) on package contract | This repo Authoring tests; Slack plugin `tests/unit/` | No |
| LLM-judged pytest of tool *selection* | Slack plugin `make test-eval` / DeepEval | No — AFK prompt → expected tool |
| Independent subagent + review artifacts | Codex bundled skill-creator | No schema |
| SDK transcript + *your* scorer | Cursor evals / `@cursor/sdk` | Bring-your-own harness |
| Chat correction after a real use | Codex "Save workflows as skills" | Informal, not a log format |
| Nothing | Cursor skills pages; Agent Skills specification | — |

### mattpocock/skills

README describes grilling, TDD, diagnosing-bugs, wayfinder, research — not a skill-eval harness. `writing-for-agents` (this repo's copy of that discipline) defines **completion criteria** on steps: checkable done-vs-not-done for the *agent running the skill*, not an eval log.

Sources: https://raw.githubusercontent.com/mattpocock/skills/main/README.md ; this repo `.agents/skills/writing-for-agents/SKILL.md`

A GitHub issue on mattpocock/skills (#722) *proposes* adding optional behavioural-evaluation guidance (baseline vs candidate, isolated sessions, observable behaviour, blinded rubric only when needed). That is an open proposal, not shipped skill text.

Source: https://github.com/mattpocock/skills/issues/722

### vercel-labs/skills

The installer (`npx skills`) maps agents to skill directories and can surface **security audits**. It does not document skill-eval recording. Community index requests that mention `evals/evals.json` are third-party skills asking to be listed, not vercel-labs eval docs.

Sources: https://github.com/vercel-labs/skills (README / `src/add.ts` as fetched); index-request issues are not used as eval-format owners

### Slack plugin in this environment (adjacent, not Cursor core)

The Cursor-public Slack plugin's `AGENTS.md` / `Makefile` define two layers: **unit** (`tests/unit/`, frontmatter/naming/markdown) and **eval** (`make test-eval` → DeepEval on `tests/eval/`). Eval scenarios are `prompt` + `accepted_tools`; an LLM (Gemini) picks a tool/skill. CI runs `make test-eval`. This is AFK tool-selection judging, not HITL Sitting recording.

Sources: `/home/agent/.cursor/plugins/cache/cursor-public/slack/e75b0cf18f1a19f3fd629e3af9565ee84b8c2ce0/AGENTS.md` ; same tree `Makefile` ; `tests/eval/test_tool_selection.py`

---

## 6. HITL specifically — vendors are silent

Automated skill evals that vendors document are AFK: one prompt (plus optional input files) → agent run in a fresh/isolated context → outputs/transcript → assertions or a human looking at files afterwards.

What the opened pages do **not** describe:

- Evaluating a skill that must interview a human turn-by-turn.
- Evaluating confirm-before-write (a yes to an interview question is not confirm — this repo's protocol; vendors do not discuss that ritual).
- A "Sitting log" file format.
- Pytest fixtures that drive a live HITL conversation.
- A checklist *in* `SKILL.md` used as the eval recorder (checklists are agent progress, §4 / §5).

Closest vendor language for non-mechanical quality: skill-creator's "subjective outputs … better evaluated qualitatively" and evaluating-skills' human `feedback.json` after AFK runs. That is still post-hoc review of produced files, not a live interview grade.

Sources: https://raw.githubusercontent.com/anthropics/skills/main/skills/skill-creator/SKILL.md ; https://agentskills.io/skill-creation/evaluating-skills ; Cursor/Codex/spec pages in §§1–4 (no HITL-eval section on the pages opened)

---

## 7. This repo — what already exists

### Authoring package-contract pytest (not Sitting behaviour)

These four files state their unit in the module docstring: the on-disk skill/package a loader can see — **not interview or write behaviour, and not application Python**. They assert: file exists; `disable-model-invocation: true`; one-line description without "use when"; Codex sidecar `allow_implicit_invocation: false`; pointer at `../master-cv-write-protocol.md`; portable wording (no Cursor tool names, no Claude `` !` `` / `$CLAUDE_`). Router tests also assert three user-invoked skills and that the protocol is **not** a skill directory.

Sources: `tests/test_authoring_content_interview_package.py` ; `tests/test_authoring_design_pins_package.py` ; `tests/test_authoring_router_package.py` ; `tests/test_authoring_write_protocol_package.py`

### In-skill "Done when…" — completion criteria, not an eval recorder

Authoring `SKILL.md` files and `master-cv-write-protocol.md` end steps with **Done when …** (Slice nominated, gaps filled, protocol finished, user confirmed, file replaced). That matches this repo's `writing-for-agents` completion-criterion lever: the agent can tell done from not-done. It is not a log written after a Sitting and not a pytest assertion.

Sources: `.agents/skills/master-cv-content-interview/SKILL.md` ; `.agents/skills/master-cv-design-pins/SKILL.md` ; `.agents/skills/master-cv-authoring/SKILL.md` ; `.agents/skills/master-cv-write-protocol.md` ; `.agents/skills/writing-for-agents/SKILL.md`

### Glossary (Sitting ≠ pytest)

**Master CV Authoring** is the user-invoked HITL skill family. **Sitting** is from the first Authoring `/name` in a conversation through abort or one Authoring write protocol confirm. ADR-0018: the draft is that conversation; **there is no Sitting store**.

Sources: `CONTEXT.md` ; `docs/adr/0018-master-cv-authoring.md`

### Wayfinder — research findings file + GitHub resolution comment

Wayfinder **research** tickets (AFK) are resolved by a `/research` subagent. Charting captures findings on a throwaway `research/<name>` branch with a context pointer from the ticket. Working the map: post the answer as a **resolution comment**, close the issue, append a gist+link to the map's Decisions-so-far. HITL vs AFK is ticket *type* (grilling/prototype vs research), not an eval format.

The research skill's job is: write findings to a **single Markdown file** in the repo, citing sources.

Tracker ops: resolve = `gh issue comment` then close then map pointer.

Sources: `.agents/skills/wayfinder/SKILL.md` ; `.agents/skills/research/SKILL.md` ; `docs/agents/issue-tracker.md`

### Grilling — conversation; this repo also keeps local outcome markdown

`grilling/SKILL.md` runs a design-tree interview until the frontier is empty; it does **not** instruct writing an outcome file. This repo nevertheless has many `.scratch/*-grill-outcome.md` files (e.g. `.scratch/content-interview-skill-grill-outcome.md`) that record ticket, decision tables, and parked items. Those are local grilling transcripts, not a vendor eval harness.

Sources: `.agents/skills/grilling/SKILL.md` ; `.scratch/content-interview-skill-grill-outcome.md` ; glob `.scratch/*-grill-outcome.md`

`grill-me` only says "Run a `/grilling` session."

Source: `.agents/skills/grill-me/SKILL.md`

### diagnosing-bugs / tdd — not Authoring Sittings

`diagnosing-bugs` is a **pass/fail signal** for a *bug* (failing test, curl, HITL bash last resort). `tdd` is pytest/unittest for **application** seams. Neither is a Sitting log.

Sources: `.agents/skills/diagnosing-bugs/SKILL.md` ; `.agents/skills/tdd/SKILL.md`

### Pytest layout under `tests/`

Besides the four Authoring package-contract files, `tests/test_*.py` exercise **Assistant** behaviour (catalog, crawl, prepare, enrichment, LLM run, packets, UI). Not Authoring Sittings.

Source: `tests/` directory listing

### Confirmed absences

No `evals/` directory, no `eval.md`, no Sitting log file, no skill-eval fixture in this repo (search for `evals/`, `eval.md`, Sitting log, skill-eval besides this ticket's own question text).

Source: repo glob/grep under `/Users/chenxiuxia/Desktop/ust-career-center-searcher`

---

## 8. Reuse without inventing a harness

Distinguish (a) vendors, (b) this repo, (c) recording convention. This section does **not** design the Sitting eval protocol (later grilling) and does **not** recommend changing ADR-0018.

### (a) Vendors document

- **Skill quality eval (AFK):** `evals/evals.json` + workspace `grading.json` (PASS/FAIL + evidence) + `benchmark.json` + optional `feedback.json`. Owner: agentskills.io evaluating-skills and Claude Code skill-creator. Not Cursor. Not Codex skills docs.
- **Trigger eval (AFK):** query JSON + trigger rate. Owner: agentskills.io optimizing-descriptions.
- **Agent-loop transcript for someone else's scorer:** Cursor SDK / CLI JSON. Owner: Cursor evals + CLI.
- **Forward-test then look at artifacts:** Codex skill-creator Independent Forward-Testing. No file schema.
- **HITL skill eval:** not documented on the pages opened.

### (b) This repo already has

- Package-contract pytest for Authoring skills (exists / user-invoked / portable wording).
- In-skill Done-when criteria (agent steps).
- Wayfinder + research: findings markdown in-repo; resolution as GitHub comment.
- `.scratch/*-grill-outcome.md` for grilling decisions.
- App pytest under `tests/` (Assistant, not Authoring).

### (c) Recording *shape* later tickets can adopt if it already exists

| Shape | Exists where | Reuse vs harness |
| --- | --- | --- |
| Markdown findings / outcome file under `.scratch/` | This repo (research + grill-outcome) | **Reuse** for a human Sitting verdict (pass/fail + evidence in prose). Same family as wayfinder research recording. |
| GitHub issue resolution comment | wayfinder / issue-tracker | **Reuse** as the canonical ticket answer once grilling decides pass/fail. |
| `evals/evals.json` + `grading.json` PASS/FAIL + evidence | Agent Skills / skill-creator | **File convention only.** Filling those files from a live HITL Sitting would be a new mapping (interview turns are not `prompt`/`expected_output`/`files`). Running skill-creator subagents against Authoring would **import a harness** this repo does not have, and would skip the human-in-the-loop the skills require. |
| Package-contract pytest | `tests/test_authoring_*_package.py` | **Reuse as-is** for loader contract. Extending it to Sitting behaviour would be a new harness. |
| In-skill Done-when / checklists | Authoring SKILL.md; writing-for-agents | **Not a recorder.** Later tickets can *read* these as the behaviour to judge; they do not write the verdict. |
| Cursor SDK transcript | Cursor evals | **Inventing a harness** if used as the Sitting runner (stateless `Agent.prompt` vs multi-turn HITL). |
| Slack `make test-eval` / DeepEval | Slack plugin only | **Not reusable** without adopting that plugin's pytest+Gemini stack; it grades tool *selection*, not Sittings. |
| Codex Independent Forward-Testing | Codex skill-creator | Informal "run a realistic request, review artifacts" — still AFK unless a human plays the user. No schema to copy. |

**Sitting log:** no vendor or in-repo file by that name. The in-repo analogue of "where judgment is recorded" for HITL work is already **markdown in `.scratch/` plus a GitHub comment**, not pytest and not `evals/evals.json`.

---

## Fetch gaps

- `https://cursor.com/docs/llms.txt` — HTTP 404; Cursor pages were fetched individually (`skills.md`, `evals`, CLI, Bugbot, SDK).
- `https://raw.githubusercontent.com/mattpocock/skills/main/skills/productivity/writing-great-skills/SKILL.md` — HTTP 404 (path not at that location). Used this repo's `.agents/skills/writing-for-agents/SKILL.md` and the mattpocock README instead.
- `https://developers.openai.com/codex/use-cases/ai-app-evals` — one WebFetch timeout; Codex **skills** page was fetched via curl and does not point at OpenAI Evals / Promptfoo as how skills are evaluated. The Promptfoo use-case is therefore noted only as a Codex *app* eval path, not as skill-eval recording.
- Claude Code skills pages link a claude.com **blog** announcement for skill-creator background; that URL was **not** used as a source (blogs excluded). Schemas and loop were taken from agentskills.io, code.claude.com/docs, and anthropics/skills raw files.
- `https://developers.openai.com/codex/skills.md` WebFetch timed out once; the same content was retrieved with `curl` (HTTP 308 to the HTML skills page; markdown body as quoted in §3).

---

## Source list

| Source | Owns |
| --- | --- |
| https://cursor.com/docs/skills.md | Cursor skills: discovery, frontmatter; no eval section |
| https://cursor.com/help/customization/skills.md | Cursor Help skills: create/invoke; no eval section |
| https://cursor.com/docs/evals | Cursor SDK inside *your* eval harness; transcript + `RunResult`; score with your tools |
| https://cursor.com/docs/sdk/typescript.md | SDK loads workspace skills; stream/transcript API |
| `/home/agent/.cursor/skills-cursor/sdk/SKILL.md` | Inspect transcript on failed SDK run |
| `/home/agent/.cursor/skills-cursor/create-skill/SKILL.md` | Sample in-skill review checklist; not skill-eval recording |
| `/home/agent/.cursor/skills-cursor/statusline/SKILL.md` | CLI `transcript_path` payload |
| https://cursor.com/docs/cli/using.md | CLI `--print` / output formats |
| https://cursor.com/docs/cli/reference/output-format.md | `json` / `stream-json` session output |
| https://cursor.com/docs/cli/changelog.md | Transcripts persist; headless JSONL |
| https://cursor.com/docs/bugbot.md | PR review, not skill evals |
| https://cursor.com/docs/agent/agent-review.md | Local change review, not skill evals |
| https://cursor.com/docs/cloud-agent.md | Cloud run artifacts/logs |
| https://cursor.com/docs/cloud-agent/capabilities.md | Cloud run transcript tool |
| https://code.claude.com/docs/en/skills.md | Evaluate-and-iterate; skill-creator artifacts |
| https://docs.anthropic.com/en/docs/claude-code/skills | Same Claude Code skills + eval section |
| https://raw.githubusercontent.com/anthropics/skills/main/skills/skill-creator/SKILL.md | skill-creator loop, qualitative vs quantitative |
| https://raw.githubusercontent.com/anthropics/skills/main/skills/skill-creator/references/schemas.md | `evals.json`, `grading.json`, `benchmark.json`, `feedback.json` |
| https://raw.githubusercontent.com/anthropics/skills/main/README.md | Example skills; "test in your environment" |
| https://docs.anthropic.com/en/docs/claude-code/goal | `/goal` verdicts in session transcript |
| https://docs.anthropic.com/en/docs/claude-code/monitoring-usage | `skill_name` telemetry |
| https://developers.openai.com/codex/skills.md | Codex skills; "test prompts against the description" |
| https://developers.openai.com/codex/use-cases/reusable-codex-skills.md | Correct the skill from real use in chat |
| https://raw.githubusercontent.com/openai/codex/main/codex-rs/skills/src/assets/samples/skill-creator/SKILL.md | `quick_validate.py`; Independent Forward-Testing |
| https://raw.githubusercontent.com/openai/codex/main/docs/skills.md | Redirect to developers.openai.com skills |
| https://agentskills.io/specification | Format spec; no evals |
| https://agentskills.io/skill.md | Creator workflow including evals |
| https://agentskills.io/skill-creation/evaluating-skills | `evals/evals.json`, grading, benchmark, `feedback.json` |
| https://agentskills.io/skill-creation/optimizing-descriptions | Trigger-query JSON and trigger rate |
| https://agentskills.io/skill-creation/best-practices | In-skill checklists; pointer to evaluating-skills |
| https://agentskills.io/llms.txt | Official page index |
| https://raw.githubusercontent.com/mattpocock/skills/main/README.md | Skill set; no eval harness |
| https://github.com/mattpocock/skills/issues/722 | Proposed behavioural eval guidance (not shipped) |
| Slack plugin `AGENTS.md` / `Makefile` / `tests/eval/test_tool_selection.py` | Adjacent `make test-eval` (DeepEval tool selection) |
| `tests/test_authoring_*_package.py` | On-disk package contract, not Sitting |
| `.agents/skills/master-cv-*/SKILL.md` ; `master-cv-write-protocol.md` | Done-when completion criteria |
| `CONTEXT.md` ; `docs/adr/0018-master-cv-authoring.md` | Sitting glossary; no Sitting store |
| `.agents/skills/wayfinder/SKILL.md` ; `research/SKILL.md` ; `docs/agents/issue-tracker.md` | Findings file + resolution comment |
| `.agents/skills/grilling/SKILL.md` ; `.scratch/*-grill-outcome.md` | Interview skill vs local outcome markdown |
| `.agents/skills/diagnosing-bugs/SKILL.md` ; `tdd/SKILL.md` | Bug pass/fail; app TDD |
| `tests/` | Assistant pytest, not Authoring Sittings |
