# Security

This is a source-available **personal** tool. There is no bounty and no response SLA.

## Do not file secrets in public

**Do not** paste API keys, tokens, passwords, a real Master CV, or Job Board session material into GitHub Issues, pull requests, or Discussions.

## How to report a leaked credential

1. **Rotate** the credential at the provider if it is still live.
2. Report **privately** via GitHub: [Report a vulnerability](https://github.com/Mark5208/ust-career-center-searcher/security/advisories/new) (Security tab → *Report a vulnerability*).
3. In that report, name the **location** (path, commit SHA, or issue URL) and the **kind** of secret. **Do not include the secret value.**

If that form is not available, open a public issue titled only that you need a private channel for a credential report — still **without** the secret — and wait for a private follow-up.

The same private channel is fine for other security issues. Do not use it to request features.

## Operator LLM keys

Live LLM credentials are **environment-only**. They must never go in the repo, in `~/.job_finding_assistant/`, or in a public issue. See [`docs/llm-api-key-security.md`](docs/llm-api-key-security.md).
