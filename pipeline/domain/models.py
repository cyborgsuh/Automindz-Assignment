from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID


@dataclass
class JobRecord:
    id: UUID | None
    apify_id: str
    linkedin_id: str | None
    job_url: str
    title: str
    description_text: str | None
    seniority: str | None
    employment_type: list[str]
    locations_derived: list[str]
    cities_derived: list[str]
    countries_derived: list[str]
    date_posted: datetime | None
    organization_name: str
    organization_url: str | None
    linkedin_org_slug: str | None
    company_domain: str | None
    linkedin_org_employees: int | None
    linkedin_org_size: str | None
    linkedin_org_industry: str | None
    linkedin_org_headquarters: str | None
    linkedin_org_description: str | None
    linkedin_org_specialties: list[str] = field(default_factory=list)

    @classmethod
    def from_apify(cls, raw: dict[str, Any]) -> JobRecord:
        date_posted = None
        if raw.get("date_posted"):
            date_posted = datetime.fromisoformat(str(raw["date_posted"]).replace("Z", "+00:00"))
        return cls(
            id=None,
            apify_id=str(raw["id"]),
            linkedin_id=str(raw.get("linkedin_id")) if raw.get("linkedin_id") else None,
            job_url=str(raw["url"]),
            title=str(raw["title"]),
            description_text=raw.get("description_text"),
            seniority=raw.get("seniority"),
            employment_type=list(raw.get("employment_type") or []),
            locations_derived=list(raw.get("locations_derived") or []),
            cities_derived=list(raw.get("cities_derived") or []),
            countries_derived=list(raw.get("countries_derived") or []),
            date_posted=date_posted,
            organization_name=str(raw.get("organization") or ""),
            organization_url=raw.get("organization_url") or raw.get("linkedin_org_url"),
            linkedin_org_slug=raw.get("linkedin_org_slug"),
            company_domain=extract_domain(raw.get("organization_url") or raw.get("linkedin_org_url")),
            linkedin_org_employees=raw.get("linkedin_org_employees"),
            linkedin_org_size=raw.get("linkedin_org_size"),
            linkedin_org_industry=raw.get("linkedin_org_industry"),
            linkedin_org_headquarters=raw.get("linkedin_org_headquarters"),
            linkedin_org_description=raw.get("linkedin_org_description"),
            linkedin_org_specialties=list(raw.get("linkedin_org_specialties") or []),
        )

    def to_db_dict(self) -> dict[str, Any]:
        return {
            "apify_id": self.apify_id,
            "linkedin_id": self.linkedin_id,
            "job_url": self.job_url,
            "title": self.title,
            "description_text": self.description_text,
            "seniority": self.seniority,
            "employment_type": self.employment_type,
            "locations_derived": self.locations_derived,
            "cities_derived": self.cities_derived,
            "countries_derived": self.countries_derived,
            "date_posted": self.date_posted,
            "organization_name": self.organization_name,
            "organization_url": self.organization_url,
            "linkedin_org_slug": self.linkedin_org_slug,
            "company_domain": self.company_domain,
            "linkedin_org_employees": self.linkedin_org_employees,
            "linkedin_org_size": self.linkedin_org_size,
            "linkedin_org_industry": self.linkedin_org_industry,
            "linkedin_org_headquarters": self.linkedin_org_headquarters,
            "linkedin_org_description": self.linkedin_org_description,
            "linkedin_org_specialties": self.linkedin_org_specialties,
        }


def extract_domain(url: str | None) -> str | None:
    if not url:
        return None
    match = re.search(r"linkedin\.com/company/([^/?#]+)", url)
    if match:
        slug = match.group(1)
        # LinkedIn slug is not a domain; return None and infer later
        return None
    match = re.search(r"https?://(?:www\.)?([^/]+)", url)
    if not match:
        return None
    host = match.group(1).lower()
    if host in {"linkedin.com", "www.linkedin.com"} or host.endswith(".linkedin.com"):
        return None
    parts = host.split(".")
    if len(parts) >= 2:
        return ".".join(parts[-2:])
    return host


@dataclass
class CompanyGroup:
    key: str
    linkedin_org_slug: str | None
    name: str
    name_normalized: str
    domain: str | None
    job_ids: list[UUID] = field(default_factory=list)
    representative_job: dict[str, Any] | None = None


@dataclass
class PersonCandidate:
    full_name: str
    title: str
    location: str | None
    linkedin_url: str
    about_snippet: str | None
    company_domain: str | None
    target_title_searched: str
    cascade_level: str
