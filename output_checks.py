"""Conservative display checks, not a substitute for human review."""
import re

DECISION = re.compile(r'\b(?:approv\w*|reject\w*|declin\w*|accept(?:ed|ance)?|onboard(?:ed|ing)?\s+(?:is\s+)?(?:complete|approved)|clear(?:ed|ance)|eligible\s+to\s+open)\b', re.I)
POLICY_ID = re.compile(r'\bSPECIMEN-POL-\d+\b', re.I)

def check_summary(text, policy=None):
    if DECISION.search(text): return 'The generated text contained decision language; it was withheld for human review.'
    if policy and policy.get('outcome') == 'ok':
        allowed = {str(s['section_id']).upper() for s in policy['sections']}
        cited = {v.upper() for v in POLICY_ID.findall(text)}
        if not cited or not cited.issubset(allowed):
            return 'The generated text omitted source IDs or cited an unreturned policy; it was withheld for human review.'
    return None
