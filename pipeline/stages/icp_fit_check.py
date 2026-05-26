from __future__ import annotations

import csv
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from pipeline.clients.openrouter_client import OpenRouterClient
from pipeline.config import Settings
from pipeline.db.repos import CompanyRepository, JobRepository
from pipeline.domain.models import CompanyGroup
from pipeline.domain.size_band import employee_count_to_band

logger = logging.getLogger(__name__)

_CSV_FIELDS = [
    "company_name",
    "linkedin_org_slug",
    "domain",
    "employee_count",
    "size_band",
    "headquarters",
    "industry",
    "icp_decision",
    "icp_confidence",
    "icp_rationale",
    "source",
    "checked_at",
]


def _write_icp_csv(output_dir: Path, rows: list[dict]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "icp_fit_decisions.csv"
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    logger.info("Wrote ICP decisions to %s", path)


def run_icp_fit_check(
    settings: Settings,
    groups: list[CompanyGroup],
    companies_repo: CompanyRepository,
    jobs_repo: JobRepository,
    llm: OpenRouterClient | None,
    *,
    company_limit: int | None = None,
) -> tuple[int, int]:
    checked = 0
    fit_count = 0
    audit_rows: list[dict] = []
    target_groups = groups[:company_limit] if company_limit is not None else groups

    for i, group in enumerate(target_groups, start=1):
        job = group.representative_job or {}
        existing = companies_repo.get_recent_check(group.linkedin_org_slug, group.name_normalized, group.domain)
        if existing:
            jobs_repo.link_company(group.job_ids, existing["id"])
            if existing["icp_decision"] == "fit":
                fit_count += 1
            checked += 1
            logger.info("ICP cache hit (%d/%d): %s", i, len(target_groups), group.name)
            audit_rows.append({
                "company_name": group.name,
                "linkedin_org_slug": group.linkedin_org_slug or "",
                "domain": group.domain or "",
                "employee_count": existing.get("employee_count") or "",
                "size_band": existing.get("size_band") or "",
                "headquarters": existing.get("headquarters") or "",
                "industry": existing.get("industry") or "",
                "icp_decision": existing["icp_decision"],
                "icp_confidence": existing.get("icp_confidence") or "",
                "icp_rationale": existing.get("icp_rationale") or "",
                "source": "cache",
                "checked_at": datetime.now(timezone.utc).isoformat(),
            })
            continue

        logger.info("ICP checking (%d/%d): %s", i, len(target_groups), group.name)
        employee_count = job.get("linkedin_org_employees")
        company_payload = {
            "name": group.name,
            "name_normalized": group.name_normalized,
            "domain": group.domain,
            "linkedin_org_slug": group.linkedin_org_slug,
            "linkedin_url": job.get("organization_url"),
            "employee_count": employee_count,
            "size_band": employee_count_to_band(employee_count),
            "headquarters": job.get("linkedin_org_headquarters"),
            "industry": job.get("linkedin_org_industry"),
            "description": job.get("linkedin_org_description"),
        }

        if settings.fixture_mode or llm is None:
            result = llm.mock_icp_fit_check(company_payload) if llm else {
                "decision": "fit" if employee_count and 50 <= employee_count <= 2000 else "not_fit",
                "rationale": "Fixture mode heuristic.",
                "confidence": "low",
            }
        else:
            logger.info("ICP calling OpenRouter for %s ...", group.name)
            result = llm.icp_fit_check(company_payload)
            logger.info("ICP OpenRouter returned for %s", group.name)

        company_row = {
            **company_payload,
            "icp_decision": result.get("decision", "not_fit"),
            "icp_rationale": result.get("rationale", "No rationale provided."),
            "icp_confidence": result.get("confidence", "low"),
            "dmm_status": "pending" if result.get("decision") == "fit" else None,
        }

        if group.linkedin_org_slug:
            company_id = companies_repo.upsert_company(company_row)
        else:
            company_id = companies_repo.upsert_by_name_domain(company_row)

        jobs_repo.link_company(group.job_ids, company_id)
        checked += 1
        if company_row["icp_decision"] == "fit":
            fit_count += 1
            logger.info("ICP fit: %s", group.name)
        else:
            logger.info("ICP not_fit: %s — %s", group.name, company_row["icp_rationale"][:120])

        audit_rows.append({
            "company_name": group.name,
            "linkedin_org_slug": group.linkedin_org_slug or "",
            "domain": group.domain or "",
            "employee_count": company_row.get("employee_count") or "",
            "size_band": company_row.get("size_band") or "",
            "headquarters": company_row.get("headquarters") or "",
            "industry": company_row.get("industry") or "",
            "icp_decision": company_row["icp_decision"],
            "icp_confidence": company_row.get("icp_confidence") or "",
            "icp_rationale": company_row.get("icp_rationale") or "",
            "source": "llm",
            "checked_at": datetime.now(timezone.utc).isoformat(),
        })

    if audit_rows:
        _write_icp_csv(settings.output_dir, audit_rows)

    return checked, fit_count
