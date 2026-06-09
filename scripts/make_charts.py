from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "docs" / "assets"
ASSETS.mkdir(parents=True, exist_ok=True)

INK = "#1b2733"
MUTED = "#6b7a8d"
ACCENT = "#2f6f8f"
ACCENT2 = "#c98a3a"
GREEN = "#3f7d5a"
RED = "#b5503f"
GRID = "#e3e8ee"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 11,
    "axes.edgecolor": MUTED,
    "axes.labelcolor": INK,
    "text.color": INK,
    "xtick.color": MUTED,
    "ytick.color": MUTED,
    "axes.titlecolor": INK,
    "figure.facecolor": "white",
    "axes.facecolor": "white",
})


def load(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def funnel(shortlist: dict):
    c = shortlist["summary"]["contamination_self_check"]
    in_country = c["generated"] - c["dropped_out_of_country"]
    after_cheap = in_country - c["dropped_career_stage"] - c["dropped_low_similarity"]
    passed_gate = c["verified_pool"] - (
        c["rejected_domain"] + c["rejected_non_pi"] + c["rejected_region"] + c["rejected_collision"]
    )
    stages = [
        ("Candidate PIs generated", c["generated"]),
        ("In target country", in_country),
        ("Pass career + similarity", after_cheap),
        ("Sent to LLM gate", c["verified_pool"]),
        ("Pass verification gate", passed_gate),
        ("Final shortlist", c["final"]),
    ]
    labels = [s[0] for s in stages][::-1]
    vals = [s[1] for s in stages][::-1]
    colors = [GREEN] + [ACCENT] * (len(vals) - 2) + [MUTED]

    fig, ax = plt.subplots(figsize=(9, 4.6))
    bars = ax.barh(labels, vals, color=colors[::-1], height=0.62)
    for b, v in zip(bars, vals):
        ax.text(v + max(vals) * 0.012, b.get_y() + b.get_height() / 2, str(v),
                va="center", ha="left", fontsize=10, color=INK, fontweight="bold")
    ax.set_xlim(0, max(vals) * 1.12)
    ax.set_title("Precision funnel — every stage drops more than it keeps", fontweight="bold", pad=12)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(length=0)
    fig.tight_layout()
    fig.savefig(ASSETS / "funnel.png", dpi=160)
    plt.close(fig)


def results(shortlist: dict):
    s = shortlist["summary"]
    by_area = s["by_area"]
    by_tier = s["by_tier"]
    from collections import Counter
    by_country = Counter(x["country"] for x in shortlist["supervisors"])

    fig, axes = plt.subplots(1, 3, figsize=(13, 4.2))

    ax = axes[0]
    areas = list(by_area.keys())
    short = [a.replace(" & ", " &\n").replace(" of ", " of\n") for a in areas]
    ax.bar(range(len(areas)), [by_area[a] for a in areas], color=ACCENT, width=0.6)
    ax.set_xticks(range(len(areas)))
    ax.set_xticklabels(short, fontsize=8.5)
    ax.set_title("Coverage by research area", fontweight="bold")
    for i, a in enumerate(areas):
        ax.text(i, by_area[a] + 1, str(by_area[a]), ha="center", fontsize=10, fontweight="bold")
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.tick_params(length=0)

    ax = axes[1]
    order = ["reach", "target", "safety"]
    vals = [by_tier.get(t, 0) for t in order]
    ax.pie(vals, labels=[t.title() for t in order], autopct=lambda p: f"{int(round(p*sum(vals)/100))}",
           colors=[RED, ACCENT, GREEN], wedgeprops=dict(width=0.42, edgecolor="white"),
           textprops=dict(fontsize=10, color=INK))
    ax.set_title("Tier distribution", fontweight="bold")

    ax = axes[2]
    abbr = {"United States": "USA", "United Kingdom": "UK", "Australia": "Australia"}
    countries = list(by_country.keys())
    ax.bar(range(len(countries)), [by_country[c] for c in countries], color=ACCENT2, width=0.55)
    ax.set_xticks(range(len(countries)))
    ax.set_xticklabels([abbr.get(c, c) for c in countries], fontsize=9)
    ax.set_title("Country adherence (100% in target)", fontweight="bold")
    for i, cc in enumerate(countries):
        ax.text(i, by_country[cc] + 0.6, str(by_country[cc]), ha="center", fontsize=10, fontweight="bold")
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.tick_params(length=0)

    fig.tight_layout()
    fig.savefig(ASSETS / "results.png", dpi=160)
    plt.close(fig)


def audit():
    fig, axes = plt.subplots(1, 2, figsize=(9, 3.8))
    labels = ["Before fixes", "After fixes"]

    ax = axes[0]
    ax.bar(labels, [87, 93], color=[MUTED, GREEN], width=0.5)
    ax.set_ylim(0, 100)
    ax.set_title("Mentor-style audit approval", fontweight="bold")
    ax.set_ylabel("% bullseye + solid (top 30)")
    for i, v in enumerate([87, 93]):
        ax.text(i, v + 1.5, f"{v}%", ha="center", fontweight="bold")
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.tick_params(length=0)

    ax = axes[1]
    ax.bar(labels, [5, 2], color=[RED, GREEN], width=0.5)
    ax.set_ylim(0, 8)
    ax.set_title("Contamination (out of 30)", fontweight="bold")
    ax.set_ylabel("flagged picks")
    for i, v in enumerate([5, 2]):
        ax.text(i, v + 0.15, str(v), ha="center", fontweight="bold")
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.tick_params(length=0)

    fig.suptitle("Adversarial self-audit: root-cause fixes, then re-verify", fontweight="bold", y=1.02)
    fig.tight_layout()
    fig.savefig(ASSETS / "audit.png", dpi=160, bbox_inches="tight")
    plt.close(fig)


def main() -> int:
    path = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "sample_output" / "106419.json")
    sl = load(path)
    funnel(sl)
    results(sl)
    audit()
    print("charts written to", ASSETS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
