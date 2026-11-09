"""Streamlit UI for the COA Cache Simulator (docs/design.md).

The UI renders engine output verbatim — it never computes cache results
and never calls the engine except through bots.engine_client and the two
bots (rules.md 4). All results live in session state: widget interactions
alone never re-run the engine (rules.md 12).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import json  # noqa: E402

import streamlit as st  # noqa: E402
import streamlit.components.v1 as components_v1  # noqa: E402

from bots import engine_client  # noqa: E402
from bots.experiment_bot import run_experiment, save_report  # noqa: E402
from bots.trace_bot import generate  # noqa: E402
from ui import cache_scene, components, tokens  # noqa: E402

st.set_page_config(page_title="COA Cache Simulator",
                   page_icon="▦", layout="wide",
                   initial_sidebar_state="expanded")

_REPORTS_DIR = Path(__file__).resolve().parents[1] / "reports"
_TRACES_DIR = Path(__file__).resolve().parents[1] / "traces"

state = st.session_state
state.setdefault("trace", None)            # trace dict from Bot 1 or a sample
state.setdefault("trace_origin", "")
state.setdefault("sim_envelope", None)     # engine ok-envelope for the trace
state.setdefault("sim_error", None)
state.setdefault("experiment_record", None)
state.setdefault("experiment_error", None)
state.setdefault("report_path", None)
state.setdefault("workflow", None)         # per-step results of the workflow
state.setdefault("scene_reasons", [])      # why the 3D view is unavailable


# --- Sidebar: theme, then cache configuration (design.md 6.3) --------------------

with st.sidebar:
    theme = st.selectbox("Theme", ["Light", "Dark"], index=0,
                         key="cm_theme_select")
    components.inject_styles(theme.lower())
    colors = components.theme_colors(theme.lower())

    st.header("Cache configuration")
    organization = st.selectbox(
        "Organization",
        ["direct", "set_associative", "fully_associative"],
        index=1)

    capacity = st.selectbox(
        "Capacity (bytes, power of two)",
        tokens.CAPACITIES, index=tokens.CAPACITIES.index(8))

    block_size = st.selectbox(
        "Block size (bytes, power of two, 1–128)",
        tokens.BLOCK_SIZES, index=tokens.BLOCK_SIZES.index(2))

    associativity = None
    if organization == "set_associative":
        ways_available = capacity // block_size
        if ways_available < 2:
            st.caption("Block size too large for a two-way "
                       "set-associative cache.")
            associativity = None
        else:
            options = [2 ** e for e in range(1, 21)
                       if 2 ** e <= ways_available]
            associativity = st.selectbox(
                "Associativity (ways, power of two)", options)
    elif organization == "direct":
        st.caption("Direct-mapped: one line per set, no policy choice.")
    else:
        st.caption(f"Fully associative: all {capacity // block_size} "
                   "lines share one set.")

    width = st.number_input("Address width (bits, 4–64)",
                            min_value=tokens.ADDRESS_WIDTH_MIN,
                            max_value=tokens.ADDRESS_WIDTH_MAX,
                            value=16, step=1)

    policy = st.selectbox(
        "Replacement policy",
        ["LRU", "FIFO", "RANDOM"],
        disabled=(organization == "direct"),
        index=0)
    random_seed = None
    if organization != "direct" and policy == "RANDOM":
        random_seed = st.number_input(
            "Random seed", min_value=0, max_value=4294967295,
            value=12345, step=1)

    use_timing = st.toggle("Timing assumptions (AMAT)", value=True)
    hit_time = miss_penalty = None
    if use_timing:
        hit_time = st.number_input("Hit time (cycles, assumption)",
                                   min_value=0.0, value=1.0, step=0.5)
        miss_penalty = st.number_input("Miss penalty (cycles, assumption)",
                                       min_value=0.0, value=20.0, step=1.0)

    config = {
        "capacity_bytes": capacity,
        "block_size_bytes": block_size,
        "organization": organization,
        "address_width_bits": int(width),
    }
    if organization == "set_associative":
        config["associativity"] = associativity
    if organization != "direct":
        config["policy"] = policy
    if policy == "RANDOM" and organization != "direct":
        config["seed"] = int(random_seed)
    if use_timing:
        config["hit_time"] = float(hit_time)
        config["miss_penalty"] = float(miss_penalty)

    config_issues = components.validate_config_early(config)
    for message in config_issues:
        st.error(message)

config_valid = not config_issues
st.title("COA Cache Simulator")
st.caption("Read-only cache simulation with two automated bots — "
           "every number on screen comes from the C++ engine.")


# --- Session-state helpers -------------------------------------------------------

def invalidate_stale_results():
    """A new trace invalidates older simulation/experiment output (they
    belonged to the previous trace)."""
    state.trace = None
    state.sim_envelope = None
    state.sim_error = None
    state.experiment_record = None
    state.experiment_error = None
    state.report_path = None


# --- Tabs (design.md 2) -----------------------------------------------------------

tab_simulator, tab_experiments, tab_workflow, tab_help = st.tabs(
    ["Simulator", "Experiments", "Automated workflow", "Help"])

# --- Simulator tab -----------------------------------------------------------------

with tab_simulator:
    st.subheader("Trace")

    source = st.radio(
        "Trace source",
        ["Bot 1 generator", "Manual paste", "Sample file"],
        horizontal=True)

    with st.container(border=True):
        if source == "Bot 1 generator":
            pattern = st.selectbox(
                "Pattern", ["sequential", "repeated", "conflict"])
            if pattern == "sequential":
                start_address = st.number_input(
                    "Start address", min_value=0, value=0, step=1)
                count = st.number_input("Access count", min_value=0,
                                        value=32, step=1)
                stride = st.number_input("Byte stride", min_value=1,
                                         value=4, step=1)
                bot_params = {"start_address": int(start_address),
                              "count": int(count),
                              "stride_bytes": int(stride)}
            elif pattern == "repeated":
                address = st.number_input("Address", min_value=0,
                                          value=16, step=1)
                count = st.number_input("Repetitions", min_value=0,
                                        value=5, step=1)
                bot_params = {"address": int(address),
                              "count": int(count)}
            else:
                distinct_blocks = st.number_input(
                    "Distinct blocks (same set)", min_value=1, value=4,
                    step=1)
                passes = st.number_input("Passes", min_value=1, value=1,
                                         step=1)
                target_set = st.number_input("Target set", min_value=0,
                                             value=0, step=1)
                start_block = st.number_input("Start block", min_value=0,
                                              value=0, step=1)
                bot_params = {"distinct_blocks": int(distinct_blocks),
                              "passes": int(passes),
                              "target_set": int(target_set),
                              "start_block": int(start_block)}
            if st.button("Generate trace", disabled=not config_valid):
                response = generate(
                    {"pattern": pattern, "config": config,
                     "params": bot_params},
                    engine_client.fetch_geometry)
                if response["ok"]:
                    invalidate_stale_results()
                    state.trace = response["trace"]
                    state.trace_origin = "Bot 1 generator"
                else:
                    # Design.md 7: an error never blanks earlier results —
                    # the still-loaded trace stays visible above the card.
                    state.sim_error = response["error"]
        elif source == "Manual paste":
            text = st.text_area(
                "Addresses — one per line, decimal or 0x hex, # comments",
                value="", height=120)
            if st.button("Parse & load trace", disabled=not config_valid):
                response = generate(
                    {"pattern": "manual", "config": config,
                     "params": {"text": text}},
                    engine_client.fetch_geometry)
                if response["ok"]:
                    invalidate_stale_results()
                    state.trace = response["trace"]
                    state.trace_origin = "Manual paste"
                else:
                    state.sim_error = response["error"]
        else:
            samples = sorted(path.name for path in
                             _TRACES_DIR.glob("*.json"))
            sample = st.selectbox("Sample trace", samples)
            st.caption(f"Sample file: traces/{sample}")
            if st.button("Load sample"):
                # A malformed or hand-edited sample file must surface as an
                # error card (design.md 7), never a traceback — and it must
                # not discard the currently loaded trace.
                try:
                    data = json.loads(
                        (_TRACES_DIR / sample).read_text(encoding="utf-8"))
                    name = data["name"]
                    addresses = data["addresses"]
                    shape_ok = (isinstance(name, str) and bool(name)
                                and isinstance(addresses, list)
                                and all(isinstance(address, int)
                                        and not isinstance(address, bool)
                                        for address in addresses))
                except (json.JSONDecodeError, KeyError, TypeError,
                        OSError, UnicodeDecodeError) as err:
                    shape_ok = False
                    problem = f"{type(err).__name__}: {err}"
                else:
                    problem = ("name must be a non-empty string and "
                               "addresses a list of integers")
                if shape_ok:
                    invalidate_stale_results()
                    state.trace = {"name": name, "pattern": "sample",
                                   "params": {}, "addresses": addresses}
                    state.trace_origin = "Sample file"
                else:
                    state.sim_error = {
                        "code": "E_TRACE_INVALID",
                        "message": f"sample file traces/{sample} is not a "
                                   "valid trace file",
                        "details": [{"field": f"traces/{sample}",
                                     "problem": problem, "received": None}]}

    if state.trace is not None:
        components.render_trace_preview(state.trace, state.trace_origin)

    st.subheader("Simulation")

    if st.button("Run simulation", type="primary",
                 disabled=(state.trace is None or not config_valid)):
        with st.spinner("Running the engine…"):
            # The 3D view needs per-access snapshots; request them whenever
            # the run qualifies (trace ≤ 2,000 and within the serialization
            # budget — cache_scene.scene_unavailable_reasons mirrors the
            # engine's rules). Runs that do not qualify behave exactly as
            # before, without the option.
            trace_length = len(state.trace["addresses"])
            state.scene_reasons = cache_scene.scene_unavailable_reasons(
                config, trace_length)
            job = {"config": config,
                   "trace": {"name": state.trace["name"],
                             "addresses": state.trace["addresses"]}}
            if not state.scene_reasons:
                job["options"] = {"include_state_after_each": True}
            try:
                state.sim_envelope = engine_client.run_simulate(job)
                state.sim_error = None
            except engine_client.EngineError as err:
                state.sim_error = err.as_error_dict()

    if state.sim_error is not None:
        components.render_error_card(state.sim_error)

    envelope = state.sim_envelope
    if envelope is None:
        components.render_empty_card(
            "No simulation yet. Configure the cache, choose a trace, and "
            "run.", colors)
    else:
        summary = envelope["summary"]
        components.render_confirmation_line(summary, colors)
        components.render_metric_cards(summary)
        components.render_hit_rate_chart(envelope["events"], colors)
        with st.container(border=True):
            st.markdown("**Event log**")
            components.render_event_table(envelope["events"])
        with st.container(border=True):
            st.markdown("**Cache state**")
            components.render_state_grid(envelope["state"],
                                         envelope["events"], colors)

        # The Cache Machine — 3D view (post-delivery enhancement, V1)
        st.subheader("The Cache Machine — 3D view")
        if state.scene_reasons:
            components.render_empty_card(
                "3D view unavailable for this run: " +
                "; ".join(state.scene_reasons) +
                ". All results above remain fully available.", colors)
        else:
            built = cache_scene.build_html(envelope, theme.lower())
            if built.get("ok"):
                st.caption(
                    "The Cache Machine replays the engine's own events and "
                    "per-access snapshots. Drag to orbit, scroll to zoom. "
                    "If the view resets after a settings change, press Play "
                    "or use the scrubber to resume.")
                components_v1.html(built["html"], height=680)
            else:
                components.render_empty_card(
                    "3D view unavailable: " + built.get("reason", ""), colors)

# --- Experiments tab -----------------------------------------------------------------

with tab_experiments:
    st.subheader("Controlled experiments")
    if state.trace is None:
        components.render_empty_card(
            "No trace. Generate one with Bot 1, paste addresses, or load "
            "a sample in the Simulator tab — experiments run on the "
            "current trace.", colors)
    mode = st.radio(
        "Experiment mode",
        ["policy_comparison", "organization_comparison"],
        horizontal=True,
        captions=["LRU vs FIFO vs RANDOM (seed recorded) — one variable: "
                  "the policy",
                  "direct vs set-associative vs fully-associative — one "
                  "variable: the organization"])
    random_seed = None
    if mode == "policy_comparison":
        random_seed = st.number_input(
            "RANDOM seed", min_value=0, max_value=4294967295,
            value=12345, step=1, key="experiment_seed")
    if st.button("Run experiments", type="primary",
                 disabled=(state.trace is None or not config_valid)):
        with st.spinner("Running the experiment…"):
            request = {"mode": mode,
                       "trace": {"name": state.trace["name"],
                                 "addresses": state.trace["addresses"]},
                       "config": config}
            if mode == "policy_comparison":
                request["random_seed"] = int(random_seed)
            try:
                response = run_experiment(request,
                                          engine_client.run_simulate)
                if response["ok"]:
                    state.experiment_record = response["record"]
                    state.experiment_error = None
                    state.report_path = None
                else:
                    state.experiment_error = response["error"]
            except engine_client.EngineError as err:
                state.experiment_error = err.as_error_dict()

    if state.experiment_error is not None:
        components.render_error_card(state.experiment_error)

    record = state.experiment_record
    if record is None:
        components.render_empty_card(
            "No experiment yet. Choose a mode and run.", colors)
    else:
        label_key = "policy" if record["mode"] == "policy_comparison" \
            else "organization"
        components.render_comparison_table(record["runs"], label_key)
        components.render_comparison_chart(
            [run["policy"] if label_key == "policy"
             else run["config"]["organization"] for run in record["runs"]],
            [run["summary"] for run in record["runs"]], colors)
        with st.container(border=True):
            st.markdown("**Summary**")
            components.render_summary_text(record["summary_text"])
        saved = state.report_path
        if saved:
            st.caption(f"Report saved to {saved}")
        columns = st.columns(2)
        if columns[0].button("Save report", key="save_report"):
            # A save failure (including a conflicting-destination refusal,
            # D-30) must surface as an error card, never a traceback — and
            # must not discard the displayed record.
            try:
                state.report_path = save_report(record, _REPORTS_DIR)
            except OSError as err:
                state.experiment_error = {
                    "code": "E_INTERNAL",
                    "message": f"the report could not be saved: {err}",
                    "details": []}
            st.rerun()
        record_json = json.dumps(record, indent=2, sort_keys=True)
        columns[1].download_button("Download record (JSON)",
                                   record_json.encode("utf-8"),
                                   file_name=f"{record['experiment_id']}.json",
                                   mime="application/json")

# --- Automated workflow tab ------------------------------------------------------------

with tab_workflow:
    st.subheader("Automated workflow")
    st.caption("Bot 1 generates a conflict trace → the engine simulates it "
               "→ Bot 2 compares the replacement policies → the report is "
               "saved. Each step shows its status; a failing step stops "
               "the sequence and leaves earlier results visible.")

    columns = st.columns(3)
    conflict_blocks = columns[0].number_input(
        "Conflict blocks", min_value=1, value=4, step=1,
        key="workflow_blocks")
    passes = columns[1].number_input("Passes", min_value=1, value=1,
                                     step=1, key="workflow_passes")
    workflow_seed = columns[2].number_input(
        "RANDOM seed", min_value=0, max_value=4294967295, value=12345,
        step=1, key="workflow_seed")

    run_clicked = st.button("Run automated workflow", type="primary",
                            disabled=not config_valid)
    retry_clicked = (state.workflow or {}).get("failed_step") is not None \
        and st.button("Retry failed step", type="secondary")

    if run_clicked or retry_clicked:
        start_step = 1
        if retry_clicked:
            start_step = state.workflow["failed_step"]
        workflow = {"trace": state.workflow.get("trace") if retry_clicked
                    and start_step > 1 else None,
                    "sim_envelope": state.workflow.get("sim_envelope")
                    if retry_clicked and start_step > 2 else None,
                    "record": state.workflow.get("record")
                    if retry_clicked and start_step > 3 else None,
                    "failed_step": None,
                    "error": None}

        # Step 1: Bot 1.
        if start_step <= 1:
            with st.status("Bot 1 — Trace Generation", expanded=True) as box:
                st.write("Generating a conflict trace from the current "
                         "configuration…")
                response = generate(
                    {"pattern": "conflict", "config": config,
                     "params": {"distinct_blocks": int(conflict_blocks),
                                "passes": int(passes), "target_set": 0,
                                "start_block": 0}},
                    engine_client.fetch_geometry)
                if response["ok"]:
                    st.write(f"Generated {len(response['trace']['addresses'])} "
                             "addresses in one set.")
                    box.update(state="complete")
                    workflow["trace"] = {"name": response["trace"]["name"],
                                         "addresses": response["trace"]["addresses"]}
                else:
                    st.error(response["error"]["message"])
                    box.update(state="error")
                    workflow["failed_step"] = 1
                    workflow["error"] = response["error"]

        # Step 2: engine simulation.
        if workflow["failed_step"] is None and start_step <= 2:
            with st.status("Engine — Simulation", expanded=True) as box:
                st.write("Simulating the generated trace…")
                try:
                    envelope = engine_client.run_simulate(
                        {"config": config, "trace": workflow["trace"]})
                    box.update(state="complete")
                    st.write(f"{envelope['summary']['accesses']} accesses, "
                             f"{envelope['summary']['hits']} hits.")
                    workflow["sim_envelope"] = envelope
                except engine_client.EngineError as err:
                    st.error(err.message)
                    box.update(state="error")
                    workflow["failed_step"] = 2
                    workflow["error"] = err.as_error_dict()

        # Step 3: Bot 2 policy comparison.
        if workflow["failed_step"] is None and start_step <= 3:
            with st.status("Bot 2 — Policy Comparison", expanded=True) as box:
                st.write("Comparing LRU / FIFO / RANDOM on the trace…")
                request = {"mode": "policy_comparison",
                           "trace": workflow["trace"],
                           "config": config,
                           "random_seed": int(workflow_seed)}
                response = run_experiment(request, engine_client.run_simulate)
                if response["ok"]:
                    box.update(state="complete")
                    st.write("Experiment complete.")
                    workflow["record"] = response["record"]
                else:
                    st.error(response["error"]["message"])
                    box.update(state="error")
                    workflow["failed_step"] = 3
                    workflow["error"] = response["error"]

        # Step 4: report.
        if workflow["failed_step"] is None and workflow.get("record"):
            # A report-save failure must fail the step like any other —
            # losing steps 1-3 results here would wipe successful output.
            try:
                workflow["report_path"] = str(save_report(
                    workflow["record"], _REPORTS_DIR))
            except OSError as err:
                workflow["failed_step"] = 4
                workflow["error"] = {
                    "code": "E_INTERNAL",
                    "message": f"the report could not be saved: {err}",
                    "details": []}
        state.workflow = workflow

    # Persisted step statuses (IDLE/RUNNING/DONE/FAILED pills; design.md 6.5).
    workflow = state.workflow or {}
    step_states = {
        1: ("Trace generation", "done" if workflow.get("trace")
            else "failed" if workflow.get("failed_step") == 1 else "idle",
            (workflow.get("trace") or {}).get("name",
             (workflow.get("error") or {}).get("message", "")
             if workflow.get("failed_step") == 1 else "")),
        2: ("Engine simulation", "done" if workflow.get("sim_envelope")
            else "failed" if workflow.get("failed_step") == 2 else "idle",
            (f"{workflow['sim_envelope']['summary']['accesses']} accesses, "
             f"{workflow['sim_envelope']['summary']['hits']} hits")
            if workflow.get("sim_envelope") else ""),
        3: ("Policy comparison", "done" if workflow.get("record")
            else "failed" if workflow.get("failed_step") == 3 else "idle",
            "experiment complete" if workflow.get("record") else ""),
        4: ("Report", "done" if workflow.get("report_path")
            else "failed" if workflow.get("failed_step") == 4 else "idle",
            (workflow.get("report_path") or "")),
    }
    for _, (name, step_state, message) in step_states.items():
        st.markdown(components.status_pill_html(step_state, name, message),
                    unsafe_allow_html=True)

    if workflow.get("error"):
        components.render_error_card(workflow["error"])

    sim_envelope = workflow.get("sim_envelope")
    if sim_envelope:
        st.markdown("**Workflow simulation result**")
        components.render_metric_cards(sim_envelope["summary"])
    record = workflow.get("record")
    if record:
        components.render_comparison_table(record["runs"], "policy")
        components.render_summary_text(record["summary_text"])
        saved = workflow.get("report_path")
        if saved:
            st.caption(f"Report saved to {saved}")
        record_json = json.dumps(record, indent=2, sort_keys=True)
        st.download_button("Download workflow report (JSON)",
                           record_json.encode("utf-8"),
                           file_name=f"{record['experiment_id']}.json",
                           mime="application/json")
    if not workflow:
        components.render_empty_card(
            "No workflow run yet. Press “Run automated workflow” to start.", colors)

# --- Help tab ----------------------------------------------------------------------------

with tab_help:
    st.subheader("Concepts")
    with st.container(border=True):
        st.markdown(
            "**Organizations.** *Direct-mapped*: every block maps to "
            "exactly one line — no replacement policy to choose. "
            "*Set-associative*: each set holds N lines (the "
            "associativity). *Fully associative*: one set holds every "
            "line; the index field is zero bits wide.")
        st.markdown(
            "**Replacement policies.** *LRU* evicts the least recently "
            "used line (hits refresh recency). *FIFO* evicts the oldest "
            "inserted line (hits never reorder). *RANDOM* evicts a line "
            "chosen by a seeded generator — identical seed, trace, and "
            "engine version always reproduce the same result. An invalid "
            "line is always filled before a valid line is evicted.")
    with st.container(border=True):
        st.markdown("**Metrics.** Hit rate = hits ÷ accesses. Miss rate = "
                    "misses ÷ accesses. "
                    "AMAT = hit time + miss rate × miss penalty. "
                    "Hit time and miss penalty are modeling assumptions "
                    "in clock cycles, not measured hardware latency.")
    with st.container(border=True):
        st.markdown("**Limits.** Traces: 0–100,000 addresses. Address "
                    "width: 4–64 bits. Block size: power of two, 1–128 B. "
                    "Capacity: power of two, at most 1,048,576 B. "
                    "Associativity: power of two, 2 up to "
                    "capacity ÷ block size. Per-access state snapshots: "
                    "traces up to 2,000 addresses.")
    with st.container(border=True):
        st.markdown("**Reading the views.** The metric cards and tables "
                    "show the engine's own numbers. The event log has one "
                    "row per access with the engine's plain-language "
                    "explanation. The cache-state grid shows the final "
                    "contents (tag · block per way); the highlighted cell "
                    "is the most recently used line. The cumulative "
                    "hit-rate chart is computed from the engine's event "
                    "log for display.")
    with st.container(border=True):
        st.markdown("**Sample traces.** Bundled under `traces/`: "
                    "e1-repeated (one block, five accesses), e2-conflict "
                    "(direct-mapped thrashing), e3-lru-vs-fifo (the "
                    "controlled demonstration where LRU and FIFO "
                    "differ), and sequential-100 (a streaming access). "
                    "Load them from the Simulator tab.")
