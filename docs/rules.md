# rules.md — How code must be written in this project

> Enforceable standards. `architecture.md` defines boundaries; this file
> defines the code inside them. Violations found in review are fixed before a
> phase is marked done.

---

## 1. Language standards

### C++ (engine)

- Standard: **C++14-compatible subset** (verified compiler: g++ 6.3.0, MinGW).
  Do not use C++17-only features (structured bindings, `std::optional`,
  `std::variant`, `if constexpr`, `string_view`) even if a newer compiler
  appears, unless `memory.md` records a deliberate compiler upgrade.
- Compile flags: `-std=c++14 -O2 -Wall -Wextra`; zero warnings tolerated.
- One responsibility per file; headers in `engine/include/` with
  `#pragma once`; sources in `engine/src/`. No precompiled headers, no
  exceptions beyond standard-library failures (validation returns errors, it
  does not throw).
- Types: exact-width integers (`uint64_t`, `uint32_t`) for addresses, tags,
  stamps, seeds; `size_t` for counts. No floating point anywhere in address
  math; doubles only for rates/AMAT.
- Naming: `snake_case` for functions/variables, `PascalCase` for types,
  `UPPER_SNAKE` for constants. Names state intent (`victim_way`, not `vw`).
- No globals with mutable state except the engine's RNG instance (owned by the
  simulator object) and the stamp counter (owned by the simulator object).
- JSON only through the vendored nlohmann header; no hand-rolled parsing.

### Python (bots, UI, tests)

- Python 3.12; standard library + declared dependencies only
  (`requirements.txt` / `requirements-dev.txt`).
- PEP 8, 4-space indents, `snake_case`, module-level docstrings. Type hints on
  all bot and engine-client function signatures (plain `dict`/`dataclass`
  shapes, not clever generics).
- Dataclasses for contracts crossing module boundaries (config, trace, job,
  result). Contracts mirror `schemas/*.json`; conversion functions are the only
  place dict shapes are handled.
- No `import *`, no global mutable state, no monkey-patching in tests.

## 2. Correctness rules (absolute)

**Prohibited, without exception:**

1. Guessing algorithm results — every expected value in a test comes from a
   hand calculation or the published worked examples (`architecture.md` §13).
2. Hardcoding simulation outcomes anywhere (engine, bots, UI).
3. Fake or stub implementations presented as complete; placeholder code left
   behind.
4. Duplicate cache logic: hit/miss, decomposition, or replacement decisions in
   Python. Python may re-render engine outputs; it may never compute them.
5. Silent exception suppression (`except: pass`, catching and continuing
   without logging/reraising).
6. Silent input repair: the engine never clamps, wraps, or defaults invalid
   input. The UI may offer a suggested value but never applies it silently.
7. Declaring success without running the available validation commands.
8. Unnecessary dependencies, unused abstractions, speculative features.
9. Arbitrary changes outside the current phase's scope.
10. Editing tests to make failing code pass without fixing the root cause.

**Required:**

- Determinism: no wall-clock, no unseeded randomness, no hash-order dependence
  in any output that tests or reports consume. All randomness = `std::mt19937`
  seeded from the config seed (engine) — Python generates no random numbers at
  all.
- Seed handling: the seed is required input for RANDOM, echoed in results and
  records, and never generated implicitly. If the UI shows a seed field, it
  shows a concrete value, never "auto".
- Integer-safe math only: bit widths derived by shift counting (`ctz` by
  loop), never `log2()` on floats; 64-bit unsigned types for all address math.
- Fill before evict; eviction counted only for valid victims (engine asserts
  the invariants of `architecture.md` §9 on every run).
- Explanations and summary text come from the fixed templates
  (`architecture.md` §10, §6.9) — no free-form generated prose in outputs.

## 3. Input validation and error handling

- Validate at the boundary, trust internally: the engine validates the entire
  job once, then works with immutable parsed structures. Bots validate their
  own request dicts before building jobs.
- Errors are structured, never stringly-typed across layers: engine ⇒ error
  envelope (`E_*` codes); bots ⇒ typed exceptions (`TraceBotError`,
  `ExperimentBotError`, `EngineError`) carrying the same codes; UI ⇒ the
  rendered message plus which control to fix.
- Collect all validation problems per object into a list before failing (the
  engine reports every violated field, not just the first).
- Every user-facing error message contains: what is wrong, the received value,
  and the accepted range/fix. Example:
  `block_size_bytes must be a power of two (received 6); valid values: 1, 2, 4, 8, 16, 32, 64, 128.`
- Retries: only engine_client may retry (spawn/transient I/O failures, max 2
  attempts). Validation errors are terminal everywhere.

## 4. Separation of concerns

- The engine reads only its `--in` file (or stdin) and writes only its
  `--out` file (or stdout) — the exact filesystem contract stated in §9 and
  `architecture.md` §5.1. No environment lookups and no other filesystem
  access of any kind.
- Bots contain no rendering and no Streamlit imports; the UI contains no
  subprocess calls (it goes through bots/engine_client only).
- Trace generation, experiment orchestration, and report formatting are pure
  functions where possible (dict in ⇒ dict out) so tests need no UI and no
  subprocess (engine-client tests use a stub script).

## 5. Testing requirements

- Every phase's tests run green before the phase is marked done; results are
  recorded verbatim (command + pass/fail counts) in `memory.md`.
- New behavior ⇒ new test first or with the change; bug fix ⇒ regression test
  reproducing the bug.
- Engine tests: every worked example (§13), every validation rule, boundary
  cases, determinism double-run, invariant checks.
- Python tests: unit tests run without the exe; integration tests skip with a
  clear message only if `build/cache_sim.exe` is missing (and the skip is
  reported, never hidden).
- No test asserts on incidental formatting (dict key order, whitespace) —
  assert on contract content.

## 6. JSON schema compliance

- Every cross-process payload (config, trace, job, result, experiment record)
  has a schema file in `schemas/` and a test that validates a real example
  against it.
- Schema files are the single definition; prose in other docs references them
  and is kept consistent. A contract change = schema change + doc change +
  test change in the same commit/phase.
- Unknown fields: the engine ignores unknown keys in `options` but rejects
  unknown top-level job keys with `E_JOB_INVALID` (typo protection).

## 7. Resource limits

The canonical numbers are in `architecture.md` §12; they are defined once as
constants in the engine and mirrored in the UI validation hints. Exceeding a
limit is an `E_LIMIT` error with the limit stated — never a truncation, wrap,
or partial run.

## 8. Logging and debugging

- Engine: stdout is reserved for the envelope; unexpected-condition details go
  to stderr (prefixed `cache_sim: `) and never alter the envelope's content.
- Python: bots print nothing to stdout in normal operation (the UI renders
  everything); use `logging` at DEBUG for diagnostics. The engine_client logs
  the exact command line it runs (without absolute user paths) for reproducibility.
- Debugging aids must not become runtime features: no debug flags in the UI.

## 9. Dependencies and security

- Minimal and justified: engine = vendored nlohmann/json header only; Python =
  streamlit, matplotlib, pandas, plus **pytest and jsonschema as declared
  development dependencies** (pytest runs the suites; jsonschema runs the
  canonical-schema compliance tests required by §6 — see `memory.md` D-11).
  Both are pinned in `requirements-dev.txt`, so
  `pip install -r requirements.txt -r requirements-dev.txt` fully provisions
  a clean environment for building and testing. Adding anything else requires
  a written reason in `memory.md` decisions.
- No network access at runtime; no telemetry; the Streamlit app runs on
  localhost by default.
- **Engine filesystem contract** (normative in `architecture.md` §5.1): the
  engine reads only its `--in` file (or stdin) and writes only its `--out`
  file (or stdout); it never touches any other path, performs no network or
  environment access, and treats an unopenable `--in`/`--out` as `E_USAGE`.
  Python-side writes are limited to `build/` and `reports/` inside the
  project directory.
- No secrets exist in this project; if any file ever needs one, it must not be
  committed — nothing in this repo should ever contain keys or tokens.
- Do not commit build artifacts (`build/`), reports, or local environment
  files. Do not make git commits or push unless explicitly asked (the
  workspace is not currently a git repository — record it if that changes).

## 10. Documentation

- Every module starts with a 2–6 line docstring saying what it is responsible
  for and what it must not do (mirrors `architecture.md` §2).
- README (completed in Phase 10): prerequisites, exact setup/build/run/test
  commands for the verified environment, the demo walkthrough, and the location
  of the six governing Markdown files.
- Keep `memory.md` current after every meaningful change — stale memory is
  worse than no memory (a later session will trust it).

## 11. Code reuse and abstraction policy

- Abstractions are created only when: (a) they isolate a real responsibility
  (engine ⇄ subprocess ⇄ bots ⇄ UI boundaries), (b) they remove proven
  duplication, or (c) they make testing materially easier. Otherwise write the
  direct code.
- One implementation per concept: e.g., config validation rules exist once (in
  the engine) and are *referenced* elsewhere; the UI's early validation is a
  thin mirror of the same numbers (documented as such), not a second authority.
- No config objects, DI containers, plugin registries, base classes with one
  subclass, or "manager" classes.

## 12. Performance

- Engine targets: 100,000-access trace < 1 s on the verified machine (O(1) per
  access; sets stored as flat arrays, no per-access allocation).
- UI: render at most the latest ~500 events in the interactive table with a
  full-table download; never re-run the engine on widget interaction alone.
- Profile only when a measured requirement fails; no speculative optimization.

## 13. Working protocol for the implementing agent

- Inspect before editing: read the file (and its callers) before changing it.
- Smallest coherent change that satisfies the phase's acceptance criteria; no
  drive-by refactors, no reformatting of untouched code.
- After any fix, rerun the failing test **and** the related regression suites.
- Never mark a phase done in `tasks.md`/`memory.md` without its acceptance
  criteria actually passing; record real command output summaries.
- If a requirement conflicts with reality (environment, contradiction between
  docs), do not silently reshape the project: document the conflict in
  `memory.md`, apply the smallest scope-preserving resolution, and surface it
  in the phase report.
