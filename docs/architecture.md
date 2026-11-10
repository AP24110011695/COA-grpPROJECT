# architecture.md — How the COA Cache Simulator is built

> Component boundaries, contracts, and schemas. Schemas are canonically defined
> as JSON Schema files in `schemas/` (created in Phase 1); this document shows
> them as concrete examples and prose rules. Where this file and a `schemas/`
> file disagree, the `schemas/` file is corrected and the discrepancy is treated
> as a bug.

---

## 1. System overview

```
+--------------------------------------------------------------+
| Streamlit UI (ui/app.py)                                     |
|  sidebar config | Simulator | Experiments | Workflow | Help  |
+---------|---------------------------------------|------------+
          | dicts (validated early)               | one-click run
          v                                       v
   +-------------+   request dict   +---------------------------+
   | Bot 1       | --------------> | Bot 2                     |
   | trace_bot   |                 | experiment_bot            |
   | (pure Py)   |                 | (pure Py, orchestrates)   |
   +------+------+                 +------------+--------------+
          |  trace dict                         | N job dicts
          v                                     v
   +----------------------------------------------------------+
   | engine_client (bots/engine_client.py)                    |
   |  builds JSON job file, spawns cache_sim, parses result   |
   +---------------------------+------------------------------+
                               | subprocess (JSON in / JSON out)
                               v
   +----------------------------------------------------------+
   | cache_sim.exe  (C++14, engine/)                          |
   |  validation -> decomposition -> simulation -> stats      |
   |  THE single source of truth for all cache behavior       |
   +----------------------------------------------------------+
```

Python never decides hits/misses or replacements. Python validates input early
(fast UX), generates traces from engine-reported geometry, schedules engine
runs, renders outputs, and saves reports.

## 2. Component responsibilities

| Component | Path | Responsibility | Must NOT |
|---|---|---|---|
| `cache_sim` engine | `engine/src/*.cpp`, `engine/include/*.hpp` | config validation, address decomposition, simulation (3 orgs, 3 policies), event log, summary, cache state, invariants, determinism | print anything but the JSON envelope to stdout; depend on Python |
| Engine tests | `engine/tests/engine_tests.cpp` | assert-based tests incl. all worked examples (§13) | use an external test framework |
| Bot 1 | `bots/trace_bot.py` | deterministic trace generation (sequential, repeated, conflict); manual-trace parsing; trace validation (width/limits) | decide hit/miss; re-derive geometry (asks the engine) |
| Bot 2 | `bots/experiment_bot.py` | experiment matrices, controlled comparisons, seed recording, aggregation, deterministic summary text, reproducibility record | invent numbers; compare policies on direct-mapped |
| Engine client | `bots/engine_client.py` | job-file creation, subprocess lifecycle (timeout, exit codes), envelope parsing, error translation, retry on spawn failure only | re-try on validation errors; catch and hide engine errors |
| Streamlit UI | `ui/app.py` (+ `ui/components.py` if needed) | forms, trace display, tables, cache-state grid, charts, workflow statuses, report save/download | compute cache results or "fix" invalid config silently |
| Python tests | `tests/test_*.py` | unit tests for bots, engine-client contract tests, integration tests vs. the built exe | require the UI to run |
| Schemas | `schemas/*.json` | canonical JSON Schema for every contract | duplicate/conflicting definitions |
| Sample traces | `traces/*.json` + `traces/*.txt` | small verified examples incl. §13 traces | be referenced as anything but samples |

## 3. Data flow

1. UI sidebar → config dict (UI-level validation with immediate messages).
2. Trace source → trace dict: Bot 1 pattern (which itself first asks the engine
   for geometry via `geometry` mode), manual text parsed by Bot 1, or a sample
   file loaded and re-validated by Bot 1's parser.
3. Simulation: engine client writes a job file → runs `cache_sim` → envelope
   parsed → UI renders metrics, event table, cache-state grid.
4. Experiments: Bot 2 builds N jobs (one per policy/organization), runs them
   through the engine client, aggregates, renders table + chart + summary text,
   and saves the experiment record to `reports/` on request.
5. Automated workflow: Bot 1 → engine → Bot 2, each step reporting status to
   the UI; the final report bundles trace + runs + record.

## 4. Build and run contract (verified environment)

- Toolchain: g++ 6.3.0 (MinGW), `mingw32-make`. No CMake, no MSVC (verified
  2026-10-24 — see `memory.md`).
- C++ standard: C++14-compatible subset, compiled `-std=c++14 -O2 -Wall -Wextra`.
- JSON: vendored single header `engine/third_party/nlohmann/json.hpp` (network
  verified available for Phase 1 vendoring).
- Build: `engine/Makefile` targets `all` (build/cache_sim.exe), `test`
  (build/engine_tests.exe + run), `clean`. Equivalent one-liner documented in
  README: `g++ -std=c++14 -O2 -Wall -Wextra -Iengine/include -Iengine/third_party engine/src/*.cpp engine/tests/engine_tests.cpp -o build/engine_tests.exe`.
- Python: Python 3.12 (`python` on PATH); `requirements.txt` = streamlit,
  matplotlib, pandas, pytest (pytest in `requirements-dev.txt`); UI launched
  with `python -m streamlit run ui/app.py`.
- The engine executable path is resolved from `build/cache_sim.exe` relative to
  the project root; `ENGINE_PATH` env var overrides (for tests).

## 5. Process integration contract (C++ ⇄ Python)

### 5.1 Invocation

```
cache_sim --mode simulate --in job.json --out result.json
cache_sim --mode geometry --in config.json --out geometry.json
cache_sim --mode version
```

- `--mode`: `simulate` | `geometry` | `version` (required for the first two).
- `--in`: path to a UTF-8 JSON file. If omitted, stdin is read (same format).
- `--out`: path for the JSON envelope. If omitted, stdout is used.
- **Filesystem contract:** the engine performs exactly two filesystem
  operations — reading `--in` (when provided) and creating/truncating `--out`
  (when provided). It never lists, probes, caches, or writes any other path,
  performs no network or environment access, and emits everything else to
  stdout/stderr. Failure to open either file is an `E_USAGE` error; the
  *caller* (UI, bots, tests) chooses the paths and owns any policy about
  where those live (project `build/`-style temp locations for tests,
  `reports/` for saved records).
- stdout carries **only** the JSON envelope when `--out` is omitted; otherwise
  stdout stays empty. Diagnostics (if ever needed) go to stderr and never
  replace the envelope.
- `--mode version` prints the version envelope (§6.2) and exits 0.

### 5.2 Exit codes

| Code | Meaning | Envelope |
|---|---|---|
| 0 | success | `{"ok": true, ...}` |
| 2 | usage error (unknown flag, missing mode, unreadable input file) | error envelope, `code: "E_USAGE"` |
| 3 | validation failure (config, trace, job shape, limits) | error envelope, matching `E_*` code |
| 4 | unexpected internal error | error envelope, `code: "E_INTERNAL"` (details on stderr) |

### 5.3 Envelopes

Success:

```json
{
  "ok": true,
  "engine": {"name": "cache_sim", "version": "0.1.0"},
  "echo": { "": "the normalized config exactly as accepted" },
  "geometry": { "": "see §6.3" },
  "events": [ { "": "see §6.5" } ],
  "summary": { "": "see §6.6" },
  "state": { "": "final cache state, see §6.7" }
}
```

Failure:

```json
{
  "ok": false,
  "engine": {"name": "cache_sim", "version": "0.1.0"},
  "error": {
    "code": "E_CONFIG_INVALID",
    "message": "block_size_bytes must be a power of two",
    "details": [
      {"field": "block_size_bytes", "problem": "must be a power of two", "received": 6}
    ]
  }
}
```

Error codes (closed set): `E_USAGE`, `E_JOB_INVALID` (malformed JSON or wrong
top-level shape), `E_CONFIG_INVALID`, `E_TRACE_INVALID`, `E_LIMIT` (a resource
limit exceeded), `E_INTERNAL`. Validation collects **all** field problems into
`details` before failing — not just the first.

`geometry` mode returns the same envelope shape with `geometry` populated
(`events`/`summary`/`state` omitted); it validates the config and is what Bot 1
calls to get the number of sets without re-deriving it in Python.

## 6. Canonical schemas (examples; normative files in `schemas/`)

### 6.1 Configuration (`schemas/config.schema.json`)

```json
{
  "capacity_bytes": 8,
  "block_size_bytes": 2,
  "organization": "set_associative",
  "associativity": 2,
  "address_width_bits": 8,
  "policy": "LRU",
  "seed": null,
  "hit_time": 1.0,
  "miss_penalty": 20.0
}
```

Rules: `associativity` present iff `set_associative` (others: omit or null);
`policy` present iff organization ≠ `direct`; `seed` required iff
`policy = RANDOM`; `hit_time`/`miss_penalty` both-or-neither; all limits per
`prd.md` §5. Field constraints mirror `prd.md` exactly — the engine is the
authority. Inapplicable fields must be null or omitted, never silently
ignored: a non-null `associativity` with organization ≠ `set_associative`,
or a non-null `seed` with `policy ≠ RANDOM`, is rejected by the engine and
forbidden by the schema (decision D-17).

### 6.2 Version envelope

```json
{"ok": true, "engine": {"name": "cache_sim", "version": "0.1.0"}}
```

Any change to simulation semantics bumps the version; the version is embedded
in every result and every experiment record.

### 6.3 Geometry object (`geometry` / schemas/geometry.schema.json)

```json
{
  "capacity_bytes": 8, "block_size_bytes": 2,
  "organization": "set_associative", "associativity": 2,
  "address_width_bits": 8,
  "lines": 4, "sets": 2,
  "offset_bits": 1, "index_bits": 1, "tag_bits": 6,
  "index_field_present": true,
  "max_address": 255
}
```

For `fully_associative`: `sets = 1`, `index_bits = 0`,
`index_field_present = false`. For `direct`: `associativity` is absent/null and
`sets = lines`.

### 6.4 Trace (`schemas/trace.schema.json`) and job (`schemas/job.schema.json`)

```json
{ "name": "lru-vs-fifo-demo", "addresses": [0, 4, 0, 8, 4] }
```

```json
{
  "config": { "": "configuration object (§6.1)" },
  "trace":  { "name": "lru-vs-fifo-demo", "addresses": [0, 4, 0, 8, 4] },
  "options": { "include_state_after_each": false }
}
```

- Addresses: integers, 0 ≤ a ≤ `max_address`, no duplicates required.
- Empty `addresses` array is valid (AC-9) — engine returns a zeroed summary.
- `include_state_after_each: true` adds per-access snapshots (§6.7) and is
  refused with `E_LIMIT` when the trace exceeds 2,000 addresses.
- Manual trace text (Bot 1 import): one address per line, decimal or `0x` hex,
  `#` comments and blank lines ignored; Bot 1 converts to a trace dict.

### 6.5 Event record (`schemas/event.schema.json`)

```json
{
  "n": 4,
  "address": 8,
  "block": 4,
  "tag": 2,
  "index": 0,
  "offset": 0,
  "set": 0,
  "way": 1,
  "result": "miss",
  "loaded": true,
  "evicted": {"block": 2, "tag": 1, "way": 1},
  "policy_meta": {"policy": "LRU", "victim_selection": "lru"},
  "explanation": "Miss: block 4 loaded into set 0 way 1, evicting block 2 (LRU)."
}
```

This is exactly access t4 of worked example E3 under LRU (§13) — the example
documents and the tests use the same per-access values.

- `index` is `null` for fully-associative (documented N/A); `set` is 0 there.
- `evicted` is `null` unless a valid line was displaced (never for fills of
  invalid lines).
- `policy_meta` for RANDOM evictions adds `"seed"` and for fills uses
  `"victim_selection": "none"`; direct-mapped accesses use
  `{"policy": null, "victim_selection": "none"}` for hits and fills and
  `{"policy": null, "victim_selection": "forced"}` for the single-way
  forced eviction (there is no policy choice to name).
- Explanation strings use the fixed templates in §10 so tests can assert them.
- `way` is always 0 for direct-mapped.

### 6.6 Summary (`schemas/summary.schema.json`)

```json
{
  "accesses": 5, "hits": 2, "misses": 3, "evictions": 1,
  "hit_rate": 0.4, "miss_rate": 0.6,
  "amat": {"hit_time": 1.0, "miss_penalty": 20.0, "value": 13.0, "unit": "cycles"},
  "replacement_meta": {"policy": "LRU"}
}
```

- Rates are full-precision doubles; `null` when `accesses = 0`.
- `amat` is present (as an object) iff both timing assumptions were
  supplied, and is **omitted entirely** otherwise — never emitted as
  `null` (AC-P4.4); `unit` is always `"cycles"` (modeling assumption per
  `prd.md` §7). For an empty trace with timing inputs the modeled miss
  rate is 0, so the value degenerates to `hit_time` (decision D-19).
- `replacement_meta` is `{"policy": "RANDOM", "seed": 12345, "rng_draws": 1}`
  for RANDOM runs; otherwise `{"policy": "LRU"|"FIFO"}` or omitted for direct.
- Every result also carries `"trace_sha256"`: SHA-256 over the canonical string
  `"addresses:" + ",".join(str(a) for a in addresses)` (lowercase hex) — used
  by Bot 2 records and reproducibility checks.

### 6.7 Cache state (`schemas/state.schema.json`)

```json
{
  "sets": [
    [ {"way": 0, "valid": true, "tag": 2, "block": 4, "last_used_rank": 2},
      {"way": 1, "valid": false, "tag": null, "block": null, "last_used_rank": null} ]
  ],
  "snapshots": null
}
```

- One array per set; one object per way; `last_used_rank` (1 = most recently
  used) applies to LRU and is `null` for FIFO/RANDOM (FIFO instead reports
  `insert_order_rank`, 1 = oldest inserted among the currently valid lines,
  renumbered as lines are evicted).
- `snapshots` is a list of per-access state arrays when
  `options.include_state_after_each` is true (trace ≤ 2,000 addresses), each
  referencing its event `n`.
- No dirty bits or write state anywhere (read-only scope).

### 6.8 Bot 1 request/response (Python-level dict contract)

Request:

```json
{
  "pattern": "sequential" | "repeated" | "conflict" | "manual",
  "config": { "": "configuration object; Bot 1 validates it via engine geometry mode" },
  "params": { "": "pattern-specific, below" }
}
```

- `sequential`: `{"start_address": 0, "count": 32, "stride_bytes": 4}`
- `repeated`: `{"address": 16, "count": 5}`
- `conflict`: `{"distinct_blocks": 4, "passes": 1, "target_set": 0,
  "start_block": 0}` — the generator first computes the smallest block
  number ≥ `start_block` that is congruent to `target_set` modulo `sets`:
  `base = start_block + ((target_set − start_block) mod sets)` (non-negative
  modulo), then emits blocks `base, base + sets, base + 2×sets, …`
  (`distinct_blocks` of them, each accessed `passes` times) at addresses
  `block × block_size` (offset 0). This maps every generated block to the
  requested set for **any** valid `start_block`/`target_set` combination
  (e.g., sets 4, target_set 3, start_block 0 → blocks 3, 7, 11, 15).
  Boundary and address-width handling: the base is computed with non-negative
  modulo (no negative intermediates; Python integers cannot overflow), every
  emitted address is validated against the engine geometry's `max_address`
  (rejection with `E_TRACE_INVALID` stating the max valid address — never a
  wrap or truncation), and the total access count against the 100,000-address
  trace limit (`E_LIMIT`). `sets` comes from the engine's geometry response.
  For `fully_associative` there is a single set (`sets = 1`): every block
  already maps to set 0, so a requested `target_set ≠ 0` is ignored with the
  documented warning and blocks are `start_block + k`.
- `manual`: `{"text": "0x00 # comment\n4\n..."}` parsed per §6.4.

Response (both directions machine-checkable):

```json
{"ok": true,
 "trace": {"name": "conflict-4-blocks", "pattern": "conflict",
           "params": {"": "as requested"}, "addresses": [0, 4, 8, 12]},
 "geometry_used": { "": "engine geometry response" },
 "warnings": []}
```

Failure: `{"ok": false, "error": {"code": "E_...", "message": "...",
"details": [...]}}` with the same `E_*` code vocabulary as the engine.
Bot 1 output is deterministic: identical requests ⇒ identical traces.

### 6.9 Bot 2 experiment record (`schemas/experiment.schema.json`)

```json
{
  "experiment_id": "exp-20261024-193000-123456-policy",
  "mode": "policy_comparison",
  "created_utc": "2026-10-24T19:30:00Z",
  "engine_version": "0.1.0",
  "trace": {"name": "lru-vs-fifo-demo", "sha256": "9f2c…",
            "addresses": [0, 4, 0, 8, 4]},
  "fixed": {"capacity_bytes": 8, "block_size_bytes": 2,
            "organization": "set_associative", "associativity": 2,
            "address_width_bits": 8},
  "amat_assumptions": {"hit_time": 1.0, "miss_penalty": 20.0, "unit": "cycles"},
  "runs": [
    {"run_id": 1, "config": {"": "full config"}, "policy": "LRU",
     "seed": null, "summary": { "": "summary object" }},
    {"run_id": 2, "policy": "FIFO", "seed": null, "summary": { "": "…" }},
    {"run_id": 3, "policy": "RANDOM", "seed": 12345, "summary": { "": "…" }}
  ],
  "summary_text": "LRU: 1 hit / 5 accesses (20.00%), 2 evictions. FIFO: 2 hits / 5 accesses (40.00%), 1 eviction. RANDOM (seed 12345): 2 hits / 5 accesses (40.00%), 1 eviction. Best hit rate: FIFO and RANDOM tie at 40.00% (LRU 20.00%)."
}
```

- `mode`: `policy_comparison` | `organization_comparison`. In
  `organization_comparison`, `fixed` holds capacity/block/width and runs vary
  `organization` (LRU wherever a policy exists; the caveat sentence is included
  in `summary_text`).
- Refusal rule: `policy_comparison` + `organization: direct` ⇒ error
  (`E_CONFIG_INVALID` at Bot 2 level), never a misleading table.
- `summary_text` is generated only from run data (fixed sentence templates,
  numbers interpolated) — deterministic for identical records.
- `experiment_id` is `exp-<UTC date>-<UTC hhmmss>-<microseconds>-<mode>`
  (decision D-30): the microsecond segment makes a same-second collision —
  two different experiments sharing an id and overwriting each other's
  report file — unreachable in practice. Records saved before D-30 use the
  historical second-resolution form `exp-<date>-<hhmmss>-<mode>`; both
  forms match the schema pattern, and `save_report` additionally refuses
  to silently overwrite a destination that already holds different
  content.
- Records are saved to `reports/<experiment_id>.json`; the UI also offers a
  download button. Every run embeds the engine version; a record is reproducible
  if re-running its trace/configs/seed(s) on the same engine version reproduces
  its summaries byte-for-byte.

## 7. Address decomposition (exact, integer-safe)

Given validated config with `block_size = B`, `sets = S`, address `a`:

```
offset_bits   = ctz(B)                    (B is a power of two; computed by
                                           counting shifts, not float log)
sets          = capacity/B              (direct)   |  capacity/(B×assoc)
              = 1                       (fully associative)
index_bits    = ctz(S)                  (0 for fully associative)
tag_bits      = address_width_bits − index_bits − offset_bits
              (config rejected if < 0: address space too small for geometry)
block         = a >> offset_bits        (= floor(a / B))
offset        = a & (B − 1)
set index     = block & (S − 1)         (= block mod S; 0 when S = 1)
tag           = block >> index_bits
way           = selected by fill/eviction rules (§8)
```

All operations are 64-bit unsigned integer ops; `a ≤ max_address =
2^address_width_bits − 1 ≤ 2^64 − 1` is enforced before decomposition, so no
overflow is possible.

## 8. Cache state and replacement semantics (exact)

### 8.1 Line representation

Each line: `valid (bool)`, `tag (uint64)`, `block (uint64)`,
`stamp_used (uint64)`, `stamp_insert (uint64)` — nothing else (no dirty bit).
One global monotonically increasing 64-bit access counter produces stamps.

### 8.2 Fill rule (all organizations, all policies)

On miss: if any invalid way exists in the set, fill the **lowest-indexed**
invalid way. Only when all ways are valid is a victim selected (§8.3). Direct
sets have one way, so a direct miss either fills the empty line or evicts it.

### 8.3 Victim selection (only among valid ways, only when no invalid way exists)

- **LRU:** victim = valid way with smallest `stamp_used`; `stamp_used` is
  updated on every hit and every fill. (Unique stamps ⇒ no ties.)
- **FIFO:** victim = valid way with smallest `stamp_insert`; `stamp_insert` is
  set only on fill; hits never touch it. (No ties.)
- **RANDOM:** victim = `rng() % ways_in_set`, where `ways_in_set` is the
  engine-geometry way count of the victim set — `associativity` for
  `set_associative`, `capacity / block_size` for `fully_associative`, and 1
  for `direct` (where no policy is selectable, so RANDOM never arises:
  validation rejects `policy` on direct-mapped configurations; the modulus
  is stated for completeness). `rng` is a single `std::mt19937` instance
  seeded once with the config `seed` before the trace begins; **one `uint32`
  draw is consumed per valid-line eviction and never otherwise** (invalid-line
  fills consume no draws). Draw order = trace order ⇒ deterministic.

Direct-mapped caches expose no policy selection (one line per set); their
events report `policy: null`.

### 8.4 Counting

- `loaded = true` on every miss (the block enters the cache), `false` on hits.
- `evictions` counts only displacements of **valid** lines.

## 9. Invariants (engine-asserted on every run)

1. `hits + misses = accesses`.
2. Nonempty trace ⇒ `hit_rate + miss_rate = 1` within 1e-9; empty ⇒ both `null`.
3. `0 ≤ evictions ≤ misses`.
4. A miss fills an invalid way before any eviction; fills never count as
   evictions.
5. Per set: valid lines have unique tags; `sum(valid) ≤ ways`; stamps strictly
   increasing in order of use.
6. Determinism: same version + config + trace + seed ⇒ byte-identical result
   file (checked in tests by diffing two runs).

Violations abort with `E_INTERNAL` (they are engine bugs, never user errors).

## 10. Explanation string templates (exact)

- Hit: `Hit: block {b} found in set {s} way {w} (tag {t}).`
- Miss, filled invalid way: `Miss: block {b} loaded into set {s} way {w} (empty line).`
- Miss, eviction: `Miss: block {b} loaded into set {s} way {w}, evicting block {eb} ({why}).`
  where `{why}` is exactly one of the fixed tokens `LRU`, `FIFO`, `Random`,
  or `direct` (direct-mapped: the single-way forced eviction). The seed is
  carried in `policy_meta` and `summary.replacement_meta`, never embedded in
  the explanation string.
- Fully-associative wording uses `set 0` (single set), index reported `null`.

## 11. Error propagation and validation responsibilities

| Layer | Validates | Passes on |
|---|---|---|
| UI | widget ranges, required fields, early config sanity (mirrors engine rules for fast feedback) | complete config + trace to bots |
| Bot 1 | pattern params, manual text syntax, generated addresses vs. `max_address` and trace limit (asks engine `geometry` for authoritative geometry) | trace dict + config |
| Bot 2 | experiment mode rules (e.g., no policy comparison on direct), seed presence for RANDOM | N job dicts |
| engine_client | file I/O, exit codes, envelope shape, subprocess timeout | parsed envelope or structured error |
| engine | **authoritative** re-validation of everything (config, trace, limits) | envelope |

Rules: an error is never swallowed; each layer either handles it (retry only
for spawn/transient I/O failures in engine_client, max 2 retries) or attaches
context and re-raises. Validation errors are never retried. The UI maps
`E_CONFIG_INVALID` details to the matching sidebar control and highlights it.

## 12. Resource limits (canonical numbers)

| Limit | Value |
|---|---|
| Trace length (engine and bots) | 0–100,000 addresses |
| Address width | 4–64 bits |
| Block size | power of two, 1–128 bytes |
| Capacity | power of two, block ≤ capacity ≤ 1,048,576 (2²⁰) |
| Associativity (set-assoc) | power of two, 2 – capacity/block |
| Seed | 0–4,294,967,295 (uint32) |
| Timing inputs | finite numbers ≥ 0, unit cycles |
| Per-access state snapshots | allowed only when trace ≤ 2,000 accesses |
| Snapshot serialization budget | snapshots × total cache lines ≤ 2,000,000 (E_LIMIT) |
| Subprocess timeout (engine_client) | 30 s per run |

## 13. Worked reference examples (manually verified — use as test expectations)

All examples use address width 8 bits (max address 255). Geometry for all:
capacity 8 B, block size 2 B ⇒ lines = 4, offset_bits = 1.

- **E1 — repeated address (direct-mapped).** Config: direct, 8 B, 2 B blocks
  (sets = 4, index_bits = 2, tag_bits = 5). Trace `[16,16,16,16,16]`:
  address 16 → block 8 → set 0, tag 2, offset 0.
  Expected: 1 miss (fill), 4 hits, 0 evictions.
- **E2 — direct-mapped conflict.** Same config. Trace `[0,8,16,24,0]`:
  blocks 0,4,8,12 all map to set 0 (block mod 4 = 0), tags 0,1,2,3.
  Expected: 5 misses, 4 evictions, 0 hits. Final state: the last access
  (t5) reloads block 0, evicting block 12 — final set 0 holds block 0,
  tag 0. (Correction, Phase 3: an earlier revision of this line wrongly
  claimed the final line holds block 12; the per-access walk above is the
  authority and was re-verified line by line.)
- **E3 — LRU vs. FIFO (the controlled demonstration trace).** Config:
  set_associative, associativity 2 (sets = 2, index_bits = 1, tag_bits = 6).
  Trace `[0,4,0,8,4]` accesses blocks A=0, B=2, C=4 (all in set 0).
  - LRU: t1 A miss fill w0; t2 B miss fill w1; t3 A hit; t4 C miss evicts B
    (smallest used stamp); t5 B miss evicts A. **1 hit, 4 misses, 2 evictions.**
  - FIFO: t1 A fill w0 (insert 1); t2 B fill w1 (insert 2); t3 A hit (no
    reorder); t4 C miss evicts A (oldest insert); t5 B hit w1.
    **2 hits, 3 misses, 1 eviction.**
  - AMAT check (hit_time 1, miss_penalty 20): LRU 1 + 0.8×20 = **17.00**;
    FIFO 1 + 0.6×20 = **13.00** cycles.
- **E4 — fully-associative mapping.** Config: fully_associative, 8 B, 2 B
  blocks, LRU. Geometry: sets = 1, index_bits = 0, lines = 4.
  Trace `[0,4,8]`: three misses filling ways 0,1,2 of set 0; tags = block
  numbers 0,2,4; every event has `index: null`; 0 evictions.
- **E5 — RANDOM reproducibility and the pinned seed-12345 reference.** Config:
  set_associative, associativity 2, policy RANDOM, seed 7. Trace
  `[0,4,8,12,16]` (blocks 0,2,4,6,8 — all set 0). Two runs with the same seed
  produce byte-identical envelopes; the run with seed 8 is also deterministic
  but may differ from seed 7 (no specific victim order is asserted for
  different seeds). **Pinned RANDOM reference — E3 trace, RANDOM policy,
  seed 12345** (computed with the verified toolchain's `std::mt19937`, which
  was sanity-checked against the canonical MT19937 reference value 3499211612
  for seed 5489): draw 1 = 3992670690, so the t4 victim is
  3992670690 % 2 = way 0 → C evicts block A (block 0); draw 2 (3823185381)
  is never consumed. Full sequence: t1 A miss fills way 0; t2 B miss fills
  way 1; t3 A hit; t4 C miss evicts block 0 (`victim_selection: "random"`,
  `seed: 12345`); t5 B hit. **Outcome: 2 hits, 3 misses, 1 eviction,
  `rng_draws` 1; AMAT (hit_time 1, miss_penalty 20) = 13.00 cycles.** Phases
  4 and 7 must reproduce this exact sequence; it is also the RANDOM run in
  the §6.9 experiment-record example.
  **Pinned seed-7 walk for this E5 trace** (same methodology): draws
  327741615 (%2 = 1), 976413892 (%2 = 0), 3349725721 (%2 = 1) → t3 evicts
  block 2 (way 1), t4 evicts block 0 (way 0), t5 evicts block 4 (way 1);
  outcome 5 misses, 0 hits, 3 evictions, `rng_draws` 3; final state:
  way 0 = block 6, way 1 = block 8.
- **E6 — invalid-first fill.** Config as E3, LRU. Trace `[0,4,8,4,0]`:
  t1/t2 fill ways 0/1 (0 evictions so far); t3 evicts; t4 hit; t5 evicts.
  Expected: 4 misses, 1 hit, 2 evictions — proving no eviction happens while an
  invalid way exists (eviction count stays 0 through t2).

These six examples are embedded as engine tests in Phase 5 and referenced by
the Python integration tests in Phase 8.

## 14. Testing architecture

- **Engine tests** (`engine/tests/engine_tests.cpp`): single-file assert-based
  runner (no framework), sections per component; on failure prints section,
  case, expected vs. actual, and exits nonzero. Includes E1–E6, validation
  matrix, boundary tests (max address, block 1, capacity = block, assoc =
  capacity/block), empty/malformed traces, determinism double-runs, and
  invariant re-checks.
- **Python tests** (`pytest`, `tests/`):
  - unit: Bot 1 patterns and manual parser; Bot 2 matrix construction,
    direct-mapped refusal, summary-text determinism; engine-client envelope
    handling with a stub executable.
  - integration (require the built exe): run engine via engine_client on
    E1–E6 and compare against the same published expectations; error paths
    (invalid config → `E_CONFIG_INVALID` surfaces as a typed Python exception).
- **UI verification** (Phase 9–10): scripted browser walkthrough (real clicks)
  covering the §8 workflow of `prd.md`, including the AC-10 check that
  displayed numbers equal engine output.

## 15. Repository structure (target)

```
engine/                     C++ engine + Makefile
  include/ src/ tests/ third_party/nlohmann/
bots/                       trace_bot.py, experiment_bot.py, engine_client.py
ui/                         app.py, components.py, .streamlit/config.toml
schemas/                    *.schema.json (canonical contracts)
traces/                     sample traces (json + manual txt)
tests/                      pytest suite (unit + integration)
reports/                    saved experiment reports (created on demand)
docs/                       report material for submission
prd.md architecture.md rules.md design.md tasks.md memory.md README.md
requirements.txt requirements-dev.txt
```

Build artifacts under `build/` only. No duplicate schemas, manifests, or
folders beyond this list without a documented reason.
