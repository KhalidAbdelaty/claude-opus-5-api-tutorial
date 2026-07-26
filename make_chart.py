"""Render the effort comparison chart from the measured benchmark rows."""

import json
from statistics import mean

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from agent.config import RESULTS_DIR

EFFORT_ORDER = ["low", "medium", "high", "xhigh", "max"]

# DataCamp-style palette.
NAVY = "#05192D"
BLUE = "#185FA5"
GREEN = "#03EF62"
GREY = "#7A8A99"


def main() -> None:
    rows = json.loads((RESULTS_DIR / "benchmark.json").read_text(encoding="utf-8"))

    costs, passed, runs = [], [], []
    for effort in EFFORT_ORDER:
        group = [row for row in rows if row["effort"] == effort]
        costs.append(mean(row["cost_usd"] for row in group))
        passed.append(sum(1 for row in group if row["fixed_root_cause"]))
        runs.append(len(group))

    fig, ax_cost = plt.subplots(figsize=(9, 4.8))
    fig.patch.set_facecolor("white")

    bars = ax_cost.bar(EFFORT_ORDER, costs, color=BLUE, width=0.55, zorder=2)
    ax_cost.set_ylabel("Average cost per run (USD)", color=NAVY, fontsize=11)
    ax_cost.set_xlabel("Effort level", color=NAVY, fontsize=11)
    ax_cost.set_ylim(0, max(costs) * 1.45)
    ax_cost.tick_params(colors=NAVY)
    ax_cost.grid(axis="y", color="#E4E8EC", zorder=0)
    ax_cost.set_axisbelow(True)
    for spine in ("top", "right"):
        ax_cost.spines[spine].set_visible(False)

    for bar, cost in zip(bars, costs):
        ax_cost.annotate(
            f"${cost:.4f}",
            (bar.get_x() + bar.get_width() / 2, bar.get_height()),
            textcoords="offset points",
            xytext=(0, 5),
            ha="center",
            color=NAVY,
            fontsize=10,
        )

    ax_pass = ax_cost.twinx()
    rate = [p / r * 100 for p, r in zip(passed, runs)]
    ax_pass.plot(
        EFFORT_ORDER, rate, color=NAVY, marker="o", markersize=9,
        markerfacecolor=GREEN, markeredgecolor=NAVY, linewidth=2.5, zorder=3,
    )
    ax_pass.set_ylabel("Runs with the full suite passing (%)", color=NAVY, fontsize=11)
    ax_pass.set_ylim(0, 115)
    ax_pass.tick_params(colors=NAVY)
    for spine in ("top", "left"):
        ax_pass.spines[spine].set_visible(False)

    for effort, value in zip(EFFORT_ORDER, rate):
        ax_pass.annotate(
            f"{value:.0f}%",
            (effort, value),
            textcoords="offset points",
            xytext=(0, -20),
            ha="center",
            color=NAVY,
            fontsize=10,
        )

    ax_cost.set_title(
        "Claude Opus 5: cost climbs with effort, the outcome does not",
        color=NAVY, fontsize=13, pad=14, loc="left",
    )
    fig.text(
        0.01, 0.01,
        "Three runs per effort level on the same bug. Bars: mean cost. Line: share of runs where all six tests passed.",
        color=GREY, fontsize=8.5,
    )

    fig.tight_layout(rect=(0, 0.04, 1, 1))
    out = RESULTS_DIR / "claude-opus-5-api_benchmark-chart.png"
    fig.savefig(out, dpi=160, facecolor="white")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
