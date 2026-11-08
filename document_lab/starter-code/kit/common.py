"""Shared helpers: paths, document listing, and label text used by the field parser."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT.parent / "fixtures"   # the provided document pack sits beside starter-code/
DOCS = FIXTURES / "documents"
LABELS_DIR = FIXTURES / "labels"
OUT = ROOT / "out"

DOC_TYPES = ("certificate_of_incorporation", "ubo_declaration", "identity_document", "proof_of_address")

LABELS = {
    "company name": "company_name", "registration number": "registration_number",
    "date of incorporation": "date_of_incorporation", "jurisdiction": "jurisdiction",
    "registered address": "registered_address", "surname": "surname", "given names": "given_names",
    "document number": "document_number", "date of birth": "date_of_birth",
    "nationality": "nationality", "date of expiry": "expiry_date", "account holder": "name",
    "supply address": "address", "statement date": "issue_date",
}
OWNER_RE = re.compile(r"^Owner (\d+) (name|date of birth|nationality|ownership percent):\s*(.*)$", re.I)
OWNER_KEYS = {"name": "name", "date of birth": "date_of_birth", "nationality": "nationality",
              "ownership percent": "ownership_pct"}


def list_documents(case=None):
    """Source documents (PDF or PNG), optionally for one case."""
    files = sorted(p for p in DOCS.iterdir() if p.suffix.lower() in (".pdf", ".png"))
    return [p for p in files if case is None or f"_{case}_" in p.name]


def doc_type_of(path):
    return next(t for t in DOC_TYPES if t in Path(path).name)


def case_of(path):
    return Path(path).name.split("_")[1]


def parse_lines(lines, confidence_of=lambda line: 0.99):
    """Map 'Label: value' lines to schema fields. Owner lines become a list of owners."""
    fields, owners = {}, {}
    for line in lines:
        line = line.strip()
        m = OWNER_RE.match(line)
        if m:
            idx, key, value = int(m.group(1)), OWNER_KEYS[m.group(2).lower()], m.group(3).strip()
            owners.setdefault(idx, {})[key] = {"value": value, "confidence": confidence_of(line)}
            continue
        if ":" in line:
            label, value = line.split(":", 1)
            key = LABELS.get(label.strip().lower())
            if key:
                fields[key] = {"value": value.strip(), "confidence": confidence_of(line)}
    if owners:
        fields["owners"] = [owners[i] for i in sorted(owners)]
    return fields
