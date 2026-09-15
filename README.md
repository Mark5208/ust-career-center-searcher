# Job Finding Assistant

A **personal local tool** that crawls the [HKUST Career Center Job Board](https://career.hkust.edu.hk/web/job.php), assesses fit against one user's Master CV, Hard Constraints, and Preferences, and prepares a Tailored CV for selected Job Postings.

It does **not** submit applications. It does **not** store Job Board passwords.

**Unofficial.** Not affiliated with the HKUST Career Center.

## Run it

Python **3.12+**. From a clone:

```bash
pip install -e .
playwright install chromium   # once, for live Job Board Crawls
```

LLM calls (assessment and Prepare) need an API key in the **same shell** that starts the app. Do not put keys in the repo, in Issues, or in this README. Operator notes: [`docs/llm-api-key-security.md`](docs/llm-api-key-security.md).

```bash
# Prefer `read -s` rather than pasting a key on an `export` line (shell history).
read -s JOB_FINDING_ASSISTANT_LLM_API_KEY
export JOB_FINDING_ASSISTANT_LLM_API_KEY
job-finding-assistant          # http://127.0.0.1:8000
```

Optional: `JOB_FINDING_ASSISTANT_LLM_BASE_URL` and `JOB_FINDING_ASSISTANT_LLM_MODEL` for a non-OpenAI OpenAI-compatible host. The app does not load `.env` itself.

Local catalog and Preparation Packets live under `~/.job_finding_assistant/` — not API keys.

## Job Board login

Crawls use **User-Attended Login**: the tool opens a browser; you complete Job Board login (including DUO); then you start the Crawl. No board passwords are stored.

## Candidate files

In the app (`/candidate`), point at:

- **Master CV** — your RenderCV YAML on disk. The tool does not overwrite it during Crawl or Prepare.
- **Hard Constraints** — optional plain-text deal-breakers.
- **Preferences** — optional plain-text soft wants.

A fictional sample Master CV is [`examples/sample_master_CV.yaml`](examples/sample_master_CV.yaml). Keep a real Master CV out of git (`private/` is gitignored).

## Using it

1. Log in, set Crawl Filters, run a Crawl.
2. Set Candidate files, then assess Pending Job Postings from the catalog.
3. Open a Match Assessment; **Prepare** builds a Preparation Packet (Gap Report, Edit Summary, Tailored CV YAML/PDF). Re-Prepare overwrites after confirm.

You remain the applicant of record.

## Secrets

If you find a leaked credential in this repository, **do not paste it into a public issue.** See [`SECURITY.md`](SECURITY.md).

## This is a personal tool

Source is available to clone or fork. Issues are the owner's tracker. Unsolicited pull requests may be ignored or closed.

MIT licensed (`LICENSE`).
