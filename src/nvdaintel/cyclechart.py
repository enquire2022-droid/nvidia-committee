"""Market-psychology cycle with "you are here" from chair.json `cycle_placement` (owner-approved 24 Nov 2026).
python -m nvdaintel.cyclechart <run_id>   -> outputs/charts/<run_id>_cycle.png
The curve is a schematic (not price); the drawdown-clock panel on the right is NVDA's real history.
"""
import json, sys, pathlib, textwrap
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
ROOT = pathlib.Path(__file__).resolve().parents[2]
INK, MUTE, GRID, RED, BLUE = "#1f2328", "#6e7781", "#e6e8eb", "#cf222e", "#0969da"
STAGES = ["Hope", "Optimism", "Belief", "Thrill", "Euphoria", "Complacency", "Anxiety", "Denial", "Panic",
          "Capitulation", "Depression", "Relief rally"]
# schematic heights for one full cycle (x 0..11), Relief rally sits after Depression and before the next Hope
Y = [0.30, 0.45, 0.62, 0.82, 1.00, 0.88, 0.72, 0.62, 0.38, 0.12, 0.05, 0.20]


def stage_index(label):
    l = label.lower()
    for i, s in enumerate(STAGES):
        if s.lower() in l:
            return i
    return None


def main(run_id):
    ch = json.loads((ROOT / f"committee/runs/{run_id}/chair.json").read_text())
    cp = ch.get("cycle_placement") or {}
    add = ROOT / f"committee/runs/{run_id}/chair_cycle_addendum.json"   # chair addendum for runs that predate the rule
    if not cp and add.exists():
        cp = json.loads(add.read_text()).get("cycle_placement") or {}
    stage = cp.get("stage", "not ruled")
    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(17, 7.2), dpi=150, gridspec_kw={"width_ratios": [1.05, 1]})
    x = np.arange(len(STAGES)); xs = np.linspace(0, len(STAGES) - 1, 300)
    ys = np.interp(xs, x, Y)
    ys = np.convolve(np.pad(ys, 12, mode="edge"), np.ones(25) / 25, mode="valid")
    ax.plot(xs, ys, color=MUTE, lw=2.2)
    Yc = [float(np.interp(i, xs, ys)) for i in range(len(STAGES))]      # dots on the drawn curve
    for i, s in enumerate(STAGES):
        ax.annotate(s, (i, Yc[i]), xytext=(0, 9 if Yc[i] < 0.9 else -16), textcoords="offset points", ha="center", fontsize=9, color=INK)
        ax.plot([i], [Yc[i]], "o", color=MUTE, ms=4)
    k = stage_index(stage)
    if k is not None:
        ax.plot([k], [Yc[k]], "o", color=RED, ms=13, zorder=5)
        ax.annotate(f"YOU ARE HERE\n{stage}", (k, Yc[k]), xytext=(-170, 40), textcoords="offset points", fontsize=10.5, color=RED,
                    fontweight="bold", ha="center", arrowprops=dict(arrowstyle="->", color=RED))
    ax.set_ylim(-0.42, 1.15); ax.set_yticks([]); ax.set_xticks([])
    for s_ in ("top", "right", "left", "bottom"):
        ax.spines[s_].set_visible(False)
    agree = cp.get("agrees_with_probabilities")
    if isinstance(agree, dict):
        agree = agree.get("value")
    if cp.get("provisional"):
        stage = f"{stage} (provisional)"
    ax.set_title("Market-psychology cycle (schematic)\nChair: " + stage, loc="left", fontsize=12, fontweight="bold", color=INK)
    ax.text(0, -0.14, "\n".join(textwrap.wrap("What moves it: " + str(cp.get('confirm_or_revert') or cp.get('basis', '')), 115)[:6]) + f"\nAgrees with the probabilities: {agree}", fontsize=8, color=MUTE, va="top")
    img = ROOT / "outputs/shadow/drawdown_clock.png"
    if img.exists():
        ax2.imshow(plt.imread(str(img))); ax2.set_title("Drawdown clock (shadow, context)", loc="left", fontsize=10.5, color=INK)
    ax2.axis("off")
    fig.text(0.01, 0.005, "The cycle curve is a schematic, not a price path. Placement moves only on structure lines (shared rules, Cycle placement).",
             fontsize=7.5, color=MUTE)
    out = ROOT / f"outputs/charts/{run_id}_cycle.png"
    fig.tight_layout(rect=(0, 0.03, 1, 1)); fig.savefig(out, facecolor="white"); print(out)


if __name__ == "__main__":
    main(sys.argv[1])
