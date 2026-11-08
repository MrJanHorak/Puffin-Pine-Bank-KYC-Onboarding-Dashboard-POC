"""Route low-confidence, missing or out-of-date fields to human review."""
import datetime


def review_items(doc_id, doc_type, record, schema, today=None):
    today = today or datetime.date.today().isoformat()
    spec = schema["document_types"][doc_type]
    items = []

    def check(fields, field_specs, prefix=""):
        for name, fs in field_specs.items():
            f = fields.get(name)
            label = prefix + name
            if f is None or str(f.get("value", "")).strip() == "":
                if fs.get("required"):
                    items.append({"doc_id": doc_id, "field": label, "reason": "missing or empty"})
            elif f["confidence"] < fs.get("review_threshold", schema.get("default_review_threshold", 0.85)):
                items.append({"doc_id": doc_id, "field": label,
                              "reason": f"confidence {f['confidence']} below {fs.get('review_threshold')}",
                              "value": f["value"], "confidence": f["confidence"]})

    check(record["fields"], spec["fields"])
    if "owner_fields" in spec:
        owners = record["fields"].get("owners", [])
        if not owners:
            items.append({"doc_id": doc_id, "field": "owners", "reason": "no beneficial owners found"})
        for i, owner in enumerate(owners, start=1):
            check(owner, spec["owner_fields"], prefix=f"owners[{i}].")
    expiry = record["fields"].get("expiry_date", {}).get("value")
    if expiry and expiry < today:
        items.append({"doc_id": doc_id, "field": "expiry_date", "reason": f"document expired {expiry}",
                      "value": expiry})
    return items


def pii_fields(schema, doc_type):
    """(PII fields at document level, PII fields inside each owner) for one document type."""
    spec = schema["document_types"][doc_type]
    top = {n for n, fs in spec.get("fields", {}).items() if fs.get("pii")}
    owner = {n for n, fs in spec.get("owner_fields", {}).items() if fs.get("pii")}
    return top, owner
