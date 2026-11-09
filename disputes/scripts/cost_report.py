"""Cost per dispute from the model_call lines in a run log (sample PRD, section 11).

    python scripts/cost_report.py logs/run.jsonl

Groups calls by correlation ID (one triage run), so a rerun counts as its own run.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path


def main(path: str) -> int:
    runs = defaultdict(lambda: {"dispute_id": None, "calls": 0, "in": 0, "out": 0, "usd": 0.0})
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row["event"] != "model_call":
            continue
        run = runs[row["correlation_id"]]
        run["dispute_id"] = row["dispute_id"]
        run["calls"] += 1
        run["in"] += row["tokens_in"]
        run["out"] += row["tokens_out"]
        run["usd"] += row["cost_usd"]
    print(f"{'dispute':8} {'calls':>5} {'tokens in':>9} {'tokens out':>10} {'USD':>9}")
    for run in runs.values():
        print(f"{run['dispute_id']:8} {run['calls']:>5} {run['in']:>9} {run['out']:>10} {run['usd']:>9.6f}")
    if runs:
        mean = sum(r["usd"] for r in runs.values()) / len(runs)
        print(f"\nmean cost per dispute: {mean:.6f} USD over {len(runs)} runs "
              "(placeholder prices; see config/price_card.yaml)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "logs/run.jsonl"))
