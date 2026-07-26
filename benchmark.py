"""Run the same bug-fixing task at several effort levels and record what happened."""

import argparse
import json
from datetime import datetime, timezone

from anthropic import Anthropic
from dotenv import load_dotenv

from agent import repo
from agent.config import MAX_ITERATIONS, MAX_TOKENS, PROJECT_ROOT, RESULTS_DIR
from agent.costs import BudgetExceeded, BudgetGuard
from agent.loop import run_agent

load_dotenv()

EFFORT_LEVELS = ["low", "medium", "high", "xhigh", "max"]
ROOT_CAUSE_FILE = "billing/timeutils.py"
REPORTED_TEST = "test_trial_active_on_final_day"


def record_run(client, effort: str, attempt: int, bug_report: str, args) -> dict:
    """Reset the repository, run the agent once, and measure the outcome."""
    repo.reset()
    before = repo.test_status()

    print(f"\n=== {effort} effort, run {attempt} ===")
    print(f"  tests before : {before.summary}")

    result = run_agent(
        client,
        effort=effort,
        bug_report=bug_report,
        max_tokens=args.max_tokens,
        max_iterations=args.max_iterations,
        on_event=lambda kind, detail: print(f"  [{kind}] {detail}") if kind == "tool_start" else None,
    )

    after = repo.test_status()
    changed = repo.changed_files()
    report = result.report

    row = {
        "effort": effort,
        "attempt": attempt,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tests_before": before.summary,
        "tests_after": after.summary,
        "suite_passed": after.all_passed,
        "tests_failed_after": after.failed,
        "touched_root_cause": ROOT_CAUSE_FILE in changed,
        "fixed_root_cause": after.all_passed and ROOT_CAUSE_FILE in changed,
        "files_changed": changed,
        "files_changed_count": len(changed),
        "patch_lines": repo.diff_line_count(),
        "tool_calls": len(result.tool_calls),
        "tool_call_names": [call.name for call in result.tool_calls],
        "tool_errors": sum(1 for call in result.tool_calls if call.is_error),
        "repeated_tool_calls": result.repeated_tool_calls,
        "iterations": result.iterations,
        "stop_reason": result.stop_reason,
        "clean_stop": result.stop_reason == "end_turn"
        and not result.hit_iteration_cap
        and not result.hit_max_tokens,
        "hit_max_tokens": result.hit_max_tokens,
        "hit_iteration_cap": result.hit_iteration_cap,
        "refused": result.refused,
        "seconds_to_first_output": round(result.seconds_to_first_output or 0.0, 2),
        "elapsed_seconds": round(result.elapsed_seconds, 1),
        "report_status": report.status if report else None,
        "report_confidence": report.confidence if report else None,
        "report_root_cause": report.root_cause if report else None,
        "report_fix_summary": report.fix_summary if report else None,
        "report_error": result.report_error,
        "diff": repo.diff_text(),
        **result.usage.as_dict(),
    }

    print(
        f"  tests after  : {after.summary} | "
        f"root cause fixed: {row['fixed_root_cause']} | "
        f"tools: {row['tool_calls']} | "
        f"out: {result.usage.output_tokens:,} tok | "
        f"{result.elapsed_seconds:.0f}s | ${result.cost_usd:.4f}"
    )
    return row


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runs", type=int, default=2, help="Runs per effort level.")
    parser.add_argument("--efforts", default=",".join(EFFORT_LEVELS))
    parser.add_argument("--budget", type=float, default=12.0, help="Spending ceiling in dollars.")
    parser.add_argument("--max-tokens", type=int, default=MAX_TOKENS)
    parser.add_argument("--max-iterations", type=int, default=MAX_ITERATIONS)
    parser.add_argument("--out", default="benchmark.json")
    args = parser.parse_args()

    efforts = [level.strip() for level in args.efforts.split(",") if level.strip()]
    bug_report = (PROJECT_ROOT / "bug_report.md").read_text(encoding="utf-8")
    client = Anthropic()
    guard = BudgetGuard(args.budget)
    RESULTS_DIR.mkdir(exist_ok=True)
    output_path = RESULTS_DIR / args.out

    rows: list[dict] = []
    stopped_early = False

    # Attempt-major order, so a budget stop still leaves one run of every level.
    for attempt in range(1, args.runs + 1):
        for effort in efforts:
            try:
                guard.check()
            except BudgetExceeded as exc:
                print(f"\nStopping before {effort} run {attempt}: {exc}")
                stopped_early = True
                break

            row = record_run(client, effort, attempt, bug_report, args)
            guard.record(row["cost_usd"])
            row["cumulative_cost_usd"] = round(guard.spent_usd, 6)
            rows.append(row)

            output_path.write_text(json.dumps(rows, indent=2), encoding="utf-8")
            print(f"  spent so far : ${guard.spent_usd:.4f} of ${guard.ceiling_usd:.2f}")

        if stopped_early:
            break

    repo.reset()
    print(f"\nTotal spend: ${guard.spent_usd:.4f} across {len(rows)} runs")
    print(f"Saved {output_path}")


if __name__ == "__main__":
    main()
