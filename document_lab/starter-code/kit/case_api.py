"""A mock case-management API, exposed to the pipeline as tools with scoped permissions."""
import json

import yaml

from kit.common import OUT, ROOT

TOOLS = {
    "create_case": {"description": "Create a KYC case from extracted documents",
                    "input_schema": {"type": "object", "required": ["case_id", "documents", "review_required"],
                                     "properties": {"case_id": {"type": "string"},
                                                    "documents": {"type": "array"},
                                                    "review_required": {"type": "boolean"}}}},
    "get_case": {"description": "Read any existing case", "input_schema": {"type": "object"}},
    "update_case": {"description": "Overwrite fields on any existing case", "input_schema": {"type": "object"}},
    "delete_case": {"description": "Delete a case", "input_schema": {"type": "object"}},
}


class PermissionDenied(Exception):
    pass


class CaseManagementAPI:
    def __init__(self, permissions_path=ROOT / "config" / "tool_permissions.yaml"):
        self.allowed = set(yaml.safe_load(open(permissions_path))["allowed_tools"])
        self.outbox = OUT / "outbox"
        self.outbox.mkdir(parents=True, exist_ok=True)

    def call(self, tool, args):
        if tool not in TOOLS:
            raise PermissionDenied(f"Unknown tool: {tool}")
        if tool not in self.allowed:
            raise PermissionDenied(f"Tool not permitted for this pipeline: {tool}")
        return getattr(self, tool)(**args)

    def create_case(self, case_id, documents, review_required):
        path = self.outbox / f"{case_id}.json"
        path.write_text(json.dumps({"case_id": case_id, "review_required": review_required,
                                    "documents": documents}, indent=2))
        return {"status": "created", "case_id": case_id}

    def get_case(self, case_id):
        return json.loads((self.outbox / f"{case_id}.json").read_text())

    def update_case(self, case_id, **changes):
        case = self.get_case(case_id)
        case.update(changes)
        (self.outbox / f"{case_id}.json").write_text(json.dumps(case, indent=2))
        return {"status": "updated"}

    def delete_case(self, case_id):
        (self.outbox / f"{case_id}.json").unlink()
        return {"status": "deleted"}


def permission_report(permissions_path=ROOT / "config" / "tool_permissions.yaml", needed=("create_case",)):
    allowed = set(yaml.safe_load(open(permissions_path))["allowed_tools"])
    extra = sorted(allowed - set(needed))
    return extra
