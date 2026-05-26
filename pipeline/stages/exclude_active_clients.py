from __future__ import annotations

import csv
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.domain.active_client_matcher import ActiveClientMatcher

logger = logging.getLogger(__name__)


def run_exclude_active_clients(
    jobs: list[dict[str, Any]],
    matcher: ActiveClientMatcher,
    output_dir: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    kept: list[dict[str, Any]] = []
    active_hiring: list[dict[str, Any]] = []
    detected_at = datetime.now(timezone.utc).isoformat()

    for job in jobs:
        match = matcher.match(job.get("organization_name", ""), job.get("organization_url"))
        if match:
            active_hiring.append(
                {
                    "client_name": match.client_name,
                    "matched_company_name_raw": match.matched_raw,
                    "scraped_job_title": job.get("title"),
                    "scraped_job_url": job.get("job_url"),
                    "location": ", ".join(job.get("locations_derived") or []),
                    "posted_at": job.get("date_posted").isoformat() if job.get("date_posted") else "",
                    "detected_at": detected_at,
                }
            )
            logger.info("Excluded active client match: %s -> %s", match.matched_raw, match.client_name)
            continue
        kept.append(job)

    if active_hiring:
        output_dir.mkdir(parents=True, exist_ok=True)
        csv_path = output_dir / "active_client_hiring.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(
                f,
                fieldnames=[
                    "client_name",
                    "matched_company_name_raw",
                    "scraped_job_title",
                    "scraped_job_url",
                    "location",
                    "posted_at",
                    "detected_at",
                ],
            )
            writer.writeheader()
            writer.writerows(active_hiring)
        logger.info("Wrote %d active client hiring signals to %s", len(active_hiring), csv_path)

    logger.info("Jobs after active-client exclusion: %d (removed %d)", len(kept), len(jobs) - len(kept))
    return kept, active_hiring, len(active_hiring)
