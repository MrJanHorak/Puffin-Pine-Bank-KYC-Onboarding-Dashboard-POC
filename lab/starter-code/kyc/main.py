"""Run one case end to end with one command (FLOOR-4).

    python -m kyc.main SPECIMEN-APP-0007

Writes logs/run.jsonl and out/case_<application_id>.json (the result the
analyst sees). The run_end line carries the status and reasons only, since
model text is never logged.
"""
import argparse
import json
import sys
from pathlib import Path

from kyc.log_config import setup_logging
from kyc.model_client import ModelUnavailable, ReplayMissing
from kyc.routing import run_case
from kyc.settings import setting


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run one KYC case.")
    parser.add_argument("application_id")
    parser.add_argument("--mode", choices=["replay", "live"])
    parser.add_argument("--log-dir", default="logs")
    args = parser.parse_args(argv)
    setup_logging(args.log_dir)
    try:
        result = run_case(args.application_id, setting("KYC_MODE", args.mode))
    except ReplayMissing:
        return 1
    except ModelUnavailable as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if result is None:
        return 1
    result.pop("trace")
    out = Path("out")
    out.mkdir(exist_ok=True)
    (out / f"case_{result['application_id']}.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
