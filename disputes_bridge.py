"""Adapter between the POC server and the card dispute triage build in disputes/."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "disputes"))
from triage import POLICY_DIR, data_layer, load_yaml, pipeline  # noqa: E402

PAGE = ROOT / "disputes" / "web" / "index.html"

# Which policy section asks for each category's required evidence.
EVIDENCE_SECTION = {"NOT_RECEIVED": "DP-3.1", "NOT_AS_DESCRIBED": "DP-4.2",
                    "CANCELLED_RECURRING": "DP-5.2"}


def policies() -> list:
    """The SPECIMEN policy manual, one entry per DP-n file, split into sections."""
    manual = []
    for path in sorted(POLICY_DIR.glob("DP-*.md")):
        text = path.read_text(encoding="utf-8")
        head = re.search(r"^# (DP-\d+) (.+?)(?: \(SPECIMEN\))?$", text, re.M)
        manual.append({"id": head.group(1), "title": head.group(2),
                       "sections": [{"id": s, "text": b} for s, b in
                                    re.findall(r"Section (DP-\d\.\d)\. ([^\n]+)", text)]})
    return manual


def policy_checks(dispute: dict, result: dict) -> list:
    """Each policy requirement that applies to this dispute, and whether the case meets it.

    status: met, missing (blocks the analyst), flag (information only) or
    check (a judgement the policy leaves to the analyst).
    """
    found = result["reasons"] + result["flags"]
    details = lambda key: [c.split(":", 1)[1] for c in found if c.startswith(key + ":")]
    category = dispute.get("reason_category")
    txns = dispute.get("txn_ids") or []
    checks = []

    not_found = details("TXN_NOT_FOUND")
    checks.append({"requirement": "Every disputed charge is in our records", "section": "DP-1.1",
                   "status": "missing" if not_found else "met",
                   "detail": "Not found: " + ", ".join(not_found) if not_found
                   else f"{len(txns)} of {len(txns)} found"})

    late = details("OUT_OF_TIME")
    if details("DATE_UNREADABLE"):
        checks.append({"requirement": "Filed within 120 days of the charge", "section": "DP-1.2",
                       "status": "check", "detail": "A date can't be read, so this couldn't be checked"})
    else:
        checks.append({"requirement": "Filed within 120 days of the charge", "section": "DP-1.2",
                       "status": "flag" if late else "met",
                       "detail": "Over 120 days: " + ", ".join(late) + ". Information only, not a denial"
                       if late else "Within 120 days"})

    if "FRAUD_CLAIM" in found:
        checks.append({"requirement": "Customer says they didn't make it: fraud team with a review case",
                       "section": "DP-2.1", "status": "met" if result["fraud_review_case"] else "missing",
                       "detail": f"Routed to fraud, draft case {result['fraud_review_case']}"})
    if "CARD_REPORTED_LOST" in found:
        checks.append({"requirement": "Card reported lost or stolen before the charge: possible fraud",
                       "section": "DP-2.2", "status": "met" if result["queue"] == "FRAUD" else "missing",
                       "detail": "Routed to the fraud team"})

    needed = load_yaml("required_evidence.yaml").get(category) or []
    have = dispute.get("evidence") or []
    for item in needed:
        checks.append({"requirement": "Evidence: " + item.replace("_", " "),
                       "section": EVIDENCE_SECTION.get(category, ""),
                       "status": "met" if item in have else "missing",
                       "detail": "Provided by the customer" if item in have else "Not provided yet"})
    if category == "NOT_RECEIVED":
        checks.append({"requirement": "The expected delivery date has passed", "section": "DP-3.1",
                       "status": "check", "detail": "Policy leaves this to the analyst"})
    if category == "NOT_AS_DESCRIBED":
        checks.append({"requirement": "Customer describes what was ordered and what arrived",
                       "section": "DP-4.1", "status": "check", "detail": "Read the statement above"})
    if category == "DUPLICATE_CHARGE":
        checks.append({"requirement": "Two or more charges for one purchase", "section": "DP-5.1",
                       "status": "check", "detail": "Compare the charges in the table above"})
    if result["customer_message_draft"]:
        checks.append({"requirement": "Only an analyst contacts the customer", "section": "DP-6.1",
                       "status": "met", "detail": "Message drafted and held; nothing sent"})
    return checks


def listing() -> list:
    """Every dispute with its masked statement, for the page's picker."""
    return [{"dispute_id": key, "reason_category": row.get("reason_category"),
             "statement": data_layer.mask_card_numbers(row.get("customer_statement", ""))}
            for key, row in data_layer.disputes().items()]


def run(dispute_id, outage=False) -> dict:
    if not isinstance(dispute_id, str) or not re.fullmatch(r"DSP-\d{2}C?", dispute_id):
        raise ValueError("Use a dispute ID such as DSP-31.")
    faults = ("search_policy:unavailable",) if outage is True else ()
    try:
        result = pipeline.run_dispute(dispute_id, faults)
    except pipeline.DisputeNotFound as exc:
        raise ValueError(str(exc)) from exc
    except Exception as exc:
        # An unfinished task can let an error escape the pipeline. Show it on
        # the page instead of dropping the request.
        raise ValueError(f"The run stopped with an error: {type(exc).__name__}: {exc}") from exc
    # What came in, so the page can show the dispute next to the proposal.
    # The statement is masked on load; transactions carry only the last 4 digits.
    dispute = data_layer.load_dispute(dispute_id)
    ledger = data_layer.transactions_for(dispute["card_id"])
    claimed = dispute.get("claimed_amounts") or []
    result["input"] = {
        "received_date": dispute.get("received_date"),
        "reason_category": dispute.get("reason_category"),
        "statement": dispute.get("customer_statement"),
        "evidence": dispute.get("evidence") or [],
        "transactions": [dict(ledger.get(t) or {"txn_id": t, "missing": True},
                              claimed=claimed[i] if i < len(claimed) else None)
                         for i, t in enumerate(dispute.get("txn_ids") or [])],
        "outage_simulated": bool(faults),
    }
    sections = {s["id"]: s["text"] for doc in policies() for s in doc["sections"]}
    result["policy_text"] = sections.get(result["policy_section"])
    result["policy_checks"] = policy_checks(dispute, result)
    return result
