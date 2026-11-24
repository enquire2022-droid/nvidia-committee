import json, pathlib, subprocess, sys, os
R = pathlib.Path(__file__).resolve().parents[1]
ENV = {**os.environ, "PYTHONPATH": str(R / "src")}
sys.path.insert(0, str(R / "src"))


def test_ladder_triggers_shape(tmp_path, monkeypatch):
    from nvdaintel import engines
    monkeypatch.setattr(engines, "DRIFT_LOG", tmp_path / "drift.jsonl")
    lad = json.loads((R / "config/ladder.json").read_text())
    t = engines.ladder_triggers(lad, "2026-11-24", 124.86, 13.22, {"breaks": []}, log=True)
    assert set(t["details"]) == {"A_anchor_drift", "B_structure_break", "C_regime_change", "D_shock_or_thesis_break"}
    assert "D" in t["fired"]                         # the 2026-11-23 +31.5% day is a >4 sd shock
    assert not t["details"]["B_structure_break"]["established"]   # 124.50 low is under 4 weeks old


def test_drift_needs_two_weeks(tmp_path, monkeypatch):
    from nvdaintel import engines
    monkeypatch.setattr(engines, "DRIFT_LOG", tmp_path / "drift.jsonl")
    lad = json.loads((R / "config/ladder.json").read_text())
    t1 = engines.ladder_triggers(lad, "2026-11-24", 120.0, 13.22, {"breaks": []})   # D0 mid 127: -5.5% drift, first week
    assert "A" not in t1["fired"]
    t2 = engines.ladder_triggers(lad, "2026-12-01", 120.0, 13.22, {"breaks": []})   # second completed week, same direction
    assert "A" in t2["fired"]


def test_shadow_history_runs():
    out = subprocess.run([sys.executable, "-m", "nvdaintel.shadow", "history", "2026-11-24-review"], env=ENV, cwd=R, capture_output=True, text=True)
    assert out.returncode == 0
    h = json.loads((R / "outputs/shadow/2026-11-24-review_history_check.json").read_text())
    assert {c["window"] for c in h["calls"]} == {"next_2_weeks", "this_quarter", "next_quarter"}
