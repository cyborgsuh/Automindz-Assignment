from __future__ import annotations

import argparse
import sys

from pipeline.config import Settings
from pipeline.orchestrator import run_pipeline
from pipeline.utils.logging import setup_logging


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PharmaTalent Europe lead discovery pipeline")
    parser.add_argument(
        "--fixture",
        action="store_true",
        help="Run using local fixtures (no Apify/AI Ark spend; mock LLM unless OPENROUTER_API_KEY set)",
    )
    parser.add_argument(
        "--skip-scrape",
        action="store_true",
        help="Skip Apify scrape and use jobs already in Supabase",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    setup_logging()
    args = build_parser().parse_args(argv)
    settings = Settings.from_env(fixture_mode=args.fixture, skip_scrape=args.skip_scrape)
    stats = run_pipeline(settings)
    print(f"Pipeline complete: {stats}")
    return 0 if stats.get("status") == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
