# Playbook card — Tetlock & Gardner, *Superforecasting* (notes in our own words)

Used by: **chair** (primary), **red team**, every specialist when setting probabilities.

**Core idea.** Good forecasters are not prophets; they break questions into parts, start from base rates, update in small steps as evidence arrives, and keep score. Being scored is what makes them improve.

## Rules to apply each review
1. **Outside view first.** Start from the base rate (how often BTC moved ±5% in two weeks / ±10% in a quarter from comparable points — the engines provide base rates and analog spreads). Then adjust for this case's specifics.
2. **Fermi-ize.** Split a big question ("is the bottom in?") into checkable parts (capitulation evidence? cost-basis support? clock timing? liquidity below?) and estimate each.
3. **Granular probabilities.** 55 vs 60 matters over many reviews. Avoid lazy 50s and lazy 80s.
4. **Update incrementally.** Change last review's probabilities by an amount proportional to the new evidence; explain each change. Big swings need big evidence.
5. **Dragonfly eye.** Combine views from different angles (the five specialists) — but weigh them by evidence and track record, never by simple averaging.
6. **Keep score.** Every probability is logged (`committee/log.jsonl`) and later scored (Brier score). Over time the chair gives more weight to members who have been better calibrated.
7. **Postmortems both ways.** Review misses *and* hits: a correct call for the wrong reason is a lesson too. Add the lesson to `lessons-log.md`.
8. **Question clarity.** A forecast must be scorable: defined outcome, defined date. That is why the committee uses fixed buckets.
