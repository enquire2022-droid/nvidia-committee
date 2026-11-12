---
name: nvidia-committee
description: Run Ayham's NVIDIA Committee (multi-agent) review of NVDA - refresh data, brief the six specialists and the red team, chair the decision, write the memo, pass the verifier, log the calls. Use ONLY when asked to "Run NVIDIA committee" or "NVIDIA committee review".
---

# NVIDIA Committee (chair procedure)

You are the **chair**. Specialists judge; code computes; you decide and write. Work from the repo root with `PYTHONPATH=src`.

## 1. Data
Pull with the TradingView MCP and save into `inputs/readings.json` (one entry per page, `status` ok / partial / failed with reason, `data_time`):
- NVDA technicals 1W / 1D / 4H; weekly OHLCV appended to `data/nvda_weekly.json`; SOX and SPX weekly to `data/benchmarks_weekly.json`
- Owner's TradingView layout (Claude in Chrome, new tab): 1W and 1D, drawn levels, labels, oscillators; restore the starting timeframe; **never save the layout, never click Buy/Sell/Trade**
- Purple list (watchlist id 345068655) incl. `AMEX:RSP/AMEX:SPY`; peers AMD, AVGO, TSM, SOX, SMH, NDX, SPX quotes
- Financials, forecasts, financial history, earnings calendar, economic calendar (high importance, 30 days)
- News: TradingView NVDA feed + web search on the governance / export-control story
- Sentiment: AAII (latest week), CNN Fear & Greed; options positioning is **deferred (paid data)** - mark failed
```
python -m nvdaintel.factsheet      # engines -> outputs/fact_sheet.json
python -m nvdaintel.committee slices
```

## 2. Specialists (in parallel), then red team
Run id `YYYY-MM-DD-review`. Dispatch `nvda-technical`, `nvda-macro`, `nvda-fundamentals`, `nvda-relative-strength`, `nvda-sentiment`, `nvda-narrative` at once (agent files in `.claude/agents/`), then `nvda-red-team`. Every submission must pass `python -m nvdaintel.committee check`.

## 3. Decide
- One probability table, **never average**; rule on each disagreement. Count overlapping evidence once.
- Outside view first (`base_rates`); conditional base rates are weak (small, overlapping samples).
- Earnings rule: separate the pre-print and post-print view; no new ladder orders inside the 3-trading-day blackout unless the owner exempts them.
- Thesis breaks TB1-TB4 (approved): status of each; any one pauses buying.
- Ladder Audit before Strategy (from `fact_sheet.ladder_audit`): level, weight, distance, anchors, drift, spacing, cumulative average; propose changes, never apply. Budget is unset until the owner gives it.
- Stances: strategic (18-36m) and tactical (1-12w) from Accumulate / Hold / Wait / Reduce / Avoid New Entry.

## 4. Memo sections (in order)
Final committee decision -> Bottom line + what changed -> Macro (Purple list + dated catalysts) -> Technicals (1W/1D/4H) -> Fundamentals & earnings setup -> Relative strength -> Sentiment -> Narrative & governance -> Kahneman (System 1 / System 2) -> Outlook (probabilities) -> Expected path (checkpoints with windows) -> Ladder Audit -> Strategy -> Thesis-break update -> Committee table (members, red team, rulings) -> Dashboard -> Sources.

## 5. Verify, log, publish
```
python -m nvdaintel.verify outputs/reviews/<run_id>.md <run_id>     # must PASS
python -m nvdaintel.committee log <run_id>
```
Publish the memo as a Doc for the owner, commit and push.
