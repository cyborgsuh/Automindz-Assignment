from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein

from pipeline.domain.normalizer import domain_root_label, extract_root_domain, normalize_company_name


@dataclass
class ActiveClientMatch:
    client_name: str
    matched_raw: str
    method: str


class ActiveClientMatcher:
    def __init__(self, config_path: Path) -> None:
        data = json.loads(config_path.read_text(encoding="utf-8"))
        self.clients: list[str] = data["clients"]
        self.normalized_clients = {normalize_company_name(c): c for c in self.clients}
        self.aliases = data.get("aliases", {})
        self.normalized_aliases: dict[str, str] = {}
        for canonical, alias_list in self.aliases.items():
            canon_norm = normalize_company_name(canonical)
            for alias in alias_list:
                self.normalized_aliases[normalize_company_name(alias)] = self.normalized_clients.get(
                    canon_norm, canonical
                )

    def match(self, company_name: str, company_url: str | None = None) -> ActiveClientMatch | None:
        raw = company_name.strip()
        normalized = normalize_company_name(raw)

        if normalized in self.normalized_clients:
            return ActiveClientMatch(self.normalized_clients[normalized], raw, "exact")

        if normalized in self.normalized_aliases:
            return ActiveClientMatch(self.normalized_aliases[normalized], raw, "alias")

        domain = extract_root_domain(company_url)
        domain_label = domain_root_label(domain)
        if domain_label:
            for norm, canonical in self.normalized_clients.items():
                if domain_label == norm.replace(" ", ""):
                    return ActiveClientMatch(canonical, raw, "domain")
                if domain_label in norm.replace(" ", ""):
                    return ActiveClientMatch(canonical, raw, "domain")

        best_score = 0.0
        best_client = None
        for norm, canonical in self.normalized_clients.items():
            score = fuzz.ratio(normalized, norm)
            if score >= 90 and score > best_score:
                best_score = score
                best_client = canonical
            if Levenshtein.distance(normalized, norm) <= 2 and score > best_score:
                best_score = score
                best_client = canonical

        if best_client:
            return ActiveClientMatch(best_client, raw, "fuzzy")

        return None
