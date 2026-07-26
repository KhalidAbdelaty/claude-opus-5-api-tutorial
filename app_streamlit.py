"""
Effort Dial - a Streamlit UI for the Claude Opus 5 bug-fixing agent.

Run the same real bug at any effort level and watch what changes: the tool calls,
the thinking tokens, the cache reads, the latency, and the cost. Every run resets
the sample repository first, so the comparison table builds up honest numbers you
measured yourself rather than numbers you read in an article.

Run with:  streamlit run app_streamlit.py
"""

import base64
import time
from pathlib import Path

import streamlit as st
from anthropic import Anthropic
from dotenv import load_dotenv

from agent import repo
from agent.config import MAX_ITERATIONS, MAX_TOKENS, PROJECT_ROOT
from agent.loop import run_agent

load_dotenv()

EFFORT_LEVELS = ["low", "medium", "high", "xhigh", "max"]
ROOT_CAUSE_FILE = "billing/timeutils.py"


@st.cache_resource
def get_client() -> Anthropic:
    return Anthropic()


@st.cache_data
def logo_data_uri(path: str) -> str:
    with open(path, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


@st.cache_data
def default_bug_report() -> str:
    return (PROJECT_ROOT / "bug_report.md").read_text(encoding="utf-8").strip()


# ──────────────────────────────────────────────────────────────────────────────
# Page setup and theme
# ──────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Effort Dial - Claude Opus 5",
    page_icon="🔧",
    layout="wide",
)

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Spectral:wght@500;600;700&display=swap');

:root {
  --bg: #FAF9F5;
  --paper: #F0EEE6;
  --coral: #D97757;
  --coral-dark: #BE5D3B;
  --ink: #1F1E1D;
  --muted: #73706B;
  --border: #E7E4DA;
  --green: #1F8A4C;
  --red: #B3402F;
}

.stApp { background: var(--bg); }
html, body, [class*="css"], .stMarkdown, p, li, label { font-family: 'Inter', sans-serif; color: var(--ink); }
h1, h2, h3, h4 { font-family: 'Spectral', Georgia, serif; color: var(--ink); letter-spacing: -0.015em; }
#MainMenu, footer, header { visibility: hidden; }
.block-container { padding-top: 1.8rem; max-width: 1250px; }

.hero { padding: 2px 0 4px 0; }
.hero h1 { font-size: 2.55rem; margin: .1rem 0 .25rem 0; }
.hero p { color: var(--muted); font-size: 1.05rem; margin: 0; }
.chip {
  display: inline-block; background: rgba(217,119,87,.12); color: var(--coral-dark);
  border: 1px solid rgba(217,119,87,.30); padding: 3px 13px; border-radius: 999px;
  font-size: .80rem; font-weight: 600; letter-spacing: .02em;
}

[data-testid="stSidebar"] { background: var(--paper); border-right: 1px solid var(--border); }
[data-testid="stSidebar"] h3 { font-size: 1.0rem; margin: .1rem 0 .1rem 0; }
[data-testid="stSidebar"] [data-testid="stVerticalBlock"] { gap: .55rem; }
[data-testid="stSidebar"] hr { margin: .45rem 0; }

.logo-link { display: block; margin: 0 0 2px 0; }
.logo-link img { width: 100%; display: block; transition: opacity .15s ease; }
.logo-link:hover img { opacity: .82; }
.logo-sub { color: var(--muted); font-size: .78rem; margin: 2px 0 6px 2px; }

[data-testid="stVerticalBlockBorderWrapper"] {
  background: #FFFFFF; border: 1px solid var(--border) !important;
  border-radius: 16px; box-shadow: 0 1px 3px rgba(31,30,29,.05);
}

.stButton > button, .stDownloadButton > button {
  background: #fff; color: var(--ink); border: 1px solid var(--border); border-radius: 11px;
  padding: .55rem 1.1rem; font-weight: 600; font-size: .94rem; transition: all .15s ease;
}
.stButton > button:hover, .stDownloadButton > button:hover {
  border-color: var(--coral); color: var(--coral-dark); transform: translateY(-1px);
}
.stButton > button[kind="primary"] { background: var(--coral); color: #fff; border: none; }
.stButton > button[kind="primary"]:hover { background: var(--coral-dark); color: #fff; }

.stTextArea textarea {
  border-radius: 12px; border: 1px solid var(--border); background: #fff;
  font-size: .98rem; color: var(--ink);
}
.stTextArea textarea:focus { border-color: var(--coral); box-shadow: 0 0 0 2px rgba(217,119,87,.18); }

[data-testid="stMetric"] {
  background: #fff; border: 1px solid var(--border); border-radius: 14px; padding: 12px 16px;
}
[data-testid="stMetricValue"] { font-family: 'Spectral', serif; color: var(--coral-dark); }

.stTabs [data-baseweb="tab-list"] { gap: 4px; }
.stTabs [data-baseweb="tab"] { border-radius: 9px 9px 0 0; padding: 6px 14px; }
.stTabs [aria-selected="true"] { color: var(--coral-dark); }

.label { font-weight: 600; color: var(--muted); font-size: .78rem; text-transform: uppercase; letter-spacing: .06em; }
.summary {
  background: rgba(217,119,87,.08); border-left: 3px solid var(--coral);
  padding: 14px 18px; border-radius: 10px; font-size: 1.02rem;
}
.pill {
  display: inline-block; background: var(--paper); border: 1px solid var(--border);
  border-radius: 8px; padding: 4px 10px; margin: 3px 4px 3px 0; font-size: .86rem;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
}
.hint {
  background: #fff; border: 1px dashed var(--border); border-radius: 14px;
  padding: 18px 20px; color: var(--muted);
}
.trace {
  background: #fff; border: 1px solid var(--border); border-radius: 12px;
  padding: 10px 14px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: .86rem; line-height: 1.75; max-height: 260px; overflow-y: auto;
}
.pass { color: var(--green); font-weight: 600; }
.fail { color: var(--red); font-weight: 600; }
hr { border-color: var(--border); margin: .8rem 0; }
a { color: var(--coral-dark); }
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)

LOGO = str(Path(__file__).parent / "assets" / "datacamp-logo.png")


# ──────────────────────────────────────────────────────────────────────────────
# Session state
# ──────────────────────────────────────────────────────────────────────────────

if "runs" not in st.session_state:
    st.session_state.runs = []
if "session_cost" not in st.session_state:
    st.session_state.session_cost = 0.0
if "bug_text" not in st.session_state:
    st.session_state.bug_text = default_bug_report()


# ──────────────────────────────────────────────────────────────────────────────
# Sidebar
# ──────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    if Path(LOGO).exists():
        st.markdown(
            f'<a class="logo-link" href="https://www.datacamp.com/blog" target="_blank" '
            f'rel="noopener"><img src="{logo_data_uri(LOGO)}" alt="DataCamp"/></a>',
            unsafe_allow_html=True,
        )
        st.markdown('<div class="logo-sub">Built for the DataCamp blog</div>',
                    unsafe_allow_html=True)

    st.markdown("### Effort")
    effort = st.select_slider(
        "Effort", options=EFFORT_LEVELS, value="low", label_visibility="collapsed",
        help="Reasoning depth for every request in the loop. Higher effort means more "
             "thinking tokens, more tool calls, more latency, and more cost. The API "
             "default is high.",
    )
    st.caption(f"`output_config={{\"effort\": \"{effort}\"}}`")

    st.markdown("### Limits")
    max_tokens = st.select_slider(
        "Max output tokens", options=[4000, 8000, 16000, 32000], value=8000,
        help="Caps thinking and visible output together. Above 21,333 the SDK requires "
             "streaming, which this agent always uses.",
    )
    max_iterations = st.slider("Max tool-loop turns", 3, 15, MAX_ITERATIONS)

    st.markdown("---")
    st.markdown("### Session spend")
    spend_ph = st.empty()
    spend_ph.metric("Total this session", f"${st.session_state.session_cost:.4f}")

    if st.session_state.runs:
        if st.button("Clear runs", width="stretch"):
            st.session_state.runs = []
            st.session_state.session_cost = 0.0
            st.rerun()

    st.markdown("---")
    if st.button("Reset sample repo", width="stretch"):
        repo.reset()
        st.toast("Sample repository restored to baseline.", icon="↩️")


# ──────────────────────────────────────────────────────────────────────────────
# Header
# ──────────────────────────────────────────────────────────────────────────────

st.markdown(
    """
    <div class="hero">
      <span class="chip">🔧 Powered by Claude Opus 5</span>
      <h1>Effort Dial</h1>
      <p>Run the same real bug at every effort level and watch what actually changes.</p>
    </div>
    """,
    unsafe_allow_html=True,
)
st.write("")

client = get_client()

left, right = st.columns([1.35, 1])

with left:
    st.markdown('<span class="label">Bug report</span>', unsafe_allow_html=True)
    bug_text = st.text_area(
        "Bug report", key="bug_text", height=150, label_visibility="collapsed",
    )
    run = st.button(f"Run the agent at {effort} effort", type="primary", width="stretch")

with right:
    st.markdown('<span class="label">Sample repository</span>', unsafe_allow_html=True)
    baseline = repo.test_status()
    state = "pass" if baseline.all_passed else "fail"
    st.markdown(
        f'<div class="hint">A small billing service with a planted defect in a shared '
        f'date helper. Two modules call it, so one bug fails two tests.<br><br>'
        f'Current suite: <span class="{state}">{baseline.summary}</span></div>',
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Run
# ──────────────────────────────────────────────────────────────────────────────

def render_metrics(result, after):
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Tool calls", len(result.tool_calls))
    c2.metric("Output tokens", f"{result.usage.output_tokens:,}")
    c3.metric("Cost", f"${result.cost_usd:.4f}")
    c4.metric("Elapsed", f"{result.elapsed_seconds:.0f}s")

    c5, c6, c7, c8 = st.columns(4)
    c5.metric("Input tokens", f"{result.usage.total_input_tokens:,}")
    c6.metric("Cache reads", f"{result.usage.cache_read_input_tokens:,}")
    c7.metric("Requests", result.usage.requests)
    c8.metric("Suite after", "passing" if after.all_passed else f"{after.failed} failing")


if run:
    if not bug_text.strip():
        st.warning("Describe the bug first.")
    else:
        repo.reset()
        before = repo.test_status()

        st.write("")
        with st.container(border=True):
            st.markdown('<span class="label">Tool calls</span>', unsafe_allow_html=True)
            trace_ph = st.empty()
            trace: list[str] = []

            def on_event(kind: str, detail: str) -> None:
                if kind == "tool_start":
                    trace.append(f"→ {detail}")
                elif kind == "tool_result" and detail.endswith("(error)"):
                    trace[-1] = trace[-1] + "  (tool error, returned to Claude)"
                elif kind == "stop":
                    trace.append(f"■ stop_reason: {detail}")
                trace_ph.markdown(
                    '<div class="trace">' + "<br>".join(trace) + "</div>",
                    unsafe_allow_html=True,
                )

            trace_ph.markdown('<div class="trace">starting…</div>', unsafe_allow_html=True)
            started = time.time()
            try:
                result = run_agent(
                    client,
                    effort=effort,
                    bug_report=bug_text,
                    max_tokens=max_tokens,
                    max_iterations=max_iterations,
                    on_event=on_event,
                )
            except Exception as exc:  # noqa: BLE001
                st.error(f"Run failed: {type(exc).__name__} - {exc}")
                st.stop()

        after = repo.test_status()
        changed = repo.changed_files()
        fixed = after.all_passed and ROOT_CAUSE_FILE in changed

        if result.refused:
            st.warning(
                "The safety classifier declined this request. A refusal arrives as an "
                "HTTP 200 with `stop_reason: \"refusal\"`, not an exception."
            )
        elif result.hit_max_tokens:
            st.warning(
                f"The run stopped at the {max_tokens:,} token ceiling. Treat it as "
                "truncated rather than as a failed repair, and raise max output tokens."
            )

        st.write("")
        render_metrics(result, after)
        st.write("")

        tabs = st.tabs(["Report", "Patch", "What the app measured"])

        with tabs[0]:
            with st.container(border=True):
                if result.report is None:
                    st.error(f"No parsed report. {result.report_error}")
                    if result.final_text:
                        st.code(result.final_text[:1500])
                else:
                    r = result.report
                    st.markdown(f'<div class="summary">{r.root_cause}</div>',
                                unsafe_allow_html=True)
                    st.write("")
                    a, b = st.columns(2)
                    a.markdown('<span class="label">Model status</span>',
                               unsafe_allow_html=True)
                    a.markdown(f"`{r.status}` at `{r.confidence}` confidence")
                    b.markdown('<span class="label">Files changed</span>',
                               unsafe_allow_html=True)
                    b.markdown(" ".join(f'<span class="pill">{f}</span>'
                                        for f in r.files_changed) or "none",
                               unsafe_allow_html=True)
                    st.write("")
                    st.markdown('<span class="label">Fix</span>', unsafe_allow_html=True)
                    st.markdown(r.fix_summary or "_none reported_")
                    if r.remaining_risks:
                        st.markdown('<span class="label">Remaining risks</span>',
                                    unsafe_allow_html=True)
                        for risk in r.remaining_risks:
                            st.markdown(f"- {risk}")

        with tabs[1]:
            diff = repo.diff_text()
            if diff.strip():
                st.code(diff, language="diff")
                st.download_button("Download patch (.diff)", diff,
                                   file_name=f"fix-{effort}.diff", mime="text/plain")
            else:
                st.info("The agent did not change any file.")

        with tabs[2]:
            st.markdown(
                f"- Tests before: `{before.summary}`\n"
                f"- Tests after: `{after.summary}`\n"
                f"- Root-cause file touched: `{ROOT_CAUSE_FILE in changed}`\n"
                f"- Patch size: {repo.diff_line_count()} changed lines\n"
                f"- Stop reason: `{result.stop_reason}`\n"
                f"- Repeated tool calls: {result.repeated_tool_calls}\n"
                f"- Cache writes: {result.usage.cache_creation_input_tokens:,} tokens"
            )
            st.caption(
                "The model reports what it concluded. This tab is what the application "
                "verified by rerunning pytest and reading git diff, which is the only "
                "part you should trust."
            )

        st.session_state.session_cost += result.cost_usd
        st.session_state.runs.append({
            "Effort": effort,
            "Suite passed": "yes" if fixed else "no",
            "Tool calls": len(result.tool_calls),
            "Output tokens": result.usage.output_tokens,
            "Cache reads": result.usage.cache_read_input_tokens,
            "Seconds": round(result.elapsed_seconds, 1),
            "Cost ($)": round(result.cost_usd, 4),
        })
        spend_ph.metric("Total this session", f"${st.session_state.session_cost:.4f}")
        st.toast(
            f"{effort} run finished - ${result.cost_usd:.4f}",
            icon="✅" if fixed else "⚠️",
        )

elif not st.session_state.runs:
    st.write("")
    st.markdown(
        '<div class="hint">Pick an effort level in the sidebar and run the agent. '
        'Start at <b>low</b>, which costs about four cents, then try <b>xhigh</b> and '
        'compare. Each run resets the repository first, so the two are measured against '
        'the same starting state.</div>',
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Comparison
# ──────────────────────────────────────────────────────────────────────────────

if st.session_state.runs:
    st.write("")
    st.markdown("### Your runs")
    st.caption(
        "Built from your own runs, not from the article. Output is non-deterministic, "
        "so run each level a few times before drawing a conclusion."
    )
    st.dataframe(st.session_state.runs, width="stretch", hide_index=True)

    costs = [r["Cost ($)"] for r in st.session_state.runs]
    if len(costs) > 1:
        cheapest = min(st.session_state.runs, key=lambda r: r["Cost ($)"])
        dearest = max(st.session_state.runs, key=lambda r: r["Cost ($)"])
        if dearest["Cost ($)"] > 0:
            ratio = dearest["Cost ($)"] / max(cheapest["Cost ($)"], 1e-9)
            st.markdown(
                f"Your `{dearest['Effort']}` run cost **{ratio:.1f}x** your "
                f"`{cheapest['Effort']}` run. Both fixed the suite: "
                f"**{cheapest['Suite passed']}** and **{dearest['Suite passed']}**."
            )
