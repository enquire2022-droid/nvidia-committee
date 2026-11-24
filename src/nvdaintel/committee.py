"""Committee plumbing: slices, submission check, log.

python -m nvdaintel.committee readings-template
python -m nvdaintel.committee slices
python -m nvdaintel.committee check <file.json>
python -m nvdaintel.committee log <run_id>
"""
import json, sys, pathlib, datetime
ROOT = pathlib.Path(__file__).resolve().parents[2]
FS = ROOT / "outputs/fact_sheet.json"

COMMON = ["as_of", "price_note", "snapshot", "base_rates", "thesis_breaks", "coverage", "reachability"]
SLICES = {
    "technical": COMMON + ["weekly_rsi", "structure", "fib_check", "ladder_audit", ("pages", ["tv_technicals_1w", "tv_technicals_1d", "tv_technicals_4h", "tv_chart_owner"])],
    "macro": COMMON + [("pages", ["tv_purple_list", "economic_calendar", "tv_relative"])],
    "fundamentals": COMMON + ["structure", "hyperscaler_capex", ("pages", ["tv_fundamentals", "economic_calendar"])],
    "relative_strength": COMMON + ["relative", "structure", ("pages", ["tv_relative", "tv_purple_list"])],
    "sentiment": COMMON + ["weekly_rsi", "structure", ("pages", ["sentiment_aaii", "sentiment_cnn_fg", "options_positioning", "tv_purple_list", "tv_chart_owner"])],
    "narrative": COMMON + ["structure", "hyperscaler_capex", ("pages", ["news_governance", "tv_fundamentals", "tv_relative"])],
}
REQ = ["agent", "run_id", "as_of", "price_at_call", "view", "probabilities", "confidence", "evidence", "key_levels", "what_would_change_my_mind", "notes_for_chair"]


def slices():
    fs = json.loads(FS.read_text())
    (ROOT / "outputs/slices").mkdir(parents=True, exist_ok=True)
    for name, keys in SLICES.items():
        s = {}
        for k in keys:
            if isinstance(k, tuple):
                s[k[0]] = {p: fs[k[0]][p] for p in k[1]}
            else:
                s[k] = fs[k]
        (ROOT / f"outputs/slices/{name}.json").write_text(json.dumps(s, indent=1))
    (ROOT / "outputs/slices/red_team.json").write_text(json.dumps(fs, indent=1))
    print("slices:", ", ".join(list(SLICES) + ["red_team"]))


def readings_template():
    """Fresh inputs/readings.json: every page in config/pages.json set to pending (keeps nothing from the last run)."""
    cfg = json.loads((ROOT / "config/pages.json").read_text())["pages"]
    tpl = {"as_of": datetime.date.today().isoformat(), "event_cutoff_utc": None, "price_note": "", "snapshot": {},
           "pages": {p["id"]: ({"status": "failed", "reason": "deferred by owner (paid data)"} if p.get("deferred") else
                               {"status": "pending", "read_utc": None, "data_time": None, "source": p["how"], "values": {}}) for p in cfg}}
    out = ROOT / "inputs/readings.json"
    if out.exists():
        out.rename(ROOT / f"inputs/readings_{json.loads(out.read_text()).get('as_of', 'old')}.json")
    out.write_text(json.dumps(tpl, indent=1))
    print("readings template:", len(cfg), "pages pending ->", out)


def check(path):
    d = json.loads(pathlib.Path(path).read_text())
    errs = [f"missing {k}" for k in REQ if k not in d]
    for h in ("next_2_weeks", "this_quarter", "next_quarter"):
        p = d.get("probabilities", {}).get(h)
        if not p or sum(p.get(x, 0) for x in ("up", "range", "down")) != 100:
            errs.append(f"probabilities.{h} must have up/range/down summing to 100")
    if not isinstance(d.get("confidence"), (int, float)) or not 0 <= d["confidence"] <= 100:
        errs.append("confidence 0-100")
    for e in d.get("evidence", []):
        if not e.get("ref") or not e.get("point"):
            errs.append("evidence items need ref and point")
    if d.get("agent") == "chair":   # decision record (Tier 1, 15 Nov 2026)
        req = ["decision", "tb_rulings", "triggers", "expected", "rulings", "expected_path", "ladder_proposals", "coverage_note", "label"]
        if str(d.get("as_of", "")) > "2026-11-24":          # cycle placement required from the run after 2026-11-24 (owner, 24 Nov 2026)
            req.append("cycle_placement")
            cp = d.get("cycle_placement") or {}
            for k in ("stage", "basis", "agrees_with_probabilities"):
                if k not in cp:
                    errs.append(f"chair: cycle_placement.{k} missing")
        for k in req:
            if k not in d:
                errs.append(f"chair: missing {k}")
        for k in ("strategic", "tactical"):
            if not (d.get("decision", {}).get(k) or {}).get("stance"):
                errs.append(f"chair: decision.{k}.stance missing")
        for t in d.get("triggers", []):
            v = (t.get("reach") or {}).get("verdict")
            if v not in ("reachable", "event"):
                errs.append(f"chair: trigger needs reach.verdict reachable/event (got {v}): {str(t.get('text'))[:60]}")
        for c in (d.get("expected_path") or {}).get("checkpoints", []):
            for k in ("window", "confirm", "invalidate", "status"):
                if k not in c:
                    errs.append(f"chair: checkpoint {c.get('n')} missing {k}")
    print("OK" if not errs else "\n".join(errs))
    return not errs


def log(run_id):
    """Append the run's final submissions (top-level files only; superseded versions in subfolders are not logged).
    A (run_id, agent) already in the log is never written twice."""
    run = ROOT / "committee/runs" / run_id
    path = ROOT / "committee/log.jsonl"
    have = set()
    if path.exists():
        for l in path.read_text().splitlines():
            if l.strip():
                r = json.loads(l); have.add((r["run_id"], r["agent"]))
    n = 0
    with open(path, "a") as f:
        for p in sorted(run.glob("*.json")):
            d = json.loads(p.read_text())
            if (run_id, d["agent"]) in have:
                continue
            f.write(json.dumps({"run_id": run_id, "agent": d["agent"], "as_of": d["as_of"], "price_at_call": d["price_at_call"],
                                "probabilities": {k: d["probabilities"][k] for k in ("next_2_weeks", "this_quarter", "next_quarter")},
                                "confidence": d.get("confidence"), "symbol": "NASDAQ:NVDA",
                                "logged_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")}) + "\n")
            n += 1
    print(f"logged {n} new submissions for {run_id}")

if __name__ == "__main__":
    cmd = sys.argv[1]
    {"readings-template": lambda: readings_template(), "slices": lambda: slices(), "check": lambda: sys.exit(0 if check(sys.argv[2]) else 1), "log": lambda: log(sys.argv[2])}[cmd]()
