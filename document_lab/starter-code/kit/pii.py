"""PII controls applied at each connection point of the pipeline.

Actions for PII fields:  pass | mask | tokenise | drop
Free-text scanning (for logs): offline regex detector, or Azure AI Language PII
detection when AZURE_LANGUAGE_ENDPOINT and AZURE_LANGUAGE_KEY are set
(pip install azure-ai-textanalytics).
"""
import copy
import hashlib
import hmac
import os
import re

import yaml

from kit.common import ROOT

ACTIONS = {"pass", "mask", "tokenise", "drop"}
DOC_ACTIONS = {"pass", "block"}
DOC_NUMBER_RE = re.compile(r"\b[A-Z]{2}\d{7}\b")
DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


class PolicyError(Exception):
    """Raised when a connection has no decision: the pipeline fails closed."""


def load_policy(path=ROOT / "config" / "pii_policy.yaml"):
    policy = yaml.safe_load(open(path))["connections"]
    problems = []
    for name, rule in policy.items():
        allowed = DOC_ACTIONS if name == "extraction_service" else ACTIONS
        decisions = [rule.get("default")] + list((rule.get("fields") or {}).values())
        for d in decisions:
            if d not in allowed:
                problems.append(f"{name}: '{d}' is not a decision ({' | '.join(sorted(allowed))})")
        if not str(rule.get("rationale", "")).strip():
            problems.append(f"{name}: rationale is empty")
    if problems:
        raise PolicyError("PII policy incomplete, pipeline will not run:\n  - " + "\n  - ".join(problems))
    return policy


def tokenise(value):
    key = (os.environ.get("TOKEN_KEY") or "training-only-key").encode()
    return "tok_" + hmac.new(key, str(value).encode(), hashlib.sha256).hexdigest()[:12]


def _apply(value, action, field):
    if action == "pass":
        return value
    if action == "mask":
        return f"[REDACTED:{field}]"
    if action == "tokenise":
        return tokenise(value)
    return None  # drop


def apply_to_record(record, rule, pii):
    """Return a copy of an extracted record with the connection's PII rule applied.

    pii is (document-level PII field names, owner-level PII field names)."""
    pii_top, pii_owner = pii
    out = copy.deepcopy(record)
    overrides = rule.get("fields") or {}

    def treat(fields, pii_fields):
        for name in list(fields):
            if name in pii_fields:
                action = overrides.get(name, rule["default"])
                new = _apply(fields[name]["value"], action, name)
                if new is None:
                    del fields[name]
                else:
                    fields[name]["value"] = new

    treat(out["fields"], pii_top)
    for owner in out["fields"].get("owners", []):
        treat(owner, pii_owner)
    return out


def scrub_text(text, known_values=(), action="mask"):
    """Remove PII from free text (log lines). Uses Azure AI Language if configured."""
    if action == "pass":
        return text
    if os.environ.get("AZURE_LANGUAGE_ENDPOINT"):
        from azure.ai.textanalytics import TextAnalyticsClient
        from azure.core.credentials import AzureKeyCredential
        client = TextAnalyticsClient(os.environ["AZURE_LANGUAGE_ENDPOINT"],
                                     AzureKeyCredential(os.environ["AZURE_LANGUAGE_KEY"]))
        result = client.recognize_pii_entities([text])[0]
        if not result.is_error:
            return result.redacted_text
    for value in sorted({v for v in known_values if v}, key=len, reverse=True):
        text = text.replace(value, "[REDACTED]" if action != "tokenise" else tokenise(value))
    text = DOC_NUMBER_RE.sub("[REDACTED]", text)
    return DATE_RE.sub("[REDACTED]", text)
