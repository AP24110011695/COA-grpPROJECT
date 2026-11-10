# Phase 9 walkthrough record — scripted browser session (2026-10-24)

Scripted browser walkthrough of `ui/app.py` (Streamlit 1.66.1, launched
headless from `ui/` so `ui/.streamlit/config.toml` applies), driven with
real interactions (clicks, fills, select options) via the browser-use
tooling. Evidence screenshots in `docs/screenshots/`.

## Steps and observed results

1. **Initial render.** Sidebar "Cache configuration" with power-of-two
   selects (set_associative, 8 B, 2 B, 2-way, LRU), width 16, timing
   toggle on (1.00 / 20.00); four tabs; empty state "No simulation yet.
   Configure the cache, choose a trace, and run."; Run button disabled
   while no trace is loaded. _(09-simulator-top.png, taken later in the
   pass)_
2. **§14 demonstration configuration.** Address width set to 8 via the
   sidebar; trace source switched to "Sample file"; sample
   `e3-lru-vs-fifo.json` selected and loaded; preview shows
   `e3-lru-vs-fifo · Sample file · 5 addresses` and the mono block
   `0, 4, 0, 8, 4`.
3. **Simulation (LRU).** "Run simulation" → confirmation line "Simulation
   complete — 5 accesses, 1 hit (20.00%)." and metric cards
   **Accesses 5 / Hits 1 / Misses 4 / Evictions 2 / Hit rate 20.00% /
   Miss rate 80.00% / AMAT (cycles) 17.00** — exactly the published §14
   LRU numbers. Event log shows the five LRU events with the engine's
   explanations; cache-state grid shows Set 0: Way 0 `tag 1 · blk 2`
   (most-recent highlight), Way 1 `tag 2 · blk 4`, Set 1 empty, with the
   caption "Last access: Miss: block 2 loaded into set 0 way 0, evicting
   block 0 (LRU)." _(09-simulator-metrics.png, 09-events-state.png)_
4. **Experiments (policy comparison, seed 12345).** Comparison table:
   LRU 1/4/2 20.00% AMAT 17.00 — FIFO 2/3/1 40.00% 13.00 — RANDOM
   (seed 12345 recorded) 2/3/1 40.00% 13.00, best rate bolded. Grouped
   bar chart (hits green / misses red / evictions amber). Summary text
   byte-identical to the Phase 7 template: "LRU: 1 hit / 5 accesses
   (20.00%), 2 evictions. FIFO: 2 hits / 5 accesses (40.00%), 1
   eviction. RANDOM (seed 12345): 2 hits / 5 accesses (40.00%), 1
   eviction. Best hit rate: FIFO and RANDOM tie at 40.00% (LRU 20.00%)."
   "Save report" wrote `reports/exp-20261024-195913-policy.json`
   (caption confirmed on screen). _(09-experiments.png)_
5. **Automated workflow.** One click ran all four steps: Bot 1 →
   Engine → Bot 2, each status container completing with its engine
   output; four DONE pills; report saved to
   `reports/exp-20261024-195913-policy.json`; workflow results rendered
   with the same components as the tabs. _(09-workflow.png)_
6. **Forced failure (bad trace).** With the successful simulation on
   screen, a manual paste of `300` (over the 8-bit maximum of 255) was
   parsed: the error card `E_TRACE_INVALID — manual trace text has 1
problem line(s)` with detail `line 1: must be between 0 and 255
(received: '300')` appeared **and the earlier successful results
   stayed fully visible** (metrics, AMAT 17.00). No crash.
   _(09-error-state.png)_
7. **Help tab.** Concepts, metrics formulas (with the modeling-assumption
   note), limits, reading guide, and the sample-trace list.
   _(09-help.png)_

## Design checklist (design.md §1) — verified in the captures

- No gradients, glassmorphism, glow, emoji, or oversized headings.
- Restrained palette: one accent blue, semantic green/red/amber only for
  meaning; hairline borders; subtle background cards.
- Monospaced numerics in the metric values, event log, and trace preview.
- Status pills (IDLE/RUNNING/DONE/FAILED) with text labels — never
  color-only.
- Every number on screen traced to engine output; sample traces labeled
  as samples.

## Issues found during the walkthrough and fixed at the root

1. `StreamlitDuplicateElementId` crash: the workflow's RANDOM-seed input
   collided with the Experiments tab's (unique `key`s added).
2. The state-grid data/style frames lacked matching "Set" index labels
   (`Styler.apply` alignment ValueError) — both frames now carry the
   same labels.
3. Trace-load errors blanked earlier results — errors now leave the
   still-loaded trace and results visible (design.md 7).
4. Status-pill text ran together without a separator; the confirmation
   line and metric labels had plural/unit polish ("1 hit",
   "AMAT (cycles) 17.00").

All four were fixed, the server restarted, and the affected steps were
re-run and re-captured — every capture in this pass is post-fix.
