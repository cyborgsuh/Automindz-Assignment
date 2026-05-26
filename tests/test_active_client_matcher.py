from pipeline.domain.active_client_matcher import ActiveClientMatcher
from pipeline.config import ROOT_DIR


def test_exact_active_client_match():
    matcher = ActiveClientMatcher(ROOT_DIR / "config" / "active_clients.json")
    match = matcher.match("Pfizer")
    assert match is not None
    assert match.client_name == "Pfizer"
    assert match.method == "exact"


def test_normalized_active_client_match():
    matcher = ActiveClientMatcher(ROOT_DIR / "config" / "active_clients.json")
    match = matcher.match("Roche (Switzerland)")
    assert match is not None
    assert match.client_name == "Roche"


def test_gsk_alias_match():
    matcher = ActiveClientMatcher(ROOT_DIR / "config" / "active_clients.json")
    match = matcher.match("GlaxoSmithKline GmbH")
    assert match is not None
    assert "GSK" in match.client_name or match.client_name == "GSK (GlaxoSmithKline)"
