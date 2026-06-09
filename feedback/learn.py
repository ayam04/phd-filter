from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

from .ingest import read_outcomes

POSITIVE = {"ADMIT", "INTERVIEW", "POSITIVE_REPLY"}
HARD_NEG = {"BOUNCE", "WRONG_PERSON", "NOT_RECRUITING"}
WEAK_NEG = {"REJECT", "NO_REPLY"}


def learn(outcomes: list[dict]) -> dict:
    suppress: set[str] = set()
    wrong_person: set[str] = set()
    pair: dict[str, dict[str, float]] = defaultdict(lambda: {"pos": 0.0, "neg": 0.0})

    for o in outcomes:
        oc = o["outcome"].upper()
        sid = o["supervisor_id"]
        key = f"{o['area']}::{o['institution']}"
        if oc in HARD_NEG:
            suppress.add(sid)
            if oc == "WRONG_PERSON":
                wrong_person.add(sid)
            pair[key]["neg"] += 1.0
        elif oc in POSITIVE:
            pair[key]["pos"] += 1.0
        elif oc in WEAK_NEG:
            pair[key]["neg"] += 0.5

    uplift: dict[str, float] = {}
    for key, c in pair.items():
        rate = (c["pos"] + 1.0) / (c["pos"] + c["neg"] + 2.0)
        u = round((rate - 0.5) * 0.6, 3)
        if abs(u) >= 0.02:
            uplift[key] = u

    return {
        "suppress": sorted(suppress),
        "wrong_person_ids": sorted(wrong_person),
        "area_institution_uplift": uplift,
        "counts": {
            "outcomes": len(outcomes),
            "suppressed": len(suppress),
            "scored_pairs": len(uplift),
        },
    }


def learn_from_csv(csv_path: str, out_path: str = "adjustments.json") -> dict:
    adj = learn(read_outcomes(csv_path))
    Path(out_path).write_text(json.dumps(adj, indent=2), encoding="utf-8")
    return adj


def main() -> int:
    ap = argparse.ArgumentParser(description="Learn ranking adjustments from an outcomes CSV")
    ap.add_argument("--outcomes", required=True)
    ap.add_argument("--out", default="adjustments.json")
    args = ap.parse_args()
    adj = learn_from_csv(args.outcomes, args.out)
    print(json.dumps(adj["counts"], indent=2))
    print("written:", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
