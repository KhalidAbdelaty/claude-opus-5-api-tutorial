"""Shared settings for the bug-fixing agent."""

from pathlib import Path

MODEL = "claude-opus-5"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = PROJECT_ROOT / "sample_repo"
RESULTS_DIR = PROJECT_ROOT / "results"

# Claude Opus 5 standard rates, in dollars per million tokens, as of July 2026.
PRICE_INPUT = 5.00
PRICE_OUTPUT = 25.00
PRICE_CACHE_WRITE_5M = 6.25
PRICE_CACHE_READ = 0.50

# max_tokens caps thinking and visible output together. Anything above 21,333
# has to be streamed, which is why the agent loop uses client.messages.stream().
MAX_TOKENS = 32_000
MAX_ITERATIONS = 10

TEST_COMMAND = ["-m", "pytest", "tests", "-q", "--no-header", "--tb=short"]
TEST_TIMEOUT_SECONDS = 120

# Tool output caps. Every tool result is resent on each later request in the
# loop, so untrimmed output is paid for many times over.
MAX_FILE_CHARS = 8_000
MAX_TEST_OUTPUT_CHARS = 3_000
MAX_SEARCH_MATCHES = 40
MAX_PATCH_CHARS = 4_000
PATCHABLE_SUFFIXES = {".py"}
