"""Pathways chart: real daily path + committee branches with probabilities.
python -m nvdaintel.pathchart <run_id>
"""
import json, sys, pathlib, datetime as dt
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
ROOT = pathlib.Path(__file__).resolve().parents[2]

def D(s): return dt.datetime.strptime(s, "%Y-%m-%d")

def main(run_id):
    px = json.loads((ROOT / "data/nvda_daily.json").read_text())
    ch = json.loads((ROOT / f"committee/runs/{run_id}/chair.json").read_text())
    t = [dt.datetime.fromtimestamp(x, dt.timezone.utc).replace(tzinfo=None) for x in px["t"]]
    c = np.array(px["c"]); o, h, l = px["o"][-1], px["h"][-1], px["l"][-1]
    P = ch["probabilities"]; tq, nq = P["this_quarter"], P["next_quarter"]
    now = t[-1]; p0 = ch["price_at_call"]

    fig, ax = plt.subplots(figsize=(15, 8.2), dpi=150)
    fig.patch.set_facecolor("white")
    INK, MUTE, GRID = "#1f2328", "#6e7781", "#e6e8eb"
    UP, RNG, DN = "#1a7f37", "#9a6700", "#cf222e"

    # zones and levels
    end = D("2027-03-31")
    xr = (t[0], end + dt.timedelta(days=40))
    ax.axhspan(179.92, 185.22, color="#8250df", alpha=0.08, lw=0)
    ax.text(xr[0] + dt.timedelta(days=3), 182.6, "Unfilled gap 179.92–185.22", fontsize=8, color="#8250df", va="center")
    for lo, hi, name in [(162, 164, "L1"), (154, 157, "L2"), (141, 145, "L3"), (124, 128, "L4")]:
        ax.axhspan(lo, hi, xmin=0.0, xmax=1, color="#0969da", alpha=0.06, lw=0)
        ax.text(D("2026-11-08"), (lo + hi) / 2, f"{name} {lo}–{hi} (proposed, paused)", fontsize=7.5, color="#0969da", ha="right", va="center")
    levels = [(243.37, "ATH 243.37", MUTE, ":"), (186, "Breakout trigger: weekly close > 186", UP, "--"),
              (175.09, "100W SMA 175.09", MUTE, "-."), (164.27, "Apr-2026 swing low 164.27", MUTE, ":"),
              (148.80, "Today's low 148.80", DN, "--"), (123.61, "200W SMA 123.61", MUTE, "-.")]
    for y, lab, col, ls in levels:
        ax.axhline(y, color=col, lw=0.9, ls=ls, alpha=0.8)
        ax.text(xr[0] + dt.timedelta(days=3), y + 1.2, lab, fontsize=8, color=col)

    # actual path
    ax.plot(t, c, color=INK, lw=1.6, label="NVDA daily close")
    ax.vlines(now, l, h, color=INK, lw=1.2)
    ax.plot([now], [l], marker="v", color=DN, ms=7)
    ax.annotate(f"Nov 12: open {o:.2f}, low {l:.2f},\nnow ~{c[-1]:.2f} (CEO resignation 8-K)", (now, l),
                xytext=(-420, -30), textcoords="offset points", fontsize=8.5, color=INK,
                arrowprops=dict(arrowstyle="-", color=MUTE, lw=0.8))
    ath_i = int(np.argmax(px["h"])); ax.plot([t[ath_i]], [px["h"][ath_i]], marker="o", color=MUTE, ms=4)

    # branches (anchor points: dates -> price), hypotheses drawn by the chair, not forecasts of exact prices
    def path(pts, col, lw, alpha, ls="-"):
        xs = [now] + [D(d) for d, _ in pts]; ys = [p0] + [v for _, v in pts]
        xx = mdates.date2num(xs); fine = np.linspace(xx[0], xx[-1], 200)
        ax.plot(mdates.num2date(fine), np.interp(fine, xx, ys), color=col, lw=lw, alpha=alpha, ls=ls)
        return xs, ys
    path([("2026-11-18", 172), ("2026-11-25", 178), ("2026-12-15", 187), ("2026-12-31", 190), ("2027-02-15", 196), ("2027-03-31", 200)], UP, 2.4, 0.95)
    path([("2026-11-18", 158), ("2026-11-25", 166), ("2026-12-10", 156), ("2026-12-31", 165), ("2027-02-15", 160), ("2027-03-31", 168)], RNG, 2.4, 0.95)
    path([("2026-11-18", 152), ("2026-11-25", 146), ("2026-12-15", 142), ("2026-12-31", 140), ("2027-02-15", 132), ("2027-03-31", 128)], DN, 2.4, 0.95)
    # uncertainty fan
    fx = mdates.date2num([now, D("2026-12-31"), end])
    fan_hi = [p0, 192, 202]; fan_lo = [p0, 138, 126]
    fine = np.linspace(fx[0], fx[-1], 200)
    ax.fill_between(mdates.num2date(fine), np.interp(fine, fx, fan_lo), np.interp(fine, fx, fan_hi), color="#8c959f", alpha=0.08, lw=0)

    # probability labels at quarter ends
    for d, pr, ys in [("2026-12-31", tq, (190, 165, 140)), ("2027-03-31", nq, (200, 168, 128))]:
        x = D(d)
        ax.axvline(x, color=MUTE, lw=0.8, ls=":")
        lab = "Q4 close 2026-12-31" if d.startswith("2026") else "Q1 close 2027-03-31"
        ax.text(x, 246, lab, fontsize=8.5, color=MUTE, ha="center")
        for y, k, col, name in [(ys[0], "up", UP, "Up  > 180.76"), (ys[1], "range", RNG, "Range"), (ys[2], "down", DN, "Down < 147.90")]:
            ax.text(x + dt.timedelta(days=3), y, f"{pr[k]}%  {name}", fontsize=9.5, color=col, fontweight="bold", va="center",
                    bbox=dict(boxstyle="round,pad=0.25", fc="white", ec=col, lw=0.8))

    # 2-week bucket
    x2 = D("2026-11-25"); w = P["next_2_weeks"]
    ax.plot([x2, x2], [156.11, 172.55], color=INK, lw=3, alpha=0.35, solid_capstyle="butt")
    ax.text(x2 + dt.timedelta(days=6), 236, f"2-week (close 2026-11-25)\nUp {w['up']}% > 172.55\nRange {w['range']}%\nDown {w['down']}% < 156.11",
            fontsize=8.5, color=INK, ha="left", va="top", bbox=dict(boxstyle="round,pad=0.35", fc="white", ec=GRID))

    # checkpoints and catalysts
    cps = [("2026-11-13", "1"), ("2026-11-18", "2"), ("2026-11-25", "3"), ("2026-12-10", "4"), ("2026-12-31", "5")]
    for d, n in cps:
        ax.annotate(n, (D(d), 112), ha="center", va="center", fontsize=8.5, color="white", fontweight="bold",
                    bbox=dict(boxstyle="circle,pad=0.25", fc=INK, ec=INK))
    ax.text(D("2026-11-05"), 112, "Checkpoints", fontsize=8, color=INK, ha="right", va="center")
    cats = [("2026-11-17", "Earnings\n(after close)"), ("2026-11-20", "Opex"), ("2026-11-24", "Huang testimony\n(before Thanksgiving)"),
            ("2026-12-09", "FOMC"), ("2026-12-10", "CPI")]
    for d, lab in cats:
        ax.axvline(D(d), ymin=0.0, ymax=0.05, color="#0969da", lw=1.2)
    ax.text(D("2026-05-15"), 99, "Catalysts (blue ticks):  Nov 17 earnings (after close)  ·  Nov 20 opex  ·  Huang testimony before Nov 26  ·  Dec 9 FOMC  ·  Dec 10 CPI",
            fontsize=8, color="#0969da", va="center")
    ax.text(D("2027-02-25"), 236, "Most-likely path (34%):\nrange 148.80–175.09 into year-end", fontsize=8.5, color=RNG, ha="center",
            bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=RNG, lw=0.8))
    ax.text(D("2026-07-15"), 249, "TB2 FIRED — all buying paused", fontsize=10, color=DN, fontweight="bold", ha="center",
            bbox=dict(boxstyle="round,pad=0.35", fc="#ffebe9", ec=DN, lw=0.8))

    ax.set_xlim(*xr); ax.set_ylim(92, 252)
    ax.set_ylabel("NVDA price (USD)", color=INK)
    ax.xaxis.set_major_locator(mdates.MonthLocator()); ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.grid(axis="y", color=GRID, lw=0.6); ax.set_axisbelow(True)
    for s in ("top", "right"): ax.spines[s].set_visible(False)
    ax.tick_params(colors=MUTE, labelsize=8.5)
    ax.set_title(f"NVDA — actual path and committee pathways to Q1 2027 (run {run_id}, call price {p0})", loc="left", fontsize=12.5, color=INK, fontweight="bold")
    fig.text(0.01, 0.005, "Branch lines are scenario sketches through the checkpoints, not price targets. Probabilities = chair, uncalibrated; quarter buckets ±10% vs 164.33. "
             "Ladder zones L1–L4 are proposed and paused. Source: TradingView daily closes; NVIDIA Committee trial run 1.", fontsize=7.5, color=MUTE)
    out = ROOT / f"outputs/charts/{run_id}_pathways.png"
    fig.tight_layout(rect=(0, 0.02, 1, 1)); fig.savefig(out, facecolor="white")
    print(out)

if __name__ == "__main__":
    main(sys.argv[1])
