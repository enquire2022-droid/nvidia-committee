"""Tier 2 research (owner-approved 15 Nov and 24 Nov 2026): do the signals the committee cites have an edge on NVDA?
Also: does a volatility-scaled starting point beat the fixed base rates?  Weekly bars, NVDA since 1999.

Method (adapted from BTC committee2 rule Q / research test4):
- completed weekly bars only; outcomes are the committee's own buckets: 2 weeks +-5%, 13 weeks +-10% (close vs close);
- independent episodes: after a signal fires, the next one counts only after the horizon has passed (no overlap);
- train = signals up to 2020-12-31, test = 2021 onward (walk-forward check, nothing tuned on the test years);
- each signal's up-rate and down-rate are compared with the unconditional rates over the same period (two-sided exact
  binomial test), and the train p-values are corrected across all signals x horizons x sides with Benjamini-Hochberg (q 0.10);
- verdict: EDGE = BH-significant in train and same direction with p < 0.10 in test; WEAK = same direction in both,
  not significant; NONE otherwise.
Volatility anchor: up/range/down from a normal on log returns (trailing 52-week vol, half the trailing drift) vs the
expanding-window base rate; 3-class Brier on non-overlapping windows, block-bootstrap CI of the difference.
Run: python research/tier2_signals.py   -> research/tier2_signals.json and .md
"""
import json, math, pathlib
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[1]
rng = np.random.default_rng(7)


def load():
    d = json.loads((ROOT / "data/nvda_weekly_full.json").read_text())
    df = pd.DataFrame({k: d[k] for k in "ohlcv"}, index=pd.to_datetime(d["t"], unit="s").normalize())
    return df.iloc[:-1]                                   # drop the forming week


def rsi(c, n=14):
    d = c.diff(); up = d.clip(lower=0); dn = -d.clip(upper=0)
    au = up.ewm(alpha=1 / n, adjust=False).mean(); ad = dn.ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + au / ad)


def wavetrend(df, n1=10, n2=21):
    ap = (df.h + df.l + df.c) / 3
    esa = ap.ewm(span=n1, adjust=False).mean()
    d = (ap - esa).abs().ewm(span=n1, adjust=False).mean()
    ci = (ap - esa) / (0.015 * d)
    wt1 = ci.ewm(span=n2, adjust=False).mean(); wt2 = wt1.rolling(4).mean()
    return wt1, wt2


def binom_p(k, n, p):
    """two-sided exact binomial p-value"""
    if n == 0:
        return 1.0
    from math import comb
    pk = [comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(n + 1)]
    obs = pk[k]
    return float(min(1.0, sum(x for x in pk if x <= obs * (1 + 1e-9))))


def episodes(flag, h):
    idx = []; last = None
    for i, f in enumerate(flag.values):
        if f and (last is None or i - last >= h):
            idx.append(i); last = i
    return idx


def outcome(c, h, thr):
    fwd = c.shift(-h) / c - 1
    return pd.Series(np.where(fwd > thr, "up", np.where(fwd < -thr, "down", "range")), index=c.index).where(fwd.notna())


def main():
    df = load(); c = df.c
    r = rsi(c); wt1, wt2 = wavetrend(df)
    cross_up = (wt1 > wt2) & (wt1.shift() <= wt2.shift())
    signals = {
        "weekly_rsi14_le_36 (first week at or below)": (r <= 36) & (r.shift() > 36),
        "weekly_rsi14_lt_30 (first week below)": (r < 30) & (r.shift() >= 30),
        "wavetrend_green_dot_oversold (WT1 crosses up, WT2 <= -53)": cross_up & (wt2 <= -53),
        "wavetrend_green_dot_any (WT1 crosses up WT2)": cross_up,
        "two_week_drop_le_-15pct": (c / c.shift(2) - 1) <= -0.15,
        "drawdown_ge_30pct_from_ath (first week)": ((c / c.cummax() - 1) <= -0.30) & ((c.shift() / c.shift().cummax() - 1) > -0.30),
        "weekly_close_below_sma200w (first week)": (c < c.rolling(200).mean()) & (c.shift() >= c.rolling(200).mean().shift()),
    }
    horizons = {"2w_5pct": (2, 0.05), "13w_10pct": (13, 0.10)}
    split = pd.Timestamp("2020-12-31")
    rows = []
    for hname, (h, thr) in horizons.items():
        out = outcome(c, h, thr)
        for per, mask in (("train", out.index <= split), ("test", out.index > split)):
            o = out[mask].dropna()
            base = {k: float((o == k).mean()) for k in ("up", "range", "down")}
            for sname, flag in signals.items():
                f = flag.reindex(o.index).fillna(False)
                ep = episodes(f, h)
                oo = o.iloc[ep]
                n = len(oo)
                row = {"signal": sname, "horizon": hname, "period": per, "n_episodes": n,
                       "base": {k: round(100 * v, 1) for k, v in base.items()}}
                for side in ("up", "down"):
                    k = int((oo == side).sum())
                    row[side] = round(100 * k / n, 1) if n else None
                    row[f"{side}_edge_pts"] = round(100 * (k / n - base[side]), 1) if n else None
                    row[f"{side}_p"] = binom_p(k, n, base[side]) if n else 1.0
                row["dates"] = [str(d.date()) for d in oo.index[-6:]]
                rows.append(row)
    # Benjamini-Hochberg on train p-values (signals x horizons x sides)
    tr = [(i, s) for i, r_ in enumerate(rows) if r_["period"] == "train" for s in ("up", "down")]
    ps = sorted([(rows[i][f"{s}_p"], i, s) for i, s in tr])
    m = len(ps); bh = {}
    kmax = 0
    for rank, (p, i, s) in enumerate(ps, 1):
        if p <= 0.10 * rank / m:
            kmax = rank
    for rank, (p, i, s) in enumerate(ps, 1):
        bh[(i, s)] = rank <= kmax
    verdicts = []
    for sname in signals:
        for hname in horizons:
            trr = next(x for x in rows if x["signal"] == sname and x["horizon"] == hname and x["period"] == "train")
            ter = next(x for x in rows if x["signal"] == sname and x["horizon"] == hname and x["period"] == "test")
            ti = rows.index(trr)
            for side in ("up", "down"):
                e1, e2 = trr[f"{side}_edge_pts"], ter[f"{side}_edge_pts"]
                same = e1 is not None and e2 is not None and np.sign(e1) == np.sign(e2) and e1 != 0
                if bh.get((ti, side)) and same and ter[f"{side}_p"] < 0.10:
                    v = "EDGE"
                elif same:
                    v = "WEAK"
                else:
                    v = "NONE"
                verdicts.append({"signal": sname, "horizon": hname, "side": side, "verdict": v,
                                 "train": f"n={trr['n_episodes']} {side} {trr[side]}% vs base {trr['base'][side]}% (edge {e1}, p={trr[side + '_p']:.3f}, BH {'pass' if bh.get((ti, side)) else 'fail'})",
                                 "test": f"n={ter['n_episodes']} {side} {ter[side]}% vs base {ter['base'][side]}% (edge {e2}, p={ter[side + '_p']:.3f})"})

    # volatility-scaled anchor vs expanding base rate
    lr = np.log(c).diff()
    vol = lr.rolling(52).std(); drift = lr.rolling(52).mean()
    from math import erf, sqrt
    Phi = lambda x: 0.5 * (1 + erf(x / sqrt(2)))
    anchor_res = {}
    for hname, (h, thr) in horizons.items():
        out = outcome(c, h, thr)
        idx = [i for i in range(60, len(c) - h, h)]          # non-overlapping windows
        recs = []
        for i in idx:
            t = c.index[i]
            past = out.iloc[:i - h + 1].dropna()             # only outcomes already known at t
            if len(past) < 52 or pd.isna(vol.iloc[i]):
                continue
            pb = np.array([(past == k).mean() for k in ("up", "range", "down")])
            s = vol.iloc[i] * math.sqrt(h); mu = 0.5 * drift.iloc[i] * h
            pu = 1 - Phi((math.log(1 + thr) - mu) / s); pd_ = Phi((math.log(1 - thr) - mu) / s)
            pv = np.array([pu, 1 - pu - pd_, pd_])
            y = np.array([out.iloc[i] == k for k in ("up", "range", "down")], dtype=float)
            recs.append({"t": t, "base": float(((pb - y) ** 2).sum()), "vol": float(((pv - y) ** 2).sum())})
        R = pd.DataFrame(recs).set_index("t")
        res = {}
        for per, sub in (("all_2000+", R), ("test_2021+", R[R.index > split])):
            dlt = (sub.vol - sub.base).values
            boots = [dlt[rng.integers(0, len(dlt), len(dlt))].mean() for _ in range(4000)]
            res[per] = {"n_windows": len(sub), "brier_base": round(sub.base.mean(), 3), "brier_vol": round(sub.vol.mean(), 3),
                        "diff_vol_minus_base": round(float(dlt.mean()), 3),
                        "ci90": [round(float(np.percentile(boots, 5)), 3), round(float(np.percentile(boots, 95)), 3)]}
        anchor_res[hname] = res
    # today's anchors for reference
    i = len(c) - 1
    today = {}
    for hname, (h, thr) in horizons.items():
        s = vol.iloc[i] * math.sqrt(h); mu = 0.5 * drift.iloc[i] * h
        pu = 1 - Phi((math.log(1 + thr) - mu) / s); pd_ = Phi((math.log(1 - thr) - mu) / s)
        today[hname] = {"up": round(100 * pu), "range": round(100 * (1 - pu - pd_)), "down": round(100 * pd_),
                        "weekly_vol_52w_pct": round(100 * vol.iloc[i], 2), "as_of_completed_week": str(c.index[i].date())}
    res = {"sample": f"NVDA weekly closes {c.index[0].date()} to {c.index[-1].date()} (n={len(c)}), completed bars",
           "verdicts": verdicts, "rows": rows, "vol_anchor_vs_base_rate": anchor_res, "vol_anchor_today": today}
    (ROOT / "research/tier2_signals.json").write_text(json.dumps(res, indent=1))
    for v in verdicts:
        print(v["verdict"].ljust(5), v["signal"][:58].ljust(58), v["horizon"], v["side"].ljust(4), "|", v["train"], "|", v["test"])
    print(json.dumps(anchor_res, indent=1)); print(today)


if __name__ == "__main__":
    main()
