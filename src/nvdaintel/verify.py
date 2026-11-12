"""Verifier: every number in the memo must trace to the fact sheet, a committee submission,
or the chair's derived list. Also checks required sections.

python -m nvdaintel.verify outputs/reviews/<run_id>.md <run_id>
"""
import json, re, sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]
SECTIONS = ["Final committee decision", "Bottom line", "Macro", "Technicals", "Fundamentals", "Relative strength",
            "Sentiment", "Narrative", "Kahneman", "System 1", "System 2", "Outlook", "Expected path",
            "Ladder Audit", "Strategy", "Thesis-break", "Committee", "Dashboard", "Sources"]


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
    for p in (ROOT / "committee/runs" / run_id).glob("*.json"):
        harvest(json.loads(p.read_text()), vals)
    for p in (ROOT / "config").glob("*.json"):
        harvest(json.loads(p.read_text()), vals)
    return vals


def matches(x, vals):
    for v in vals:
        for scale in (1, 1e-9, 1e-6, 1e-3):  # allow $bn / $m / thousands display
            vv = v * scale
            if abs(vv) < 1e-12:
                continue
            if abs(x - vv) <= max(0.051, abs(vv) * 0.0006) or abs(abs(x) - abs(vv)) <= 0.051:
                return True
    return False


def main(memo, run_id):
    text = pathlib.Path(memo).read_text()
    vals = known(run_id)
    body = re.sub(r"\d{4}-\d{2}-\d{2}", " ", text)          # ISO dates
    body = re.sub(r"\b(Q[1-4]|L[1-4]|TB[1-4]|B[1-4]|T[1-5]|1W|1D|4H|2w|13w|7w|52w|59w|10y|30y|2y|3m|1m|1y|10Y|30Y|2Y|3M|1M|1Y|20W|21W|50W|100W|200W|200D|0\.\d+ fib)\b", " ", body)
    body = re.sub(r"\b(19|20)\d{2}\b", " ", body)            # years
    body = re.sub(r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2}\b", " ", body)
    nums = [m for m in re.findall(r"(?<![\w.])-?\d[\d,]*\.?\d*", body)]
    bad = []
    for n in nums:
        try:
            x = float(n.replace(",", "").rstrip("."))
        except ValueError:
            continue
        if abs(x) <= 10 and float(x).is_integer():
            continue  # small counts / list numbers
        if not matches(x, vals):
            bad.append(n)
    missing = [s for s in SECTIONS if s.lower() not in text.lower()]
    print(f"numbers checked: {len(nums)}; unmatched: {len(bad)}; missing sections: {len(missing)}")
    if bad:
        print("UNMATCHED:", sorted(set(bad)))
    if missing:
        print("MISSING SECTIONS:", missing)
    ok = not bad and not missing
    print("PASS" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    sys.exit(0 if main(sys.argv[1], sys.argv[2]) else 1)
