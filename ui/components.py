"""Reusable rendering components for the Streamlit UI (docs/design.md).

Everything here renders engine output verbatim (formatting aside) — no
cache logic, no invented numbers. Charts use the tokens from ui.tokens so
CSS and matplotlib never drift.
"""

from pathlib import Path
from types import SimpleNamespace

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from ui import tokens  # noqa: E402

_STYLES_PATH = Path(__file__).parent / "styles.css"
_STYLES_DARK_PATH = Path(__file__).parent / "styles_dark.css"


def theme_colors(theme="light"):
    """Color namespace for the active theme ("light"/"dark"). Falls back to
    the delivered Light palette for unknown values."""
    return SimpleNamespace(**tokens.get_tokens(theme))


def inject_styles(theme="light"):
    """Injects the base stylesheet plus the theme bundle ("light" = the
    delivered appearance, unchanged; "dark" = the palette and Streamlit
    chrome overrides from ui/styles_dark.css). Presentation only.
    Returns the combined CSS (test-friendly)."""
    css = _STYLES_PATH.read_text(encoding="utf-8")
    if theme == "dark":
        css += "\n" + _STYLES_DARK_PATH.read_text(encoding="utf-8")
    st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
    return css


def validate_config_early(config):
    """Thin UI-side mirror of the engine's validation for fast feedback
    (prd.md 9): the selects make most invalid input untypable, this catches
    the cross-field rules. The engine re-validates authoritatively and the
    two never disagree — same numbers, derived the same pow2 way."""
    issues = []
    capacity = config["capacity_bytes"]
    block = config["block_size_bytes"]
    width = config["address_width_bits"]
    organization = config["organization"]
    if block > capacity:
        issues.append(f"block_size_bytes ({block}) must not exceed "
                      f"capacity_bytes ({capacity}).")
    sets = capacity // block
    if organization == "set_associative":
        associativity = config.get("associativity")
        if associativity is None:
            issues.append("associativity is required for a set-associative "
                          "cache.")
        elif associativity > capacity // block:
            issues.append(f"associativity ({associativity}) must not "
                          f"exceed capacity_bytes / block_size_bytes "
                          f"({capacity // block}).")
        else:
            sets = capacity // (block * associativity)
    offset_bits = block.bit_length() - 1
    index_bits = sets.bit_length() - 1
    if width < offset_bits + index_bits:
        issues.append(f"address_width_bits ({width}) is too small: the "
                      f"geometry needs {offset_bits} offset bits + "
                      f"{index_bits} index bits, leaving no bits for the "
                      f"tag.")
    return issues


def status_pill_html(state, timestamp=None, message=None):
    """One IDLE/RUNNING/DONE/FAILED pill line (design.md 6.5)."""
    colors = {"idle": "pill-idle", "running": "pill-running",
              "done": "pill-done", "failed": "pill-failed"}
    css_class = colors.get(state, "pill-idle")
    parts = [f'<span class="pill {css_class}">{state.upper()}</span>']
    if timestamp:
        parts.append(f'<span class="pill-timestamp">{timestamp}</span>')
    if message:
        parts.append(f'<span class="pill-message"> — {message}</span>')
    return f'<div class="pill-line">{"".join(parts)}</div>'


def render_error_card(error):
    """First-class error card (design.md 7): code, message, and every
    validation detail — the actionable text lives in details[].problem."""
    lines = [f"**{error.get('code', 'E_INTERNAL')}** — "
             f"{error.get('message', 'the operation failed')}"]
    for detail in error.get("details", []):
        received = detail.get("received")
        received_text = (f" (received: {received!r})"
                         if received is not None else "")
        lines.append(f"- `{detail.get('field', '')}`: "
                     f"{detail.get('problem', '')}{received_text}")
    st.error("\n".join(lines))


def render_empty_card(message, colors=None):
    """Empty state: says what unlocks it (design.md 7)."""
    colors = colors or theme_colors("light")
    with st.container(border=True):
        st.markdown(f"<span style='color:{colors.TEXT_SECONDARY}; "
                    f"font-size:14px'>{message}</span>",
                    unsafe_allow_html=True)


def render_metric_cards(summary):
    """One row of compact stat blocks (design.md 6.6); rates as 2-decimal
    percents, AMAT in cycles, and an em-dash when a value does not exist."""
    accesses = summary["accesses"]
    hit_rate = summary["hit_rate"]
    miss_rate = summary["miss_rate"]
    amat = summary.get("amat")
    columns = st.columns([1, 1, 1, 1, 1, 1, 1.4])
    values = [
        ("Accesses", f"{accesses}"),
        ("Hits", f"{summary['hits']}"),
        ("Misses", f"{summary['misses']}"),
        ("Evictions", f"{summary['evictions']}"),
        ("Hit rate", "—" if hit_rate is None else f"{hit_rate * 100:.2f}%"),
        ("Miss rate", "—" if miss_rate is None else f"{miss_rate * 100:.2f}%"),
        ("AMAT (cycles)", "—" if not amat else f"{amat['value']:.2f}"),
    ]
    for column, (label, value) in zip(columns, values):
        column.metric(label, value)


def render_confirmation_line(summary, colors=None):
    colors = colors or theme_colors("light")
    hits = summary["hits"]
    rate = summary["hit_rate"]
    if summary["accesses"] == 0:
        st.markdown(f"<span style='color:{colors.SUCCESS}; font-size:14px'>"
                    "Simulation complete — empty trace (0 accesses)."
                    f"</span>", unsafe_allow_html=True)
        return
    def plural(count, singular, plural_form=None):
        if count == 1:
            return f"{count} {singular}"
        return f"{count} {plural_form or singular + 's'}"

    st.markdown(
        f"<span style='color:{colors.SUCCESS}; font-size:14px'>"
        f"Simulation complete — {plural(summary['accesses'], 'access', 'accesses')}, "
        f"{plural(hits, 'hit')} ({rate * 100:.2f}%)."
        f"</span>", unsafe_allow_html=True)


def render_trace_preview(trace, origin_label):
    """Monospaced preview: first 32 addresses, then the count (design.md 6.8)."""
    addresses = trace["addresses"]
    shown = addresses[:32]
    body = ", ".join(str(address) for address in shown)
    if len(addresses) > 32:
        body += f", … {len(addresses) - 32} more"
    st.markdown(
        f"**{trace['name']}** · {origin_label} · {len(addresses)} addresses")
    st.markdown(f"<div class='trace-preview'>{body}</div>",
                unsafe_allow_html=True)
    if trace.get("warnings"):
        for warning in trace["warnings"]:
            st.warning(warning)


def render_event_table(events):
    """Interactive event table, at most 500 rows on screen, full CSV
    download always available (design.md 6.4)."""
    rows = []
    for event in events:
        evicted = event["evicted"]
        rows.append({
            "n": event["n"],
            "address": event["address"],
            "block": event["block"],
            "tag": event["tag"],
            "index": "—" if event["index"] is None else event["index"],
            "offset": event["offset"],
            "set": event["set"],
            "way": event["way"],
            "result": event["result"],
            "evicted block": ("—" if evicted is None
                              else evicted["block"]),
            "explanation": event["explanation"],
        })
    frame = pd.DataFrame(rows)
    # rules.md 12: show the LATEST ~500 events on screen (the most recent
    # accesses are the interesting ones); the download always has everything.
    st.dataframe(frame.tail(tokens.EVENT_TABLE_ROWS), hide_index=True,
                 width="stretch")
    if len(frame) > tokens.EVENT_TABLE_ROWS:
        st.caption(f"Showing the most recent {tokens.EVENT_TABLE_ROWS} rows; "
                   "download for the full log.")
    csv = frame.to_csv(index=False).encode("utf-8")
    st.download_button("Download all events (CSV)", csv,
                       file_name="cache-events.csv", mime="text/csv")


def render_state_grid(state, events, colors=None):
    """Cache-state grid: rows = sets, columns = ways; valid lines tinted,
    the most-recently-used line highlighted, and the engine's own
    explanation of the last access as the caption (design.md 6.4)."""
    colors = colors or theme_colors("light")
    columns = max((len(ways) for ways in state["sets"]), default=0)
    grid = []
    styles = []
    for set_number, ways in enumerate(state["sets"]):
        grid_row = {"Set": f"Set {set_number}"}
        # The style frame must carry the SAME index labels as the data
        # frame for Styler.apply to align (the values are the CSS).
        style_row = {"Set": f"Set {set_number}"}
        for way in range(columns):
            column = f"Way {way}"
            if way < len(ways) and ways[way]["valid"]:
                line = ways[way]
                grid_row[column] = f"tag {line['tag']} · blk {line['block']}"
                if line.get("last_used_rank") == 1:
                    style_row[column] = (f"background-color: "
                                         f"{colors.SUCCESS_SOFT};")
                else:
                    style_row[column] = (f"background-color: "
                                         f"{colors.ACCENT_SOFT};")
            else:
                grid_row[column] = "—"
                style_row[column] = ""
        grid.append(grid_row)
        styles.append(style_row)
    frame = pd.DataFrame(grid)
    if frame.empty:
        st.caption("The cache is empty.")
        return
    frame = frame.set_index("Set")
    style_frame = pd.DataFrame(styles).set_index("Set")
    styled = frame.style.apply(
        lambda _column: style_frame, axis=None)
    st.dataframe(styled, hide_index=True, width="stretch")
    if events:
        st.caption(f"Last access: {events[-1]['explanation']}")


def render_hit_rate_chart(events, colors=None):
    """Cumulative hit rate over the access number (design.md 6.7)."""
    colors = colors or theme_colors("light")
    if not events:
        return
    access_numbers = []
    rates = []
    hits = 0
    total = 0
    for event in events:
        total += 1
        hits += 1 if event["result"] == "hit" else 0
        access_numbers.append(event["n"])
        rates.append(hits / total)
    figure, axis = plt.subplots(figsize=(6.4, 2.6), dpi=150)
    figure.patch.set_alpha(0)
    axis.set_facecolor("none")
    axis.plot(access_numbers, rates, color=colors.ACCENT, linewidth=1.5)
    axis.axhline(0.5, color=colors.BORDER, linestyle="--", linewidth=0.8)
    axis.set_ylim(0, 1)
    axis.set_xlabel("Access number")
    axis.set_ylabel("Cumulative hit rate")
    axis.set_title("Cumulative hit rate", fontsize=10, loc="left")
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    axis.spines["bottom"].set_color(colors.BORDER)
    axis.spines["left"].set_color(colors.BORDER)
    axis.tick_params(labelsize=8, colors=colors.TEXT_SECONDARY)
    axis.xaxis.label.set_color(colors.TEXT_SECONDARY)
    axis.yaxis.label.set_color(colors.TEXT_SECONDARY)
    axis.title.set_color(colors.TEXT)
    axis.grid(axis="y", color=colors.BORDER, linewidth=0.5)
    st.pyplot(figure)
    plt.close(figure)


def render_comparison_chart(labels, summaries, colors=None):
    """Grouped bars: hits / misses / evictions per run (design.md 6.7)."""
    colors = colors or theme_colors("light")
    count = len(labels)
    import numpy as np
    x = np.arange(count)
    width = 0.25
    figure, axis = plt.subplots(figsize=(6.4, 3.0), dpi=150)
    figure.patch.set_alpha(0)
    axis.set_facecolor("none")
    for offset, (series, color) in enumerate([
            ("hits", colors.CHART_HITS),
            ("misses", colors.CHART_MISSES),
            ("evictions", colors.CHART_EVICTIONS)]):
        values = [summary[series] for summary in summaries]
        bars = axis.bar(x + (offset - 1) * width, values, width,
                        label=series.capitalize(), color=color)
        axis.bar_label(bars, fontsize=7, padding=1, color=colors.TEXT)
    axis.set_xticks(x, labels, fontsize=8)
    axis.set_ylabel("Count")
    axis.set_title("Hits / misses / evictions per run", fontsize=10,
                   loc="left")
    axis.legend(loc="upper left", ncols=3, frameon=False, fontsize=8)
    axis.spines["top"].set_visible(False)
    axis.spines["right"].set_visible(False)
    axis.spines["bottom"].set_color(colors.BORDER)
    axis.spines["left"].set_color(colors.BORDER)
    axis.tick_params(labelsize=8, colors=colors.TEXT_SECONDARY)
    axis.yaxis.label.set_color(colors.TEXT_SECONDARY)
    axis.title.set_color(colors.TEXT)
    axis.grid(axis="y", color=colors.BORDER, linewidth=0.5)
    st.pyplot(figure)
    plt.close(figure)


def render_comparison_table(runs, label_key):
    """Static comparison table (design.md 6.4): one row per run with the
    best hit rate bolded (never scrollable, never color-only)."""
    rows = []
    best_rate = max(run["summary"]["hit_rate"] for run in runs)
    for run in runs:
        summary = run["summary"]
        label = run["policy"] if label_key == "policy" \
            else run["config"]["organization"]
        seed = run["seed"]
        amat = summary.get("amat")
        is_best = abs(summary["hit_rate"] - best_rate) <= 1e-12
        rate_html = (f"<b>{summary['hit_rate'] * 100:.2f}%</b>"
                     if is_best else f"{summary['hit_rate'] * 100:.2f}%")
        rows.append({
            "Run": run["run_id"],
            "Policy" if label_key == "policy" else "Organization": label,
            "Seed": "—" if seed is None else seed,
            "Hits": summary["hits"],
            "Misses": summary["misses"],
            "Evictions": summary["evictions"],
            "Hit rate": rate_html,
            "AMAT (cycles)": "—" if not amat else f"{amat['value']:.2f}",
        })
    frame = pd.DataFrame(rows)
    st.markdown(frame.to_html(escape=False, index=False),
                unsafe_allow_html=True)


def render_summary_text(text):
    st.markdown(f"<div class='summary-text'>{text}</div>",
                unsafe_allow_html=True)
