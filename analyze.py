"""Turn the raw benchmark rows into the summary table used in the article."""

import argparse
import json
from statistics import mean

from agent.config import RESULTS_DIR

EFFORT_ORDER = ["low", "medium", "high", "xhigh", "max"]


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def summarize(rows: list[dict]) -> list[dict]:
    summary = []
    for effort in EFFORT_ORDER:
        group = [row for row in rows if row["effort"] == effort]
        if not group:
            continue
        summary.append(
            {
                "effort": effort,
                "runs": len(group),
                "fixed": sum(1 for row in group if row["fixed_root_cause"]),
                "tool_calls": mean(row["tool_calls"] for row in group),
                "repeated_calls": mean(row["repeated_tool_calls"] for row in group),
                "output_tokens": mean(row["output_tokens"] for row in group),
                "input_tokens": mean(row["total_input_tokens"] for row in group),
                "cache_read": mean(row["cache_read_input_tokens"] for row in group),
                "patch_lines": mean(row["patch_lines"] for row in group),
                "files_changed": mean(row["files_changed_count"] for row in group),
                "first_output": mean(row["seconds_to_first_output"] for row in group),
                "seconds": mean(row["elapsed_seconds"] for row in group),
                "cost": mean(row["cost_usd"] for row in group),
            }
        )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", default="benchmark.json")
    args = parser.parse_args()

    rows = load(RESULTS_DIR / args.file)
    summary = summarize(rows)

    header = (
        "| Effort | Suite passed | Tool calls | Output tokens | Time to first output | "
        "Total time | Cost per run |"
    )
    divider = "|---|---|---|---|---|---|---|"
    print(header)
    print(divider)
    for row in summary:
        print(
            f"| `{row['effort']}` | {row['fixed']}/{row['runs']} | {row['tool_calls']:.1f} | "
            f"{row['output_tokens']:,.0f} | {row['first_output']:.1f}s | "
            f"{row['seconds']:.0f}s | ${row['cost']:.4f} |"
        )

    print("\nSupporting detail")
    for row in summary:
        print(
            f"  {row['effort']:>6}: input {row['input_tokens']:,.0f} tok "
            f"(cache reads {row['cache_read']:,.0f}), patch {row['patch_lines']:.1f} lines, "
            f"files {row['files_changed']:.1f}, repeats {row['repeated_calls']:.1f}"
        )

    total = sum(row["cost_usd"] for row in rows)
    print(f"\nRuns: {len(rows)}   Total measured spend: ${total:.4f}")

    failures = [row for row in rows if not row["fixed_root_cause"]]
    if failures:
        print("\nRuns that did not fix the root cause:")
        for row in failures:
            print(
                f"  {row['effort']} run {row['attempt']}: stop={row['stop_reason']}, "
                f"tools={row['tool_calls']}, status={row['report_status']!r}, "
                f"tests_after={row['tests_after']!r}"
            )


if __name__ == "__main__":
    main()
