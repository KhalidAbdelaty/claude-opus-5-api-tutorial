"""Run the bug-fixing agent once at a chosen effort level."""

import argparse
from pathlib import Path

from anthropic import Anthropic
from dotenv import load_dotenv

from agent import repo
from agent.config import MAX_ITERATIONS, MAX_TOKENS, PROJECT_ROOT
from agent.loop import run_agent

load_dotenv()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--effort", default="low", choices=["low", "medium", "high", "xhigh", "max"])
    parser.add_argument("--max-tokens", type=int, default=MAX_TOKENS)
    parser.add_argument("--max-iterations", type=int, default=MAX_ITERATIONS)
    parser.add_argument("--no-reset", action="store_true")
    args = parser.parse_args()

    if not args.no_reset:
        repo.reset()

    before = repo.test_status()
    print(f"Tests before: {before.summary or before.exit_code}")

    bug_report = (PROJECT_ROOT / "bug_report.md").read_text(encoding="utf-8")
    client = Anthropic()

    def show(kind: str, detail: str) -> None:
        print(f"  [{kind}] {detail}")

    result = run_agent(
        client,
        effort=args.effort,
        bug_report=bug_report,
        max_tokens=args.max_tokens,
        max_iterations=args.max_iterations,
        on_event=show,
    )

    after = repo.test_status()

    print(f"\nStop reason      : {result.stop_reason}")
    print(f"Iterations       : {result.iterations}")
    print(f"Tool calls       : {len(result.tool_calls)}")
    print(f"Input tokens     : {result.usage.total_input_tokens:,}")
    print(f"Output tokens    : {result.usage.output_tokens:,}")
    print(f"Cache read       : {result.usage.cache_read_input_tokens:,}")
    print(f"Cache write      : {result.usage.cache_creation_input_tokens:,}")
    print(f"Cost             : ${result.cost_usd:.4f}")
    print(f"Elapsed          : {result.elapsed_seconds:.1f}s")
    print(f"Tests after      : {after.summary or after.exit_code}")
    print(f"Files changed    : {repo.changed_files()}")

    if result.report is not None:
        report = result.report
        print(f"\nStatus     : {report.status}")
        print(f"Confidence : {report.confidence}")
        print(f"Root cause : {report.root_cause}")
        print(f"Fix        : {report.fix_summary}")
    else:
        print(f"\nNo parsed report: {result.report_error}")
        if result.final_text:
            print(result.final_text[:800])


if __name__ == "__main__":
    main()
