from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

ICP_SYSTEM_PROMPT = """You are an expert biotech/pharma recruiter evaluating whether a company fits an ICP.
Use web search to inspect the company's website and public information.
Apply these rules strictly:
- Target: biotech, pharma, CRO, or CDMO with in-house clinical trials
- Size: 50-2000 employees globally
- Must have EU/EEA/UK/CH/Norway operational footprint
- Disqualify: universities, hospitals, staffing agencies, device-only, cosmetics/nutra, fully remote with no EU entity

Respond in strict JSON:
{"decision": "fit" | "not_fit", "rationale": "1-3 sentences referencing website findings", "confidence": "high" | "medium" | "low"}
"""

ICP_FALLBACK_SYSTEM_PROMPT = """You are an expert biotech/pharma recruiter evaluating whether a company fits an ICP.
You do not have live web search. Use the LinkedIn metadata and any homepage excerpt provided.
Apply these rules strictly:
- Target: biotech, pharma, CRO, or CDMO with in-house clinical trials
- Size: 50-2000 employees globally
- Must have EU/EEA/UK/CH/Norway operational footprint
- Disqualify: universities, hospitals, staffing agencies, device-only, cosmetics/nutra, fully remote with no EU entity
- If evidence is thin, prefer not_fit with low confidence rather than guessing.

Respond in strict JSON:
{"decision": "fit" | "not_fit", "rationale": "1-3 sentences referencing provided data", "confidence": "high" | "medium" | "low"}
"""

_PAYMENT_ERROR_CODES = frozenset({402, 403})
_FALLBACK_RETRY_CODES = frozenset({402, 403, 404, 429})

HM_SYSTEM_PROMPT = """You are an expert at evaluating whether a person could plausibly be the hiring manager or
final decision-maker for a specific open job.

Rules:
- Hiring managers are typically the role-level owner or the function-head one to two levels above the open role.
- Talent / People / HR leaders qualify ONLY if the open role is junior or mid-level and the company is under 200 employees.
- When in doubt, say no.

Answer in strict JSON:
{"decision": "yes" | "no", "reason": "<one sentence>"}
"""


class OpenRouterClient:
    def __init__(
        self,
        api_key: str,
        icp_model: str,
        hm_model: str,
        icp_fallback_model: str = "openrouter/free",
    ) -> None:
        self.api_key = api_key
        self.icp_model = icp_model
        self.hm_model = hm_model
        self.icp_fallback_model = icp_fallback_model
        self._client = httpx.Client(timeout=120.0)

    def _chat(
        self,
        model: str,
        system: str,
        user: str,
        *,
        web_search: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }
        if web_search:
            payload["plugins"] = [{"id": "web"}]

        logger.info("OpenRouter POST model=%s web=%s", model, web_search)
        response = self._client.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/pharmatalent-pipeline",
                "X-Title": "PharmaTalent Pipeline",
            },
            json=payload,
        )
        response.raise_for_status()
        data = response.json()
        logger.info("OpenRouter OK model=%s", model)
        content = data["choices"][0]["message"]["content"]
        return self._parse_json(content)

    @staticmethod
    def _parse_json(content: str) -> dict[str, Any]:
        content = content.strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            raise

    @staticmethod
    def _strip_html(html: str) -> str:
        html = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<style[^>]*>.*?</style>", " ", html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r"<[^>]+>", " ", html)
        return re.sub(r"\s+", " ", html).strip()

    def _fetch_homepage_snippet(self, domain: str | None, *, max_chars: int = 2000) -> str | None:
        if not domain:
            return None
        domain = domain.strip().lower().removeprefix("www.")
        if not domain or " " in domain or domain in {"linkedin.com", "facebook.com"}:
            return None
        url = f"https://{domain}"
        try:
            response = self._client.get(
                url,
                follow_redirects=True,
                timeout=8.0,
                headers={"User-Agent": "PharmaTalentPipeline/1.0 (ICP fit-check fallback)"},
            )
            response.raise_for_status()
            content_type = response.headers.get("content-type", "")
            if "html" not in content_type and "<html" not in response.text[:500].lower():
                return None
            text = self._strip_html(response.text)
            return text[:max_chars] if text else None
        except httpx.HTTPError as exc:
            logger.debug("Homepage fetch failed for %s: %s", domain, exc)
            return None

    def _build_icp_user_prompt(self, company: dict[str, Any], *, website_snippet: str | None = None) -> str:
        website_block = website_snippet or "none"
        return f"""Company: {company.get('name')}
Domain: {company.get('domain') or 'unknown'}
LinkedIn industry: {company.get('industry') or 'unknown'}
Employee count: {company.get('employee_count') or 'unknown'}
Headquarters: {company.get('headquarters') or 'unknown'}
LinkedIn description: {company.get('description') or 'none'}
Homepage excerpt: {website_block}

Research this company and decide if it fits the ICP."""

    def _icp_fit_check_fallback(self, company: dict[str, Any]) -> dict[str, Any]:
        domain = company.get("domain")
        logger.info("ICP fallback: fetching homepage for %s (domain=%s)", company.get("name"), domain or "none")
        website_snippet = self._fetch_homepage_snippet(domain)
        logger.info("ICP fallback: homepage %s", "found" if website_snippet else "skipped/empty")
        user_prompt = self._build_icp_user_prompt(company, website_snippet=website_snippet)

        fallback_models: list[tuple[str, str]] = []
        if self.icp_fallback_model:
            fallback_models.append((self.icp_fallback_model, "free"))
        if self.hm_model and self.hm_model != self.icp_fallback_model:
            fallback_models.append((self.hm_model, "cheap"))

        last_exc: httpx.HTTPStatusError | None = None
        for model, tier in fallback_models:
            try:
                result = self._chat(
                    model,
                    ICP_FALLBACK_SYSTEM_PROMPT,
                    user_prompt,
                    web_search=False,
                )
                note = f" (ICP fallback [{tier}]: LinkedIn metadata"
                if website_snippet:
                    note += " + homepage excerpt"
                note += ")"
                rationale = result.get("rationale", "")
                result["rationale"] = f"{rationale}{note}".strip()
                if result.get("confidence") == "high" and not website_snippet:
                    result["confidence"] = "medium"
                logger.info("ICP fallback succeeded with model %s", model)
                return result
            except httpx.HTTPStatusError as exc:
                last_exc = exc
                if exc.response.status_code in _FALLBACK_RETRY_CODES:
                    logger.warning(
                        "ICP fallback model %s unavailable (%s).",
                        model,
                        exc.response.status_code,
                    )
                    continue
                raise

        if last_exc is not None:
            raise last_exc
        raise RuntimeError("No ICP fallback models configured")

    def icp_fit_check(self, company: dict[str, Any]) -> dict[str, Any]:
        user_prompt = self._build_icp_user_prompt(company)
        logger.info("ICP trying primary model %s for %s", self.icp_model, company.get("name"))
        try:
            return self._chat(self.icp_model, ICP_SYSTEM_PROMPT, user_prompt, web_search=True)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in _PAYMENT_ERROR_CODES:
                raise
            logger.warning(
                "ICP primary model %s unavailable (%s). Falling back to %s.",
                self.icp_model,
                exc.response.status_code,
                self.icp_fallback_model,
            )
            return self._icp_fit_check_fallback(company)

    def validate_hiring_manager(self, payload: dict[str, Any]) -> dict[str, Any]:
        user_prompt = f"""SCRAPED JOB
-----------
Title:        {payload['scraped_job_title']}
Location:     {payload['scraped_job_location']}
Company:      {payload['company_name']}
Company size: {payload['company_size_band']}
Description (first ~500 chars):
{payload['scraped_job_description_snippet']}

CANDIDATE PERSON
----------------
Full name:    {payload['person_full_name']}
Current title: {payload['person_title']}
Location:     {payload['person_location']}
About:        {payload['person_about_snippet']}

Could this person plausibly be the hiring manager or final decision-maker for this specific role?"""
        return self._chat(self.hm_model, HM_SYSTEM_PROMPT, user_prompt, web_search=False)

    def mock_icp_fit_check(self, company: dict[str, Any]) -> dict[str, Any]:
        employees = company.get("employee_count") or 0
        if employees < 50 or employees > 2000:
            return {
                "decision": "not_fit",
                "rationale": "Employee count outside 50-2000 band (fixture mock).",
                "confidence": "high",
            }
        return {
            "decision": "fit",
            "rationale": "Biotech/pharma company in EU with appropriate size (fixture mock).",
            "confidence": "medium",
        }

    def mock_validate_hm(self, payload: dict[str, Any]) -> dict[str, Any]:
        title = payload["person_title"].lower()
        job = payload["scraped_job_title"].lower()
        if any(k in title for k in ("director", "head", "vp", "talent", "people", "hr")):
            if "associate" in title and "senior" not in title:
                return {"decision": "no", "reason": "Too junior for this requisition (fixture mock)."}
            if "regulatory" in job and "regulatory" in title:
                return {"decision": "yes", "reason": "Functional RA leader owns this requisition (fixture mock)."}
            if any(k in job for k in ("clinical", "trial", "research")) and "clinical" in title:
                return {"decision": "yes", "reason": "Clinical ops leader owns this requisition (fixture mock)."}
            if any(k in title for k in ("talent", "people", "hr")):
                return {"decision": "yes", "reason": "Talent leader plausible for this level (fixture mock)."}
        return {"decision": "no", "reason": "Title does not plausibly own this requisition (fixture mock)."}

    def close(self) -> None:
        self._client.close()
