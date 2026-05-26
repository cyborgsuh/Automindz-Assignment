from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from pipeline.clients.ai_ark_client import AIArkClient
from pipeline.clients.openrouter_client import OpenRouterClient
from pipeline.config import LOCATION_SEARCH, TITLE_SEARCH, Settings
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
from pipeline.stages.dedupe_companies import run_dedupe_companies
from pipeline.stages.dmm_search import run_dmm_search
from pipeline.stages.exclude_active_clients import run_exclude_active_clients
from pipeline.stages.icp_fit_check import run_icp_fit_check
from pipeline.stages.scrape_jobs import run_scrape_jobs
from pipeline.stages.validate_hiring_manager import run_validate_hiring_manager
from pipeline.stages.write_run_summary import write_run_summary

logger = logging.getLogger(__name__)


def _config_hash(settings: Settings) -> str:
    payload = {
        "titles": TITLE_SEARCH,
        "locations": LOCATION_SEARCH,
        "fixture": settings.fixture_mode,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:16]


def run_pipeline(settings: Settings) -> dict[str, Any]:
    settings.validate_for_run()
    stats: dict[str, Any] = {
        "jobs_scraped": 0,
        "jobs_after_exclusion": 0,
        "companies_checked": 0,
        "companies_fit": 0,
        "contacts_validated": 0,
        "contacts_kept": 0,
        "ai_ark_credits_used": 0,
        "active_client_hiring_signals": 0,
        "status": "success",
    }

    llm: OpenRouterClient | None = None
    ai_ark: AIArkClient | None = None

    if settings.openrouter_api_key:
        llm = OpenRouterClient(
            settings.openrouter_api_key,
            settings.openrouter_icp_model,
            settings.openrouter_hm_model,
            settings.openrouter_icp_fallback_model,
        )
    elif not settings.fixture_mode:
        logger.warning("No OPENROUTER_API_KEY; LLM stages will fail unless in fixture mode")

    if settings.ai_ark_token or settings.fixture_mode:
        ai_ark = AIArkClient(
            token=settings.ai_ark_token,
            base_url=settings.ai_ark_base_url,
            fixture_path=settings.fixture_people_path if settings.fixture_mode else None,
        )

    matcher = ActiveClientMatcher(settings.active_clients_path)

    db = ConnectionManager(settings.supabase_db_url)
    try:
        migrate(db.conn)
        runs_repo = RunRepository(db)
        jobs_repo = JobRepository(db)
        companies_repo = CompanyRepository(db)
        contacts_repo = ContactRepository(db)
        dmm_cache = DMMCacheRepository(db)
        hm_repo = HMValidationRepository(db)

        run_id = runs_repo.start_run(_config_hash(settings))
        logger.info("=== Pipeline run %s started ===", run_id)
        try:
            logger.info("--- Stage 1/5: Scrape jobs ---")
            stats["jobs_scraped"] = run_scrape_jobs(settings, run_id, jobs_repo)
            logger.info("Scrape done: %d jobs in database", stats["jobs_scraped"])

            logger.info("--- Stage 2/5: Exclude active clients ---")
            all_jobs = jobs_repo.list_all()
            kept_jobs, _, active_signals = run_exclude_active_clients(
                all_jobs, matcher, settings.output_dir
            )
            stats["jobs_after_exclusion"] = len(kept_jobs)
            stats["active_client_hiring_signals"] = active_signals
            logger.info("Excluded active clients: %d jobs remain", len(kept_jobs))

            logger.info("--- Stage 3/5: ICP fit-check ---")
            groups = run_dedupe_companies(kept_jobs)
            logger.info("Starting ICP fit-check on %d companies", len(groups))
            checked, fit_count = run_icp_fit_check(
                settings, groups, companies_repo, jobs_repo, llm
            )
            stats["companies_checked"] = checked
            stats["companies_fit"] = fit_count
            logger.info("ICP complete: %d checked, %d fit", checked, fit_count)

            if ai_ark:
                logger.info("--- Stage 4/5: DMM search ---")
                credits, findings = run_dmm_search(
                    settings, companies_repo, jobs_repo, dmm_cache, ai_ark
                )
                stats["ai_ark_credits_used"] = credits
                logger.info("DMM complete: %d credits, %d findings", credits, len(findings))
                logger.info("--- Stage 5/5: Validate hiring managers ---")
                validated, kept = run_validate_hiring_manager(
                    settings, findings, jobs_repo, contacts_repo, hm_repo, llm
                )
                stats["contacts_validated"] = validated
                stats["contacts_kept"] = kept
                logger.info("Validation complete: %d validated, %d kept", validated, kept)
            else:
                logger.warning("Skipping DMM — no AI_ARK_TOKEN and not in fixture mode")

            write_run_summary(settings.output_dir, run_id, stats)
            runs_repo.finish_run(run_id, "success", stats)
            logger.info("=== Pipeline run %s finished: %s ===", run_id, stats)
        except Exception as exc:
            stats["status"] = "failed"
            stats["error"] = str(exc)
            runs_repo.finish_run(run_id, "failed", stats)
            logger.exception("Pipeline failed")
            raise
        finally:
            if llm:
                llm.close()
            if ai_ark:
                ai_ark.close()

    finally:
        db.close()

    return stats
