from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from apify_client import ApifyClient

from pipeline.config import APIFY_ACTOR_ID, APIFY_MAX_ITEMS, LOCATION_SEARCH, TITLE_SEARCH

logger = logging.getLogger(__name__)


def build_apify_input(max_items: int | None = None) -> dict[str, Any]:
    return {
        "titleSearch": TITLE_SEARCH,
        "locationSearch": LOCATION_SEARCH,
        "timeRange": "7d",
        "EmploymentTypeFilter": ["FULL_TIME", "CONTRACTOR"],
        "removeAgency": True,
        "descriptionType": "text",
        "includeAi": False,
        "maxItems": max_items if max_items is not None else APIFY_MAX_ITEMS,
    }


def scrape_jobs(
    token: str,
    fixture_path: Path | None = None,
    *,
    max_items: int | None = None,
) -> list[dict[str, Any]]:
    if fixture_path:
        logger.info("Loading jobs from fixture %s", fixture_path)
        items = json.loads(fixture_path.read_text(encoding="utf-8"))
        if max_items is not None:
            items = items[:max_items]
        return items

    logger.info("Starting Apify actor %s", APIFY_ACTOR_ID)
    client = ApifyClient(token)
    run_input = build_apify_input(max_items=max_items)
    run = client.actor(APIFY_ACTOR_ID).call(run_input=run_input)
    dataset_id = run.default_dataset_id if not isinstance(run, dict) else run["defaultDatasetId"]
    items = list(client.dataset(dataset_id).iterate_items())
    if max_items is not None:
        items = items[:max_items]
    logger.info("Apify returned %d jobs", len(items))
    return items
