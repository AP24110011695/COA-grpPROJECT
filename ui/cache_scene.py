"""The Cache Machine — 3D view builder (post-delivery enhancement).

Builds a self-contained HTML animation from an engine result envelope that
was captured with ``options.include_state_after_each``. The builder copies
engine-reported fields verbatim into a JSON payload; it never computes
cache behavior.

Stage limits (mirroring docs/architecture.md §12 and the V1 design):
- traces > 2,000 accesses: per-access snapshots are refused by the engine
  (E_LIMIT), so the 3D view is disabled with a caption;
- snapshots × total cache lines must stay ≤ 2,000,000 (engine budget);
- the 3D stage itself supports at most 512 cache lines, 128 sets and
  64 ways per set — larger caches keep the 2D views.

The generated HTML is deterministic for a given envelope (sorted JSON
keys, no timestamps), which keeps the embedded iframe stable across
Streamlit reruns when the simulation results are unchanged.
"""

import json
from pathlib import Path

_STAGE_MAX_LINES = 512
_STAGE_MAX_SETS = 128
_STAGE_MAX_WAYS = 64
_TRACE_MAX = 2000           # engine per-access snapshot cap
_SNAPSHOT_BUDGET = 2_000_000  # snapshots × total cache lines
_WALL_MAX_SLABS = 128       # memory-wall slabs drawn (rest covered by labels)

_THREE_MIN = Path(__file__).parent / "static" / "three.min.js"
_SCENE_JS = Path(__file__).parent / "scene_app.js"
_SCENE_CSS = Path(__file__).parent / "scene.css"
_SCENE_DARK_CSS = Path(__file__).parent / "scene_dark.css"

def snapshot_limits(lines):
    """Per-trace snapshot limits for `lines` total cache lines (mirror of
    the engine/UI rules in docs/architecture.md §12)."""
    return {"max_trace": _TRACE_MAX,
            "max_line_states": _SNAPSHOT_BUDGET // max(lines, 1)}


def scene_unavailable_reasons(config, trace_length):
    """Returns a list of reasons why the 3D view cannot be offered for a
    run with `config` over `trace_length` accesses (empty list = available)."""
    lines = config["capacity_bytes"] // config["block_size_bytes"]
    reasons = []
    if trace_length > _TRACE_MAX:
        reasons.append(
            f"the trace has {trace_length} accesses; per-access snapshots are "
            f"capped at {_TRACE_MAX} (docs/architecture.md §12)")
    if lines > _STAGE_MAX_LINES:
        reasons.append(
            f"the cache has {lines} lines; the 3D stage supports at most "
            f"{_STAGE_MAX_LINES} lines per scene")
    if trace_length * lines > _SNAPSHOT_BUDGET:
        reasons.append(
            f"per-access snapshots would need {trace_length * lines} line "
            f"states (budget {_SNAPSHOT_BUDGET})")
    organization = config["organization"]
    if organization == "direct":
        sets, ways = lines, 1
    elif organization == "fully_associative":
        sets, ways = 1, lines
    else:
        sets = lines // config.get("associativity") or lines
        ways = lines // sets if sets else lines
    if sets > _STAGE_MAX_SETS:
        reasons.append(f"the cache has {sets} sets; the 3D stage supports at "
                       f"most {_STAGE_MAX_SETS}")
    if ways > _STAGE_MAX_WAYS:
        reasons.append(f"each set has {ways} ways; the 3D stage supports at "
                       f"most {_STAGE_MAX_WAYS} ways per set")
    return reasons


def build_payload(envelope):
    """Maps the engine envelope to the animation payload (verbatim field
    copies; no cache logic). Returns {"ok": True, "payload": ...} or
    {"ok": False, "reason": ...}."""
    geometry = envelope["geometry"]
    events = envelope["events"]
    state = envelope.get("state") or {}
    snapshots = state.get("snapshots")
    if snapshots is None:
        return {"ok": False, "reason":
                "per-access snapshots were not captured for this run. Run the "
                "simulation again from the Simulator tab — the 3D view captures "
                "them automatically for supported traces."}
    if len(snapshots) != len(events):
        # The engine emits one snapshot per access (architecture.md 6.7); a
        # disagreement means a malformed envelope, and replaying it would
        # desynchronize the scene from the real accesses.
        return {"ok": False, "reason":
                f"the run's {len(snapshots)} snapshots do not match its "
                f"{len(events)} events; the 3D view refuses inconsistent "
                "engine data."}

    events_out = []
    for event in events:
        meta = event.get("policy_meta") or {}
        index = event.get("index")
        events_out.append({
            "n": event["n"],
            "address": event["address"],
            "block": event["block"],
            "tag": event["tag"],
            "index": index,
            "hasIndex": index is not None,
            "offset": event["offset"],
            "set": event["set"],
            "way": event["way"],
            "result": event["result"],
            "loaded": event["loaded"],
            "evicted": event["evicted"],
            "policy": meta.get("policy"),
            "victimSelection": meta.get("victim_selection"),
            "seed": meta.get("seed"),
            "explanation": event["explanation"],
        })

    memory_blocks = sorted({event["block"] for event in events})
    wall_slabs = memory_blocks[:_WALL_MAX_SLABS]
    summary = envelope["summary"]

    payload = {
        "geometry": {
            "sets": geometry["sets"],
            "waysPerSet": geometry["lines"] // geometry["sets"],
            "lines": geometry["lines"],
            "organization": geometry["organization"],
            "offsetBits": geometry["offset_bits"],
            "indexBits": geometry["index_bits"],
            "tagBits": geometry["tag_bits"],
            "blockSizeBytes": geometry["block_size_bytes"],
            "addressWidthBits": geometry["address_width_bits"],
        },
        "events": events_out,
        "snapshots": [{"n": snap["n"], "sets": snap["sets"]}
                      for snap in snapshots],
        "summary": {"accesses": summary["accesses"],
                    "hits": summary["hits"],
                    "misses": summary["misses"],
                    "evictions": summary["evictions"]},
        "memory": {"blocks": wall_slabs,
                   "truncated": len(memory_blocks) > len(wall_slabs),
                   "blockSizeBytes": geometry["block_size_bytes"]},
    }
    return {"ok": True, "payload": payload}


def build_html(envelope, theme="light"):
    """Builds the self-contained 3D-view HTML for `envelope`. Deterministic:
    the same envelope and theme always produce the same HTML string. The
    theme travels as presentation-only metadata (`payload["theme"]`) and
    selects the themed scene assets — simulation fields are identical in
    both themes."""
    result = build_payload(envelope)
    if not result.get("ok"):
        return result
    payload = result["payload"]
    payload["theme"] = (theme or "light").lower()
    payload_json = json.dumps(payload, sort_keys=True).replace(
        "</", "<\\/")  # keep </script> inside the JSON from closing the tag
    scene_css = _SCENE_CSS.read_text(encoding="utf-8")
    if payload["theme"] == "dark":
        scene_css += "\n" + _SCENE_DARK_CSS.read_text(encoding="utf-8")
    html = (
        "<!DOCTYPE html><html><head><meta charset='utf-8'><style>"
        + scene_css
        + "</style></head><body>"
        + _OVERLAY_HTML
        + "<div id='cm-stage'></div>"
        + "<script>" + _THREE_MIN.read_text(encoding="utf-8") + "</script>"
        + "<script>window.CACHE_PAYLOAD = " + payload_json + ";</script>"
        + "<script>" + _SCENE_JS.read_text(encoding="utf-8") + "</script>"
        + "</body></html>")
    return {"ok": True, "html": html}


_OVERLAY_HTML = (
    "<div class='cm-controls'>"
    "<button id='cm-play' title='Play'>▶</button>"
    "<button id='cm-pause' title='Pause'>⏸</button>"
    "<button id='cm-prev' title='Previous access'>◀</button>"
    "<button id='cm-next' title='Next access'>▶|</button>"
    "<button id='cm-replay' title='Replay'>↺</button>"
    "<button id='cm-reset' title='Reset'>⏮</button>"
    "<select id='cm-speed' title='Playback speed'>"
    "<option value='0.5'>0.5×</option>"
    "<option value='1' selected>1×</option>"
    "<option value='2'>2×</option>"
    "<option value='4'>4×</option>"
    "</select>"
    "<input id='cm-scrub' type='range' min='0' value='0' step='1'/>"
    "<span id='cm-progress'></span>"
    "</div>"
    "<div class='cm-info' id='cm-info'></div>"
    "<div class='cm-counters' id='cm-counters'></div>"
    "<div class='cm-log' id='cm-log'></div>")
