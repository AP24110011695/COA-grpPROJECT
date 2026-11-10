# projdemo.md — How to Run and Demonstrate the COA Cache Simulator

This guide explains, in plain English, how to set up the application, what
every part of the screen does, and how to demonstrate the project live. Every
command, button, label, and number below was checked against the working
application and its test suites in this repository (verification note at the
end lists exactly what was executed). You do not need to know anything about
caches, C++, or "bots" before reading this — every technical word is
explained the first time it appears.

---

## Quick Start — Run the Project

**In VS Code, open the terminal (Git Bash recommended), then run:**

```bash
cd "/c/Projects/COA Cache Simulator with Two Automated Bots"
mingw32-make -C engine all        # build the C++ engine (skip if already built)
cd ui
python -m streamlit run app.py
```

Then open **http://localhost:8501** in your browser.
To stop the application, click the terminal and press **Ctrl + C**.

**PowerShell version** (verified to work as well — the build ran from
PowerShell too; if `mingw32-make` is not found there, use Git Bash for that
one step):

```powershell
cd "C:\Projects\COA Cache Simulator with Two Automated Bots"
mingw32-make -C engine all
cd ui
python -m streamlit run app.py
```

First-time setup (installing Python packages) is explained in Part 1.

---

## Part 1 — Setup, Build, Launch, Stop

### 1.1 What you need (prerequisites)

| Software | Version used by this project | Where it is needed |
|---|---|---|
| Python | 3.12 | The interface, the two bots, the tests |
| pip packages | `requirements.txt` (streamlit, matplotlib, pandas) + `requirements-dev.txt` (pytest, jsonschema) | Interface and tests |
| g++ (MinGW.org GCC-6.3.0) | 6.3.0 | The C++ engine |
| `mingw32-make` | ships with MinGW at `C:\MinGW\bin` | Building/testing the engine |
| A browser | any current Chrome/Edge/Firefox | Viewing the app |

There is nothing else to install: the engine's JSON library is one header
file already inside the project (`engine/third_party/`), the 3D view's
three.js library is vendored inside `ui/static/`, and the app runs entirely
on your machine (no network, no accounts, no API keys).

### 1.2 Open the project and the terminal

1. Open VS Code → **File → Open Folder…** → choose
   `C:\Projects\COA Cache Simulator with Two Automated Bots`.
2. Open the terminal: **Terminal → New Terminal** (or **Ctrl + `**).
3. In the terminal's top-right **▾** dropdown, pick **Git Bash**. Git Bash
   is the project's verified shell for the build commands; PowerShell also
   works for the Python commands (and was verified for the build too).

### 1.3 Install the Python dependencies (first time only)

From the project root:

```bash
pip install -r requirements.txt -r requirements-dev.txt
```

PowerShell: identical command (only the `cd` path looks different:
`cd "C:\Projects\COA Cache Simulator with Two Automated Bots"`).

### 1.4 Build the C++ engine

The actual cache simulation is a small C++ program
(`build/cache_sim.exe`). Build it once, and again only if you ever change
C++ code:

```bash
cd "/c/Projects/COA Cache Simulator with Two Automated Bots"
mingw32-make -C engine all
```

Success looks quiet — a few `g++` lines and no red text. A fresh build was
verified to compile with **zero warnings**. The result is
`build/cache_sim.exe`.

### 1.5 Start the app

```bash
cd ui
python -m streamlit run app.py
```

The terminal prints:

```
  You can now view your Streamlit app in your browser.

  Local URL: http://localhost:8501
```

Open **http://localhost:8501** (usually it opens by itself). You should see
the page title **"COA Cache Simulator"** and a left sidebar
**"Cache configuration"** with a **"Theme"** selector at the top.

> **Run it from the `ui/` folder** — the command above must be executed
> there so the app finds `ui/.streamlit/config.toml` (its theme settings).

### 1.6 Stop the app

Click the terminal and press **Ctrl + C**. The terminal returns to normal
and the browser page stops responding. To free a stuck port before
restarting, see Part 6 (Troubleshooting).

### 1.7 Know which folder each command needs

| Command | Run it from | Why |
|---|---|---|
| `pip install -r …` | Project root | The `requirements*.txt` files live there. |
| `mingw32-make -C engine all` | Project root | `-C engine` enters `engine/` for you. |
| `mingw32-make -C engine test` | Project root | Same reason. |
| `python -m pytest tests -q` | Project root | The `tests/` folder lives there. |
| `python -m streamlit run app.py` | **`ui/` folder** | Documented launch convention (loads the app theme). |

---

## Part 2 — What Every Part of the Screen Does

The app has one sidebar (left) and four tabs (top):
**Simulator**, **Experiments**, **Automated workflow**, **Help**.

### A. The Sidebar — "Cache configuration"

A **cache** is a small, fast memory that keeps copies of data the computer
uses often. When the processor reads an address, it first looks in the
cache: finding it is a **hit** (fast); not finding it is a **miss** (slow —
the data must be fetched from main memory).

**"Theme"** — `Light` / `Dark` selector at the very top. Light is the
default and reproduces the classic look; Dark applies a charcoal/navy
palette. This is presentation only — every number, table, and download is
identical in both themes. Two accepted quirks: refreshing the browser
always returns to Light, and in Dark mode the two interactive grid tables
(event log, cache state) keep Streamlit's light rendering inside their
themed containers.

**"Organization"** — how cache slots are arranged.

- Think of the cache as a parking lot with numbered spots, and every memory
  block as a car.
- **direct**: each car has exactly ONE allowed spot (`block number → one
  spot`). Simple, but two cars sharing a spot keep kicking each other out.
  The sidebar shows the caption *"Direct-mapped: one line per set, no
  policy choice."* and the policy box is greyed out.
- **set_associative**: the lot is divided into groups (**sets**); a car may
  park in any free spot **inside its group**. **"Associativity (ways,
  power of two)"** is the number of spots per group — it only appears for
  this organization, and only valid values are offered.
- **fully_associative**: one big group — a car may park anywhere. The
  sidebar caption states how many lines share the single set.

**"Capacity (bytes, power of two)"** — total cache size (default 8, up to
1,048,576). **"Block size (bytes, power of two, 1–128)"** — how many bytes
travel together as one block (default 2). **"Address width (bits, 4–64)"**
— how many bits an address has (default 16; width 8 → addresses 0–255).

**"Replacement policy"** — when a set is full and a new block arrives,
which old block leaves?

- **LRU** (Least Recently Used): evict the block unused for the longest
  time (hits refresh recency).
- **FIFO** (First In, First Out): evict the block that arrived first;
  hits never reorder it.
- **RANDOM**: evict a block chosen by a seeded random generator. The
  **"Random seed"** box (shown only for RANDOM, pre-filled 12345) makes it
  repeatable: same seed → same choices every run.

**"Timing assumptions (AMAT)" toggle** (on by default) with
**"Hit time (cycles, assumption)"** (1.00) and **"Miss penalty (cycles,
assumption)"** (20.00) — make-believe speeds used to compute **AMAT**
(Average Memory Access Time):

```
AMAT = hit time + miss rate × miss penalty
```

These are modeling assumptions in clock cycles, not measured hardware
timings. Turn the toggle off and the AMAT card shows "—".

Invalid combinations show a red message immediately (for example, setting
block size 128 with capacity 8 shows exactly
*"block_size_bytes (128) must not exceed capacity_bytes (8)."*) and the
main buttons become disabled until you fix it.

### B. Simulator tab

This tab answers: *"For this cache and this list of addresses, what happens
on every single access?"* The list of addresses is called a **trace**.

**"Trace source" (three choices):**

1. **"Bot 1 generator"** — Bot 1 is a small program that writes traces for
   you. Pick a **"Pattern"**:
   - *sequential*: addresses one after another (**"Start address"**,
     **"Access count"**, **"Byte stride"** — start 0, count 8, stride 4 →
     0, 4, 8, 12, 16, 20, 24, 28).
   - *repeated*: the same address again and again (**"Address"**,
     **"Repetitions"**) — great for showing hits.
   - *conflict*: addresses that all fight for the **same set**
     (**"Distinct blocks (same set)"**, **"Passes"**, **"Target set"**,
     **"Start block"**) — great for showing evictions.
   Then click **"Generate trace"**.
2. **"Manual paste"** — type addresses yourself in the text area labelled
   *"Addresses — one per line, decimal or 0x hex, # comments"*, then click
   **"Parse & load trace"**.
3. **"Sample file"** — pick a ready-made trace (the caption shows its path,
   e.g. *"Sample file: traces/e3-lru-vs-fifo.json"*), then click
   **"Load sample"**. Bundled samples: `e1-repeated.json`,
   `e2-conflict.json`, `e3-lru-vs-fifo.json`, `sequential-100.json`.

After loading, a preview line shows the trace name, where it came from, the
address count, and the first 32 addresses (e.g. **e3-lru-vs-fifo · Sample
file · 5 addresses** over `0, 4, 0, 8, 4`).

**"Run simulation"** (blue) starts the real C++ engine. It is disabled
(grey) until a trace is loaded and the sidebar configuration is valid.

**What appears after running:**

- A green line, e.g. *"Simulation complete — 5 accesses, 1 hit (20.00%)."*
- **Seven metric cards**: Accesses, Hits, Misses, Evictions, Hit rate,
  Miss rate, AMAT (cycles).
  - An **eviction** happens when a set is full and an old block is thrown
    out to make room. Filling an empty slot is NOT an eviction.
  - **Hit rate** = hits ÷ accesses, shown as a percent.
  - **AMAT** appears only when the timing toggle is on.
- **Cumulative hit-rate chart** — how the running hit rate evolves from
  the first access to the last; the dashed line marks 50%.
- **"Event log"** — one row per access: `n`, `address`, `block`, `tag`,
  `index`, `offset`, `set`, `way`, `result` (hit/miss), `evicted block`,
  and the engine's plain-language `explanation`. For a fully-associative
  cache `index` shows "—". The table is a live grid (scroll, sort by
  clicking a column, Search button). For long traces it shows the **most
  recent 500 rows** with the caption *"Showing the most recent 500 rows;
  download for the full log."* — **"Download all events (CSV)"** always
  saves everything.
- **"Cache state"** — the final contents, one row per set and one column
  per way. Filled cells show `tag X · blk Y`; the green cell is the most
  recently used line. The caption under the grid quotes the engine's
  explanation of the very last access.

If a run fails (for example an address larger than the address width
allows), a red **error card** appears with a code like `E_TRACE_INVALID`,
the exact problem, and the value you gave. Your previous successful results
stay on screen — nothing is erased.

### C. Experiments tab

Bot 2 runs **controlled experiments**: same trace, change exactly ONE
thing, compare fairly. You need a trace loaded first (otherwise the tab
shows a grey hint and **"Run experiments"** is disabled).

**"Experiment mode" (two choices, with captions):**

1. **`policy_comparison`** — keep the cache fixed, compare **LRU vs FIFO
   vs RANDOM**. A **"RANDOM seed"** box (pre-filled 12345) makes the
   RANDOM run repeatable and is recorded in the results.
2. **`organization_comparison`** — keep capacity, block size, and trace
   fixed, compare **direct vs set_associative vs fully_associative**.
   Your sidebar organization must be `set_associative` (it supplies the
   associativity); LRU is used wherever a policy exists, and the summary
   states that caveat.

The app refuses meaningless combinations with a clear red message:
policy comparison on a direct-mapped cache (`E_CONFIG_INVALID` — there is
no policy to compare) and organization comparison from a non-set-associative
sidebar config.

Click **"Run experiments"**. What appears:

- **Comparison table** — one row per run: Run, Policy (or Organization),
  Seed, Hits, Misses, Evictions, Hit rate, AMAT (cycles). The best hit
  rate is **bold**.
- **Grouped bar chart** — green hits, red misses, amber evictions per run.
- **"Summary"** — one plain-English sentence per run plus a conclusion,
  built only from the numbers.
- **"Save report"** — writes the full experiment record into the
  `reports/` folder as `<experiment_id>.json`; the caption
  *"Report saved to …"* shows the path. The record stores everything
  needed to repeat the experiment: the trace, all configs, the seed, the
  engine version, and every number. Report file names look like
  `exp-20261029-161214-007711-policy.json` (date, time, microseconds,
  mode). A save can never silently overwrite an existing report with
  different content — a conflict or disk failure surfaces as an error
  card, and the displayed record is kept.
- **"Download record (JSON)"** — saves the same record as a file through
  the browser.

### D. Automated workflow tab

This tab shows the whole project working by itself with **one click**. The
three players:

- **Bot 1** — writes a trace (here: a conflict trace for your sidebar
  configuration).
- **The C++ engine** — simulates the trace. It is the only part that
  computes cache behavior; the bots never invent results.
- **Bot 2** — runs the policy comparison on that trace and writes the
  report.

Inputs: **"Conflict blocks"** (default 4), **"Passes"** (default 1),
**"RANDOM seed"** (default 12345). Click **"Run automated workflow"**.

Four steps run in order, each as a live status box:

1. **Bot 1 — Trace Generation** → message like *"Generated 4 addresses in
   one set."*
2. **Engine — Simulation** → message like *"4 accesses, 0 hits."*
3. **Bot 2 — Policy Comparison** → *"Experiment complete."*
4. **Report** → the saved file path.

Below them, four persistent status pills read **DONE — Trace generation —
conflict-4b-set0-p1**, **DONE — Engine simulation — …accesses…**,
**DONE — Policy comparison**, **DONE — Report — …path…**, followed by the
workflow's own metric cards, comparison table, summary text, and a
**"Download workflow report (JSON)"** button.

If a step fails, its pill turns **FAILED**, a red error card explains why,
earlier finished steps stay visible, and a **"Retry failed step"** button
appears — it re-runs from the failed step only, keeping the earlier
results.

### E. Help tab and general behaviors

- **Help tab** — short reference cards: Concepts (organizations,
  policies), Metrics (formulas, the modeling-assumption note), Limits
  (trace/address/size caps), Reading the views, and the sample-trace list.
  Good to open if your teacher asks a definition.
- **Empty states** — before you run anything, grey cards say what is
  missing, e.g. *"No simulation yet. Configure the cache, choose a trace,
  and run."* They are normal, not errors.
- **Demo habit:** do **not** refresh the browser page (F5) during a
  demonstration. A refresh resets the session: results vanish and the
  theme returns to Light. If it happens, simply load the trace and run
  again — the numbers will be identical, because everything is
  deterministic.
- **Changing sidebar values does not re-run anything by itself.** Results
  change only when you press a button. Old results stay until you load a
  new trace or run again.
- The small **"Running…"** indicator (top right) appears while Streamlit
  works and disappears on its own.

---

## Part 3 — The Cache Machine (3D view)

After a simulation, the section **"The Cache Machine — 3D view"** appears
under the Cache state (Simulator tab). It replays the engine's own events
and per-access snapshots as a small 3D world. It displays engine output
only — it never computes cache behavior.

- **Left — Main Memory:** a wall of blocks. The blocks your trace uses are
  labeled (e.g. `blk 0`, `blk 2`); they never disappear — memory always
  keeps the original data.
- **Middle — Address Bus:** every access appears here as a chip that
  splits into `tag | index | offset` — how the simulator decodes an
  address.
- **Right — CPU Cache:** shelves (sets) with slots (ways). Filled slots
  hold a cached copy (`tag X · blk Y`).

**Controls (top of the view):** ▶ Play, ⏸ Pause, ◀ Previous, ▶| Next, ↺
Replay, ⏮ Reset, a speed dropdown (0.5×–4×), and a scrubber. Drag the
scene to orbit; scroll to zoom. A counters panel (Accesses / Hits / Misses
/ Evictions), the current access explanation, and a mini-log of all
accesses sit on/under the scene. The counters always match the 2D event
log — both come from the same engine result.

**During playback:** a **hit** pulses the cached copy green and sends a
packet back to the CPU (main memory untouched); a **miss into an empty
slot** pulses the slot and flies an amber copy of the block in from main
memory; a **miss with eviction** flashes the discarded copy red and fades
it (it is discarded, not written back), then the new copy flies in.

**Limits and fallbacks:** the 3D view is offered when the trace is at most
2,000 accesses and the cache fits the stage (at most 512 lines, 128 sets,
64 ways; the engine's snapshot budget also applies). Larger runs keep all
2D results and show a one-line reason instead, e.g. *"3D view unavailable
for this run: the trace has 3000 accesses; per-access snapshots are
capped at 2000 (docs/architecture.md §12)…"* Switching the theme rebuilds
the 3D view and resets playback to the start — press Play (or use the
scrubber) to resume; the data is unchanged.

---

## Part 4 — Step-by-Step Demonstration

This sequence uses the project's own worked example **E3** — the same five
addresses on the same cache where FIFO beats LRU. All numbers below were
re-verified against the running application and the engine.

**One-line story of the demo:** same five addresses, same cache, three
replacement policies — FIFO and RANDOM get more hits than LRU. The
replacement policy really matters.

### Before your audience arrives

Run the app (Quick Start), open http://localhost:8501, and do nothing else.
Everything below happens live.

### Step 1 — Introduce the configuration

1. **Action:** point at the sidebar and set it exactly like this:
   - Theme: `Light` (or Dark — the numbers do not change)
   - Organization: `set_associative`
   - Capacity: `8`
   - Block size: `2`
   - Associativity: `2`
   - Address width: `8` *(type 8 — the default is 16)*
   - Replacement policy: `LRU`
   - Timing assumptions: ON (Hit time 1.00, Miss penalty 20.00)
2. **Expected result:** no red messages; the policy box is enabled.
3. **What it means:** a tiny 8-byte, 2-way set-associative cache with
   8-bit addresses (0–255) — small enough to check every number by hand.
   Derived geometry (the engine computes it): 4 lines, 2 sets, offset 1
   bit, index 1 bit, tag 6 bits, max address 255.

### Step 2 — Load the demonstration trace

1. **Action:** in the **Simulator** tab, set Trace source to
   **"Sample file"**, pick **`e3-lru-vs-fifo.json`**, click
   **"Load sample"**.
2. **Expected result:** the preview shows `e3-lru-vs-fifo · Sample file ·
   5 addresses` and the block `0, 4, 0, 8, 4`.
3. **What it means:** three memory blocks (A=0, B=2, C=4) are read in the
   order A, B, A, C, B. All three map to set 0, which only has two slots —
   the cache is forced to make replacement decisions.

### Step 3 — Run the LRU simulation and read the metrics

1. **Action:** click **"Run simulation"**.
2. **Expected result** (verified):
   - Green line: *"Simulation complete — 5 accesses, 1 hit (20.00%)."*
   - Cards: Accesses 5, Hits 1, Misses 4, Evictions 2, Hit rate 20.00%,
     Miss rate 80.00%, AMAT (cycles) 17.00.
3. **Hand check you can show:** AMAT = 1 + 0.8 × 20 = 17.00 cycles. Only
   the second read of A (access 3) was a hit; when C arrived, LRU removed
   B (least recently used), so B's re-read missed.
4. **Point at the Event log** — five rows, each with the engine's
   explanation, e.g. row 4: *"Miss: block 4 loaded into set 0 way 1,
   evicting block 2 (LRU)."* — and the **Cache state** grid: Set 0 holds
   `tag 1 · blk 2` (green, most recently used) and `tag 2 · blk 4`; Set 1
   is empty. The caption repeats the last access explanation.

### Step 4 — Show the same run in the 3D view

1. **Action:** scroll to **"The Cache Machine — 3D view"**. Press **Next**
   (▶|) a few times, or **Play**.
2. **Expected result:** the progress reads *k / 5*; after two steps the
   counters show *Accesses 2, Misses 2*; after four steps *Accesses 4,
   Hits 1, Misses 3, Evictions 1* — identical to the 2D cards, because
   both come from the same engine events.
3. **What to say:** *"Memory on the left never changes — the cache only
   keeps copies. Each access is decoded on the bus into tag, index and
   offset, and the cache shelf on the right shows where the block lands."*

### Step 5 — Demonstrate Bot 1 trace generation

1. **Action:** still in the Simulator tab, set Trace source to
   **"Bot 1 generator"**, Pattern **`conflict`**, Distinct blocks `3`,
   Passes `1`, Target set `0`, Start block `0`. Click
   **"Generate trace"**.
2. **Expected result:** the preview shows `conflict-3b-set0-p1 · Bot 1
   generator · 3 addresses` over `0, 4, 8` — three blocks that all map to
   set 0 of your 2-set cache (blocks 0, 2, 4).
3. **Action:** click **"Run simulation"**.
4. **Expected result (verified):** 3 accesses, 0 hits, 3 misses, 1
   eviction, hit rate 0.00%, AMAT 21.00 (= 1 + 1.0 × 20). The third block
   had to evict the first — a conflict miss made visible.
5. **What to say:** *"Bot 1 writes traces on purpose: sequential,
   repeated, or — like here — a conflict pattern that forces evictions on
   any cache configuration I choose."*

### Step 6 — Bot 2's controlled experiment (policies)

1. **Action:** load `e3-lru-vs-fifo.json` again (Sample file → Load
   sample), then open the **Experiments** tab. Leave mode
   `policy_comparison`, RANDOM seed `12345`. Click **"Run experiments"**.
2. **Expected result** (verified — the table shows exactly):

   | Run | Policy | Seed | Hits | Misses | Evictions | Hit rate | AMAT (cycles) |
   |---|---|---|---|---|---|---|---|
   | 1 | LRU | — | 1 | 4 | 2 | 20.00% | 17.00 |
   | 2 | FIFO | — | 2 | 3 | 1 | **40.00%** | 13.00 |
   | 3 | RANDOM | 12345 | 2 | 3 | 1 | **40.00%** | 13.00 |

   Summary: *"LRU: 1 hit / 5 accesses (20.00%), 2 evictions. FIFO: 2 hits
   / 5 accesses (40.00%), 1 eviction. RANDOM (seed 12345): 2 hits / 5
   accesses (40.00%), 1 eviction. Best hit rate: FIFO and RANDOM tie at
   40.00% (LRU 20.00%)."* (best rates bold in the table)
3. **What it means:** same trace, same cache — only the policy changed.
   FIFO's rule (evict the oldest resident) kept B in the cache, so B's
   re-read hit. LRU had just evicted B. The RANDOM run used exactly one
   random draw; seed 12345 is recorded in the results, so anyone can
   re-run it and get the same answer.
4. **Optional, if time allows:** switch to `organization_comparison` and
   run — the table compares direct / set_associative / fully_associative
   on the same trace (LRU wherever a policy exists; the summary includes
   that caveat).

### Step 7 — Save the report and download it

1. **Action:** click **"Save report"**, then **"Download record (JSON)"**.
2. **Expected result:** the caption *"Report saved to
   …\reports\exp-<date>-<time>-<microseconds>-policy.json"*; the browser
   downloads the same record.
3. **What to say:** *"The record contains the trace, all three
   configurations, the seed, the engine version and every number —
   re-running it reproduces this exact result. A save can never overwrite
   an existing report with different content."*

### Step 8 — The one-click automated workflow

1. **Action:** open the **Automated workflow** tab. Leave Conflict blocks
   4, Passes 1, RANDOM seed 12345. Click **"Run automated workflow"**.
2. **Expected result:** four status boxes complete in order (Bot 1 —
   Trace Generation → Engine — Simulation → Bot 2 — Policy Comparison),
   then four DONE pills, the workflow metric cards for the generated
   conflict trace (4 accesses, 0 hits, 2 evictions, AMAT 21.00), the
   comparison table, the summary text, and the saved-report path.
3. **What to say:** *"The two bots and the engine cooperate on their own:
   Bot 1 generates a conflict trace from my configuration, the engine
   simulates it, Bot 2 compares the policies, and the report is saved —
   with per-step status the whole way."*

### Step 9 — Invalid input never crashes the app

1. **Action:** in the Simulator tab choose **"Manual paste"** and type
   `0x10`, then `abc`, then `300` on three lines. Click
   **"Parse & load trace"**.
2. **Expected result (verified):** a red error card
   **E_TRACE_INVALID — manual trace text has 2 problem line(s)** with
   details `line 2: not a valid address (decimal or 0x hex) (received:
   'abc')` and `line 3: must be between 0 and 255 (received: '300')` —
   and your earlier successful results are still on screen above it.
3. **Action:** set the sidebar Block size to `128` (with Capacity 8).
4. **Expected result:** the sidebar message *"block_size_bytes (128) must
   not exceed capacity_bytes (8)."* appears and the buttons disable until
   you set it back to `2`.
5. **What to say:** *"Every invalid input gets a structured message
   naming the field, the problem and the received value — the app keeps
   running and keeps the good results."*

### Short speaking script (in your own words)

- **Opening:** *"This is a cache memory simulator. A cache is a small,
  fast memory in front of main memory. It shows how cache design and the
  replacement policy change performance."*
- **Architecture:** *"The simulation itself is a C++ engine — the single
  source of truth for every number. Two automated bots prepare the work:
  one generates address traces, the other runs controlled experiments.
  The interface only shows the engine's results."*
- **Main point:** *"On the same trace and the same cache, LRU scored 1
  hit but FIFO scored 2 — same hardware, different policy, different
  speed. RANDOM is seeded, so its results are repeatable."*
- **Closing:** *"Every result can be checked access by access in the
  event log and replayed in the 3D view, and every experiment saves a
  reproducible record. Thank you."*

---

## Part 5 — Verification Commands

Run these from the project root (Git Bash; PowerShell also worked for all
of them during verification):

```bash
python -m pytest tests -q        # the whole Python suite
mingw32-make -C engine test      # the C++ engine suite
mingw32-make -C engine all       # build check (zero warnings expected)
```

**What success looks like:**

- `pytest`: the last line reads **`202 passed, 4 warnings in …s`**. The 4
  warnings are third-party *deprecation notices* (from the installed
  `pytest-asyncio`/`jsonschema` versions) — they are not failures and are
  safe to ignore. Any word like `failed` or `error` in the summary line is
  a real failure.
- Engine tests: the last line reads **`summary: 729 checks, 0 failures`**
  (17 sections run before it; a `100000-access simulate` timing line such
  as `0.08 s` is informational). Any `FAILURES: n` means a real failure.
- Build: a few `g++` lines and no red text; `mingw32-make` printing
  `Nothing to be done for 'all'.` means the engine is already built —
  also fine.

The engine can also be exercised directly (JSON in, JSON out):

```bash
build/cache_sim.exe --mode version
build/cache_sim.exe --mode geometry --in config.json
build/cache_sim.exe --mode simulate --in job.json
```

---

## Part 6 — Troubleshooting

**`python -m streamlit run app.py` says it can't open `app.py`.**
You are not in the `ui/` folder. Run `cd ui` first (see §1.7).

**`No module named streamlit` (or matplotlib/pandas).**
From the project root: `pip install -r requirements.txt -r
requirements-dev.txt`.

**`mingw32-make` is not found.**
The MinGW bin folder (`C:\MinGW\bin`) is missing from PATH, or you are in
a shell that cannot see it. Use the Git Bash terminal in VS Code. If it
still fails, MinGW itself is not installed — install MinGW.org GCC 6.3 (or
ask your instructor for the course environment) and retry.

**The build prints errors about `g++` or missing headers.**
Read the first red line — it names the file and the problem. The engine
needs only the C++14 standard library plus the vendored header in
`engine/third_party/`; a compiler older than GCC 6 may not be sufficient.

**The browser page does not open / the port is busy.**
The terminal prints the real `Local URL:` — open that address yourself.
If port 8501 is already used by an older copy of the app, press **Ctrl +
C** in that older terminal first, then start again (or start on another
port with `python -m streamlit run app.py --server.port 8502` and open
http://localhost:8502).

**A red error card says the engine executable was not found (`E_INTERNAL`,
mentions `mingw32-make`).**
The engine was never built (or `build/` was deleted). Run
`mingw32-make -C engine all` from the project root, then press the button
again.

**A button is grey / disabled.**
"Run simulation" and "Run experiments" need a loaded trace. Buttons also
disable while the sidebar configuration is invalid — fix the red sidebar
message first (see Step 9 for the exact example).

**A red error card appears (`E_CONFIG_INVALID`, `E_TRACE_INVALID`,
`E_LIMIT`, …).**
This is the app working correctly. The card names the field, the rule,
and the value you gave. Fix that one thing and press the button again;
your earlier results are not erased.

**An experiment refuses to run on a direct-mapped cache.**
Intentional: one line per set means there is no replacement policy to
compare. Switch the sidebar Organization to `set_associative` (or use
`organization_comparison`).

**A workflow step failed.**
Press **"Retry failed step"** — it re-runs from the failed step and keeps
everything that already succeeded. If the trace step keeps failing, read
the red card (usually an address outside the configured width).

**My numbers differ from this guide.**
The results depend on the exact configuration, trace, and seed. The guide's
numbers need: `set_associative`, capacity 8, block 2, associativity 2,
**address width 8**, trace `e3-lru-vs-fifo.json`, seed 12345. A different
width, capacity, policy, or seed gives different — still correct —
results.

**I refreshed the browser and everything vanished.**
That is how Streamlit sessions work. Reload the trace and run again — all
numbers are deterministic, so you will get exactly the same results. The
theme also returns to Light on refresh.

**The 3D view disappeared / says "unavailable for this run".**
The 3D view has stage limits (trace ≤ 2,000 accesses; ≤ 512 cache lines,
128 sets, 64 ways). All 2D results remain fully available. For the demo
traces in this guide the 3D view is always available.

---

## Part 7 — Demonstration Checklist

Print this and tick it off before the presentation:

- [ ] Terminal opens in the project root; `build/cache_sim.exe` exists
      (or `mingw32-make -C engine all` completes quietly).
- [ ] `mingw32-make -C engine test` ends with `summary: 729 checks,
      0 failures`.
- [ ] `python -m pytest tests -q` ends with `202 passed` (warnings are
      OK; failures are not).
- [ ] App started from the `ui/` folder; http://localhost:8501 shows
      "COA Cache Simulator" with the sidebar and four tabs.
- [ ] Sidebar set for the demo: set_associative / 8 / 2 / 2 / width 8 /
      LRU / timing ON.
- [ ] `e3-lru-vs-fifo.json` loads; simulation shows 5 accesses, 1 hit,
      4 misses, 2 evictions, 20.00%, AMAT 17.00.
- [ ] 3D view plays and its counters match the metric cards.
- [ ] Bot 1 conflict trace (3 blocks) shows `conflict-3b-set0-p1` =
      0, 4, 8 → 3 accesses, 1 eviction.
- [ ] Experiments policy table: LRU 20.00% vs FIFO/RANDOM 40.00%
      (seed 12345); "Save report" writes into `reports/`.
- [ ] Automated workflow ends with four DONE pills.
- [ ] Invalid input (paste `abc` / `300`) shows the error card without
      erasing results.
- [ ] Browser refresh NOT pressed during the demo (or results re-run
      knowingly).

---

*Verification note (2026-10-29): every command, control name, tab, caption,
error message, and number in this guide was executed or checked against the
current repository in this environment — the Python suite (`202 passed, 4
warnings`), the engine suite (`summary: 729 checks, 0 failures`), a from-
scratch engine rebuild (zero warnings, Git Bash and PowerShell), 31 direct
engine-CLI checks against the hand-verified worked examples E1–E6, 40
end-to-end Bot 2 checks (including a byte-identical policy comparison
against `docs/demo-record.json` and report save/conflict behavior), and a
live browser walkthrough of the full demo sequence above (configuration,
sample load, LRU metrics, event log, cache state, 3D playback counters,
Light/Dark switching, the policy experiment, report save with the
microsecond file name, the automated workflow's four DONE steps, and the
invalid-input error cards). The only items not re-executed here are the
PowerShell launch from a shell without Git's `sh` on PATH (the project's
documented convention is Git Bash, which was verified) and the animation
appearance details quoted from the delivered design record
(`docs/design.md` §6.9) rather than re-judged frame by frame.*
