"""Figure fig:timeline (SenSys section 4): how the input was shaped for people over the collection period.

Two histogram panels on one monthly axis, 2023-08 .. 2024-12, one bar per month at the same positions in both, so
each month's bar has the same height in both panels and only the split differs.
  top     dives per month by laser color, red or green.
  bottom  dives per month by slate pattern: H, tic-tac-toe, chevron, or pattern unknown (outline only).
Per dive (date, laser color, slate pattern, each with its source): analysis/codesign/timeline_dives.py, which
documents every rule; 481 dives, the pool and test deployments excluded (the author, 2026-10-27). Laser color is
from the dive's labels where it has them, else FishSense laser_colors (for 15 of 19 dives the unvalidated
automatic dot color), else the dives whose images an imageless duplicate holds. Counts per month:
analysis/codesign/results/timeline_counts_by_month.csv (timeline_counts.py).
Each class has a color AND a fill, so the figure reads in grayscale and for red-green colorblind readers (checked
here: grayscale luminance and a deuteranopia simulation, Machado et al. 2009). Laser: red solid dark red, green
light green with / hatching. Slate: neutral blue-grays, unrelated to the laser hues, at three lightness steps
(H dark, tic-tac-toe mid, chevron light with \\ hatching); unknown is an outline.

Writes analysis/codesign/figures/fig_timeline.{pdf,png} at 7 x 2 in, no title, no metadata, and
fig_timeline_{gray,deutan}.png previews (not for the paper).
Run: uv run python analysis/codesign/fig_timeline.py
"""
from __future__ import annotations

import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import to_rgb
from matplotlib.patches import Patch

from fishsense_cscw.paths import REPO

sys.path.insert(0, str(REPO / "analysis/codesign"))
import timeline_dives as T  # noqa: E402

OUT = REPO / "analysis/codesign/figures"
W, H, FS = 7.0, 2.0, 7
INK, INK2, MUTED, GRID = "#0b0b0b", "#52514e", "#8a8984", "#e4e3df"
RED, GREEN, GREEN_HATCH = "#a8322b", "#c4e8b8", "#3f7a37"
SLATE = {"H": "#2f3f52", "tic-tac-toe": "#8395aa", "chevron": "#dbe2ea"}
SLATE_HATCH = "#4f5f72"
MONTHS = pd.period_range("2023-08", "2024-12", freq="M")
BAR, YMAX = 0.78, 125
DEUTAN = np.array([[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.011820, 0.042940, 0.968881]])  # Machado 2009, severity 1

LASER = {"red": dict(facecolor=RED, edgecolor=RED, lw=0.6),
         "green": dict(facecolor=GREEN, edgecolor=GREEN_HATCH, hatch="//////", lw=0.6)}
PATTERN = {"H": dict(facecolor=SLATE["H"], edgecolor=SLATE["H"], lw=0.6),
           "tic-tac-toe": dict(facecolor=SLATE["tic-tac-toe"], edgecolor=SLATE["tic-tac-toe"], lw=0.6),
           "chevron": dict(facecolor=SLATE["chevron"], edgecolor=SLATE_HATCH, hatch="\\\\\\\\\\\\", lw=0.6),
           "unknown": dict(facecolor="white", edgecolor=INK2, lw=0.6)}


def lin(c):
    c = np.asarray(c, float)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def luminance(c):
    return float(lin(to_rgb(c)) @ [0.2126, 0.7152, 0.0722])


def deutan_luminance(c):
    return float(np.clip(lin(to_rgb(c)) @ DEUTAN.T, 0, 1) @ [0.2126, 0.7152, 0.0722])


def previews(png):
    """Grayscale and deuteranopia versions of the rendered PNG, to look at (not for the paper)."""
    img = plt.imread(png)[..., :3]
    L = lin(img)
    gray = (L @ [0.2126, 0.7152, 0.0722])
    gray = np.where(gray <= 0.0031308, gray * 12.92, 1.055 * gray ** (1 / 2.4) - 0.055)
    plt.imsave(OUT / "fig_timeline_gray.png", np.clip(gray, 0, 1), cmap="gray", vmin=0, vmax=1)
    d = np.clip(L @ DEUTAN.T, 0, 1)
    plt.imsave(OUT / "fig_timeline_deutan.png", np.clip(np.where(d <= 0.0031308, d * 12.92, 1.055 * d ** (1 / 2.4) - 0.055), 0, 1))


def stack(ax, per, styles):
    pos = np.arange(len(MONTHS))
    bottom = np.zeros(len(MONTHS))
    for k, st in styles.items():
        v = per[k].to_numpy(float)
        ax.bar(pos[v > 0], v[v > 0], width=BAR, bottom=bottom[v > 0], zorder=2, **st)   # empty bars would still draw an outline
        bottom += v
    ax.set_ylim(0, YMAX); ax.set_yticks([0, 50, 100])
    ax.set_ylabel("dives", rotation=0, ha="right", va="center", labelpad=4, color=INK2)
    ax.grid(axis="y", color=GRID, lw=0.6, zorder=1)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(MUTED)
    ax.tick_params(axis="y", length=0)
    return bottom


def main():
    # within each panel the classes differ in lightness (grayscale) and after a deuteranopia simulation
    assert luminance(RED) < 0.15 < luminance(GREEN) < 0.9, (luminance(RED), luminance(GREEN))
    assert abs(deutan_luminance(RED) - deutan_luminance(GREEN)) > 0.3
    for f in (luminance, deutan_luminance):
        l = [f(SLATE[k]) for k in ("H", "tic-tac-toe", "chevron")]
        assert l[0] + 0.15 < l[1] < l[2] - 0.3 and l[2] < 0.85, (f.__name__, l)

    D = T.load()
    D["pattern"] = D.pattern.fillna("unknown")
    assert D.laser.notna().all(), D[D.laser.isna()].dive_id.tolist()
    assert D.month.between(MONTHS[0], MONTHS[-1]).all()
    laser = D.groupby(["month", "laser"]).size().unstack(fill_value=0).reindex(index=MONTHS, columns=list(LASER), fill_value=0)
    slate = D.groupby(["month", "pattern"]).size().unstack(fill_value=0).reindex(index=MONTHS, columns=list(PATTERN), fill_value=0)

    plt.rcParams.update({"font.size": FS, "axes.labelsize": FS, "xtick.labelsize": FS, "ytick.labelsize": FS, "legend.fontsize": FS,
                         "axes.edgecolor": MUTED, "text.color": INK, "xtick.color": INK2, "ytick.color": INK2,
                         "hatch.linewidth": 0.6, "pdf.fonttype": 42, "savefig.bbox": "standard"})
    fig, (top, bot) = plt.subplots(2, 1, figsize=(W, H), sharex=True, layout="constrained")
    fig.get_layout_engine().set(h_pad=0.02, hspace=0.04)
    a = stack(top, laser, LASER)
    b = stack(bot, slate, PATTERN)
    assert (a == b).all() and a.sum() == len(D)
    top.tick_params(axis="x", which="both", length=0)
    bot.set_xticks(np.arange(len(MONTHS)), minor=True)
    major = [i for i, m in enumerate(MONTHS) if m.month in (4, 8, 12)]   # every fourth month, so the first and last are labeled
    assert major[0] == 0 and major[-1] == len(MONTHS) - 1
    bot.set_xticks(major, [MONTHS[i].strftime("%b %Y") for i in major])
    bot.tick_params(axis="x", which="minor", length=2, color=MUTED); bot.tick_params(axis="x", which="major", length=3, color=MUTED)
    bot.set_xlim(-0.6, len(MONTHS) - 0.4)

    key = [Patch(**LASER["red"], label="red laser"), Patch(**LASER["green"], label="green laser"),
           Patch(**PATTERN["H"], label="H slate"), Patch(**PATTERN["tic-tac-toe"], label="tic-tac-toe slate"),
           Patch(**PATTERN["chevron"], label="chevron slate"), Patch(**PATTERN["unknown"], label="pattern unknown")]
    fig.legend(handles=key, loc="outside upper center", ncol=len(key), frameon=False, handlelength=1.4, handleheight=0.9,
               columnspacing=1.2, borderaxespad=0.1)

    OUT.mkdir(exist_ok=True)
    fig.savefig(OUT / "fig_timeline.pdf", metadata={"Creator": None, "Producer": None, "CreationDate": None, "ModDate": None})
    fig.savefig(OUT / "fig_timeline.png", dpi=300, metadata={"Software": None})
    previews(OUT / "fig_timeline.png")
    print("wrote fig_timeline;", len(D), "dives; by laser:", D.laser.value_counts().to_dict(), "; by pattern:", D.pattern.value_counts().to_dict())


if __name__ == "__main__":
    main()
