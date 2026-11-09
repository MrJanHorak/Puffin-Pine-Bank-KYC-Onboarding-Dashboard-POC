"""One JSON line per event in logs/run.jsonl (hard rule H5).

Only IDs, codes and counts are logged. A field outside ALLOWED_FIELDS is
dropped, so a statement or a card number can't reach the log by accident.
"""
import json
import uuid
from datetime import datetime, timezone

from triage import LOG_DIR

ALLOWED_FIELDS = {
    "dispute_id", "tool", "outcome", "reason", "reasons", "flags", "queue",
    "reviewer", "readiness", "call", "mode", "tokens_in", "tokens_out",
    "prompt_tokens_est", "cost_usd", "section", "review_case_id", "approver_role",
    "txn_count", "ms",
}

_correlation = {"id": None}


def new_correlation_id() -> str:
    _correlation["id"] = uuid.uuid4().hex[:12]
    return _correlation["id"]


def log_event(event: str, **fields) -> None:
    line = {"time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "event": event, "correlation_id": _correlation["id"]}
    line.update({k: v for k, v in fields.items() if k in ALLOWED_FIELDS})
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_DIR / "run.jsonl", "a", encoding="utf-8") as handle:
        handle.write(json.dumps(line) + "\n")
