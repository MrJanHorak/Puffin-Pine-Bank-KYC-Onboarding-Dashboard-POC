"""Triage one dispute from the command line and print the result as JSON.

From the disputes/ folder:
    python -m triage.run DSP-31
    python -m triage.run DSP-34 --fault search_policy:unavailable
"""
import argparse
import json

from triage import pipeline


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("dispute_id")
    parser.add_argument("--fault", action="append", default=[],
                        help="search_policy:unavailable or search_policy:slow")
    args = parser.parse_args(argv)
    try:
        result = pipeline.run_dispute(args.dispute_id, tuple(args.fault))
    except pipeline.DisputeNotFound as exc:
        print(exc)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
