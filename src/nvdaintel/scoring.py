"""Scoring engine. Code keeps score; the performance-review agent explains it.

Every logged forecast (committee/log.jsonl: one line per agent per run) is resolved against
NVDA completed daily closes (data/nvda_daily.json, TradingView, regular session):
  next_2_weeks  -> last close on or before as_of + 14 days (holiday-aware; e.g. Thanksgiving)
  this_quarter  -> last close on or before the end of as_of's calendar quarter
  next_quarter  -> last close on or before the end of the following quarter
Buckets vs price_at_call: 2 weeks +-5%, quarters +-10% (same contract as the memo and market-data).
A forecast stays 'pending' until a close exists within 3 calendar days before the resolve date
(a close older than that = 'pending_no_price').

Score: 3-class Brier (0 = perfect, 2 = worst) vs the outside view known at as_of
(share of past windows of the same length, from NVDA daily closes up to as_of):
skill = 1 - Brier / Brier_base (positive = better than quoting the base rate).
Weights are proposed only for members with >= MIN_N resolved forecasts; the owner approves any change.

  python -m nvdaintel.scoring   -> outputs/scorecard.json (+ .csv)
"""
import csv, json, datetime as dt, pathlib
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parents[2]
LOG = ROOT / "committee" / "log.jsonl"
MIN_N = 10
BUCKETS = ("up", "range", "down")
THRESH = {"next_2_weeks": 5.0, "this_quarter": 10.0, "next_quarter": 10.0}


def closes(include_today=False) -> pd.Series:
    d = json.loads((ROOT / "data/nvda_daily.json").read_text())
    s = pd.Series(d["c"], index=pd.to_datetime(d["t"], unit="s").normalize(), dtype=float)
    s = s[~s.index.duplicated(keep="last")].sort_index()
    if not include_today:
        today = pd.Timestamp.now(tz="UTC").tz_localize(None).normalize()
        s = s[s.index < today]  # today's bar is still open
    return s


def resolve_date(h: str, as_of: pd.Timestamp) -> pd.Timestamp:
    if h == "next_2_weeks":
        return as_of + pd.Timedelta(days=14)
    q = (as_of + pd.offsets.QuarterEnd(0)).normalize()
    return q if h == "this_quarter" else (q + pd.offsets.QuarterEnd(1)).normalize()


def close_on_or_before(c: pd.Series, d: pd.Timestamp, max_gap_days=3):
    s = c[c.index <= d]
    if s.empty or (d - s.index[-1]).days > max_gap_days:
        return None, None
    return float(s.iloc[-1]), s.index[-1]


def outcome(p0, close, t):
    r = round((close / p0 - 1) * 100, 9)  # avoid float noise at the exact threshold
    return "up" if r > t else "down" if r < -t else "range"


def brier(p, out):
    return float(sum((p[b] / 100 - (1.0 if b == out else 0.0)) ** 2 for b in BUCKETS))


def base_rate(c: pd.Series, as_of: pd.Timestamp, days: int, t: float) -> dict:
    s = c[c.index <= as_of]
    idx = s.index.searchsorted(s.index + pd.Timedelta(days=days))
    ok = idx < len(s)
    r = (s.to_numpy()[idx[ok]] / s.to_numpy()[ok] - 1) * 100
    if not len(r):
        return {b: 100 / 3 for b in BUCKETS}
    return {"up": float((r > t).mean() * 100), "range": float(((r >= -t) & (r <= t)).mean() * 100), "down": float((r < -t).mean() * 100)}


def entries():
    if not LOG.exists():
        return []
    return [json.loads(l) for l in LOG.read_text().splitlines() if l.strip()]


def score():
    c = closes()
    last = c.index.max()
    rows = []
    for e in entries():
        as_of = pd.Timestamp(e["as_of"])
        for h, t in THRESH.items():
            p = (e.get("probabilities") or {}).get(h)
            if not isinstance(p, dict):
                continue
            rd = resolve_date(h, as_of)
            row = {"run_id": e["run_id"], "agent": e["agent"], "horizon": h, "as_of": str(as_of.date()), "resolves": str(rd.date()),
                   "price_at_call": e["price_at_call"], "p_up": p["up"], "p_range": p["range"], "p_down": p["down"],
                   "confidence": e.get("confidence"), "status": "pending"}
            if rd <= last:
                close, cd = close_on_or_before(c, rd)
                if close is None:
                    row["status"] = "pending_no_price"
                else:
                    out = outcome(e["price_at_call"], close, t)
                    b = brier(p, out)
                    base = base_rate(c, as_of, (rd - as_of).days, t)
                    bb = brier(base, out)
                    row.update({"status": "resolved", "close_date": str(cd.date()), "close": close, "outcome": out,
                                "brier": round(b, 4), "brier_base": round(bb, 4), "skill": round(1 - b / bb, 3) if bb else None})
            rows.append(row)
    res = [r for r in rows if r["status"] == "resolved"]
    by_agent = {}
    for r in res:
        a = by_agent.setdefault(r["agent"], {"n": 0, "brier": [], "brier_base": []})
        a["n"] += 1; a["brier"].append(r["brier"]); a["brier_base"].append(r["brier_base"])
    summary = {k: {"n": v["n"], "mean_brier": round(float(np.mean(v["brier"])), 4), "mean_brier_base": round(float(np.mean(v["brier_base"])), 4),
                   "skill": round(1 - np.mean(v["brier"]) / np.mean(v["brier_base"]), 3) if np.mean(v["brier_base"]) else None,
                   "weight_proposal_eligible": v["n"] >= MIN_N} for k, v in by_agent.items()}
    out = {"built_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "last_close": str(last.date()),
           "n_forecasts": len(rows), "n_resolved": len(res), "n_pending": len(rows) - len(res), "by_agent": summary,
           "calibration_note": "uncalibrated: fewer than 20 resolved forecasts" if len(res) < 20 else "", "min_n_for_weights": MIN_N}
    (ROOT / "outputs").mkdir(exist_ok=True)
    (ROOT / "outputs/scorecard.json").write_text(json.dumps(out, indent=1))
    keys = sorted({k for r in rows for k in r})
    with open(ROOT / "outputs/scorecard.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(rows)
    print(f"scorecard: {len(rows)} forecasts, {len(res)} resolved, {len(rows)-len(res)} pending (last close {last.date()})")
    return out


if __name__ == "__main__":
    score()
