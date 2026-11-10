# design.md — UI design system: COA Cache Simulator

> The visual and interaction system for the Streamlit app. The goal is a
> carefully designed engineering tool — a lab instrument, not a dashboard and
> not a landing page. Clarity, simulation transparency, and usability outrank
> decoration in every decision below.

---

## 1. Product visual direction

A compact, precise, datasheet-like interface: light background, hairline
borders, dense but readable tables, monospaced numerics, one restrained accent
blue, and semantic colors used only for meaning (hit/miss/error), never
decoration. Everything on screen exists because a student or instructor needs
it to read a simulation result.

Avoid: gradients, glassmorphism, glow, oversized headings, decorative emoji,
excessive rounded cards, meaningless metric tiles, generic dashboard chrome,
color-only signaling.

## 2. Layout

- Streamlit **wide layout**; main content max-width **1100 px** (CSS on
  `.block-container`), left-aligned with generous top padding (24 px).
- **Sidebar** (fixed, ~360 px): "Cache Configuration" — all cache parameters,
  timing assumptions, and (in Simulator tab) trace controls live here. The
  sidebar is the single configuration surface; the main area only shows results.
- **Main area tabs** (Streamlit `st.tabs`, in this order):
  1. **Simulator** — trace preview, run button, metric cards, event table,
     cache-state grid.
  2. **Experiments** — Bot 2 controls (mode, seed), comparison table, chart,
     summary text, report save/download.
  3. **Automated Workflow** — one-click Bot 1 → engine → Bot 2 run with
     per-step status and combined report.
  4. **Help** — concepts, formulas, limits, how to read each view.
- Responsive: below ~900 px the sidebar stacks (Streamlit default); tables
  scroll horizontally rather than squashing; charts reflow to container width.
- Whitespace: results grouped in bordered cards (see §6) with 16 px internal
  padding and 16 px vertical rhythm between cards.

## 3. Typography

- UI text: `Inter, "Segoe UI", system-ui, sans-serif` (Inter loaded if
  available; Segoe UI is the verified Windows fallback).
- Numerics, addresses, tags, tables of addresses, all hex/binary fields:
  `"JetBrains Mono", "Cascadia Mono", Consolas, monospace`.
- Scale (px): page title 20 semibold; section headers 15 semibold; body 14;
  table text 13; captions/labels 12; never below 12.
- Case: sentence case everywhere ("Run simulation", "Hit rate"); no all-caps
  except status pill labels (HIT/MISS/IDLE/RUNNING/DONE/FAILED).

## 4. Color tokens (explicit)

| Token | Hex | Use |
|---|---|---|
| `--bg` | `#FFFFFF` | page background |
| `--bg-subtle` | `#F5F7FA` | cards, table header rows, code blocks |
| `--border` | `#D9DEE4` | hairline borders, dividers |
| `--text` | `#1F2933` | primary text |
| `--text-secondary` | `#52606D` | labels, captions |
| `--accent` | `#1F5FA8` | primary buttons, links, focused elements, chart series 1 |
| `--accent-soft` | `#E8F0F8` | selected/valid cache lines, hover fills |
| `--success` | `#2E7D32` | hits, DONE states, positive deltas |
| `--success-soft` | `#E6F2E8` | hit cell fill |
| `--danger` | `#C62828` | misses, FAILED states, error text |
| `--danger-soft` | `#FBEAEA` | miss cell fill |
| `--warning` | `#B26A00` | evictions, warnings |
| `--warning-soft` | `#FBF1E2` | eviction highlighting |
| `--bot1` | `#1F5FA8` | Bot 1 identity (same family as accent) |
| `--bot2` | `#0B7285` | Bot 2 identity (teal) |

- Chart series order and colors: accent `#1F5FA8`, teal `#0B7285`, amber
  `#B26A00`, gray `#52606D`. Hits = green `#2E7D32`, misses = red `#C62828`
  wherever the hit/miss distinction appears in a chart.
- All text/background pairs above meet WCAG AA (≥ 4.5:1) on their intended
  backgrounds; soft fills are never used behind primary text.

## 5. Spacing scale

4, 8, 12, 16, 24, 32 px. Rules: 8 px inside control groups, 16 px between
cards and around section headers, 24 px before major sections, 32 px page
top. No other spacing values without a reason.

## 6. Components

### 6.1 Cards
Bordered (`1px solid var(--border)`, radius 6 px) on `--bg-subtle`; a 15 px
semibold header line and body content. Used for: result groups, each bot's
output, Help sections. No shadows, no nested cards.

### 6.2 Buttons
- Primary (one per view: "Run simulation", "Run experiments", "Run automated
  workflow"): accent background, white text, radius 4 px, 8×16 px padding.
- Secondary/reset: white background, border, `--text` label.
- Disabled state: 40% opacity with an adjacent caption explaining why
  ("Configure a valid cache to enable").
- Destructive actions (clear trace/report): secondary styling only; no red
  buttons (nothing here is truly destructive).

### 6.3 Form controls (sidebar)
- Number inputs with explicit `min`/`max`/`step` from `architecture.md` §12;
  the accepted range is stated in the field label (e.g., "Block size (bytes,
  power of two, 1–128)").
- Select boxes for organization and policy; policy options adapt to the
  organization (direct-mapped ⇒ policy control disabled with caption
  "Direct-mapped: one line per set, no policy choice").
- Seed: number input shown only when policy = RANDOM, pre-filled 12345.
- Hit time / miss penalty: number inputs in cycles, labels marked
  "(assumption)".
- Capacity/block/associativity: offered as power-of-two select boxes (values
  1…128 for block; capacities up to 1,048,576) instead of free integers —
  this makes invalid input untypable while staying honest (the engine still
  validates authoritatively).
- Validation feedback: inline under the field, `--danger` text, 12 px,
  phrased per `rules.md` §3; the affected field gets a 2 px `--danger` border
  (via CSS class where Streamlit allows; otherwise the message alone).

### 6.4 Tables
- `st.dataframe` for the event log (interactive, scrollable): columns exactly
  the event fields (`n`, address, block, tag, index, offset, set, way, result,
  loaded, evicted block, explanation). Monospace digits, right-aligned
  numbers, 13 px. Result column rendered as text `hit`/`miss` (lowercase) with
  green/red text via column styling.
- Cache-state grid: a compact DataFrame — rows = sets (label "Set 0…"),
  columns = ways ("Way 0…"). Cell content: `tag 2 · blk 4` for valid lines,
  `—` for invalid. Valid cells filled `--accent-soft`; the way touched by the
  most recent access filled `--success-soft`; a line evicted by the most
  recent access (its previous occupant noted in the caption) is referenced in
  a one-line caption under the grid, e.g. "Last access: miss, loaded block 4
  into set 0 way 1, evicted block 2 (LRU)." LRU/FIFO rank shown as a second
  line in the cell (`#1` = most recent / oldest-respective rank) in 11 px
  secondary text.
- Comparison table (Experiments): one row per run (policy/organization, hits,
  misses, evictions, hit rate %, miss rate %, AMAT, seed); best hit rate per
  column bolded. `st.table` (static) — comparisons must not be scrollable.

### 6.5 Status indicators (bots)
Pills with fixed labels: `IDLE` (gray `--border`/`--text-secondary`),
`RUNNING` (`--accent`, with Streamlit spinner inside the step), `DONE`
(`--success`), `FAILED` (`--danger`). Each pill is followed by a 12 px
timestamp and a one-line message ("Generated 32 addresses", "Engine exit 0,
5 events", "Error E_CONFIG_INVALID: block_size_bytes must be a power of two").
Both bots appear as two cards side by side; the workflow tab shows a vertical
step list (Bot 1 → Engine → Bot 2 → Report) using `st.status`.

### 6.6 Metric cards (summary statistics)
A single row of compact stat blocks: label (12 px, secondary) over value
(20 px, semibold, monospace): Accesses, Hits, Misses, Evictions, Hit rate,
Miss rate, AMAT (cycles). Rate values show two decimals in percent (e.g.,
`40.00%` — prd.md §7 governs the display rounding); AMAT shows `13.00 cycles` or `—` when assumptions are absent. No
icons, no deltas, no invented KPIs.

### 6.7 Charts (matplotlib, `st.pyplot`, dpi 150)
- **Comparison bar chart** (Experiments): grouped bars — x axis = policy or
  organization (exact run labels), series = Hits (`--success`), Misses
  (`--danger`), Evictions (`--warning`); y axis integer-labeled "Count";
  title states the fixed parameters (e.g., "Policy comparison — 2-way, 8 B,
  block 2 B, trace lru-vs-fifo-demo"). Legend one row, top, no frame.
- **Hit-rate line chart** (Simulator): cumulative hit rate vs. access number;
  accent line 1.5 px; y axis 0–1 ("Cumulative hit rate"); x axis "Access
  number"; faint dashed 50% reference line in `--border` gray.
- Rules: axis titles always; units in axis titles; chart titles descriptive
  not cute; source data always the engine's numbers; identical color meaning
  across all charts; gridlines only horizontal, `--border` color, 0.5 px;
  no pie charts, no 3-D, no annotations beyond necessary value labels on bars.

### 6.8 Trace preview
Monospace block (`--bg-subtle`, 13 px): first N = 32 addresses, then "… 968
more"; header line with trace name, pattern/origin, count, and the
configuration it was validated against. Full trace available via the event
table and downloads. A horizontal "address strip" is explicitly avoided —
it adds noise, not information.

### 6.9 The Cache Machine — 3D view (post-delivery enhancement)
A three-lane 3D diorama under the cache state in the Simulator tab:
**Main Memory** (a wall of block slabs — the persistent source of data),
**Address Bus** (the decoding stage: each access appears as an address chip
that splits into tag | index | offset), and **CPU Cache** (shelves = sets,
slots = ways; filled slots show `tag X · blk Y`). The scene replays the
engine's own events and per-access snapshots — hits pulse green with a
response packet returning to the CPU, misses copy a block from memory into
a slot, evictions flash the discarded cached copy red with the policy
reason labeled. Playback controls (Play/Pause/Next/Previous/Replay/Reset,
speed, scrubber) and a compact info/counters/mini-log panel live inside the
embedded component; the panel state is self-contained. Outcomes are always
text-labeled, never color-only. Palette and tokens come from §4. Limits
and fallbacks: traces ≤ 2,000 accesses, snapshot budget, stage caps (512
lines / 128 sets / 64 ways) — beyond them the section explains why and the
2D views remain. Implemented with vendored three.js r128 (MIT).

### 6.10 Theme selection — Light/Dark (post-delivery enhancement)
A Light/Dark selector at the top of the sidebar (above cache
configuration), implemented in `app.py` as a session-state selectbox:
**Light is the default** and reproduces the delivered appearance exactly
(light tokens in §4 are asserted verbatim by tests). Dark mode applies the
dark counterparts of every §4 token (defined alongside them in
`ui/tokens.py` `THEMES` — charcoal/navy surfaces `#16181D`/`#1F232B`, no
pure black, soft accents; text ≥ 4.5:1 and borders ≥ 3:1 WCAG-verified and
test-asserted). Presentation only: no simulation data, controls, or
behavior change — events, snapshots, summaries, CSV downloads, and
experiment results are byte-identical across themes (test-asserted).
Mechanics: `components.inject_styles(theme)` appends `ui/styles_dark.css`
(project components consume the same CSS variables; Streamlit chrome
overrides are scoped to verified testids/classes); matplotlib charts take
the active palette with transparent figure backgrounds; the 3D view
receives `theme` as presentation-only payload metadata and selects a scene
palette plus `ui/scene_dark.css` (`body.cm-dark`). Persistence: session
state survives reruns and tab navigation; browser refresh resets to Light
in V1 (accepted). Accepted fallback: switching theme rebuilds the 3D
iframe, resetting playback to access 1 paused. Known V1 limitation: the
`st.dataframe` event-log/state-grid canvases keep Streamlit's light
rendering inside themed containers (full-dark grids would need
`theme.base` runtime switching, unsupported on Streamlit 1.66).

## 7. State design

| State | Presentation |
|---|---|
| Loading | Streamlit spinner inside the relevant card/button; card headers stay visible; no full-page spinners |
| Empty (no run yet) | Card with 14 px secondary text: "No simulation yet. Configure the cache, choose a trace, and run." Each empty card says what unlocks it |
| Empty (no trace) | "No trace. Generate one with Bot 1, paste addresses, or load a sample." |
| Success | Metric cards + tables render; a single confirmation line "Simulation complete — 5 accesses, 2 hits (40.0%)" in `--success` text above results; no confetti, no banners |
| Warning | `--warning` text block, e.g., RANDOM policy without visible seed, or fully-associative conflict-pattern note; never blocks execution |
| Error | `--danger` card: error code (mono), message, field(s) to fix, and the exact retry affordance; bot FAILED pill in the workflow; the previous successful results remain visible (never blanked by an error) |

## 8. Bot execution model in the UI

- Every bot action is explicit (button press or part of the workflow button);
  bots never run merely because a widget changed.
- During the workflow, each step streams its one-line status into the step
  list as it completes; a failing step stops the sequence, marks the step
  FAILED with the error, and leaves earlier DONE steps visible. "Retry"
  re-runs only the failed step's group.
- Results of the workflow are the same components as the tabs' results
  (identical rendering functions) — no separate "workflow-only" view to
  maintain.

## 9. Accessibility and contrast

- All state changes are conveyed by text labels, never color alone
  (hit/miss are words; bot states are words; error cards contain full
  sentences).
- Contrast ≥ 4.5:1 for all text/background pairs (tokens in §4 were chosen to
  satisfy this; `--text-secondary` on `--bg-subtle` included).
- Number inputs expose ranges to assistive tech (Streamlit min/max); tab
  order is Streamlit's natural order; charts carry their data in an adjacent
  table (never chart-only information).
- Interactive elements have visible focus (Streamlit default retained; do not
  remove outlines via CSS).

## 10. UI copy style

- Sentence case; concise, technical, no exclamation marks, no emoji, no
  marketing adjectives ("blazing", "powerful" are banned).
- Numbers in copy match engine output exactly (no "about", no rounding beyond
  the display rules in `prd.md` §7).
- Error copy pattern: `[What failed]. [Received]. [Accepted range/fix].`
- Buttons are verbs: "Run simulation", "Run experiments", "Save report",
  "Download JSON", "Load sample trace".

## 11. Theming implementation (for Phase 9)

- `ui/.streamlit/config.toml`: theme mapping — primaryColor `#1F5FA8`,
  backgroundColor `#FFFFFF`, secondaryBackgroundColor `#F5F7FA`,
  textColor `#1F2933`, font "sans serif"; base "light".
- `ui/styles.css` injected once via `st.markdown(unsafe_allow_html=True)`:
  max-width, font stacks, table/mono refinements, card borders, pill styles.
  Keep the CSS under ~120 lines; if a style fights Streamlit, drop the style —
  never stack `!important` chains.
- All colors referenced from the token table in §4 (the CSS file defines them
  as CSS variables; Python code imports the same hex values from
  `ui/tokens.py` so charts and CSS never drift).

## 12. Data honesty

- The app renders engine output verbatim (formatting aside). No sample or
  illustrative numbers appear in any real view. Bundled sample traces
  (`traces/`) are clearly labeled "Sample" at the point of loading.
- Any future mock/screenshot data for documentation must live in `docs/`
  assets and be visibly watermarked "illustrative" — never loadable into the
  running app.
