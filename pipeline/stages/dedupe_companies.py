from __future__ import annotations

import logging
from typing import Any

from pipeline.domain.models import CompanyGroup, extract_domain
from pipeline.domain.normalizer import normalize_company_name

logger = logging.getLogger(__name__)


def run_dedupe_companies(jobs: list[dict[str, Any]]) -> list[CompanyGroup]:
    groups: dict[str, CompanyGroup] = {}

    for job in jobs:
        slug = job.get("linkedin_org_slug")
        name = job.get("organization_name") or ""
        domain = job.get("company_domain") or extract_domain(job.get("organization_url"))
        name_normalized = normalize_company_name(name)
        key = slug or f"{name_normalized}|{domain or ''}"

        if key not in groups:
            groups[key] = CompanyGroup(
                key=key,
                linkedin_org_slug=slug,
                name=name,
                name_normalized=name_normalized,
                domain=domain,
                representative_job=job,
            )
        group = groups[key]
        group.job_ids.append(job["id"])
        if not group.representative_job:
            group.representative_job = job

    result = list(groups.values())
    logger.info("Deduped to %d unique posting companies", len(result))
    return result
