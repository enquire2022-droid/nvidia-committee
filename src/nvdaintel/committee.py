"""Committee plumbing: slices, submission check, log.

python -m nvdaintel.committee slices
python -m nvdaintel.committee check <file.json>
python -m nvdaintel.committee log <run_id>
"""
import json, sys, pathlib, datetime
ROOT = pathlib.Path(__file__).resolve().parents[2]
FS = ROOT / "outputs/fact_sheet.json"

COMMON = ["as_of", "price_note", "snapshot", "base_rates", "thesis_breaks"]
SLICES = {
    "technical": COMMON + ["weekly_rsi", "structure", "fib_check", "ladder_audit", ("pages", ["tv_technicals_1w", "tv_technicals_1d", "tv_technicals_4h", "tv_chart_owner"])],
    "macro": COMMON + [("pages", ["tv_purple_list", "economic_calendar", "tv_relative"])],
    "fundamentals": COMMON + ["structure", ("pages", ["tv_fundamentals", "economic_calendar"])],
    "relative_strength": COMMON + ["relative", "structure", ("pages", ["tv_relative", "tv_purple_list"])],
    "sentiment": COMMON + ["weekly_rsi", "structure", ("pages", ["sentiment_aaii", "sentiment_cnn_fg", "options_positioning", "tv_purple_list", "tv_chart_owner"])],
    "narrative": COMMON + ["structure", ("pages", ["news_governance", "tv_fundamentals", "tv_relative"])],
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
    print("OK" if not errs else "\n".join(errs))
    return not errs


def log(run_id):
    run = ROOT / "committee/runs" / run_id
    with open(ROOT / "committee/log.jsonl", "a") as f:
        for p in sorted(run.glob("*.json")):
            d = json.loads(p.read_text())
            f.write(json.dumps({"logged": datetime.date.today().isoformat(), "run_id": run_id, "agent": d["agent"],
                                "price_at_call": d["price_at_call"], "probabilities": d["probabilities"]}) + "\n")
    print("logged", run_id)


if __name__ == "__main__":
    cmd = sys.argv[1]
    {"slices": lambda: slices(), "check": lambda: sys.exit(0 if check(sys.argv[2]) else 1), "log": lambda: log(sys.argv[2])}[cmd]()
