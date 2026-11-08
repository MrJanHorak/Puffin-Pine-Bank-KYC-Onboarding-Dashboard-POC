"""Approval gates (Day 8): deterministic checks that hold an action for a
person.

check_action(action, application_id, context) returns a GateDecision. The
facts in `context` come from the calling code, never from model text. An
action config/gates.yaml does not list is denied (default deny).

  GATE-01  never-class and unlisted actions (H1, H6, H8)
  GATE-02  close_review_case needs a listed human approver
  GATE-03  publish_case_result while a party is unscreened (H4)
  GATE-04  publish_case_result while a review reason has no case (H2, H3)
  GATE-07  publish_case_result with a model summary on a pending status (H7)
"""
import logging
from dataclasses import dataclass

import yaml

from kyc import CONFIG_DIR
from kyc.log_config import log_event
from kyc.rules import reason_status

logger = logging.getLogger("kyc.gate")

PENDING_STATUSES = ("MISSING_DATA", "SCREENING_UNAVAILABLE")


@dataclass(frozen=True)
class GateDecision:
    allowed: bool
    gate_id: str | None
    reason_code: str


def load_gates() -> dict:
    """config/gates.yaml, read on every check so an approved change applies."""
    text = (CONFIG_DIR / "gates.yaml").read_text(encoding="utf-8")
    return yaml.safe_load(text)


def blocks(gate: dict, action_class: str | None, context: dict) -> bool:
    """True when this gate holds the action, given the facts in context."""
    gate_id = gate["gate_id"]
    if gate_id == "GATE-01":
        return action_class in (None, "never")
    if gate_id == "GATE-02":
        # Programs act as "agent" or "system", never a listed approver role.
        return context.get("actor_role") not in gate["approver_roles"]
    if gate_id == "GATE-03":
        screened = set(context.get("screened_party_ids", []))
        return "party_ids" not in context or any(
            party_id not in screened for party_id in context["party_ids"])
    if gate_id == "GATE-04":
        opened = set(context.get("review_case_reasons", []))
        return any(reason_status(reason) == "COMPLIANCE_REVIEW"
                   and reason not in opened
                   for reason in context.get("reasons", []))
    if gate_id == "GATE-07":
        return (context.get("status") in PENDING_STATUSES
                and context.get("summary_source") == "model")
    return True  # a gate with no check here fails closed


def covers(gate: dict, action: str, action_class: str | None) -> bool:
    """True when the gate applies to this action."""
    if gate["gate_id"] == "GATE-01":
        return action_class in (None, "never")
    if gate["gate_id"] == "GATE-02":
        return action_class == "write_with_approval"
    return action == "publish_case_result"


def check_action(action: str, application_id: str,
                 context: dict | None = None) -> GateDecision:
    """Check every gate that covers the action, in config order.

    One gate_decision line per gate checked; the first gate that blocks
    stops the check.
    """
    config = load_gates()
    context = context or {}
    action_class = config["actions"].get(action)
    for gate in config["gates"]:
        if not covers(gate, action, action_class):
            continue
        held = blocks(gate, action_class, context)
        log_event(logger, "gate_decision", action=action,
                  gate_id=gate["gate_id"], allowed=not held,
                  reason_code=gate["reason_code"] if held else "ALLOWED",
                  application_id=application_id)
        if held:
            return GateDecision(False, gate["gate_id"], gate["reason_code"])
    return GateDecision(True, None, "ALLOWED")
