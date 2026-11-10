# prd.md — Product Requirements: COA Cache Simulator with Two Automated Bots

> Canonical scope and acceptance criteria for this project. Per the specification
> hierarchy (see §13), current-conversation instructions override this file;
> this file overrides `architecture.md`, which overrides `rules.md`, and so on.

---

## 1. Project identity

- **Title:** COA Cache Simulator with Two Automated Bots
- **Subject:** Computer Organization and Architecture (COA), college project
- **One-paragraph problem statement:** Students studying cache memory need to
  *see* how cache organization and replacement policy change hit/miss behavior.
  This project is an interactive, software-based cache memory simulator that
  processes read-only memory-address traces. A C++ engine performs all cache
  calculations; a Python/Streamlit interface configures the cache, visualizes
  every access, and displays statistics. Two automated software components —
  Bot 1 (trace generation) and Bot 2 (experiment running and analysis) — make
  controlled, reproducible experiments possible with one click.

## 2. Objective and intended users

- **Objective:** Demonstrate how direct-mapped, N-way set-associative, and
  fully-associative caches, and LRU / FIFO / Random replacement policies, behave
  on configurable address traces; make every result transparent (per-access
  event log, cache state, derived bit fields) and every comparison controlled
  (one variable changed at a time) and reproducible (seeded, recorded inputs).
- **Intended users:** COA students preparing/attending lab demonstrations, and
  the course instructor evaluating the project. Secondary: the development
  agents themselves (the six Markdown files are their operating context).

## 3. Scope and explicit non-goals

### 3.1 In scope

1. A C++ cache simulation engine — the **single source of truth** for all cache
   behavior (validation, address decomposition, hit/miss, replacement, statistics).
2. Bot 1 — Trace Generation Bot: deterministic generation of sequential,
   repeated-address, and conflict-heavy traces, validated against the cache
   configuration.
3. Bot 2 — Experiment Runner and Performance Analysis Bot: controlled
   experiments over replacement policies and cache organizations, comparison
   tables/graphs, and a reproducible experiment record.
4. A Streamlit (Python) user interface: configuration, trace display, per-access
   event table, cache-state visualization, summary metrics, comparison charts,
   bot workflow with statuses, report saving/download.
5. Automated tests at the engine level (C++) and bot/integration level (Python).
6. Documentation: this file set + `README.md` + sample traces.

### 3.2 Explicit non-goals (must NOT be built)

- **No AI/LLM layer**: no chatbot, no "explain with AI" feature, no AI service
  dependency, no API keys.
- **No write behavior**: no write-through, write-back, dirty bits, write
  allocation, write buffers. The simulator is **read-only**.
- No cache coherence, no multi-level/inclusive/exclusive caches, no TLBs,
  no virtual memory, no prefetching.
- No measured hardware timing: hit time and miss penalty are *modeling
  assumptions* supplied by the user, never presented as measured latencies.
- No GUI framework beyond Streamlit; no web services, no database, no Docker.
- No "advanced" boilerplate: no service layers, dependency injection, plugin
  systems, or abstractions without a stated reason (see `rules.md`).

## 4. Core concepts (as implemented)

### 4.1 Cache organizations

| Organization | Sets | Lines per set | Address fields | Policy selectable? |
|---|---|---|---|---|
| `direct` | capacity / block_size | 1 | tag, index, offset | No (single line per set) |
| `set_associative` | capacity / (block_size × associativity) | associativity (≥ 2) | tag, index, offset | Yes |
| `fully_associative` | 1 | capacity / block_size | tag, offset (index field = 0 bits; index reported as `null`) | Yes |

### 4.2 Replacement policies (multi-way organizations only)

- **LRU** — evict the valid line least recently *used*; recency updates on
  hits and on fills.
- **FIFO** — evict the valid line that entered the cache first; hits do **not**
  change insertion order.
- **Random** — evict a valid line chosen by an explicitly seeded pseudo-random
  generator (`std::mt19937`); identical configuration + trace + seed + engine
  version ⇒ identical results. A seed is mandatory whenever Random is used.

Fill rule (all organizations, all policies): an **invalid line is always filled
before any valid line is evicted**; an eviction is counted only when a *valid*
line is actually displaced.

### 4.3 Read-only scope

Only memory read accesses exist. An unaligned byte address is valid as long as
it fits the configured address width. Block contents are represented by block
number / base address — no data bytes are stored.

## 5. Configuration and validation

The engine accepts **explicit, complete** configuration objects only — it never
silently substitutes defaults or repairs invalid input. Defaults live in the UI
layer only. Byte-addressed memory is the documented convention.

| Field | Type | Constraint |
|---|---|---|
| `capacity_bytes` | integer | power of two, 1 ≤ capacity ≤ 1,048,576 (2²⁰) |
| `block_size_bytes` | integer | power of two, 1 ≤ block ≤ 128; block ≤ capacity |
| `organization` | string | one of `direct`, `set_associative`, `fully_associative` |
| `associativity` | integer | required iff `set_associative`; power of two, 2 ≤ assoc ≤ capacity / block_size |
| `address_width_bits` | integer | 4 ≤ width ≤ 64 |
| `policy` | string | required iff not `direct`; one of `LRU`, `FIFO`, `RANDOM` |
| `seed` | integer | required iff `policy = RANDOM`; 0 ≤ seed ≤ 4,294,967,295 |
| `hit_time` | number | finite, ≥ 0 (unit: clock cycles) |
| `miss_penalty` | number | finite, ≥ 0 (unit: clock cycles); AMAT computed iff both hit_time and miss_penalty supplied |

Derived geometry (computed by the engine, never re-derived authoritatively
elsewhere): lines, sets, offset/index/tag bit widths, maximum valid address.
Validation is additive: every violated constraint produces an error entry with
field name, problem, and received value. See `architecture.md` §7 for the exact
decomposition formulas and §12 for the resource limits table.

## 6. Functional requirements

### FR-A Engine

- **FR-A1** Validate the full configuration; reject invalid parameters with
  clear, actionable messages (field, problem, received value, suggested fix
  where obvious). Never clamp or "fix" user input.
- **FR-A2** Decompose every address into block number, tag, index, offset, set,
  and way, exactly per `architecture.md` §7. For fully-associative caches the
  index is `null` and the set is 0 (documented N/A convention).
- **FR-A3** Process traces of 0–100,000 byte addresses; handle the empty trace
  safely (zeroed statistics, rates reported as `null`, no division by zero).
- **FR-A4** For every access, record a structured event: sequence number,
  address, block number, tag, index, offset, set, way, hit/miss, whether a
  block was loaded, evicted block (if any), replacement metadata, and a concise
  plain-language explanation of the operation.
- **FR-A5** Report final cache state: per set and way — valid, tag, block
  number, replacement metadata. Optionally (bounded: trace ≤ 2,000 accesses)
  per-access state snapshots for UI animation.
- **FR-A6** Compute summary statistics: total accesses, hits, misses, evictions,
  hit rate, miss rate, and AMAT when timing assumptions are supplied:
  `AMAT = hit_time + miss_rate × miss_penalty`.
- **FR-A7** Enforce the invariants of `architecture.md` §9 internally
  (hits + misses = accesses; evictions ≤ misses; invalid-before-valid; …).
- **FR-A8** Be deterministic: same engine version + config + trace + seed ⇒
  byte-identical event log and summary.

### FR-B Bot 1 — Trace Generation

- **FR-B1** Generate, deterministically from its inputs:
  - **Sequential:** start address, access count, byte stride.
  - **Repeated-address:** one address, repetition count.
  - **Conflict-heavy:** `distinct_blocks` different blocks mapping to the *same
    set* under the current configuration (uses engine-derived number of sets;
    supports a chosen target set; handles the fully-associative single-set case
    by documenting that all blocks already map to one set).
- **FR-B2** Validate generated addresses against the configured address width
  and resource limits; refuse (with an error) rather than wrap or truncate.
- **FR-B3** Display the generated trace (and its parameters) before simulation.
- **FR-B4** Accept a manually supplied/imported trace (one address per line,
  decimal or `0x` hex, `#` comments) validated by the same rules.
- **FR-B5** Have independently testable logic and an explicit request/response
  contract (see `architecture.md` §8.6). Bot 1 never decides hit/miss — it only
  produces addresses.

### FR-C Bot 2 — Experiment Runner and Performance Analysis

- **FR-C1** Accept a valid trace and an experiment configuration; execute the
  C++ engine for each required configuration; never re-implement cache logic.
- **FR-C2** `policy_comparison` mode: hold trace, capacity, block size, address
  width, and associativity fixed; run LRU, FIFO, and Random (seed recorded).
  **Refuse** (clear error) policy comparison on direct-mapped configurations —
  there is no meaningful policy choice with one line per set.
- **FR-C3** `organization_comparison` mode: hold trace, capacity, block size,
  address width fixed; compare direct vs. set-associative vs. fully-associative.
  LRU is used wherever a policy exists; the report states this caveat. One
  variable changes at a time.
- **FR-C4** Collect per run: hits, misses, evictions, hit rate, miss rate,
  AMAT (when assumptions supplied), policy, seed, engine version.
- **FR-C5** Produce a comparison table and appropriate chart(s).
- **FR-C6** Produce a concise, deterministic, data-based summary sentence set
  (generated from the numbers, not prose templates with invented claims).
- **FR-C7** Record everything needed to reproduce the experiment (trace +
  parameters + seeds + engine version) in an experiment record, saveable as a
  report file.

### FR-D Interface, bots workflow, reporting

- **FR-D1** One visible automated workflow: Bot 1 generates a trace → engine
  processes it → Bot 2 runs experiments → comparison results, graphs, and a
  saved report are shown — each step with live status and output.
- **FR-D2** Bot failures surface clearly (which bot, which error) and allow
  safe retries without stale state.
- **FR-D3** Outputs shown in the UI are always derived from actual engine
  execution — the UI never computes or fabricates cache results.
- **FR-D4** Reports (simulation result and experiment record) can be saved and
  downloaded as JSON; CSV export of the event log is provided for the report.

## 7. Metrics (exact definitions)

- Hit rate = hits / total accesses (empty trace ⇒ `null`, not 0 or 1).
- Miss rate = misses / total accesses.
- AMAT = hit_time + miss_rate × miss_penalty (only when both timing inputs are
  supplied; unit: clock cycles — a documented modeling assumption, not measured
  hardware latency).
- Engine returns full-precision doubles; the UI rounds for display only
  (rates to 4 decimal places, percentages to 2, AMAT to 2) and states units.

## 8. End-to-end user workflow (the demo path)

1. User configures the cache in the sidebar (organization, capacity, block
   size, associativity, address width, policy, seed, timing assumptions);
   validation messages appear inline as parameters are chosen.
2. User obtains a trace: Bot 1 pattern generator, manual paste, or a bundled
   sample file. The trace is shown before running.
3. User runs the simulation: summary metric cards, per-access event table, and
   the final cache-state grid are displayed, all from the engine result.
4. User opens the Experiments tab: Bot 2 runs a controlled comparison
   (policy or organization mode) on the current trace; table + chart + summary
   text are shown; the experiment record can be saved/downloaded.
5. User opens the Automated Workflow tab and presses one button: Bot 1 →
   engine → Bot 2 execute with visible statuses, then results and the saved
   report are presented.
6. Failure at any step shows the failing bot/step, the error, and a retry
   affordance.

## 9. UI and reporting requirements

- Follow `design.md` exactly: restrained engineering-tool aesthetic, sidebar
  configuration, tabbed main area (Simulator / Experiments / Automated
  Workflow / Help), metric cards, event table, cache-state grid, bot status
  pills, charts with labeled axes, loading/empty/error states.
- The UI validates input early (fast feedback) but the engine re-validates
  authoritatively; UI-level messages and engine errors must agree in substance.
- No fake data anywhere in the app; bundled sample traces live in `traces/`
  and are labeled as samples.

## 10. Nonfunctional requirements

- **NFR-1 Reproducibility:** all randomness is seeded; results embed the engine
  version and a trace digest; identical inputs re-run to identical outputs.
- **NFR-2 Performance:** a 100,000-access trace simulates in < 1 s on the
  verified machine; the UI remains responsive (batch rendering, no per-access
  re-render).
- **NFR-3 Testability:** the engine builds and runs without the GUI; bots are
  pure-Python modules testable without the UI; the full test suite runs in one
  command each for C++ (`mingw32-make test`) and Python (`pytest`).
- **NFR-4 Portability (documented):** targets the verified environment —
  g++ 6.3.0 (MinGW), mingw32-make, Python 3.12 — with exact commands in
  `README.md`; code stays within the C++14-compatible subset (see
  `memory.md` decisions).
- **NFR-5 Maintainability:** a college student can read every module; no file
  over ~600 lines without justification; naming per `rules.md`.
- **NFR-6 Safety:** no secrets, no network calls at runtime, no writes outside
  the project directory except `reports/` and `build/`.
- **NFR-7 Honesty:** the UI never claims success for a step that failed; error
  states are first-class (see `design.md` §11).

## 11. Error handling and reproducibility requirements

- Every invalid input yields an actionable message naming the field, the
  problem, and the received value (engine) or the widget and the accepted range
  (UI).
- Errors are structured (machine-readable codes — see `architecture.md` §6.3)
  so bots and the UI can route them (e.g., configuration error ⇒ highlight the
  sidebar control).
- An address outside `0 .. 2^address_width_bits − 1` is rejected with the
  maximum valid address stated.
- Reproducibility record for every experiment: full config(s), trace (content,
  not just a name), seed(s), engine version, timestamp of creation.

## 12. Acceptance criteria (testable)

These are the pass/fail criteria for the project; each maps to automated tests
or a scripted manual check (phase mapping in `tasks.md`).

- **AC-1** Repeated access to one block: exactly one miss, subsequent accesses
  hit (worked example E1 of `architecture.md` §13: trace `[16,16,16,16,16]`,
  direct, 8 B capacity, 2 B blocks ⇒ 1 miss, 4 hits, 0 evictions).
- **AC-2** Direct-mapped conflict trace produces the predicted evictions (E2:
  trace `[0,8,16,24,0]` ⇒ 5 misses, 4 evictions, 0 hits).
- **AC-3** LRU vs. FIFO differ on the verified trace (E3: `[0,4,0,8,4]`, 2-way,
  8 B capacity, 2 B blocks ⇒ LRU 1 hit/4 misses/2 evictions; FIFO 2 hits/
  3 misses/1 eviction). The controlled demonstration (§14) reproduces this in
  the UI.
- **AC-4** Fully-associative: one set, zero index bits, `index: null` events
  (E4).
- **AC-5** Random replacement with a fixed seed is byte-identical across runs
  (E5), and the seed appears in the result and every experiment record.
- **AC-6** Invalid configuration rejected with a useful message naming field +
  problem + received value (e.g., block size 6 ⇒ "must be a power of two").
- **AC-7** Address ≥ 2^address_width_bits rejected with the max valid address
  stated.
- **AC-8** A miss fills an invalid line before evicting any valid line; no
  eviction is counted for filling an invalid line (E6 and engine-internal
  invariant checks).
- **AC-9** Empty trace ⇒ zeroed summary with `null` rates and no crash;
  malformed traces (non-integer, negative, too long) rejected safely.
- **AC-10** Both bots complete the full workflow from the UI, statuses shown,
  and every displayed number matches the engine's output for the same inputs.
- **AC-11** Invariants hold on every run (engine-asserted): hits + misses =
  accesses; hit rate + miss rate = 1 (±1e-9) when nonempty; evictions ≤ misses.
- **AC-12** Determinism: same version+config+trace+seed ⇒ identical result
  bytes, verified twice for LRU, FIFO, and each of two Random seeds.

## 13. Specification priority

All six governing documents live in `docs/` (relocated from the project
root on 2026-10-24):

1. Explicit instructions in the current conversation.
2. `docs/prd.md` (this file) — scope and acceptance criteria.
3. `docs/architecture.md` — component boundaries, contracts, schemas.
4. `docs/rules.md` — coding and correctness standards.
5. `docs/design.md` — UI system.
6. `docs/tasks.md` — phase scope and ordering.
7. `docs/memory.md` — verified current state.

The repository is evidence of what exists, not permission to contradict the
agreed requirements. Contradictions are documented and resolved with the
smallest scope-preserving change.

## 14. Required controlled demonstration (final project)

- Two-way set-associative cache: capacity 8 B, block size 2 B, address width
  8 bits (derived: 2 sets, offset 1 bit, index 1 bit, tag 6 bits).
- Fixed trace `[0, 4, 0, 8, 4]` (verified in `architecture.md` E3 to make LRU
  and FIFO differ: LRU 1 hit vs. FIFO 2 hits).
- All parameters and the trace held constant across runs; LRU, FIFO, and Random
  (seed recorded, default 12345) each executed; hits, misses, evictions, hit
  rate, and AMAT (1-cycle hit time, 20-cycle miss penalty) compared in the UI
  table and chart; experiment record saved with the seed.
- Expected published numbers: LRU 1/4/2, FIFO 2/3/1 (hits/misses/evictions),
  AMAT LRU 17.00 cycles vs. FIFO 13.00 cycles at the stated assumptions.

## 15. Constraints and documented assumptions

- Byte-addressed memory; addresses are non-negative integers within the
  configured width.
- Powers of two required for capacity, block size, and associativity so bit
  fields are exact integers; this is a documented teaching-tool constraint.
- The two bots are ordinary deterministic software components — there is no AI
  anywhere in this project.
- Hit time / miss penalty are assumptions in clock cycles; AMAT is a modeled
  average, not a measurement.
- Environment constraints verified on 2026-10-24 are recorded in `memory.md`
  (g++ 6.3.0 ⇒ C++14-compatible subset; no CMake ⇒ Makefile build; Streamlit
  to be installed in Phase 1).
- Trace contents represent read addresses only; data values are never modeled.
