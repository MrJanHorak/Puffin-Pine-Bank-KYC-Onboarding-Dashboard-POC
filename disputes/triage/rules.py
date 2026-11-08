"""Rules R1 to R6, in code (sample PRD, section 5). No model, no network.

Each check returns (reasons, flags). Reasons can block or route a dispute;
flags are for the analyst to read and never block work.
"""
from datetime import date, datetime, timedelta


def parse_date(text) -> date | None:
    """A real calendar date in YYYY-MM-DD form, else None."""
    try:
        return datetime.strptime(str(text), "%Y-%m-%d").date() if text else None
    except ValueError:
        return None


def parse_datetime(text) -> datetime | None:
    """A real date and time in YYYY-MM-DDTHH:MM form, else None."""
    try:
        return datetime.strptime(str(text), "%Y-%m-%dT%H:%M") if text else None
    except ValueError:
        return None


def check_ledger(dispute: dict, ledger: dict, config: dict) -> tuple[list, list]:
    """R1: every disputed transaction is in the ledger, at the claimed amount (H4)."""
    # TODO(Task 6): R1. For each disputed txn_id: not in the ledger -> reason
    # TXN_NOT_FOUND:<txn_id>; claimed amount differs by more than
    # config["amount_tolerance"] -> flag AMOUNT_MISMATCH:<txn_id>.
    return [], []


def check_time_limit(dispute: dict, ledger: dict, config: dict) -> tuple[list, list]:
    """R2: flag a transaction disputed more than the limit after it posted.

    Skipped for a transaction R1 couldn't find, or an unreadable received_date (R3).
    """
    received = parse_date(dispute.get("received_date"))
    if received is None:
        return [], []
    flags = []
    for txn_id in dispute["txn_ids"]:
        posted = parse_datetime(ledger.get(txn_id, {}).get("posted_at"))
        if posted and (received - posted.date()).days > config["time_limit_days"]:
            flags.append(f"OUT_OF_TIME:{txn_id}")
    return [], flags


def check_completeness(dispute: dict, ledger: dict, config: dict,
                       required_evidence: dict) -> tuple[list, list]:
    """R3: required fields, the category's evidence and valid dates (H7)."""
    reasons = []
    fields = config["required_fields"]["system"] + config["required_fields"]["customer"]
    for field in fields:
        if dispute.get(field) in (None, "", []):
            reasons.append(f"MISSING_FIELD:{field}")
    for item in required_evidence.get(dispute.get("reason_category"), []):
        if item not in dispute.get("evidence", []):
            reasons.append(f"MISSING_EVIDENCE:{item}")
    if dispute.get("received_date") and parse_date(dispute["received_date"]) is None:
        reasons.append("DATE_UNREADABLE:received_date")
    for txn_id in dispute.get("txn_ids", []):
        posted = ledger.get(txn_id, {}).get("posted_at")
        if posted and parse_datetime(posted) is None:
            reasons.append(f"DATE_UNREADABLE:posted_at:{txn_id}")
    return reasons, []


def reported_before(card: dict | None, posted_at: str) -> bool:
    """R4: the card was reported lost or stolen at or before this charge (E3)."""
    # TODO(Task 6): True only when the card is LOST or STOLEN and reported_at
    # is at or before posted_at. Use parse_datetime for both.
    return False


def check_fraud(dispute: dict, ledger: dict, card: dict | None,
                config: dict) -> tuple[list, list]:
    """R4: fraud claim, lost or stolen card, or a cluster across merchants (H2)."""
    reasons = []
    if dispute.get("reason_category") == "UNAUTHORISED":
        reasons.append("FRAUD_CLAIM")
    found = [ledger[t] for t in dispute["txn_ids"] if t in ledger]
    if any(reported_before(card, row["posted_at"]) for row in found):
        reasons.append("CARD_REPORTED_LOST")
    times = sorted((parse_datetime(r["posted_at"]), r["merchant_id"]) for r in found
                   if parse_datetime(r["posted_at"]))
    window = timedelta(hours=config["cluster_window_hours"])
    for start, _ in times:
        merchants = {m for t, m in times if start <= t <= start + window}
        if len(merchants) >= config["cluster_min_merchants"]:
            reasons.append("CLUSTER_24H")
            break
    return reasons, []


def disputed_total(dispute: dict, ledger: dict, config: dict) -> float:
    """R5 and E2: the amount that decides senior review."""
    total = 0.0
    for txn_id, claimed in zip(dispute["txn_ids"], dispute["claimed_amounts"]):
        claimed = float(claimed)
        row = ledger.get(txn_id)
        if row is None:
            total += claimed
        elif abs(float(row["amount"]) - claimed) <= config["amount_tolerance"] + 1e-9:
            total += float(row["amount"])
        else:
            total += max(float(row["amount"]), claimed)
    return round(total, 2)


def check_amount(dispute: dict, ledger: dict, config: dict) -> tuple[list, list]:
    """R5: over the line -> HIGH_VALUE (H3). Per dispute, a training assumption."""
    if disputed_total(dispute, ledger, config) > config["senior_review_over"]:
        return ["HIGH_VALUE"], []
    return [], []


def check_duplicates(dispute: dict, open_txns: dict) -> tuple[list, list]:
    """R6: a transaction already in another OPEN dispute."""
    flags = [f"DUPLICATE_DISPUTE:{open_txns[t]}" for t in dispute["txn_ids"] if t in open_txns]
    return [], flags
