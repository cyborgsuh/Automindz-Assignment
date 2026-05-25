# EVALUATION — How We Score Your Submission

We are transparent about scoring. Build to the rubric.

We score on five axes, 1–5 each. Maximum total is 25.

---

## 1. Correctness (1–5)

Does the pipeline run end-to-end **after we swap our credentials into your `.env`** and populate a Supabase project with `jobs`, `companies`, and `contacts` rows that obey the rules in `ICP.md` and `DMM.md`?

- **5** — Runs cleanly on a fresh clone with our credentials. Schema is created from code. Every row in `companies` and `contacts` obeys every rule. Edge cases (no jobs found, AI Ark returns empty, no DMM candidate) handled gracefully.
- **3** — Runs to completion but with rough edges. Schema needs a manual nudge, some rules are bent (e.g. company size band ignored, exclusion list misses obvious matches), or the relationships between tables are inconsistent.
- **1** — Pipeline crashes mid-run, requires code edits to point at a different Supabase project, or the tables come out malformed.

---

## 2. Code quality (1–5)

Readability, structure, error handling, naming. Would we accept this into our `internal-workflows/` monorepo without a major rewrite?

- **5** — Clean module boundaries (scrape / qualify / map / validate / persist). Errors are caught at the boundary they happen at. Supabase access is isolated behind a thin data layer. Naming is precise. No dead code, no commented-out experiments.
- **3** — Works but feels rushed. One big script, ad-hoc try/excepts, inconsistent naming.
- **1** — Unreadable. We can't trace data flow without running it.

---

## 3. Judgment (1–5)

Did you make sensible scope cuts? Did you pick the right tool for each step? Did you understand what the case study was actually asking for?

- **5** — P0 fully shipped, P1 mostly shipped, P2 thoughtfully chosen. Tool choices are explained in the README — *e.g.* which OpenRouter model for which stage and why. Anything you cut, you cut deliberately and said so.
- **3** — Built what was asked, but missed obvious tradeoffs (used a $$$ model for a cheap task, no caching, no exclusion match on aliases).
- **1** — Over-built or under-built. Spent time on P2 bonuses while P0 is incomplete.

---

## 4. Operational thinking (1–5)

How does this behave in production? What happens on rerun? What happens when a provider 429s? Does the pipeline respect the tight free-tier budgets (especially AI Ark's 100-credit cap)?

- **5** — Idempotent reruns against an already-populated Supabase (no duplicate rows, no re-spent API calls). AI Ark `people_search` is capped at 2 results per call and never re-queries the same `(company, title)` pair. Logs are structured and tell us what happened without us reading code. Retries are sane (not infinite). Rate limits respected.
- **3** — Logs exist but are `print()`. No retry strategy. Rerunning the pipeline duplicates rows or re-spends API budget.
- **1** — No logs. No summary. Hidden state. Failures eaten silently.

---

## 5. Communication (1–5)

README clarity, commit hygiene, the optional ADR, any decision log.

- **5** — README is enough to run, understand, and review the project without opening a single source file. Commits are atomic with meaningful messages. ADR (if present) names the alternatives considered.
- **3** — README runs the project but doesn't explain decisions. Commits are `wip`, `fix`, `more changes`.
- **1** — No README, or README is wrong (commands that don't work).

---

## What we explicitly do **not** score

- The volume of leads — 20 great leads beats 200 mediocre ones.
- Whether you hit P2 — a polished P0 beats a half-built P2.
- Hours spent — we don't penalize fast work, we reward judgment.

---

## A note on AI assistance

We use Claude Code and similar tools every day. We expect you to. The signal we care about is **whether you can drive an AI to ship a working pipeline that holds up to scrutiny** — not whether you can hand-type every line. Be ready in the follow-up call to explain:

- Why you structured the modules the way you did
- Why you chose each OpenRouter model
- How you handled the cases where the AI suggested something wrong
- What you would change if we asked you to extend this to a second client

Good luck.
