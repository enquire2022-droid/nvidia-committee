"""Engines -> outputs/fact_sheet.json. Every number agents may use comes from here.

python -m nvdaintel.factsheet
"""
import json, math, pathlib
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[2]


def load(p):
    return json.loads((ROOT / p).read_text())


def rsi(closes, n=14):
    c = np.asarray(closes, float)
    d = np.diff(c)
    up, dn = np.clip(d, 0, None), np.clip(-d, 0, None)
    au, ad = up[:n].mean(), dn[:n].mean()
    out = [None] * (n + 1)
    for i in range(n, len(d)):
        au = (au * (n - 1) + up[i]) / n
        ad = (ad * (n - 1) + dn[i]) / n
        out.append(100 - 100 / (1 + au / ad) if ad else 100.0)
    return out[: len(c)]


def buckets(closes, horizon, thr):
    c = np.asarray(closes, float)
    r = c[horizon:] / c[:-horizon] - 1
    n = len(r)
    up = float((r > thr).mean() * 100)
    dn = float((r < -thr).mean() * 100)
    return {"n": n, "up": round(up), "range": round(100 - up - dn), "down": round(dn), "horizon_weeks": horizon, "threshold_pct": thr * 100}


def conditional(closes, rsis, horizon, thr, cond):
    c = np.asarray(closes, float)
    idx = [i for i in range(30, len(c) - horizon) if cond(i)]
    if not idx:
        return {"n": 0}
    r = np.array([c[i + horizon] / c[i] - 1 for i in idx])
    up, dn = (r > thr).mean() * 100, (r < -thr).mean() * 100
    return {"n": len(idx), "up": round(up), "range": round(100 - up - dn), "down": round(dn),
            "median_return_pct": round(float(np.median(r) * 100), 1), "note": "overlapping weekly windows; small, autocorrelated sample"}


def build():
    rd = load("inputs/readings.json")
    pg = rd["pages"]
    nv = load("data/nvda_weekly.json")
    bm = load("data/benchmarks_weekly.json")
    ladder = load("config/ladder.json")
    tb = load("config/thesis_breaks.json")
    c = nv["close"]
    price = rd["snapshot"]["nvda_price"]
    r = rsi(c)

    # base rates (outside view), NVDA weekly since Nov 2021
    base = {
        "next_2_weeks": buckets(c, 2, 0.05),
        "this_quarter_approx_7w": buckets(c, 7, 0.10),
        "next_quarter_13w": buckets(c, 13, 0.10),
        "sample": f"NVDA weekly closes {len(c)} bars from 2021-11-22",
    }
    # conditional: weekly RSI <= 36 (stretched, as now)
    cond = lambda i: r[i] is not None and r[i] <= 36
    base["conditional_weekly_rsi_le_36"] = {
        "next_2_weeks": conditional(c, r, 2, 0.05, cond),
        "next_quarter_13w": conditional(c, r, 13, 0.10, cond),
    }
    cond2 = lambda i: c[i] / c[i - 2] - 1 <= -0.15
    base["conditional_2w_drop_le_minus15"] = {
        "next_2_weeks": conditional(c, r, 2, 0.05, cond2),
        "next_quarter_13w": conditional(c, r, 13, 0.10, cond2),
    }

    # weekly RSI context
    rs_hist = [x for x in r if x is not None]
    weekly_rsi = {
        "now_engine": round(r[-1], 1),
        "now_tradingview": pg["tv_technicals_1w"]["values"]["rsi14"],
        "oversold_threshold": 30,
        "is_oversold": bool(r[-1] < 30),
        "rsi_at_apr_2025_low_week": 35.7,
        "lowest_since_2023": round(min(rs_hist[60:]), 1),
        "note": "current weekly bar is open (Thursday); RSI on completed bars only after Friday close",
    }

    # drawdown / structure
    ath = rd["snapshot"]["nvda_ath"]
    structure = {
        "price": price, "last_completed_close": rd["snapshot"]["nvda_last_close"],
        "prev_week_close": rd["snapshot"]["nvda_prev_week_close"],
        "drawdown_from_ath_pct": round((price / ath - 1) * 100, 1),
        "week_change_pct": round((price / rd["snapshot"]["nvda_prev_week_close"] - 1) * 100, 1),
        "dist_to_sma100w_pct": round((price / pg["tv_technicals_1w"]["values"]["sma100"] - 1) * 100, 1),
        "dist_to_sma200w_pct": round((price / pg["tv_technicals_1w"]["values"]["sma200"] - 1) * 100, 1),
        "dist_to_sma200d_pct": round((price / pg["tv_technicals_1d"]["values"]["sma200"] - 1) * 100, 1),
        "gap_zone": [179.92, 185.22],
        "volume_spike_ratio_mon": round(pg["tv_chart_owner"]["values"]["volume_mon_tue_shares"][0] / pg["tv_chart_owner"]["values"]["daily_avg_volume_60d_shares"], 1),
        "atr_daily": pg["tv_technicals_1d"]["values"]["atr14"],
        "atr_daily_pct": round(pg["tv_technicals_1d"]["values"]["atr14"] / price * 100, 1),
        "two_week_change_pct": round((price / rd["snapshot"]["nvda_close_2w_ago_weekly"] - 1) * 100, 1),
        "today_gap_open_pct": round((rd["snapshot"]["today_open"] / rd["snapshot"]["nvda_last_close"] - 1) * 100, 1),
        "today_recovery_from_low_pct": round((price / rd["snapshot"]["today_low"] - 1) * 100, 1),
        "today_low_vs_prev_close_pct": round((rd["snapshot"]["today_low"] / rd["snapshot"]["nvda_last_close"] - 1) * 100, 1),
        "today_volume_vs_60d_avg": round(rd["snapshot"]["today_volume_so_far"] / pg["tv_chart_owner"]["values"]["daily_avg_volume_60d_shares"], 1),
        "today_bar_status": "open (intraday, streaming); hammer/spring shape is unconfirmed until the close",
    }

    # fib check (linear, owner's anchors)
    lo, hi = pg["tv_chart_owner"]["values"]["fib_anchor_low"], pg["tv_chart_owner"]["values"]["fib_anchor_high"]
    fib = {f"fib_{k}": round(hi - (hi - lo) * k, 2) for k in (0.236, 0.382, 0.5, 0.618, 0.65, 0.786)}
    labels = {"fib_0.786": "fib_0786", "fib_0.65": "fib_065", "fib_0.618": "fib_0618", "fib_0.5": "fib_05", "fib_0.382": "fib_0382"}
    # owner's chart labels measure retracement from the low (0 at 10.81, 1 at ATH): level = lo + (hi-lo)*k
    fib_owner = {f"level_{k}": round(lo + (hi - lo) * k, 2) for k in (0.236, 0.382, 0.5, 0.618, 0.65, 0.786)}
    fib_check = {"anchors": [lo, hi], "scale": "linear", "computed": fib_owner,
                 "chart_labels": {k: pg["tv_chart_owner"]["values"][v] for k, v in [("0.786", "fib_0786"), ("0.65", "fib_065"), ("0.618", "fib_0618"), ("0.5", "fib_05"), ("0.382", "fib_0382")]},
                 "log_scale_info": {f"log_{k}": round(math.exp(math.log(lo) + (math.log(hi) - math.log(lo)) * k), 2) for k in (0.5, 0.618, 0.65, 0.786)}}

    # relative strength (weekly)
    sox, spx = bm["SOX"], bm["SPX"]
    nv60 = c[-60:]
    rel = {
        "nvda_vs_sox_ratio_now": round(nv60[-1] / sox[-1] * 1000, 4),
        "nvda_vs_sox_ratio_13w_ago": round(nv60[-14] / sox[-14] * 1000, 4),
        "nvda_vs_sox_ratio_52w_ago": round(nv60[-53] / sox[-53] * 1000, 4),
        "nvda_vs_sox_13w_change_pct": round(((nv60[-1] / sox[-1]) / (nv60[-14] / sox[-14]) - 1) * 100, 1),
        "nvda_vs_sox_52w_change_pct": round(((nv60[-1] / sox[-1]) / (nv60[-53] / sox[-53]) - 1) * 100, 1),
        "nvda_vs_spx_13w_change_pct": round(((nv60[-1] / spx[-1]) / (nv60[-14] / spx[-14]) - 1) * 100, 1),
        "nvda_vs_spx_52w_change_pct": round(((nv60[-1] / spx[-1]) / (nv60[-53] / spx[-53]) - 1) * 100, 1),
    }
    rn = np.diff(np.log(nv60)); rs_ = np.diff(np.log(sox)); rp = np.diff(np.log(spx))
    rel["beta_vs_spx_59w"] = round(float(np.cov(rn, rp)[0, 1] / np.var(rp, ddof=1)), 2)
    rel["beta_vs_sox_59w"] = round(float(np.cov(rn, rs_)[0, 1] / np.var(rs_, ddof=1)), 2)
    rel["corr_vs_sox_59w"] = round(float(np.corrcoef(rn, rs_)[0, 1]), 2)
    rel["this_week_nvda_minus_sox_pts"] = round(pg["tv_relative"]["values"]["nvda_perf_w"] - pg["tv_relative"]["values"]["sox_perf_w"], 1)

    # ladder audit
    fibv = pg["tv_chart_owner"]["values"]
    sma200w = pg["tv_technicals_1w"]["values"]["sma200"]
    resolve = {"tv_chart_owner.fib_065": fibv["fib_065"], "tv_chart_owner.fib_0618": fibv["fib_0618"], "tv_chart_owner.fib_05": fibv["fib_05"], "tv_technicals_1w.sma200": sma200w}
    orders, prev_mid = [], None
    for o in ladder["orders"]:
        mid = round((o["zone_low"] + o["zone_high"]) / 2, 2)
        anchors = []
        for a in o["anchors"]:
            v = a.get("value", resolve.get(a.get("ref")))
            anchors.append({"name": a["name"], "value": v, "drift_pct_vs_mid": round((mid / v - 1) * 100, 1)})
        gap = None if prev_mid is None else round((prev_mid / mid - 1) * 100, 1)
        flags = []
        if any(abs(a["drift_pct_vs_mid"]) > 2 for a in anchors):
            flags.append("anchor drift >2%")
        if gap is not None and gap < 3:
            flags.append("<3% from previous order")
        orders.append({"id": o["id"], "zone": [o["zone_low"], o["zone_high"]], "mid": mid, "weight": o["weight"],
                       "dist_from_price_pct": round((mid / price - 1) * 100, 1), "gap_from_prev_pct": gap,
                       "anchors": anchors, "flags": flags})
        prev_mid = mid
    w = np.array([o["weight"] for o in orders]); m = np.array([o["mid"] for o in orders])
    # cumulative average for equal-dollar-per-weight sizing (shares = usd/price)
    cum = []
    for k in range(1, len(orders) + 1):
        usd = w[:k]; sh = (usd / m[:k]).sum()
        cum.append({"through": orders[k - 1]["id"], "weight_used": float(usd.sum()), "share_of_budget_pct": round(float(usd.sum() / w.sum() * 100), 1),
                    "avg_price_if_filled": round(float(usd.sum() / sh), 2)})
    ladder_audit = {"status": ladder["_status"], "budget_usd": ladder["budget_usd"], "orders": orders, "cumulative": cum,
                    "earnings_blackout": {"earnings": pg["tv_fundamentals"]["values"]["next_earnings"], "blackout_trading_days": ladder["earnings_blackout_trading_days"], "blackout_window": "2026-11-12 to 2026-11-17 (today is inside it)", "orders_touched_today_intraday": [o["id"] for o in ladder["orders"] if rd["snapshot"]["today_low"] <= o["zone_high"]]},
                    "breakout_tranche": ladder["breakout_tranche"]}

    fs = {
        "as_of": rd["as_of"], "price_note": rd["price_note"], "snapshot": rd["snapshot"],
        "base_rates": base, "weekly_rsi": weekly_rsi, "structure": structure, "fib_check": fib_check,
        "relative": rel, "ladder_audit": ladder_audit, "thesis_breaks": tb["breaks"],
        "thesis_break_status": {"TB1": "not fired (no finding or charge)", "TB2": "CANDIDATE FIRED 2026-11-11: CEO resigned effective immediately during board probe, DOJ inquiry and congressional pressure; 8-K gives no reason. Chair to rule; owner confirms.", "TB3": "not fired (no restriction enacted)", "TB4": "unmonitored (hyperscaler capex not in data)"},
        "pages": pg,
    }
    out = ROOT / "outputs/fact_sheet.json"
    out.write_text(json.dumps(fs, indent=1, default=float))
    print("wrote", out)
    return fs


if __name__ == "__main__":
    build()
