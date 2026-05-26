from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import httpx

from pipeline.domain.models import PersonCandidate
from pipeline.utils.urls import canonicalize_linkedin_url

logger = logging.getLogger(__name__)

MAX_RESULTS = 2
PEOPLE_SEARCH_PATH = "/people"


def _any_include(values: list[str]) -> dict[str, Any]:
    return {"any": {"include": values}}


def _any_include_smart(values: list[str]) -> dict[str, Any]:
    return {"any": {"include": {"mode": "SMART", "content": values}}}


class AIArkClient:
    def __init__(self, token: str, base_url: str, fixture_path: Path | None = None) -> None:
        self.token = token
        self.base_url = base_url.rstrip("/")
        self.fixture_path = fixture_path
        self._client = httpx.Client(timeout=httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=5.0))

    def people_search(
        self,
        company_name: str,
        company_domain: str | None,
        target_title: str,
        location: str,
        cascade_level: str,
    ) -> list[PersonCandidate]:
        if self.fixture_path:
            return self._search_fixture(company_name, target_title, cascade_level)

        contact: dict[str, Any] = {
            "experience": {
                "current": {"title": _any_include_smart([target_title])},
            },
        }

        account: dict[str, Any] = {}
        if company_domain:
            account["domain"] = _any_include([company_domain.lower().removeprefix("www.")])
        if company_name:
            account["name"] = _any_include_smart([company_name])
        # When domain scopes the company, extra location filters often zero out results.
        if location and location.lower() != "worldwide" and not company_domain:
            account["location"] = _any_include([location.lower()])

        body: dict[str, Any] = {
            "page": 0,
            "size": MAX_RESULTS,
            "contact": contact,
        }
        if account:
            body["account"] = account

        headers = {
            "X-TOKEN": self.token,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        url = f"{self.base_url}{PEOPLE_SEARCH_PATH}"
        response = self._post_with_retry(url, headers, body)
        data = response.json()

        results = data.get("content") or data.get("results") or data.get("data") or []
        logger.info(
            "AI Ark people search for %s / %s: %d results (totalElements=%s)",
            company_name,
            target_title,
            len(results),
            data.get("totalElements"),
        )
        return [self._to_candidate(r, target_title, cascade_level) for r in results[:MAX_RESULTS]]

    def _post_with_retry(
        self,
        url: str,
        headers: dict[str, str],
        body: dict[str, Any],
        *,
        max_attempts: int = 4,
    ) -> httpx.Response:
        last_response: httpx.Response | None = None
        for attempt in range(max_attempts):
            response = self._client.post(url, headers=headers, json=body)
            last_response = response
            if response.status_code == 429 and attempt + 1 < max_attempts:
                wait_s = 15 * (attempt + 1)
                logger.warning("AI Ark rate limited; retrying in %ss", wait_s)
                time.sleep(wait_s)
                continue
            response.raise_for_status()
            return response
        assert last_response is not None
        last_response.raise_for_status()
        raise RuntimeError("unreachable")

    def _search_fixture(
        self,
        company_name: str,
        target_title: str,
        cascade_level: str,
    ) -> list[PersonCandidate]:
        data = json.loads(self.fixture_path.read_text(encoding="utf-8"))
        results = data.get("results", [])[:MAX_RESULTS]
        logger.info("Using AI Ark fixture for %s / %s", company_name, target_title)
        return [self._to_candidate(r, target_title, cascade_level) for r in results]

    @staticmethod
    def _to_candidate(raw: dict[str, Any], target_title: str, cascade_level: str) -> PersonCandidate:
        profile = raw.get("profile") or raw
        linkedin = (
            profile.get("linkedin_url")
            or profile.get("linkedinUrl")
            or raw.get("linkedin_url")
            or (raw.get("link") or {}).get("linkedin")
            or ""
        )
        location = profile.get("location") or raw.get("location")
        if isinstance(location, dict):
            location = location.get("default") or location.get("short")
        about = profile.get("summary") or profile.get("about_snippet") or profile.get("about") or raw.get("about_snippet")
        company_domain = None
        company = raw.get("company") or profile.get("company")
        if isinstance(company, dict):
            company_domain = company.get("domain")
        return PersonCandidate(
            full_name=profile.get("full_name") or profile.get("fullName") or raw.get("full_name") or "",
            title=profile.get("title") or profile.get("headline") or raw.get("title") or "",
            location=location,
            linkedin_url=canonicalize_linkedin_url(linkedin),
            about_snippet=about,
            company_domain=company_domain or profile.get("company_domain") or raw.get("company_domain"),
            target_title_searched=target_title,
            cascade_level=cascade_level,
        )

    def close(self) -> None:
        self._client.close()
