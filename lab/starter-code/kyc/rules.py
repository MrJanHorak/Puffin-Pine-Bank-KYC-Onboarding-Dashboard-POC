"""Deterministic case rules, with thresholds in
config/rules.yaml.

check_application(pack, screenings) runs every rule and returns the status
and every reason. Each rule logs one `check_result` line: the rule's code,
pass or flag, and the application ID, nothing else. No status approves or
rejects an application: a person decides (hard rule H1).
"""
import logging
import re
from datetime import date

import yaml

from kyc import CONFIG_DIR
from kyc.log_config import log_event

logger = logging.getLogger("kyc.rules")

PEOPLE_ROLES = ("DIRECTOR", "BENEFICIAL_OWNER",
                "DIRECTOR_AND_BENEFICIAL_OWNER")
ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def load_config() -> dict:
    """config/rules.yaml, read on every call so an approved change applies."""
    text = (CONFIG_DIR / "rules.yaml").read_text(encoding="utf-8")
    return yaml.safe_load(text)


def reason_status(reason: str, config: dict | None = None) -> str:
    """The status one reason code sets, such as COMPLIANCE_REVIEW."""
    config = config or load_config()
    family = reason.split(":", 1)[0]
    return config["reasons"].get(reason) or config["reason_families"][family]


def status_for(reasons: list[str], config: dict | None = None) -> str:
    """The most protective status any reason sets; NO_FLAGS when none."""
    config = config or load_config()
    statuses = {reason_status(reason, config) for reason in reasons}
    for item in config["statuses"]:
        if item["code"] in statuses:
            return item["code"]
    return "NO_FLAGS"


def display_text(status: str) -> str:
    """The words the analyst sees for a status."""
    return next(item["display"] for item in load_config()["statuses"]
                if item["code"] == status)


def as_date(text: str | None) -> date | None:
    """A YYYY-MM-DD date, or None when blank or written another way."""
    if text and ISO_DATE.fullmatch(text):
        try:
            return date.fromisoformat(text)
        except ValueError:
            return None
    return None


def normalise_name(name: str) -> str:
    """Drop the SPECIMEN marker, then ignore case, spaces and punctuation."""
    text = name.strip()
    if text.upper().startswith("SPECIMEN "):
        text = text[len("SPECIMEN "):]
    return re.sub(r"[^a-z0-9]", "", text.lower())


def people(pack: dict) -> list[dict]:
    """The directors and beneficial owners."""
    return [p for p in pack["parties"] if p["role"] in PEOPLE_ROLES]


def parties_to_screen(pack: dict) -> list[dict]:
    """The company and every director and beneficial owner (hard rule H4)."""
    return [pack["company"]] + people(pack)


def document(pack: dict, doc_type: str, party_id: str | None = None):
    """The first document of one type (for one party when party_id is set)."""
    for doc in pack["documents"]:
        if doc["doc_type"] == doc_type and party_id in (None, doc["party_id"]):
            return doc
    return None


def date_reason(text: str | None, field: str) -> str | None:
    """MISSING_FIELD for a blank date, DATE_UNREADABLE for a non-ISO one."""
    if not text:
        return f"MISSING_FIELD:{field}"
    return None if as_date(text) else f"DATE_UNREADABLE:{field}"


def missing_data_reasons(pack: dict) -> list[str]:
    """Missing documents, blank fields and unreadable dates (hard rule H7)."""
    reasons = [date_reason(pack["application_date"], "application_date")]
    proof = document(pack, "PROOF_OF_ADDRESS")
    if proof is None:
        reasons.append("MISSING_DOCUMENT:PROOF_OF_ADDRESS")
    else:
        reasons.append(date_reason(proof["document_date"],
                                   "proof_of_address_date"))
    company = pack["company"]
    certificate = document(pack, "CERTIFICATE_OF_INCORPORATION",
                           company["party_id"])
    if certificate is None:
        reasons.append("MISSING_DOCUMENT:CERTIFICATE_OF_INCORPORATION")
    reasons.append(date_reason(company["incorporation_date"],
                               "incorporation_date"))
    for person in people(pack):
        reasons.append(date_reason(person["date_of_birth"], "date_of_birth"))
        if "OWNER" in person["role"] and person["ownership_pct"] is None:
            reasons.append("MISSING_FIELD:ownership_pct")
        passport = document(pack, "PASSPORT", person["party_id"])
        if passport is None:
            reasons.append("MISSING_DOCUMENT:PASSPORT")
        else:
            reasons.append(date_reason(passport["expiry_date"], "expiry_date"))
    return sorted({reason for reason in reasons if reason})


def owner_chains(pack: dict) -> list[tuple[float, int]]:
    """Each person's effective share of the company and the number of
    owning companies it passes through (50% of a 50% owner is 25%, 1 layer).
    A chain with a blank share on the way is left out.
    """
    by_id = {p["party_id"]: p for p in pack["parties"]}
    chains = []
    for person in people(pack):
        if person["ownership_pct"] is None:
            continue
        share, layers = float(person["ownership_pct"]), 0
        via = person["owned_via_party_id"]
        while via:
            owner = by_id.get(via)
            if owner is None or owner["ownership_pct"] is None:
                break
            share = share * float(owner["ownership_pct"]) / 100
            layers += 1
            via = owner["owned_via_party_id"]
        if not via:
            chains.append((share, layers))
    return chains


def document_flags(pack: dict, config: dict) -> dict:
    """The document rules (FLAGGED). None means a value it needs is blank."""
    applied = as_date(pack["application_date"])
    proof = document(pack, "PROOF_OF_ADDRESS")
    proof_date = as_date(proof["document_date"]) if proof else None
    incorporated = as_date(pack["company"]["incorporation_date"])
    passports = [(person, document(pack, "PASSPORT", person["party_id"]))
                 for person in people(pack)]
    passports = [(person, doc) for person, doc in passports if doc]
    expiries = [as_date(doc["expiry_date"]) for _, doc in passports]
    expiries = [day for day in expiries if day]
    flags = {"POA_STALE": None, "PASSPORT_EXPIRED": None,
             "NAME_MISMATCH": None, "INCORPORATED_AFTER_APPLICATION": None}
    if applied and proof_date:
        age = (applied - proof_date).days
        flags["POA_STALE"] = age > config["poa_max_age_days"]
    if applied and expiries:
        flags["PASSPORT_EXPIRED"] = any(day < applied for day in expiries)
    if passports:
        flags["NAME_MISMATCH"] = any(
            normalise_name(person["full_name"] or "")
            != normalise_name(doc["name_on_document"] or "")
            for person, doc in passports)
    if applied and incorporated:
        flags["INCORPORATED_AFTER_APPLICATION"] = incorporated > applied
    flags["DUPLICATE_APPLICATION"] = pack["duplicate_of"] is not None
    return flags


def risk_flags(pack: dict, screenings: dict, config: dict) -> dict:
    """Every rule's verdict: True flags, False passes, None cannot run.

    The dict keeps the rules in a fixed order, the order the
    check_result lines are logged in.
    """
    everyone = [pack["company"]] + pack["parties"]
    tiers = [pack["jurisdiction_risk"]] + [p["risk_tier"] for p in everyone]
    direct = [float(p["ownership_pct"]) for p in pack["parties"]
              if p["ownership_pct"] and not p["owned_via_party_id"]]
    chains = owner_chains(pack)
    owner_pct = config["beneficial_owner_threshold_pct"]
    scores = [c["score"] for answer in screenings.values()
              for c in answer.get("candidates", [])]
    screened = {party_id for party_id, answer in screenings.items()
                if answer.get("found")}
    flags = document_flags(pack, config)
    flags.update({
        "PEP_PARTY": any(p["declared_pep"] == "Y" for p in everyone),
        "HIGH_RISK_JURISDICTION": "HIGH" in tiers,
        "POSSIBLE_WATCHLIST_MATCH": any(
            score >= config["possible_match_threshold"] for score in scores),
        "OWNERSHIP_OVER_100": round(sum(direct), 6) > 100,
        # 1e-9 allows for rounding when shares are multiplied through owners.
        "NO_BENEFICIAL_OWNER_IDENTIFIED": not any(
            share >= owner_pct - 1e-9 for share, _ in chains),
        "COMPLEX_OWNERSHIP": any(layers >= 2 for _, layers in chains),
        "SCREENING_UNAVAILABLE": any(
            p["party_id"] not in screened for p in parties_to_screen(pack)),
    })
    return flags


def check_application(pack: dict, screenings: dict) -> tuple[str, list[str]]:
    """Run every rule; return (status, reasons), reasons sorted.

    screenings: party_id -> screen_watchlist answer, for each party screened.
    """
    config = load_config()
    application_id = pack["application_id"]
    reasons = missing_data_reasons(pack)
    for reason in reasons:
        log_event(logger, "check_result", rule=reason, result="flag",
                  application_id=application_id)
    for rule, flagged in risk_flags(pack, screenings, config).items():
        if flagged is None:
            continue
        log_event(logger, "check_result", rule=rule,
                  result="flag" if flagged else "pass",
                  application_id=application_id)
        if flagged:
            reasons.append(rule)
    reasons = sorted(set(reasons))
    return status_for(reasons, config), reasons
