"""Tier-1 gate tests (15 Nov 2026), run on trial-run-1 data:  PYTHONPATH=src python -m pytest -q tests"""
import json, os, pathlib, shutil, subprocess, sys
import pandas as pd

R = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(R / "src"))
from nvdaintel import engines, scoring, verify  # noqa: E402

RUN = "2026-11-12-trial1"
ENV = dict(os.environ, PYTHONPATH=str(R / "src"))


def _verify(text):
    p = R / "outputs/reviews/_test.md"
    p.write_text(text)
    try:
        return subprocess.run([sys.executable, "-m", "nvdaintel.verify", str(p), RUN], capture_output=True, text=True, env=ENV, cwd=R).stdout
    finally:
        p.unlink()


def memo():
    return (R / f"outputs/reviews/{RUN}.md").read_text()


def test_stale_ladder_distance_caught():
    m = memo()
    bad = m.replace("| L1 | 162–164 | 1.0 | −0.8% |", "| L1 | 162–164 | 1.0 | −1.7% |")
    assert bad != m
    assert "L1 ladder L1" in _verify(bad)


def test_wrong_chair_row_caught():
    bad = memo().replace("| **Chair** | **33 / 30 / 37** |", "| **Chair** | **35 / 30 / 35** |")
    assert "L2 Chair row" in _verify(bad)


def test_free_text_numbers_not_sources():
    # 165.785 (pre-event price) appears only in submission free text / old notes: must not validate
    assert not verify.matches(165.785, verify.known(RUN))


def test_unreachable_trigger():
    r = engines.reach_trigger(260, "2026-11-25", 164.33, "2026-11-12")
    assert r["verdict"] == "unreachable"


def test_coverage_and_event_cutoff():
    d = json.loads((R / "inputs/readings.json").read_text())
    for v in d["pages"].values():
        v["read_utc"] = "2026-11-12T16:00:00Z"
    d["event_cutoff_utc"] = "2026-11-12T14:30:00Z"
    ok = engines.coverage(d, "2026-11-12")
    d["event_cutoff_utc"] = "2026-11-12T17:00:00Z"
    late = engines.coverage(d, "2026-11-12")
    assert late["stale"] > ok["stale"] and late["stale"] >= 10


def test_readings_template_archives(tmp_path):
    src = R / "inputs/readings.json"
    backup = tmp_path / "r.json"
    shutil.copy(src, backup)
    try:
        subprocess.run([sys.executable, "-m", "nvdaintel.committee", "readings-template"], env=ENV, cwd=R, check=True, capture_output=True)
        t = json.loads(src.read_text())
        assert len(t["pages"]) == 15 and all(v["status"] in ("pending", "failed") for v in t["pages"].values())
        assert (R / "inputs/readings_2026-11-12.json").exists()
    finally:
        (R / "inputs/readings_2026-11-12.json").unlink(missing_ok=True)
        shutil.copy(backup, src)


def test_scoring_rules():
    c = pd.Series([100, 104, 111, 95], index=pd.to_datetime(["2026-11-12", "2026-11-24", "2026-11-25", "2026-11-27"]))
    v, d = scoring.close_on_or_before(c, pd.Timestamp("2026-11-26"))
    assert v == 111 and str(d.date()) == "2026-11-25"          # Thanksgiving -> prior close
    assert scoring.outcome(100, 105, 5) == "range" and scoring.outcome(100, 105.1, 5) == "up"
    assert abs(scoring.brier({"up": 100, "range": 0, "down": 0}, "down") - 2) < 1e-9


def test_capex_monitor_flags():
    m = engines.capex_monitor()
    assert set(m["companies"]) == {"MSFT", "GOOGL", "AMZN", "META"} and m["status"] in ("no capex cut signal", "TB4 WATCH")
