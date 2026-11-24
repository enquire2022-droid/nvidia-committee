"""Shadow checks (owner-approved 24 Nov 2026). Code only. Computed AFTER the chair is final and shown only in the memo's
"Shadow checks" section; no member, red team or chair reads these files before its own submission is final.
They never move bucket probabilities, thesis-break rulings or the ladder.

  python -m nvdaintel.shadow drawdown            -> outputs/shadow/drawdown_clock.json
  python -m nvdaintel.shadow history <run_id>    -> outputs/shadow/<run_id>_history_check.json

Drawdown clock: past NVDA drawdowns of 30% or more from an all-time-high weekly close (since 1999), with depth on weekly
closes and on lows, weeks from top to low and from low to a new high, against the current one. LOW CONFIDENCE: few episodes.
History check: NVDA's own history, in volatility units (move / (trailing 52-week weekly vol x sqrt(weeks))), gives the odds of
the chair's bucket lines and of each ladder level being touched within 1 and 4 weeks. Gaps of more than 10 points to the
chair are flagged as questions for the next run, not corrections.
"""
import json, math, sys, pathlib
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs/shadow"


def _weekly():
    d = json.loads((ROOT / "data/nvda_weekly_full.json").read_text())
    df = pd.DataFrame({k: d[k] for k in "ohlcv"}, index=pd.to_datetime(d["t"], unit="s").normalize())
    return df


def drawdown_clock(min_dd=0.30):
    df = _weekly(); c = df.c; low = df.l
    ath = c.cummax(); dd = c / ath - 1
    eps = []; i = 0; n = len(c)
    while i < n:
        if dd.iloc[i] <= -min_dd:
            pk_i = int(np.where(c.iloc[:i + 1].values == ath.iloc[i])[0][-1])
            j = i
            while j < n and c.iloc[j] < ath.iloc[i]:
                j += 1
            seg = slice(pk_i, j)
            tr_i = pk_i + int(np.argmin(c.iloc[seg].values)); lw_i = pk_i + int(np.argmin(low.iloc[seg].values))
            e = {"peak_week": str(c.index[pk_i].date()), "peak_close": round(float(c.iloc[pk_i]), 4),
                 "trough_week_close": str(c.index[tr_i].date()), "depth_close_pct": round(float(c.iloc[tr_i] / c.iloc[pk_i] - 1) * 100, 1),
                 "depth_low_pct": round(float(low.iloc[lw_i] / c.iloc[pk_i] - 1) * 100, 1),
                 "weeks_top_to_low": tr_i - pk_i,
                 "recovered_week": str(c.index[j].date()) if j < n else None,
                 "weeks_low_to_new_high": (j - tr_i) if j < n else None, "ongoing": j >= n}
            eps.append(e); i = j + 1
        else:
            i += 1
    done = [e for e in eps if not e["ongoing"]]
    cur = next((e for e in eps if e["ongoing"]), None)
    stats = {}
    if done:
        for k in ("depth_close_pct", "depth_low_pct", "weeks_top_to_low", "weeks_low_to_new_high"):
            v = np.array([e[k] for e in done], dtype=float)
            stats[k] = {"min": float(v.min()), "median": float(np.median(v)), "max": float(v.max())}
    weeks_since_peak = None
    if cur:
        weeks_since_peak = len(c) - 1 - c.index.get_loc(pd.Timestamp(cur["peak_week"]))
    res = {"label": "SHADOW, context only, LOW CONFIDENCE (few episodes; NVDA's business changed a lot since 1999)",
           "sample": f"NVDA weekly closes {c.index[0].date()} to {c.index[-1].date()} (last bar may be forming)",
           "threshold": f"drawdown of {int(min_dd * 100)}% or more from an all-time-high weekly close",
           "completed_episodes": done, "current": cur, "weeks_since_peak": weeks_since_peak,
           "completed_stats": stats, "n_completed": len(done)}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "drawdown_clock.json").write_text(json.dumps(res, indent=1))
    return res


def _wilson(p, n, z=1.645):
    if n <= 0:
        return [None, None]
    den = 1 + z * z / n; ctr = (p + z * z / (2 * n)) / den; hw = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return [round(100 * max(0, ctr - hw), 1), round(100 * min(1, ctr + hw), 1)]


def history_check(run_id):
    ch = json.loads((ROOT / f"committee/runs/{run_id}/chair.json").read_text())
    lad = json.loads((ROOT / "config/ladder.json").read_text())
    df = _weekly()
    asof = pd.Timestamp(ch["as_of"])
    df = df[df.index < asof - pd.Timedelta(days=0)]
    comp = df.iloc[:-1] if (asof - df.index[-1]).days < 7 else df          # completed weeks for the vol estimate
    lr = np.log(comp.c).diff(); vol = lr.rolling(52).std()
    v_now = float(vol.iloc[-1]); p0 = float(ch["price_at_call"])
    c, l, h = comp.c, comp.l, comp.h
    out = {"label": "SHADOW: history's odds for the chair's own calls (volatility units); never moves the numbers",
           "price_at_call": p0, "weekly_vol_52w_pct": round(100 * v_now, 2), "calls": [], "ladder_touch_odds": [], "flags": []}

    def close_odds(hw, up, dn):
        z = np.log(c.shift(-hw) / c) / (vol * math.sqrt(hw)); z = z.dropna()
        zu = math.log(up / p0) / (v_now * math.sqrt(hw)); zd = math.log(dn / p0) / (v_now * math.sqrt(hw))
        pu = float((z > zu).mean()); pdn = float((z < zd).mean()); n_eff = len(z) / hw
        return pu, pdn, n_eff

    P = ch["probabilities"]
    windows = [("next_2_weeks", 2, p0 * 1.05, p0 * 0.95)]
    for key, end in (("this_quarter", pd.Timestamp(f"{asof.year}-12-31") if asof.month > 9 else (asof + pd.offsets.QuarterEnd(0))),
                     ("next_quarter", (asof + pd.offsets.QuarterEnd(0) + pd.offsets.QuarterEnd(1)))):
        windows.append((key, max(1, round((end - asof).days / 7)), p0 * 1.10, p0 * 0.90))
    for key, hw, up, dn in windows:
        pu, pdn, n_eff = close_odds(hw, up, dn)
        hist = {"up": round(100 * pu, 1), "range": round(100 * (1 - pu - pdn), 1), "down": round(100 * pdn, 1)}
        chair = P[key]
        row = {"window": key, "weeks": hw, "history": hist, "history_band90": {"up": _wilson(pu, n_eff), "down": _wilson(pdn, n_eff)},
               "chair": {k: chair[k] for k in ("up", "range", "down")}, "n_eff": round(n_eff)}
        out["calls"].append(row)
        for k in ("up", "down"):
            if abs(hist[k] - chair[k]) > 10:
                out["flags"].append(f"{key} {k}: chair {chair[k]} vs history {hist[k]} (gap > 10): question for the next run")
    for o in lad["orders"]:
        lvl = o["zone_high"] if o.get("type", "dip") == "dip" else o["zone_low"]
        below = lvl < p0
        row = {"order": o["id"], "type": o.get("type", "dip"), "level": lvl}
        for hw in (1, 4):
            if below:
                ext = l[::-1].rolling(hw, min_periods=hw).min()[::-1].shift(-1)
            else:
                ext = h[::-1].rolling(hw, min_periods=hw).max()[::-1].shift(-1)
            z = (np.log(ext / c) / (vol * math.sqrt(hw))).dropna()
            zl = math.log(lvl / p0) / (v_now * math.sqrt(hw))
            p = float((z <= zl).mean()) if below else float((z >= zl).mean())
            row[f"touch_{hw}w_pct"] = round(100 * p, 1); row[f"touch_{hw}w_band90"] = _wilson(p, len(z) / hw)
        out["ladder_touch_odds"].append(row)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{run_id}_history_check.json").write_text(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    cmd = sys.argv[1]
    r = drawdown_clock() if cmd == "drawdown" else history_check(sys.argv[2])
    print(json.dumps(r, indent=1)[:4000])
