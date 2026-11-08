"""Adapter between the POC server and the card dispute triage build in disputes/."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "disputes"))
from triage import pipeline  # noqa: E402

PAGE = ROOT / "disputes" / "web" / "index.html"


def run(dispute_id) -> dict:
    if not isinstance(dispute_id, str) or not re.fullmatch(r"DSP-\d{2}", dispute_id):
        raise ValueError("Use a dispute ID such as DSP-31.")
    try:
        return pipeline.run_dispute(dispute_id)
    except pipeline.DisputeNotFound as exc:
        raise ValueError(str(exc)) from exc
