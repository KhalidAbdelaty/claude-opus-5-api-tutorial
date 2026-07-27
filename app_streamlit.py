"""
Effort Dial - a live view of the Claude Opus 5 bug-fixing agent.

Watch the model reason, call tools, patch a real defect and rerun the suite,
with the token count and the bill updating as it goes. Then run the same bug at
another effort level and let the app build the comparison for you.

Thinking is streamed with display "summarized", which the API bills identically
to the default, so the reasoning you see here is free to show.

Run with:  streamlit run app_streamlit.py
"""

import base64
import html
import time
from pathlib import Path

import streamlit as st
from anthropic import Anthropic
from dotenv import load_dotenv

from agent import repo
from agent.config import MAX_ITERATIONS, PROJECT_ROOT
from agent.loop import run_agent

load_dotenv()

EFFORTS = ["low", "medium", "high", "xhigh", "max"]
ROOT_CAUSE_FILE = "billing/timeutils.py"

# How many recent turns stay on screen. The panel is fixed height, so an
# unwindowed feed would push the newest reasoning out of view mid-run.
WINDOW = 3


@st.cache_resource
def get_client() -> Anthropic:
    return Anthropic()


@st.cache_data
def logo_uri(path: str) -> str:
    return "data:image/png;base64," + base64.b64encode(Path(path).read_bytes()).decode()


@st.cache_data
def default_bug() -> str:
    return (PROJECT_ROOT / "bug_report.md").read_text(encoding="utf-8").strip()


st.set_page_config(page_title="Effort Dial - Claude Opus 5", page_icon="🔧", layout="wide")

CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Spectral:wght@500;600;700&display=swap');
:root{--bg:#FAF9F5;--paper:#F0EEE6;--coral:#D97757;--coral-dark:#BE5D3B;--ink:#1F1E1D;
--muted:#73706B;--border:#E7E4DA;--green:#1F8A4C;--red:#B3402F;--violet:#6B5B95;}
.stApp{background:var(--bg);}
html,body,[class*="css"],.stMarkdown,p,li,label{font-family:'Inter',sans-serif;color:var(--ink);}
h1,h2,h3,h4{font-family:'Spectral',Georgia,serif;color:var(--ink);letter-spacing:-.015em;}
#MainMenu,footer,header{visibility:hidden;}
.block-container{padding-top:1.6rem;max-width:1320px;}

.hero h1{font-size:2.5rem;margin:.1rem 0 .2rem 0;}
.hero p{color:var(--muted);font-size:1.04rem;margin:0;}
.chip{display:inline-block;background:rgba(217,119,87,.12);color:var(--coral-dark);
border:1px solid rgba(217,119,87,.30);padding:3px 13px;border-radius:999px;
font-size:.79rem;font-weight:600;letter-spacing:.02em;}

[data-testid="stSidebar"]{background:var(--paper);border-right:1px solid var(--border);}
[data-testid="stSidebar"] h3{font-size:1rem;margin:.1rem 0;}
[data-testid="stSidebar"] [data-testid="stVerticalBlock"]{gap:.5rem;}
.logo-link{display:block;margin-bottom:2px;}
.logo-link img{width:100%;display:block;transition:opacity .15s ease;}
.logo-link:hover img{opacity:.82;}
.logo-sub{color:var(--muted);font-size:.78rem;margin:2px 0 6px 2px;}

[data-testid="stVerticalBlockBorderWrapper"]{background:#fff;border:1px solid var(--border)!important;
border-radius:16px;box-shadow:0 1px 3px rgba(31,30,29,.05);}
.stButton>button{background:#fff;color:var(--ink);border:1px solid var(--border);border-radius:11px;
padding:.6rem 1.1rem;font-weight:600;transition:all .15s ease;}
.stButton>button:hover{border-color:var(--coral);color:var(--coral-dark);transform:translateY(-1px);}
.stButton>button[kind="primary"]{background:var(--coral);color:#fff;border:none;}
.stButton>button[kind="primary"]:hover{background:var(--coral-dark);}
.stTextArea textarea{border-radius:12px;border:1px solid var(--border);background:#fff;font-size:.97rem;}
[data-testid="stMetric"]{background:#fff;border:1px solid var(--border);border-radius:14px;padding:10px 14px;}
[data-testid="stMetricValue"]{font-family:'Spectral',serif;color:var(--coral-dark);font-size:1.55rem;}
.stTabs [aria-selected="true"]{color:var(--coral-dark);}

.label{font-weight:600;color:var(--muted);font-size:.76rem;text-transform:uppercase;letter-spacing:.06em;}
.pill{display:inline-block;background:var(--paper);border:1px solid var(--border);border-radius:8px;
padding:3px 9px;margin:2px 4px 2px 0;font-size:.84rem;
font-family:ui-monospace,SFMono-Regular,Menlo,monospace;}
.hint{background:#fff;border:1px dashed var(--border);border-radius:14px;padding:16px 18px;color:var(--muted);}
.summary{background:rgba(217,119,87,.08);border-left:3px solid var(--coral);
padding:13px 17px;border-radius:10px;font-size:1.01rem;}
.pass{color:var(--green);font-weight:700;} .fail{color:var(--red);font-weight:700;}

/* Live feed */
.feed{background:#fff;border:1px solid var(--border);border-radius:14px;padding:6px 4px;
max-height:430px;overflow-y:auto;}
.turn{border-left:3px solid var(--border);margin:8px 10px;padding:2px 0 2px 12px;}
.turn-h{font-size:.74rem;font-weight:700;color:var(--muted);text-transform:uppercase;
letter-spacing:.07em;margin-bottom:4px;}
.think{color:var(--violet);font-size:.90rem;line-height:1.6;white-space:pre-wrap;
border-left:2px solid rgba(107,91,149,.28);padding-left:10px;margin:4px 0 6px 0;}
.think-tag{font-size:.7rem;font-weight:700;letter-spacing:.07em;color:var(--violet);
text-transform:uppercase;display:block;margin-bottom:2px;}
.tool{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:.86rem;
background:var(--paper);border:1px solid var(--border);border-radius:8px;
padding:4px 9px;margin:3px 0;display:inline-block;}
.tool-ok{border-left:3px solid var(--green);}
.tool-err{border-left:3px solid var(--red);}
.cursor{color:var(--coral);font-weight:700;}
hr{border-color:var(--border);margin:.7rem 0;}
a{color:var(--coral-dark);}
</style>
"""
st.markdown(CSS, unsafe_allow_html=True)
LOGO = str(Path(__file__).parent / "assets" / "datacamp-logo.png")

for key, default in [("runs", []), ("spend", 0.0), ("bug_text", default_bug())]:
    st.session_state.setdefault(key, default)


# ──────────────────────────────────────────────────────────────────────────────
# Sidebar
# ──────────────────────────────────────────────────────────────────────────────

with st.sidebar:
    if Path(LOGO).exists():
        st.markdown(
            f'<a class="logo-link" href="https://www.datacamp.com/blog" target="_blank" '
            f'rel="noopener"><img src="{logo_uri(LOGO)}" alt="DataCamp"/></a>'
            f'<div class="logo-sub">Built for the DataCamp blog</div>',
            unsafe_allow_html=True,
        )

    st.markdown("### Effort")
    effort = st.select_slider("Effort", EFFORTS, value="low", label_visibility="collapsed")
    st.caption(f'`output_config={{"effort": "{effort}"}}`')

    st.markdown("### Live view")
    show_thinking = st.toggle(
        "Stream the reasoning", value=True,
        help='Sets thinking display to "summarized". The API bills it the same as the '
             'default, so showing it costs nothing extra.',
    )
    max_tokens = st.select_slider("Max output tokens", [4000, 8000, 16000, 32000], value=8000)
    max_iterations = st.slider("Max turns", 3, 15, MAX_ITERATIONS)

    st.markdown("---")
    spend_box = st.empty()
    spend_box.metric("Session spend", f"${st.session_state.spend:.4f}")
    if st.session_state.runs and st.button("Clear runs", width="stretch"):
        st.session_state.runs, st.session_state.spend = [], 0.0
        st.rerun()
    if st.button("Reset sample repo", width="stretch"):
        repo.reset()
        st.rerun()


# ──────────────────────────────────────────────────────────────────────────────
# Header
# ──────────────────────────────────────────────────────────────────────────────

st.markdown(
    '<div class="hero"><span class="chip">🔧 Powered by Claude Opus 5</span>'
    '<h1>Effort Dial</h1><p>Watch the agent reason, patch a real bug, and bill you for it.</p></div>',
    unsafe_allow_html=True,
)
st.write("")

client = get_client()
left, right = st.columns([1.5, 1])

with left:
    st.markdown('<span class="label">Bug report</span>', unsafe_allow_html=True)
    bug_text = st.text_area("Bug", key="bug_text", height=120, label_visibility="collapsed")
    go = st.button(f"Run the agent at {effort} effort", type="primary", width="stretch")

with right:
    st.markdown('<span class="label">Sample repository</span>', unsafe_allow_html=True)
    base = repo.test_status()
    cls = "pass" if base.all_passed else "fail"
    st.markdown(
        f'<div class="hint">A billing service with a planted defect in a shared date '
        f'helper. Two modules call it, so one bug breaks two tests.<br><br>'
        f'<b>Suite now:</b> <span class="{cls}">{base.summary}</span></div>',
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Live run
# ──────────────────────────────────────────────────────────────────────────────

class LiveFeed:
    """Renders streaming turns into a single scrolling panel."""

    def __init__(self, slot, metric_slots, started):
        self.slot = slot
        self.tok, self.cost, self.secs, self.turns = metric_slots
        self.started = started
        self.turns_html: list[str] = []
        self.buf = ""
        self.mode = None
        self.last_paint = 0.0

    def _flush(self):
        if self.buf and self.mode == "think":
            body = html.escape(self.buf)
            self.turns_html[-1] += (
                f'<span class="think-tag">reasoning</span><div class="think">{body}</div>'
            )
        self.buf, self.mode = "", None

    def paint(self, force=False):
        """Repaint the feed, keeping only the newest turns so nothing scrolls away."""
        now = time.perf_counter()
        if not force and now - self.last_paint < 0.12:
            return
        self.last_paint = now

        live = ""
        if self.buf and self.mode == "think":
            live = (f'<span class="think-tag">reasoning</span>'
                    f'<div class="think">{html.escape(self.buf)}<span class="cursor">▌</span></div>')

        window = self.turns_html[-WINDOW:]
        hidden = len(self.turns_html) - len(window)
        head = (f'<div class="turn-h" style="margin:8px 12px;">'
                f'{hidden} earlier turn{"s" if hidden > 1 else ""} above</div>') if hidden else ""
        blocks = "".join(f'<div class="turn">{t}</div>' for t in window[:-1])
        last = window[-1] + live if window else ""
        self.slot.markdown(
            f'<div class="feed">{head}{blocks}<div class="turn">{last}</div></div>',
            unsafe_allow_html=True,
        )

    def event(self, kind, detail):
        if kind == "turn_start":
            self._flush()
            self.turns_html.append(f'<div class="turn-h">Turn {detail["turn"]}</div>')
            self.turns.metric("Turn", detail["turn"])
            self.paint(force=True)

        elif kind == "thinking_delta":
            self.mode = "think"
            self.buf += detail
            self.paint()

        elif kind == "tool_start":
            self._flush()
            self.turns_html[-1] += f'<div class="tool tool-ok">→ {html.escape(detail)}</div>'
            self.paint(force=True)

        elif kind == "tool_result":
            name = detail if isinstance(detail, str) else detail.get("name", "")
            if name.endswith("(error)"):
                self.turns_html[-1] += (
                    f'<div class="tool tool-err">! {html.escape(name)}</div>')
                self.paint(force=True)

        elif kind == "turn_end":
            self._flush()
            usage = detail["usage"]
            spent = usage.cost_usd()
            self.tok.metric("Output tokens", f"{usage.output_tokens:,}")
            self.cost.metric("Cost so far", f"${spent:.4f}")
            self.secs.metric("Elapsed", f"{time.perf_counter() - self.started:.0f}s")
            self.paint(force=True)

        elif kind == "stop":
            self._flush()
            self.paint(force=True)


if go and bug_text.strip():
    repo.reset()
    before = repo.test_status()

    st.write("")
    m1, m2, m3, m4 = st.columns(4)
    slots = (m1.empty(), m2.empty(), m3.empty(), m4.empty())
    slots[0].metric("Output tokens", "0")
    slots[1].metric("Cost so far", "$0.0000")
    slots[2].metric("Elapsed", "0s")
    slots[3].metric("Turn", "0")

    st.write("")
    st.markdown('<span class="label">Live agent feed</span>', unsafe_allow_html=True)
    feed_slot = st.empty()
    feed_slot.markdown('<div class="feed"><div class="turn">waiting for the first '
                       'token…</div></div>', unsafe_allow_html=True)

    feed = LiveFeed(feed_slot, slots, time.perf_counter())
    try:
        result = run_agent(
            client, effort=effort, bug_report=bug_text,
            max_tokens=max_tokens, max_iterations=max_iterations,
            show_thinking=show_thinking, on_event=feed.event,
        )
    except Exception as exc:  # noqa: BLE001
        st.error(f"Run failed: {type(exc).__name__} - {exc}")
        st.stop()

    after = repo.test_status()
    changed = repo.changed_files()
    fixed = after.all_passed and ROOT_CAUSE_FILE in changed

    st.write("")
    verdict = ("Root cause fixed, full suite green" if fixed
               else "Suite still failing" if not after.all_passed
               else "Suite passes but the shared helper was untouched")
    (st.success if fixed else st.warning)(
        f"{verdict}  ·  {before.summary}  →  {after.summary}  ·  "
        f"{len(result.tool_calls)} tool calls  ·  ${result.cost_usd:.4f}"
    )

    tabs = st.tabs(["Report", "Patch", "Verified by the app"])
    with tabs[0]:
        with st.container(border=True):
            r = result.report
            if r is None:
                st.error(f"No parsed report. {result.report_error}")
            else:
                st.markdown(f'<div class="summary">{html.escape(r.root_cause)}</div>',
                            unsafe_allow_html=True)
                st.write("")
                a, b = st.columns(2)
                a.markdown('<span class="label">Model status</span>', unsafe_allow_html=True)
                a.markdown(f"`{r.status}` at `{r.confidence}` confidence")
                b.markdown('<span class="label">Files changed</span>', unsafe_allow_html=True)
                b.markdown(" ".join(f'<span class="pill">{f}</span>' for f in r.files_changed)
                           or "none", unsafe_allow_html=True)
                st.markdown('<span class="label">Fix</span>', unsafe_allow_html=True)
                st.markdown(r.fix_summary or "_none reported_")

    with tabs[1]:
        diff = repo.diff_text()
        st.code(diff, language="diff") if diff.strip() else st.info("No file was changed.")

    with tabs[2]:
        st.markdown(
            f"- Tests before: `{before.summary}`\n"
            f"- Tests after: `{after.summary}`\n"
            f"- Shared helper touched: `{ROOT_CAUSE_FILE in changed}`\n"
            f"- Patch size: {repo.diff_line_count()} changed lines\n"
            f"- Stop reason: `{result.stop_reason}`  ·  turns: {result.iterations}\n"
            f"- Cache reads: {result.usage.cache_read_input_tokens:,} tokens"
        )
        st.caption("The report tab is what the model claimed. This tab is what the "
                   "application confirmed by rerunning pytest and reading git diff.")

    st.session_state.spend += result.cost_usd
    st.session_state.runs.append({
        "Effort": effort,
        "Fixed": "yes" if fixed else "no",
        "Turns": result.iterations,
        "Tool calls": len(result.tool_calls),
        "Output tokens": result.usage.output_tokens,
        "Seconds": round(result.elapsed_seconds, 1),
        "Cost ($)": round(result.cost_usd, 4),
    })
    spend_box.metric("Session spend", f"${st.session_state.spend:.4f}")

elif go:
    st.warning("Describe the bug first.")
elif not st.session_state.runs:
    st.write("")
    st.markdown(
        '<div class="hint">Pick an effort level and run it. Start at <b>low</b>, which '
        'takes about half a minute and costs roughly four cents, then run <b>xhigh</b> '
        'on the same bug and compare the two rows below.</div>',
        unsafe_allow_html=True,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Comparison
# ──────────────────────────────────────────────────────────────────────────────

if st.session_state.runs:
    st.write("")
    st.markdown("### Your runs")
    rows = st.session_state.runs
    st.dataframe(rows, width="stretch", hide_index=True)

    if len({r["Effort"] for r in rows}) > 1:
        chart = {r["Effort"]: r["Cost ($)"] for r in rows}
        st.bar_chart(chart, height=210, color="#D97757")
        cheap = min(rows, key=lambda r: r["Cost ($)"])
        dear = max(rows, key=lambda r: r["Cost ($)"])
        ratio = dear["Cost ($)"] / max(cheap["Cost ($)"], 1e-9)
        st.markdown(
            f"`{dear['Effort']}` cost **{ratio:.1f}x** what `{cheap['Effort']}` did. "
            f"Suite fixed: **{cheap['Effort']} {cheap['Fixed']}**, "
            f"**{dear['Effort']} {dear['Fixed']}**."
        )
