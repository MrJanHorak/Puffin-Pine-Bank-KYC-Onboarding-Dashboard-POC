"""Check that each connection's PII decision is actually enforced in the pipeline outputs.

For every PII value in the ground-truth labels, look for it in each connection's output.
A raw value found where the policy says mask, tokenise or drop is a VIOLATION.
python -m kit.leak_check
"""
import json

import yaml

from kit.case_api import permission_report
from kit.common import LABELS_DIR, OUT, ROOT
from kit.pii import load_policy
from kit.review import pii_fields

CONNECTIONS = {"case_management_api": "outbox", "trace_log": "trace.log", "review_queue": "review_queue.jsonl"}


def raw_pii(schema):
    """[(value, field)] for every PII value in the labels."""
    found = []
    for path in sorted(LABELS_DIR.glob("*.json")):
        label = json.loads(path.read_text())
        top, owner = pii_fields(schema, label["doc_type"])
        for k, v in label["fields"].items():
            if k in top and v:
                found.append((str(v), k))
        for o in label["fields"].get("owners", []):
            found += [(str(v), k) for k, v in o.items() if k in owner and v]
    return found


def main():
    schema = yaml.safe_load(open(ROOT / "schema" / "kyc_extraction_schema.yaml"))
    policy = load_policy()
    values = raw_pii(schema)
    violations = 0
    print("PII enforcement by connection:")
    for connection, target in CONNECTIONS.items():
        paths = list((OUT / target).glob("*.json")) if (OUT / target).is_dir() else [OUT / target]
        text = "".join(p.read_text() for p in paths if p.exists())
        rule = policy[connection]
        passed, bad = 0, []
        for value, field in values:
            if value in text:
                action = (rule.get("fields") or {}).get(field, rule["default"])
                if action == "pass":
                    passed += 1
                else:
                    bad.append(f"{field}={value} (policy: {action})")
        violations += len(bad)
        status = "OK " if not bad else "VIOLATION"
        print(f"  {status} {connection:<22} raw values allowed by policy: {passed:<3} violations: {len(bad)}"
              + (f"  e.g. {bad[:2]}" if bad else ""))
    extra = permission_report()
    print("Tool permissions beyond what the pipeline needs: " + (", ".join(extra) if extra else "none"))
    return 1 if violations or extra else 0


if __name__ == "__main__":
    raise SystemExit(main())
