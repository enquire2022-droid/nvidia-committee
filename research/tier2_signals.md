# Tier 2 research: do the cited signals have an edge on NVDA? (24 Nov 2026)

Data: NVDA weekly closes 1999-01-18 to 2026-11-16 (completed bars, TradingView, split-adjusted). Script: `research/tier2_signals.py`;
full numbers in `research/tier2_signals.json`.
Method: the committee's own buckets (2 weeks ±5%, 13 weeks ±10%); independent episodes (no overlap); train to 2020-12-31,
test 2021+; exact binomial tests vs the unconditional rate of the same period; Benjamini-Hochberg (q 0.10) on train.

## Verdict: no signal has an edge
| Signal | Best-looking result | Why it does not count |
|---|---|---|
| Weekly RSI14 ≤ 36 (first week) | 13w down 45% vs 22% (train, n=11) | Points DOWN, not up; BH fail; test n=3 goes the other way |
| Weekly RSI14 < 30 (first week) | 2w up 53% vs 33% (train, n=15, p=0.11) | BH fail; no cases at all in 2021+ |
| WaveTrend green dot, oversold | 13w up 6 of 6 (train, p=0.013) | n=6, BH fail, no cases in 2021+ |
| WaveTrend green dot, any | 2w up 48% vs 35% (test, n=25) | Train shows nothing (34% vs 33%, n=80) |
| 2-week drop ≤ −15% | 13w down 38% vs 22% (train) | Two-sided: raises up AND down; BH fail |
| First 30% drawdown | 2w up 57% vs 33% (train, n=14, p=0.08) | BH fail; test n=6 |
| First weekly close below 200W SMA | 2w up 13% vs 33% (train, n=15) | BH fail; test n=1 |

## Volatility-scaled starting point
| Horizon | 2000–2026 (Brier, vol vs base) | 2021+ test |
|---|---|---|
| 2 weeks ±5% | 0.615 vs 0.641 (better; CI −0.037 to −0.016) | 0.625 vs 0.621 (no gain; CI −0.010 to +0.018) |
| 13 weeks ±10% | 0.624 vs 0.649 (CI crosses zero) | 0.611 vs 0.613 (no gain) |
Not adopted: it did not win in the out-of-sample years. Today it would read 2w 26/44/30 and 13w 26/35/39 (52-week weekly vol 6.0%, negative trailing drift).
