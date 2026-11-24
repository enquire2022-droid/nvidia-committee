"""Tier-1 engines (owner-approved 15 Nov 2026): page coverage + stale flags, trigger reachability,
hyperscaler capex monitor (TB4), full ladder history. Called by factsheet.build().

python -m nvdaintel.engines reach <level> <YYYY-MM-DD>   # one trigger: how often NVDA has moved that far in that window
"""
import json, math, sys, pathlib, datetime as dt
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[2]
UNREACHABLE_PCT = 5.0   # a trigger reached in < 5% of past windows of the same length is not a fair trigger
EXPECTED_PCT = 95.0     # reached in > 95% -> belongs on the "Expected" line, not under triggers


def _utc(s):
    if not s:
        return None
    try:
        return pd.Timestamp(s).tz_convert("UTC") if pd.Timestamp(s).tzinfo else pd.Timestamp(s).tz_localize("UTC")
    except Exception:  # noqa: BLE001
        return None


# ---------- page coverage and stale flags ----------
def coverage(readings: dict, as_of: str) -> dict:
    cfg = json.loads((ROOT / "config/pages.json").read_text())["pages"]
    pages = readings.get("pages", {})
    cutoff = _utc(readings.get("event_cutoff_utc"))
    asof = pd.Timestamp(as_of).tz_localize("UTC")
    rows, ok, stale, failed, missing, deferred = [], 0, 0, 0, 0, 0
    for p in cfg:
        r = pages.get(p["id"])
        row = {"id": p["id"], "how": p["how"]}
        if p.get("deferred"):
            row["state"] = "deferred"; deferred += 1
        elif r is None:
            row["state"] = "missing"; missing += 1
        elif r.get("status") == "failed":
            row["state"] = "failed"; row["reason"] = r.get("reason"); failed += 1
        else:
            read = _utc(r.get("read_utc"))
            reasons = []
            if read is None:
                reasons.append("no read_utc recorded")
            else:
                if cutoff is not None and read < cutoff:
                    reasons.append(f"read before event cutoff {readings.get('event_cutoff_utc')}")
                if (asof - read.normalize()).days > p.get("max_age_days", 1):
                    reasons.append(f"older than {p.get('max_age_days', 1)} day(s)")
            if r.get("status") == "partial":
                reasons.append("partial read")
            row["state"] = "stale" if reasons else "ok"
            row["read_utc"] = r.get("read_utc"); row["data_time"] = r.get("data_time")
            if reasons:
                row["reasons"] = reasons; stale += 1
            else:
                ok += 1
        rows.append(row)
    n = len(cfg) - deferred
    return {"pages_total": len(cfg), "pages_required": n, "ok": ok, "stale": stale, "failed": failed, "missing": missing,
            "deferred": deferred, "line": f"{ok}/{n} pages ok ({stale} stale, {failed} failed, {missing} missing; {deferred} deferred)",
            "complete": ok == n, "event_cutoff_utc": readings.get("event_cutoff_utc"), "rows": rows}


# ---------- reachability ----------
def _daily():
    d = json.loads((ROOT / "data/nvda_daily.json").read_text())
    return pd.Series(d["c"], index=pd.to_datetime(d["t"], unit="s").normalize(), dtype=float).sort_index()


def reach_freq(move_pct: float, trading_days: int, c: pd.Series = None) -> dict:
    """Share of past windows (NVDA daily closes) in which some close within `trading_days` reached `move_pct`
    from the window's start (positive = up, negative = down)."""
    c = _daily() if c is None else c
    a = c.to_numpy()
    n = len(a) - trading_days
    if n <= 0:
        return {"freq_pct": None, "n": 0}
    hits = 0
    for i in range(n):
        w = a[i + 1:i + 1 + trading_days] / a[i] - 1
        hits += (w.max() * 100 >= move_pct) if move_pct > 0 else (w.min() * 100 <= move_pct)
    return {"freq_pct": round(hits / n * 100, 1), "n": n}


def trading_days_between(start: pd.Timestamp, end: pd.Timestamp) -> int:
    return max(1, int(np.busday_count(start.date(), end.date())))


def reach_trigger(level: float, end: str, price: float, start: str) -> dict:
    s, e = pd.Timestamp(start), pd.Timestamp(end)
    td = trading_days_between(s, e)
    move = (level / price - 1) * 100
    f = reach_freq(move, td)
    verdict = ("unreachable" if f["freq_pct"] is not None and f["freq_pct"] < UNREACHABLE_PCT else
               "expected" if f["freq_pct"] is not None and f["freq_pct"] > EXPECTED_PCT else "reachable")
    return {"level": level, "by": end, "trading_days": td, "move_needed_pct": round(move, 1), **f, "verdict": verdict}


def reach_table(c: pd.Series = None) -> dict:
    c = _daily() if c is None else c
    out = {"sample": f"NVDA daily closes {c.index[0].date()} to {c.index[-1].date()} (n={len(c)})",
           "rule": f"under {UNREACHABLE_PCT}% = unreachable (not a trigger); over {EXPECTED_PCT}% = Expected line", "windows": {}}
    r1 = c.pct_change().dropna() * 100
    out["one_day"] = {f"ge_+{k}": round(float((r1 >= k).mean() * 100), 2) for k in (5, 10, 15)}
    out["one_day"].update({f"le_-{k}": round(float((r1 <= -k).mean() * 100), 2) for k in (5, 10, 15)})
    for name, td in (("1w", 5), ("2w", 10), ("6w", 30), ("1q", 63)):
        out["windows"][name] = {f"{m:+d}%": reach_freq(m, td, c)["freq_pct"] for m in (-30, -20, -10, -5, 5, 10, 20, 30)}
    return out


# ---------- hyperscaler capex (TB4 monitor) ----------
def capex_monitor() -> dict:
    p = ROOT / "data/capex_snapshots.json"
    if not p.exists():
        return {"status": "no data"}
    snaps = json.loads(p.read_text())["snapshots"]
    last = snaps[-1]
    rows, falling = {}, 0
    for k, v in last["companies"].items():
        q, ttm, fy = -v["last_quarter"], -v["ttm"], -v["last_fiscal_year"]
        rr = q * 4
        row = {"last_quarter_bn": round(q / 1e9, 1), "ttm_bn": round(ttm / 1e9, 1), "last_fy_bn": round(fy / 1e9, 1),
               "run_rate_vs_ttm_pct": round((rr / ttm - 1) * 100, 1), "ttm_vs_last_fy_pct": round((ttm / fy - 1) * 100, 1)}
        prev = [s for s in snaps[:-1] if k in s["companies"]]
        if prev:
            pq = -prev[-1]["companies"][k]["last_quarter"]
            if pq != q:
                row["q_vs_previous_snapshot_pct"] = round((q / pq - 1) * 100, 1)
        row["falling"] = row["run_rate_vs_ttm_pct"] < -10
        falling += row["falling"]
        rows[k] = row
    return {"read_utc": last["read_utc"], "companies": rows, "n_falling": falling,
            "proxy_flag": falling >= 2,
            "rule": "Proxy only: 'falling' = last-quarter run-rate more than 10% below TTM. Two or more falling raises a TB4 WATCH; "
                    "TB4 itself fires only on capex guidance cuts by two or more of the four (narrative member confirms from filings/calls).",
            "status": "TB4 WATCH" if falling >= 2 else "no capex cut signal"}


# ---------- full ladder history ----------
def ladder_history(ladder: dict) -> list:
    rows = []
    for f in ladder.get("pre_ladder_fills", []):
        rows.append({"order": "pre-ladder", "status": "filled", **f})
    for f in ladder.get("dropped_orders", []):
        rows.append({"order": f.get("id"), "status": "dropped", **f})
    for f in ladder.get("filled_orders", []):
        rows.append({"order": f.get("id"), "status": "filled", **f})
    filled_ids = {f.get("id") for f in ladder.get("filled_orders", [])} | {f.get("id") for f in ladder.get("dropped_orders", [])}
    for o in ladder.get("orders", []):
        if o["id"] not in filled_ids:
            default = "resting (proposed)" if ladder.get("budget_usd") is None else "resting"
            rows.append({"order": o["id"], "status": o.get("status", default),
                         "planned_zone": [o["zone_low"], o["zone_high"]], "planned_weight": o["weight"]})
    return rows


if __name__ == "__main__":
    if sys.argv[1:2] == ["reach"]:
        fs = json.loads((ROOT / "outputs/fact_sheet.json").read_text())
        print(json.dumps(reach_trigger(float(sys.argv[2]), sys.argv[3], fs["snapshot"]["nvda_price"], fs["as_of"]), indent=1))
    else:
        print(__doc__)


# ---- Ladder change triggers (owner-approved 24 Nov 2026, adapted from BTC committee2 rule P) ----
# A level changes only when what it is tied to changes, never because the expected path failed. Proposals only.
DRIFT_LOG = ROOT / "outputs/ladder_drift_log.jsonl"


def _weekly_full():
    d = json.loads((ROOT / "data/nvda_weekly_full.json").read_text())
    return pd.DataFrame({k: d[k] for k in "ohlcv"}, index=pd.to_datetime(d["t"], unit="s").normalize())


def ladder_triggers(ladder, as_of, sma200w, atr_daily, thesis_breaks=None, log=True, max_drift_pct=2.0):
    wk = _weekly_full()
    asof = pd.Timestamp(as_of)
    comp = wk[wk.index <= asof - pd.Timedelta(days=7)]          # completed weeks only
    last_week = str(comp.index[-1].date())
    fired, notes = [], {}
    # A. anchor drift on two consecutive completed weeks, same direction (dynamic anchors only)
    rows = []
    for o in ladder["orders"]:
        if o.get("type", "dip") != "dip":
            continue
        mid = (o["zone_low"] + o["zone_high"]) / 2
        for a in o.get("anchors", []):
            name = a["name"]; val = None
            if "sma200w" in name:
                val = sma200w
            elif name == "anchor_rule" and o["id"] == "D1":
                val = sma200w - atr_daily                         # D1 = 200W SMA minus one daily ATR
            if val is None:
                continue
            rows.append({"week": last_week, "order": o["id"], "anchor": name, "value": round(val, 2), "zone_mid": mid,
                         "drift_pct": round((val / mid - 1) * 100, 2)})
    hist = []
    if DRIFT_LOG.exists():
        hist = [json.loads(x) for x in DRIFT_LOG.read_text().splitlines() if x.strip()]
    if log and rows and not any(h["week"] == last_week for h in hist):
        DRIFT_LOG.parent.mkdir(parents=True, exist_ok=True)
        with DRIFT_LOG.open("a") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        hist += rows
    drift_hits = []
    for r in rows:
        prev = [h for h in hist if h["order"] == r["order"] and h["anchor"] == r["anchor"] and h["week"] < r["week"]]
        if prev:
            p = sorted(prev, key=lambda x: x["week"])[-1]
            if abs(r["drift_pct"]) > max_drift_pct and abs(p["drift_pct"]) > max_drift_pct and np.sign(r["drift_pct"]) == np.sign(p["drift_pct"]):
                drift_hits.append(f"{r['order']} anchor {r['anchor']} {r['value']} vs zone mid {r['zone_mid']} ({r['drift_pct']:+.1f}%) two weeks running")
    notes["A_anchor_drift"] = {"rows_this_week": rows, "hits": drift_hits}
    if drift_hits:
        fired.append("A")
    # B. structure break: weekly close below the established drawdown low (a low 4+ weeks old; newer lows = bottoming)
    c, low = comp.c, comp.l
    pk = int(np.argmax(c.values)); seg = low.iloc[pk:]
    lo_i = int(np.argmin(seg.values)); lo_val = float(seg.iloc[lo_i]); lo_date = seg.index[lo_i]
    weeks_old = len(seg) - 1 - lo_i
    established = weeks_old >= 4
    b = established and float(c.iloc[-1]) < lo_val
    notes["B_structure_break"] = {"drawdown_low": round(lo_val, 2), "low_week": str(lo_date.date()), "weeks_old": weeks_old,
                                  "established": established, "last_weekly_close": round(float(c.iloc[-1]), 2), "fired": b}
    if b:
        fired.append("B")
    # C. regime change: two consecutive weekly closes above the 100W SMA within the last 8 weeks, after a close below it
    s100 = c.rolling(100).mean()
    above = (c > s100)
    cfire = False
    for k in range(max(2, len(c) - 8), len(c)):
        if above.iloc[k] and above.iloc[k - 1] and not above.iloc[k - 2]:
            cfire = True
    notes["C_regime_change"] = {"sma100w_last_completed": round(float(s100.iloc[-1]), 2), "fired": cfire}
    if cfire:
        fired.append("C")
    # D. shock or thesis-break change: a daily move > 4x its prior 60-day stdev in the last 5 sessions, or a TB status change in 7 days
    dd = json.loads((ROOT / "data/nvda_daily.json").read_text())
    dc = pd.Series(dd["c"], index=pd.to_datetime(dd["t"], unit="s").normalize())
    r1 = np.log(dc).diff(); sd = r1.rolling(60).std().shift(1)
    shocks = [f"{d.date()} {100 * (math.exp(x) - 1):+.1f}% ({abs(x) / s:.1f} sd)" for d, x, s in zip(r1.index[-5:], r1.values[-5:], sd.values[-5:]) if abs(x) > 4 * s]
    tb_changes = []
    for b_ in (thesis_breaks or {}).get("breaks", []):
        st = str(b_.get("status", ""))
        for tag in ("2026-", "2027-"):
            pass
        if any(k in st for k in ("CLEARED", "FIRED", "WATCH")) and b_.get("changed_on") and (asof - pd.Timestamp(b_["changed_on"])).days <= 7:
            tb_changes.append(f"{b_['id']}: {st[:60]}")
    notes["D_shock_or_thesis_break"] = {"shocks": shocks, "tb_changes": tb_changes}
    if shocks or tb_changes:
        fired.append("D")
    return {"rule": "Ladder change triggers (owner-approved 24 Nov 2026): A anchor drift >2% two weekly runs, B weekly close below the "
                    "established drawdown low, C confirmed 100W reclaim within 8 weeks, D shock (>4 sd day) or thesis-break change within 7 days. "
                    "Proposals only; never because the expected path failed.",
            "last_completed_week": last_week, "fired": fired, "details": notes,
            "memo_line": ("Ladder: no change trigger - hold" if not fired else f"Ladder review opened by trigger(s) {', '.join(fired)}")}
