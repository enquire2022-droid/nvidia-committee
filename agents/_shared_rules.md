# Rules every NVIDIA Committee member follows

Adapted from the BTC committee (btc-intelligence). Owner: Ayham. Approved 2026-11-12.

1. **Numbers come only from your slice** (`outputs/slices/<you>.json`). Never introduce a number from memory or the web. If you need one that is missing, write "not in slice".
2. **Cite everything.** Each evidence item has `ref` (a fact-sheet path such as `structure.dist_to_sma100w_pct` or a page id such as `tv_fundamentals`) and `point`.
3. **A page marked failed/partial is unknown, not neutral.** Say what its absence does to your confidence (options positioning is not available this run).
4. **Fixed probability buckets** relative to `snapshot.nvda_price` (= price_at_call; the orchestrator states the exact thresholds and dates in each run's brief):
   - `next_2_weeks`: up > +5%, down < -5%, range in between; measured at the last close on or before as_of + 14 days (weekends and holidays roll back to the prior session).
   - `this_quarter`: to the last close of the current calendar quarter; `next_quarter`: to the last close of the following quarter. Up > +10%, down < -10%.
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
  "agent": "<name>", "run_id": "<given>", "as_of": "<YYYY-MM-DD>", "price_at_call": <price>,
  "view": "one or two sentences",
  "probabilities": {
    "defs": "2w ±5%, quarters ±10%, vs price_at_call <price>; thresholds and dates as given in the brief",
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
Accumulate / Hold / Wait / Reduce / Avoid New Entry: strategic (18-36 months) and tactical (1-12 weeks). Reduce is not available while price is below the owner's blended cost unless a thesis break fires (owner holds 30 shares at $171 since 2026-11-22; see config/ladder.json holdings).

## Thesis breaks (approved): any FIRED one pauses all buying
TB1 export violations confirmed; TB2 CEO departs under legal pressure; TB3 new export restrictions enacted that materially cut the addressable market;
TB4 hyperscaler capex cuts; TB5 financial-reporting integrity failure (adopted 2026-11-24). Current status, re-fire and clear tests: `config/thesis_breaks.json`.

## Tier 1 rules (owner-approved 15 Nov 2026, adapted from BTC committee2)

**Coverage and stale data.** Read `coverage` in your slice first. A page marked `stale`, `missing` or `failed` is unknown, not
current: never quote its numbers as today's, say so, and lower your confidence. After a material event the orchestrator sets
`event_cutoff_utc`; anything read before it is stale until re-read.

**Rule L — reachable triggers, Expected line, full ladder.**
1. Every item you put under `what_would_change_my_mind` must be reachable in its window, judged by NVDA's own history
   (`reachability` in the fact sheet; the chair checks each price trigger with `python -m nvdaintel.engines reach`).
   Under 5% of past windows = unreachable (drop it); over 95% = near-certain (it belongs on an "Expected" line with its effect, not a trigger).
2. A scheduled event that will happen (an earnings date, a weekly close) is Expected; what matters is its outcome, so phrase the
   trigger as the outcome (e.g. "guide below X"), not the event.
3. The Ladder Audit shows every order from the plan — pre-ladder fills, dropped, filled (planned zone and weight next to actual
   price, shares, USD and date) and resting — from `ladder_audit.history`. Rows are never removed once filled or dropped.

**TB4 monitor.** `hyperscaler_capex` gives MSFT / GOOGL / AMZN / META capex (last quarter, TTM, last FY, run-rate vs TTM).
Two or more with run-rate more than 10% below TTM = TB4 WATCH (narrative member checks guidance). TB4 fires only on capex
guidance cuts by two or more of the four.

**Independent chair.** The chair is a fresh agent (`nvda-chair`). Members write for the chair, not for the orchestrator.

## Lessons adopted 2026-11-24 (owner-approved, after the Huang reinstatement)
1. **Reversal probability.** Every reversible governance or thesis-break state (a CEO exit, a rule, a probe) gets an explicit
   probability of reversal in every run, with the dated signals for and against listed. Never leave it at zero by default.
2. **Weigh political signals by leverage.** A President, Treasury or Commerce head speaking about a company that depends on their
   licences or approvals is signal for governance and licence outcomes. Petitions, celebrities and individual legislators stay near noise.
   Official documents remain the only bar for firing or clearing a thesis break.
3. **Intent is not a decision.** "Does not intend to" is a statement of intent. Never call a governance state permanent without a
   structural lock (a signed successor, a charge, a court order, a filing).
4. **Trap clock first.** Do not call a level break CONFIRMED before its 1-3 close trap clock has run.
5. **Count shared evidence once (chair).** The chair tabulates which evidence items each member used and nets shared items once
   before ruling.

## Added 24 Nov 2026 (owner-approved, adapted from BTC committee2)
**Ladder change triggers.** A ladder level changes only when what it is tied to changes, never because the expected path
failed (a broken path redraws the path, not the ladder). A review opens only when `ladder_triggers.fired` lists one:
A anchor drift above 2% on two consecutive completed weeks, same direction (dynamic anchors: 200W SMA, D1's 200W-minus-ATR);
B weekly close below the established drawdown low (a low 4+ weeks old; newer lows are bottoming);
C regime change (two consecutive weekly closes back above the 100W SMA within the last 8 weeks);
D shock (a daily move above 4 standard deviations in the last 5 sessions) or a thesis-break status change within 7 days.
The chair proposes; the owner approves. With no trigger, the memo says "Ladder: no change trigger - hold".

**Signals must be tested.** `research/tier2_signals.json` holds the walk-forward verdict for each tested signal
(train to 2020, test 2021+, independent episodes, Benjamini-Hochberg). Only an EDGE verdict may move probabilities.
At the first test (24 Nov 2026) no signal had an edge: weekly RSI <= 36 and < 30, the WaveTrend green dot (oversold and
any), a 2-week drop of 15% or more, a first 30% drawdown, a first weekly close below the 200W SMA. Say "no tested edge"
when you cite one; it may describe the setup, not shift the numbers. Untested signals: same rule until tested.
The volatility-scaled starting point (normal on log returns, 52-week vol, half drift) did NOT beat the base rates in the
2021+ test (2 weeks: Brier 0.625 vs 0.621); the base rates stay the starting point.

## Cycle placement (owner-approved 24 Nov 2026, adapted from BTC committee2 rule L; first used in the run after 2026-11-24)
Stages (market-psychology cycle for a stock): Euphoria, Complacency, Anxiety, Denial, Panic, Capitulation, Depression,
Relief rally, Hope, Optimism, Belief, Thrill.
1. **Owner of the label.** The sentiment member proposes `cycle_placement_proposal` {stage, why, refs}; the chair rules and saves
   `cycle_placement` {stage, since, basis, agrees_with_probabilities}. The memo has a "Cycle placement" line and the chart.
2. **Moves only on structure, never on a probability alone.** A weekly close below the established drawdown low
   (`ladder_triggers.details.B_structure_break`) = "Depression: new low". Two weekly closes back above the 100W SMA = "Hope confirmed"
   (trigger C). Between those lines the label may move one step only with a stated reason (e.g. Capitulation -> Relief rally after
   a reversal week); it never jumps to Hope/Optimism on one day's move.
3. **Label must agree with the probabilities next to it** (owner's lesson, Jul 2026): a bottom-is-in label (Hope or later) cannot sit
   next to this-quarter down >= 30 or a 2-week down above up. The red team checks this every run and names any contradiction.

## Equity Bottom / Top checklists
**Draft, not approved, not back-tested.** Report them as information only until the owner approves them after a back-test on NVDA's 2018, 2022 and 2025 drawdowns.
