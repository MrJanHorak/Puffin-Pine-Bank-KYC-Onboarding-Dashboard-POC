"""The data layer: reads the system-of-record files in fixtures/data/ (FLOOR-1).

get_application_pack(application_id) returns one application's pack: the
company, its other parties, its documents and its jurisdiction risk. The pack
holds personal data, so it is used in code and never written to a log.
"""
import copy
import csv
from functools import lru_cache

from kyc import DATA_DIR

# An earlier application still in one of these states makes a duplicate.
OPEN_PORTAL_STATUSES = ("SUBMITTED", "IN_REVIEW")


def read_csv(name: str) -> list[dict]:
    """Every row of one data file, skipping the `# SPECIMEN` comment line."""
    with open(DATA_DIR / name, encoding="utf-8", newline="") as handle:
        lines = [line for line in handle if not line.startswith("#")]
    return list(csv.DictReader(lines))


@lru_cache(maxsize=1)
def tables() -> dict:
    """All data files, read once (the files are read only)."""
    parties, documents = {}, {}
    for row in read_csv("parties.csv"):
        parties.setdefault(row["application_id"], []).append(row)
    for row in read_csv("documents.csv"):
        documents.setdefault(row["application_id"], []).append(row)
    return {
        "applications": {r["application_id"]: r
                         for r in read_csv("applications.csv")},
        "parties": parties,
        "documents": documents,
        "tiers": {r["country_code"]: r["risk_tier"]
                  for r in read_csv("jurisdictions.csv")},
    }


def blank_to_none(row: dict) -> dict:
    """Blank cells become None."""
    return {key: (value or None) for key, value in row.items()}


def company_of(application_id: str) -> dict:
    """The applicant company's party row."""
    return next(row for row in tables()["parties"][application_id]
                if row["role"] == "APPLICANT_COMPANY")


def duplicate_of(application_id: str) -> str | None:
    """An earlier, still-open application from the same company, or None."""
    data = tables()
    this = data["applications"][application_id]
    registration = company_of(application_id)["registration_number"]
    for other_id, other in data["applications"].items():
        if (other_id != application_id
                and company_of(other_id)["registration_number"] == registration
                and other["application_date"] < this["application_date"]
                and other["portal_status"] in OPEN_PORTAL_STATUSES):
            return other_id
    return None


def get_application_pack(application_id: str,
                         fields: dict | None = None) -> dict | None:
    """One application's pack, or None for an ID that was never issued.

    fields: eval-case overrides by flat-record column name (apply_overrides).
    """
    application_id = application_id.strip().upper()
    data = tables()
    if application_id not in data["applications"]:
        return None
    tiers = data["tiers"]
    company = blank_to_none(company_of(application_id))
    company["risk_tier"] = tiers.get(company["country_code"])
    parties = []
    for row in data["parties"][application_id]:
        if row["role"] != "APPLICANT_COMPANY":
            party = blank_to_none(row)
            party["risk_tier"] = tiers.get(party["country_code"])
            parties.append(party)
    pack = {
        "application_id": application_id,
        "application_date":
            data["applications"][application_id]["application_date"],
        "company": company,
        "parties": parties,
        "documents": [blank_to_none(row)
                      for row in data["documents"].get(application_id, [])],
        "jurisdiction_risk": company["risk_tier"],
        "duplicate_of": duplicate_of(application_id),
    }
    return apply_overrides(pack, fields) if fields else pack


def apply_overrides(pack: dict, fields: dict) -> dict:
    """A copy of the pack with eval-case overrides applied.

    Only the four flat-record names the eval suites use are accepted, so a
    typo fails loudly instead of testing the stored value.
    """
    pack = copy.deepcopy(pack)
    director = next(p for p in pack["parties"]
                    if p["role"].startswith("DIRECTOR"))
    for name, value in fields.items():
        if name == "application_date":
            pack["application_date"] = value
        elif name == "incorporation_date":
            pack["company"]["incorporation_date"] = value
        elif name == "director_full_name":
            director["full_name"] = value
        elif name == "proof_of_address_date":
            for doc in pack["documents"]:
                if doc["doc_type"] == "PROOF_OF_ADDRESS":
                    doc["document_date"] = value
        else:
            raise ValueError(f"unknown field override: {name}")
    return pack
