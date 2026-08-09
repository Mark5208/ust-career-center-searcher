# LLM API key security

Operator notes for supplying the live LLM API key safely. Product decision: [ADR-0015](adr/0015-llm-runtime-for-v1.md).

## What the app expects

Set these in the **same shell** that starts `job-finding-assistant`:

| Variable | Required | Purpose |
|----------|----------|---------|
| `JOB_FINDING_ASSISTANT_LLM_API_KEY` | Yes (for live calls) | Bearer token for the OpenAI-compatible host |
| `JOB_FINDING_ASSISTANT_LLM_BASE_URL` | No | API base URL (default OpenAI); e.g. `https://api.deepseek.com` |
| `JOB_FINDING_ASSISTANT_LLM_MODEL` | No | One model for judge + tailor; match the host when not using OpenAI |

Watch the name: **`ASSISTANT`**, not `ASSISTANCE`. A typo yields `LLM Unavailable: API key not configured` even if a key value exists under the wrong name.

The key is read **at process start**. After changing env vars, stop the old server and start a new one (port `8000` stays bound to the previous process otherwise).

## Project rule (ADR-0015)

- Credentials come from the **environment only**.
- No key or model UI, and **no disk-stored secrets in the app**. `~/.job_finding_assistant/` holds catalog, packets, and path state — not API keys.
- The catalog may show a short non-secret **LLM Unavailable** reason. The app must never echo the key.

## Shell-history risk

```bash
export JOB_FINDING_ASSISTANT_LLM_API_KEY='…'
```

often writes the secret into `~/.zsh_history` (or equivalent). Treat that as exposure on this machine.

If a key was pasted into history, chat, screenshots, or committed files: **rotate it at the provider**, then scrub local history if you can.

Prefer not putting the raw value on the command line:

```bash
read -s JOB_FINDING_ASSISTANT_LLM_API_KEY
export JOB_FINDING_ASSISTANT_LLM_API_KEY
```

Or, if `HIST_IGNORE_SPACE` is enabled, a leading space on the `export` line can keep it out of history.

## Safe local patterns (still env to the app)

- Export in the session, then run `job-finding-assistant` from that same terminal.
- Optional operator helper: a **gitignored** `.env` loaded by you (`direnv`, or `set -a; source .env; set +a`) before start. The app does not load `.env` itself.
- Never commit keys. Never put real keys in the repo, docs, or examples.

## Quick verify

1. In the launch shell: `echo ${JOB_FINDING_ASSISTANT_LLM_API_KEY:+set}` prints `set` (does not print the secret).
2. Confirm the name is `JOB_FINDING_ASSISTANT_LLM_API_KEY` (not `…ASSISTANCE…`).
3. Restart `job-finding-assistant` after any env change.
4. Open the Assessment Summary (`/`). It should not show `LLM Unavailable: API key not configured` when the key is present.
