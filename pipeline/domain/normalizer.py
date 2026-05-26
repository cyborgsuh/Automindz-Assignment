from __future__ import annotations

import re
import unicodedata

from unidecode import unidecode

LEGAL_SUFFIXES = [
    r"gmbh",
    r"ag",
    r"se",
    r"s\.a\.",
    r"s\.a\.s\.",
    r"s\.p\.a\.",
    r"inc\.?",
    r"ltd\.?",
    r"llc",
    r"plc",
    r"& co\. kg",
    r"holding",
    r"limited",
    r"corp\.?",
    r"corporation",
]


def normalize_company_name(name: str) -> str:
    text = name.strip().lower()
    text = re.sub(r"\([^)]*\)", "", text)
    for suffix in LEGAL_SUFFIXES:
        text = re.sub(rf",?\s+{suffix}\.?\s*$", "", text, flags=re.IGNORECASE)
        text = re.sub(rf"\s+{suffix}\.?\s*$", "", text, flags=re.IGNORECASE)
    text = re.sub(r"[^\w\s&-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_person_name(name: str) -> str:
    text = unidecode(name.strip().lower())
    text = unicodedata.normalize("NFKD", text)
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_root_domain(domain_or_url: str | None) -> str | None:
    if not domain_or_url:
        return None
    value = domain_or_url.strip().lower()
    if value.startswith("http"):
        match = re.search(r"https?://(?:www\.)?([^/]+)", value)
        if not match:
            return None
        value = match.group(1)
    value = value.split("/")[0]
    parts = value.split(".")
    if len(parts) >= 2:
        domain = ".".join(parts[-2:])
    else:
        domain = value or None
    generic = {
        "linkedin.com",
        "facebook.com",
        "twitter.com",
        "myworkdayjobs.com",
        "greenhouse.io",
        "lever.co",
        "smartrecruiters.com",
    }
    if domain in generic:
        return None
    return domain


def domain_root_label(domain: str | None) -> str | None:
    if not domain:
        return None
    return domain.split(".")[0]
