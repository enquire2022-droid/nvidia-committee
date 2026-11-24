---
name: nvidia-committee
description: Run Ayham's NVIDIA Committee (multi-agent) review of NVDA - score past forecasts, refresh every page, brief the six specialists and the red team, have an independent chair decide, write the memo, pass the verifier, log and copy the calls. Use ONLY when asked to "Run NVIDIA committee", "NVIDIA committee review" or "Score the NVIDIA committee".
---

# NVIDIA Committee (orchestrator procedure)

You are the **orchestrator**, not the chair (Tier 1, owner-approved 15 Nov 2026). You gather data, dispatch agents, write the memo
**only from chair.json and the fact sheet**, and run the gates. You never add your own judgment to the decision.
Work from the repo root with `PYTHONPATH=src`.

Commands: "Run NVIDIA committee" = steps 0-9. "Score the NVIDIA committee" = step 0 only.

## 0. Score the past
```
python -m nvdaintel.scoring            # needs data/nvda_daily.json refreshed (step 1) for new closes
```
If any forecast resolved since the last file in `committee/performance/`, dispatch `nvda-performance-review`; its proposals go in the
memo's "Performance review" section for the owner's approval. Apply none. Otherwise the section says "No forecasts resolved yet".

## 1. Read every page (config/pages.json — fixed list, no substitution)
```
python -m nvdaintel.committee readings-template     # inputs/readings.json, every page pending (old file archived)
```
For **every** page record `status` (ok / partial / failed + reason), `read_utc` (ISO UTC, the moment you read it), `data_time`, `values`.
- TradingView MCP: technicals 1W/1D/4H, OHLCV (append new daily bars to data/nvda_daily.json and weekly to data/nvda_weekly.json),
  Purple List quotes (incl. AMEX:RSP/AMEX:SPY), peers, fundamentals, earnings and economic calendars, news.
- **Hyperscaler capex**: financial-history for NASDAQ:MSFT, NASDAQ:GOOGL, NASDAQ:AMZN, NASDAQ:META; append a snapshot to
  `data/capex_snapshots.json` (never edit earlier snapshots).
- Owner's TradingView layout in Chrome (load the chrome-browser skill first): new tab, note the starting timeframe, read 1W/1D/4H, every
  oscillator, drawn levels; restore the timeframe; **never save the layout, never click Buy/Sell/Trade**; close the tab.
- Web: SEC filings (8-K, 10-Q, Form 4), AAII, CNN Fear & Greed, governance/export news. Fetch pages; a snippet is not a reading.
- If a page fails after one retry: `failed` with the reason. Options positioning stays `failed: deferred by owner`.
**Material event rule:** if anything material happens during the run (a gap, a filing, CEO news), set `event_cutoff_utc` in
inputs/readings.json to its time and re-read every price-sensitive page; the fact sheet marks earlier reads STALE.
```
python -m nvdaintel.factsheet          # prints coverage, e.g. "14/14 pages ok (...)"; lists every stale/missing page
python -m nvdaintel.committee slices
```
Do not dispatch members while a required page is missing or stale, unless it truly cannot be read (then `failed` with reason).

## 2. Specialists (parallel)
Run id `YYYY-MM-DD-review` (or `-postprint` etc.). Dispatch `nvda-technical`, `nvda-macro`, `nvda-fundamentals`,
`nvda-relative-strength`, `nvda-sentiment`, `nvda-narrative` at once, each with the run id. Each must pass
`python -m nvdaintel.committee check`. If the facts change mid-run, move first versions to `committee/runs/<run_id>/v1_<reason>/`, rebuild,
and ask every member to revise; only top-level files count.

## 3. Red team
`nvda-red-team` with the run id (reads all submissions + full fact sheet).

## 4. Independent chair
Dispatch `nvda-chair` (fresh agent) with the run id. It writes `chair.json` (decision, TB rulings, triggers with reachability verdicts,
Expected list, rulings, expected path with checkpoint status, ladder proposals, coverage note) and must pass `check`.
Do not edit chair.json. If it fails a gate, send it back to the chair with the gate's message.

## 4b. Shadow checks (owner-approved 24 Nov 2026) — only AFTER chair.json is final
```
python -m nvdaintel.shadow drawdown              # drawdown clock (context, low confidence)
python -m nvdaintel.shadow history <run_id>      # history check: history's odds for the chair's calls + ladder touch odds
```
No member, red team or chair reads `outputs/shadow/` before its own file is final. Shadow checks never move probabilities,
thesis-break rulings or the ladder. Gaps over 10 points are questions for the next run, not corrections.

## 5. Charts
```
python -m nvdaintel.pathchart <run_id>        # actual path + branches; probabilities from chair.json
```

## 6. Memo — `outputs/reviews/<run_id>.md`, from chair.json + fact sheet only
Order: **Final committee decision** box (strategic, tactical, thesis break, what it means for you, **Expected** line with effects,
**What would change it** = chair.triggers with their reachability %) → Bottom line + what changed (+ the coverage line verbatim) →
Macro (Purple List + dated catalysts) → Technicals (1W/1D/4H) → Fundamentals & earnings setup → Relative strength → Sentiment →
Narrative & governance (incl. TB4 capex monitor) → Kahneman (System 1 / System 2) → Outlook (probabilities + base rates) →
Expected path (chart + checkpoint table with status) → **Ladder Audit** (full history from `ladder_audit.history`, then resting orders,
distances from the fact sheet) → Strategy → Thesis-break update → Committee table (every member, red team, chair rulings) →
**Performance review** → **Shadow checks** (drawdown clock line; history check table with flags; the ladder-trigger
line from `ladder_triggers.memo_line` and, if fired, the review) → Dashboard → Sources (every page in config/pages.json with ✓ / stale / ✗ and read time).

## 7. Verifier gate
```
python -m nvdaintel.verify outputs/reviews/<run_id>.md <run_id>
```
Must print PASS (numbers from current sources only; ladder distances; chair row; coverage line; every stale/failed page named in
Sources; every trigger reachable). Fix and re-run; never deliver a failing memo.

## 8. Log and copy
```
python -m nvdaintel.committee log <run_id>
```
Copy to market-data (owner approved 15 Nov 2026; copy only): clone `enquire2022-droid/market-data` as a sibling folder, then
`cd ../market-data && PYTHONPATH=src python -m mdata.forecasts import nvidia_committee ../nvidia-committee/committee/log.jsonl --asset nvda`,
commit, `git pull --rebase`, push; report any WARNING lines. Never block the run on it.

## 9. Publish and tell
Publish the memo as a Doc (embed the chart); commit and push this repo. Tell the owner the decision, the committee split, the coverage
line, any proposals awaiting approval, and the Expected line.
