# nvidia-committee

Private NVDA analysis committee, adapted from `btc-intelligence` (first engine of "one engine per stock category"; approved 2026-11-12).

| Layer | What | Where |
|---|---|---|
| 1. Data | TradingView MCP pulls, owner's chart, Purple list, news, sentiment | `inputs/readings.json`, `data/` |
| 2. Engines | Base rates, weekly RSI, structure, fib check, relative strength / beta, Ladder Audit | `src/nvdaintel/factsheet.py` -> `outputs/fact_sheet.json` |
| 3. Committee | Technical, Macro, Fundamentals & catalysts, Relative strength, Sentiment, Narrative & governance + Red team | `.claude/agents/`, `agents/_shared_rules.md`, `playbooks/` |
| 4. Chair + verifier | Memo; every number checked against the fact sheet | `.claude/skills/nvidia-committee/`, `src/nvdaintel/verify.py` |

Tier 1 (owner-approved 15 Nov 2026, from BTC committee2): scoring + performance review (`nvdaintel.scoring`,
`nvda-performance-review`), forecasts copied to market-data (`forecasts/stocks/nvda_forecasts.jsonl`), independent chair (`nvda-chair`),
fixed page list with coverage and stale flags (`config/pages.json`, `event_cutoff_utc`), strict verifier (labelled checks, no free-text
sources), rule L (reachable triggers via `nvdaintel.engines reach`, Expected line, full ladder history), TB4 hyperscaler-capex monitor.
Tests: `PYTHONPATH=src python -m pytest -q tests`.

Golden rule: **agents never introduce numbers**; everything comes from the fact sheet.

Run command: **"Run NVIDIA committee"**.

```bash
PYTHONPATH=src python -m nvdaintel.scoring
PYTHONPATH=src python -m nvdaintel.committee readings-template
PYTHONPATH=src python -m nvdaintel.factsheet
PYTHONPATH=src python -m nvdaintel.committee slices
PYTHONPATH=src python -m nvdaintel.verify outputs/reviews/<run_id>.md <run_id>
PYTHONPATH=src python -m nvdaintel.committee log <run_id>
```

Deferred: paid options data (gamma / flow / put-call), market-maker agent, equity Bottom/Top checklists (draft until back-tested on 2018 / 2022 / 2025).
Config: `config/ladder.json` (proposed, unapproved, no budget), `config/thesis_breaks.json` (approved).
