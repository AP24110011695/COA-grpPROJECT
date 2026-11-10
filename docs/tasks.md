# tasks.md — Ten-phase implementation plan

> Execute phases strictly in order via `Execute Phase N`. A phase is DONE only
> when its acceptance criteria have actually passed (evidence recorded in
> `memory.md`). Statuses: `NOT STARTED` | `IN PROGRESS` | `BLOCKED` | `DONE`.

---

## Phase 1 — Repository foundation and interface contracts

**Status:** `DONE` (2026-10-24 — all five acceptance criteria passed, and
re-verified after the D-14–D-16 documentation corrections; latest run:
zero-warning rebuild, engine tests 2 checks / 0 failures, pytest 21 passed.
Evidence: `memory.md` §7–§8; decisions D-11…D-16)

- **Objective:** Establish the minimal project structure, canonical schemas,
  and a runnable build + test workflow — no simulation behavior yet beyond an
  engine that identifies itself.
- **Prerequisites:** None (greenfield repo; verified environment in
  `memory.md`).
- **Scope:** Directory skeleton; vendored JSON header; engine Makefile;
  `cache_sim` with `version` mode only; schema files; Python requirements;
  pytest smoke test; README stub. Excluded: any cache logic (Phase 2+).
- **Files:** `engine/Makefile`, `engine/src/main.cpp`, `engine/include/version.hpp`,
  `engine/third_party/nlohmann/json.hpp` (vendored),
  `schemas/{config,trace,job,geometry,event,summary,state,experiment}.schema.json`,
  `requirements.txt`, `requirements-dev.txt`, `tests/test_smoke.py`,
  `traces/` (empty placeholder), `README.md` (stub), bots/ui package stubs
  (`bots/__init__.py`, `ui/` empty).
- **Ordered tasks:**
  1. Create the directory tree of `architecture.md` §15.
  2. Download and vendor nlohmann/json single header into
     `engine/third_party/nlohmann/` (network verified available); record its
     version in `memory.md`.
  3. Write `engine/src/main.cpp`: argument parsing (`--mode`, `--in`, `--out`),
     `version` mode emitting the §6.2 envelope, `geometry`/`simulate` stubs
     returning `E_INTERNAL` "not implemented until Phase 2/3" (explicit, not
     silent), usage errors → exit 2.
  4. Write `engine/Makefile` (mingw32-make): `all`, `test`, `clean` targets
     per `architecture.md` §4.
  5. Write the eight JSON Schema files (draft-07) from `architecture.md` §6.
  6. Write `requirements.txt` (streamlit, matplotlib, pandas) +
     `requirements-dev.txt` (pytest, jsonschema); `pip install -r` both
     (installs streamlit; completed 2026-10-24).
  7. Write `tests/test_smoke.py`: builds nothing itself; asserts
     `build/cache_sim.exe --mode version` returns exit 0 and parses to the
     expected envelope (skipped with a clear message if the exe is absent).
  8. README stub: project one-liner, governing docs list, verified env.
- **Validation/tests:** `mingw32-make -C engine` builds with zero warnings;
  `build/cache_sim.exe --mode version` exits 0 with the envelope;
  `python -m pytest tests -q` passes (1 passed or documented skip);
  `python -c "import streamlit"` succeeds.
- **Acceptance criteria:**
  - AC-P1 `mingw32-make -C engine all` produces `build/cache_sim.exe` with zero
    compiler warnings.
  - AC-P2 `cache_sim --mode version` output parses as JSON and matches §6.2
    exactly (`ok`, `engine.name = "cache_sim"`, `engine.version = "0.1.0"`).
  - AC-P3 Unknown flag / missing mode → exit 2 with an `E_USAGE` envelope.
  - AC-P4 All eight schema files exist and each validates at least one
    concrete example document in a pytest check.
  - AC-P5 `python -m pytest tests -q` green; `import streamlit` works.
- **Definition of Done:** all AC-P pass with commands + results recorded in
  `memory.md`; tree matches §15; no cache logic present.

## Phase 2 — Configuration validation and address decomposition

**Status:** `DONE` (2026-10-24 — all four acceptance criteria passed; latest
run: zero-warning clean rebuild, engine tests 154 checks / 0 failures, pytest
30 passed / 2 warnings. Evidence: `memory.md` §7–§8; contract tightening
recorded as decision D-17)

- **Objective:** The engine authoritatively validates configurations and
  reports derived geometry — the foundation every later phase trusts.
- **Prerequisites:** Phase 1 DONE.
- **Scope:** `geometry` mode complete; validation with all problems collected;
  integer-safe bit-width derivation. Excluded: simulation, events, stats.
- **Files:** `engine/include/{config.hpp,geometry.hpp}`, `engine/src/{config.cpp,geometry.cpp}`,
  `engine/tests/engine_tests.cpp` (validation + geometry sections).
- **Ordered tasks:**
  1. Implement config parsing + full validation per `prd.md` §5 and
     `architecture.md` §12 (every rule, all problems collected into `details`).
  2. Implement geometry derivation per `architecture.md` §7 (shift-count bit
     widths, `tag_bits < 0` rejection, fully-associative `index_bits = 0`).
  3. Wire `geometry` mode: valid → geometry envelope; invalid → `E_CONFIG_INVALID`
     envelope, exit 3.
  4. Write engine tests: valid configs for all three organizations; each
     validation rule violated once (assert field/problem/received); boundary
     configs (block 1; capacity = block; assoc = capacity/block; width 4 and
     64; capacity 2²⁰); power-of-two checks; geometry numbers hand-computed
     for E1–E4 configs.
- **Validation/tests:** `mingw32-make -C engine test` green.
- **Acceptance criteria:**
  - AC-P2.1 Every rule in `prd.md` §5 has a passing test with a hand-written
    expectation.
  - AC-P2.2 E1–E4 geometries match the published numbers exactly (sets, lines,
    offset/index/tag bits, max_address).
  - AC-P2.3 Invalid config → exit 3, `E_CONFIG_INVALID`, details listing every
    violated field; nothing is clamped or defaulted.
  - AC-P2.4 `tag_bits < 0` case (tiny address width) rejected with a message
    naming the conflict.
- **Definition of Done:** tests green and recorded; `memory.md` updated.

## Phase 3 — Cache organizations and access engine

**Status:** `DONE` (2026-10-24 — all five acceptance criteria passed; latest
run: zero-warning clean rebuild, engine tests 343 checks / 0 failures, pytest
43 passed / 2 warnings. Evidence: `memory.md` §7–§8; scope and corrections
recorded as decision D-18, including the E2 final-state fix)

- **Objective:** `simulate` mode processes traces correctly for all three
  organizations — hits, misses, fills, cache-state updates — with LRU as the
  working multi-way policy (required so set-assoc/fully-assoc can evict; FIFO
  and RANDOM arrive in Phase 4 as designed, not as placeholders).
- **Prerequisites:** Phase 2 DONE.
- **Scope:** Line state, fill/eviction mechanics, per-access core events,
  final cache state, direct-mapped no-policy rule. Excluded: FIFO/RANDOM,
  summary statistics, AMAT, full explanation strings (Phase 4).
- **Files:** `engine/include/{cache.hpp,simulator.hpp}`, `engine/src/{cache.cpp,simulator.cpp}`,
  `engine/src/main.cpp` (wire `simulate`), `engine/tests/engine_tests.cpp`.
- **Ordered tasks:**
  1. Line/set storage (flat arrays), global 64-bit stamp counter.
  2. Address decomposition into per-access core event (§6.5 core fields).
  3. Lookup: hit detection on (valid, tag); miss → fill lowest-index invalid
     way; if none, LRU victim.
  4. Direct-mapped: single way, `policy: null` in events.
  5. Fully-associative: one set, `index: null` in events, `set: 0`.
  6. Final state output (§6.7); `include_state_after_each` with the 2,000-access
     cap.
  7. Tests: E1, E2, E4, E6 walked per-access; direct conflict behavior;
     fully-assoc tags = block numbers; state snapshots equal expected arrays.
- **Validation/tests:** engine test suite green.
- **Acceptance criteria:**
  - AC-P3.1 E1: per-access events match the hand-computed sequence (fields
    address/block/tag/index/offset/set/way/result).
  - AC-P3.2 E2: 5 misses, 4 evictions (direct-mapped: single-way forced
    eviction, `policy: null`); final set 0 = block 0 (the last access
    reloads block 0 and evicts block 12 — corrected final state, see
    `architecture.md` §13 E2).
  - AC-P3.3 E4: all events have `index: null`; ways filled 0,1,2; 0 evictions.
  - AC-P3.4 E6: no eviction occurs while an invalid way exists (evictions stay
    0 through t2).
  - AC-P3.5 Every run satisfies the §9 invariants (asserted in the engine).
- **Definition of Done:** tests green; event schema example validated against
  `schemas/event.schema.json`; `memory.md` updated.

## Phase 4 — Replacement policies and statistics

**Status:** `DONE` (2026-10-24 — all five acceptance criteria passed; latest
run: zero-warning clean rebuild, engine tests 435 checks / 0 failures, pytest
52 passed / 2 warnings, byte-identical subprocess determinism verified.
Evidence: `docs/memory.md` §7–§8; decisions D-15 and D-19)

- **Objective:** All three replacement policies, complete event records,
  summary statistics and AMAT — the engine reaches its full contract.
- **Prerequisites:** Phase 3 DONE.
- **Scope:** FIFO and RANDOM policies (mt19937 + documented draw rule), full
  event fields (`evicted`, `policy_meta`, explanations), summary + AMAT +
  `trace_sha256` + `replacement_meta`, empty-trace handling. Excluded: nothing
  in the engine contract.
- **Files:** `engine/src/cache.cpp` (policy strategy), `engine/src/stats.cpp`,
  `engine/include/{stats.hpp,rng.hpp}`, `engine/tests/engine_tests.cpp`.
- **Ordered tasks:**
  1. FIFO stamps (`stamp_insert`, untouched by hits) + victim rule.
  2. RANDOM: `std::mt19937` seeded once per run; one draw per valid-line
     eviction only; victim = `draw % ways_in_set`, with `ways_in_set` taken
     from engine geometry (`associativity` for set-associative,
     `capacity/block_size` for fully-associative).
  3. Full event records incl. exact explanation templates (§10).
  4. Summary: counts, full-precision rates (`null` when empty), AMAT
     (both-or-neither inputs), `replacement_meta`, `trace_sha256`.
  5. Tests: E3 both policies per-access; E5 determinism (two identical runs,
     byte-compare); empty trace envelope; AMAT values 17.00/13.00 for E3;
     FIFO hit does not reorder; RANDOM consumes no draws on invalid-line fills.
- **Validation/tests:** engine test suite green.
- **Acceptance criteria:**
  - AC-P4.1 E3: LRU 1/4/2 and FIFO 2/3/1 (hits/misses/evictions), matching the
    published per-access walk.
  - AC-P4.2 E5: byte-identical envelopes for repeated same-seed runs (RANDOM),
    and the pinned seed-12345 reference on the E3 trace (§13 E5: draw values,
    victims, and per-access events) is reproduced exactly.
  - AC-P4.3 Empty trace → zeroed summary, `null` rates, no crash, exit 0.
  - AC-P4.4 AMAT values match §13 exactly; `amat` absent when inputs absent;
    rejected when only one is supplied.
  - AC-P4.5 Explanation strings match the templates; policy_meta correct for
    all policies and for direct-mapped.
- **Definition of Done:** tests green; result envelope validates against
  schemas; `memory.md` updated.

## Phase 5 — Engine verification (comprehensive)

**Status:** `DONE` (2026-10-24 — all four acceptance criteria passed; latest
run: zero-warning clean rebuild, engine tests 729 checks / 0 failures across
17 sections with per-section counts, 100k-access simulate measured at
0.0806 s, pytest 52 passed / 2 warnings. Evidence: `docs/memory.md` §7–§8;
performance root cause and fixes recorded as decision D-20)

- **Objective:** Prove the engine end-to-end with the full worked-example
  suite, boundary and abuse cases; fix everything found before any Python
  consumer is built.
- **Prerequisites:** Phase 4 DONE.
- **Scope:** Test hardening and bug fixes only — no features.
- **Files:** `engine/tests/engine_tests.cpp` (extended), fixes across engine
  sources as needed.
- **Ordered tasks:**
  1. Port E1–E6 as full expected-vs-actual tables (every event, every field).
  2. Boundary tests: max valid address accepted; max+1 rejected (`E_TRACE_INVALID`
     with max stated); trace of 100,000 sequential accesses completes < 1 s;
     100,001 rejected `E_LIMIT`; `include_state_after_each` at 2,001 refused.
  3. Malformed-job tests: broken JSON, unknown top-level keys, wrong types,
     trace longer than limit, negative/huge/float addresses.
  4. Determinism matrix: LRU, FIFO, RANDOM(seed 7), RANDOM(seed 8) each run
     twice — byte-identical pairs.
  5. Property sweep: for a randomized-but-seeded set of configs × traces,
     assert the §9 invariants (self-check harness with a fixed seed; expectations
     are invariants, not invented numbers).
  6. Fix every failure at the root; rerun the full suite after each fix.
- **Validation/tests:** full engine suite green; `README` build commands
  unchanged.
- **Acceptance criteria:**
  - AC-P5.1 E1–E6 pass field-by-field (AC-1…AC-5 of `prd.md` covered at engine
    level).
  - AC-P5.2 AC-6, AC-7, AC-9, AC-11, AC-12 demonstrated by named tests.
  - AC-P5.3 100k-trace run < 1 s (measured once, recorded).
  - AC-P5.4 Test runner prints a per-section summary (counts) — recorded
    verbatim in `memory.md`.
- **Definition of Done:** suite green with recorded output; zero known engine
  bugs; `memory.md` updated.

## Phase 6 — Bot 1: Trace Generation

**Status:** `DONE` (2026-10-24 — all five acceptance criteria passed; latest
run: pytest 90 passed / 2 warnings (38 new Bot 1 tests incl. 3 real-engine
integration cases), engine suite 729 checks / 0 failures, zero-warning clean
build. Evidence: `docs/memory.md` §7–§8; decisions D-6 and D-21)

- **Objective:** A tested, deterministic Trace Generation Bot with a strict
  request/response contract, including manual-trace import.
- **Prerequisites:** Phase 5 DONE (geometry mode authoritative; engine stable).
- **Scope:** `bots/trace_bot.py` only (plus its tests). Excluded: UI, Bot 2.
- **Files:** `bots/trace_bot.py`, `tests/test_trace_bot.py`.
- **Ordered tasks:**
  1. Implement the four request patterns per `architecture.md` §6.8
     (sequential, repeated, conflict, manual) — pure functions, dict in/out.
  2. Geometry via engine `geometry` mode (engine_client stubbed for unit
     tests; real in integration) — Bot 1 never derives sets itself.
  3. Validation: params, addresses vs. `max_address`, trace length limit;
     `E_*`-coded errors; fully-associative conflict warning.
  4. Manual parser: decimal/`0x` hex lines, `#` comments, blank lines.
  5. Unit tests: each pattern's exact expected addresses (hand-computed, e.g.,
     conflict blocks 0,S,2S,3S for S=2/4/1); determinism (same request twice);
     width violations; manual parsing edge cases.
  6. Integration test: real engine geometry call through engine_client.
- **Validation/tests:** `python -m pytest tests -q` green.
- **Acceptance criteria:**
  - AC-P6.1 Sequential/repeated/conflict examples match hand-computed
    addresses exactly, including the base-block rounding rule of
    `architecture.md` §6.8 (e.g., sets 4, target_set 3, start_block 0 →
    blocks 3, 7, 11, 15) and rejection when any generated address exceeds
    `max_address`.
  - AC-P6.2 Identical requests produce identical responses (proven in test).
  - AC-P6.3 Address ≥ 2^width and count > 100,000 rejected with `E_LIMIT` /
    `E_TRACE_INVALID` codes and actionable messages.
  - AC-P6.4 Manual import of the E3 trace text (`0 # A\n4 # B\n0\n8 # C\n4`)
    yields exactly `[0,4,0,8,4]`.
  - AC-P6.5 Fully-associative conflict request returns blocks in one set with
    the documented warning; no crash.
- **Definition of Done:** tests green; contract section validated against
  schemas where applicable; `memory.md` updated.

## Phase 7 — Bot 2: Experiment Runner and Performance Analysis

**Status:** `DONE` (2026-10-24 — all five acceptance criteria passed; latest
run: pytest 119 passed / 4 warnings (29 new Bot 2 tests incl. real-engine E3
policy and E2 organization comparisons), engine suite 729 checks / 0
failures, zero-warning clean build. Evidence: `docs/memory.md` §7–§8;
decisions D-15 and D-22)

- **Objective:** A tested Experiment Runner producing controlled comparisons,
  deterministic summaries, and reproducible experiment records.
- **Prerequisites:** Phase 6 DONE (trace contract stable).
- **Scope:** `bots/experiment_bot.py` only (plus tests); report persistence
  function (pure; caller supplies path). Excluded: UI wiring (Phase 8/9).
- **Files:** `bots/experiment_bot.py`, `tests/test_experiment_bot.py`.
- **Ordered tasks:**
  1. Experiment construction: `policy_comparison` (LRU/FIFO/RANDOM with seed)
     and `organization_comparison` (direct/set-assoc/fully-assoc with LRU),
     fixed-parameter checks, one-variable-at-a-time enforcement.
  2. Direct-mapped refusal for policy comparisons (`E_CONFIG_INVALID`,
     actionable message).
  3. Execution through engine_client; per-run summaries; seed + engine version
     recording; `trace_sha256` propagation.
  4. Deterministic `summary_text` from fixed templates with interpolated
     numbers (per §6.9); best-run identification.
  5. Experiment record assembly + `reports/<experiment_id>.json` writer.
  6. Unit tests (engine stubbed): matrix correctness, refusal, record shape,
     summary-text determinism; integration tests (real engine): E3 policy
     comparison reproduces 1/4/2 vs 2/3/1 with recorded AMAT 17.00/13.00;
     organization comparison on E2's trace.
- **Validation/tests:** `python -m pytest tests -q` green.
- **Acceptance criteria:**
  - AC-P7.1 Policy comparison on E3 config + trace yields run summaries
    matching §13 exactly and AMAT 17.00/13.00; the RANDOM run (seed 12345)
    matches the exact documented outcome of `architecture.md` §13 E5
    (2 hits / 3 misses / 1 eviction / rng_draws 1 / AMAT 13.00).
  - AC-P7.2 Policy comparison with direct-mapped config is refused with a
    clear error (AC of `prd.md` FR-C2).
  - AC-P7.3 Experiment record contains trace + configs + seeds + engine
    version and validates against `schemas/experiment.schema.json`.
  - AC-P7.4 `summary_text` is byte-identical for identical records and changes
    only when the underlying numbers change.
  - AC-P7.5 Organization comparison holds capacity/block/width fixed and uses
    LRU wherever a policy exists (asserted), with the caveat sentence present.
- **Definition of Done:** tests green; `memory.md` updated.

## Phase 8 — Engine, bots, and data integration

**Status:** `DONE` (2026-10-24 — all four acceptance criteria passed; latest
run: pytest 135 passed / 4 warnings (16 new integration tests incl. the
scripted Bot 1 → engine → Bot 2 → report workflow with reproducibility
proof), engine suite 729 checks / 0 failures, zero-warning clean build.
Evidence: `docs/memory.md` §7–§8; retry taxonomy recorded as decision D-23)

- **Objective:** Wire the engine client contract tightly, connect bots to the
  real engine, and prove the whole non-UI stack (config+trace in →
  results+reports out) including failure paths.
- **Prerequisites:** Phase 7 DONE.
- **Scope:** `bots/engine_client.py` completed and hardened; cross-component
  integration tests; report save flow. Excluded: Streamlit UI.
- **Files:** `bots/engine_client.py`, `tests/test_integration.py`,
  `traces/` sample files (E1–E3 + a longer sequential sample, json + txt).
- **Ordered tasks:**
  1. engine_client: job file creation, subprocess run (timeout 30 s), exit-code
     mapping, envelope parsing, typed `EngineError` with `E_*` codes, retry
     (max 2) on spawn/transient failures only, `ENGINE_PATH` override.
  2. Sample trace files for the demonstration workflow.
  3. Integration tests: full path UI-level payloads → bots → engine for the
     §8 workflow of `prd.md` minus the UI; error paths (bad config → typed
     error surfacing `details`; engine missing → clear message).
  4. End-to-end experiment: Bot 1 conflict trace → engine → Bot 2 policy
     comparison → record saved to `reports/`, then re-run reproduces
     byte-identical summaries.
- **Validation/tests:** full pytest suite green (unit + integration).
- **Acceptance criteria:**
  - AC-P8.1 `EngineError` carries code/message/details for every `E_*` family;
    validation errors are never retried (proven by test).
  - AC-P8.2 The scripted workflow (Bot 1 → engine → Bot 2) completes and its
    saved record re-runs reproducibly.
  - AC-P8.3 Missing/unbuilt engine produces an actionable error, not a crash.
  - AC-P8.4 All AC-6, AC-7, AC-9, AC-12 hold through the Python path.
- **Definition of Done:** integration suite green; `memory.md` updated with
  the exact working commands.

## Phase 9 — Streamlit user interface and visualizations

**Status:** `DONE` (2026-10-24 — all four acceptance criteria passed in the
scripted browser walkthrough; regression gate green: pytest 135 passed,
engine 729 checks / 0 failures, zero-warning build. Evidence: walkthrough
record `docs/phase9-walkthrough.md` + `docs/screenshots/09-*.png`;
`docs/memory.md` §7–§8)

- **Objective:** The complete UI per `design.md`: configuration, traces,
  simulation views, experiments, one-click workflow, reports.
- **Prerequisites:** Phase 8 DONE.
- **Scope:** `ui/app.py`, `ui/components.py`, `ui/tokens.py`, `ui/styles.css`,
  `ui/.streamlit/config.toml`. Excluded: any new bot/engine logic.
- **Ordered tasks:**
  1. Theme + CSS + tokens (§11 of `design.md`).
  2. Sidebar configuration (power-of-two selects, adaptive policy/seed
     controls, timing assumptions, inline validation messages).
  3. Simulator tab: trace sources (Bot 1 form, manual paste, sample loader),
     preview block, run button, metric cards, event table (≤ 500 rows shown +
     full CSV download), cache-state grid with last-access highlighting,
     cumulative hit-rate chart.
  4. Experiments tab: mode selection, seed field, run, comparison table, bar
     chart, summary text, save/download record.
  5. Automated Workflow tab: step list with statuses, retry, combined report
     download.
  6. Help tab: concepts, formulas, limits, reading guide.
  7. Error/empty/loading states per `design.md` §7; UI mirrors engine
     validation (thin mirror, single token source).
  8. GUI verification: scripted browser session clicking through the whole
     workflow (real interactions, screenshots) — including the §14 controlled
     demonstration of `prd.md`.
- **Validation/tests:** pytest suite still green (UI unchanged underneath);
  browser walkthrough passes with screenshots recorded in `docs/`.
- **Acceptance criteria:**
  - AC-P9.1 Every view renders real engine output only (AC-10); numbers in
    the demonstration match §14/§13 exactly (LRU 1/4/2, FIFO 2/3/1, AMAT
    17.00/13.00, seed recorded).
  - AC-P9.2 Invalid config shows the inline message naming field + range;
    the engine re-validation never contradicts it.
  - AC-P9.3 Workflow statuses (IDLE/RUNNING/DONE/FAILED) behave per §8 of
    `design.md`, including a forced failure (bad trace) leaving earlier
    results visible.
  - AC-P9.4 Design checklist of `design.md` §1 (no gradients/emoji/glow;
    tokens used; monospace numerics) verified in the walkthrough.
- **Definition of Done:** walkthrough evidence in `docs/`; `memory.md`
  updated.

## Phase 10 — End-to-end verification and delivery

**Status:** `DONE` (2026-10-25 — all four acceptance criteria passed:
fresh-setup path executed verbatim per the README; AC-1…AC-12 verified
with the evidence map in `docs/memory.md` §7; §14 demo executed from the
UI and archived as `docs/demo-record.json` matching §14 exactly; README
completed. Regression gate: engine 729 checks / 0 failures, pytest 135
passed / 4 warnings, zero-warning rebuild. Evidence: `docs/memory.md`
§7–§8)

- **Objective:** Ship it: full regression, complete documentation, fresh-setup
  reproducibility, and the final demonstration.
- **Prerequisites:** Phase 9 DONE.
- **Scope:** Verification, documentation, cleanup. Any code change here is a
  regression fix, not a feature.
- **Files:** `README.md` (full), `docs/` (report material: worked examples,
  screenshots, demo record), all six governing files (status sync).
- **Ordered tasks:**
  1. Run every test suite and build from scratch (delete `build/`, rebuild;
     fresh `pip install -r`); record outputs.
  2. Execute the controlled demonstration (§14) end-to-end from the UI and
     save its experiment record to `docs/`.
  3. README: prerequisites, exact setup/build/run/test commands, architecture
     summary, demo walkthrough, limits, links to the six governing files.
  4. Cross-check all six governing files against the shipped behavior; fix
     doc drift; finalize `memory.md` (state, evidence, known limitations).
  5. Final repo hygiene: no build artifacts or stray files; schemas,
     requirements, and docs consistent.
- **Validation/tests:** everything green; demo record matches published
  expectations.
- **Acceptance criteria:**
  - AC-P10.1 Fresh-setup path in README executed verbatim succeeds on a clean
    `build/` + reinstalled requirements.
  - AC-P10.2 All AC-1…AC-12 of `prd.md` verified with recorded evidence.
  - AC-P10.3 The saved demonstration record matches §14 (LRU 1/4/2, FIFO
    2/3/1, RANDOM seed recorded, AMAT 17.00/13.00).
  - AC-P10.4 README enables a coursemate to run the demo unaided.
- **Definition of Done:** phase report written; `memory.md` says DELIVERED
  with evidence links; no unresolved regressions.

---

## Post-delivery enhancement — E-3D "The Cache Machine" (V1)

**Status:** `DONE` (2026-10-25 — implemented and verified after delivery,
per the professor's 3D-visualization request and the reviewed v2 proposal;
not a numbered phase, all ten phases remain `DONE`.)

**Delivered:** three-lane 3D diorama (Main Memory / Address Bus / CPU
Cache) embedded in the Simulator tab via three.js r128 (MIT, vendored);
driven strictly by engine events + per-access snapshots (the UI now
requests `options.include_state_after_each` when the run qualifies);
correct copy semantics (loads copy, evictions discard the cached copy,
hits highlight with no memory traffic); playback controls with in-iframe
synchronized info/counters/mini-log; availability rules mirroring the
engine limits (trace ≤ 2,000, snapshot budget, stage caps 512 lines /
128 sets / 64 ways) with graceful captions. Tests: `tests/test_cache_scene.py`
(17 tests — payload fidelity, determinism, limits, org layouts, option
regression). Engine fix required and made: empty trace + snapshots
requested now returns `[]` instead of `null` (D-26). Evidence:
`docs/memory.md` §8 (D-25/D-26), `docs/screenshots/v1-3d-*.png`.

---

## Post-delivery enhancement — Light/Dark theme (dark mode)

**Status:** `DONE` (2026-10-27 — implemented and verified after delivery
from the approved read-only dark-mode audit; presentation only, not a
numbered phase, all ten phases remain `DONE`.)

**Delivered:** Light/Dark selector at the top of the sidebar (Light
default, session-state persistence across reruns and tab navigation;
browser refresh resets to Light in V1 — accepted). Centralized dark
palette in `ui/tokens.py` `THEMES` (WCAG-verified, test-asserted; light
values asserted verbatim so the delivered appearance cannot drift);
`ui/styles_dark.css` Streamlit-chrome overrides appended by
`components.inject_styles(theme)`; theme-aware charts, status lines, state
grid, and empty cards via a color namespace; 3D view themed through
presentation-only payload metadata + `ui/scene_dark.css` + a scene palette
in `scene_app.js`. Simulation data (events, snapshots, summaries, CSV,
experiments) is byte-identical across themes — test-asserted, including
E3 run identically in both themes. Accepted fallbacks: theme switch
resets 3D playback to access 1 paused; `st.dataframe` canvases keep
Streamlit's light rendering inside themed containers (Streamlit 1.66
limitation). No engine changes; no dependencies added. Tests:
`tests/test_theme.py` (15 tests — palette completeness + light regression,
computed WCAG contrast, CSS bundles, 3D theme embedding and
presentation-data separation, E3 identity across themes). Evidence:
`docs/memory.md` §8 (D-27), `docs/design.md` §6.10,
`docs/screenshots/theme-*.png`.

---

## Execution rules

- One phase per `Execute Phase N` command; stop after the phase report.
- If a prerequisite is incomplete, complete it first and say so in the report.
- Update `tasks.md` statuses and `memory.md` before closing each phase.
- Phase statuses here must always agree with `memory.md`.
