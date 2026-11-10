# memory.md — Current project state

> The verified, current state of the project. Updated after every meaningful
> change. Facts below marked **verified** were actually executed/inspected on
> the stated date; anything else is an assumption or limitation and is labeled.
> Last updated: 2026-10-29 (**DELIVERED**; post-delivery: 3D view V1, dark
> mode, reliability audit with four fixes — D-28, D-29/D-30 report
> persistence, D-31 final verification + projdemo rewrite).

---

## 1. Project identity

- **Project:** COA Cache Simulator with Two Automated Bots — a college Computer
  Organization and Architecture project.
- **Objective:** Interactive read-only cache simulator (direct / N-way
  set-associative / fully-associative; LRU / FIFO / seeded Random) with a C++
  engine as the single source of truth, Bot 1 (trace generation), Bot 2
  (experiment runner/analysis), and a Streamlit UI. No AI/LLM layer anywhere.
- **Governing docs:** `docs/prd.md` (scope/AC), `docs/architecture.md`
  (contracts/schemas/worked examples), `docs/rules.md` (standards),
  `docs/design.md` (UI system), `docs/tasks.md` (10 phases), this file.
  Specification priority is defined in `docs/prd.md` §13.

## 2. Current phase and status

- **Current phase:** **DELIVERED.** Phase 10 — end-to-end verification and
  delivery: `DONE` (2026-10-25; all four acceptance criteria passed —
  evidence in §7/§8). **All ten phases: `DONE`.** The project satisfies
  AC-1…AC-12 of `prd.md` (mapping table in §7).
- **Status:** the shipped state is the working tree as verified on
  2026-10-25 (fresh-setup verification §8). No pending phases; optional
  future work is listed in §10.
- **Next recommended action:** none required. For a fresh demonstration,
  follow the README walkthrough (build, test, `cd ui && python -m
  streamlit run app.py`, load `e3-lru-vs-fifo.json`, run the simulation
  and the policy comparison).

## 3. Verified repository state (final inventory, 2026-10-25)

- Repository: `C:\Projects\COA Cache Simulator with Two Automated Bots` —
  started completely empty (no files, not a git repository); the six governing
  Markdown files were created in the documentation phase.
- **Final repository inventory (verified 2026-10-25, delivered state; this
  single entry supersedes the earlier per-phase inventory paragraphs):**
  - `docs/` — the six governing `.md` files (no copies in the root) +
    `phase9-walkthrough.md`, `demo-record.json` (archived §14 record),
    `projdemo.md` (student demonstration guide), `screenshots/`
    (UI evidence: `09-*.png` walkthrough captures,
    `10-demo-delivery.png` delivery demonstration,
    `audit-event-table-tail.png` final-audit verification).
  - `README.md`, `requirements.txt`, `requirements-dev.txt`.
  - `engine/` — `Makefile`,
    `include/{version,config,geometry,cache,simulator,rng,stats,textutil}.hpp`,
    `src/{main,config,geometry,cache,simulator,stats}.cpp`,
    `tests/engine_tests.cpp`,
    `third_party/nlohmann/json.hpp` (nlohmann 3.11.3, vendored).
  - `schemas/` — all eight canonical JSON schemas.
  - `tests/` — `{test_smoke,test_trace_bot,test_experiment_bot,test_integration}.py`
    + `conftest.py`.
  - `bots/` — `{__init__,trace_bot,engine_client,experiment_bot}.py`.
  - `ui/` — `{app.py,components.py,tokens.py,styles.css,__init__.py}` +
    `.streamlit/config.toml`.
  - `traces/` — 4 sample traces (json + manual txt each).
  - `reports/` — saved experiment records (created on demand by the UI).
  - `build/` — build products (`cache_sim.exe`, `engine_tests.exe`).
- **Verified** there is no prior work to preserve or reconcile.

## 4. Verified environment (2026-10-24)

| Item | Finding | Consequence |
|---|---|---|
| C++ compiler | g++ (MinGW.org GCC-6.3.0-1) 6.3.0 — **verified** compiling and running a C++14 program | Engine targets a C++14-compatible subset; `-std=c++14 -O2 -Wall -Wextra` |
| C++17 | Not relied upon; GCC 6.3's C++17 support is incomplete | Do not use C++17-only features (`rules.md` §1) |
| MSVC / clang / CMake | `cl`, `clang++`, `cmake` all **absent** | Plain `engine/Makefile` for `mingw32-make`; no CMake |
| Make | `mingw32-make` at `C:\MinGW\bin` **present** | Build/test targets per `architecture.md` §4 |
| Python | `python` = 3.12.10 (`py` also offers 3.14.3) | Target 3.12; pandas/matplotlib/pytest verified importable on it |
| Python packages | pandas 2.3.2, matplotlib 3.10.6, pytest 8.3.3, jsonschema 4.25.1, **streamlit 1.66.1** (streamlit + floors installed in Phase 1 via `requirements.txt`/`requirements-dev.txt`) | All declared dependencies installed; no further installs needed |
| Network | **Verified** reachable (GitHub raw) | nlohmann/json 3.11.3 vendored from release tag `v3.11.3` |
| Shell/OS | Git Bash on Windows (win32) | Paths with spaces must be quoted; mingw32-make uses `sh` (verified: POSIX `mkdir -p`/`rm -rf` in Makefile worked) |

## 5. Architectural decisions (D-1 …, made and binding)

- **D-1 C++ standard:** C++14-compatible subset (compiler constraint, D-table
  above). Upgrade path: only with a verified newer compiler + `memory.md`
  decision entry.
- **D-2 Build system:** `engine/Makefile` driven by `mingw32-make` (`all`,
  `test`, `clean`); documented single-line g++ fallback. No CMake.
- **D-3 JSON handling:** vendored nlohmann/json single header in the engine
  (justified: cross-process contract needs robust JSON; hand-rolling a parser
  is a correctness risk). Python uses stdlib `json`.
- **D-4 Process contract:** `cache_sim --mode {simulate|geometry|version}
  [--in file] [--out file]`; JSON envelopes; exit codes 0/2/3/4; error codes
  `E_USAGE, E_JOB_INVALID, E_CONFIG_INVALID, E_TRACE_INVALID, E_LIMIT,
  E_INTERNAL`. Full detail: `architecture.md` §5–§6.
- **D-5 Engine semantics pinned:** fill = lowest-index invalid way; LRU =
  smallest `stamp_used` (updated on hit+fill); FIFO = smallest `stamp_insert`
  (fill only); RANDOM = `std::mt19937(seed)`, one draw per valid-line eviction,
  victim = `draw % ways_in_set` (from engine geometry: `associativity` for
  set-associative, `capacity/block_size` for fully-associative, 1 for direct —
  where no policy is selectable, so RANDOM never arises there); fully-associative
  reports `index: null`; explanation templates fixed with `{why}` token
  vocabulary `LRU | FIFO | Random | direct`. `architecture.md` §7–§10.
- **D-6 Bot 1 geometry:** Bot 1 obtains `sets` from the engine's `geometry`
  mode rather than re-deriving it in Python (keeps the engine the single
  source of truth; costs one cheap subprocess call).
- **D-7 Bot 2 modes:** `policy_comparison` and `organization_comparison`
  — the two required modes were **implemented and verified in Phase 7**
  (historical note: at decision time, Phase 6, they were specified but not
  yet implemented); generic parameter sweeps remain deferred (documented
  deferral, §10; `prd.md` FR-C3 covers the required organization mode,
  which ships).
- **D-8 UI stack:** Streamlit + matplotlib (already installed; no new chart
  dependency); design tokens single-sourced in `ui/tokens.py` + `styles.css`
  (see `design.md` §11).
- **D-9 Testing:** engine = single-file assert-based runner (no framework,
  mingw32-make `test` target); Python = pytest (unit tests stub the engine;
  integration tests require `build/cache_sim.exe` and skip loudly if absent).
- **D-10 Versioning:** engine version string `0.1.0` embedded in every
  envelope/record; any semantic change bumps it and is noted here.
- **D-11 `jsonschema` (4.25.1) listed in `requirements-dev.txt`:** needed to
  run the canonical-schema compliance tests (rules.md §6). It is already a
  transitive dependency of Streamlit/Altair, but tests import it directly, so
  it is declared explicitly.
- **D-12 Vendored nlohmann/json pinned to release tag `v3.11.3`**
  (`engine/third_party/nlohmann/json.hpp`), compiled via `-isystem` so
  third-party-header warnings cannot break the zero-warning gate (AC-P1).
  Verified to compile cleanly under GCC 6.3 with `-std=c++14`.
- **D-13 Phase-1 CLI behavior details (documented contract):** duplicate or
  unknown flags are `E_USAGE` errors; there is no separate `--help` (any
  usage error carries the usage line in `error.message`); `version` mode
  ignores `--in`; envelopes are written compact (`json.dump()`). All
  original mode stubs are gone: `geometry` is fully implemented since
  Phase 2 and `simulate` since Phase 3.
- **D-17 Config-validation contract tightening (Phase 2, 2026-10-24):**
  inapplicable fields must be null or absent, never silently ignored — the
  engine rejects a non-null `associativity` when organization ≠
  `set_associative`, and a non-null `seed` when `policy ≠ RANDOM`
  (silently ignoring them would violate the no-silent-repair rule,
  `rules.md` §2). `schemas/config.schema.json` was tightened to match
  (two `if/then` branches) and `architecture.md` §6.1 prose updated in the
  same change (schema + docs + tests together, `rules.md` §6). Error
  messages are part of the tested contract: engine tests assert exact
  `problem` strings. **Gotcha encoded in a regression test:** nlohmann
  parses positive JSON integers as unsigned, so numeric validation must go
  through the shared `get_non_negative_int` helper (a text-parsed
  `"address_width_bits": 8` was initially rejected by an
  `is_number_unsigned()` branch — caught by pytest, fixed, and locked with
  an in-process text-parsed test).
- **D-14 Pre-Phase-2 specification consistency pass (2026-10-24, explicit
  user request):** documentation/fixture corrections only; no engine code
  changed; Phase 1 acceptance criteria re-verified afterwards. Corrections,
  each found by manual recalculation:
  (a) `architecture.md` §6.5 event example mixed LRU labels with the FIFO
  victim — corrected to the true E3-LRU t4 event (evicts block 2, tag 1,
  way 1);
  (b) the RANDOM run in the experiment-record example (§6.9) and the
  `tests/test_smoke.py` EXPERIMENT_DEMO fixture was infeasible for the E3
  trace (0 hits impossible — t3 always hits before any eviction; AMAT 23.0
  contradicted its own miss rate) — provisionally corrected to a feasible
  outcome, then **pinned to the exact deterministic outcome in D-15**;
  (c) RANDOM victim modulus changed from `% associativity` to
  `% ways_in_set` (geometry-derived; `associativity` does not exist for
  fully-associative) — D-5 amended, `tasks.md` Phase 4 updated;
  (d) Bot 1 conflict formula corrected: base = smallest block ≥ start_block
  with block ≡ target_set (mod sets) — the old
  `start_block + target_set + k×sets` formula missed the requested set for
  start_block not congruent to target_set; boundary/address-width handling
  documented (E_TRACE_INVALID / E_LIMIT, never wrap);
  (e) direct-mapped evictions got the `victim_selection: "forced"` label and
  the `{why}` explanation token `direct` (schema enum extended);
  (f) `insert_order_rank` direction pinned (1 = oldest among valid lines);
  (g) engine filesystem contract made explicit (§5.1, `rules.md` §9);
  (h) `rules.md` §9 dependency list corrected to include pytest + jsonschema
  (already in `requirements-dev.txt` since Phase 1).
- **D-15 RANDOM reference pinned to the exact deterministic outcome
  (2026-10-24, final pre-Phase-2 pass):** seed 12345 on the E3 trace
  (2-way set-associative). `std::mt19937` draw 1 = **3992670690**
  (draw 2 = 3823185381, never consumed); victim = draw 1 % 2 = **way 0**,
  so t4 evicts block A (block 0) and t5 hits. Actual outcome: **2 hits /
  3 misses / 1 eviction / rng_draws 1 / AMAT 13.00** (RANDOM ties FIFO on
  hit rate). Method: throwaway probe compiled with the verified toolchain
  (g++ 6.3.0 / libstdc++); the C++11 standard pins the mt19937 algorithm and
  seeding, and the probe sanity-checked seed 5489 against the canonical
  MT19937 reference value 3499211612 (exact match). Documented in
  `architecture.md` §13 E5 and §6.9; `tests/test_smoke.py` EXPERIMENT_DEMO
  updated; `rules.md` §4 reconciled with §9 (engine filesystem contract).
  Phases 4 and 7 must reproduce this sequence exactly.
- **D-19 Phase-4 decisions and corrections (2026-10-24):**
  (a) Empty-trace AMAT: `architecture.md` §6.6 says `amat` is present iff
  the timing inputs are supplied; for an empty trace the modeled miss rate
  is 0, so the value degenerates to `hit_time` (e.g., 1.0 with the standard
  assumptions). Pinned by tests.
  (b) **`parse_and_validate_config` now resets `*out` unconditionally** —
  reusing a `Config` across parses previously leaked `has_policy`/`policy`
  from the prior parse into a direct-mapped config (found by the Phase 4
  `replacement_meta`-omission test; root-cause fixed, not worked around).
  (c) `state_to_json` takes the policy: LRU/direct report
  `last_used_rank`, FIFO reports `insert_order_rank` (1 = oldest), RANDOM
  reports neither — per `architecture.md` §6.7. Snapshots serialize with
  the run's policy.
  (d) `summary_to_json` was removed (dead code after `build_summary`);
  the complete `summary` now validates against `summary.schema.json`,
  closing the Phase 3 interim-shape note in D-18b.
  (e) The trace digest uses a minimal FIPS 180-4 SHA-256 pinned by the
  canonical vectors (empty string, "abc") and cross-checked against Python
  `hashlib` in pytest.
  (f) **Contract-check correction (pre-Phase 5, 2026-10-24):** AC-P4.4 and
  `architecture.md` §6.6 require `amat` to be **omitted entirely** when
  timing inputs are absent; the Phase 4 implementation initially emitted
  `"amat": null` and `summary.schema.json` required/allowed it. Fixed in
  `build_summary` (key omitted), the schema (`amat` removed from
  `required`; the null variant dropped — present means the object),
  the engine test (key-absence via `find`), and pytest (omission +
  no-timing summary schema validation). Empty-trace-with-timing behavior
  unchanged: AMAT = `hit_time` (D-19a).
- **D-20 Phase-5 verification findings and fixes (2026-10-24):**
  (a) **Performance root cause (NFR-2):** calibration showed the verified
  machine's string operations are pathologically slow (~2.2 µs per
  `std::to_string`/concat — 100M integer adds take 0.07 s, so the CPU is
  fine); the hot loop built ~10 string temporaries per access, making a
  100,000-access simulate take ~0.97 s — barely under the 1 s gate and
  flaky. Fixed by `engine/include/textutil.hpp` (`append_u64`: allocation-
  free decimal formatting), in-place explanation building, `events.reserve`,
  and an in-place canonical-string builder in `trace_sha256`. Measured:
  **0.0806 s** for 100,000 sequential accesses (~12× faster). The 100k
  eviction expectation in the new boundary test was corrected during the
  walk: 49,996 (the first four misses fill the four empty sets), not 49,999.
  (b) **`validate_trace` never populated `trace.name`** — found by the new
  unit tests; fixed (name assigned on success).
  (c) The E5 engine test now pins the full seed-7 walk (draws
  327741615 / 976413892 / 3349725721 → victims way 1, way 0, way 1),
  published in `architecture.md` §13 E5.
  (d) The property sweep uses a fixed-seed LCG for pseudo-random addresses
  (no unseeded randomness, `rules.md` §2) and asserts recountable
  event/summary consistency plus `rng_draws == evictions` for RANDOM runs;
  expectations are invariants only.
  (e) The harness prints per-section counts (`[done] <section>: N checks,
  M failures`) per AC-P5.4.
- **D-21 Phase-6 decisions (2026-10-24):**
  (a) `bots/engine_client.py` ships minimal for Phase 6 — `run_mode`
  (payload via stdin, 30 s timeout, `ENGINE_PATH` override) +
  `fetch_geometry`; `simulate`-mode support, retries, and hardened
  translation arrive in Phase 8 per the phase plan.
  (b) `trace_bot.generate(request, geometry_provider)` takes the geometry
  provider as an injected callable: unit tests use a lookup-table stub over
  the *published* fixture geometries (no geometry logic reimplemented in
  the stub), while integration tests inject the real
  `engine_client.fetch_geometry` (D-6).
  (c) All pattern parameters are required (no bot-side defaults — the UI
  will pre-fill its own); unknown request/params keys are rejected as typos;
  booleans are not accepted as integers.
  (d) Trace names are derived deterministically from the parameters (e.g.,
  `conflict-4b-set3-p1`, `manual-import`) — never from a clock, so
  AC-P6.2's full-response equality holds.
  (e) `sequential.stride_bytes` must be >= 1; a zero stride is rejected
  with a message pointing at the repeated pattern.
  (f) The manual parser collects ALL problem lines into one
  `E_TRACE_INVALID` error (line-numbered details) rather than failing on
  the first.
  (g) `tests/conftest.py` bootstraps sys.path so `python -m pytest` and
  plain `pytest` both resolve `bots.*` and the shared `test_smoke` fixtures.
- **D-23 Phase-8 decisions (2026-10-25):**
  (a) Retry taxonomy (AC-P8.1): engine error envelopes are terminal and
  never retried; transient failures — spawn OSError, timeouts, exit codes
  outside {0, 2, 3, 4}, and unparseable output — retry up to 2 times
  (3 attempts) inside `run_mode`, then raise `E_INTERNAL`. Proven by
  counting-fake tests over the injectable `_spawn_attempt` seam.
  (b) Exit-code/envelope consistency: `returncode == 0` must agree with
  `envelope.ok`; contradictions are terminal `E_INTERNAL` (contract bugs,
  not transient).
  (c) Payloads travel via stdin rather than job files — contract-compliant
  (architecture.md §5.1) and filesystem-clean; the "job file creation"
  idea from the original Phase 8 task list is superseded by the stdin
  path.
  (d) Sample traces live in `traces/` as pairs (`*.json` for direct
  loading, `*.txt` in the manual-import format); the integration suite
  proves both versions of each pair produce identical addresses through
  Bot 1.
- **D-25 The Cache Machine — 3D view V1 (post-delivery enhancement,
  2026-10-25):** implements the animation deferred in §10. Three-lane 3D
  diorama (Main Memory wall → Address Bus → CPU Cache shelves) embedded in
  the Simulator tab via `streamlit.components.v1.html`; driven strictly by
  engine output — events (block/set/way/tag/offset/result/loaded/evicted/
  policy_meta/explanation) plus per-access snapshots requested through the
  existing `options.include_state_after_each` (the UI now sends this option
  when the run qualifies: trace ≤ 2,000, snapshots × lines ≤ 2,000,000,
  and the stage caps — 512 lines, 128 sets, 64 ways; otherwise the 3D view
  is disabled with a caption and the run behaves exactly as before).
  Playback (Play/Pause/Next/Previous/Replay/Reset/speed/scrubber) is owned
  by the iframe's JavaScript; the payload is deterministic per envelope so
  identical results produce identical HTML. Copy semantics enforced: loads
  are copies (memory persists), evictions discard the cached copy only,
  hits highlight the cached copy with no memory traffic. New files:
  `ui/cache_scene.py` (payload builder + availability rules + HTML
  assembly), `ui/scene_app.js` (scene + playback, no cache logic),
  `ui/scene.css`, `ui/static/three.min.js` (three.js r128, MIT, vendored —
  dependency recorded per rules.md §9), `tests/test_cache_scene.py` (17
  tests). **Verified limitation:** the iframe does not survive page
  refresh (session reset, existing behavior); a Streamlit rerun with an
  unchanged payload was tested in the browser and playback position
  survived (4/5 preserved across a forced rerun). Scene evidence:
  `docs/screenshots/v1-3d-final.png` (canvas extraction after playback),
  `v1-3d-midplay.png` (mid-play page capture).
- **D-26 Empty-trace snapshot semantics fix (2026-10-25):** with
  `include_state_after_each` requested and an empty trace, the envelope
  reported `state.snapshots: null` (`state_to_json` collapsed the empty
  array), contradicting `architecture.md` §6.7 ("snapshots is a list …
  when the option is true") and breaking the UI's captured/not-captured
  distinction. Fixed: `SimulateResult` records `snapshots_requested`,
  `state_to_json` emits `[]` for requested-but-empty and `null` only when
  the option was absent; `ui/cache_scene.py` treats `[]` as a valid empty
  animation. Verified: empty trace + option → `[]` (3D shows "Empty
  trace"); no option → `null` ("not captured"). Cache algorithm untouched.
- **D-27 Dark mode (post-delivery enhancement, 2026-10-27):** Light/Dark
  sidebar selector (`st.session_state` widget, Light default; resets on
  browser refresh — accepted V1 limitation, no URL persistence per
  approved decision). Implementation: `ui/tokens.py` gains `THEMES` +
  `get_tokens` (dark palette WCAG-verified — text 14.73:1, secondary
  8.13:1, accent 5.33:1, border 3.55:1 on #16181D);
  `components.inject_styles(theme)` emits the base sheet plus
  `ui/styles_dark.css` (Streamlit chrome overrides scoped to the verified
  1.66 testids/classes — `.stApp`-prefixed to out-specify emotion styles);
  matplotlib charts take a theme-color namespace (transparent figure bg);
  `cache_scene.build_html(envelope, theme)` adds `payload["theme"]`
  (presentation-only) and appends `ui/scene_dark.css`; `scene_app.js`
  selects a scene palette from `P.theme` and sets `body.cm-dark`/`cm-light`.
  Simulation data is theme-independent (test-asserted). Accepted fallback:
  a theme switch rebuilds the 3D iframe, resetting playback to access 1
  paused (same class as any payload change). Known V1 limitation: the
  st.dataframe event-log canvas keeps Streamlit's light rendering (its
  container is themed; a full-dark grid would need theme.base runtime
  switching, which Streamlit 1.66 does not support).
- **D-28 Reliability-audit fixes (2026-10-27):** full application audit
  (config/geometry/policy matrix, trace sources, engine invariants, Bot 2,
  workflow, experiments, 3D view, themes) found four verified defects, all
  fixed with regression tests:
  1. `bots/experiment_bot.py` — policy_comparison built the record's
     `fixed` metadata with `config["associativity"]` unconditionally, so a
     fully_associative config (which must NOT carry that field, per
     `architecture.md` §6.1) crashed Bot 2 with a raw `KeyError`
     (production incident: fully associative 16 B / 16 B / 13-bit FIFO,
     conflict 8×11, seed 5457). Fix: `associativity` is included in
     `fixed` only for set_associative, and `_validate_config_shape` now
     requires an integer `associativity` for set_associative bases so an
     incomplete config is a structured `E_JOB_INVALID`, never a KeyError.
     Verified end-to-end in the running app: the incident workflow now
     completes all four steps (88 accesses, 0 hits, 87 evictions per
     policy, RANDOM seed 5457 with 87 rng draws — hand-calculated values).
  2. `bots/trace_bot.py` — the manual parser collected every problem line
     with no cap (the engine truncates at 10), so a pathological all-bad
     paste built an unbounded error card. Fix: first 10 issues plus one
     "further problem lines truncated (N more)" summary; the message
     keeps the true total.
  3. `ui/app.py` — "Load sample" crashed the run on a malformed or
     hand-edited sample file (raw `JSONDecodeError`/`KeyError`, or a
     non-list `addresses` crashing the preview render). Fix: samples are
     shape-checked at load; an invalid file renders an `E_TRACE_INVALID`
     error card and keeps the currently loaded trace and results
     (browser-verified with a bad file, then removed).
  4. `ui/app.py` — workflow step 4 called `save_report` unguarded; an
     `OSError` unwound before `state.workflow = workflow`, wiping the
     successful steps 1–3 results from session state. Fix: a save failure
     marks step 4 failed (`E_INTERNAL` error card, FAILED pill) with
     steps 1–3 kept; "Retry failed step" re-runs step 4 only.
  Audit harnesses (scratch, not committed): 12,573 engine checks (543
  simulate runs across 5 geometries × 9 organization/policy combos × 10
  boundary traces, plus ~60 validation cases) and 111 bot/scene checks —
  no engine or bot defects beyond the four above. pytest 167 → 172 (5
  regression tests). No commit/push performed.
- **D-29 Adversarial reliability pass (2026-10-27, second audit):**
  differential + metamorphic + fault-injection + mutation testing against
  the already-committed D-28 state. One verified engine defect found and
  fixed, plus two boundary hardenings; everything else confirmed clean.
  1. **Engine crash fix (`engine/src/main.cpp`):** a VALID supported
     configuration — capacity 2^20, block 1, direct-mapped (1,048,576
     sets) with a 100,000-access trace — exhausted memory on a
     constrained machine and died with an **uncaught `std::bad_alloc`**:
     empty stdout, `terminate()`, abort exit code 3 — colliding with the
     documented "validation" exit code and producing no contract
     envelope. Root cause: the final-state JSON for a 2^20-line cache
     (≈101 MB of text, several hundred MB of nlohmann structures) plus
     100,000 event objects can exceed available RAM; nothing caught the
     standard-library failure. Fix: the simulate/serialize/emit phase in
     `run_simulate` is wrapped in try/catch — `std::bad_alloc` emits the
     documented `E_INTERNAL` envelope ("the engine ran out of memory
     …") with exit 4; any other `std::exception` emits
     `E_INTERNAL` with `what()`. Contract-conformant failure on any
     machine (bigger-RAM machines may legitimately succeed with ok:true
     — the regression test accepts both branches and asserts the
     envelope contract). The final emit was initially left outside the
     try (the 101 MB `dump()` threw there) — caught in review-by-test.
  2. **Transport hardening (`bots/engine_client.py`):** ok-envelopes are
     now shape-validated per mode (simulate: engine/geometry/events/
     summary/state with types; geometry: engine/geometry; version:
     engine) — a stale or mismatched engine binary emitting a
     "successful" envelope missing its contract fields now fails as
     terminal `E_INTERNAL` at the client boundary instead of flowing
     through as a false success that would KeyError later consumers.
  3. **Scene-payload hardening (`ui/cache_scene.py`):** `build_payload`
     refuses envelopes whose snapshot count disagrees with the event
     count (the JS reads `snapshots[k-1]` by index; a mismatch would
     desynchronize the scene from the real accesses).
  Evidence from the pass: independent test-only Python reference model
  (exact mt19937 replication — seed 12345 first draw 3992670690
  confirmed) agreed with the engine on **496,980 checks over 946 runs /
  39,640 events** (every event field, final state incl. ranks, counters,
  rng draws, every per-access snapshot); metamorphic invariances
  (snapshots/AMAT-off/byte-identical rerun/resident-block
  re-access/prefix-event agreement/final-snapshot==state) all hold;
  adversarial field limits (2^62/2^64-1 capacity values, seed 2^32-1
  accepted & 2^32 rejected, float-where-int rejected, nulls rejected,
  inf hit_time rejected at the JSON boundary as E_JOB_INVALID, u64
  address extremes) behave per contract; 100k-access timing < 1 s;
  CLI/exit-code/`--out` contract verified. **Mutation testing (scratch
  copies, never the real build):** LRU→MRU killed by the engine suite
  (18 failures), missing eviction-counter increment killed (26
  failures), digest canonical-prefix change survived `engine_tests`
  (0 failures) but is killed by pytest (3 failures — the digest is
  pinned against independent hashlib values only at the Python layer).
  ruff (pyflakes/bugbear subset): production code clean; 2 nits in new
  test code fixed; B904 raise-from chains in `engine_client` are
  pre-existing intentional style (left unchanged). Streamlit 1.66
  auto-fixes the mixed str/int "evicted block" dataframe column
  ("Applying automatic fixes", logged only — the table renders; CSV
  unaffected) — accepted behavior, documented here rather than changed.
  Known accepted limitation: `experiment_id` has second resolution, so
  two DIFFERENT experiments completing within the same wall-clock
  second would collide on the report filename (same-second reruns of
  identical input are byte-identical and harmless); observed reachability
  requires sub-second back-to-back runs — documented, not redesigned.
  (RESOLVED by D-30 the same day: microsecond id segment + schema
  pattern widened + non-overwriting `save_report`; the historical
  explanation above is preserved for context.)
  pytest 172 → **194** (22 new: 9 AppTest UI-sequence tests incl. the
  failure→retry→recovery path with engine-call counting, 5
  ok-envelope-shape + empty-stdout transient, 4 save_report filesystem
  failures, 1 snapshot-alignment, 1 engine extreme-state regression,
  2 Bot 1 exact-sequence). Engine suite 729 checks / 0 failures.
  Sanitizer note: MinGW.org GCC 6.3 does not support ASan/UBSan builds —
  overflow/shift safety was reviewed by reading the arithmetic (all
  address math is uint64 with explicit width==64 guard) and by the
  differential/limit testing above, not by sanitizer run. No commit or
  push performed; the unrelated untracked `imulator"` file untouched.
- **D-30 Experiment-ID collision fix (2026-10-27):** resolution of the
  D-29 known limitation. Reproduced deterministically with a controlled
  clock (`bots.experiment_bot.datetime` patched to a frozen timestamp):
  two different experiments created in the same wall-clock second
  received the identical `experiment_id` (`exp-YYYYMMDD-HHMMSS-mode`),
  resolved to the same `reports/<id>.json` path, and the second
  `save_report` silently overwrote the first report — losing it while
  the UI still displayed the first record. Why the fix was made: the id
  is the sole report filename key, the incident was reachable in
  principle from back-to-back runs, and the loss was silent. Fix
  (smallest change preserving contracts):
  (1) `experiment_id` gains a 6-digit microsecond segment
  (`exp-YYYYMMDD-HHMMSS-ffffff-mode`) — wall-clock based like the
  existing `created_utc` (no in-memory counter, no randomness;
  experiments are created sequentially in one process and each involves
  multiple engine subprocesses, so same-microsecond completion is
  unreachable in practice);
  (2) `schemas/experiment.schema.json` pattern widened to
  `^exp-[0-9]{8}-[0-9]{6}(-[0-9]{6})?-[a-z_]+$` — the historical
  second-resolution format (e.g. `docs/demo-record.json` and every
  pre-D-30 report) remains valid, so no consumer changes;
  (3) `save_report` never silently overwrites a destination holding
  DIFFERENT content — it raises `FileExistsError` (an OSError, so the
  workflow's step-4 handler already treats it as a failed step with
  steps 1-3 preserved); re-saving the identical record stays allowed
  (idempotent, byte-identical);
  (4) the Experiments tab "Save report" button, previously unguarded,
  now surfaces save failures as an error card (design.md 7) instead of
  a traceback. `architecture.md` §6.9 documents the new format and the
  no-overwrite rule; the schema description carries the rationale.
  Report determinism is unaffected: identical inputs under identical
  conditions still produce identical records, and `summary_text`
  determinism is untouched. Regression tests (5, in
  `TestReportIdentity`): distinct ids + separate reports + first report
  intact under a controlled same-second clock; id↔filename↔serialized
  metadata agreement; frozen-clock identical-input reproducibility with
  idempotent re-save; conflicting-destination refusal leaving the
  existing file byte-identical; schema accepts microsecond + legacy ids
  and rejects malformed variants. pytest 194 → **199**.
  **Atomicity hardening (same day, concurrency review):** the original
  D-30 guard was a check-then-write sequence (`path.exists()`/`read_text`
  then unconditional `write_text`) — a TOCTOU race in which two
  concurrent saves of different content under one id could both pass the
  check and the last writer silently won (Streamlit runs sessions as
  threads, so concurrent saves are reachable). `save_report` now creates
  the destination atomically with `os.open(O_WRONLY|O_CREAT|O_EXCL)`
  (honored on POSIX and Windows) and writes through that exclusive
  handle: exactly one concurrent save wins, losers get `FileExistsError`,
  and a refused save never modifies the original. A bounded 0.5 s poll in
  the `EEXIST` path keeps concurrent identical saves idempotent (the
  winner may still be mid-write), and a failed write unlinks the file it
  exclusively created so no misleading partial report survives. Bytes are
  now LF on all platforms (written via `O_BINARY` binary handle;
  `read_text` normalization keeps legacy CRLF pre-D-30 reports
  idempotent). Regression tests: `TestSaveReportAtomicity` (concurrent
  identical saves all succeed idempotently with intact bytes; six
  concurrent conflicting saves all refused with the original
  byte-identical; a true first-save race yields exactly one winner and
  one complete record — 10 repeat runs, no flakiness), and the two
  fault-injection tests now inject at the new write point (`os.fdopen`).
  pytest 199 → **202**.
- **D-31 Final project-wide verification + demonstration-guide rewrite
  (2026-10-29):** no code changes; the delivered state was re-verified
  from scratch (suites, from-scratch builds in Git Bash AND PowerShell,
  31 direct engine-CLI checks against E1–E6, 40 end-to-end Bot 2 checks
  against `docs/demo-record.json`, and a live browser walkthrough of the
  whole demo sequence). No defects found. `docs/projdemo.md` was rewritten
  from that evidence — the previous copy still claimed "135 tests" and
  omitted the Theme control, the D-30 report behavior, and the 3D limits.
  Evidence recorded in §8 (2026-10-29 entry).
- **D-24 Phase-9 decisions (2026-10-25):**
  (a) Launch convention: the app is started from the `ui/` directory
  (`cd ui && python -m streamlit run app.py`) so `ui/.streamlit/config.toml`
  applies; `app.py` bootstraps the project root onto sys.path for the
  `bots.*`/`ui.*` imports.
  (b) Streamlit imported modules are cached until the server restarts —
  edits to `ui/components.py` require a server restart (hit twice during
  the walkthrough; file-watcher reruns do not reload imports).
  (c) The workflow renders live `st.status` containers during a run and
  persisted IDLE/DONE/FAILED pills from session state afterwards; a
  failed step stores its step number so "Retry failed step" re-runs from
  there with earlier artifacts kept.
  (d) UI early validation is a thin mirror only (power-of-two selects
  make most invalid input untypable; cross-field checks duplicate the
  engine's numbers for fast feedback, engine stays authoritative).
  (e) The AMAT metric renders as label "AMAT (cycles)" + value "17.00" —
  the unit moved to the label after the value truncated in the 7-column
  row (design.md 6.6 wording updated to match).
  (f) A full-page screenshot of the Streamlit app double-renders content
  (IAB capture artifact) — viewport screenshots at scroll positions are
  used for evidence instead.
- **D-22 Phase-7 decisions (2026-10-25):**
  (a) `run_experiment(request, simulate_fn)` takes the engine runner as an
  injected callable — production injects `engine_client.run_simulate`
  (added in this phase; retries stay Phase 8), tests inject canned
  schema-shaped stubs. Responses follow the Bot 1 convention:
  `{"ok": True, "record": ...}` / `{"ok": False, "error": ...}`.
  (b) Request contract: `{mode, trace, config, random_seed}` —
  `random_seed` required for policy_comparison, rejected in
  organization_comparison (D-17-style inapplicability).
  (c) Experiments refuse empty traces (`E_TRACE_INVALID`): an empty-trace
  comparison is meaningless and would put null rates into the summary
  templates.
  (d) The best-hit-rate sentence names runs by short labels (policy or
  organization — the RANDOM seed stays in the per-run sentences); winners
  group with a 1e-12 rate tolerance; single-winner "vs" and N-way "tie"
  forms are pinned by tests, including the 3-way tie.
  (e) Stale-seed stripping: policy-comparison run configs derived from a
  RANDOM-shaped base drop `seed` for the LRU/FIFO runs (D-17 would reject
  them at the engine).
  (f) Bot-level config shape validation checks only what the bots need
  (capacity/block/width ints + organization string); associativity is
  required only by the organization-comparison branch — everything deeper
  stays engine-authoritative.
  (g) `save_report(record, directory)` writes deterministic bytes (sorted
  keys, 2-space indent, trailing newline) to
  `<directory>/<experiment_id>.json`; `experiment_id`/`created_utc` come
  from the UTC clock, which is why AC-P7.4 pins `summary_text` (timestamp-
  free) rather than whole-record equality.
- **D-16 rules.md §4 wording reconciled with §9 (same pass):** §4 previously
  said the engine has "no filesystem side effects", which contradicted the
  sanctioned `--out` write; both sections now state the identical contract
  (read only `--in`/stdin, write only `--out`/stdout, no other filesystem,
  network, or environment access).
- **D-18 Phase-3 decisions and corrections (2026-10-24):**
  (a) Per-access events include ALL `event.schema.json` fields already in
  Phase 3 — `policy_meta` and the exact §10 explanation templates ship now
  (LRU / direct cases) because events must validate against the canonical
  schema; the tasks.md scope note deferring "full explanation strings" is
  superseded on contract-completeness grounds (FIFO/RANDOM
  `victim_selection` values remain Phase 4).
  (b) The Phase 3 result envelope carries `echo` (config), `geometry`,
  `events`, `summary` (counts + full-precision rates, `null` on an empty
  trace), and `state`; `amat`, `trace_sha256`, and `replacement_meta` are
  added in Phase 4, so the summary does not yet validate against
  `summary.schema.json` (events and state do).
  (c) **E2 final-state correction:** the trace `[0,8,16,24,0]` ends with
  address 0, so its last access reloads block 0 and evicts block 12 — the
  final line holds block 0, not block 12 as an earlier revision of
  `architecture.md` §13 E2 claimed. Doc, `tasks.md` AC-P3.2, and the engine
  test were corrected together after re-walking the trace line by line.
  (d) Snapshot limits implemented as specified plus a serialization budget:
  trace ≤ 2,000 accesses AND snapshots × total cache lines ≤ 2,000,000
  (both `E_LIMIT`; budget row added to `architecture.md` §12) — prevents a
  pathological cache-size × trace-length hang.
  (e) Trace-level unknown keys are rejected (`E_TRACE_INVALID`), consistent
  with config-level typo protection; unknown `options` keys stay ignored per
  `architecture.md` §6.4.
  (f) Build gotcha fixed: `add_issue`/`get_non_negative_int` definitions
  were moved out of config.cpp's anonymous namespace when exported (header
  declarations + anonymous-namespace definitions made unqualified calls
  ambiguous).

## 6. Interface/schema decisions

- Canonical schemas **created and example-verified in Phase 1**:
  `schemas/{config,trace,job,geometry,event,summary,state,experiment}.schema.json`.
  Concrete examples and prose rules: `architecture.md` §6. No schema may
  exist in two places.
- Limits (canonical, `docs/architecture.md` §12): trace 0–100,000 addresses;
  width 4–64 bits; block power of two 1–128 B; capacity power of two ≤ 2²⁰ B;
  assoc power of two 2–capacity/block; seed uint32; per-access state
  snapshots only for traces ≤ 2,000 accesses AND
  snapshots × total cache lines ≤ 2,000,000 (Phase 3 budget); subprocess
  timeout 30 s.
- Worked reference examples E1–E6 with hand-verified expected numbers:
  `architecture.md` §13 (E1 1 miss/4 hits; E2 5 misses/4 evictions; E3 LRU
  1/4/2 vs FIFO 2/3/1, AMAT 17.00 vs 13.00; E4 fully-assoc index null;
  E5 RANDOM determinism (seed-12345 E3 outcome pinned exactly, D-15);
  E6 invalid-first fill). These are the published test
  expectations — never invent others.

## 7. Implemented functionality

- **Phases 1–10 are implemented and verified** (DELIVERED, 2026-10-25;
  this snapshot supersedes the Phase-1–9-only summary that stood here
  before Phase 10).
  Phase 1: engine build with zero warnings; `version` mode plus the full CLI
  contract (usage envelopes, exit codes 0/2/4); all eight canonical schemas
  created and example-validated; requirements installed. Phase 2:
  authoritative configuration validation (every rule of `prd.md` §5, all
  problems collected into `error.details`) and `--mode geometry` with exact
  `architecture.md` §6.3 geometry output. Phase 3: `--mode simulate` — all
  three organizations with the exact §8 semantics (lowest-index invalid-way
  fill, LRU victims, forced single-way direct eviction), full
  `event.schema.json`-valid events with `policy_meta` and the §10
  explanation templates, final state, optional per-access snapshots under
  the §12 caps, staged job validation, engine-asserted invariants. Phase 4:
  FIFO (hits never reorder insertion) and seeded RANDOM (`std::mt19937`,
  one draw per valid-line eviction, victim = draw % ways_in_set; the
  seed-12345 outcome is pinned exactly per D-15), complete summaries
  (`amat`, `trace_sha256`, `replacement_meta`) that validate against
  `summary.schema.json`, and policy-aware state ranks. Phase 5:
  comprehensive verification — 729-check engine suite across 17 sections
  (full E1–E6 tables incl. the pinned seed-7 E5 walk, engine-level
  validate_trace unit tests, boundary and abuse cases, the 100k-access
  performance gate, determinism matrix, seeded property sweep) with the
  performance root cause fixed (D-20). Phase 6: Bot 1 — `bots/trace_bot.py`
  with the four §6.8 patterns (sequential, repeated, conflict with the
  base-block rounding rule, manual import), strict E_*-coded validation,
  deterministic parameter-derived names, geometry via the engine through
  `bots/engine_client.py` (D-6), and 38 tests including real-engine
  integration. Phase 7: Bot 2 — `bots/experiment_bot.py` with the two
  experiment modes (policy comparison with the direct-mapped refusal;
  organization comparison on a set-associative base with LRU wherever a
  policy exists), one-variable-at-a-time run matrices, stale-seed
  stripping, deterministic `summary_text` with the best-hit-rate sentence
  and org-mode caveat, reproducibility records (`experiment.schema.json`-valid)
  and the deterministic `save_report` writer; `engine_client` gained
  `run_simulate`. Phase 8: integration — engine_client hardened (retry
  taxonomy: transient spawn/timeout/crash failures retried up to 2 times,
  error envelopes terminal; exit-code/envelope consistency check), four
  sample traces in `traces/` (json + manual txt), and
  `tests/test_integration.py` proving the full scripted workflow (Bot 1 →
  engine → Bot 2 → saved report) reproducibly, with error paths and
  AC-6/7/9/12 through the Python path. Phase 9: the Streamlit UI per
  `design.md` — sidebar configuration with power-of-two selects and a
  thin early-validation mirror, Simulator/Experiments/Automated
  workflow/Help tabs, session-state flow that never re-runs the engine on
  widget interaction, metric cards / event log / state grid / charts all
  rendering engine output verbatim, and the scripted browser walkthrough
  reproducing the §14 demonstration exactly (evidence: walkthrough record
  + screenshots in `docs/`). Phase 10: delivery — fresh-setup
  verification executed verbatim, the §14 demonstration run from the UI
  with its record archived (`docs/demo-record.json`), AC-1…AC-12 mapped
  to evidence (table below), and the README completed. **Nothing remains
  unimplemented: all ten phases are `DONE` and the project is
  delivered.** Status per capability:

| Capability | Status | Evidence |
|---|---|---|
| Engine build | **DONE (Phase 1)** | AC-P1: `mingw32-make -C engine all` zero warnings; exe produced |
| `version` mode + CLI contract | **DONE (Phase 1)** | AC-P2/P3: exact envelope; usage errors exit 2; at Phase 1 time the `simulate` stub exited 4 `E_INTERNAL` (historical — `simulate` is real since Phase 3); `--out` behavior verified |
| Canonical schemas (8 files) | **DONE (Phase 1, tightened in Phase 2/D-17)** | AC-P4: every schema validates ≥1 concrete example (13 positive/negative pytest cases) |
| Python environment | **DONE (Phase 1)** | AC-P5: `pytest` green; `import streamlit` works (1.66.1) |
| Config validation + geometry (`--mode geometry`) | **DONE (Phase 2)** | AC-P2.1–P2.4: every `prd.md` §5 rule tested with exact field/problem/received; E1–E4 geometries exact; all problems collected; `tag_bits < 0` rejected naming the conflict; 154 engine checks + 10 geometry pytest cases |
| Simulation (3 orgs) (`--mode simulate`) | **DONE (Phase 3)** | AC-P3.1–P3.5: E1/E2/E3-LRU/E4/E6 walked per-access with exact events and explanations; final state + LRU ranks; snapshots incl. caps; empty trace safe; invariants engine-asserted; 343 engine checks + 13 simulate pytest cases |
| Policies (LRU/FIFO/RANDOM) + stats/AMAT | **DONE (Phase 4)** | AC-P4.1–P4.5: E3 FIFO walk 2/3/1 vs LRU 1/4/2; pinned RANDOM seed-12345 outcome exact (D-15); E5 byte-identical determinism (engine + subprocess); AMAT 17.00/13.00/13.00; `summary` schema-valid; 435 engine checks + 9 policy/stats pytest cases |
| Engine verification suite | **DONE (Phase 5)** | AC-P5.1–P5.4: E1–E6 field-by-field incl. pinned seed-7 E5 walk; boundary + abuse cases (max address, 100k/100,001, validate_trace unit tests); determinism matrix (LRU/FIFO/R7/R8 byte-identical); seeded property sweep (28 config×trace runs); 100k gate 0.0806 s; 729 checks / 0 failures with per-section counts |
| Bot 1 | **DONE (Phase 6)** | AC-P6.1–P6.5: all four §6.8 patterns with exact hand-computed addresses (incl. base-block rounding 3,7,11,15 → 6,14,22,30); determinism proven by full-response equality; width/limit rejections E_TRACE_INVALID/E_LIMIT; manual E3 import exact; fully-assoc warning path; engine error pass-through; 35 unit + 3 real-engine integration tests |
| Bot 2 | **DONE (Phase 7)** | AC-P7.1–P7.5: E3 policy comparison reproduces LRU 1/4/2 (AMAT 17.00), FIFO 2/3/1 (13.00), RANDOM seed-12345 2/3/1 (13.00, rng_draws 1); direct-mapped refusal; record schema-valid; summary_text deterministic + exact; org comparison on E2 with LRU-where-applicable + caveat; 25 unit + 4 real-engine integration tests (29 collected — verified by `pytest --collect-only`, reconciled 2026-10-25) |
| Integration | **DONE (Phase 8)** | AC-P8.1–P8.4: retry taxonomy proven (validation terminal after 1 call; transient retried 3 attempts, success-after-transient); missing engine actionable; full workflow reproducible (byte-identical summaries on re-run, report saved); AC-6/7/9/12 through the Python path; sample traces json/txt agree |
| Streamlit UI | **DONE (Phase 9)** | AC-P9.1–P9.4: §14 demo reproduced exactly in the browser (LRU 1/4/2 AMAT 17.00; FIFO 2/3/1 13.00; RANDOM 2/3/1 13.00 seed recorded; summary text exact); engine-error contract verified; workflow statuses incl. forced failure leaving results visible; design checklist verified in captures (`docs/phase9-walkthrough.md` + `docs/screenshots/`) |
| E2E + delivery | **DONE (Phase 10)** | AC-P10.1–P10.4: fresh-setup path executed verbatim (clean build/, requirements reinstall, zero-warning rebuild, all suites green); §14 demo executed from the UI with the record archived to `docs/demo-record.json` and verified against §14; README complete; AC-1…AC-12 evidence mapped (table above) |

### prd.md acceptance-criteria evidence map (final, Phase 10)

| AC | Claim | Verified by |
|---|---|---|
| AC-1 | Repeated block: one miss then hits | engine `simulate_direct` (E1 walk); UI demo step 3 |
| AC-2 | Direct-mapped conflict evictions predictable | engine `simulate_direct_conflict` (E2 walk, corrected final state) |
| AC-3 | LRU vs FIFO differ on the verified trace | engine `simulate_fifo` + `simulate_lru` (E3 walks); Phase 7 integration; UI experiments table |
| AC-4 | Fully-associative: one set, zero index bits, `index: null` | engine `simulate_fully_assoc` (E4 walk) |
| AC-5 | RANDOM fixed-seed reproducible | engine `simulate_random` (E5 byte-identical double-runs) + pytest byte-identical subprocess runs |
| AC-6 | Invalid config rejected, useful message | engine `config_invalid` (89 checks); `test_invalid_config_surfaces_details` |
| AC-7 | Address outside width rejected with max stated | engine `trace_validation_unit`; `test_address_over_width_surfaces_twice_over` |
| AC-8 | Miss fills an invalid line before any eviction | engine `simulate_lru` (E6) + architecture.md §9 invariants asserted per run |
| AC-9 | Empty/malformed traces safe | engine empty-trace + `trace_validation_unit`; pytest/integration empty + malformed cases |
| AC-10 | Bots complete the workflow; UI shows engine outputs | Phase 8 `TestFullWorkflow` (reproducible record); Phase 9 walkthrough (UI renders verbatim engine numbers) |
| AC-11 | Invariants hold on every run | engine-asserted (E_INTERNAL on violation) + `property_sweep` (155 checks) |
| AC-12 | Same version+config+trace+seed ⇒ identical bytes | `determinism_matrix` (LRU/FIFO/R7/R8) + pytest/integration determinism tests |

## 8. Tests executed and actual results

- 2026-10-24 (documentation phase): g++ smoke test (`-std=c++14`, trivial
  program) — **pass**. `curl -I` GitHub raw (nlohmann/json) — **HTTP 200**.
- 2026-10-24 (Phase 1):
  - `mingw32-make -C engine all` — **pass**: compiled `src/main.cpp` with
    `-std=c++14 -O2 -Wall -Wextra -Iinclude -isystem third_party`, zero
    warnings, produced `build/cache_sim.exe` (AC-P1).
  - `mingw32-make -C engine test` — **pass**: `[section] version / summary:
    2 checks, 0 failures`.
  - `build/cache_sim.exe --mode version` — **pass**: exit 0, output
    `{"engine":{"name":"cache_sim","version":"0.1.0"},"ok":true}` (AC-P2).
  - Manual CLI checks — **pass**: unknown flag / missing mode / unknown mode
    → exit 2 + `E_USAGE` envelope incl. usage line; `--mode simulate
    --in <missing>` → exit 2 + `E_USAGE`; `--mode simulate|geometry` with a
    readable input → exit 4 + `E_INTERNAL` naming the implementing phase;
    `--out <file>` → file receives envelope, stdout empty (AC-P3).
  - `python -m pip install -r requirements.txt -r requirements-dev.txt` —
    **pass** (streamlit 1.66.1 installed; others already satisfied).
  - `python -m pytest tests -q` — **pass: 21 passed, 2 warnings in 1.77 s**
    (warnings = jsonschema RefResolver deprecation only). Two initial
    failures were found and fixed at the root: (1) config schema's
    RANDOM-requires-seed `if` was vacuously true when `policy` was absent —
    fixed by adding `required: ["policy"]` to the `if`; (2) a negative test
    asserted a rule the contract does not state (seed with non-RANDOM) —
    replaced with the real rule (RANDOM with `seed: null` is rejected).

  - 2026-10-24 (pre-Phase-2 consistency pass, after documentation/fixture
    corrections): `mingw32-make -C engine clean && mingw32-make -C engine
    all` — **pass**, zero warnings; `mingw32-make -C engine test` — **pass**
    (2 checks, 0 failures); `build/cache_sim.exe --mode version` — **pass**
    (exact envelope, exit 0); `python -m pytest tests -q` — **pass: 21
    passed** in 1.80 s. Phase 1 acceptance criteria re-verified and still
    hold; no test was skipped.

  - 2026-10-24 (final pre-Phase-2 pass, after D-15/D-16 corrections and the
    fixture update): `mingw32-make -C engine clean && mingw32-make -C engine
    all` — **pass**, zero warnings; `mingw32-make -C engine test` — **pass**
    (2 checks, 0 failures); `build/cache_sim.exe --mode version` — **pass**
    (exact envelope, exit 0); `python -m pytest tests -q` — **pass: 21
    passed** in 1.92 s (warnings = jsonschema RefResolver deprecation only).
    Phase 1 acceptance criteria still hold; nothing skipped; Phase 2 remains
    `NOT STARTED`.

  - 2026-10-24 (documentation-status correction pass: §7/§9 rewording,
    Phase 1 status annotation updated — no code, schema, or fixture changes):
    `python -m pytest tests -q` — **pass: 21 passed** in 1.74 s; stale-phrase
    sweep clean; Phase 1 `DONE` and Phase 2 `NOT STARTED` agree across
    `tasks.md` and this file.

  - 2026-10-24 (Phase 2):
    - `mingw32-make -C engine clean && mingw32-make -C engine all` —
      **pass**, zero warnings (app + test runner compile `config.cpp`,
      `geometry.cpp`).
    - `mingw32-make -C engine test` — **pass: 154 checks, 0 failures**
      across sections version / geometry_valid / config_invalid; covers
      every `prd.md` §5 rule with exact field/problem/received assertions,
      E1–E4 geometries, boundaries (block 1, capacity = block, assoc =
      capacity/block, width 4 and 64 incl. max_address = 2^64−1 without
      overflow, capacity 2^20), collect-all behavior, and the text-parsed
      unsigned-integer regression case.
    - Manual geometry-mode runs — **pass**: E3 config via stdin → exit 0,
      envelope with `echo` + exact §6.3 geometry (sets 2, offset 1, index 1,
      tag 6, max 255); direct config → `associativity: null`, sets = lines;
      invalid config → exit 3, `E_CONFIG_INVALID`, details
      `{field, problem, received}`.
    - `python -m pytest tests -q` — **pass: 30 passed, 2 warnings in ~2 s**
      (warnings = jsonschema RefResolver deprecation only). New:
      TestGeometryMode (10 cases incl. stdin input, malformed JSON →
      `E_JOB_INVALID`, all-problems-collected, D-17 rejections, geometry
      validated against `geometry.schema.json`) and 2 new schema negatives.
      One test bug found and fixed at the root: the tag-bits test asserted
      the conflict text in `error.message`, but the envelope design keeps
      the summary in `message` and the conflict in `details[].problem`
      (architecture.md §5.3) — test corrected, engine unchanged.

  - 2026-10-24 (post-Phase-2 documentation-status repair — doc-only, no
    code/schema/test changes): `python -m pytest tests -q` — **pass: 30
    passed, 2 warnings in 2.47 s** (warnings = jsonschema RefResolver
    deprecation only). The §11 fallback one-line compile command (which had
    gone stale after Phase 2 added `config.cpp`/`geometry.cpp`) was corrected
    and **verified**: compiles with zero warnings to a temporary output and
    the binary emits the exact §6.2 version envelope; the temp binary was
    removed afterwards. Status sweep: Phase 1/2 `DONE` and Phases 3–10
    `NOT STARTED` agree across `tasks.md` and this file.
  - 2026-10-24 (Phase 3):
    - `mingw32-make -C engine clean && mingw32-make -C engine all` —
      **pass**, zero warnings (`cache.cpp`, `simulator.cpp` added to the
      Makefile's shared library sources).
    - `mingw32-make -C engine test` — **pass: 343 checks, 0 failures**
      across sections version / geometry_valid / config_invalid /
      simulate_direct / simulate_direct_conflict / simulate_lru /
      simulate_fully_assoc / simulate_snapshots_and_empty. E1, E2, E3-LRU,
      E4, and E6 are asserted per access with exact core fields,
      explanations, and policy_meta; LRU ranks, snapshots, the empty trace,
      and direct-mapped forced evictions are covered.
    - Manual simulate runs — **pass**: E1 job via stdin → exit 0 envelope
      with echo/geometry/events/summary/state as specified; invalid jobs →
      staged `E_JOB_INVALID`/`E_CONFIG_INVALID`/`E_TRACE_INVALID`/`E_LIMIT`.
    - `python -m pytest tests -q` — **pass: 43 passed, 2 warnings in ~3 s**
      (warnings = jsonschema RefResolver deprecation only). New:
      TestSimulateMode (13 cases incl. E1/E2/E3-LRU/E4 walks, schema
      validation of real events and state against `event.schema.json` /
      `state.schema.json`, snapshot cap + over-100k `E_LIMIT`s, unknown
      job/trace keys, empty trace). Test-side fixes at the root: the
      simulate-stub test was replaced (simulate is real now); two snapshot
      tests corrected (5 accesses ⇒ 5 snapshots; the 2000-cap test needed a
      width-16 config so trace validation passes before the cap check).
      One compile fix (D-18f) and one spec correction (D-18c, E2 final
      state) found and fixed during the phase.
    - The §11 fallback one-line compile command was updated for the Phase 3
      sources and **verified**: zero warnings to a temporary output, binary
      emits the exact version envelope; temp binary removed.

  - 2026-10-24 (documentation relocation + Phase 3 consistency repair —
    doc-only; no engine, schema, or test changes): the six governing
    documents were moved from the project root into **`docs/`** (no
    duplicates left in the root; root keeps only `README.md`). Reference
    sweep: all cross-references between the six documents are sibling
    citations (`architecture.md §5` style) that resolve within `docs/`;
    `README.md` was updated to repo-relative `docs/*.md` links (all six
    verified to resolve); `docs/memory.md` §1 and `docs/prd.md` §13 now
    carry `docs/` paths; code-path references (`engine/`, `schemas/`,
    `tests/`, `bots/`) are untouched, and no code comment citations were
    rewritten. §6 gained the Phase 3 snapshot serialization budget
    (snapshots × total cache lines ≤ 2,000,000) beside the 2,000-access
    cap; §7 was rewritten as a Phases-1–3 snapshot (superseding the
    Phase-1–2-only text). Verification from the project root:
    `mingw32-make -C engine clean && mingw32-make -C engine all` — **pass,
    zero warnings**; `mingw32-make -C engine test` — **pass: 343 checks,
    0 failures**; `python -m pytest tests -q` — **pass: 43 passed,
    2 warnings in 2.64 s** (warnings = jsonschema RefResolver deprecation
    only). Phase 1–3 `DONE` and Phases 4–10 `NOT STARTED` confirmed
    consistent across `docs/tasks.md` and this file.

  - 2026-10-24 (Phase 4):
    - `mingw32-make -C engine clean && mingw32-make -C engine all` —
      **pass**, zero warnings (`stats.cpp` added; `rng.hpp`/`stats.hpp`
      headers).
    - `mingw32-make -C engine test` — **pass: 435 checks, 0 failures**
      across 13 sections, including: RNG reference draws for seed 12345
      (3992670690, 3823185381 — D-15), SHA-256 canonical vectors, the E3
      FIFO walk (2/3/1 with no reorder on hit), the pinned RANDOM
      seed-12345 walk (2/3/1, evicting block 0 at t4), fills-consume-no-
      draws, E5 determinism double-runs (byte-identical serialized results
      for seeds 7 and 8), AMAT 17.00/13.00/13.00, `amat` null without
      timing, empty-trace AMAT degenerating to `hit_time` (D-19a), and
      `replacement_meta` variants.
    - Subprocess determinism — **pass**: two identical RANDOM seed-12345
      runs produced byte-identical envelopes (`cmp` clean).
    - `python -m pytest tests -q` — **pass: 52 passed, 2 warnings in ~3 s**
      (warnings = jsonschema RefResolver deprecation only). New:
      TestPoliciesAndStats (9 cases: E3 FIFO walk, pinned RANDOM walk,
      `summary` validated against `summary.schema.json`, `trace_sha256`
      cross-checked against Python hashlib, byte-identical subprocess
      determinism, AMAT trio, `amat` null without timing, empty-trace AMAT,
      `replacement_meta` omitted for direct). Two Phase 3 summary-equality
      tests were extended with the Phase 4 summary keys.
    - **Bugs found and fixed at the root:** `parse_and_validate_config`
      did not reset `*out`, leaking `has_policy`/`policy` across reused
      `Config` structs (D-19b) — caught by the `replacement_meta`-omission
      test; plus one test-side config mixup (LRU config passed where FIFO
      was intended).
    - The §11 fallback one-line compile command was updated for the Phase 4
      source list and **verified**: zero warnings to a temporary output,
      binary emits the exact version envelope; temp binary removed.

  - 2026-10-24 (pre-Phase-5 Phase 4 contract check — `amat` omission,
    D-19f): inspected AC-P4.4, `architecture.md` §6.6,
    `schemas/summary.schema.json`, the `build_summary` code, and actual
    engine output, which confirmed the bug: a no-timing run emitted
    `"amat": null`. Fixed the engine (`amat` key omitted entirely), the
    schema (`amat` no longer required; null variant removed), and both
    test layers (key-absence regression tests; no-timing summary
    validated against the tightened schema). `architecture.md` §6.6
    wording sharpened ("omitted entirely — never emitted as null").
    Verification: `mingw32-make -C engine clean && mingw32-make -C engine
    all` — **pass, zero warnings**; `mingw32-make -C engine test` —
    **pass: 435 checks, 0 failures**; `python -m pytest tests -q` —
    **pass: 52 passed, 2 warnings in 2.72 s**. Confirmed by inspecting
    real output: no-timing summary contains no `amat` key; empty trace
    with timing inputs reports `amat.value = 1.0` (`hit_time`). Supplying
    only one timing input remains rejected (Phase 2 both-or-neither rule,
    unchanged). Schema is now stricter, so no specification conflict
    remains.

  - 2026-10-24 (Phase 5):
    - `mingw32-make -C engine clean && mingw32-make -C engine all` —
      **pass**, zero warnings (`textutil.hpp` added; hot-loop string
      building reworked per D-20a).
    - `mingw32-make -C engine test` — **pass: 729 checks, 0 failures**
      across 17 sections, with per-section counts printed (AC-P5.4).
      Verbatim section results:
      `[done] version: 2 checks, 0 failures` / `[done] geometry_valid: 63
      checks, 0 failures` / `[done] config_invalid: 89 checks, 0 failures`
      / `[done] simulate_direct: 55 checks, 0 failures` /
      `[done] simulate_direct_conflict: 34 checks, 0 failures` /
      `[done] simulate_lru: 55 checks, 0 failures` /
      `[done] simulate_fully_assoc: 54 checks, 0 failures` /
      `[done] simulate_snapshots_and_empty: 22 checks, 0 failures` /
      `[done] rng_reference: 3 checks, 0 failures` /
      `[done] sha256_vectors: 2 checks, 0 failures` /
      `[done] simulate_fifo: 25 checks, 0 failures` /
      `[done] simulate_random: 85 checks, 0 failures` /
      `[done] simulate_stats: 24 checks, 0 failures` /
      `[done] trace_validation_unit: 29 checks, 0 failures` /
      `[done] boundaries: 16 checks, 0 failures` /
      `[done] determinism_matrix: 16 checks, 0 failures` /
      `[done] property_sweep: 155 checks, 0 failures`.
    - AC-P5.3 measured twice: `[perf] 100000-access simulate: 0.0770 s`
      then `0.0806 s` (post-fix; pre-fix measurement was 0.9931 s).
    - `python -m pytest tests -q` — **pass: 52 passed, 2 warnings in ~3 s**
      (warnings = jsonschema RefResolver deprecation only).
    - Findings fixed at the root during the phase: the performance root
      cause (D-20a), `validate_trace` never populating `trace.name`
      (D-20b), and one hand-derivation error in the new 100k eviction
      expectation (49,996, not 49,999 — corrected against the walk).

  - 2026-10-24 (pre-Phase-6 E5 reference check): verified that Phase 5
    preserved the original seed-12345 E5 reference everywhere it is
    pinned — `architecture.md` §13 E5 (seed-12345 paragraph intact; the
    seed-7 walk was appended as an additional pin, not an overwrite),
    `docs/tasks.md` AC-P4.2 (unchanged), `docs/memory.md` D-15 (intact),
    the engine tests (`rng_reference` draws 3992670690/3823185381; the
    `simulate_random` seed-12345 walk with its t4 eviction, explanation,
    and `policy_meta.seed`; determinism double-runs for seeds 7/8), and
    pytest (`test_pinned_random_seed_12345`,
    `test_random_determinism_byte_identical` — both pass). Seed-7/seed-8
    coverage is additive. Verification: `mingw32-make -C engine clean &&
    mingw32-make -C engine all` — **pass, zero warnings**;
    `mingw32-make -C engine test` — **pass: 729 checks, 0 failures**
    (`[perf] 0.0830 s`); `python -m pytest tests -q` — **pass: 52 passed,
    2 warnings in 2.62 s**; `pytest -k "pinned or determinism"` — **2
    passed**. No fixes were needed; no conflicts found.

  - 2026-10-24 (Phase 6):
    - `mingw32-make -C engine clean && mingw32-make -C engine all` —
      **pass**, zero warnings; `mingw32-make -C engine test` — **pass:
      729 checks, 0 failures** (engine untouched by Phase 6; standard
      regression gate).
    - `python -m pytest tests -q` — **pass: 90 passed, 2 warnings in ~3 s**
      (warnings = jsonschema RefResolver deprecation only). New:
      `tests/test_trace_bot.py` with 38 tests — exact hand-computed
      addresses for all four patterns (incl. the AC-P6.1 rounding case
      blocks 3,7,11,15 → addresses 6,14,22,30), full-response determinism
      equality, width (`E_TRACE_INVALID` with the max stated) and limit
      (`E_LIMIT`) rejections for every pattern, the manual E3 import
      (`0 # A\n4 # B\n0\n8 # C\n4` → `[0,4,0,8,4]`) with hex/comment/
      blank-line handling and line-numbered collect-all errors, the
      fully-associative conflict warning path, engine error pass-through,
      request/params shape rejections, and 3 real-engine integration
      tests (fetch_geometry matches the published fixture; generate works
      end-to-end; bad configs surface `E_CONFIG_INVALID` with details).
      `tests/conftest.py` added for import robustness. No engine changes
      were needed; no failures remained after the initial run.

  - 2026-10-25 (Phase 7):
    - `mingw32-make -C engine clean && mingw32-make -C engine all` —
      **pass**, zero warnings; `mingw32-make -C engine test` — **pass:
      729 checks, 0 failures** (engine untouched by Phase 7; standard
      regression gate).
    - `python -m pytest tests -q` — **pass: 119 passed, 4 warnings in ~3 s**
      (all 4 = the known jsonschema RefResolver deprecation). New:
      `tests/test_experiment_bot.py` with 29 tests — stubbed unit tests
      for the run matrices (one-variable-at-a-time, stale-seed stripping),
      the direct-mapped refusal, seed requirements, all three
      summary-text template forms (single winner / 2-way tie / 3-way tie),
      trace and request validation, report persistence, and 4 real-engine
      integration tests (E3 policy comparison reproduces LRU 1/4/2 AMAT
      17.00, FIFO 2/3/1 13.00, RANDOM seed-12345 2/3/1 13.00 with
      rng_draws 1; record validates against `experiment.schema.json`; E2
      organization comparison with 5/4/0 direct counts and the caveat
      sentence; report round-trip).
    - Failures during the phase, fixed at the root: the best-hit-rate
      sentence used the seed-suffixed RANDOM label (moved to short labels,
      D-22d), and the bot-level config shape check demanded
      `associativity` unconditionally, which blocked the direct-mapped
      refusal (scope narrowed, D-22f). One pytest warning added by the new
      jsonschema import in the integration test (same known deprecation).

  - 2026-10-25 (Phase 8):
    - `mingw32-make -C engine clean && mingw32-make -C engine all` —
      **pass**, zero warnings; `mingw32-make -C engine test` — **pass:
      729 checks, 0 failures** (engine untouched by Phase 8; standard
      regression gate).
    - `python -m pytest tests -q` — **pass: 135 passed, 4 warnings in ~4 s**
      (warnings = the known jsonschema RefResolver deprecation). New:
      `tests/test_integration.py` with 16 tests — retry taxonomy
      (validation errors terminal after exactly 1 attempt; transient
      failures retried to 3 attempts then `E_INTERNAL`; success after one
      transient), missing-engine actionability through the bot boundary,
      the full scripted workflow (Bot 1 conflict trace → engine → Bot 2
      policy comparison → report saved) with byte-identical summaries on
      re-run, sample-trace json/txt agreement, the E1 sample asserted
      against the published Phase-3 summary, determinism through the
      Python path, and AC-6/7/9/12 error paths.
    - Failures during the phase, fixed at the root: the generated sample
      `.txt` files had an uncommented description line (manual parser
      rightly rejected it — files regenerated with `#` prefixes), and one
      test expected Bot 2's `trace.addresses[0]` detail-field prefix where
      the engine correctly reports trace-relative `addresses[0]`
      (architecture.md 5.3) — test corrected.
    - One control-flow bug caught by review before any run: the retry loop
      initially let transient exceptions escape instead of retrying —
      fixed and covered by the counting-fake tests.

  - 2026-10-25 (Phase 9):
    - `python -m pytest tests -q` — **pass: 135 passed, 4 warnings in ~4 s**
      (no engine/bot changes; standard gate). `mingw32-make -C engine
      clean && all` — **zero warnings**; `engine test` — **729 checks,
      0 failures**.
    - Scripted browser walkthrough (Streamlit 1.66.1, headless, launched
      from `ui/`): full §14 demonstration reproduced in the real UI —
      LRU simulation 1 hit / 4 misses / 2 evictions / 20.00% / AMAT
      17.00; policy comparison table LRU 1/4/2 17.00, FIFO 2/3/1 13.00,
      RANDOM (seed 12345) 2/3/1 13.00 with the exact summary text;
      automated workflow all four steps DONE with the report saved to
      `reports/`; forced failure (manual paste of 300 on an 8-bit width)
      showed `E_TRACE_INVALID` with the line detail while earlier results
      stayed visible; Help tab rendered. Evidence:
      `docs/phase9-walkthrough.md` + `docs/screenshots/09-*.png`
      (simulator-top, simulator-metrics, events-state, experiments,
      workflow, error-state, help).
    - UI defects found by the walkthrough and fixed at the root: a
      `StreamlitDuplicateElementId` crash (workflow seed input vs the
      Experiments seed input — unique `key`s), the state-grid Styler
      misalignment (style frame missing the "Set" index labels),
      trace-load errors blanking earlier results (now preserved per
      design.md 7), pill/confirmation wording and the AMAT metric
      truncation (unit moved to the label). Each fix was followed by a
      server restart and re-run of the affected steps.

  - 2026-10-25 (Phase 10 — delivery):
    - Fresh-setup verification (AC-P10.1), executed verbatim per the
      README: `rm -rf build` → `pip install -r requirements.txt
      -r requirements-dev.txt` (clean resolve, confirming the requirement
      files are complete) → `mingw32-make -C engine all` — **zero
      warnings** → `mingw32-make -C engine test` — **729 checks,
      0 failures** → `python -m pytest tests -q` — **135 passed,
      4 warnings in 3.42 s**.
    - §14 demonstration executed end-to-end from the UI (browser-driven:
      width 8 → E3 sample → simulation → policy comparison seed 12345 →
      save report). Observed in the UI: LRU 1/4/2 AMAT 17.00, FIFO 2/3/1
      13.00, RANDOM (seed 12345) 2/3/1 13.00 with `rng_draws` 1, summary
      text exact. Record archived to `docs/demo-record.json` and
      programmatically verified against §14 (AC-P10.3); delivery capture
      `docs/screenshots/10-demo-delivery.png`.
    - README completed (AC-P10.4): prerequisites, verified setup/build/
      test commands, two-minute demo walkthrough, limits, repository
      layout, links to the governing documents.
    - Hygiene: repo inventory clean (root holds only README + the
      documented directories; caches are regenerable Python artifacts);
      demo record archived; no code changes in this phase.

  - 2026-10-25 (final documentation-only cleanup — no engine, schema, or
    test changes): §3 replaced the overlapping/truncated Phase 6/Phase 9
    inventory paragraphs with one final repository inventory (dated
    2026-10-25, delivered state); the duplicated D-19(f) `amat`-omission
    note was deduplicated (one entry kept); §11 dropped the obsolete
    `python -m streamlit run ui/app.py` line (the verified launch command
    is `cd ui && python -m streamlit run app.py`); README resource limits
    gained the snapshot serialization budget
    (snapshots × total cache lines ≤ 2,000,000). Verification: evidence
    files (`docs/demo-record.json`, `docs/phase9-walkthrough.md`, all
    screenshots) exist; all README/documentation links resolve; D-19(f)
    appears exactly once; `python -m pytest tests -q` — **pass: 135
    passed, 4 warnings in 3.70 s**. All ten phases remain `DONE`.

  - 2026-10-25 (final memory.md consistency pass — documentation only; no
    engine, schema, or test changes): §7's "Still unimplemented: Phase 10"
    sentence replaced with the delivered Phases 1–10 closing statement;
    §9 rewritten to the delivered state (bots, integration suite, UI all
    exist; Phase 5 verification has run — only design-intentional notes
    and §10 deferrals remain as limitations); §11 heading/dated to the
    delivered state with command descriptions matched to §8 (launch
    convention `cd ui && python -m streamlit run app.py` kept); D-7
    clarified that both required Bot 2 modes were implemented and
    verified in Phase 7 while preserving the historical note; a full-file
    sweep found no remaining current-tense contradictions ("not yet
    implemented", "do not exist yet", "has not run yet", stale
    Phase 1–4/1–3 foundation claims — all zero hits). Verification:
    the §11 fallback one-line compile (complete six-source list) —
    **pass, zero warnings**, exact version envelope, temp binary removed;
    `python -m pytest tests -q` — **pass: 135 passed, 4 warnings in
    3.55 s**. All ten phases remain `DONE`.

  - 2026-10-25 (final memory.md micro-corrections — documentation only):
    §11's fallback-compile caption corrected from "all six library
    sources plus main" to "all five library sources plus main" (the
    command lists six `.cpp` files total: five library sources plus
    `main.cpp`; the command itself unchanged); §7's Bot 2 row corrected
    from "26 unit + 4" to "25 unit + 4 real-engine integration tests
    (29 collected)" to match §8 — evidence: `python -m pytest
    tests/test_experiment_bot.py --collect-only -q` → **29 tests
    collected** (TestPolicyComparisonUnit 10, TestOrganizationComparisonUnit 4,
    TestRequestAndTraceValidation 9, TestSaveReport 2 = 25 unit; +
    TestRealEngineIntegration 4). Regression: `python -m pytest tests -q`
    — **pass: 135 passed, 4 warnings in 3.41 s**. All ten phases remain
    `DONE`.

  - 2026-10-25 (final codebase audit — three confirmed defects fixed, full
    regression green): baseline re-verified first (729 checks, 135 passed,
    zero warnings), then a repository-wide sweep (no TODO/debug/placeholder
    code; all `reports/*.json` parse; traces/schemas/docs consistent).
    Fixes: (1) `ui/components.py` — the event table showed the FIRST 500
    rows while `rules.md` §12 requires the LATEST ~500; now
    `frame.tail(500)` with the caption "Showing the most recent 500
    rows"; **verified in the running app** with a real 600-access Bot 1
    trace (table starts at n=101; capture
    `docs/screenshots/audit-event-table-tail.png`). (2)
    `engine/src/cache.cpp` — `verify_invariants` now also asserts
    architecture.md §9 invariant 5's stamp property (distinct
    `stamp_used`/`stamp_insert` among a set's valid lines — ties would
    make LRU/FIFO victim selection ambiguous); the check runs on every
    simulate across the whole suite. (3) `docs/memory.md` §3 — inventory
    now lists `projdemo.md`. E3/§14 numbers re-confirmed unchanged via the
    suites. Post-fix regression: `mingw32-make -C engine clean && all` —
    **zero warnings**; `mingw32-make -C engine test` — **729 checks,
    0 failures**; `python -m pytest tests -q` — **135 passed, 4 warnings
    in 3.45 s**. All ten phases remain `DONE`.

  - 2026-10-27 (dark mode — post-delivery enhancement, presentation
    only): `python -m pytest tests -q` — **pass: 167 passed, 4 warnings**
    (15 new theme tests: palette completeness, WCAG contrast, CSS
    bundles, presentation-only separation, E3 identical across themes).
    `mingw32-make -C engine clean && all` — **zero warnings**;
    `mingw32-make -C engine test` — **729 checks, 0 failures**. Browser
    verification: Light→Dark→Light switching; dark simulation (E1 sample
    4 hits/1 miss/AMAT 5.00 verified on screen); dark 3D playback to 3/5;
    light restoration confirmed; oversize/empty-trace captions intact.
    Engine untouched this round (D-26 fix was Phase-10-audit). See
    `docs/screenshots/theme-*.png`.

  - 2026-10-27 (reliability audit — four defects fixed, D-28): baseline
    re-verified first (**167 passed**; engine **729 checks, 0 failures**),
    then the scripted audit matrix and the incident reproduction. Post-fix
    regression: `python -m pytest tests -q` — **172 passed, 4 warnings**
    (5 new tests: 3 Bot 2 `fixed`/incomplete-associativity regressions
    including the incident end-to-end, plus the manual-issue truncation
    and the sample/error-path additions); `mingw32-make -C engine test` —
    **729
    checks, 0 failures**; `mingw32-make -C engine all` — up to date (no
    C++ changes; zero-warning state unchanged). Browser verification in
    the running app: the incident workflow (fully associative 16/16,
    width 13, FIFO, blocks 8 × passes 11, seed 5457) completes all four
    steps DONE with the report saved; Simulator trace-generate/simulate
    (8 accesses, 7 evictions, FIFO explanation); 3D view stepped to 2/8
    with counters/scrubber/log consistent; Light→Dark→Light with results
    unchanged; malformed sample file → `E_TRACE_INVALID` card with prior
    results preserved; Experiments policy comparison + Save report.
    Engine C++ untouched this round.

  - 2026-10-27 (adversarial reliability pass, D-29): baseline re-verified
    first (**172 passed**; engine **729 checks, 0 failures**). Then the
    differential/metamorphic/adversarial campaign (D-29 for details).
    Post-fix regression: `python -m pytest tests -q` — **194 passed, 4
    warnings** (22 new tests; `tests/test_app_sequences.py` adds the
    project's first AppTest-level UI coverage); `mingw32-make -C engine
    test` — **729 checks, 0 failures**; `mingw32-make -C engine all` —
    rebuilt clean (engine fix), zero warnings. Browser re-verification
    after all changes: the D-28 incident workflow (fully associative
    16/16, width 13, FIFO, blocks 8 × passes 11, seed 5457) completes
    all four steps DONE with the report saved; a normal 32-access
    simulation (24 hits / 8 misses / 7 evictions / AMAT 6.00 — hand
    checked); 3D playback stepped to 2/32 with consistent counters;
    Light→Dark→Light with metrics intact.

  - 2026-10-29 (final project-wide verification + `projdemo.md` rewrite,
    D-31): evidence-based re-verification of the delivered state with no
    code changes. Baseline: `python -m pytest tests -q` — **202 passed,
    4 warnings** (202nd-test state incl. the atomicity tests; warnings are
    the known pytest-asyncio/jsonschema deprecations); `mingw32-make -C
    engine test` — **729 checks, 0 failures across 17 sections** (100k-
    access simulate 0.083 s). From-scratch `clean` + `all` rebuild verified
    in BOTH Git Bash and PowerShell (zero warnings, `build/cache_sim.exe`
    produced; PowerShell also verified for `pytest`, the UI launch, and
    `--server.port`). Independent checks (scratch scripts, not committed):
    31 direct engine-CLI assertions reproducing E1–E6 (incl. exact E3 LRU
    per-access explanations, E5 seed-7 final state, geometry fields,
    error-envelope shapes and the empty-trace/null-rates contract), and 40
    end-to-end Bot 2 assertions (policy comparison byte-identical to
    `docs/demo-record.json` incl. `summary_text`, microsecond `experiment_id`,
    idempotent re-save, conflicting-destination refusal leaving the original
    byte-identical, org-comparison caveat, refusals, schema validation).
    Live browser walkthrough of the full demo sequence: startup/empty
    states, sample load, E3 LRU metrics (5/1/4/2, 20.00%, AMAT 17.00),
    event log + state grid captions, 3D view counters matching engine
    events during stepped playback, Light→Dark→Light (metrics intact; 3D
    resets per D-27), policy comparison table with bolded best rates,
    "Save report" writing a microsecond-id file, automated workflow with
    four DONE steps (conflict-4b-set0-p1: 4 accesses, 0 hits, 2 evictions,
    AMAT 21.00 — hand checked), E_TRACE_INVALID error card for an invalid
    manual paste with earlier results preserved, and the invalid-config
    sidebar message with disabled buttons. Static checks: pyflakes (F)
    clean over bots/ui/tests; the only lint findings are the documented
    accepted-style items (B904 chains, B905 zip) — ruff's default full
    rule set (v0.16, no project config) reports 40 style-only findings and
    is NOT the project gate. `docs/projdemo.md` was rewritten end-to-end
    from this verified evidence (D-30 id format, theme behavior, D-25 3D
    limits/fallbacks, current test counts — the previous copy still said
    "135 tests" and omitted the theme). No defects found; no source file
    modified; the pre-existing working-tree changes and the two stray
    untracked files (`imulator"`, `tatus --short`) were left untouched.

  - 2026-10-27 (report-persistence closure, D-30): collision reproduced
    with a controlled clock, then fixed and regression-tested. Focused
    run of all seven prior-fix test groups plus the new
    `TestReportIdentity` — **34 passed**. Final: `python -m pytest
    tests -q` — **199 passed, 4 warnings**; `mingw32-make -C engine
    test` — **729 checks, 0 failures**; `mingw32-make -C engine all` —
    up to date (no engine changes this round). The workflow's
    report-save path (now writing microsecond-precision ids) is
    exercised end-to-end against the real engine and real `reports/`
    directory by the AppTest workflow-sequence tests (both green), and
    the Experiments tab's real-engine schema validation covers the new
    id format (`test_record_validates_against_schema`). The audit-2
    browser session above predates D-30; no UI-facing rendering changed
    in this round (only the save-button guard and id text).

No test result may be claimed without being recorded in this section.

## 9. Known bugs and unresolved issues

- **No known bugs. All ten phases are `DONE` and verified** — the engine
  (full contract from `prd.md`, 729-check verification suite incl. the
  Phase 5 boundary/performance sweeps at the 100,000-address limit), both
  bots, the hardened integration layer (retry taxonomy, reproducible
  workflow), the browser-verified Streamlit UI, and the delivery evidence
  (§7/§8) are all in place. Known limitations of the delivered state,
  none blocking and none contradicting the acceptance criteria:
  - error envelopes carry a summary in `message`; the actionable per-field
    text lives in `error.details[].problem`, so consumers (bots/UI) must
    render the details (architecture.md §5.3) — by design;
  - the D-17 rule that inapplicable fields (`associativity` outside
    set-associative, `seed` outside RANDOM) must be null or absent is
    stricter than the original "required iff" wording — intentional,
    documented in `architecture.md` §6.1;
  - UI operational notes (D-24): Streamlit caches imported modules until
    the server restarts, and full-page screenshots of the app
    double-render (viewport captures are the evidence convention).
- Explicitly deferred work (§10, all optional and outside `prd.md`
  scope): Bot 2 parameter sweeps, UI config save/load, per-access state
  animation.
- Record bugs here with: symptom, root cause, fix, regression test reference.

## 10. Decisions deliberately deferred

- Parameter-sweep experiment mode for Bot 2 (D-7) — only if time permits;
  requires a one-variable-at-a-time justification like the other modes.
- Config file save/load in the UI — not required by `prd.md`; do not add
  without a stated requirement.
- Per-access cache-state animation — **V1 implemented post-delivery**
  (the "Cache Machine" 3D view; see D-25). Still deferred: the V2/V3
  refinements (tag/index/offset inspector panels, camera presets per
  organization, running hit-rate overlay, report export).

## 11. Latest verified working commands

All verified in the delivered state (latest full verification 2026-10-25,
Phase 10 fresh-setup run — see §8 for every recorded result):

```bash
mingw32-make -C engine all          # builds build/cache_sim.exe (zero warnings)
mingw32-make -C engine test         # 729 engine checks across 17 sections
build/cache_sim.exe --mode version  # exit 0, exact §6.2 envelope
build/cache_sim.exe --mode geometry --in config.json   # geometry envelope / E_CONFIG_INVALID
build/cache_sim.exe --mode simulate --in job.json   # full result envelope
python -m pytest tests -q           # 135 passed (see §8 for the latest recorded run)

# UI (from the ui/ directory so ui/.streamlit/config.toml applies):
cd ui && python -m streamlit run app.py
```

Fallback one-line engine compile (complete final source list — all five
library sources plus main; verified 2026-10-25; per `architecture.md` §4):

```bash
g++ -std=c++14 -O2 -Wall -Wextra -Iengine/include -isystem engine/third_party engine/src/main.cpp engine/src/config.cpp engine/src/geometry.cpp engine/src/cache.cpp engine/src/simulator.cpp engine/src/stats.cpp -o build/cache_sim.exe
```

## 12. Exact next recommended action

None — **the project is DELIVERED.** All ten phases are `DONE` with
recorded evidence, and AC-1…AC-12 of `prd.md` are verified (map in §7).
For future sessions: reread the six governing documents (this file first)
before changing anything; keep the zero-warning gate and the
requirements-verbatim fresh-setup check green after any change. Optional,
explicitly deferred work is listed in §10 (parameter sweeps, config
save/load, per-access animation).

## 13. Facts vs. assumptions vs. limitations

- **Verified facts:** everything in §4 (environment table), §8 (tests
  executed), and §7 (completed capabilities). The delivered repo (§3)
  contains the Phase 1–10 deliverables: the C++ engine with its full
  verification suite (729 checks), both bots with the hardened engine
  client, the four sample traces, the browser-verified Streamlit UI, all
  eight schemas, the 135-test pytest suite, the archived §14
  demonstration record (`docs/demo-record.json`), the walkthrough record
  and screenshots (`docs/phase9-walkthrough.md`,
  `docs/screenshots/`), and the complete README.
- **Assumptions:** none currently open — nlohmann/json 3.11.3 compiles
  cleanly under GCC 6.3 with `-std=c++14` (verified in Phase 1), and
  mingw32-make runs the Makefile's POSIX syntax via `sh` (verified).
- **Limitations:** GCC 6.3 blocks C++17 features; MinGW.org toolchain is
  unmaintained — if it fails on a genuine need, the fallback is installing a
  newer MinGW-w64 toolchain and recording a D-entry here first. Makefile
  build/test commands assume Git Bash is on PATH (mingw32-make picks `sh`);
  running them from a bare cmd.exe shell is untested and not supported.
