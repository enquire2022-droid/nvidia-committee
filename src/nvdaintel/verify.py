"""Verifier gate (rewritten 15 Nov 2026, Tier 1 item 4).

Numbers in the memo must trace to the CURRENT fact sheet, the chair's chair.json, config, or the structured
fields of this run's final submissions (probabilities, confidence, key-level values, price_at_call).
Free text in submissions (evidence, notes) is NOT a source: stale numbers there must not pass.
Superseded submissions in sub-folders are ignored.

Labelled checks (fail the memo):
  L1 ladder table: each L-row's distance must equal fact_sheet.ladder_audit (current price)
  L2 outlook: the Chair row must equal chair.json probabilities
  L3 coverage line: the memo states fact_sheet.coverage.line verbatim; every stale/failed/missing page is named in Sources
  L4 decision box: has an "Expected" line and "What would change it"; every chair trigger carries a reachability verdict
     and none is 'unreachable' or 'expected'
  L5 sections present

python -m nvdaintel.verify outputs/reviews/<run_id>.md <run_id>
"""
import json, re, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]
SECTIONS = ["Final committee decision", "Expected", "What would change it", "Bottom line", "Macro", "Technicals", "Fundamentals",
            "Relative strength", "Sentiment", "Narrative", "Kahneman", "System 1", "System 2", "Outlook", "Expected path",
            "Ladder Audit", "Strategy", "Thesis-break", "Committee", "Performance review", "Dashboard", "Sources"]


def harvest(obj, out):
    if isinstance(obj, dict):
        for v in obj.values():
            harvest(v, out)
    elif isinstance(obj, list):
        for v in obj:
            harvest(v, out)
    elif isinstance(obj, bool):
        return
    elif isinstance(obj, (int, float)):
        out.add(float(obj))
    elif isinstance(obj, str):
        for m in re.findall(r"-?\d[\d,]*\.?\d*", obj):
            try:
                out.add(float(m.replace(",", "")))
            except ValueError:
                pass


def known(run_id):
    vals = set()
    harvest(json.loads((ROOT / "outputs/fact_sheet.json").read_text()), vals)
    harvest(json.loads((ROOT / "outputs/scorecard.json").read_text()) if (ROOT / "outputs/scorecard.json").exists() else {}, vals)
    for p in (ROOT / "config").glob("*.json"):
        harvest(json.loads(p.read_text()), vals)
    run = ROOT / "committee/runs" / run_id
    for p in run.glob("*.json"):   # top level only = final versions
        d = json.loads(p.read_text())
        if d.get("agent") == "chair":
            harvest(d, vals)       # chair.json is the decision record: all of it is citable
        else:
            harvest({k: d.get(k) for k in ("price_at_call", "probabilities", "confidence")}, vals)
            harvest([kl.get("level") for kl in d.get("key_levels", []) if isinstance(kl, dict)], vals)
    return vals


def matches(x, vals):
    for v in vals:
        for scale in (1, 1e-9, 1e-6, 1e-3):
            vv = v * scale
            if abs(vv) < 1e-12:
                continue
            if abs(x - vv) <= max(0.051, abs(vv) * 0.0006) or abs(abs(x) - abs(vv)) <= 0.051:
                return True
    return False


def labelled(text, run_id):
    fs = json.loads((ROOT / "outputs/fact_sheet.json").read_text())
    chair = json.loads((ROOT / "committee/runs" / run_id / "chair.json").read_text())
    errs = []
    # L1 ladder distances
    for o in fs["ladder_audit"]["orders"]:
        m = re.search(rf"^\|\s*{o['id']}\s*\|[^\n]*", text, re.M)
        if m:
            nums = [float(x.replace("−", "-")) for x in re.findall(r"[−-]?\d+\.\d+(?=%)", m.group(0))]
            if nums and not any(abs(n - o["dist_from_price_pct"]) < 0.051 for n in nums):
                errs.append(f"L1 ladder {o['id']}: distance in memo {nums} != fact sheet {o['dist_from_price_pct']}%")
    # L2 chair outlook row
    pr = chair["probabilities"]
    want = [pr[h][b] for h in ("next_2_weeks", "this_quarter", "next_quarter") for b in ("up", "range", "down")]
    rows = re.findall(r"^\|\s*\**Chair\**\s*\|[^\n]*", text, re.M)
    if not rows:
        errs.append("L2 no Chair row in the outlook/committee table")
    for r in rows:
        got = [int(x) for x in re.findall(r"\b\d{1,3}\b", r)][:9]
        if len(got) >= 9 and got != want:
            errs.append(f"L2 Chair row {got} != chair.json {want}")
    # L3 coverage
    cov = fs.get("coverage", {})
    if cov.get("line") and cov["line"] not in text:
        errs.append(f"L3 coverage line missing: '{cov['line']}'")
    src = text[text.lower().rfind("## sources"):] if "## sources" in text.lower() else ""
    for r in cov.get("rows", []):
        if r["state"] in ("stale", "failed", "missing") and r["id"] not in src:
            errs.append(f"L3 {r['state']} page '{r['id']}' not named in Sources")
    # L4 triggers
    for t in chair.get("triggers", []):
        v = (t.get("reach") or {}).get("verdict")
        if v is None:
            errs.append(f"L4 trigger without reachability: {t.get('text', '')[:60]}")
        elif v in ("unreachable", "expected"):
            errs.append(f"L4 trigger is '{v}' and must move to the Expected line or be dropped: {t.get('text', '')[:60]}")
    if not chair.get("expected"):
        errs.append("L4 chair.json has no 'expected' list (may be empty list with a reason)") if "expected" not in chair else None
    return errs


def main(memo, run_id):
    text = pathlib.Path(memo).read_text()
    vals = known(run_id)
    body = re.sub(r"\d{4}-\d{2}-\d{2}(T[\d:]+Z)?", " ", text)
    body = re.sub(r"\b(Q[1-4]|L[1-4]|TB[1-4]|[1-4]W|1D|4H|\d+w|\d+W|10Y|30Y|2Y|3M|1M|1Y|200D|100W|200W|0\.\d+ fib)\b", " ", body)
    body = re.sub(r"\b(19|20)\d{2}\b", " ", body)
    body = re.sub(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2}\b", " ", body)
    nums = re.findall(r"(?<![\w.])-?\d[\d,]*\.?\d*", body)
    bad = []
    for n in nums:
        try:
            x = float(n.replace(",", "").rstrip("."))
        except ValueError:
            continue
        if abs(x) <= 10 and float(x).is_integer():
            continue
        if not matches(x, vals):
            bad.append(n)
    missing = [s for s in SECTIONS if s.lower() not in text.lower()]
    lab = labelled(text, run_id)
    print(f"numbers checked: {len(nums)}; unmatched: {len(bad)}; labelled-check failures: {len(lab)}; missing sections: {len(missing)}")
    if bad:
        print("UNMATCHED:", sorted(set(bad)))
    for e in lab:
        print("FAIL", e)
    if missing:
        print("MISSING SECTIONS:", missing)
    ok = not bad and not missing and not lab
    print("PASS" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    sys.exit(0 if main(sys.argv[1], sys.argv[2]) else 1)
