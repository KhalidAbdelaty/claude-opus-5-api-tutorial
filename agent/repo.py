"""Git and pytest helpers the runner uses to measure what actually happened."""

import re
import subprocess
import sys
from dataclasses import dataclass

from agent.config import REPO_ROOT, TEST_COMMAND, TEST_TIMEOUT_SECONDS

SUMMARY_PATTERN = re.compile(r"(\d+) (passed|failed|error|errors)")


@dataclass
class TestStatus:
    exit_code: int
    passed: int
    failed: int
    summary: str

    @property
    def all_passed(self) -> bool:
        return self.exit_code == 0 and self.failed == 0


def ensure_repo() -> None:
    """Give the sample repository its own git history the first time it is used.

    It ships as plain files inside the tutorial repository. Without a `.git` of
    its own, `git checkout -- .` would resolve to the parent repository instead,
    so a fresh clone has to be initialized before the first run.
    """
    if (REPO_ROOT / ".git").exists():
        return

    subprocess.run(["git", "init", "-q"], cwd=REPO_ROOT, check=True)
    subprocess.run(["git", "add", "-A"], cwd=REPO_ROOT, check=True)
    subprocess.run(
        [
            "git",
            "-c", "user.name=Bug-Fixing Agent Tutorial",
            "-c", "user.email=tutorial@example.invalid",
            "commit", "-q", "-m",
            "Baseline billing service with failing trial and proration tests",
        ],
        cwd=REPO_ROOT,
        check=True,
    )


def reset() -> None:
    """Restore the sample repository to its baseline commit."""
    ensure_repo()
    subprocess.run(["git", "checkout", "--", "."], cwd=REPO_ROOT, check=True)
    subprocess.run(["git", "clean", "-qfd"], cwd=REPO_ROOT, check=True)


def test_status() -> TestStatus:
    """Run the suite the same way the agent's run_tests tool does."""
    completed = subprocess.run(
        [sys.executable, *TEST_COMMAND],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=TEST_TIMEOUT_SECONDS,
    )
    output = completed.stdout + completed.stderr
    counts = {kind: int(number) for number, kind in SUMMARY_PATTERN.findall(output)}
    summary_line = next(
        (line.strip() for line in reversed(output.splitlines()) if " passed" in line or " failed" in line),
        "",
    )
    return TestStatus(
        exit_code=completed.returncode,
        passed=counts.get("passed", 0),
        failed=counts.get("failed", 0) + counts.get("error", 0) + counts.get("errors", 0),
        summary=re.sub(r"=+", "", summary_line).strip(),
    )


def changed_files() -> list[str]:
    """Repository-relative paths the agent modified."""
    completed = subprocess.run(
        ["git", "diff", "--name-only"], cwd=REPO_ROOT, capture_output=True, text=True
    )
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def diff_line_count() -> int:
    """Total added and removed lines, a rough measure of patch size."""
    completed = subprocess.run(
        ["git", "diff", "--numstat"], cwd=REPO_ROOT, capture_output=True, text=True
    )
    total = 0
    for line in completed.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            added, removed = parts[0], parts[1]
            total += int(added) if added.isdigit() else 0
            total += int(removed) if removed.isdigit() else 0
    return total


def diff_text() -> str:
    completed = subprocess.run(["git", "diff"], cwd=REPO_ROOT, capture_output=True, text=True)
    return completed.stdout
