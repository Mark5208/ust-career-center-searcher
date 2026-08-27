# Research: portable skill loading

Question: what do Cursor, Claude Code, Codex, and this repo's `.agents/skills/` + `agents/openai.yaml` layout actually load? What must a `SKILL.md` avoid to stay portable (no Cursor-only tools)? Where should Master CV Authoring skills live?

Primary sources only. Each claim cites the source that owns it.

## Verdict

One copy under `.agents/skills/<name>/SKILL.md` (plus Codex sidecar `agents/openai.yaml`) is the portable project layout. Cursor and Codex load that path natively. Claude Code's official discovery list does **not** include `.agents/skills/` — it loads `.claude/skills/` (and plugins / personal / enterprise). This repo currently has the `.agents/skills/` copy and no `.claude/skills/` symlink, so Claude Code will not auto-discover these skills unless a peer adds a Claude-side copy, symlink, or plugin.

Authoring skills should live as three user-invoked skills plus one plain write-protocol file (not a fourth skill) under `.agents/skills/`. Keep `SKILL.md` bodies on generic verbs and relative paths; do not name Cursor tools (`AskQuestion`, `CallMcpTool`) or Claude-only injection syntax.

---

## 1. Discovery paths

### Agent Skills open format (shared package shape)

A skill is a directory whose required entry file is `SKILL.md` (YAML frontmatter + markdown body). Optional conventional dirs: `scripts/`, `references/`, `assets/`. Required frontmatter: `name`, `description`. Optional spec fields: `license`, `compatibility`, `metadata`, `allowed-tools`.

Source: https://agentskills.io/specification

The spec's own skill page names discovery as:

| Scope | Path |
| --- | --- |
| Project | `.agents/skills/` (cross-client standard) and `.<client>/skills/` (client-specific) |
| User | `~/.agents/skills/` and `~/.<client>/skills/` |

Source: https://agentskills.io/skill.md

Progressive disclosure (all three products claim this pattern): load `name` + `description` at startup; load the `SKILL.md` body only when the skill is activated; load referenced files only when needed.

Sources: https://agentskills.io/specification ; https://cursor.com/docs/skills.md ; https://developers.openai.com/codex/skills.md ; https://docs.anthropic.com/en/docs/claude-code/skills

### Cursor — skills

Official load table:

| Location | Scope |
| --- | --- |
| `.agents/skills/` | Project |
| `.cursor/skills/` | Project |
| `~/.agents/skills/` | User (global) |
| `~/.cursor/skills/` | User (global) |

Compatibility extras: `.claude/skills/`, `.codex/skills/`, `~/.claude/skills/`, `~/.codex/skills/`.

Each skill is a folder containing `SKILL.md`. Cursor walks a skills root recursively (category folders are organizational; identity is the folder that contains `SKILL.md`). A `.cursor/skills/` or `.agents/skills/` folder **anywhere** in the repo is picked up; nested project skills are auto-scoped to that directory (same idea as the `paths` frontmatter field).

Cursor frontmatter it documents: `name` (required, must match parent folder), `description` (required), `paths` (optional globs), `disable-model-invocation` (optional; `true` = only `/skill-name`), `metadata` (optional). Legacy `globs` still accepted.

Manual `/create-skill` help still shows creating `.cursor/skills/your-skill-name/SKILL.md` as the typed example; the reference table lists `.agents/skills/` first.

Sources: https://cursor.com/docs/skills.md ; https://cursor.com/help/customization/skills

Cursor built-in create-skill (Cursor-primary, not a repo file) stores personal skills at `~/.cursor/skills/` and project skills at `.cursor/skills/`, and forbids writing `~/.cursor/skills-cursor/` (reserved for Cursor built-ins). It also tells the author to use the `AskQuestion` tool when available.

Source: `/home/agent/.cursor/skills-cursor/create-skill/SKILL.md`

### Cursor — AGENTS.md / rules / CLAUDE.md

- Project rules: `.cursor/rules/*.mdc` (plain `.md` in that folder is ignored).
- `AGENTS.md`: project root and nested subdirectories; nested files apply when working in that directory; more specific instructions take precedence.
- Cursor CLI also reads `AGENTS.md` **and** `CLAUDE.md` at the project root and applies them as rules alongside `.cursor/rules`.

Sources: https://cursor.com/docs/rules.md ; https://cursor.com/docs/cli/using.md

This repo has root `AGENTS.md` (the `## Agent skills` block written by `/setup-matt-pocock-skills`) and no `CLAUDE.md`.

Source: `AGENTS.md` ; `.agents/skills/setup-matt-pocock-skills/SKILL.md`

### Claude Code — skills

Official project/personal table (no `.agents/skills/` row):

| Location | Path |
| --- | --- |
| Enterprise | managed settings |
| Personal | `~/.claude/skills/<name>/SKILL.md` |
| Project | `.claude/skills/<name>/SKILL.md` |
| Plugin | `<plugin>/skills/<name>/SKILL.md` |

Also still loads `.claude/commands/*.md` (merged into skills; a same-named skill wins).

Discovery rules Claude Code owns:

- Project skills load from `.claude/skills/` in the start directory **and every parent up to the repository root**.
- Nested `.claude/skills/` **below** the start directory load on demand the first time Claude reads/edits a file in that subdirectory; name clashes become directory-qualified (`/apps/web:deploy`).
- `--add-dir` / `/add-dir` also load `.claude/skills/` and `.claude/commands/` from the added directory.
- A skill directory may be a **symlink**; Claude Code follows it and de-dupes the same target.
- Cloud / Cowork sessions do **not** read `~/.claude/skills/` on the machine; they load claude.ai-enabled skills plus repo `.claude/skills/`.

Sources: https://docs.anthropic.com/en/docs/claude-code/skills ; https://code.claude.com/docs/en/skills

Claude Code follows Agent Skills and then **extends** it. Spec fields vs Claude-only fields are called out in "Using skill frontmatter outside Claude Code":

- Spec (portable packaging / claude.ai upload / Skills API): `name`, `description`, `license`, `compatibility`, `metadata`, `allowed-tools`.
- Extra keys (`disable-model-invocation`, `when_to_use`, `argument-hint`, `context`, `agent`, `hooks`, `paths`, …) are accepted **inside Claude Code**. The same extra keys are a **hard error** on claude.ai upload / `package_skill.py` ("Unexpected key(s) in SKILL.md frontmatter").

`disable-model-invocation: true` is the Claude Code control that hides the skill from automatic / Skill-tool invocation (user types `/name`). Default `false`.

Sources: https://docs.anthropic.com/en/docs/claude-code/skills

### Claude Code — CLAUDE.md / AGENTS.md

Claude Code reads `CLAUDE.md`, **not** `AGENTS.md`. Official locations (broad → specific): managed policy `CLAUDE.md`, `~/.claude/CLAUDE.md`, `./CLAUDE.md` or `./.claude/CLAUDE.md`, `./CLAUDE.local.md`. Nested `CLAUDE.md` files above cwd load at launch; subdirectory files load on demand.

To share one instruction file with other agents: put `@AGENTS.md` at the top of `CLAUDE.md`, or `ln -s AGENTS.md CLAUDE.md`.

Source: https://docs.anthropic.com/en/docs/claude-code/memory

This repo has `AGENTS.md` and no `CLAUDE.md`, so a Claude Code session does not load the root agent-skills pointer unless a peer adds that import/symlink.

### Codex (OpenAI) — skills

Official scan (current docs):

| Scope | Location |
| --- | --- |
| REPO | `.agents/skills` in **every directory from CWD up to the repository root** |
| USER | `$HOME/.agents/skills` |
| ADMIN | `/etc/codex/skills` |
| SYSTEM | bundled with Codex |

Same-`name` skills are not merged; both can appear. Symlinked skill folders are followed.

Invocation: explicit `$skill` / `/skills` / ChatGPT `@`; implicit from `description` unless policy forbids it.

Optional sidecar **inside the skill directory**: `agents/openai.yaml` — ChatGPT desktop UI metadata (`interface.display_name`, `interface.short_description`, icons, `default_prompt`), invocation policy, and MCP tool dependencies.

```yaml
policy:
  allow_implicit_invocation: false
```

Default of `allow_implicit_invocation` is `true`. When `false`, Codex will not implicitly invoke from the prompt; explicit `$skill` still works.

Sources: https://developers.openai.com/codex/skills.md ; https://developers.openai.com/codex/concepts/customization.md

Customization table (same product):

| Layer | Global | Repo |
| --- | --- | --- |
| AGENTS | `~/.codex/AGENTS.md` | `AGENTS.md` in repo root or nested directories |
| Skills | `~/.agents/skills` | `.agents/skills` in repo |

Source: https://developers.openai.com/codex/concepts/customization.md

First-party history (openai/codex): repo loading from `.agents/skills/` was added because a single `.agents/` location avoids symlink/duplication across agents; `.codex/skills/` "will remain but will be deprecated" for REPO scope. User loading from `$HOME/.agents/skills` was added next, keeping `~/.codex/skills` for compatibility until deprecation.

Sources: https://github.com/openai/codex/pull/10317 ; https://github.com/openai/codex/pull/10437

The current official "Where Codex loads local skills" table no longer lists `.codex/skills` as a REPO path. The skills.sh installer still maps Codex **global** installs to `~/.codex/skills/` (see §2).

### Codex — AGENTS.md

Discovery (once per run):

1. Global: `~/.codex/AGENTS.override.md` if present, else `~/.codex/AGENTS.md` (`CODEX_HOME` overrides the home).
2. Project: from git root down to CWD, at most one file per directory, checking `AGENTS.override.md`, then `AGENTS.md`, then `project_doc_fallback_filenames`.
3. Concatenate root → cwd; later (closer) files override. Default cap `project_doc_max_bytes` = 32 KiB.

Codex does not read `CLAUDE.md` unless that name is added to the fallback list.

Source: https://developers.openai.com/codex/guides/agents-md.md

---

## 2. What this repo's `.agents/skills/` + `agents/openai.yaml` layout means

### Verified on-disk facts (this repo)

- Skills live at `.agents/skills/<name>/SKILL.md`. Example: `.agents/skills/grilling/SKILL.md`.
- Almost every skill also has `.agents/skills/<name>/agents/openai.yaml`.
- User-invoked skills set `disable-model-invocation: true` in `SKILL.md` **and** `policy.allow_implicit_invocation: false` in `agents/openai.yaml` (example: `.agents/skills/grill-me/`, `.agents/skills/wayfinder/`).
- Model-invoked skills omit both (example: `.agents/skills/grilling/agents/openai.yaml` is only `interface.display_name` / `short_description`).
- Shared reference beside a skill is a **plain sibling file**, not a fourth skill: `.agents/skills/writing-for-agents/SKILL-MECHANICS.md`, reached by a pointer from `SKILL.md`.
- Install lockfile `skills-lock.json` pins each skill to `source: mattpocock/skills`, `sourceType: github`, a `skillPath`, and a `computedHash`.
- There is **no** `.claude/skills/`, **no** `.cursor/skills/`, **no** `.codex/skills/`, and **no** `CLAUDE.md` in this repo.

Sources: this repo's `.agents/skills/`, `skills-lock.json`, `AGENTS.md`

### mattpocock / agentskills packaging

mattpocock/skills ships each skill as `SKILL.md` plus `agents/openai.yaml` so the **same files** work in Claude Code and Codex without generated copies.

Invocation contract (mattpocock first-party):

- **User-invoked:** `disable-model-invocation: true` (Claude Code) **and** `policy.allow_implicit_invocation: false` (Codex). Description is human-facing; strip "Use when…" trigger lists.
- **Model-invoked:** omit both. Description is model-facing and keeps trigger phrasing.
- Keep the two harnesses in sync: user-invoked in both or neither.
- Cross-skill reach is `/skill`-style prose ("Run the `/grilling` skill"), not `../other-skill/FILE.md` links. Shared reference that two **user-invoked** skills both need cannot live in either skill (neither can fire the other); it goes to a plain file outside the skill system.

Sources: https://raw.githubusercontent.com/mattpocock/skills/main/.agents/invocation.md ; https://raw.githubusercontent.com/mattpocock/skills/main/README.md ; this repo `.agents/skills/writing-for-agents/SKILL-MECHANICS.md`

Codex does **not** honor `disable-model-invocation` by itself. Without `agents/openai.yaml`, `allow_implicit_invocation` defaults to `true`, so a "user-invoked" skill can still be implicitly selected. That is why every skill in this set carries the sidecar.

Sources: https://developers.openai.com/codex/skills.md ; https://github.com/mattpocock/skills/issues/516 ; https://github.com/mattpocock/skills/commit/697d4ce9742da558fd1ba6697c8e9775e2e302dd

### Which agents load this repo's copy with no extra copies

| Agent | Loads `.agents/skills/<name>/SKILL.md` as-is? | Extra copy needed? |
| --- | --- | --- |
| **Cursor** | Yes. Official project path. | No. Do not also write `.cursor/skills/`. |
| **Codex** | Yes. Official REPO scan is `.agents/skills` from CWD to root. Reads `agents/openai.yaml` from that same folder. | No. Do not also write `.codex/skills/` (deprecated REPO path). |
| **Claude Code** | **No**, not from official discovery. Official project path is `.claude/skills/`. | Yes: symlink/copy into `.claude/skills/<name>`, or install the Claude Code plugin (`claude plugins install mattpocock-skills`) for the upstream set, or `--add-dir` at a tree that already has `.claude/skills/`. Skill **directories** may be symlinks. |
| **Peers that follow Agent Skills** (Cline, Copilot, Gemini CLI, … per skills.sh) | Yes if they treat `.agents/skills/` as the universal project dir. | Usually no. |

Sources: https://cursor.com/docs/skills.md ; https://developers.openai.com/codex/skills.md ; https://docs.anthropic.com/en/docs/claude-code/skills ; https://raw.githubusercontent.com/vercel-labs/skills/main/README.md ; https://raw.githubusercontent.com/vercel-labs/skills/main/src/agents.ts

### How the installer thinks about this layout

`npx skills add` (vercel-labs/skills, the CLI behind skills.sh / this repo's `skills-lock.json`) writes a **canonical** copy under `.agents/skills/` and, for agents whose project path is **not** `.agents/skills/`, optionally symlinks or copies into the agent-specific dir.

Installer project paths (first-party table):

| Agent | Project path | Global path |
| --- | --- | --- |
| Cursor | `.agents/skills/` | `~/.cursor/skills/` |
| Codex | `.agents/skills/` | `~/.codex/skills/` |
| Claude Code | `.claude/skills/` | `~/.claude/skills/` |

Cursor and Codex are "universal" agents in that source (`skillsDir === '.agents/skills'`): they share the canonical directory and do not need a second project copy. Claude Code is a non-universal agent: it needs `.claude/skills/` (symlink recommended).

This repo's working tree has the canonical `.agents/skills/` tree and **no** `.claude/skills/` links, which matches "installed for Cursor/Codex/universal, not also for Claude Code."

Sources: https://raw.githubusercontent.com/vercel-labs/skills/main/README.md ; https://raw.githubusercontent.com/vercel-labs/skills/main/src/agents.ts ; https://github.com/mattpocock/skills/blob/main/README.md

---

## 3. Portability bar — what binds a SKILL.md to one harness

### Stay portable (safe in Cursor + Claude Code + Codex + Agent Skills peers)

Write the body as markdown steps any agent can follow with **generic** tools: read a file, edit a file, run a shell command, ask the user a question in chat.

- Frontmatter: `name` + `description` (Agent Skills required). `name` matches the parent folder; lowercase / digits / hyphens; no leading, trailing, or consecutive hyphens.
- User-invoked pair (not in the open spec, but both coding harnesses here understand one half): `disable-model-invocation: true` **and** `agents/openai.yaml` `policy.allow_implicit_invocation: false`. Extra keys are ignored by clients that do not implement them; they **fail** claude.ai / Skills API packaging.
- Supporting files: relative paths from the skill root, one level deep (`SKILL-MECHANICS.md`, `references/FOO.md`, `scripts/validate.py`).
- Scripts: Python / Bash, non-interactive, documented deps. Agents run them via their shell tool.
- Ask the user in prose ("ask the user…", numbered questions). Do not name a host-specific question tool.
- If MCP is useful, say "use the project's configured MCP servers if present"; do not require a host-specific MCP caller.

Sources: https://agentskills.io/specification ; https://agentskills.io/skill.md ; https://raw.githubusercontent.com/mattpocock/skills/main/.agents/invocation.md ; this repo `.agents/skills/writing-for-agents/SKILL-MECHANICS.md`

### Binds the skill to Cursor

| Instruction | Why it is Cursor-only |
| --- | --- |
| "Use the AskQuestion tool" / "ask questions tool" | Cursor Agent tool and ACP method `cursor/ask_question`. Cursor's own skills reference even lists "Use the ask questions tool…" as a sample instruction. Claude Code's analog is `AskUserQuestion`; Codex has no such tool name. |
| `CallMcpTool` | Cursor-specific tool name for MCP. Other hosts expose MCP under different tool surfaces. |
| Paths `~/.cursor/skills-cursor/`, exclusive `.cursor/skills/` | Cursor reserved / Cursor-only trees. Official Cursor also loads `.agents/skills/`; writing only `.cursor/skills/` hides the skill from Codex. |
| Built-in Cursor skills as required steps (`/create-skill`, `/create-rule`, `/create-hook`, `/update-cli-config`, `/update-cursor-settings`) | Listed as Cursor built-ins. |
| `paths:` frontmatter as the **only** discovery mechanism | Documented by Cursor (and also by Claude Code). **Not** an Agent Skills spec field. Codex's official skill frontmatter is `name` + `description`. |

Sources: https://cursor.com/docs/skills.md ; https://cursor.com/docs/agent/overview.md ; https://cursor.com/docs/cli/acp.md ; `/home/agent/.cursor/skills-cursor/create-skill/SKILL.md` ; https://docs.anthropic.com/en/docs/claude-code/skills ; https://agentskills.io/specification

### Binds the skill to Claude Code

| Instruction | Why it is Claude-only |
| --- | --- |
| `` !`command` `` / ` ```! ` dynamic context injection | Claude Code pre-runs the command and inlines stdout before the model sees the skill. Documented as not functioning in claude.ai / API; not a Cursor or Codex feature. |
| `${CLAUDE_SKILL_DIR}`, `${CLAUDE_PROJECT_DIR}`, `$ARGUMENTS`, `context: fork`, `agent:`, `hooks:`, `when_to_use`, `user-invocable` | Claude Code frontmatter / substitutions. |
| Requiring `AskUserQuestion` | Named in Claude Code's `disallowed-tools` docs as a Claude tool. |
| `allowed-tools` / `disallowed-tools` with Claude tool names (`Bash(git:*)`, `Read`, `Grep`) | Spec marks `allowed-tools` experimental; the grant/deny semantics and tool names are Claude Code's. |
| Living **only** under `.claude/skills/` | Cursor and Codex will not see it unless they also scan that compatibility path (Cursor does; Codex's current official table does not). |

Sources: https://docs.anthropic.com/en/docs/claude-code/skills ; https://agentskills.io/specification

### Binds the skill to Codex

| Instruction | Why it is Codex-only |
| --- | --- |
| Requiring `$skill-name` as the only invoke syntax | Codex CLI/IDE mention syntax. Cursor and Claude Code use `/skill-name`. |
| MCP **only** via `agents/openai.yaml` `dependencies.tools` | Codex/ChatGPT sidecar. Other hosts configure MCP elsewhere (`.cursor/mcp.json`, Claude `settings.json` / plugins). The sidecar itself is harmless if unused. |
| Living **only** under `.codex/skills/` | Current official REPO scan is `.agents/skills`. `.codex/skills` is the old/deprecated repo path. |

Sources: https://developers.openai.com/codex/skills.md ; https://github.com/openai/codex/pull/10317

### Frontmatter that is portable vs harness-local

| Field | Agent Skills spec | Cursor | Claude Code | Codex |
| --- | --- | --- | --- | --- |
| `name`, `description` | Required | Required | `name` optional (dir name wins for project skills); `description` recommended | Required |
| `license`, `compatibility`, `metadata` | Optional | `metadata` documented | Accepted; not acted on | Not in Codex skill docs |
| `allowed-tools` | Optional, experimental | Not in Cursor skills table | Implemented (turn-scoped grant) | Not in Codex skill docs |
| `disable-model-invocation` | **No** | Yes | Yes | **No** — use `agents/openai.yaml` |
| `paths` | **No** | Yes | Yes | Not in Codex skill docs |
| `agents/openai.yaml` | **No** (sidecar file) | Ignored | Ignored | Official optional metadata |

Sources: https://agentskills.io/specification ; https://cursor.com/docs/skills.md ; https://docs.anthropic.com/en/docs/claude-code/skills ; https://developers.openai.com/codex/skills.md

---

## 4. Recommendation — where Master CV Authoring should live in this repo

### Put the one copy here

```
.agents/skills/
  master-cv-authoring/                 # user-invoked router
    SKILL.md
    agents/openai.yaml
  master-cv-content-interview/         # user-invoked
    SKILL.md
    agents/openai.yaml
  master-cv-design-pins/               # user-invoked
    SKILL.md
    agents/openai.yaml
  master-cv-write-protocol.md          # plain file, not a skill
```

Why this tree:

1. **Cursor and Codex load it with no extra copies.** Official project path for both is `.agents/skills/`.
2. **Agent Skills names `.agents/skills/` as the cross-client standard.**
3. **Matches this repo's existing mattpocock install** (`skills-lock.json` + `.agents/skills/<name>/`).
4. **Router + two user-invoked skills + shared protocol as a plain file** is exactly this repo's writing rules: user-invoked skills cannot invoke each other; shared reference they both need must sit **outside** the skill system. `SKILL-MECHANICS.md` is the in-repo precedent for a sibling plain file; because *two* user-invoked skills need the protocol, it must not live inside either skill as the only copy, and it must not be a fourth `SKILL.md`.

Sources: https://cursor.com/docs/skills.md ; https://developers.openai.com/codex/skills.md ; https://agentskills.io/skill.md ; this repo `.agents/skills/writing-for-agents/SKILL-MECHANICS.md` ; https://raw.githubusercontent.com/mattpocock/skills/main/.agents/invocation.md

### Invocation metadata for each of the three skills

```yaml
# SKILL.md frontmatter
name: master-cv-authoring   # or content-interview / design-pins
description: <one-line human summary; no trigger list>
disable-model-invocation: true
```

```yaml
# agents/openai.yaml
interface:
  display_name: "Master CV Authoring"   # human picker label
  short_description: "<same one-liner>"
policy:
  allow_implicit_invocation: false
```

Do not make the write-protocol file a skill (no directory, no frontmatter, no `openai.yaml`). Each of the three `SKILL.md` files points at it with a relative link, e.g. `[write protocol](../master-cv-write-protocol.md)`.

### What not to do

- Do **not** also author copies under `.cursor/skills/` or `.codex/skills/`. That is duplication; Cursor and Codex already see `.agents/skills/`.
- Do **not** put Authoring only under `.claude/skills/`. Cursor would still see it (compatibility scan); Codex's current official REPO table would not.
- Do **not** require Cursor tools, Claude `` !`…` `` injection, or `$CLAUDE_*` paths in the bodies.
- Do **not** rely on this repo's `AGENTS.md` to load the skills. `AGENTS.md` is always-on instruction text (Cursor + Codex). It does not register `SKILL.md` files. Claude Code will not even read `AGENTS.md` until a `CLAUDE.md` imports it.

### Claude Code / peer gap (this repo, today)

For a Claude Code peer to auto-load the same files without a second authored copy:

1. Symlink (installer-native): `.claude/skills/master-cv-authoring` → `../.agents/skills/master-cv-authoring` (and the same for the other two skill dirs). Claude Code follows skill-directory symlinks.
2. Or run `npx skills add` with `-a claude-code` so the CLI creates those links.
3. Optionally add root `CLAUDE.md` containing `@AGENTS.md` so Claude Code shares the always-on issue-tracker / domain pointers. That still does **not** register `.agents/skills/`; it only shares `AGENTS.md`.

Sources: https://docs.anthropic.com/en/docs/claude-code/skills ; https://docs.anthropic.com/en/docs/claude-code/memory ; https://raw.githubusercontent.com/vercel-labs/skills/main/README.md

### Body-writing rule for Authoring

Keep instructions harness-agnostic:

- "Ask the user the next frontier questions" — not "call AskQuestion".
- "Read `../master-cv-write-protocol.md` before writing YAML" — not a host tool name.
- "If an MCP server for the user's files is already configured, use it; otherwise read the files from disk."
- User-invoked router names the other two skills in `/name` prose and tells the human when to type each; it cannot fire them.

That is the same pattern `grill-me` already uses (`Run a /grilling session.`) and the same invocation split `SKILL-MECHANICS.md` requires.

Sources: this repo `.agents/skills/grill-me/SKILL.md` ; `.agents/skills/writing-for-agents/SKILL-MECHANICS.md`

---

## Source list

| Source | Owns |
| --- | --- |
| https://agentskills.io/specification | Open `SKILL.md` format, frontmatter, progressive disclosure |
| https://agentskills.io/skill.md | Cross-client discovery paths (`.agents/skills/` vs `.<client>/skills/`) |
| https://cursor.com/docs/skills.md | Cursor skill directories, frontmatter, compatibility scans |
| https://cursor.com/help/customization/skills | Cursor help: create/load/scope |
| https://cursor.com/docs/rules.md | Cursor `AGENTS.md` + `.cursor/rules` |
| https://cursor.com/docs/cli/using.md | Cursor CLI also loads root `CLAUDE.md` |
| https://cursor.com/docs/agent/overview.md | Cursor "Ask questions" tool |
| https://cursor.com/docs/cli/acp.md | `cursor/ask_question` |
| `/home/agent/.cursor/skills-cursor/create-skill/SKILL.md` | Cursor built-in authoring (AskQuestion, `.cursor/skills/`) |
| https://docs.anthropic.com/en/docs/claude-code/skills | Claude Code skill paths, frontmatter extensions, no `.agents/skills/` |
| https://docs.anthropic.com/en/docs/claude-code/memory | Claude Code reads `CLAUDE.md`, not `AGENTS.md` |
| https://developers.openai.com/codex/skills.md | Codex skill scan, `$` invoke, `agents/openai.yaml` |
| https://developers.openai.com/codex/concepts/customization.md | Codex AGENTS vs skills table |
| https://developers.openai.com/codex/guides/agents-md.md | Codex `AGENTS.md` walk |
| https://github.com/openai/codex/pull/10317 | Codex adopted `.agents/skills/`; `.codex/skills/` deprecated for REPO |
| https://github.com/openai/codex/pull/10437 | Codex user skills at `~/.agents/skills` |
| https://raw.githubusercontent.com/mattpocock/skills/main/.agents/invocation.md | Dual-harness invocation + `openai.yaml` |
| https://raw.githubusercontent.com/mattpocock/skills/main/README.md | Install: plugin vs `npx skills add` |
| https://raw.githubusercontent.com/vercel-labs/skills/main/README.md | Installer agent → directory map; symlink vs copy |
| https://raw.githubusercontent.com/vercel-labs/skills/main/src/agents.ts | Cursor/Codex universal `.agents/skills/`; Claude Code `.claude/skills/` |
| This repo `.agents/skills/`, `skills-lock.json`, `AGENTS.md`, `.agents/skills/writing-for-agents/SKILL-MECHANICS.md` | Actual layout and writing rules |
