"""Scan a run log for personal data (hard rule H5).

    python scripts/scan_log.py logs/run.jsonl

Reports card-number-like digits and any customer statement text found in the
log. findings=0 means the log holds IDs and codes only.
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from triage import data_layer  # noqa: E402

CARD_DIGITS = re.compile(r"\d(?:[ -]?\d){12,18}")


def main(path: str) -> int:
    findings = 0
    statements = [d["customer_statement"] for d in data_layer.disputes().values()
                  if len(d.get("customer_statement", "")) > 20]
    for number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        if CARD_DIGITS.search(line):
            findings += 1
            print(f"line {number}: card-number-like digits")
        if any(s[:20] in line for s in statements):
            findings += 1
            print(f"line {number}: customer statement text")
    print(f"findings={findings}")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "logs/run.jsonl"))
