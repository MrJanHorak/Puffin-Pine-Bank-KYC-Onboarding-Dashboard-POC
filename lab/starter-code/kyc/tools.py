"""The build's tools: get_application, screen_watchlist, open_review_case.

Each call writes exactly one `tool_call` line with IDs and codes only. An
error comes back as {"type", "message", "retryable"}. --fault makes a tool
fail on purpose: `tool:unavailable` fails every call, `tool:timeout:once`
fails the first call only.
"""
import json
import logging
import time
from pathlib import Path

from kyc import data_layer, rules, screening
from kyc.log_config import log_event

logger = logging.getLogger("kyc.tools")

DEFAULT_CASE_STORE = Path("state/review_cases.json")


class FaultPlan:
    """Which tool calls fail on purpose in one run."""

    def __init__(self, faults=()):
        self.faults = [fault.split(":") for fault in faults if fault]

    def next_fault(self, tool: str) -> str | None:
        """The fault kind for this call of the tool, or None."""
        for fault in self.faults:
            if fault[0] == tool:
                if fault[-1] == "once":
                    self.faults.remove(fault)
                return fault[1]
        return None


def log_call(tool: str, started: float, outcome: str, **fields) -> None:
    """The one tool_call line; WARNING when the call did not succeed."""
    level = logging.INFO if outcome in ("ok", "duplicate_suppressed") \
        else logging.WARNING
    log_event(logger, "tool_call", level=level, tool=tool, **fields,
              outcome=outcome,
              latency_ms=int((time.perf_counter() - started) * 1000))


def unavailable(kind: str) -> dict:
    """The error a faulted call returns."""
    message = ("timed out after the request was received" if kind == "timeout"
               else "screening service unavailable; try again later")
    return {"type": "unavailable", "message": message, "retryable": True}


def get_application(application_id: str, fields: dict | None = None) -> dict:
    """What the agent may see of an application: IDs, roles and codes only,
    no names, dates of birth or document numbers. It reads the data layer,
    never the prompt (FLOOR-1).
    """
    started = time.perf_counter()
    pack = data_layer.get_application_pack(application_id, fields)
    if pack is None:
        log_call("get_application", started, "not_found",
                 application_id=application_id.strip().upper())
        return {"found": False,
                "message": "No application with this id; nothing was checked."}
    answer = {
        "found": True,
        "application_id": pack["application_id"],
        "application_date": pack["application_date"],
        "parties": [{"party_id": p["party_id"], "role": p.get("role"),
                     "party_type": p["party_type"]}
                    for p in rules.parties_to_screen(pack)],
        "missing_documents": [r.split(":", 1)[1] for r in
                              rules.missing_data_reasons(pack)
                              if r.startswith("MISSING_DOCUMENT")],
        "jurisdiction_risk": pack["jurisdiction_risk"],
    }
    log_call("get_application", started, "ok",
             application_id=pack["application_id"],
             party_count=len(answer["parties"]))
    return answer


def screen_watchlist(party: dict, application_id: str, faults: FaultPlan,
                     retry: bool = False) -> dict:
    """Screen one party against the watchlist; never decides a match."""
    started = time.perf_counter()
    kind = faults.next_fault("screen_watchlist")
    if kind:
        log_call("screen_watchlist", started, kind,
                 application_id=application_id, party_id=party["party_id"],
                 retry=retry)
        return unavailable(kind)
    answer = screening.match_party(party)
    log_call("screen_watchlist", started, "ok", application_id=application_id,
             party_id=party["party_id"], retry=retry)
    return answer


def open_review_case(application_id: str, reason_code: str, party_id: str = "",
                     store: Path = DEFAULT_CASE_STORE) -> dict:
    """Open a DRAFT review case for a compliance reviewer (hard rules H2, H3).

    A repeat request for the same application and reason returns the case
    already open, so a retry never adds a second case.
    """
    started = time.perf_counter()
    store = Path(store)
    cases = json.loads(store.read_text(encoding="utf-8")) \
        if store.exists() else []
    for case in cases:
        if (case["application_id"], case["reason_code"]) == \
                (application_id, reason_code):
            log_call("open_review_case", started, "duplicate_suppressed",
                     application_id=application_id, reason_code=reason_code,
                     review_case_id=case["review_case_id"])
            return {"review_case_id": case["review_case_id"],
                    "status": case["status"], "created": False}
    case = {"review_case_id": f"SPECIMEN-RC-{len(cases) + 5001:04d}",
            "application_id": application_id, "reason_code": reason_code,
            "party_id": party_id, "status": "DRAFT"}
    store.parent.mkdir(parents=True, exist_ok=True)
    store.write_text(json.dumps(cases + [case], indent=2), encoding="utf-8")
    log_call("open_review_case", started, "ok", application_id=application_id,
             reason_code=reason_code, review_case_id=case["review_case_id"])
    return {"review_case_id": case["review_case_id"], "status": "DRAFT",
            "created": True}

