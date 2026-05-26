from __future__ import annotations

import logging
import time
from typing import Any
from uuid import UUID

from pipeline.clients.ai_ark_client import AIArkClient
from pipeline.config import Settings
from pipeline.db.repos import CompanyRepository, DMMCacheRepository, JobRepository
from pipeline.domain.geo_cascade import build_cascade
from pipeline.domain.models import PersonCandidate
from pipeline.domain.size_band import titles_for_band

logger = logging.getLogger(__name__)


def run_dmm_search(
    settings: Settings,
    companies_repo: CompanyRepository,
    jobs_repo: JobRepository,
    dmm_cache: DMMCacheRepository,
    ai_ark: AIArkClient,
    *,
    max_companies: int | None = None,
    stop_after_first_api_call: bool = False,
) -> tuple[int, list[tuple[dict[str, Any], PersonCandidate, list[UUID]]]]:
    """Returns (credits_used, list of (company, person, job_ids))."""
    credits_used = 0
    findings: list[tuple[dict[str, Any], PersonCandidate, list[UUID]]] = []
    api_calls_made = 0

    fit_companies = companies_repo.list_fit_companies()
    if max_companies is not None:
        fit_companies = fit_companies[:max_companies]

    logger.info("DMM: %d ICP-fit companies to search", len(fit_companies))

    for company_idx, company in enumerate(fit_companies, start=1):
        logger.info("DMM company (%d/%d): %s", company_idx, len(fit_companies), company["name"])
        jobs = jobs_repo.get_by_ids(
            [j["id"] for j in jobs_repo.list_all() if j.get("company_id") == company["id"]]
        )
        if not jobs:
            companies_repo.update_dmm_status(company["id"], "no_candidate", "No linked jobs found")
            continue

        rep = jobs[0]
        job_ids = [j["id"] for j in jobs]
        titles = titles_for_band(company.get("size_band") or "")
        if not titles:
            companies_repo.update_dmm_status(
                company["id"],
                "no_candidate",
                f"No DMM titles for size band {company.get('size_band')}",
            )
            continue

        cascade = build_cascade(
            list(rep.get("cities_derived") or []),
            list(rep.get("countries_derived") or []),
            list(rep.get("locations_derived") or []),
            company.get("employee_count"),
        )
        if company.get("domain"):
            # AI Ark scopes by domain; geo cascade levels would repeat the same query.
            cascade = [("company", "")]

        found_person: PersonCandidate | None = None
        stop_dmm = False
        for target_title in titles:
            if found_person or stop_dmm:
                break
            for cascade_level, location_query in cascade:
                cached = dmm_cache.get_cached(company["id"], target_title, cascade_level)
                if cached:
                    if cached.get("hit") and cached.get("raw_response"):
                        raw_people = cached["raw_response"].get("people") or []
                        if raw_people:
                            found_person = AIArkClient._to_candidate(
                                raw_people[0], target_title, cascade_level
                            )
                            break
                    continue

                logger.info(
                    "DMM API call: %s / title=%s / level=%s",
                    company["name"],
                    target_title,
                    cascade_level,
                )
                people = ai_ark.people_search(
                    company_name=company["name"],
                    company_domain=company.get("domain"),
                    target_title=target_title,
                    location=location_query,
                    cascade_level=cascade_level,
                )
                api_calls_made += 1
                time.sleep(2)
                credits_used += len(people)
                hit = len(people) > 0
                hit_url = people[0].linkedin_url if people else None
                dmm_cache.save_search(
                    company_id=company["id"],
                    target_title=target_title,
                    cascade_level=cascade_level,
                    location_query=location_query,
                    results_returned=len(people),
                    hit=hit,
                    hit_linkedin_url=hit_url,
                    raw_response={
                        "people": [
                            {
                                "full_name": p.full_name,
                                "title": p.title,
                                "location": p.location,
                                "linkedin_url": p.linkedin_url,
                                "about_snippet": p.about_snippet,
                                "company_domain": p.company_domain,
                            }
                            for p in people
                        ]
                    },
                )
                if people:
                    found_person = people[0]
                    logger.info(
                        "DMM hit for %s at %s/%s: %s",
                        company["name"],
                        cascade_level,
                        target_title,
                        found_person.full_name,
                    )
                    break
                if stop_after_first_api_call and api_calls_made >= 1:
                    stop_dmm = True
                    break

        if found_person:
            companies_repo.update_dmm_status(company["id"], "found", None)
            findings.append((company, found_person, job_ids))
        else:
            companies_repo.update_dmm_status(
                company["id"],
                "no_candidate",
                "No DMM candidate found across cascade",
            )
            logger.info("No DMM candidate for %s", company["name"])

        if stop_after_first_api_call and api_calls_made >= 1:
            break

    return credits_used, findings
