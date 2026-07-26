"""Repository tools. Claude requests them, this module decides whether to run them."""

import subprocess
import sys
from pathlib import Path

from agent.config import (
    MAX_FILE_CHARS,
    MAX_PATCH_CHARS,
    MAX_SEARCH_MATCHES,
    MAX_TEST_OUTPUT_CHARS,
    PATCHABLE_SUFFIXES,
    REPO_ROOT,
    TEST_COMMAND,
    TEST_TIMEOUT_SECONDS,
)

SKIP_DIRS = {"__pycache__", ".git", ".pytest_cache"}

TOOLS = [
    {
        "name": "list_files",
        "description": "List every source file in the repository, as repository-relative paths.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "search_code",
        "description": (
            "Search the repository for a literal string and return matching "
            "path, line number and line text. Cheaper than reading whole files."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Literal text to search for."}
            },
            "required": ["query"],
        },
    },
    {
        "name": "read_file",
        "description": "Read one repository file by its repository-relative path.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Repository-relative path, for example billing/invoices.py.",
                }
            },
            "required": ["path"],
        },
    },
    {
        "name": "run_tests",
        "description": (
            "Run the project's pytest suite and return the exit code with "
            "captured output. Takes no arguments; the command is fixed."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "apply_patch",
        "description": (
            "Replace an exact snippet in one Python file. The old_text must "
            "appear exactly once in the file."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Repository-relative path."},
                "old_text": {
                    "type": "string",
                    "description": "Exact text to replace, including indentation.",
                },
                "new_text": {"type": "string", "description": "Replacement text."},
            },
            "required": ["path", "old_text", "new_text"],
        },
    },
]

READ_ONLY_TOOL_NAMES = ["list_files", "search_code", "read_file", "run_tests"]


class ToolError(Exception):
    """A tool call that failed in a way Claude should see and react to."""


def _resolve(relative_path: str) -> Path:
    """Resolve a repository-relative path, refusing anything outside the repo."""
    candidate = Path(relative_path)
    if candidate.is_absolute():
        raise ToolError("Absolute paths are not allowed. Use a repository-relative path.")

    resolved = (REPO_ROOT / candidate).resolve()
    repo_root = REPO_ROOT.resolve()
    if resolved != repo_root and repo_root not in resolved.parents:
        raise ToolError("Path escapes the repository.")
    return resolved


def _repo_files() -> list[Path]:
    files = [
        path
        for path in sorted(REPO_ROOT.rglob("*"))
        if path.is_file()
        and not any(part in SKIP_DIRS for part in path.parts)
        and path.suffix in {".py", ".md", ".toml", ".cfg"}
    ]
    return files


def list_files() -> str:
    paths = [str(path.relative_to(REPO_ROOT)).replace("\\", "/") for path in _repo_files()]
    return "\n".join(paths) if paths else "(no files)"


def search_code(query: str) -> str:
    if not query:
        raise ToolError("query must not be empty.")

    matches: list[str] = []
    for path in _repo_files():
        if path.suffix != ".py":
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        relative = str(path.relative_to(REPO_ROOT)).replace("\\", "/")
        for number, line in enumerate(lines, start=1):
            if query in line:
                matches.append(f"{relative}:{number}: {line.strip()}")
                if len(matches) >= MAX_SEARCH_MATCHES:
                    matches.append("... more matches omitted")
                    return "\n".join(matches)

    return "\n".join(matches) if matches else f"No matches for {query!r}."


def read_file(path: str) -> str:
    resolved = _resolve(path)
    if not resolved.is_file():
        raise ToolError(f"File not found: {path}")

    text = resolved.read_text(encoding="utf-8")
    if len(text) > MAX_FILE_CHARS:
        text = text[:MAX_FILE_CHARS] + "\n... truncated"
    return text


def run_tests() -> str:
    completed = subprocess.run(
        [sys.executable, *TEST_COMMAND],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=TEST_TIMEOUT_SECONDS,
    )
    output = (completed.stdout + completed.stderr).strip()
    if len(output) > MAX_TEST_OUTPUT_CHARS:
        head = output[: MAX_TEST_OUTPUT_CHARS // 2]
        tail = output[-MAX_TEST_OUTPUT_CHARS // 2 :]
        output = f"{head}\n... truncated ...\n{tail}"
    return f"exit_code: {completed.returncode}\n{output}"


def apply_patch(path: str, old_text: str, new_text: str) -> str:
    resolved = _resolve(path)
    if resolved.suffix not in PATCHABLE_SUFFIXES:
        raise ToolError(f"Only {sorted(PATCHABLE_SUFFIXES)} files can be patched.")
    if not resolved.is_file():
        raise ToolError(f"File not found: {path}")
    if len(new_text) > MAX_PATCH_CHARS:
        raise ToolError(f"Patch is larger than the {MAX_PATCH_CHARS} character limit.")

    source = resolved.read_text(encoding="utf-8")
    occurrences = source.count(old_text)
    if occurrences == 0:
        raise ToolError("old_text was not found in the file. Read the file and retry.")
    if occurrences > 1:
        raise ToolError(f"old_text appears {occurrences} times. Include more context.")

    resolved.write_text(source.replace(old_text, new_text, 1), encoding="utf-8")
    return f"Patched {path}."


HANDLERS = {
    "list_files": list_files,
    "search_code": search_code,
    "read_file": read_file,
    "run_tests": run_tests,
    "apply_patch": apply_patch,
}


def execute(name: str, tool_input: dict) -> tuple[str, bool]:
    """Run one tool call. Returns the result text and whether it errored."""
    handler = HANDLERS.get(name)
    if handler is None:
        return f"Unknown tool: {name}", True
    try:
        return handler(**tool_input), False
    except ToolError as exc:
        return str(exc), True
    except subprocess.TimeoutExpired:
        return f"Tests exceeded the {TEST_TIMEOUT_SECONDS} second timeout.", True
    except TypeError as exc:
        return f"Bad arguments for {name}: {exc}", True
