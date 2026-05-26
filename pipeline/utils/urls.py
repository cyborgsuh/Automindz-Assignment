from __future__ import annotations

import re


def canonicalize_linkedin_url(url: str) -> str:
    text = url.strip().rstrip("/")
    text = re.sub(r"\?.*$", "", text)
    text = re.sub(r"^https://[a-z]{2}\.linkedin\.com/", "https://www.linkedin.com/", text)
    if not text.startswith("http"):
        text = f"https://www.linkedin.com/in/{text.lstrip('/')}"
    return text
