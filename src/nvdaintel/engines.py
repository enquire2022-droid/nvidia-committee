"""Tier-1 engines (owner-approved 15 Nov 2026): page coverage + stale flags, trigger reachability,
hyperscaler capex monitor (TB4), full ladder history. Called by factsheet.build().

python -m nvdaintel.engines reach <level> <YYYY-MM-DD>   # one trigger: how often NVDA has moved that far in that window
"""
import json, sys, pathlib, datetime as dt
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
            rows.append({"order": o["id"], "status": "resting (proposed)" if ladder.get("budget_usd") is None else "resting",
                         "planned_zone": [o["zone_low"], o["zone_high"]], "planned_weight": o["weight"]})
    return rows


if __name__ == "__main__":
    if sys.argv[1:2] == ["reach"]:
        fs = json.loads((ROOT / "outputs/fact_sheet.json").read_text())
        print(json.dumps(reach_trigger(float(sys.argv[2]), sys.argv[3], fs["snapshot"]["nvda_price"], fs["as_of"]), indent=1))
    else:
        print(__doc__)
