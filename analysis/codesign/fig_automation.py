"""Figure fig:automation (SenSys section 5): attempts to automate each labelling task, 2023-07 .. 2026-10.

One row per task (laser dot, laser calibration, head/tail), on a shared time axis. Each attempt is a bar from its
start to the date its outcome happened (a short mark where only one date is known; to the right edge where it is
still in use), filled by its outcome in analysis/codesign/automation_attempts.yaml's terms: deployed, reverted (used,
then replaced by human labels), dropped, evaluated (analysis only), unrecorded. Each fill differs in grey level and
pattern, so the key reads in black and white and for colour-blind readers (checked here: grayscale luminance, and a
deuteranopia simulation, Machado et al. 2009).

Attempts, from automation_attempts.yaml unless noted:
  laser dot          brightest spot 2023-07-13..09-21; 2D Gaussian fit, undated (placed at 2023-08 by the author's
                     ordering; no code found); neural network, one model (byte-identical weights) used three times:
                     CLI demo 2023-09-22 (outcome unrecorded), laser calibration 2024-09-13..2025-03-25 and Label
                     Studio pre-fill 2024-11-09..2024-11 (both reverted); Gaussian-mixture colour detector 2025-04-21
                     (no end date); fine-tuned Depth Anything 2025-08-29..11-30; RAW U-Net pre-fill from 2026-05-02,
                     auto-accept from 2026-07-27 (deployed). The 2023 guess-correction script is not a detection
                     method (the author's counting rule) and is not shown.
  laser calibration  template matching to the slate's scan (several keypoint-matching methods) 2024-09-15..2025-04-08;
                     slate pose by pattern alignment (fishsense-core's estimator: template search, ECC alignment,
                     solvePnP; fishsense-core 4808151 2026-08-01) scheduled as a Label Studio pre-fill 2026-08-02
                     (fishsense-lite b2978886) and taken off the schedule the same day for confident false fits on
                     pool frames (65582b6e, e32bd9bc; kept for on-demand use: no record of it running since);
                     checkerboard calibration automated in the lab 2026-09-08 (deployed); size constancy with SAM 3,
                     this paper, 2026-09-26 (evaluated).
  head/tail          the mask rule (PCA on the fish mask for the line of symmetry, later refined with morphology,
                     the author, 2026-10-28; refinement undated) with three mask providers: Fishial in the mobile app
                     2024-05-20..06-25 (deployed there, not in Lite labelling), Fishial as a Label Studio pre-fill
                     2024-11-12..2024-11 (reverted), SAM 3 2026-09-04..05 (replaced by SAM 3.1), SAM 3.1 from
                     2026-09-07 (deployed); a trained SimCC snout/fork keypoint model, not in the yaml: trained in
                     UCSD-E4E/2026-10-22_headtail_keypoints, ported to fishsense-core f5daad7 2026-10-23, evaluated
                     only (its docstring: better on reef, worse on pool fish models).

Writes analysis/codesign/figures/fig_automation.{pdf,png} at 7 in wide, no title, no metadata, and
fig_automation_{gray,deutan}.png previews (not for the paper).
Run: uv run python analysis/codesign/fig_automation.py
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import to_rgb
from matplotlib.patches import Patch, Rectangle

from fishsense_cscw.paths import REPO

OUT = REPO / "analysis/codesign/figures"
W, FS = 7.0, 7
INK, INK2, MUTED = "#0b0b0b", "#52514e", "#8a8984"
T0, T1, NOW = pd.Timestamp("2023-07-01"), pd.Timestamp("2026-11-01"), pd.Timestamp("2026-10-28")
MIN_DAYS, PAD_DAYS, LANE_H, BAR_H = 12, 8, 0.165, 0.105      # bar height and lane pitch in inches
DEUTAN = np.array([[0.367322, 0.860646, -0.227968], [0.280085, 0.672501, 0.047413], [-0.011820, 0.042940, 0.968881]])  # Machado 2009, severity 1

STYLE = {"deployed": dict(facecolor="#2f3f52", edgecolor="#2f3f52"),
         "reverted": dict(facecolor="#8a99ab", edgecolor="#5a6a7d"),
         "dropped": dict(facecolor="white", edgecolor="#2f3f52", hatch="xxxxxx"),
         "evaluated": dict(facecolor="#dbe2ea", edgecolor="#5a6a7d", hatch="......"),
         "unrecorded": dict(facecolor="white", edgecolor=INK2, linestyle=(0, (2, 1.2)))}
KEY = {"deployed": "deployed", "reverted": "reverted to human labels", "dropped": "dropped",
       "evaluated": "evaluated only", "unrecorded": "outcome not recorded"}

# (task, label, start, end or None, outcome); end NOW = still in use
ATTEMPTS = [
    ("laser dot", "brightest spot", "2023-07-13", "2023-09-21", "dropped"),
    ("laser dot", "Gaussian fit (undated)", "2023-08-15", None, "dropped"),
    ("laser dot", "neural network, demo", "2023-09-22", None, "unrecorded"),
    ("laser dot", "neural network, calibration", "2024-09-13", "2025-03-25", "reverted"),
    ("laser dot", "neural network, pre-fill", "2024-11-09", "2024-11-30", "reverted"),
    ("laser dot", "color-mixture detector", "2025-04-21", None, "dropped"),
    ("laser dot", "fine-tuned depth model", "2025-08-29", "2025-11-30", "dropped"),
    ("laser dot", "RAW U-Net", "2026-05-02", "now", "deployed"),
    ("laser calibration", "template matching to the scan", "2024-09-15", "2025-04-08", "dropped"),
    ("laser calibration", "pattern alignment", "2026-08-02", None, "reverted"),
    ("laser calibration", "checkerboard (lab)", "2026-09-08", "now", "deployed"),
    ("laser calibration", "size constancy (this paper)", "2026-09-26", None, "evaluated"),
    ("head/tail", "mask rule, Fishial (mobile app)", "2024-05-20", "2024-06-25", "deployed"),
    ("head/tail", "mask rule, Fishial pre-fill", "2024-11-12", "2024-11-30", "reverted"),
    ("head/tail", "mask rule, SAM 3", "2026-09-04", "2026-09-05", "dropped"),
    ("head/tail", "mask rule, SAM 3.1", "2026-09-07", "now", "deployed"),
    ("head/tail", "trained keypoint model", "2026-10-22", None, "evaluated"),
]
TASKS = ["laser dot", "laser calibration", "head/tail"]
LEFT_FROM = pd.Timestamp("2026-01-01")      # labels of late attempts go left of the bar, so they stay inside the axis


def lin(c):
    c = np.asarray(c, float)
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def luminance(c, m=None):
    v = lin(to_rgb(c))
    return float((np.clip(v @ m.T, 0, 1) if m is not None else v) @ [0.2126, 0.7152, 0.0722])


def previews(png):
    """Grayscale and deuteranopia versions of the rendered PNG, to look at (not for the paper)."""
    img = plt.imread(png)[..., :3]
    L = lin(img)
    g = L @ [0.2126, 0.7152, 0.0722]
    plt.imsave(OUT / "fig_automation_gray.png", np.clip(np.where(g <= 0.0031308, g * 12.92, 1.055 * g ** (1 / 2.4) - 0.055), 0, 1), cmap="gray", vmin=0, vmax=1)
    d = np.clip(L @ DEUTAN.T, 0, 1)
    plt.imsave(OUT / "fig_automation_deutan.png", np.clip(np.where(d <= 0.0031308, d * 12.92, 1.055 * d ** (1 / 2.4) - 0.055), 0, 1))


def main():
    # solid fills differ in lightness in grayscale and for deuteranopes; patterned and outlined fills differ in pattern
    for m in (None, DEUTAN):
        assert luminance(STYLE["deployed"]["facecolor"], m) + 0.2 < luminance(STYLE["reverted"]["facecolor"], m) < luminance(STYLE["evaluated"]["facecolor"], m) - 0.25

    plt.rcParams.update({"font.size": FS, "legend.fontsize": FS, "xtick.labelsize": FS, "ytick.labelsize": FS,
                         "axes.edgecolor": MUTED, "text.color": INK, "xtick.color": INK2, "ytick.color": INK2,
                         "hatch.linewidth": 0.5, "pdf.fonttype": 42, "savefig.bbox": "standard"})
    # lay out lanes in data units: a bar plus its label occupies [x0, x1]; each takes the first free lane of its row
    fig = plt.figure(figsize=(W, 1.0)); r = fig.canvas.get_renderer()
    days_per_in = (T1 - T0).days / (W * 0.86)
    rows = {}
    for task, label, s, e, outcome in ATTEMPTS:
        t0 = pd.Timestamp(s); t1 = NOW if e == "now" else pd.Timestamp(e) if e else t0
        t1 = max(t1, t0 + pd.Timedelta(days=MIN_DAYS))
        w = fig.text(0, 0, label, fontsize=FS).get_window_extent(r).width / fig.dpi * days_per_in
        left = t0 >= LEFT_FROM
        span = (t0 - pd.Timedelta(days=PAD_DAYS + w), t1) if left else (t0, t1 + pd.Timedelta(days=PAD_DAYS + w))
        lanes = rows.setdefault(task, [])
        k = next((i for i, occ in enumerate(lanes) if all(span[0] > b + pd.Timedelta(days=PAD_DAYS) or span[1] < a - pd.Timedelta(days=PAD_DAYS) for a, b in occ)), None)
        if k is None:
            lanes.append([]); k = len(lanes) - 1
        lanes[k].append(span)
        rows[task + "/items"] = rows.get(task + "/items", []) + [(label, t0, t1, outcome, k, left, e == "now")]
    plt.close(fig)

    n = {t: len(rows[t]) for t in TASKS}
    gap = 0.12                                                   # inches between task rows
    plot_h = sum(n.values()) * LANE_H + gap * (len(TASKS) - 1) + 0.06
    H = plot_h + 0.62                                            # axis labels and the key
    fig = plt.figure(figsize=(W, H))
    ax = fig.add_axes([0.13, 0.42 / H, 0.86, plot_h / H])
    ax.set_xlim(mdates.date2num(T0), mdates.date2num(T1)); ax.set_ylim(plot_h, 0)
    y, ticks = 0.03, []
    for t in TASKS:
        top = y
        for label, t0, t1, outcome, k, left, ongoing in rows[t + "/items"]:
            yc = top + (k + 0.5) * LANE_H
            x0, x1 = mdates.date2num(t0), mdates.date2num(t1)
            ax.add_patch(Rectangle((x0, yc - BAR_H / 2), x1 - x0, BAR_H, lw=0.6, zorder=2, **STYLE[outcome]))
            if ongoing:
                ax.annotate("", xy=(x1 + 9, yc), xytext=(x1, yc), arrowprops=dict(arrowstyle="-|>", color=STYLE[outcome]["edgecolor"], lw=0.6, mutation_scale=5))
            pad = PAD_DAYS * 0.6
            ax.text(x0 - pad if left else x1 + pad, yc, label, ha="right" if left else "left", va="center", fontsize=FS, color=INK2)
        y = top + n[t] * LANE_H
        ticks.append((top + y) / 2)
        if t != TASKS[-1]:
            ax.axhline(y + gap / 2, color="#e4e3df", lw=0.6, zorder=0)
            y += gap
    ax.set_yticks(ticks, TASKS); ax.tick_params(axis="y", length=0)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.xaxis.set_major_locator(mdates.MonthLocator(bymonth=[1, 7])); ax.xaxis.set_major_formatter(mdates.DateFormatter("%b %Y"))
    ax.xaxis.set_minor_locator(mdates.MonthLocator())
    ax.tick_params(axis="x", which="minor", length=2, color=MUTED); ax.tick_params(axis="x", which="major", length=3, color=MUTED)

    key = [Patch(label=KEY[k], lw=0.6, **v) for k, v in STYLE.items()]
    fig.legend(handles=key, loc="lower center", bbox_to_anchor=(0.5, 0.0), ncol=len(key), frameon=False,
               handlelength=1.6, handleheight=0.9, columnspacing=1.4, borderaxespad=0.1)

    OUT.mkdir(exist_ok=True)
    fig.savefig(OUT / "fig_automation.pdf", metadata={"Creator": None, "Producer": None, "CreationDate": None, "ModDate": None})
    fig.savefig(OUT / "fig_automation.png", dpi=300, metadata={"Software": None})
    previews(OUT / "fig_automation.png")
    print(f"wrote fig_automation ({W} x {H:.2f} in); lanes per row:", n, "; attempts:", len(ATTEMPTS))


if __name__ == "__main__":
    main()
