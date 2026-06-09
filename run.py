from __future__ import annotations

import argparse
import json
import sys
import time

from src.pipeline import run


def main() -> int:
    ap = argparse.ArgumentParser(description="PhD Shortlist Builder")
    ap.add_argument("--profile", required=True, help="path to student profile JSON")
    ap.add_argument("--out", default=None, help="output shortlist JSON path")
    ap.add_argument("--target", type=int, default=None, help="target shortlist size")
    ap.add_argument("--adjustments", default=None, help="feedback adjustments.json path")
    args = ap.parse_args()

    start = time.time()
    shortlist = run(args.profile, args.out, args.adjustments, args.target)
    elapsed = time.time() - start

    summary = shortlist.summary
    print(json.dumps(summary, indent=2))
    print(f"\nsupervisors: {len(shortlist.supervisors)}")
    print(f"wall_clock_seconds: {elapsed:.1f}")
    if args.out:
        print(f"written: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
