# ICP — PharmaTalent Europe

This file drives **both** your job scrape (Half 1) and your company fit-check (Half 2). Treat the two halves as one source of truth: the scrape brings candidates in; the fit-check decides who stays.

---

## Client (fictional)

**PharmaTalent Europe** — a recruitment agency placing PhD-level pharmacists, regulatory-affairs leads, clinical operations managers, and clinical research scientists into biotech and pharma companies operating in Europe.

**What we sell to:** internal Talent / People / HR leadership at biotech and pharma companies, and the functional heads who own the hiring requisition (Director Regulatory Affairs, Head of Clinical Operations, etc.).

---

## Half 1 — Job-scrape parameters

These map onto the fantastic.jobs LinkedIn Jobs API actor (`vIGxjRrHqDTPuE6M4`) — see `TOOLS.md` for the full parameter reference.

### `titleSearch` (OR-combined)

**Regulatory Affairs**
- Regulatory Affairs Manager
- Senior Regulatory Affairs Manager
- Director Regulatory Affairs
- Head of Regulatory Affairs
- Regulatory Affairs Specialist

**Clinical Operations & Research**
- Clinical Operations Manager
- Director Clinical Operations
- Head of Clinical Operations
- Senior Clinical Research Associate
- Clinical Trial Manager
- Clinical Project Manager

**Pharmacovigilance & Drug Safety**
- Pharmacovigilance Manager
- Drug Safety Officer
- Qualified Person for Pharmacovigilance

**Medical Affairs**
- Medical Affairs Lead
- Medical Science Liaison
- Senior Medical Advisor

### `locationSearch`

Use exact `City, Region, Country` strings or just the country name. **English names only** — the actor requires `Munich, Bavaria, Germany` (not `München, Bayern, Deutschland`). For a 7-day weekly run, country-level is usually enough:

`Germany`, `Switzerland`, `Netherlands`, `Belgium`, `Denmark`, `Sweden`, `Ireland`, `France`, `United Kingdom`, `Spain`, `Italy`, `Austria`, `Finland`, `Norway`.

### Other scrape parameters

- **Time range:** `7d` (use the actor's time-range param, not `datePostedAfter` — see TOOLS.md).
- **`EmploymentTypeFilter`:** `FULL_TIME`, `CONTRACTOR`.
- **`removeAgency`:** `true` (recruitment/staffing agencies are disqualified anyway — see Half 2).
- **`descriptionType`:** `text`.
- **`maxItems`:** up your choice, but stay within compute budget. The actor max is 5000 per run.
- **`organizationEmployeesGte/Lte`:** optional pre-filter. If you use it with `50/2000`, see the design note in TOOLS.md about losing active-client visibility.

---

## Half 2 — Company fit-check criteria

Apply these to the *posting company* of every scraped job. **The fit-check must include a website-research step** — use a web-enabled OpenRouter model (e.g. `perplexity/sonar`, `perplexity/sonar-pro`, or any `:online` variant) so the check uses real company information, not just the LinkedIn snippet.

### Target industries (any of)

- Biotech (drug discovery, drug development, gene/cell therapy, mRNA, immunotherapy, oncology, rare disease)
- Pharma (small-to-mid clinical-stage and commercial-stage)
- Contract Research Organizations (CROs)
- Contract Development & Manufacturing (CDMOs) — *but only if they run clinical trials in-house*

### Company size

50–2000 employees globally. Outside this band → not a fit.

### Geography rule

The company **must have at least one operational/hiring location in EU/EEA/UK/CH/Norway**. Headquarters can be anywhere — a US, Japanese, Korean, or Chinese biotech with a Berlin or Basel office is **in scope**. A fully US-only or fully Asia-only company with no European footprint is **not**.

When in doubt, the web-research step should look for: European subsidiary, EU office address on the website, European job postings, or a registered European entity.

### Disqualifiers (any one → drop)

- Pure academic institutions, universities, research institutes
- Hospitals and clinics
- Generic-drug-only manufacturers under 50 employees
- Fully remote companies with no EU legal entity
- Staffing, recruitment, or consulting agencies (we don't sell to competitors or to consultants who'd replace us)
- Medical-device companies with no drug-development arm
- Cosmetic, nutraceutical, or food-supplement companies

### Output of the fit-check

For every posting company, persist the fit-check verdict — at minimum:

- `company_name`, `company_domain`
- `decision`: `fit` | `not_fit`
- `rationale`: 1–3 sentences, must reference website findings
- `confidence`: `high` | `medium` | `low`
- `checked_at`: ISO8601

Companies tagged `fit` land in the Supabase `companies` table and continue to the DMM step. Companies tagged `not_fit` are dropped — but persist the rationale somewhere (the `companies` table, an audit table, or both) so we can read why.

### Building the company list

**There is no seed company list.** Building the qualified company list from your job scrape is part of what we're evaluating. Don't hardcode companies — derive them from the data.

The exclusion list lives in **`ACTIVE_CLIENTS.md`**. Companies in there must never appear in your outreach output, even if they're a perfect fit.
