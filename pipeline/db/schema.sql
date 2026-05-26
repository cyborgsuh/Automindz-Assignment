-- PharmaTalent pipeline schema (idempotent)

CREATE TABLE IF NOT EXISTS pipeline_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL DEFAULT 'running',
    config_hash TEXT,
    stats JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    name_normalized TEXT NOT NULL,
    domain TEXT,
    linkedin_org_slug TEXT UNIQUE,
    linkedin_url TEXT,
    employee_count INT,
    size_band TEXT,
    headquarters TEXT,
    industry TEXT,
    icp_decision TEXT NOT NULL,
    icp_rationale TEXT NOT NULL,
    icp_confidence TEXT NOT NULL,
    icp_checked_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    dmm_status TEXT,
    dmm_drop_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (name_normalized, domain)
);

CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pipeline_run_id UUID REFERENCES pipeline_runs(id),
    apify_id TEXT NOT NULL UNIQUE,
    linkedin_id TEXT UNIQUE,
    job_url TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    description_text TEXT,
    seniority TEXT,
    employment_type TEXT[],
    locations_derived TEXT[],
    cities_derived TEXT[],
    countries_derived TEXT[],
    date_posted TIMESTAMPTZ,
    organization_name TEXT NOT NULL,
    organization_url TEXT,
    linkedin_org_slug TEXT,
    company_domain TEXT,
    linkedin_org_employees INT,
    linkedin_org_size TEXT,
    linkedin_org_industry TEXT,
    linkedin_org_headquarters TEXT,
    linkedin_org_description TEXT,
    linkedin_org_specialties TEXT[],
    company_id UUID REFERENCES companies(id),
    scraped_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_jobs_org_slug ON jobs(linkedin_org_slug);
CREATE INDEX IF NOT EXISTS idx_jobs_company_id ON jobs(company_id);

CREATE TABLE IF NOT EXISTS contacts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    full_name TEXT NOT NULL,
    full_name_normalized TEXT NOT NULL,
    title TEXT NOT NULL,
    location TEXT,
    about_snippet TEXT,
    linkedin_url TEXT NOT NULL,
    target_title_searched TEXT NOT NULL,
    cascade_level TEXT NOT NULL,
    validation_decision TEXT NOT NULL,
    validation_reason TEXT NOT NULL,
    found_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    validated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (linkedin_url),
    UNIQUE (full_name_normalized, company_id)
);

CREATE TABLE IF NOT EXISTS contact_jobs (
    contact_id UUID NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
    job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    surfaced_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (contact_id, job_id)
);

CREATE TABLE IF NOT EXISTS dmm_search_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    target_title TEXT NOT NULL,
    cascade_level TEXT NOT NULL,
    location_query TEXT,
    results_returned INT NOT NULL DEFAULT 0,
    hit BOOLEAN NOT NULL DEFAULT false,
    hit_linkedin_url TEXT,
    raw_response JSONB,
    searched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (company_id, target_title, cascade_level)
);

CREATE TABLE IF NOT EXISTS hm_validation_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    person_linkedin_url TEXT NOT NULL,
    person_full_name TEXT NOT NULL,
    person_title TEXT NOT NULL,
    decision TEXT NOT NULL,
    reason TEXT NOT NULL,
    validated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (person_linkedin_url, job_id)
);
