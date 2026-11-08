"""The five tools the triage build uses. Each one logs a `tool_call` line.

  get_dispute            read
  get_transactions       read
  search_policy          read
  open_review_case       draft_for_human   (idempotent on dispute_id)
  send_customer_message  write_with_approval

Refunds, credits and chargebacks have no tool at all (hard rule H1).
Faults such as "search_policy:unavailable" are injected by the eval runner
so failure paths can be tested without breaking anything real.
"""
import json
import re
import time
from pathlib import Path

from triage import POLICY_DIR, STATE_DIR, data_layer, load_yaml
from triage.log import log_event

APPROVER_ROLES = ("card_analyst", "senior_analyst")


class PolicyUnavailable(Exception):
    """Policy search failed or took too long."""


def _logged(tool: str, started: float, outcome: str, **fields) -> None:
    log_event("tool_call", tool=tool, outcome=outcome,
              ms=round((time.perf_counter() - started) * 1000), **fields)


def get_dispute(dispute_id: str) -> dict | None:
    started = time.perf_counter()
    dispute = data_layer.load_dispute(dispute_id)
    _logged("get_dispute", started, "ok" if dispute else "not_found", dispute_id=dispute_id)
    return dispute


def get_transactions(card_id: str, dispute_id: str) -> dict:
    started = time.perf_counter()
    rows = data_layer.transactions_for(card_id)
    _logged("get_transactions", started, "ok", dispute_id=dispute_id, txn_count=len(rows))
    return rows


def _raw_search(category: str, faults: tuple) -> dict:
    """Keyword search over policy_manual/. Faults simulate an outage or a slow index."""
    if "search_policy:unavailable" in faults:
        raise PolicyUnavailable("policy index unavailable")
    if "search_policy:slow" in faults:
        raise TimeoutError("policy search took longer than the limit")
    words = {"NOT_RECEIVED": "not received", "NOT_AS_DESCRIBED": "not as described"}[category]
    for path in sorted(POLICY_DIR.glob("DP-*.md")):
        text = path.read_text(encoding="utf-8")
        if words in text.lower():
            sections = re.findall(r"Section (DP-\d\.\d)\. ([^\n]+)", text)
            section_id, body = next(((s, b) for s, b in sections if words in b.lower()),
                                    sections[-1])
            return {"section": section_id, "text": body}
    raise PolicyUnavailable("no matching section")


def search_policy(category: str, dispute_id: str, faults: tuple = ()) -> dict:
    """Return {"outcome": "ok", "section", "text"} or {"outcome": "unavailable"} (R8, E9)."""
    started = time.perf_counter()
    # TODO(Task 5): a failure or a slow search should return {"outcome": "unavailable"} and log it.
    found = _raw_search(category, faults)
    _logged("search_policy", started, "ok", dispute_id=dispute_id, section=found["section"])
    return {"outcome": "ok", **found}


def open_review_case(dispute_id: str, reason: str, store: Path | None = None) -> dict:
    """Save a DRAFT fraud review case. A rerun returns the case already open (E11)."""
    started = time.perf_counter()
    store = Path(store or STATE_DIR / "review_cases.json")
    cases = json.loads(store.read_text(encoding="utf-8")) if store.exists() else []
    for case in cases:
        if case["dispute_id"] == dispute_id:
            _logged("open_review_case", started, "duplicate_suppressed",
                    dispute_id=dispute_id, review_case_id=case["review_case_id"])
            return {"review_case_id": case["review_case_id"], "created": False}
    case = {"review_case_id": f"SPECIMEN-FRC-{len(cases) + 1:04d}",
            "dispute_id": dispute_id, "reason": reason, "status": "DRAFT"}
    store.parent.mkdir(parents=True, exist_ok=True)
    store.write_text(json.dumps(cases + [case], indent=2), encoding="utf-8")
    _logged("open_review_case", started, "ok", dispute_id=dispute_id,
            reason=reason, review_case_id=case["review_case_id"])
    return {"review_case_id": case["review_case_id"], "created": True}


def send_customer_message(dispute_id: str, draft: str, approval: dict | None = None,
                          outbox: Path | None = None) -> dict:
    """Send the R11 draft to the customer, only with an analyst's approval (H6).

    `approval` is {"approver_role": ..., "approved_by": ...} from the analyst's
    action on the page, never from model text.
    """
    started = time.perf_counter()
    # TODO(Task 8): only send with an analyst's approval (H6); refuse and log otherwise.
    outbox = Path(outbox or STATE_DIR / "outbox.json")
    sent = json.loads(outbox.read_text(encoding="utf-8")) if outbox.exists() else []
    sent.append({"dispute_id": dispute_id, "message": draft,
                 "approved_by": (approval or {}).get("approved_by"),
                 "approver_role": (approval or {}).get("approver_role")})
    outbox.parent.mkdir(parents=True, exist_ok=True)
    outbox.write_text(json.dumps(sent, indent=2), encoding="utf-8")
    _logged("send_customer_message", started, "sent", dispute_id=dispute_id,
            approver_role=(approval or {}).get("approver_role"))
    return {"sent": True}


def rules_config() -> dict:
    return load_yaml("rules.yaml")
