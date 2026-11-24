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


# ---- charts (owner request 24 Nov 2026) ----
def _plt():
    import matplotlib; matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    return plt


INK, MUTE, GRID, RED, BLUE, GREEN = "#1f2328", "#6e7781", "#e6e8eb", "#cf222e", "#0969da", "#1a7f37"


def chart_drawdown(out_png=None):
    """Drawdown clock: every 30%+ NVDA drawdown since 1999 as % below the peak vs weeks since the peak; current one in red."""
    plt = _plt(); r = json.loads((OUT / "drawdown_clock.json").read_text()); df = _weekly(); c = df.c
    fig, ax = plt.subplots(figsize=(13, 6.8), dpi=150)
    for e in r["completed_episodes"]:
        i0 = c.index.get_loc(pd.Timestamp(e["peak_week"]))
        i1 = c.index.get_loc(pd.Timestamp(e["recovered_week"])) if e["recovered_week"] else len(c) - 1
        i1 = min(i1, i0 + 80)
        seg = c.iloc[i0:i1 + 1] / c.iloc[i0] * 100 - 100
        ax.plot(range(len(seg)), seg.values, color=MUTE, lw=1.1, alpha=0.75)
        k = int(np.argmin(seg.values))
        ax.annotate(f"{e['peak_week'][:4]} ({e['depth_close_pct']:.0f}%, {e['weeks_top_to_low']}w)", (k, seg.values[k]),
                    xytext=(4, -4), textcoords="offset points", fontsize=7.5, color=MUTE)
    cur = r["current"]
    if cur:
        i0 = c.index.get_loc(pd.Timestamp(cur["peak_week"]))
        seg = c.iloc[i0:] / c.iloc[i0] * 100 - 100
        ax.plot(range(len(seg)), seg.values, color=RED, lw=2.6)
        ax.annotate(f"now: {seg.values[-1]:.1f}% at week {len(seg) - 1}\n(low {cur['depth_close_pct']}% at week {cur['weeks_top_to_low']})",
                    (len(seg) - 1, seg.values[-1]), xytext=(10, 6), textcoords="offset points", fontsize=9, color=RED, fontweight="bold")
    st = r["completed_stats"]
    ax.axhline(st["depth_close_pct"]["median"], color=BLUE, ls="--", lw=1)
    ax.text(79, st["depth_close_pct"]["median"] + 1.2, f"median depth {st['depth_close_pct']['median']:.0f}%", ha="right", fontsize=8.5, color=BLUE)
    ax.axvline(st["weeks_top_to_low"]["median"], color=BLUE, ls=":", lw=1)
    ax.text(st["weeks_top_to_low"]["median"] + 0.6, 3, f"median top-to-low {st['weeks_top_to_low']['median']:.0f}w", fontsize=8.5, color=BLUE)
    ax.set_xlim(0, 80); ax.set_ylim(-95, 8)
    ax.set_xlabel("weeks since the all-time-high weekly close", color=INK); ax.set_ylabel("% below the peak (weekly closes)", color=INK)
    ax.grid(color=GRID, lw=0.6); ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.set_title(f"NVDA drawdown clock - {r['n_completed']} completed drawdowns of 30%+ since 1999 vs now", loc="left", fontsize=12.5, fontweight="bold", color=INK)
    fig.text(0.01, 0.005, "SHADOW check, context only, LOW CONFIDENCE (few episodes; the business changed). Episodes cut at 80 weeks "
             "(2002 and 2008 took 215 and 390 weeks from the low to a new high). Source: TradingView weekly closes.", fontsize=7.5, color=MUTE)
    out = out_png or OUT / "drawdown_clock.png"; fig.tight_layout(rect=(0, 0.03, 1, 1)); fig.savefig(out, facecolor="white"); return out


def chart_history(run_id, out_png=None):
    """History check: chair vs history (with 90% band) per window and bucket; ladder touch odds within 1 and 4 weeks."""
    plt = _plt(); h = json.loads((OUT / f"{run_id}_history_check.json").read_text())
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(14, 6.2), dpi=150, gridspec_kw={"width_ratios": [1.5, 1]})
    names = {"next_2_weeks": "2 weeks", "this_quarter": "this quarter", "next_quarter": "next quarter"}
    x = 0; ticks = []; labels = []
    for cw in h["calls"]:
        for k, col in (("up", GREEN), ("range", "#9a6700"), ("down", RED)):
            hv = cw["history"][k]; cv = cw["chair"][k]
            a1.bar(x - 0.18, hv, 0.36, color=col, alpha=0.35, edgecolor=col)
            a1.bar(x + 0.18, cv, 0.36, color=col, alpha=0.95)
            band = cw["history_band90"].get(k)
            if band and band[0] is not None:
                a1.plot([x - 0.18, x - 0.18], band, color=INK, lw=1.2)
            if abs(hv - cv) > 10:
                a1.annotate(f"gap {cv - hv:+.0f}", (x, max(hv, cv) + 2), ha="center", fontsize=8.5, color=RED, fontweight="bold")
            ticks.append(x); labels.append(f"{names[cw['window']]}\n{k}"); x += 1
        x += 0.6
    a1.set_xticks(ticks); a1.set_xticklabels(labels, fontsize=7.8)
    a1.set_ylabel("probability %"); a1.set_title("Chair (solid) vs NVDA history (light, 90% band)", loc="left", fontsize=10.5, color=INK)
    a1.grid(axis="y", color=GRID, lw=0.6); a1.set_axisbelow(True)
    rows = h["ladder_touch_odds"]
    y = np.arange(len(rows))
    a2.barh(y + 0.2, [r["touch_4w_pct"] for r in rows], 0.4, color=BLUE, label="within 4 weeks")
    a2.barh(y - 0.2, [r["touch_1w_pct"] for r in rows], 0.4, color="#8c959f", label="within 1 week")
    for i, r in enumerate(rows):
        a2.text(r["touch_4w_pct"] + 0.8, i + 0.2, f"{r['touch_4w_pct']}%", va="center", fontsize=8)
    a2.set_yticks(y); a2.set_yticklabels([f"{r['order']} {r['level']:g}" for r in rows], fontsize=8.5)
    a2.invert_yaxis(); a2.legend(fontsize=8, frameon=False, loc="upper right"); a2.set_xlim(0, max(r["touch_4w_pct"] for r in rows) * 1.25 + 2)
    a2.set_title("Ladder levels: odds of a touch (history)", loc="left", fontsize=10.5, color=INK)
    a2.grid(axis="x", color=GRID, lw=0.6); a2.set_axisbelow(True)
    for a in (a1, a2):
        for s in ("top", "right"):
            a.spines[s].set_visible(False)
    fig.suptitle(f"NVDA history check - run {run_id}, call {h['price_at_call']}, weekly vol {h['weekly_vol_52w_pct']}%", x=0.01, ha="left",
                 fontsize=12.5, fontweight="bold", color=INK)
    fig.text(0.01, 0.005, "SHADOW check: NVDA weekly history since 1999 in volatility units; never moves the numbers. Gaps over 10 points "
             "are questions for the next run. History contains no accounting or governance overhang.", fontsize=7.5, color=MUTE)
    out = out_png or OUT / f"{run_id}_history_check.png"; fig.tight_layout(rect=(0, 0.03, 1, 0.95)); fig.savefig(out, facecolor="white"); return out


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "drawdown":
        r = drawdown_clock(); print(chart_drawdown())
    else:
        r = history_check(sys.argv[2]); print(chart_history(sys.argv[2]))
    print(json.dumps(r, indent=1)[:1500])
