# DMM — Decision-Maker Mapping

Once a posting company passes the ICP fit-check (`ICP.md`), find the right person to contact at that company. This file defines target titles, the people-search step, the mandatory LLM validation step, and what to persist to Supabase.

> 💸 **Credit budget warning.** The AI Ark free tier ships with **only 100 credits = 100 people returned across the entire run.** This is the tightest constraint in the whole pipeline. **Cap `people_search` at a maximum of 2 results per call** and stop the cascade on first hit — see "People search" below. Blowing the budget here means the pipeline can't finish, and the account can't be reused for the next run. Treat every credit as scarce.

---

## Target titles by company size band

| Size band | Primary titles (in priority order) |
|---|---|
| **50 – 200 employees** | Head of Talent · Head of People · Head of HR · Director Regulatory Affairs · Director Clinical Operations |
| **201 – 1000 employees** | VP People · VP Talent Acquisition · Senior Director Regulatory Affairs · Senior Director Clinical Operations · Director Talent Acquisition Europe |
| **1001 – 2000 employees** | Global Head of Talent · EU Head of Talent Acquisition · VP Regulatory Affairs EU · VP Clinical Operations EU · Senior Director Talent Acquisition |

If you can't find a person in the size-appropriate band, **do not** fall back to a wildly different title (e.g. don't target a junior HR Coordinator just because the Head of Talent doesn't surface). Drop the company instead and log why.

---

## Geographic cascade

For each target company + target title:

1. Search the **city** of the posted job
2. Then the **country** of the posted job
3. Then **EU region** (DACH / Benelux / Nordics / UKI / Southern Europe)
4. Then **worldwide** — only if the company is small enough that there's a single global owner

Stop on first hit. Log which cascade level returned the person.

---

## People search — AI Ark API

Use AI Ark's `people_search` **HTTP API** (see `TOOLS.md` for the endpoint and auth header). Pass: company name, company domain, target title list (size-band-appropriate), location cascade level.

**Hard cap: max 2 results returned per `people_search` call.** Each returned person costs one credit, and the free tier ships with 100 credits total. Ask AI Ark for two candidates, not ten — you do not need a long list to find one valid hiring manager, and a run that empties the credit pool can't be rerun.

**Stop on first hit per (company, target title) pair.** Log the cascade level that produced the hit.

If `people_search` returns nothing across the entire cascade, drop the company and log "no DMM candidate found." Do not try to substitute other providers — AI Ark is the one people-search source we expose for this case study.

> **Bonus:** AI Ark also exposes its tools via MCP. The pipeline must call the API directly (so we can rerun it headlessly with our credentials), but if you also ship an `mcp.json` in the repo that wires up the AI Ark MCP server, a reviewer can plug your account straight into Claude Code or Cursor for ad-hoc exploration. Optional, but a nice plus.

---

## LLM hiring-manager validation (mandatory)

Every candidate person returned by `people_search` **must** pass an LLM validation step before being written to the `contacts` table.

### Prompt inputs

```
{
  "scraped_job_title":             string,
  "scraped_job_description_snippet": string,  // first ~500 chars
  "scraped_job_location":          string,
  "person_full_name":              string,
  "person_title":                  string,
  "person_about_snippet":          string,    // if available, else empty
  "person_location":               string,
  "company_name":                  string,
  "company_size_band":             string
}
```

### Prompt task

Ask the model: *"Could this person plausibly be the hiring manager or final decision-maker for this specific role? Answer `yes` or `no` and give a one-sentence reason."*

A starter prompt template lives at `fixtures/sample_hm_validation_prompt.md`. You are free to improve it.

### Decision rule

- `yes` → keep the contact, persist to Supabase.
- `no` → drop the contact. Log the reason — we read these to evaluate your validation step.

---

## Deduplication

Dedup key precedence (apply in order):

1. `linkedin_url` (canonicalized — strip query params, trailing slash, language prefix)
2. `(normalized_full_name, company_domain)` where `normalized_full_name` is lowercase, accent-stripped, single-spaced

If the same person matches **multiple scraped jobs at the same company**, keep one `contacts` row and link both jobs through whatever join table you designed in Supabase.

---

## What to persist to Supabase

The `contacts` table is the final landing spot for every validated decision-maker. At minimum, each row should capture:

- The person (full name, title, LinkedIn URL, location)
- The company they belong to (foreign key into `companies`)
- The job(s) that surfaced them (relationship into `jobs` — one-to-many; design the join)
- The LLM validation decision and reason
- The geographic cascade level that produced the hit (`city` / `country` / `region` / `worldwide`)
- Timestamps (`found_at`, `validated_at`)

Exact column names and types are your call — we look at whether the schema is coherent, not whether it matches a template.
