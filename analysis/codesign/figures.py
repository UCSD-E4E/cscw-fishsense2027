"""Figures for the SenSys 2027 co-design paper (task 4), built only from committed files.

  codesign_timeline      design revisions over time by component, coloured by driver (timeline.yaml)
  codesign_frames_fish   share of fish with a length within 10% of manual vs frames taken (3b)
  codesign_spread        calibration angle error vs slate size spread, 0.05 deg target marked (3c)
  codesign_redgreen      green - red difference in dot misses and coverage under each control (3d)
  design_rules.tex       LaTeX design-rules table from design_rules.yaml + claims.yaml (evidence level, section)

SenSys figure set, one per paper section (the rest of the set reuses figures above and in figures/):
  sensys_system          s2  each stage as designed for a person, as redesigned for a machine, and what the
                             machine needed from the rest of the system
  sensys_calibration     s5  (a) slate size measures scored against tape, labelled vs label-free;
                             (b) calibration error vs slate size spread
  sensys_capture         s7  (a) frames per fish divers delivered; (b) what each extra frame buys
  sensys_labelling       s8  (a) a person's seconds per label, from scratch vs accepting a model pre-fill;
                             (b) what labellers do with a pre-fill (unchanged / nudged / replaced)

Style, colours and ACM column widths come from figures/make_figures.py. Output goes to
analysis/codesign/figures/ (PDF and PNG, no timestamps, so rebuilds are byte-identical).
Run: uv run --with pyyaml python analysis/codesign/figures.py
"""
from __future__ import annotations

import re, sys
from pathlib import Path

import matplotlib.dates as mdates
import numpy as np
import pandas as pd
import yaml
from matplotlib.transforms import Bbox

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "figures"))
import make_figures as MF  # noqa: E402  (rcParams, palette, widths)

plt = MF.plt
BLUE, ORANGE, AQUA, INK, INK2, MUTED, GRID = MF.BLUE, MF.ORANGE, MF.AQUA, MF.INK, MF.INK2, MF.MUTED, MF.GRID
ONE, TWO = MF.ONE, MF.TWO
OUT = HERE / "figures"
RES = HERE / "results"
DRIVER = {"human": ("human", BLUE), "machine": ("machine", ORANGE), "other": ("other (durability, failure)", AQUA),
          "unknown": ("no record of why", MUTED)}


def save(fig, name):
    OUT.mkdir(exist_ok=True)
    fig.savefig(OUT / f"{name}.pdf", metadata={"CreationDate": None, "ModDate": None})
    fig.savefig(OUT / f"{name}.png", metadata={"Software": None})
    plt.close(fig); print("wrote", name)


def _dates(text):
    """(start, end) from timeline.yaml's free-text date, or None when no date is given."""
    found = re.findall(r"(\d{4}-\d{2}(?:-\d{2})?)", str(text))
    if not found or str(text).startswith(("before", "unknown", "throughout")):
        return None
    ts = [pd.Timestamp(f + ("-15" if len(f) == 7 else "")) for f in found]
    return ts[0], ts[-1]


def codesign_timeline():
    T = yaml.safe_load(open(HERE / "timeline.yaml"))
    lanes = ["hardware", "protocol", "calibration", "labeling", "pipeline"]
    names = {"labeling": "labelling"}
    GAP = 2.0                                   # vertical distance between lanes
    fig, ax = plt.subplots(figsize=(TWO, 4.8))
    ax.axvspan(pd.Timestamp("2023-08-01"), pd.Timestamp("2025-01-17"), color=GRID, alpha=0.55, lw=0, zorder=0)
    ax.text(pd.Timestamp("2023-08-10"), (len(lanes) - 1) * GAP + 1.1, "dives captured (2023-08 .. 2025-01)",
            fontsize=6.5, color=INK2, va="top")
    ax.set_xlim(pd.Timestamp("2023-06-01"), pd.Timestamp("2026-12-31"))
    ax.set_ylim(-1.1, (len(lanes) - 1) * GAP + 1.15)
    undated, events = [], []
    for li, lane in enumerate(lanes):
        y = (len(lanes) - 1 - li) * GAP
        for e in T:
            if e["component"] != lane or str(e["driver"]).startswith("n/a"):
                continue
            d = _dates(e["date"])
            (events.append((y, d, e)) if d else undated.append(e["label"]))
    r = fig.canvas.get_renderer()
    placed, marks, drawn = [], [], []
    for y0, (t0, t1), e in sorted(events, key=lambda x: (x[0], x[1][0])):
        # markers within 12 days of one already drawn in the lane are nudged up/down so neither hides
        near = sum(1 for (yy, tt) in marks if yy == y0 and abs((tt - t0).days) <= 12)
        y = y0 + [0, 0.17, -0.17, 0.34][min(near, 3)]
        marks.append((y0, t0))
        lab, col = DRIVER.get(str(e["driver"]), DRIVER["unknown"])
        planned = "not deployed" in str(e["date"]) or "analysis only" in str(e["date"])
        if (t1 - t0).days > 20:
            ax.plot([t0, t1], [y, y], color=col, lw=4, alpha=0.55, solid_capstyle="butt", zorder=2)
        sc = ax.scatter([t0], [y], s=34, zorder=3, color="white" if planned else col, edgecolor=col, linewidth=1.3)
        drawn.append((t0, y, e))
    fig.canvas.draw()
    for t0, y, _ in drawn:                       # marker boxes, so labels never sit on a marker
        cx, cy = ax.transData.transform((mdates.date2num(t0), y))
        placed.append(Bbox([[cx - 9, cy - 9], [cx + 9, cy + 9]]))
    for t0, y, e in drawn:
        late = t0 >= pd.Timestamp("2026-03-01")
        text = e["label"]
        prefer = ("right", "left", "center") if late else ("left", "right", "center")
        for dy, ha in [(dy, ha) for dy in (0.28, -0.28, 0.5, -0.5, 0.72, -0.72, 0.94, 1.16, 1.38, 1.6) for ha in prefer]:
            tx = ax.text(t0, y + dy, text, fontsize=5.8, color=INK2, ha=ha, va="center")
            bb = tx.get_window_extent(r).expanded(1.04, 1.25)
            if not any(bb.overlaps(q) for q in placed):
                placed.append(bb)
                ax.plot([t0, t0], [y, y + dy * 0.8], color=MUTED, lw=0.5, zorder=1)
                break
            tx.remove()
        else:
            raise RuntimeError(f"no room for label {text!r}")
    ax.set_yticks([(len(lanes) - 1 - i) * GAP for i in range(len(lanes))], [names.get(l, l) for l in lanes])
    ax.grid(axis="y", visible=False)
    for k, (lab, col) in DRIVER.items():
        ax.scatter([], [], s=30, color=col, label=lab)
    ax.scatter([], [], s=30, color="white", edgecolor=MUTED, label="not deployed")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.07), ncol=5, frameon=False, fontsize=6.5, handletextpad=0.2)
    ax.text(0.0, -0.17, "not shown (no date recorded): " + "; ".join(undated), transform=ax.transAxes,
            fontsize=5.8, color=INK2, va="top")
    ax.set_title("Design revisions by component, coloured by the recorded reason", loc="left", color=INK2)
    save(fig, "codesign_timeline")


def codesign_frames_fish():
    R = pd.read_csv(RES / "frames_per_fish.csv")
    R = R[R.design.str.startswith("fixed set")]
    fig, ax = plt.subplots(figsize=(ONE, 2.3))
    for src, col, dx in (("predicted", BLUE, -0.05), ("labelled", ORANGE, 0.05)):
        g = R[R.clusters == src].sort_values("k")
        ax.errorbar(g.k + dx, g.within10 * 100, yerr=[(g.within10 - g.within10_lo) * 100, (g.within10_hi - g.within10) * 100],
                    color=col, marker="o", ms=4, lw=1.6, capsize=2, elinewidth=0.8,
                    label=f"{src} clusters ({int(g.fish.iloc[0])} fish)")
        for k, v in zip(g.k, g.within10):
            if src == "predicted":
                ax.text(k - 0.12, v * 100 + 2.5, f"{v * 100:.0f}%", fontsize=6.5, color=col, ha="right")
    ax.set_xticks([1, 2, 3, 4]); ax.set_xlim(0.6, 4.4); ax.set_ylim(40, 102)
    ax.set_xlabel("frames taken of the fish"); ax.set_ylabel("fish with a length within 10%, %")
    ax.set_title("Each extra frame of a fish (fish with ≥ 4 frames)", loc="left", color=INK2)
    ax.legend(loc="lower right", frameon=False, fontsize=6.5)
    save(fig, "codesign_frames_fish")


def codesign_spread():
    B = pd.read_csv(RES / "calibration_spread_bins.csv")
    B = B[B.frames == "m >= 8"]
    lo = B.bin.str.extract(r"\(([\d.]+), ([\d.]+)\]").astype(float)
    mid = (lo[0] + lo[1]) / 2
    fig, ax = plt.subplots(figsize=(ONE, 2.3))
    ax.axhline(0.05, color=ORANGE, lw=1, ls="--"); ax.text(3.3, 0.056, "0.05° target", color=ORANGE, fontsize=6.5, ha="right")
    ax.plot(mid, B.self_median, color=BLUE, marker="o", ms=4, lw=1.6, label="median")
    ax.plot(mid, B.self_p90, color=BLUE, marker="o", ms=3, lw=1, ls=":", label="90th percentile")
    for x, (a, b), n in zip(mid, lo.to_numpy(), B.subsets):
        ax.text(x, 0.0035, f"{n:,}", fontsize=5.5, color=MUTED, ha="center")
    ax.set_yscale("log"); ax.set_ylim(0.003, 100); ax.set_xlim(1.0, 3.4)
    ax.set_xlabel("slate size spread in the calibration frames (largest / smallest)")
    ax.set_ylabel("angle error, deg (vs all frames)")
    ax.set_title("How much spread size constancy needs", loc="left", color=INK2)
    ax.legend(loc="upper right", frameon=False, fontsize=6.5)
    save(fig, "codesign_spread")


def codesign_redgreen():
    R = pd.read_csv(RES / "redgreen.csv"); C = pd.read_csv(RES / "redgreen_coverage.csv")
    miss = R[(R.outcome == "missed") & (R.design != "raw, per-frame label colour (T3)")
             & ~R.design.isin(["fish length: frames with head/tail (raw)", "fish length: quartile x environment"])]
    names = {"raw": "all frames", "camera x environment": "same camera, setting",
             "camera x environment x half-year": "+ same half-year", "stagger window 2024-03..2024-12": "both colours in use (2024)",
             "fish length: quartile": "same fish-size quartile", "fish length: quartile x camera x environment": "+ same camera, setting"}
    cov = C[C.outcome == "produced"]
    cnames = {"reef, raw": "all reef frames", "reef, fish-length quartile": "same fish-size quartile",
              "Alligator 2024-03-14 (341 red vs 347+349 green)": "same site and day",
              "Alligator 2024-03-14, fish-length quartile": "+ same fish-size quartile"}
    fig, (a, b) = plt.subplots(1, 2, figsize=(TWO, 2.2), gridspec_kw=dict(width_ratios=[1.1, 1]))
    for ax, D, nm, col, title, xl in ((a, miss, names, ORANGE, "(a) laser dot missed by the detector", "green − red, percentage points"),
                                      (b, cov, cnames, BLUE, "(b) frames given an automatic length (reef)", "green − red, percentage points")):
        y = np.arange(len(D))[::-1]
        ax.axvline(0, color=MUTED, lw=0.8)
        ax.errorbar(D.green_minus_red * 100, y, xerr=[(D.green_minus_red - D.ci_lo) * 100, (D.ci_hi - D.green_minus_red) * 100],
                    fmt="o", color=col, ms=4, capsize=2, elinewidth=1)
        ax.set_yticks(y, [f"{nm[d]}  ({int(r)}/{int(g)} dives)" for d, r, g in zip(D.design, D.dives_red, D.dives_green)])
        ax.grid(axis="y", visible=False); ax.set_xlabel(xl)
        ax.set_title(title, loc="left", color=INK2)
    fig.text(0.01, -0.04, "Bars: 95% interval, resampling whole dives. Dives: red/green. Colour is assigned per dive.",
             fontsize=6, color=INK2)
    fig.tight_layout(); save(fig, "codesign_redgreen")


# ---------------------------------------------------------------- SenSys set
def sensys_system():
    cols = ["Laser dot", "Calibration (per dive)", "Snout and fork", "Species"]
    rows = [
        ("for a person", ["clicks the dot\n13 s per label",
                          "clicks 6-8 slate points\n61 s per frame; tape pattern\nchosen so people can click it",
                          "clicks snout and fork\n15 s per label", "names the species\n12 s per label"], MUTED),
        ("for a machine", ["detector; skips review\nwhen on the dive's\nown laser line",
                           "SAM 3.1 board mask, an\nobject of unknown size;\nframes found by a classifier",
                           "SAM 3.1 fish mask at\nthe dot; head and tail\nfrom the mask", "BioCLIP 2.5 with\na trained head"], BLUE),
        ("what the\nmachine needs\nfrom the system", ["a colour it sees:\ngreen missed 3\u00d7\nas often as red",
                                                                    "slate shot near and far:\n\u2265 2\u00d7 apparent size",
                                                                    "\u2265 2 frames per fish:\n71% \u2192 85% within 10%",
                                                                    "nothing found"], ORANGE),
    ]
    fig, ax = plt.subplots(figsize=(TWO, 2.75)); ax.set_axis_off(); ax.set_xlim(0, 10.6); ax.set_ylim(0, 3.55)
    x0, w, gap, h = 1.6, 2.12, 0.12, 0.9
    for j, c in enumerate(cols):
        ax.text(x0 + j * (w + gap) + w / 2, 3.38, c, ha="center", va="center", fontsize=7.5, fontweight="bold", color=INK)
    for i, (lab, cells, col) in enumerate(rows):
        y = 2.2 - i * (h + 0.13)
        ax.text(0.0, y + h / 2, lab, ha="left", va="center", fontsize=6.6, color=INK2, linespacing=1.15)
        for j, txt in enumerate(cells):
            x = x0 + j * (w + gap)
            ax.add_patch(MF.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.06", lw=1.2,
                                           edgecolor=col, facecolor="white" if col == MUTED else col + "14"))
            ax.text(x + w / 2, y + h / 2, txt, ha="center", va="center", fontsize=5.4,
                    color=MUTED if txt == "nothing found" else INK, linespacing=1.2)
    save(fig, "sensys_system")


def _size_measures(ax):
    T = pd.read_csv(REPO / "calibration_analysis/e1j_size_constancy/tape_by_session.csv")
    M = T.pivot(index="session", columns="cal", values="mae") * 100
    methods = [("known size", "known size + template (production)", True),
               ("unknown size (labelled)", "human corner spread", True),
               ("sam3_box", "SAM 3.1 mask from a human box", True),
               ("label-free", "image registration", False),
               ("sam3_rect_dot", "SAM 3.1 mask + rigid-board fit", False),
               ("sam3_text", "SAM 3.1 mask area", False)]
    methods = [m for m in methods if m[0] in M]
    order = sorted(methods, key=lambda m: -M[m[0]].mean())
    rng = np.random.default_rng(0)
    for i, (key, lab, labelled) in enumerate(order):
        col = MUTED if labelled else BLUE
        v = M[key].to_numpy(); jit = rng.uniform(-0.12, 0.12, len(v))
        ax.scatter(v, i + jit, s=11, color=col, alpha=0.55, edgecolor="none", zorder=2)
        ax.plot([v.mean()] * 2, [i - 0.3, i + 0.3], color=col, lw=2.2, zorder=3)
        ax.text(1.02, i, f"{v.mean():.1f}%", va="center", fontsize=6.8, color=INK, transform=ax.get_yaxis_transform())
    ax.set_yticks(range(len(order)), [lab for _, lab, _ in order]); ax.grid(axis="y", visible=False)
    ax.set_xlim(0, M[[m[0] for m in order]].max().max() * 1.05); ax.set_ylim(-0.6, len(order) - 0.4)
    ax.set_xlabel("length error vs tape, % (dots: 10 sessions; bar: mean)")
    ax.set_title("(a) measuring the slate's apparent size", loc="left", color=INK2, pad=12)
    ax.text(0.0, 1.0, "grey: needs human labels   blue: no labels", transform=ax.transAxes, va="bottom", fontsize=6.2, color=INK2)


def _spread(ax):
    B = pd.read_csv(RES / "calibration_spread_bins.csv"); B = B[B.frames == "m >= 8"]
    lo = B.bin.str.extract(r"\(([\d.]+), ([\d.]+)\]").astype(float); mid = (lo[0] + lo[1]) / 2
    ax.axhline(0.05, color=ORANGE, lw=1, ls="--"); ax.text(3.35, 0.057, "0.05\u00b0 target", color=ORANGE, fontsize=6.5, ha="right")
    ax.plot(mid, B.self_median, color=BLUE, marker="o", ms=4, lw=1.6, label="median")
    ax.plot(mid, B.self_p90, color=BLUE, marker="o", ms=3, lw=1, ls=":", label="90th percentile")
    ax.set_yscale("log"); ax.set_ylim(0.004, 100); ax.set_xlim(1.0, 3.4)
    ax.set_xlabel("slate size spread in the frames (largest / smallest)"); ax.set_ylabel("laser angle error, deg")
    ax.set_title("(b) how much near-far spread it needs", loc="left", color=INK2, pad=12)
    ax.legend(loc="upper right", frameon=False, fontsize=6.5)


def sensys_calibration():
    fig, (a, b) = plt.subplots(1, 2, figsize=(TWO, 2.5), gridspec_kw=dict(width_ratios=[1.25, 1]))
    _size_measures(a); _spread(b)
    fig.tight_layout(w_pad=2.5); save(fig, "sensys_calibration")


def sensys_capture():
    from frames_per_fish import clusters, frame_outcomes  # noqa: E402  (same directory)
    fr = frame_outcomes(); cid = clusters()["labelled"]
    n = fr.assign(cid=fr.image_id.map(cid)).dropna(subset=["cid"]).groupby("cid").size()
    cnt = n.clip(upper=8).value_counts().sort_index()
    fig, (a, b) = plt.subplots(1, 2, figsize=(TWO, 2.3), gridspec_kw=dict(width_ratios=[1, 1.1]))
    a.bar(cnt.index, cnt.values / cnt.sum() * 100, width=0.62, color=BLUE)
    a.set_xticks(range(1, 9), [str(k) for k in range(1, 8)] + ["8+"])
    a.set_xlabel("frames of the fish"); a.set_ylabel("fish, %"); a.grid(axis="x", visible=False)
    a.set_title(f"(a) what divers delivered ({len(n)} fish, median {int(n.median())} frames)", loc="left", color=INK2)
    R = pd.read_csv(RES / "frames_per_fish.csv"); g = R[(R.clusters == "predicted") & R.design.str.startswith("fixed set")].sort_values("k")
    b.errorbar(g.k, g.within10 * 100, yerr=[(g.within10 - g.within10_lo) * 100, (g.within10_hi - g.within10) * 100],
               color=BLUE, marker="o", ms=4, lw=1.6, capsize=2, elinewidth=0.8)
    for k, v in zip(g.k, g.within10):
        b.text(k + 0.1, v * 100 - 4, f"{v * 100:.0f}%", fontsize=6.5, color=INK2)
    b.set_xticks([1, 2, 3, 4]); b.set_xlim(0.7, 4.4); b.set_ylim(40, 102)
    b.set_xlabel("frames taken of the fish"); b.set_ylabel("fish with a length within 10%, %")
    b.set_title(f"(b) what each frame buys ({int(g.fish.iloc[0])} fish with \u2265 4 frames)", loc="left", color=INK2)
    fig.tight_layout(w_pad=2.0); save(fig, "sensys_capture")


def sensys_labelling():
    from labelling import seed_moves  # noqa: E402  (same directory)
    L = pd.read_csv(REPO / "data/labeling/lead_times.csv"); L = L[L.seeded == "f"]
    d = seed_moves()
    a_ = d.groupby(["kind", "seed", "ann_id"]).agg(dist=("dist", "max"), lead=("lead_time_s", "first")).reset_index()
    acc = a_[(a_.seed == "model") & (a_.dist < 0.5)]
    rows = [("slate corners (per frame)", L[L.label_type == "slate_corners"].lead_time_s, None),
            ("snout + fork", L[L.label_type == "head_tail"].lead_time_s, acc[acc.kind == "headtail"].lead),
            ("laser dot", L[L.label_type == "laser_dot"].lead_time_s, acc[acc.kind == "laser"].lead),
            ("species", L[L.label_type == "species"].lead_time_s, None)]
    fig, (a, b) = plt.subplots(1, 2, figsize=(TWO, 2.4), gridspec_kw=dict(width_ratios=[1, 1.15]))
    for i, (lab, scratch, pre) in enumerate(rows[::-1]):
        for v, col, dy, name in ((scratch, MUTED, 0.13, "drawn from scratch"), (pre, BLUE, -0.13, "model pre-fill accepted")):
            if v is None or not len(v):
                continue
            q = np.percentile(v, [25, 50, 75])
            a.plot([q[0], q[2]], [i + dy] * 2, color=col, lw=2.2, solid_capstyle="round")
            a.scatter([q[1]], [i + dy], s=22, color=col, zorder=3, label=name if i == 2 else None)
            a.text(q[2] + 2, i + dy, f"{q[1]:.0f} s", va="center", fontsize=6.5, color=INK2)
    a.set_yticks(range(len(rows)), [r[0] for r in rows[::-1]]); a.grid(axis="y", visible=False); a.set_xlim(0, 100)
    a.set_xlabel("a person's seconds per label (median, IQR)")
    a.set_title("(a) what a label costs a person", loc="left", color=INK2)
    a.legend(loc="upper center", bbox_to_anchor=(0.45, -0.27), ncol=2, frameon=False, fontsize=6.3, handletextpad=0.2)
    S = pd.read_csv(RES / "labelling_seeds.csv")
    bars = [("laser dot, seeded with\nan earlier human label", S[(S.kind == "laser") & (S.seed == "earlier human label")]),
            ("laser dot, seeded by\nthe detector", S[(S.kind == "laser") & (S.seed == "model")]),
            ("snout, seeded by SAM 3.1", S[(S.kind == "headtail") & (S.label == "Snout")]),
            ("fork, seeded by SAM 3.1", S[(S.kind == "headtail") & (S.label == "Fork")])]
    parts = [("unchanged", "unchanged", BLUE), ("nudged", "nudged \u2264 20 px", AQUA), ("replaced", "replaced > 20 px", ORANGE)]
    y = np.arange(len(bars))[::-1]
    for yi, (lab, g) in zip(y, bars):
        w = g.keypoints.to_numpy(); left = 0.0
        for key, plab, col in parts:
            v = float(np.average(g[key], weights=w)) * 100
            b.barh(yi, v, left=left, height=0.6, color=col, edgecolor="white", linewidth=1, label=plab if yi == y[0] else None)
            if v >= 9:
                b.text(left + v / 2, yi, f"{v:.0f}%", ha="center", va="center", fontsize=6.3,
                       color=INK if col == AQUA else "white")   # aqua is below 3:1 against white text
            left += v
        b.text(101.5, yi, f"n={int(w.sum()):,}", va="center", fontsize=6.2, color=INK2)
    b.set_yticks(y, [l for l, _ in bars]); b.set_xlim(0, 100); b.grid(axis="y", visible=False)
    b.set_xlabel("pre-filled keypoints, %")
    b.set_title("(b) what labellers do with a pre-fill", loc="left", color=INK2)
    b.legend(loc="upper center", bbox_to_anchor=(0.4, -0.27), ncol=3, frameon=False, fontsize=6.3, handletextpad=0.3)
    fig.tight_layout(w_pad=2.0); save(fig, "sensys_labelling")


LEVEL = {"designed_experiment": "designed experiment", "deployment_before_after": "deployment before/after",
         "retrospective": "retrospective", "projected": "projected"}


def _tex(x: str) -> str:
    x = x.replace("%", r"\%").replace("|O|", r"$|O|$").replace("->", r"$\rightarrow$").replace(">=", r"$\geq$")
    x = x.replace("+-", r"$\pm$").replace(" deg", r"$^\circ$").replace("~", r"$\sim$")
    return re.sub(r"(\d)x\b", lambda m: m.group(1) + r"$\times$", x)


def design_rules_table():
    C = yaml.safe_load(open(HERE / "claims.yaml"))
    R = yaml.safe_load(open(HERE / "design_rules.yaml"))
    rows = []
    for r in R:
        hits = []
        for start in r["claims"]:
            m = [c for c in C if c["claim"].startswith(start) and "evidence_level" in c]
            if len(m) != 1:
                raise ValueError(f"claim {start!r} matched {len(m)} entries")
            hits.append(m[0])
        # a claim whose number is still a \todo has not been run yet: say so instead of its planned level
        levels = sorted({"pending" if "todo" in str(c.get("number", "")) else LEVEL[c["evidence_level"]] for c in hits})
        secs = sorted({int(x) for c in hits for x in str(c["paper_section"]).split(",")})
        rows.append(f"{_tex(r['rule'])} & {_tex(r['short'])} & {'; '.join(levels)} & "
                    + ", ".join(rf"\S{x}" for x in secs) + r" \\")
    tex = "\n".join([
        "% Generated by analysis/codesign/figures.py from design_rules.yaml and claims.yaml; do not edit by hand.",
        r"\begin{table*}[t]", r"\caption{Design rules for automating a human-labelled sensing system, with the evidence behind each.}",
        r"\label{tab:design-rules}", r"\small", r"\begin{tabular}{p{0.36\textwidth}p{0.34\textwidth}p{0.15\textwidth}l}",
        r"\toprule", r"Rule & Evidence & Kind & Section \\", r"\midrule", *rows, r"\bottomrule", r"\end{tabular}", r"\end{table*}", ""])
    (HERE / "design_rules.tex").write_text(tex); print("wrote design_rules.tex")


if __name__ == "__main__":
    design_rules_table()
    sys.path.insert(0, str(HERE))
    for f in (codesign_timeline, codesign_frames_fish, codesign_spread, codesign_redgreen,
              sensys_system, sensys_calibration, sensys_capture, sensys_labelling):
        f()
