"""
Cost-limited step-by-step test runner.

Runs one API call per paid service (by default), persists all data to Supabase,
and writes checkpoint state so you can debug a failed step and resume later.

Usage:
  python -m pipeline.smoke_test --step scrape
  python -m pipeline.smoke_test --step icp
  python -m pipeline.smoke_test --step dmm
  python -m pipeline.smoke_test --step validate
  python -m pipeline.smoke_test --step all

  python -m pipeline.smoke_test --step scrape --fixture   # zero Apify cost
"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

from pipeline.clients.ai_ark_client import AIArkClient
from pipeline.clients.openrouter_client import OpenRouterClient
from pipeline.config import Settings
from pipeline.db.client import ConnectionManager, migrate
from pipeline.db.repos import (
    CompanyRepository,
    ContactRepository,
    DMMCacheRepository,
    HMValidationRepository,
    JobRepository,
    RunRepository,
)
from pipeline.domain.active_client_matcher import ActiveClientMatcher
from pipeline.domain.models import PersonCandidate
from pipeline.stages.dedupe_companies import run_dedupe_companies
from pipeline.stages.dmm_search import run_dmm_search
from pipeline.stages.exclude_active_clients import run_exclude_active_clients
from pipeline.stages.icp_fit_check import run_icp_fit_check
from pipeline.stages.scrape_jobs import run_scrape_jobs
from pipeline.stages.validate_hiring_manager import run_validate_hiring_manager
from pipeline.utils.logging import setup_logging

logger = logging.getLogger(__name__)

SMOKE_MAX_JOBS = 3
SMOKE_MAX_COMPANIES_ICP = 1
SMOKE_MAX_VALIDATIONS = 1

STEPS = ("scrape", "exclude", "icp", "dmm", "validate", "all")


def _state_path(settings: Settings) -> Path:
    return settings.output_dir / "smoke_state.json"


def load_state(settings: Settings) -> dict[str, Any]:
    path = _state_path(settings)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"steps_completed": [], "run_id": None, "findings": []}


def save_state(settings: Settings, state: dict[str, Any]) -> None:
    settings.output_dir.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    _state_path(settings).write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")
    logger.info("Smoke state saved to %s", _state_path(settings))


def _load_kept_jobs(settings: Settings, jobs_repo: JobRepository, matcher: ActiveClientMatcher) -> list[dict[str, Any]]:
    all_jobs = jobs_repo.list_all()
    kept, _, _ = run_exclude_active_clients(all_jobs, matcher, settings.output_dir)
    return kept


def _serialize_findings(
    findings: list[tuple[dict[str, Any], PersonCandidate, list[UUID]]],
) -> list[dict[str, Any]]:
    return [
        {
            "company_id": str(company["id"]),
            "company_name": company.get("name"),
            "job_ids": [str(j) for j in job_ids],
            "person": {
                "full_name": person.full_name,
                "title": person.title,
                "location": person.location,
                "linkedin_url": person.linkedin_url,
                "about_snippet": person.about_snippet,
                "company_domain": person.company_domain,
                "target_title_searched": person.target_title_searched,
                "cascade_level": person.cascade_level,
            },
        }
        for company, person, job_ids in findings
    ]


def _findings_from_state(
    conn,
    state: dict[str, Any],
    jobs_repo: JobRepository,
) -> list[tuple[dict[str, Any], PersonCandidate, list[UUID]]]:
    from psycopg.rows import dict_row

    findings: list[tuple[dict[str, Any], PersonCandidate, list[UUID]]] = []
    for item in state.get("findings") or []:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM companies WHERE id = %s", (UUID(item["company_id"]),))
            company = cur.fetchone()
        if not company:
            continue
        p = item["person"]
        person = PersonCandidate(
            full_name=p["full_name"],
            title=p["title"],
            location=p.get("location"),
            linkedin_url=p["linkedin_url"],
            about_snippet=p.get("about_snippet"),
            company_domain=p.get("company_domain"),
            target_title_searched=p["target_title_searched"],
            cascade_level=p["cascade_level"],
        )
        job_ids = [UUID(j) for j in item["job_ids"]]
        findings.append((company, person, job_ids))
    return findings


def rebuild_findings_from_db(
    companies_repo: CompanyRepository,
    jobs_repo: JobRepository,
    dmm_cache: DMMCacheRepository,
    conn,
) -> list[tuple[dict[str, Any], PersonCandidate, list[UUID]]]:
    """Rebuild DMM findings from Supabase when resuming validate-only."""
    from psycopg.rows import dict_row

    findings: list[tuple[dict[str, Any], PersonCandidate, list[UUID]]] = []
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            SELECT c.* FROM companies c
            WHERE c.icp_decision = 'fit' AND c.dmm_status = 'found'
            ORDER BY c.updated_at DESC LIMIT 1
            """
        )
        company = cur.fetchone()
        if not company:
            return findings

        cur.execute(
            """
            SELECT * FROM dmm_search_log
            WHERE company_id = %s AND hit = true
            ORDER BY searched_at DESC LIMIT 1
            """,
            (company["id"],),
        )
        hit = cur.fetchone()
        if not hit or not hit.get("raw_response"):
            return findings

        people = hit["raw_response"].get("people") or []
        if not people:
            return findings

        person = AIArkClient._to_candidate(
            people[0],
            hit["target_title"],
            hit["cascade_level"],
        )
        job_ids = [
            j["id"]
            for j in jobs_repo.list_all()
            if j.get("company_id") == company["id"]
        ]
        if job_ids:
            findings.append((company, person, job_ids))
    return findings


def run_smoke_step(step: str, settings: Settings) -> dict[str, Any]:
    if not settings.supabase_db_url:
        raise ValueError("SUPABASE_POOLER_URL is required for smoke test")

    state = load_state(settings)
    stats: dict[str, Any] = {"step": step, "status": "success"}

    llm: OpenRouterClient | None = None
    ai_ark: AIArkClient | None = None

    if settings.openrouter_api_key:
        llm = OpenRouterClient(
            settings.openrouter_api_key,
            settings.openrouter_icp_model,
            settings.openrouter_hm_model,
            settings.openrouter_icp_fallback_model,
        )
    if settings.ai_ark_token or settings.fixture_mode:
        ai_ark = AIArkClient(
            token=settings.ai_ark_token,
            base_url=settings.ai_ark_base_url,
            fixture_path=settings.fixture_people_path if settings.fixture_mode else None,
        )

    matcher = ActiveClientMatcher(settings.active_clients_path)
    steps_to_run = list(STEPS[:-1]) if step == "all" else [step]

    db = ConnectionManager(settings.supabase_db_url)
    try:
        migrate(db.conn)
        runs_repo = RunRepository(db)
        jobs_repo = JobRepository(db)
        companies_repo = CompanyRepository(db)
        contacts_repo = ContactRepository(db)
        dmm_cache = DMMCacheRepository(db)
        hm_repo = HMValidationRepository(db)

        run_id = state.get("run_id")
        if run_id:
            run_id = UUID(str(run_id))
        else:
            run_id = runs_repo.start_run("smoke-test")
            state["run_id"] = str(run_id)

        findings: list[tuple[dict[str, Any], PersonCandidate, list[UUID]]] = []

        try:
            for current in steps_to_run:
                logger.info("=== Smoke step: %s ===", current)

                if current == "scrape":
                    count = run_scrape_jobs(
                        settings, run_id, jobs_repo, max_items=SMOKE_MAX_JOBS
                    )
                    stats["jobs_scraped"] = count
                    stats["api_calls"] = {"apify": 0 if settings.fixture_mode else 1}

                elif current == "exclude":
                    kept = _load_kept_jobs(settings, jobs_repo, matcher)
                    stats["jobs_after_exclusion"] = len(kept)
                    stats["api_calls"] = {}

                elif current == "icp":
                    kept = _load_kept_jobs(settings, jobs_repo, matcher)
                    groups = run_dedupe_companies(kept)
                    checked, fit_count = run_icp_fit_check(
                        settings,
                        groups,
                        companies_repo,
                        jobs_repo,
                        llm,
                        company_limit=SMOKE_MAX_COMPANIES_ICP,
                    )
                    stats["companies_checked"] = checked
                    stats["companies_fit"] = fit_count
                    stats["api_calls"] = {
                        "openrouter_icp": 0
                        if settings.fixture_mode or not llm
                        else min(checked, SMOKE_MAX_COMPANIES_ICP)
                    }

                elif current == "dmm":
                    if not ai_ark:
                        raise ValueError("AI_ARK_TOKEN required for dmm step (or use --fixture)")
                    credits, findings = run_dmm_search(
                        settings,
                        companies_repo,
                        jobs_repo,
                        dmm_cache,
                        ai_ark,
                        max_companies=1,
                        stop_after_first_api_call=True,
                    )
                    stats["ai_ark_credits_used"] = credits
                    stats["api_calls"] = {"ai_ark": 1 if credits else 0}
                    state["findings"] = _serialize_findings(findings)

                elif current == "validate":
                    if not findings:
                        findings = _findings_from_state(conn, state, jobs_repo)

                    if not findings:
                        findings = rebuild_findings_from_db(
                            companies_repo, jobs_repo, dmm_cache, conn
                        )

                    if not findings:
                        raise ValueError(
                            "No DMM findings in DB — run --step dmm first"
                        )

                    validated, kept = run_validate_hiring_manager(
                        settings,
                        findings,
                        jobs_repo,
                        contacts_repo,
                        hm_repo,
                        llm,
                        max_validations=SMOKE_MAX_VALIDATIONS,
                    )
                    stats["contacts_validated"] = validated
                    stats["contacts_kept"] = kept
                    stats["api_calls"] = {
                        "openrouter_hm": 0
                        if settings.fixture_mode or not llm
                        else min(validated, SMOKE_MAX_VALIDATIONS)
                    }

                if current not in state["steps_completed"]:
                    state["steps_completed"].append(current)
                save_state(settings, state)

        except Exception as exc:
            stats["status"] = "failed"
            stats["error"] = str(exc)
            save_state(settings, state)
            raise
        finally:
            if llm:
                llm.close()
            if ai_ark:
                ai_ark.close()
    finally:
        db.close()

    logger.info("Smoke step %s complete: %s", step, stats)
    return stats


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Cost-limited smoke test — one API call per service, resume via Supabase + smoke_state.json"
    )
    parser.add_argument(
        "--step",
        choices=STEPS,
        required=True,
        help="Pipeline step to run (or 'all' for full minimal-cost pass)",
    )
    parser.add_argument(
        "--fixture",
        action="store_true",
        help="Use fixtures for scrape/DMM; mock LLM unless OPENROUTER_API_KEY set",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    args = build_parser().parse_args(argv)
    settings = Settings.from_env(fixture_mode=args.fixture)
    stats = run_smoke_step(args.step, settings)
    print(json.dumps(stats, indent=2))
    return 0 if stats.get("status") == "success" else 1


if __name__ == "__main__":
    raise SystemExit(main())
