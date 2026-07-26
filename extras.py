"""Small focused demos for the features that sit outside the main agent loop."""

import argparse
import json

import anthropic
from anthropic import Anthropic
from dotenv import load_dotenv

from agent import repo, tools as tool_module
from agent.config import MODEL, PROJECT_ROOT
from agent.costs import Usage
from agent.loop import run_agent
from agent.prompts import SYSTEM_PROMPT, build_task_prompt

load_dotenv()
client = Anthropic()


def bug_report() -> str:
    return (PROJECT_ROOT / "bug_report.md").read_text(encoding="utf-8")


def demo_disabled_thinking() -> None:
    """Thinking can only be switched off at effort high or below."""
    for effort in ["high", "xhigh"]:
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=512,
                thinking={"type": "disabled"},
                output_config={"effort": effort},
                messages=[{"role": "user", "content": "Reply with the word ready."}],
            )
            blocks = [block.type for block in response.content]
            print(f"effort={effort:<5} accepted, blocks={blocks}")
        except anthropic.APIStatusError as exc:
            print(f"effort={effort:<5} HTTP {exc.status_code}: {exc.message}")


def demo_caching() -> None:
    """Cache writes on the first request, cache reads on every one after it."""
    messages = [{"role": "user", "content": build_task_prompt(bug_report())}]

    for turn in (1, 2):
        response = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            tools=tool_module.TOOLS,
            output_config={"effort": "low"},
            cache_control={"type": "ephemeral"},
            messages=messages,
        )
        usage = response.usage
        print(
            f"turn {turn}: uncached_input={usage.input_tokens:<5} "
            f"cache_write={usage.cache_creation_input_tokens or 0:<6} "
            f"cache_read={usage.cache_read_input_tokens or 0:<6} "
            f"output={usage.output_tokens}"
        )
        messages.append({"role": "assistant", "content": response.content})
        if response.stop_reason == "tool_use":
            results = []
            for block in response.content:
                if block.type == "tool_use":
                    output, is_error = tool_module.execute(block.name, dict(block.input or {}))
                    results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": output,
                            "is_error": is_error,
                        }
                    )
            messages.append({"role": "user", "content": results})
        else:
            break

    repo.reset()


def demo_task_budget(total: int) -> None:
    """An advisory budget for the whole loop, separate from the per-request max_tokens."""
    usage = Usage()
    messages = [{"role": "user", "content": build_task_prompt(bug_report())}]
    repo.reset()
    tool_calls = 0

    for _ in range(10):
        with client.beta.messages.stream(
            model=MODEL,
            max_tokens=32_000,
            system=SYSTEM_PROMPT,
            tools=tool_module.TOOLS,
            output_config={
                "effort": "high",
                "task_budget": {"type": "tokens", "total": total},
            },
            cache_control={"type": "ephemeral"},
            messages=messages,
            betas=["task-budgets-2026-03-13"],
        ) as stream:
            response = stream.get_final_message()

        usage.add(response.usage)
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            break

        results = []
        for block in response.content:
            if block.type == "tool_use":
                tool_calls += 1
                output, is_error = tool_module.execute(block.name, dict(block.input or {}))
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": output,
                        "is_error": is_error,
                    }
                )
        messages.append({"role": "user", "content": results})

    after = repo.test_status()
    print(
        f"budget={total:<7} tool_calls={tool_calls:<3} "
        f"output={usage.output_tokens:<6} cost=${usage.cost_usd():.4f} "
        f"tests_after={after.summary!r}"
    )
    repo.reset()


def demo_tool_addition() -> None:
    """Withhold the patch tool until the diagnosis is done, without touching `tools`."""
    repo.reset()
    usage = Usage()

    # The full tool set is declared up front so the cached prefix never changes.
    # Tool changes ride inside a mid-conversation system message, and a system
    # message cannot be the first entry in `messages`.
    withhold_patch = {
        "role": "system",
        "content": [
            {
                "type": "tool_removal",
                "tool": {"type": "tool_reference", "name": "apply_patch"},
            }
        ],
    }
    offer_patch = {
        "role": "system",
        "content": [
            {
                "type": "tool_addition",
                "tool": {"type": "tool_reference", "name": "apply_patch"},
            }
        ],
    }

    messages = [
        {
            "role": "user",
            "content": build_task_prompt(bug_report())
            + "\n\nDiagnose the root cause first. Report it in your reply.",
        },
        withhold_patch,
    ]

    offered = False
    granted_at = None

    for turn in range(1, 9):
        with client.beta.messages.stream(
            model=MODEL,
            max_tokens=32_000,
            system=SYSTEM_PROMPT,
            tools=tool_module.TOOLS,
            output_config={"effort": "high"},
            cache_control={"type": "ephemeral"},
            messages=messages,
            betas=["mid-conversation-tool-changes-2026-07-01"],
        ) as stream:
            response = stream.get_final_message()

        usage.add(response.usage)
        names = [b.name for b in response.content if b.type == "tool_use"]
        print(f"  turn {turn}: stop={response.stop_reason} tools={names}")
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason != "tool_use":
            if not offered:
                print("  diagnosis done, granting write access")
                messages.append(
                    {
                        "role": "user",
                        "content": "Write access is now available. Apply the minimal fix and rerun the tests.",
                    }
                )
                messages.append(offer_patch)
                offered = True
                granted_at = turn
                continue
            break

        results = []
        for block in response.content:
            if block.type == "tool_use":
                output, is_error = tool_module.execute(block.name, dict(block.input or {}))
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": output,
                        "is_error": is_error,
                    }
                )
        messages.append({"role": "user", "content": results})

    after = repo.test_status()
    print(
        f"  write access granted after turn {granted_at}, "
        f"cache_read={usage.cache_read_input_tokens:,}, cost=${usage.cost_usd():.4f}, "
        f"tests_after={after.summary!r}, changed={repo.changed_files()}"
    )
    repo.reset()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "demo",
        choices=["disabled-thinking", "caching", "task-budget", "tool-addition"],
    )
    parser.add_argument("--total", type=int, default=20_000)
    args = parser.parse_args()

    if args.demo == "disabled-thinking":
        demo_disabled_thinking()
    elif args.demo == "caching":
        demo_caching()
    elif args.demo == "task-budget":
        demo_task_budget(args.total)
    elif args.demo == "tool-addition":
        demo_tool_addition()


if __name__ == "__main__":
    main()
