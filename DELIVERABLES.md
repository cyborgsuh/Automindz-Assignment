# DELIVERABLES — Submission Checklist

Tick every box before you submit. Items marked **(required)** are P0 — without them we cannot review your work.

---

## Repository hygiene

- [x] Public GitHub repository (required)
- [x] Code is written in **Python** (required)
- [x] At least **one pull request** opened (and merged) via **Claude Code or Codex**, visible in the repo's PR history (required)
- [x] `README.md` at the root explaining how to clone, install, configure, and run (required)
- [x] `.env.example` listing every required env var, no values (required)
- [x] `.gitignore` excludes `.env`, `__pycache__/`, `.venv/`, and any `output/` artifacts you choose not to commit (required)
- [x] No committed secrets — we will grep your repo (required)
- [x] No hardcoded URLs, project IDs, or account-scoped values — everything account-specific reads from env vars (required)
- [x] Open-source license file (`LICENSE`, MIT or Apache-2.0 is fine)
- [x] (Optional) Hours-spent self-report at the top of the README

---

## Supabase output

When we swap our credentials into your `.env` and run the pipeline against a **blank** Supabase project, we expect:

- [x] Schema (`jobs`, `companies`, `contacts`) is created from code (migration / `CREATE TABLE IF NOT EXISTS` / supabase CLI / ORM) — no manual table creation in our project (required)
- [x] `jobs` table is populated by the Apify scrape stage (required)
- [x] `companies` table is populated with ICP-qualified companies + fit-check rationale (required)
- [x] `contacts` table is populated with validated decision-makers, linked back to the company and the surfacing job(s) (required)
- [x] Relationships between the three tables are coherent (foreign keys, join table for multi-job contacts, etc.) — design is your call but it must hold up (required)
- [x] Rerunning the pipeline against an already-populated DB does not produce duplicate rows (P1)

---

## Pipeline outputs (committed in `output/`)

- [x] `output/run_summary.json` — last-run stats (P1)
- [x] `output/active_client_hiring.csv` — only if you implemented the P2 bonus (P2)
- [x] (Optional) `output/icp_fit_decisions.csv` — your fit-check audit trail; we love seeing these

---

## Code expectations

- [x] Pipeline runs end-to-end with a single command (e.g. `python -m pipeline`, `make run`) (required)
- [x] All credentials and account-scoped values read from env vars — pipeline works after swapping `.env` values, with no code changes (required)
- [x] Apify scrape stage uses the ICP keywords + locations + last-7-days filter from `ICP.md` (required)
- [x] Active-client exclusion happens before the ICP fit-check (required)
- [x] ICP fit-check uses a web-enabled OpenRouter model and reads real company website content (required)
- [x] DMM step uses the AI Ark `people_search` HTTP API, capped at max 2 results per call, logs which cascade level returned each person (required)
- [x] LLM hiring-manager validation gates every contact, with the reason logged for every drop (required)
- [x] Schema creation is idempotent (running it twice doesn't fail) (P1)
- [ ] (P2 bonus) `mcp.json` in the repo wiring up the AI Ark MCP server, so reviewers can plug their account into Claude Code / Cursor alongside the API-driven pipeline

---

## Documentation expectations

- [x] README explains:
  - [x] What the pipeline does (one paragraph)
  - [x] How to run it from a fresh clone, including how to swap `.env` credentials so our keys work without code changes (required)
  - [x] Which OpenRouter models you chose for which stage and **why** (required)
  - [x] How the Supabase tables relate to each other (a short ER sketch is plenty) (required)
  - [x] What you cut for time and what you'd do with another day
- [ ] (P2) A short `docs/adr-XXX-*.md` for at least one non-obvious design choice — the Supabase relationship design is a natural fit

---

## Submission steps

1. Final commit + push to a public GitHub repo, with at least one merged PR opened via Claude Code or Codex.
2. Reply to the interview email with:
   - The repo URL
   - A link to the Claude Code / Codex PR(s)
   - (Optional) self-reported hours
   - Any clarifications about scope cuts or partial features

We aim to give you feedback within 5 working days of submission.
