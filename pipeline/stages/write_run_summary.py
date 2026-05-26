from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


def write_run_summary(output_dir: Path, run_id: UUID, stats: dict[str, Any]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "run_id": str(run_id),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **stats,
    }
    path = output_dir / "run_summary.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    logger.info("Wrote run summary to %s", path)
    return path
