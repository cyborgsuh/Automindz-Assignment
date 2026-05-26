from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from pipeline.db.client import ConnectionManager

logger = logging.getLogger(__name__)


class _RepoBase:
    def __init__(self, conn: psycopg.Connection | ConnectionManager) -> None:
        self._manager = conn if isinstance(conn, ConnectionManager) else None
        self._conn = None if self._manager else conn

    @property
    def conn(self) -> psycopg.Connection:
        if self._manager is not None:
            return self._manager.conn
        return self._conn  # type: ignore[return-value]


class RunRepository(_RepoBase):
    def start_run(self, config_hash: str | None = None) -> UUID:
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO pipeline_runs (config_hash)
                VALUES (%s)
                RETURNING id
                """,
                (config_hash,),
            )
            row = cur.fetchone()
        self.conn.commit()
        return row["id"]

    def finish_run(self, run_id: UUID, status: str, stats: dict[str, Any]) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE pipeline_runs
                SET finished_at = now(), status = %s, stats = %s
                WHERE id = %s
                """,
                (status, Jsonb(stats), run_id),
            )
        self.conn.commit()


class JobRepository(_RepoBase):
    def upsert_job(self, run_id: UUID, job: dict[str, Any]) -> UUID:
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO jobs (
                    pipeline_run_id, apify_id, linkedin_id, job_url, title,
                    description_text, seniority, employment_type, locations_derived,
                    cities_derived, countries_derived, date_posted, organization_name,
                    organization_url, linkedin_org_slug, company_domain,
                    linkedin_org_employees, linkedin_org_size, linkedin_org_industry,
                    linkedin_org_headquarters, linkedin_org_description,
                    linkedin_org_specialties
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s
                )
                ON CONFLICT (apify_id) DO UPDATE SET
                    title = EXCLUDED.title,
                    description_text = EXCLUDED.description_text,
                    pipeline_run_id = EXCLUDED.pipeline_run_id,
                    updated_at = now()
                RETURNING id
                """,
                (
                    run_id,
                    job["apify_id"],
                    job.get("linkedin_id"),
                    job["job_url"],
                    job["title"],
                    job.get("description_text"),
                    job.get("seniority"),
                    job.get("employment_type"),
                    job.get("locations_derived"),
                    job.get("cities_derived"),
                    job.get("countries_derived"),
                    job.get("date_posted"),
                    job["organization_name"],
                    job.get("organization_url"),
                    job.get("linkedin_org_slug"),
                    job.get("company_domain"),
                    job.get("linkedin_org_employees"),
                    job.get("linkedin_org_size"),
                    job.get("linkedin_org_industry"),
                    job.get("linkedin_org_headquarters"),
                    job.get("linkedin_org_description"),
                    job.get("linkedin_org_specialties"),
                ),
            )
            row = cur.fetchone()
        self.conn.commit()
        return row["id"]

    def list_all(self) -> list[dict[str, Any]]:
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM jobs ORDER BY date_posted DESC NULLS LAST")
            return list(cur.fetchall())

    def link_company(self, job_ids: list[UUID], company_id: UUID) -> None:
        if not job_ids:
            return
        with self.conn.cursor() as cur:
            cur.execute(
                "UPDATE jobs SET company_id = %s, updated_at = now() WHERE id = ANY(%s)",
                (company_id, job_ids),
            )
        self.conn.commit()

    def get_by_ids(self, job_ids: list[UUID]) -> list[dict[str, Any]]:
        if not job_ids:
            return []
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM jobs WHERE id = ANY(%s)", (job_ids,))
            return list(cur.fetchall())


class CompanyRepository(_RepoBase):
    def get_by_slug(self, slug: str | None) -> dict[str, Any] | None:
        if not slug:
            return None
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM companies WHERE linkedin_org_slug = %s", (slug,))
            return cur.fetchone()

    def get_recent_check(self, slug: str | None, name_normalized: str, domain: str | None, days: int = 7) -> dict[str, Any] | None:
        with self.conn.cursor(row_factory=dict_row) as cur:
            if slug:
                cur.execute(
                    """
                    SELECT * FROM companies
                    WHERE linkedin_org_slug = %s
                      AND icp_checked_at >= now() - make_interval(days => %s)
                    """,
                    (slug, days),
                )
                row = cur.fetchone()
                if row:
                    return row
            cur.execute(
                """
                SELECT * FROM companies
                WHERE name_normalized = %s
                  AND COALESCE(domain, '') = COALESCE(%s, '')
                  AND icp_checked_at >= now() - make_interval(days => %s)
                """,
                (name_normalized, domain, days),
            )
            return cur.fetchone()

    def upsert_company(self, company: dict[str, Any]) -> UUID:
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO companies (
                    name, name_normalized, domain, linkedin_org_slug, linkedin_url,
                    employee_count, size_band, headquarters, industry,
                    icp_decision, icp_rationale, icp_confidence, icp_checked_at,
                    dmm_status, dmm_drop_reason
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s
                )
                ON CONFLICT (linkedin_org_slug) DO UPDATE SET
                    name = EXCLUDED.name,
                    employee_count = EXCLUDED.employee_count,
                    size_band = EXCLUDED.size_band,
                    icp_decision = EXCLUDED.icp_decision,
                    icp_rationale = EXCLUDED.icp_rationale,
                    icp_confidence = EXCLUDED.icp_confidence,
                    icp_checked_at = EXCLUDED.icp_checked_at,
                    dmm_status = COALESCE(EXCLUDED.dmm_status, companies.dmm_status),
                    dmm_drop_reason = EXCLUDED.dmm_drop_reason,
                    updated_at = now()
                RETURNING id
                """,
                (
                    company["name"],
                    company["name_normalized"],
                    company.get("domain"),
                    company.get("linkedin_org_slug"),
                    company.get("linkedin_url"),
                    company.get("employee_count"),
                    company.get("size_band"),
                    company.get("headquarters"),
                    company.get("industry"),
                    company["icp_decision"],
                    company["icp_rationale"],
                    company["icp_confidence"],
                    company.get("icp_checked_at") or datetime.utcnow(),
                    company.get("dmm_status"),
                    company.get("dmm_drop_reason"),
                ),
            )
            row = cur.fetchone()
        self.conn.commit()
        return row["id"]

    def upsert_by_name_domain(self, company: dict[str, Any]) -> UUID:
        """Fallback upsert when linkedin_org_slug is missing."""
        if company.get("linkedin_org_slug"):
            return self.upsert_company(company)
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO companies (
                    name, name_normalized, domain, linkedin_org_slug, linkedin_url,
                    employee_count, size_band, headquarters, industry,
                    icp_decision, icp_rationale, icp_confidence, icp_checked_at,
                    dmm_status, dmm_drop_reason
                ) VALUES (
                    %s, %s, %s, NULL, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s
                )
                ON CONFLICT (name_normalized, domain) DO UPDATE SET
                    icp_decision = EXCLUDED.icp_decision,
                    icp_rationale = EXCLUDED.icp_rationale,
                    icp_confidence = EXCLUDED.icp_confidence,
                    icp_checked_at = EXCLUDED.icp_checked_at,
                    dmm_status = COALESCE(EXCLUDED.dmm_status, companies.dmm_status),
                    updated_at = now()
                RETURNING id
                """,
                (
                    company["name"],
                    company["name_normalized"],
                    company.get("domain"),
                    company.get("linkedin_url"),
                    company.get("employee_count"),
                    company.get("size_band"),
                    company.get("headquarters"),
                    company.get("industry"),
                    company["icp_decision"],
                    company["icp_rationale"],
                    company["icp_confidence"],
                    company.get("icp_checked_at") or datetime.utcnow(),
                    company.get("dmm_status"),
                    company.get("dmm_drop_reason"),
                ),
            )
            row = cur.fetchone()
        self.conn.commit()
        return row["id"]

    def list_fit_companies(self) -> list[dict[str, Any]]:
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT * FROM companies
                WHERE icp_decision = 'fit'
                  AND (dmm_status IS NULL OR dmm_status = 'pending')
                ORDER BY icp_checked_at DESC
                """
            )
            return list(cur.fetchall())

    def update_dmm_status(self, company_id: UUID, status: str, reason: str | None = None) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                UPDATE companies
                SET dmm_status = %s, dmm_drop_reason = %s, updated_at = now()
                WHERE id = %s
                """,
                (status, reason, company_id),
            )
        self.conn.commit()


class ContactRepository(_RepoBase):
    def upsert_contact(self, contact: dict[str, Any]) -> UUID:
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                INSERT INTO contacts (
                    company_id, full_name, full_name_normalized, title, location,
                    about_snippet, linkedin_url, target_title_searched, cascade_level,
                    validation_decision, validation_reason, found_at, validated_at
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s,
                    %s, %s, %s, %s
                )
                ON CONFLICT (linkedin_url) DO UPDATE SET
                    title = EXCLUDED.title,
                    validation_decision = EXCLUDED.validation_decision,
                    validation_reason = EXCLUDED.validation_reason,
                    validated_at = EXCLUDED.validated_at,
                    updated_at = now()
                RETURNING id
                """,
                (
                    contact["company_id"],
                    contact["full_name"],
                    contact["full_name_normalized"],
                    contact["title"],
                    contact.get("location"),
                    contact.get("about_snippet"),
                    contact["linkedin_url"],
                    contact["target_title_searched"],
                    contact["cascade_level"],
                    contact["validation_decision"],
                    contact["validation_reason"],
                    contact.get("found_at") or datetime.utcnow(),
                    contact.get("validated_at") or datetime.utcnow(),
                ),
            )
            row = cur.fetchone()
        self.conn.commit()
        return row["id"]

    def link_job(self, contact_id: UUID, job_id: UUID) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO contact_jobs (contact_id, job_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
                """,
                (contact_id, job_id),
            )
        self.conn.commit()


class DMMCacheRepository(_RepoBase):
    def get_cached(self, company_id: UUID, target_title: str, cascade_level: str) -> dict[str, Any] | None:
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT * FROM dmm_search_log
                WHERE company_id = %s AND target_title = %s AND cascade_level = %s
                """,
                (company_id, target_title, cascade_level),
            )
            return cur.fetchone()

    def save_search(
        self,
        company_id: UUID,
        target_title: str,
        cascade_level: str,
        location_query: str | None,
        results_returned: int,
        hit: bool,
        hit_linkedin_url: str | None,
        raw_response: dict[str, Any] | None,
    ) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO dmm_search_log (
                    company_id, target_title, cascade_level, location_query,
                    results_returned, hit, hit_linkedin_url, raw_response
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (company_id, target_title, cascade_level) DO NOTHING
                """,
                (
                    company_id,
                    target_title,
                    cascade_level,
                    location_query,
                    results_returned,
                    hit,
                    hit_linkedin_url,
                    Jsonb(raw_response) if raw_response else None,
                ),
            )
        self.conn.commit()


class HMValidationRepository(_RepoBase):
    def get_cached(self, person_linkedin_url: str, job_id: UUID) -> dict[str, Any] | None:
        with self.conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                """
                SELECT * FROM hm_validation_log
                WHERE person_linkedin_url = %s AND job_id = %s
                """,
                (person_linkedin_url, job_id),
            )
            return cur.fetchone()

    def save(
        self,
        company_id: UUID,
        job_id: UUID,
        person_linkedin_url: str,
        person_full_name: str,
        person_title: str,
        decision: str,
        reason: str,
    ) -> None:
        with self.conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO hm_validation_log (
                    company_id, job_id, person_linkedin_url, person_full_name,
                    person_title, decision, reason
                ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (person_linkedin_url, job_id) DO NOTHING
                """,
                (company_id, job_id, person_linkedin_url, person_full_name, person_title, decision, reason),
            )
        self.conn.commit()
