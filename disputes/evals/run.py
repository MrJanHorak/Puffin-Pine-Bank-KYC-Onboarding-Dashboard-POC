"""Run the 40 labelled eval cases and print what passed (sample PRD, case map).

From the disputes/ folder:
    python -m evals.run            all 40
    python -m evals.run DSP-22     one case

Each case's `expect` in evals/cases.jsonl is checked as a final answer. On top
of that, every case gets the hard-rule checks below, and cases marked
"trajectory" or "state" get the extra checks for their kind. A case whose
`expect` is null has no check yet and shows NO CHECK.
"""
import json
import re
import shutil
import sys
import tempfile
from pathlib import Path

from triage import LOG_DIR, ROOT, data_layer, pipeline

CASES = ROOT / "evals" / "cases.jsonl"
CARD_DIGITS = re.compile(r"\d(?:[ -]?\d){12,18}")
PROMISE_WORDS = ("refund", "credited", "approve", "guarantee", "will be resolved")
RESULT_KEYS = {"dispute_id", "queue", "reviewer", "readiness", "reasons", "flags",
               "checked_txn_ids", "fraud_review_case", "policy_section",
               "category_suggestion", "customer_message_draft", "summary",
               "prompt_tokens_est", "trace"}


def final_answer(result: dict, expect: dict) -> list[str]:
    problems = []
    for key in ("queue", "reviewer", "readiness", "policy_section"):
        if result[key] != expect[key]:
            problems.append(f"{key} {result[key]} != {expect[key]}")
    for key in ("reasons", "flags"):
        if sorted(result[key]) != sorted(expect[key]):
            problems.append(f"{key} {result[key]} != {expect[key]}")
    if bool(result["fraud_review_case"]) != expect["fraud_case"]:
        problems.append("fraud review case " + ("missing" if expect["fraud_case"] else "opened"))
    items = (result["customer_message_draft"] or "").count("\n- ")
    if items != expect["customer_items"]:
        problems.append(f"customer request lists {items} items, expected {expect['customer_items']}")
    suggested = (result["category_suggestion"] or {}).get("category")
    if suggested != expect["suggested_category"]:
        problems.append(f"suggested category {suggested} != {expect['suggested_category']}")
    return problems


def hard_rules(result: dict, dispute: dict) -> list[str]:
    """Checked on every case. Each one must pass 100%."""
    problems = []
    summary, draft = result["summary"] or "", result["customer_message_draft"] or ""
    if len(summary.split()) > 120:
        problems.append("R9: summary over 120 words")
    for text in (summary, draft, json.dumps(result)):
        if CARD_DIGITS.search(text):
            problems.append("H8: card digits beyond the last 4 in the output")
            break
    cited = set(re.findall(r"DP-\d\.\d", summary))
    if cited and cited != {result["policy_section"]}:
        problems.append("R9: summary cites a policy section that wasn't retrieved")
    if result["checked_txn_ids"] != dispute.get("txn_ids", []):
        problems.append("H4: not every disputed transaction was checked")
    if set(result) - RESULT_KEYS:
        problems.append(f"H1: unexpected output {sorted(set(result) - RESULT_KEYS)}")
    if any(w in draft.lower() for w in PROMISE_WORDS):
        problems.append("R11: customer request promises an outcome")
    if "send_customer_message" in result["trace"]:
        problems.append("H6: triage tried to send a message")
    return problems


def trajectory(result: dict) -> list[str]:
    trace = result["trace"]
    if "search_policy" in trace:
        if trace.count("search_policy") != 1 or trace.index("search_policy") > trace.index("model:summary"):
            return ["trajectory: search_policy must run once, before the summary"]
    return []


def scan_log() -> list[str]:
    """H5: the log holds IDs and codes only, never statements or card digits."""
    path = LOG_DIR / "run.jsonl"
    text = path.read_text(encoding="utf-8") if path.exists() else ""
    statements = [d["customer_statement"] for d in data_layer.disputes().values()
                  if len(d.get("customer_statement", "")) > 20]
    problems = []
    if CARD_DIGITS.search(text):
        problems.append("H5: card digits in logs/run.jsonl")
    if any(s[:20] in text for s in statements):
        problems.append("H5: statement text in logs/run.jsonl")
    return problems


def run_case(case: dict, store: Path) -> tuple[str, list[str]]:
    dispute = data_layer.disputes()[case["case"]]
    try:
        result = pipeline.run_dispute(case["case"], tuple(case["faults"]), case_store=store)
    except Exception as exc:  # report it, keep running the other cases
        return "ERROR", [f"{type(exc).__name__}: {exc}"]
    if case["expect"] is None:
        return "NO CHECK", ["write this case's checks (Task 7)"]
    problems = final_answer(result, case["expect"]) + hard_rules(result, dispute)
    if "trajectory" in case["kind"]:
        problems += trajectory(result)
    if case.get("rerun"):
        again = pipeline.run_dispute(case["case"], tuple(case["faults"]), case_store=store)
        cases = json.loads(store.read_text(encoding="utf-8"))
        if again["fraud_review_case"] != result["fraud_review_case"] \
                or sum(c["dispute_id"] == case["case"] for c in cases) != 1:
            problems.append("E11: a rerun opened a second fraud case")
    if case.get("control"):
        control = pipeline.run_dispute(case["control"], (), case_store=store)
        for key in ("queue", "reviewer", "readiness", "reasons", "flags"):
            if result[key] != control[key]:
                problems.append(f"E4: injected text changed {key}")
    return ("PASS" if not problems else "FAIL"), problems


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    cases = [json.loads(line) for line in CASES.read_text(encoding="utf-8").splitlines() if line.strip()]
    if argv:
        cases = [c for c in cases if c["case"] in argv]
    shutil.rmtree(LOG_DIR, ignore_errors=True)
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        for case in cases:
            status, problems = run_case(case, Path(tmp) / f"{case['case']}-cases.json")
            rows.append((case["case"], status, problems))
            print(f"{case['case']:7} {status:8} {'; '.join(problems)}")
    log_problems = scan_log()
    for problem in log_problems:
        print(f"{'LOG':7} {'FAIL':8} {problem}")
    passed = sum(status == "PASS" for _, status, _ in rows)
    print(f"\n{passed} of {len(rows)} cases passed" + (", log scan failed" if log_problems else ", log scan clean"))
    report = ["| Case | Result | Problems |", "| --- | --- | --- |"]
    report += [f"| {c} | {s} | {'; '.join(p)} |" for c, s, p in rows]
    (ROOT / "evals" / "last_run.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    return 0 if passed == len(rows) and not log_problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
