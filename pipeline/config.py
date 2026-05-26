from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parent.parent
load_dotenv(ROOT_DIR / ".env")


TITLE_SEARCH: list[str] = [
    "Regulatory Affairs Manager",
    "Senior Regulatory Affairs Manager",
    "Director Regulatory Affairs",
    "Head of Regulatory Affairs",
    "Regulatory Affairs Specialist",
    "Clinical Operations Manager",
    "Director Clinical Operations",
    "Head of Clinical Operations",
    "Senior Clinical Research Associate",
    "Clinical Trial Manager",
    "Clinical Project Manager",
    "Pharmacovigilance Manager",
    "Drug Safety Officer",
    "Qualified Person for Pharmacovigilance",
    "Medical Affairs Lead",
    "Medical Science Liaison",
    "Senior Medical Advisor",
]

LOCATION_SEARCH: list[str] = [
    "Germany",
    "Switzerland",
    "Netherlands",
    "Belgium",
    "Denmark",
    "Sweden",
    "Ireland",
    "France",
    "United Kingdom",
    "Spain",
    "Italy",
    "Austria",
    "Finland",
    "Norway",
]

APIFY_ACTOR_ID = "vIGxjRrHqDTPuE6M4"
APIFY_MAX_ITEMS = int(os.getenv("APIFY_MAX_ITEMS", "2"))

EU_REGIONS: dict[str, list[str]] = {
    "DACH": ["Germany", "Austria", "Switzerland"],
    "Benelux": ["Belgium", "Netherlands", "Luxembourg"],
    "Nordics": ["Denmark", "Sweden", "Finland", "Norway"],
    "UKI": ["United Kingdom", "Ireland"],
    "Southern Europe": ["France", "Spain", "Italy"],
}

COUNTRY_TO_REGION: dict[str, str] = {}
for region, countries in EU_REGIONS.items():
    for country in countries:
        COUNTRY_TO_REGION[country] = region


@dataclass
class Settings:
    apify_token: str = ""
    ai_ark_token: str = ""
    ai_ark_base_url: str = "https://api.ai-ark.com/api/developer-portal/v1"
    openrouter_api_key: str = ""
    openrouter_icp_model: str = "perplexity/sonar"
    openrouter_icp_fallback_model: str = "openrouter/free"
    openrouter_hm_model: str = "meta-llama/llama-3.1-8b-instruct"
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_db_url: str = ""
    fixture_mode: bool = False
    skip_scrape: bool = False
    fixture_jobs_path: Path = field(default_factory=lambda: ROOT_DIR / "fixtures" / "sample_apify_jobs.json")
    fixture_people_path: Path = field(default_factory=lambda: ROOT_DIR / "fixtures" / "sample_people_search.json")
    active_clients_path: Path = field(default_factory=lambda: ROOT_DIR / "config" / "active_clients.json")
    output_dir: Path = field(default_factory=lambda: ROOT_DIR / "output")

    @classmethod
    def from_env(cls, **overrides: object) -> Settings:
        settings = cls(
            apify_token=os.getenv("APIFY_TOKEN", ""),
            ai_ark_token=os.getenv("AI_ARK_TOKEN", ""),
            ai_ark_base_url=os.getenv(
                "AI_ARK_BASE_URL",
                "https://api.ai-ark.com/api/developer-portal/v1",
            ),
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY", ""),
            openrouter_icp_model=os.getenv("OPENROUTER_ICP_MODEL", "perplexity/sonar"),
            openrouter_icp_fallback_model=os.getenv(
                "OPENROUTER_ICP_FALLBACK_MODEL",
                "openrouter/free",
            ),
            openrouter_hm_model=os.getenv("OPENROUTER_HM_MODEL", "meta-llama/llama-3.1-8b-instruct"),
            supabase_url=os.getenv("SUPABASE_URL", ""),
            supabase_service_role_key=os.getenv("SUPABASE_SERVICE_ROLE_KEY", ""),
            supabase_db_url=os.getenv("SUPABASE_POOLER_URL") or os.getenv("SUPABASE_DB_URL", ""),
        )
        for key, value in overrides.items():
            setattr(settings, key, value)
        return settings

    def validate_for_run(self) -> None:
        if not self.supabase_db_url:
            raise ValueError("SUPABASE_POOLER_URL is required")
        if not self.fixture_mode and not self.skip_scrape and not self.apify_token:
            raise ValueError("APIFY_TOKEN is required unless --fixture or --skip-scrape")
        if not self.fixture_mode and not self.openrouter_api_key:
            raise ValueError("OPENROUTER_API_KEY is required unless --fixture with mocked LLM stages")
