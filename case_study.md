# Case Study: PharmaTalent Europe — Lead Discovery Pipeline

Welcome, and thank you for taking the time. This is the take-home portion of our delivery-engineer interview. Everything you need is in this folder.

---

## How to use this folder

1. Drop this `Case_Study/` folder into your working directory.
2. Open it with your AI coding tool of choice (Claude Code, Codex, Cursor, etc.). For Claude Code: `cd` into the folder and run `claude`.
3. Tell the model: *"Read every `.md` file in this folder in order, then help me plan and build the pipeline described in `case_study.md`."*
4. **Read order:** `ICP.md` → `ACTIVE_CLIENTS.md` → `DMM.md` → `TOOLS.md` → `DELIVERABLES.md` → `EVALUATION.md`.

You may freely use AI assistance. We expect it — that's how we work. Just make sure you understand and stand behind every line you ship.

---

## The scenario

**PharmaTalent Europe** is a (fictional) recruitment agency we just signed. They place PhD-level pharmacists, regulatory affairs leads, clinical operations managers, and clinical research scientists into biotech and pharma companies that operate in Europe.

They want a weekly lead-discovery pipeline that:

- Finds biotech/pharma companies in Europe that are *actively hiring* the kinds of roles PharmaTalent fills.
- Skips companies we already work with (the active-client list).
- Identifies the right hiring manager / talent leader at each qualifying company.
- Stores everything it finds in a structured database, ready to feed downstream outreach tooling.

**You are PharmaTalent's delivery engineer. You have 3 days to build this.**

We expect ~8–12 focused hours of work, not 72. Quality and judgment matter far more than volume.

---

## What you're building

A Python pipeline that runs end-to-end, in this order:

1. **Scrape open biotech jobs** from LinkedIn via Apify's *advanced LinkedIn jobs scraper*. Use the job titles and locations defined in `ICP.md`. Restrict to jobs posted in the **last 7 days**.
2. **Persist every scraped job to Supabase** in a `jobs` table.
3. **Exclude active clients** (per `ACTIVE_CLIENTS.md`) and dedupe the posting-company list.
4. **ICP fit-check** every remaining posting company against the criteria in `ICP.md`. This step **must include a website-research pass** using a web-enabled OpenRouter model (e.g. `perplexity/sonar` or any `:online` variant) — don't rely on LinkedIn metadata alone. Persist the rationale for every keep/drop decision.
5. **Persist every qualifying company to Supabase** in a `companies` table.
6. **Decision-maker mapping** for each ICP-fit company via the **AI Ark `people_search` API** — see `DMM.md`. (Connecting AI Ark's MCP server as an additional channel — e.g. shipping an `mcp.json` in the repo — is a nice plus, but the pipeline itself must call the API directly.)
7. **LLM hiring-manager validation.** For every candidate person, prompt the LLM with the scraped job + the person's title/profile and ask: *"Could this person plausibly be the hiring manager for this role?"* Drop the ones that fail, log the reason for every drop.
8. **Persist every validated contact to Supabase** in a `contacts` table, linked back to the company and the job(s) that surfaced them.
9. **Be rerunnable, idempotent, and observable.** Structured logs + a `run_summary.json` artifact at the end of every run.

### Supabase schema — design it yourself

You need three tables in Supabase: **`jobs`**, **`companies`**, **`contacts`**. The relationships between them (foreign keys, link tables, dedup keys) are **part of what we're evaluating** — figure them out from the pipeline's data flow. Don't over-engineer; do think it through.

---

## Constraints

- **Stack:** Python. Must be cloneable + runnable from a fresh machine following only your README.
- **AI-assisted workflow:** at least **one pull request** in the submission repo must be opened (and merged) via Claude Code or Codex. We want to see the PR in the repo's history — it is part of the deliverable, not just a process suggestion.
- **API keys / accounts:** **we do not provide any API keys.** You create your own **free-tier accounts** for every external tool (Apify, AI Ark, Supabase, OpenRouter). Free tiers are sufficient to build and demo the whole pipeline at the scale we need, **but the free credits are tight — especially on AI Ark.** Read the credit-budget notes in `TOOLS.md` before you start coding, and design your DMM step to stay within them. See `TOOLS.md` for signup links.
- **LLM use:** required. Use OpenRouter. Note in code or README why you chose each model for each step.
- **Secrets:** none in the repo. `.env.example` only.
- **No real PII:** only use data the provider APIs return through the accounts you set up.

### How we'll verify your pipeline

After review, we will **swap the values in your `.env`** for our own Apify / AI Ark / Supabase / OpenRouter credentials and rerun your pipeline. The bar is: **it runs end-to-end on our credentials with no code changes**, and our Supabase project ends up with populated `jobs`, `companies`, and `contacts` tables. If that works, that's a pass on correctness.

Design accordingly:

- Read every credential from environment variables — no hardcoded URLs, project IDs, tokens, or account-specific values.
- Create the Supabase schema from code (a migration script, `supabase db push`, an idempotent `CREATE TABLE IF NOT EXISTS`, or similar) — we don't want to hand-create your tables in our project.

---

## Phased deliverables

### P0 — must have (we don't review further without these)

- Apify LinkedIn jobs scrape runs end-to-end with the ICP keywords + locations + last-7-days filter.
- Scraped jobs land in the Supabase `jobs` table.
- Posting companies are deduped and filtered against `ACTIVE_CLIENTS.md`.
- ICP fit-check filters remaining companies down to a qualified set. **Includes a website-research step** using a web-enabled OpenRouter model.
- Qualifying companies land in the Supabase `companies` table with the fit-check rationale persisted.
- AI Ark `people_search` on qualified companies.
- LLM hiring-manager validation (job + person → keep/drop, with a reason logged for every decision).
- Validated contacts land in the Supabase `contacts` table, linked back to the company and the surfacing job(s).
- Schema is created from code (migration / `CREATE TABLE IF NOT EXISTS` / supabase CLI), not by hand.
- README with run instructions that work on a fresh clone, including how to swap in different credentials.

### P1 — strong candidate

- Idempotent reruns: re-running the pipeline against an already-populated Supabase does not duplicate rows, re-scrape the same jobs, or re-spend AI Ark calls on the same `(company, title)` pairs.
- Dedup handles aliasing — the same person matching multiple jobs at the same company gets one `contacts` row with the job references linked through whatever join you designed.
- Structured logging + a `run_summary.json` artifact.
- Pipeline runs on a fresh Supabase project too (i.e. schema creation works from a blank database, not just yours).

### P2 — bonus

- **"Active client is hiring" side output** → `output/active_client_hiring.csv` (see `ACTIVE_CLIENTS.md` for the spec).
- LLM-scored ICP fit (not just binary) + rationale per company.
- Concurrency / rate-limit-aware client wrappers.
- Retry + resume from last checkpoint.
- An `mcp.json` in the repo that wires up AI Ark's MCP server — so a reviewer can plug the pipeline's AI Ark account straight into Claude Code / Cursor for ad-hoc exploration alongside the API-driven pipeline.
- A short ADR (architecture decision record) in `/docs/` covering your top 2–3 design choices — including how you modeled the Supabase relationships and why.

We'd rather see **P0 done well** than a half-built P2. State scope cuts explicitly in the README.

---

## Submission

1. Push your code to a **public GitHub repository**.
2. At least **one pull request** in that repo must be opened (and merged) via Claude Code or Codex.
3. Reply to the interview email with:
   - The repo URL
   - A link to the Claude Code / Codex PR(s)
4. The repo must contain:
   - All your source code (Python)
   - `README.md` with run instructions, including how to swap `.env` credentials so our keys work without code changes
   - `.env.example` listing every required env var (no values)
   - Supabase schema creation in code (migration / `CREATE TABLE IF NOT EXISTS` / supabase CLI scripts)
   - `output/run_summary.json` (P1)
   - `output/active_client_hiring.csv` (P2, if implemented)
5. (Optional but appreciated) self-report your hours spent at the top of the README.

---

## Ground rules

- AI tools encouraged. Cite anything you copy verbatim from external sources.
- Free-tier accounts will be plenty for the volume in this case study. If something rate-limits you, narrow your scrape window or location list — don't pay to upgrade.
- Ask clarifying questions by email anytime. We'd rather answer one question now than score a wrong interpretation later.
- If anything in this folder contradicts itself, flag it in your README. Spotting contradictions is a positive signal.

Good luck.
