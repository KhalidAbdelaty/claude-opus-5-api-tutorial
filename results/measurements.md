# Measured results

Every number in the article comes from this file. Runs executed July 25 and 26, 2026
against `claude-opus-5` with `anthropic==0.120.0`.

## Effort benchmark, three runs per level

Raw rows in `benchmark.json`. Averages produced by `analyze.py`.

| Effort | Suite passed | Tool calls | Output tokens | Time to first output | Total time | Cost per run |
|---|---|---|---|---|---|---|
| `low` | 3/3 | 8.0 | 827 | 2.9s | 24s | $0.0387 |
| `medium` | 3/3 | 8.0 | 1,008 | 2.7s | 26s | $0.0466 |
| `high` | 3/3 | 10.0 | 1,352 | 2.9s | 29s | $0.0659 |
| `xhigh` | 3/3 | 11.3 | 1,546 | 2.8s | 35s | $0.0778 |
| `max` | 2/3 | 8.3 | 1,787 | 6.6s | 38s | $0.0762 |

Supporting detail, averaged per level:

- `low`: input 19,190 tok (17,712 cache reads), patch 4.0 lines, 1.0 file
- `medium`: input 19,876 tok (17,873 cache reads), patch 3.7 lines, 1.0 file
- `high`: input 28,525 tok (25,417 cache reads), patch 4.3 lines, 1.0 file
- `xhigh`: input 36,236 tok (32,582 cache reads), patch 4.3 lines, 1.0 file
- `max`: input 26,647 tok (23,475 cache reads), patch 4.7 lines, 0.7 files

The `max` row is dragged down by one degenerate run. Excluding it, the two `max`
runs that actually used tools: 2/2 fixed, 12.5 tool calls, 2,576 output tokens,
47s, $0.1112 per run.

Total: 15 runs, $0.9159.

## The degenerate run

`max` effort, attempt 1. `stop_reason: end_turn`, 1 iteration, 0 tool calls,
209 output tokens, $0.0063. It returned schema-valid JSON with
`root_cause: "b0"`, `fix_summary: ""`, `status: "partial"`. Tests were untouched
at 2 failed, 4 passed. Pydantic accepted it because the shape was correct.

## Prompt caching inside one run

System prompt plus tool definitions measured at 1,231 tokens, above the 512-token
minimum for Opus 5.

```
turn 1: uncached_input=2  cache_write=1231  cache_read=0     output=26
turn 2: uncached_input=2  cache_write=111   cache_read=1231  output=108
```

## Task budgets

Both runs at `high` effort, `task-budgets-2026-03-13` beta header.

```
budget=20000   tool_calls=9    output=1465   cost=$0.0719  tests_after='6 passed'
budget=80000   tool_calls=10   output=1169   cost=$0.0597  tests_after='6 passed'
```

Below the documented minimum:

```
HTTP 400: `task_budget.total` must be at least 20,000 tokens for this model.
```

## Mid-conversation tool changes

`mid-conversation-tool-changes-2026-07-01`. `apply_patch` withheld with a
`tool_removal` block, granted after diagnosis with `tool_addition`.

```
turn 1: stop=tool_use tools=['list_files', 'run_tests']
turn 2: stop=tool_use tools=['read_file', 'read_file', 'read_file']
turn 3: stop=tool_use tools=['read_file', 'read_file']
turn 4: stop=tool_use tools=['read_file']
turn 5: stop=end_turn tools=[]
  -> granted write access
turn 6: stop=tool_use tools=['apply_patch']
turn 7: stop=tool_use tools=['apply_patch']
turn 8: stop=tool_use tools=['read_file', 'run_tests']
```

Cache reads 25,557, cost $0.1197, tests after: 6 passed, changed:
`billing/timeutils.py`.

Placing the blocks in a `user` message returns:

```
HTTP 400: 'tool_addition'/'tool_removal' blocks are only permitted within
`role: "system"` messages
```

## Errors captured

Disabling thinking above `high` effort:

```
effort=high  accepted, blocks=['text']
effort=xhigh HTTP 400: output_config.effort 'xhigh' is not supported when
thinking is disabled on this model. Use effort 'high' or below, or enable thinking.
```

Non-streaming request at 32,000 `max_tokens`:

```
ValueError: Streaming is required for operations that may take longer than 10 minutes.
```

## First call block types

```
Block types: ['thinking', 'text']
```

## Total spend

Benchmark 15 runs $0.9159, exploratory pass $0.3847, harness debugging $0.0538,
side demos $0.2642, first call $0.0080. Whole project: about $1.63.
