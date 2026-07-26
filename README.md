# Claude Opus 5 bug-fixing agent

Working code for the DataCamp tutorial *Claude Opus 5 API Tutorial: Build and Benchmark a
Bug-Fixing Agent in Python*. Every number in the article was produced by this project and is
recorded in `results/measurements.md`.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
echo "ANTHROPIC_API_KEY=sk-ant-..." > .env
```

Tested on Python 3.11 with `anthropic==0.120.0` on July 26, 2026.

## Layout

- `app_streamlit.py` the Effort Dial UI
- `agent/config.py` model, prices, token ceilings, tool output caps
- `agent/tools.py` the five repository tools and their validation
- `agent/loop.py` the streaming multi-turn tool loop
- `agent/schemas.py` the Pydantic repair report
- `agent/costs.py` four-rate cost accounting and the budget guard
- `agent/repo.py` git reset and pytest measurement used by the runner
- `agent/prompts.py` the system prompt, held constant across runs
- `sample_repo/` the disposable billing service with the planted bug
- `results/` raw benchmark rows, the chart, and the measurements writeup
- `assets/` the DataCamp logo used in the app sidebar

## The Streamlit app

```bash
streamlit run app_streamlit.py
```

Pick an effort level, run the agent against the sample bug, and watch the tool calls
arrive live. Each run resets the repository first and appends a row to a comparison
table, so you build the effort tradeoff from your own measurements. A `low` run costs
about four cents.

The app surfaces what the article argues: the model's own report sits in one tab, and
what the application verified by rerunning pytest sits in another.

## Running it from the terminal

One agent run at a chosen effort level. Resets the sample repository first.

```bash
python run_agent.py --effort low --max-tokens 8000
```

The full effort matrix. The budget guard stops cleanly at the ceiling.

```bash
python benchmark.py --runs 3 --budget 8.0 --out benchmark.json
python analyze.py
python make_chart.py
```

The side demos used in the article.

```bash
python extras.py disabled-thinking     # the 400 error, unbilled
python extras.py caching               # cache write then cache read
python extras.py task-budget --total 20000
python extras.py tool-addition         # progressive write access
```

## The planted bug

`billing/timeutils.py` documents ceiling behavior for `days_between` and implements
`timedelta.days`, which truncates. Two modules call it, so one defect fails two tests:
`test_trial_active_on_final_day` and `test_prorated_credit_counts_partial_day`. The baseline is
two failures and four passes.

Patching `is_trial_active` to accept zero fixes the reported symptom and leaves the invoice test
failing, so a shallow fix is objectively detectable. `sample_repo/` is its own git repository and
`agent/repo.py` resets it to the baseline commit before every measured run.

## Cost

The fifteen-run benchmark cost $0.92. Everything in the project, including exploratory runs,
came to about $1.63.
