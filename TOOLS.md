# TOOLS — Available APIs, Accounts, and Fixtures

**You set up your own accounts.** We do not issue any API keys for this case study. Every external tool listed below has a free tier that is sufficient to build, test, and demo the full pipeline at the volume this case study requires — **but the budgets are tight**, especially on AI Ark. Read the per-tool credit notes below before you start coding.

### Credit budget at a glance

| Tool | Free-tier budget | Roughly covers | Watch out for |
|---|---|---|---|
| **Apify** | ~$5 of free monthly compute on the `fantastic.jobs` LinkedIn Jobs actor | ~1,000 jobs scraped — plenty for a 7-day weekly run across the ICP locations | Cache the scrape output in Supabase so reruns during development don't re-spend |
| **AI Ark** | **100 credits = 100 people returned, total** | Enough for ~50 qualified companies at 2 results per `people_search` call | **This is the tightest budget in the pipeline.** Cap `people_search` at **max 2 results per call** (see `DMM.md`), stop the cascade on first hit, and never re-query the same `(company, title)` pair on rerun |
| **OpenRouter** | Free signup credits + ~$5 top-up if you want margin | All ICP fit-checks + every hiring-manager validation | The web-research model (`perplexity/sonar` etc.) costs more per call than the validation model — use the cheap one for validation |
| **Supabase** | 500 MB Postgres | Orders of magnitude more than this case study needs | n/a |

If a tool rate-limits or throttles you while developing, narrow the scrape window or location list — **don't pay to upgrade**, and don't burn AI Ark credits trying to brute-force a result.

When we review, we will swap the values in your `.env` for our own credentials and rerun the pipeline. So:

- Read every credential and every account-scoped value (project URL, region, organization ID, etc.) from environment variables.
- Hardcoded URLs, project IDs, or workspace IDs are a red flag — make them env-driven.

---

## 1. Apify — LinkedIn Jobs Scraper (fantastic.jobs API)

**Purpose:** Source of all open jobs. The primary input to the pipeline.

**Sign up:** https://apify.com — free tier includes monthly compute credits, which is more than enough for a 7-day weekly scrape at our volume.

**Actor ID:** `vIGxjRrHqDTPuE6M4` — *LinkedIn Jobs API* by fantastic.jobs. This is a queryable index of LinkedIn jobs, not a per-run scraper, so runs return in seconds. **Use this exact actor** — the output shape and input parameters in `fixtures/sample_apify_jobs.json` come from this actor's response schema, not a generic LinkedIn-jobs scraper.

**Env var:** `APIFY_TOKEN`

**How to run it:**

- REST (sync, blocks until run completes): `POST https://api.apify.com/v2/acts/vIGxjRrHqDTPuE6M4/run-sync-get-dataset-items?token=$APIFY_TOKEN`
- REST (async): `POST https://api.apify.com/v2/acts/vIGxjRrHqDTPuE6M4/runs?token=$APIFY_TOKEN`
- SDK: `apify-client` for Python — `client.actor("vIGxjRrHqDTPuE6M4").call({ ...input... })`

### Key input parameters (relevant to this pipeline)

| Param | What to use |
|---|---|
| `titleSearch` | OR-combined list of target titles from `ICP.md` Half 1 |
| `locationSearch` | EU locations from `ICP.md` Half 1. **Exact `City, Region, Country` strings, English names only** (`Munich` not `München`, `Bavaria` not `Bayern`, full country names — never `DE`/`UK`/`US`). |
| `EmploymentTypeFilter` | `FULL_TIME`, `CONTRACTOR` |
| Time range | Use the actor's **time-range** parameter set to `7d` for last-7-days. **Do not** combine with `datePostedAfter` on regular reruns — duplicate-risk per the actor docs. |
| `organizationEmployeesGte` / `organizationEmployeesLte` | Optional — `50` / `2000`. Lets you push the ICP size band down to the scrape, which saves enrichment budget but **excludes active-client mega-pharma** (Pfizer, Bayer, Roche) from the result. See design note below. |
| `removeAgency` | `true` — drops recruitment/staffing agencies (matches the disqualifier in `ICP.md`). |
| `industryFilter` | Optional — narrow to biotech/pharma industries to cut noise. List of valid LinkedIn industries: https://fantastic.jobs/article/linkedin-industries |
| `maxItems` | Up to 5,000 per run. For >2,000 set memory to 512 MB. |
| `descriptionType` | `text` (cheaper to parse than `html`). |
| `includeAi` | `false` — the BETA AI enrichment only covers tech roles; not useful for biotech. |

### Output fields you'll care about (per job row)

`id`, `title`, `organization`, `organization_url`, `date_posted`, `url`, `description_text`, `seniority`, `employment_type` (array), `locations_derived` (array of `City, Region, Country` strings), `cities_derived`, `countries_derived`, `linkedin_org_employees` (int), `linkedin_org_size` (text like `"501-1000 employees"`), `linkedin_org_industry`, `linkedin_org_headquarters`, `linkedin_org_slug` (the URL slug for the company — useful for active-client matching), `linkedin_org_specialties`, `linkedin_org_description`, `linkedin_id`.

`external_apply_url` is currently empty (actor-side issue since 2026-03-18) — don't depend on it.

### Design note: pre-filter at scrape time, or filter after?

`organizationEmployeesGte/Lte` and `industryFilter` can do most of the ICP filtering at scrape time, which saves you LLM budget downstream. **But** if you pre-filter on size, you lose the "active client is hiring" signal (Pfizer = 80k+ employees, would never come back). One clean option: run **two scrapes** — one ICP-sized (`50–2000`, `removeAgency=true`) for the main pipeline, and a second pass with `organizationSlugFilter` set to your active-client slugs for the side-output. Other options are fine; document whichever you pick.

### Constraints

- Max 5,000 jobs per run. Increase memory to 512 MB if you ask for more than 2,000.
- 1–2 hour indexing delay before jobs appear in the API.
- Description-keyword searches (`descriptionSearch`) are slow — avoid unless you need them.

**Docs:** open the actor in Apify Console (`vIGxjRrHqDTPuE6M4`) → Input tab for the live schema.

**Fixture fallback:** `fixtures/sample_apify_jobs.json` — same shape as the live API response. Use this if you hit rate limits while developing.

**Cost note:** Apify charges compute units per run. The free tier ships with ~$5 of compute, which is enough for roughly 1,000 jobs on this actor — more than sufficient for a weekly 7-day run across the ICP locations. Cache scrape output in Supabase (P1) so reruns during development don't re-spend.

---

## 2. AI Ark — People Search (DMM step)

**Purpose:** The decision-maker mapping step (per `DMM.md`).

**Sign up:** https://aiark.com — create an account and generate an API token.

**Connection:** **HTTP API.** Call AI Ark's `people_search` endpoint directly from Python (`httpx` / `requests`) using a bearer token. The pipeline must be runnable headlessly after we swap your token for ours, so a hand-driven MCP integration is **not** an acceptable substitute for the API call.

**Env var:** `AI_ARK_TOKEN`

**Key endpoint:** `people_search` — takes company + target titles + location, returns candidate people with title, linkedin_url, and (sometimes) other profile metadata.

> ⚠️ **Free tier = 100 credits. One returned person = one credit.** Run out and the account is dead for the rest of the case study. Concretely:
> - **Cap `people_search` at a maximum of 2 results per call** (see `DMM.md`).
> - Stop the cascade on first hit per `(company, target title)` pair.
> - Make reruns idempotent so the same `(company, title)` is never queried twice.
> - If you want to experiment freely, develop against `fixtures/sample_people_search.json` and only burn real credits on the final demo run.

### Bonus: MCP connection on top of the API

AI Ark also exposes its tools via an MCP server. Wiring it up in addition to the API call is a nice plus — for example, shipping an `mcp.json` in the repo so a reviewer can drop their own AI Ark token in and connect the same account to Claude Code / Cursor for ad-hoc exploration. **The pipeline itself must still use the HTTP API.** This is a P2 bonus, not a substitute.

**Fixture fallback:** `fixtures/sample_people_search.json`

---

## 3. OpenRouter — LLMs for every reasoning step

**Purpose:** ICP fit-check (web-research) and hiring-manager validation. Two distinct stages, **at least two different models** (one needs web access, the other doesn't).

**Sign up:** https://openrouter.ai — free credits on signup are enough to cover a full case-study run; a small top-up (a few dollars) gives you safety margin if you want to experiment. Save your budget for the web-research model — the validation step should use a cheap model since it runs once per candidate person.

**Env var:** `OPENROUTER_API_KEY`

**Docs:** https://openrouter.ai/docs

### Model picks (suggested, you may deviate with justification)

| Stage | Suggested model | Why |
|---|---|---|
| **ICP fit-check website-research** | `perplexity/sonar` or `perplexity/sonar-pro` — or any OpenRouter model with `:online` (e.g. `openai/gpt-4o:online`) | These models can browse. The fit-check **must** read real company website content, not just the LinkedIn snippet. |
| **Hiring-manager validation** | `anthropic/claude-sonnet-4` or `deepseek/deepseek-chat` | Cheap, fast, structured-output friendly. You're running this once per candidate person — count the calls. |

Note in code or README **which model you chose for each stage and why**. We score on judgment, not just outcome.

---

## 4. Supabase — Persistence

**Purpose:** The pipeline writes everything it finds to Supabase. Three tables are required: **`jobs`**, **`companies`**, **`contacts`**. Relationships between them are your design call (see `case_study.md` and `DMM.md`).

**Sign up:** https://supabase.com — free tier gives you a Postgres project with plenty of headroom for this case study (500 MB DB, no row caps that matter at this scale).

**Env vars (the typical set — name yours sensibly and document them):**

- `SUPABASE_URL` — project URL
- `SUPABASE_SERVICE_ROLE_KEY` *or* `SUPABASE_ANON_KEY` — depending on which client you use; service-role for server-side ingest is fine since this is not a public-facing app
- *(Optional)* `SUPABASE_DB_URL` — direct Postgres connection string, if you'd rather use `psycopg`/`asyncpg`/an ORM than `supabase-py`

**Schema creation must live in code.** Pick one:

- A migration script (`supabase migration new …` + `supabase db push`)
- Idempotent `CREATE TABLE IF NOT EXISTS` SQL run on pipeline startup
- An ORM with auto-migrations (SQLAlchemy + Alembic, etc.)

When we swap in our Supabase credentials and run your pipeline against an empty project, the schema needs to come up on its own.

**Client options:**
- `supabase-py` — official Python client, fine for inserts/upserts.
- Direct Postgres via `psycopg`, `asyncpg`, or `sqlalchemy` using the project's connection string — gives you full SQL.

Either is acceptable. Document the choice.

---

## 5. GitHub — Delivery

**Purpose:** Where you push the finished code. Must be a **public** repository.

At least **one merged pull request** in this repo must have been opened via Claude Code or Codex. Include a link to it in your submission email. This is part of the deliverable, not an aesthetic suggestion — we want to see the AI-assisted workflow show up in the repo history.

---

## Tools we do NOT use in this pipeline

For clarity (and to keep you from over-scoping):

- ❌ Other people-search providers (Apollo, Lusha, FullEnrich, Exa-People, etc.) — AI Ark is the only people-search source for this case study.
- ❌ Firecrawl or other web-scrape services — the web-enabled OpenRouter model replaces them for the ICP fit-check.
- ❌ Any email-finder or email-verifier service — emails are not part of this pipeline at all.
- ❌ Any outreach platform — sending mail (or generating copy to send) is not part of this case study.
- ❌ Any phone/SMS provider.
- ❌ SQLite or any other local database — Supabase is the persistence layer; do not introduce a second store.

If you want to use something not on this list, that's fine, but justify it in your README. Just remember: **we will not be providing any keys**, and we will rerun your pipeline by swapping `.env` values — so anything you add must also be free-tier-friendly and env-driven.

---

## `.env.example` you should ship

```
# Apify
APIFY_TOKEN=

# AI Ark (HTTP API — see TOOLS.md §2)
AI_ARK_TOKEN=

# OpenRouter
OPENROUTER_API_KEY=

# Supabase
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
# Optional, if you connect directly to Postgres:
# SUPABASE_DB_URL=
```
