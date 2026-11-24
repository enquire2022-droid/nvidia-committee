"""Pathways chart: real daily path + the chair's branches with probabilities. Everything shown comes from
data/nvda_daily.json, committee/runs/<run_id>/chair.json and config/ladder.json — nothing typed in here.
python -m nvdaintel.pathchart <run_id>
"""
import json, re, sys, pathlib, datetime as dt
import numpy as np
import pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
ROOT = pathlib.Path(__file__).resolve().parents[2]
INK, MUTE, GRID = "#1f2328", "#6e7781", "#e6e8eb"
UP, RNG, DN, BLUE = "#1a7f37", "#9a6700", "#cf222e", "#0969da"


def D(s):
    return pd.Timestamp(s).to_pydatetime()


def _window_end(w):
    m = re.findall(r"\d{4}-\d{2}-\d{2}", str(w))
    return D(m[-1]) if m else None


def main(run_id):
    px = json.loads((ROOT / "data/nvda_daily.json").read_text())
    ch = json.loads((ROOT / f"committee/runs/{run_id}/chair.json").read_text())
    lad = json.loads((ROOT / "config/ladder.json").read_text())
    t = [dt.datetime.fromtimestamp(x, dt.timezone.utc).replace(tzinfo=None) for x in px["t"]]
    keep = [i for i, x in enumerate(t) if x >= t[-1] - dt.timedelta(days=190)]
    t = [t[i] for i in keep]; c = np.array([px["c"][i] for i in keep]); lows = [px["l"][i] for i in keep]
    P, p0 = ch["probabilities"], ch["price_at_call"]
    from decimal import Decimal, ROUND_HALF_UP
    rd = lambda x: float(Decimal(str(x)).quantize(Decimal("0.01"), ROUND_HALF_UP))
    b = Decimal(str(p0))
    up2, dn2, upq, dnq = (rd(b * Decimal(m)) for m in ("1.05", "0.95", "1.10", "0.90"))
    as_of = pd.Timestamp(ch["as_of"])
    r2 = as_of + pd.Timedelta(days=14)
    while r2.weekday() >= 5 or (r2.month == 11 and r2.day in (26,)):  # weekend / Thanksgiving -> prior session
        r2 -= pd.Timedelta(days=1)
    q4, q1 = D("2026-12-31"), D("2027-03-31")
    now = t[-1]

    fig, ax = plt.subplots(figsize=(15, 8.2), dpi=150)
    xr = (t[0], q1 + dt.timedelta(days=45))
    # ladder zones (proposed / paused)
    def _fired(v):
        st = str(v.get("status", v) if isinstance(v, dict) else v).strip().upper()
        return st.startswith("FIRED")
    fired = [k for k, v in ch.get("tb_rulings", {}).items() if _fired(v)]
    status = "paused" if fired else "proposed"
    zones = ch.get("ladder_proposed") or lad["orders"]
    zlabel = "proposed, dormant" if ch.get("ladder_proposed") else status
    for o in zones:
        ax.axhspan(o["zone_low"], o["zone_high"], color=BLUE, alpha=0.06, lw=0)
        ax.text(t[-1] - dt.timedelta(days=4), (o["zone_low"] + o["zone_high"]) / 2, f"{o['id']} {o['zone_low']:g}–{o['zone_high']:g} w{o['weight']:g} ({zlabel})",
                fontsize=7.5, color=BLUE, ha="right", va="center")
    # key levels from chair.json
    shown = []
    for kl in ch.get("key_levels", [])[:10]:
        y = float(kl["level"])
        if any(abs(y - z) / z < 0.012 for z in shown):
            continue          # skip labels that would overprint a nearby level
        shown.append(y)
        col = UP if y > p0 * 1.04 else DN if y < p0 * 0.96 else MUTE
        ax.axhline(y, color=col, lw=0.8, ls=":", alpha=0.75)
        ax.text(t[0] + dt.timedelta(days=2), y + 0.9, f"{y:g}  {kl.get('why', '')[:58]}", fontsize=7.3, color=col)
    # scoring thresholds
    for y, lab, col in [(upq, f"quarter 'up' line {upq:.2f} (+10%)", UP), (dnq, f"quarter 'down' line {dnq:.2f} (−10%)", DN)]:
        ax.axhline(y, color=col, lw=0.9, ls="--", alpha=0.5)
        ax.text(q1 + dt.timedelta(days=2), y - 2.2, lab, fontsize=7.2, color=col)

    # actual path
    ax.plot(t, c, color=INK, lw=1.6)
    i_low = int(np.argmin(lows)); ax.plot([t[i_low]], [lows[i_low]], marker="v", color=DN, ms=6)
    ax.annotate(f"low {lows[i_low]:.2f}", (t[i_low], lows[i_low]), xytext=(-60, -14), textcoords="offset points", fontsize=8, color=DN)
    ax.plot([now], [p0], marker="o", color=INK, ms=5)
    ax.annotate(f"call {p0:.2f}\n({ch['as_of']})", (now, p0), xytext=(-70, 18), textcoords="offset points", fontsize=8, color=INK)

    # branches: sketches through the scoring lines (not targets)
    def path(pts, col):
        xs = [now] + [D(d) if isinstance(d, str) else d for d, _ in pts]; ys = [p0] + [v for _, v in pts]
        xx = mdates.date2num(xs); fine = np.linspace(xx[0], xx[-1], 200)
        ax.plot(mdates.num2date(fine), np.interp(fine, xx, ys), color=col, lw=2.4, alpha=0.95)
    path([(r2, up2 * 1.01), (q4, upq * 1.03), (q1, upq * 1.08)], UP)
    path([(r2, p0 * 0.99), ((as_of + pd.Timedelta(days=30)).to_pydatetime(), p0 * 0.965), (q4, p0 * 1.01), (q1, p0 * 1.02)], RNG)
    path([(r2, dn2 * 0.99), (q4, dnq * 0.97), (q1, dnq * 0.92)], DN)
    fx = mdates.date2num([now, q4, q1]); fine = np.linspace(fx[0], fx[-1], 200)
    ax.fill_between(mdates.num2date(fine), np.interp(fine, fx, [p0, dnq * 0.95, dnq * 0.9]), np.interp(fine, fx, [p0, upq * 1.06, upq * 1.12]),
                    color="#8c959f", alpha=0.08, lw=0)
    for x, pr, ys, lab in [(q4, P["this_quarter"], (upq * 1.03, p0 * 1.01, dnq * 0.97), "Q4 close 2026-12-31"),
                           (q1, P["next_quarter"], (upq * 1.08, p0 * 1.02, dnq * 0.92), "Q1 close 2027-03-31")]:
        ax.axvline(x, color=MUTE, lw=0.8, ls=":")
        ax.text(x, ax.get_ylim()[1] if False else 0, "")
        ax.annotate(lab, (x, 1.0), xycoords=("data", "axes fraction"), ha="center", va="bottom", fontsize=8.3, color=MUTE)
        for y, k, col, name in [(ys[0], "up", UP, f"Up (> {upq:.2f})"), (ys[1], "range", RNG, "Range"), (ys[2], "down", DN, f"Down (< {dnq:.2f})")]:
            ax.text(x + dt.timedelta(days=3), y, f"{pr[k]}%  {name}", fontsize=9.3, color=col, fontweight="bold", va="center",
                    bbox=dict(boxstyle="round,pad=0.25", fc="white", ec=col, lw=0.8))
    w = P["next_2_weeks"]
    ax.plot([r2, r2], [dn2, up2], color=INK, lw=3, alpha=0.35, solid_capstyle="butt")
    ax.annotate(f"2-week score, close {r2.date()}\nUp {w['up']}% (> {up2:.2f})\nRange {w['range']}%\nDown {w['down']}% (< {dn2:.2f})",
                (r2, 0.97), xycoords=("data", "axes fraction"), ha="left", va="top", fontsize=8.3, color=INK,
                bbox=dict(boxstyle="round,pad=0.35", fc="white", ec=GRID))

    # checkpoints as ticks at their window end, with status
    ep = ch.get("expected_path", {})
    seen = {}
    for cp in ep.get("checkpoints", []):
        x = _window_end(cp.get("window"))
        if not x:
            continue
        k = x.date(); seen[k] = seen.get(k, -1) + 1
        x = x - dt.timedelta(days=5 * seen[k])   # nudge checkpoints sharing a window end
        stc = {"confirmed": UP, "invalidated": DN}.get(str(cp.get("status", "")).lower(), INK)
        ax.annotate(str(cp.get("n")), (x, 0.06), xycoords=("data", "axes fraction"), ha="center", va="center", fontsize=8,
                    color="white", fontweight="bold", bbox=dict(boxstyle="circle,pad=0.25", fc=stc, ec=stc))
    ax.annotate("checkpoints (window end)", (now - dt.timedelta(days=4), 0.06), xycoords=("data", "axes fraction"), ha="right", va="center", fontsize=7.5, color=INK)
    if ep.get("hypothesis"):
        hyp = ep['hypothesis'].split(":")[0].split(".")[0]
        ax.annotate(f"Most-likely path ({ep.get('probability')}%): {hyp}", (0.01, 0.97), xycoords="axes fraction",
                    fontsize=8.3, color=RNG, va="top", bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=RNG, lw=0.8))
    if fired:
        ax.annotate(f"{', '.join(fired)} FIRED — buying paused", (0.01, 0.91), xycoords="axes fraction", fontsize=9.5, color=DN, fontweight="bold",
                    va="top", bbox=dict(boxstyle="round,pad=0.3", fc="#ffebe9", ec=DN, lw=0.8))
    def _dated(c_):
        try:
            return pd.Timestamp(c_["date"])
        except Exception:
            return None                      # e.g. "2027-02 (late, not confirmed)": no tick
    ch["catalysts"] = [c_ for c_ in ch.get("catalysts", []) if _dated(c_) is not None]
    for cat in ch.get("catalysts", []):
        x = D(cat["date"]); ax.axvline(x, ymin=0, ymax=0.025, color=BLUE, lw=1.2)
    if ch.get("catalysts"):
        short = lambda n: n.split("(")[0].split(";")[0].split(" - ")[0].strip()[:28]
        ax.annotate("Catalysts: " + "  ·  ".join(f"{pd.Timestamp(c_['date']):%b %d} {short(c_['name'])}" for c_ in ch["catalysts"][:7]),
                    (0.01, 0.015), xycoords="axes fraction", fontsize=7.6, color=BLUE)

    lo = min(min(c), dnq * 0.85, min(o["zone_low"] for o in zones)) - 5
    hi = max(max(c), upq * 1.15) + 8
    ax.set_xlim(*xr); ax.set_ylim(lo, hi)
    ax.set_ylabel("NVDA price (USD)", color=INK)
    ax.xaxis.set_major_locator(mdates.MonthLocator()); ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.grid(axis="y", color=GRID, lw=0.6); ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(colors=MUTE, labelsize=8.5)
    ax.set_title(f"NVDA — actual path and committee pathways (run {run_id}, call {p0})", loc="left", fontsize=12.5, color=INK, fontweight="bold", pad=18)
    fig.text(0.01, 0.005, f"Branch lines are sketches through the scoring lines, not targets. Probabilities: independent chair ({ch.get('label', 'uncalibrated')}). "
             "Dotted lines = chair key levels; dashed = quarter scoring lines. Source: TradingView daily closes; NVIDIA Committee.", fontsize=7.3, color=MUTE)
    out = ROOT / f"outputs/charts/{run_id}_pathways.png"
    fig.tight_layout(rect=(0, 0.02, 1, 1)); fig.savefig(out, facecolor="white")
    print(out)


if __name__ == "__main__":
    main(sys.argv[1])
