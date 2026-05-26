from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from pipeline.clients.openrouter_client import OpenRouterClient
from pipeline.config import Settings
from pipeline.db.repos import ContactRepository, HMValidationRepository, JobRepository
from pipeline.domain.models import PersonCandidate
from pipeline.domain.normalizer import normalize_person_name

logger = logging.getLogger(__name__)


def run_validate_hiring_manager(
    settings: Settings,
    findings: list[tuple[dict[str, Any], PersonCandidate, list[UUID]]],
    jobs_repo: JobRepository,
    contacts_repo: ContactRepository,
    hm_repo: HMValidationRepository,
    llm: OpenRouterClient | None,
    *,
    max_validations: int | None = None,
) -> tuple[int, int]:
    validated = 0
    kept = 0
    remaining = max_validations

    for company, person, job_ids in findings:
        jobs = jobs_repo.get_by_ids(job_ids)
        for job in jobs:
            if remaining is not None and remaining <= 0:
                return validated, kept
            cached = hm_repo.get_cached(person.linkedin_url, job["id"])
            if cached:
                validated += 1
                if cached["decision"] == "yes":
                    kept += 1
                logger.info("HM cache hit: %s / %s -> %s", person.full_name, job.get("title"), cached["decision"])
                continue

            logger.info("HM validating: %s for job %s at %s", person.full_name, job.get("title"), company.get("name"))
            snippet = (job.get("description_text") or "")[:500]
            payload = {
                "scraped_job_title": job.get("title"),
                "scraped_job_description_snippet": snippet,
                "scraped_job_location": ", ".join(job.get("locations_derived") or []),
                "person_full_name": person.full_name,
                "person_title": person.title,
                "person_about_snippet": person.about_snippet or "",
                "person_location": person.location or "",
                "company_name": company.get("name"),
                "company_size_band": company.get("size_band") or "unknown",
            }

            if settings.fixture_mode or llm is None:
                result = llm.mock_validate_hm(payload) if llm else {"decision": "yes", "reason": "Fixture default."}
            else:
                result = llm.validate_hiring_manager(payload)

            decision = result.get("decision", "no")
            reason = result.get("reason", "No reason provided.")
            hm_repo.save(
                company_id=company["id"],
                job_id=job["id"],
                person_linkedin_url=person.linkedin_url,
                person_full_name=person.full_name,
                person_title=person.title,
                decision=decision,
                reason=reason,
            )
            validated += 1
            if remaining is not None:
                remaining -= 1

            if decision == "yes":
                contact_id = contacts_repo.upsert_contact(
                    {
                        "company_id": company["id"],
                        "full_name": person.full_name,
                        "full_name_normalized": normalize_person_name(person.full_name),
                        "title": person.title,
                        "location": person.location,
                        "about_snippet": person.about_snippet,
                        "linkedin_url": person.linkedin_url,
                        "target_title_searched": person.target_title_searched,
                        "cascade_level": person.cascade_level,
                        "validation_decision": decision,
                        "validation_reason": reason,
                    }
                )
                contacts_repo.link_job(contact_id, job["id"])
                kept += 1
                logger.info("Kept contact %s for job %s", person.full_name, job.get("title"))
            else:
                logger.info("Dropped contact %s for job %s: %s", person.full_name, job.get("title"), reason)

    return validated, kept
