"""The multi-turn tool-use loop."""

import json
import time
from dataclasses import dataclass, field

from pydantic import ValidationError

from agent import tools as tool_module
from agent.config import MAX_ITERATIONS, MAX_TOKENS, MODEL
from agent.costs import Usage
from agent.prompts import SYSTEM_PROMPT, build_task_prompt
from agent.schemas import RepairReport

REPEAT_LIMIT = 3

# Sentinel so an unset thinking config is simply left out of the request.
NOT_SET = object()


@dataclass
class ToolCall:
    name: str
    arguments: dict
    is_error: bool


@dataclass
class RunResult:
    effort: str
    usage: Usage
    tool_calls: list[ToolCall] = field(default_factory=list)
    iterations: int = 0
    stop_reason: str | None = None
    report: RepairReport | None = None
    report_error: str | None = None
    final_text: str = ""
    elapsed_seconds: float = 0.0
    seconds_to_first_output: float | None = None
    hit_max_tokens: bool = False
    refused: bool = False
    hit_iteration_cap: bool = False

    @property
    def cost_usd(self) -> float:
        return self.usage.cost_usd()

    @property
    def repeated_tool_calls(self) -> int:
        seen: set[str] = set()
        repeats = 0
        for call in self.tool_calls:
            signature = f"{call.name}:{json.dumps(call.arguments, sort_keys=True)}"
            if signature in seen:
                repeats += 1
            seen.add(signature)
        return repeats


def _tool_signature(name: str, arguments: dict) -> str:
    return f"{name}:{json.dumps(arguments, sort_keys=True)}"


def run_agent(
    client,
    effort: str,
    bug_report: str,
    *,
    max_tokens: int = MAX_TOKENS,
    max_iterations: int = MAX_ITERATIONS,
    tools: list[dict] | None = None,
    show_thinking: bool = False,
    on_event=None,
) -> RunResult:
    """Drive Claude Opus 5 through one bug-fixing attempt.

    Set show_thinking to stream the model's reasoning summary. It is billed the
    same either way, so the only cost is a little latency.
    """
    tools = tools if tools is not None else tool_module.TOOLS
    result = RunResult(effort=effort, usage=Usage())
    messages = [{"role": "user", "content": build_task_prompt(bug_report)}]
    call_counts: dict[str, int] = {}
    response = None
    started = time.perf_counter()

    thinking = {"type": "adaptive", "display": "summarized"} if show_thinking else NOT_SET

    def emit(kind: str, detail) -> None:
        if on_event is not None:
            on_event(kind, detail)

    for iteration in range(1, max_iterations + 1):
        result.iterations = iteration
        emit("turn_start", {"turn": iteration})

        request = {
            "model": MODEL,
            "max_tokens": max_tokens,
            "system": SYSTEM_PROMPT,
            "tools": tools,
            "output_config": {"effort": effort},
            "output_format": RepairReport,
            "cache_control": {"type": "ephemeral"},
            "messages": messages,
        }
        if thinking is not NOT_SET:
            request["thinking"] = thinking

        # max_tokens sits above 21,333, so the SDK requires a streamed request.
        with client.messages.stream(**request) as stream:
            for event in stream:
                if result.seconds_to_first_output is None and _is_visible(event):
                    result.seconds_to_first_output = time.perf_counter() - started

                if event.type == "content_block_start":
                    block = event.content_block
                    if block.type == "tool_use":
                        emit("tool_start", block.name)
                    elif block.type == "thinking":
                        emit("thinking_start", {})
                elif event.type == "content_block_delta":
                    delta = event.delta
                    if delta.type == "thinking_delta":
                        emit("thinking_delta", delta.thinking)
                    elif delta.type == "text_delta":
                        emit("text_delta", delta.text)
                    elif delta.type == "input_json_delta":
                        emit("tool_args_delta", delta.partial_json)

            response = stream.get_final_message()

        result.usage.add(response.usage)
        result.stop_reason = response.stop_reason
        emit("turn_end", {"turn": iteration, "usage": result.usage,
                          "stop_reason": response.stop_reason})

        # Thinking and redacted_thinking blocks have to go back unmodified, so
        # append the whole content list rather than a filtered subset.
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "refusal":
            result.refused = True
            emit("stop", "refusal")
            break

        if response.stop_reason == "max_tokens":
            result.hit_max_tokens = True
            emit("stop", "max_tokens")
            break

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type != "tool_use":
                    continue
                arguments = dict(block.input or {})
                signature = _tool_signature(block.name, arguments)
                call_counts[signature] = call_counts.get(signature, 0) + 1

                if call_counts[signature] >= REPEAT_LIMIT:
                    output, is_error = (
                        "You have already made this exact call twice. "
                        "Use the earlier result or try something different.",
                        True,
                    )
                else:
                    output, is_error = tool_module.execute(block.name, arguments)

                result.tool_calls.append(ToolCall(block.name, arguments, is_error))
                emit("tool_result", f"{block.name}{' (error)' if is_error else ''}")
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": output,
                        "is_error": is_error,
                    }
                )

            # Tool results come first in the content array. Text before them is a 400.
            messages.append({"role": "user", "content": tool_results})
            continue

        emit("stop", response.stop_reason or "unknown")
        break
    else:
        result.hit_iteration_cap = True

    result.elapsed_seconds = time.perf_counter() - started
    if response is not None:
        _attach_report(result, response)
    return result


def _is_visible(event) -> bool:
    """True for the first output a user would actually see."""
    if event.type == "content_block_delta":
        return event.delta.type in {"text_delta", "input_json_delta"}
    if event.type == "content_block_start":
        return event.content_block.type in {"text", "tool_use"}
    return False


def _attach_report(result: RunResult, response) -> None:
    """Pull the structured report off the final message."""
    text = next((b.text for b in response.content if b.type == "text"), "")
    result.final_text = text

    parsed = getattr(response, "parsed_output", None)
    if isinstance(parsed, RepairReport):
        result.report = parsed
        return

    if not text.strip():
        result.report_error = f"No text block to parse (stop_reason={result.stop_reason})."
        return

    try:
        result.report = RepairReport.model_validate_json(text)
    except ValidationError as exc:
        result.report_error = f"Report did not match the schema: {exc.error_count()} errors."
