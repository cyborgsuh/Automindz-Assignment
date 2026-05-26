from __future__ import annotations

import logging
from pathlib import Path
from uuid import UUID

from pipeline.clients.apify_client import scrape_jobs
from pipeline.config import Settings
from pipeline.db.repos import JobRepository
from pipeline.domain.models import JobRecord

logger = logging.getLogger(__name__)


def run_scrape_jobs(
    settings: Settings,
    run_id: UUID,
    jobs_repo: JobRepository,
    *,
    max_items: int | None = None,
) -> int:
    fixture = settings.fixture_jobs_path if settings.fixture_mode or settings.skip_scrape else None
    if settings.skip_scrape and not settings.fixture_mode:
        logger.info("Skipping scrape; using jobs already in database")
        return len(jobs_repo.list_all())

    raw_jobs = scrape_jobs(settings.apify_token, fixture_path=fixture, max_items=max_items)
    logger.info("Upserting %d scraped jobs to Supabase ...", len(raw_jobs))
    count = 0
    for raw in raw_jobs:
        record = JobRecord.from_apify(raw)
        jobs_repo.upsert_job(run_id, record.to_db_dict())
        count += 1
    logger.info("Persisted %d jobs", count)
    return count
