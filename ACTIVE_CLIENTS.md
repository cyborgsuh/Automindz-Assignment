# ACTIVE_CLIENTS — Exclusion List

These are **fictional active clients** of PharmaTalent Europe. For the purposes of this case study, treat every company in this list as one we already work with — they must **never** appear in your outreach output.

We use real biotech and pharma company names here on purpose. Your Apify scrape will return real LinkedIn data, and if the exclusion list were fictional, the matching logic would never get exercised. Using real names lets us see whether your exclusion code actually works against real-world data.

> ⚠️ These are **not** real clients of any real company. They are stand-ins. Do not contact them. Do not assume anything about their real-world hiring activity.

---

## The list

### Big pharma

- Pfizer
- Bayer
- Novartis
- Roche
- Sanofi
- GSK (GlaxoSmithKline)
- AstraZeneca
- Merck KGaA
- Boehringer Ingelheim

### Mid biotech

- BioNTech
- CureVac
- MorphoSys
- Evotec

### CROs

- ICON plc
- IQVIA

---

## Matching rules

You will encounter these names with messy variations in real LinkedIn data: legal suffixes, country tags, casing, abbreviations. Your matching logic must handle that.

**Required normalization before matching:**

1. Lowercase
2. Strip legal suffixes: `GmbH`, `AG`, `SE`, `S.A.`, `S.A.S.`, `S.p.A.`, `Inc.`, `Ltd.`, `LLC`, `plc`, `& Co. KG`, `Holding`
3. Strip country/region tags in parentheses: `Roche (Switzerland)` → `roche`
4. Collapse whitespace

**Matching strategy:**

1. **Exact match** on normalized name
2. **Domain match** on root domain when available (e.g. `biontech.de`, `biontech.com` → `biontech`)
3. **Fuzzy match** — Levenshtein ≤ 2 OR similarity ≥ 90% — catches typos, casing variants, and minor formatting drift
4. **LLM tiebreak** (optional) — for ambiguous casing/formatting edges, you may pass the name to an LLM and ask "is this the same company as `<client>`?" Log the decision either way.

You only need to match the names on the list above — no need to chase down subsidiaries, parents, or sister brands. Match what's in the scrape against what's in the list.

---

## Hidden bonus (P2): "Active Client Is Hiring" signal

When one of these active clients **does** show up in your scrape, do *not* just silently drop them. Instead:

1. Exclude them from the main pipeline output — they must not land in your Supabase `companies` or `contacts` tables.
2. **Also** write a row to `output/active_client_hiring.csv` with these columns:

| Column | Description |
|---|---|
| `client_name` | The matched active-client name (normalized) |
| `matched_company_name_raw` | The raw company name as it appeared in the scrape |
| `scraped_job_title` | The job title |
| `scraped_job_url` | LinkedIn URL of the job |
| `location` | Job location |
| `posted_at` | When LinkedIn says the job was posted |
| `detected_at` | When your pipeline ran |

This is a real operational pattern in our delivery workflow: an active client posting a relevant role is an **expansion/upsell signal** for the account manager to act on — they can offer to help fill the role.

A candidate who reads this section, notices the signal, and implements it is showing exactly the operational thinking we want to see in a senior delivery engineer.
