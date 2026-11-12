# Rules every NVIDIA Committee member follows

Adapted from the BTC committee (btc-intelligence). Owner: Ayham. Approved 2026-11-12.

1. **Numbers come only from your slice** (`outputs/slices/<you>.json`). Never introduce a number from memory or the web. If you need one that is missing, write "not in slice".
2. **Cite everything.** Each evidence item has `ref` (a fact-sheet path such as `structure.dist_to_sma100w_pct` or a page id such as `tv_fundamentals`) and `point`.
3. **A page marked failed/partial is unknown, not neutral.** Say what its absence does to your confidence (options positioning is not available this run).
4. **Fixed probability buckets** relative to `snapshot.nvda_price` (price_at_call = 164.33, 2026-11-12 intraday, revision 2):
   - `next_2_weeks`: up > +5% (close > 172.55), down < -5% (close < 156.11), range in between; measured at the 2026-11-25 close (2026-11-26 is Thanksgiving, market closed).
   - `this_quarter`: to the last close of Q4 2026 (2026-12-31); `next_quarter`: to the last close of Q1 2027 (2027-03-31). Up > +10% (> 180.76), down < -10% (< 147.90).
   - up + range + down = 100. Copy these definitions into `probabilities.defs`.
5. **Outside view first.** Start from `base_rates` (NVDA weekly since Nov 2021), then adjust. Say how far you moved from the base rate and why. Conditional base rates are small, overlapping samples: treat them as weak evidence.
6. **Calibrate.** 50/50 is honest when evidence conflicts. Confidence (0-100) = how much your evidence should move the chair.
7. **Name what would change your mind**: observable, with a level or date.
8. **Stay in your lane**; flag cross-domain issues in `notes_for_chair`.
9. **Earnings is a binary event** (2026-11-17 after close). Say explicitly how your view differs before vs after the print.
10. **Read the playbooks** (`playbooks/kahneman.md`, `playbooks/superforecasting.md`, `playbooks/lessons-log.md`).

## Submission format (JSON only)
```json
{
  "agent": "<name>", "run_id": "<given>", "as_of": "2026-11-12", "price_at_call": 164.33,
  "view": "one or two sentences",
  "probabilities": {
    "defs": "2w ±5%, quarters ±10%, vs price_at_call 164.33",
    "next_2_weeks": {"up": 0, "range": 0, "down": 0},
    "this_quarter": {"up": 0, "range": 0, "down": 0},
    "next_quarter": {"up": 0, "range": 0, "down": 0}
  },
  "confidence": 0,
  "evidence": [{"ref": "path-or-page-id", "point": "..."}],
  "key_levels": [{"level": 0, "why": "...", "ref": "..."}],
  "what_would_change_my_mind": ["..."],
  "notes_for_chair": ["..."]
}
```
Validate: `PYTHONPATH=src python -m nvdaintel.committee check <file>` must print OK.

## Overlapping evidence (count once)
Price momentum (RSI, MACD, MAs, Stochastic, oscillators) = one group. Analyst targets and ratings = one group. Governance / export-control news = one group, however many headlines.

## Stance words
Accumulate / Hold / Wait / Reduce / Avoid New Entry: strategic (18-36 months) and tactical (1-12 weeks). Reduce is not available while price is below the owner's blended cost unless a thesis break fires (owner holds no recorded position yet).

## Thesis breaks (approved): any one pauses all buying
TB1 export violations confirmed; TB2 CEO departs under legal pressure; TB3 new export restrictions enacted; TB4 hyperscaler capex cuts.

## Equity Bottom / Top checklists
**Draft, not approved, not back-tested.** Report them as information only until the owner approves them after a back-test on NVDA's 2018, 2022 and 2025 drawdowns.
