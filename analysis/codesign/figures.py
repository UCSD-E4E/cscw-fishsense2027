"""Figures for the SenSys 2027 co-design paper (task 4), built only from committed files.

  codesign_timeline      design revisions over time by component, coloured by driver (timeline.yaml)
  codesign_frames_fish   share of fish with a length within 10% of manual vs frames taken (3b)
  codesign_spread        calibration angle error vs slate size spread, 0.05 deg target marked (3c)
  codesign_redgreen      what green cost the detector, the pipeline and the labeller: red vs green rates, matched comparison noted (3d, 3e)
  design_rules.tex       LaTeX design-rules table from design_rules.yaml + claims.yaml (evidence level, section)

Experiences-paper figures (2026-10-07 brief):
  paper_laser_calibration  s3  laser calibration as two parallel tracks (lab checkerboard, field slate) and the
                               mount band; colour = who finds the target (person or machine)
  paper_automation         s3/s4  automation attempts per labelling task, by outcome (automation_attempts.yaml)

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
    # calibration runs on two parallel tracks (lab checkerboard, field slate), not in sequence
    lanes = ["hardware", "protocol", "calibration:lab", "calibration:field", "automation", "labeling", "pipeline"]
    names = {"labeling": "labelling", "calibration:lab": "calibration, lab", "calibration:field": "calibration, field",
             "automation": "machine labelling\n(plan, attempts)"}
    GAP = 2.0                                   # vertical distance between lanes
    fig, ax = plt.subplots(figsize=(TWO, 6.2))
    ax.axvspan(pd.Timestamp("2023-08-01"), pd.Timestamp("2025-01-17"), color=GRID, alpha=0.55, lw=0, zorder=0)
    ax.text(pd.Timestamp("2023-08-10"), (len(lanes) - 1) * GAP + 1.1, "dives captured (2023-08 .. 2025-01)",
            fontsize=6.5, color=INK2, va="top")
    ax.set_xlim(pd.Timestamp("2023-06-01"), pd.Timestamp("2026-12-31"))
    ax.set_ylim(-1.1, (len(lanes) - 1) * GAP + 1.15)
    undated, yearonly, events = [], [], []
    for li, lane in enumerate(lanes):
        y = (len(lanes) - 1 - li) * GAP
        for e in T:
            key = e["component"] + (f":{e['track']}" if e.get("track") else "")
            if key != lane or str(e["driver"]).startswith("n/a"):
                continue
            d = _dates(e["date"])
            if d:
                events.append((y, d, e))
            elif re.fullmatch(r"\d{4}", str(e["date"]).strip()):
                yearonly.append(f'{e["label"]} ({e["date"]})')     # a year but no month: listed, not placed
            else:
                undated.append(e["label"])
    r = fig.canvas.get_renderer()
    placed, marks, drawn = [], [], []
    for y0, (t0, t1), e in sorted(events, key=lambda x: (x[0], x[1][0])):
        # markers within 12 days of one already drawn in the lane are nudged up/down so neither hides
        near = sum(1 for (yy, tt) in marks if yy == y0 and abs((tt - t0).days) <= 12)
        y = y0 + [0, 0.17, -0.17, 0.34][min(near, 3)]
        marks.append((y0, t0))
        lab, col = DRIVER.get(str(e["driver"]), DRIVER["unknown"])
        planned = ("not deployed" in str(e["date"]) or "analysis only" in str(e["date"])
                   or "not deployed" in str(e.get("status", "")) or str(e.get("status", "")).startswith("attempted"))
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
    ax.scatter([], [], s=30, color="white", edgecolor=MUTED, label="not deployed / attempted")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.07), ncol=5, frameon=False, fontsize=6.5, handletextpad=0.2)
    ax.text(0.0, -0.13, "not placed - year only: " + "; ".join(yearonly) + ".   No date recorded: " + "; ".join(undated),
            transform=ax.transAxes, fontsize=5.8, color=INK2, va="top", wrap=True)
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
    """What the switch to green cost each stage: the detector, the end-to-end pipeline, the labeller.
    Bars are plain red-vs-green rates; the line under each panel is the matched comparison."""
    R = pd.read_csv(RES / "redgreen.csv"); C = pd.read_csv(RES / "redgreen_coverage.csv"); B = pd.read_csv(RES / "before_after.csv")
    row = lambda D, design, outcome: D[(D.design == design) & (D.outcome == outcome)].iloc[0]
    RED, GRN = ORANGE, AQUA      # laser colours; always named in the legend, never colour alone
    fig, axes = plt.subplots(1, 3, figsize=(TWO, 2.45), gridspec_kw=dict(width_ratios=[1.15, 1.15, 0.7]))

    def pairs(ax, groups, fmt, ymax):
        for k, (name, r, g) in enumerate(groups):
            for dx, v, col in ((-0.19, r, RED), (0.19, g, GRN)):
                ax.bar(k + dx, v, width=0.36, color=col, edgecolor="white", linewidth=1)
                ax.text(k + dx, v + ymax * 0.02, fmt(v), ha="center", va="bottom", fontsize=6.4, color=INK)
        ax.set_xticks(range(len(groups)), [g[0] for g in groups], fontsize=6.6)
        ax.set_xlim(-0.6, len(groups) - 0.4)
        ax.set_ylim(0, ymax); ax.grid(axis="x", visible=False)

    a, b, c = axes
    m, w = row(R, "raw", "missed"), row(R, "raw", "confident-wrong")
    pairs(a, [("missed", m.red_rate * 100, m.green_rate * 100),
              ("wrong spot", w.red_rate * 100, w.green_rate * 100)], lambda v: f"{v:.0f}%", 22)
    a.set_ylabel("frames with a laser dot, %")
    a.set_title("(a) the detector", loc="left", color=INK2)
    mm = row(R, "camera x environment", "missed")
    a.text(0.0, -0.36, f"Same camera and setting: green misses\n{mm.green_minus_red * 100:.0f} pt more dots "
           f"(95% CI {mm.ci_lo * 100:.0f} to {mm.ci_hi * 100:.0f}).", transform=a.transAxes, fontsize=6.2, color=INK2, va="top")

    al, sd = row(C, "reef, raw", "produced"), row(C, "Alligator 2024-03-14 (341 red vs 347+349 green)", "produced")
    pairs(b, [(f"all reef dives\n({int(al.dives_red)} red, {int(al.dives_green)} green)", al.red_rate * 100, al.green_rate * 100),
              ("one site,\none day", sd.red_rate * 100, sd.green_rate * 100)],
          lambda v: f"{v:.0f}%", 110)
    b.set_ylabel("measured frames given\nan automatic length, %")
    b.set_title("(b) the whole pipeline (reef)", loc="left", color=INK2)
    b.text(0.0, -0.36, f"Mostly a difference between dives: on one\nsite and day, green is {-sd.green_minus_red * 100:.0f} pt lower "
           f"({int(sd.dives_red)} red, {int(sd.dives_green)} green dives).",
           transform=b.transAxes, fontsize=6.2, color=INK2, va="top")

    lb = B[B.revision.str.startswith("laser red")].iloc[0]
    pairs(c, [("seconds per\nlaser label", lb.pooled_median_a, lb.pooled_median_b)], lambda v: f"{v:.1f} s", 19)
    c.set_ylabel("median seconds")
    c.set_title("(c) the labeller", loc="left", color=INK2)
    c.text(0.0, -0.36, f"Same labeller: green takes\n{lb.within_annotator_diff:.1f} s longer "
           f"(CI {lb.ci_lo:.1f} to {lb.ci_hi:.1f}).", transform=c.transAxes, fontsize=6.2, color=INK2, va="top")

    handles = [MF.matplotlib.patches.Patch(color=RED, label="red laser"), MF.matplotlib.patches.Patch(color=GRN, label="green laser")]
    fig.legend(handles=handles, loc="upper right", ncol=2, frameon=False, fontsize=6.8, bbox_to_anchor=(1.0, 1.0))
    fig.subplots_adjust(left=0.07, right=0.985, bottom=0.3, top=0.8, wspace=0.55); save(fig, "codesign_redgreen")


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


# ---------------------------------------------------------------- Experiences paper (2026-10-07)
def _ts(x):
    """A date from YAML: a date object, YYYY-MM-DD, or YYYY-MM (placed mid-month)."""
    x = str(x)
    return pd.Timestamp(x + "-15") if len(x) == 7 else pd.Timestamp(x)


def _place_labels(fig, ax, items, levels=(0.26, -0.26, 0.46, -0.46, 0.66, -0.66), size=5.8, late_from="2026-01-01"):
    """items: (x, y, text). Each label goes to the first level and side that overlaps nothing placed."""
    fig.canvas.draw(); r = fig.canvas.get_renderer(); placed = []
    for x, y, _ in items:
        cx, cy = ax.transData.transform((mdates.date2num(x), y))
        placed.append(Bbox([[cx - 8, cy - 8], [cx + 8, cy + 8]]))
    for x, y, text in items:
        prefer = ("right", "left") if x >= pd.Timestamp(late_from) else ("left", "right")
        for dy, ha in [(d, h) for d in levels for h in prefer]:
            t = ax.text(x, y + dy, text, fontsize=size, color=INK2, ha=ha, va="center")
            bb = t.get_window_extent(r).expanded(1.08, 1.3)
            if not any(bb.overlaps(q) for q in placed):
                placed.append(bb); ax.plot([x, x], [y, y + dy * 0.8], color=MUTED, lw=0.5, zorder=1); break
            t.remove()
        else:
            raise RuntimeError(f"no room for label {text!r}")


def paper_laser_calibration():
    T = yaml.safe_load(open(HERE / "laser_calibration_tracks.yaml"))
    COL = {"human": BLUE, "machine": ORANGE}
    fig, ax = plt.subplots(figsize=(TWO, 3.0))
    ax.axvspan(pd.Timestamp("2023-08-01"), pd.Timestamp("2025-01-17"), color=GRID, alpha=0.55, lw=0, zorder=0)
    ax.text(pd.Timestamp("2023-08-10"), 2.72, "dives captured (2023-08 .. 2025-01)", fontsize=6.3, color=INK2, va="top")
    ys = {"lab": 2.0, "field": 1.0}
    items = []
    for track, y in ys.items():
        for e in T[track]:
            t0 = _ts(e["date"]); t1 = _ts(e["end"]) if e.get("end") else t0
            col = COL[e["interface"]]
            if t1 > t0:
                ax.plot([t0, t1], [y, y], color=col, lw=4, alpha=0.5, solid_capstyle="butt", zorder=2)
            hollow = e["kind"] in ("attempted", "proposed")
            ax.scatter([t0], [y], s=34, zorder=3, color="white" if hollow else col, edgecolor=col, linewidth=1.3,
                       marker="D" if e["kind"] == "proposed" else "o")
            if e["kind"] == "reverted":       # replaced by human labels: a blue cross at the end of the bar
                ax.scatter([t1], [y], s=40, zorder=4, color=BLUE, marker="X", edgecolor="white", linewidth=0.6)
            items.append((t0, y, e["label"]))
    m = T["mount"]; m0, m1 = (_ts(x) for x in m["span"])
    ax.plot([m0, m1], [0.15, 0.15], color=MUTED, lw=6, alpha=0.45, solid_capstyle="butt")
    ax.text(m1 + pd.Timedelta(days=20), 0.15, "PLA, redesigned after field breakage; later aluminium for field units\n"
            "(revision and switch dates not recorded). Before 2023-08 a PLA mount warped,\nso laser calibration became per dive.",
            fontsize=5.6, color=INK2, va="center")
    _place_labels(fig, ax, items)
    ax.set_yticks([2.0, 1.0, 0.15], ["lab\n(checkerboard)", "field\n(dive slate)", "laser mount"])
    ax.set_ylim(-0.25, 2.8); ax.set_xlim(pd.Timestamp("2023-06-01"), pd.Timestamp("2026-12-31")); ax.grid(axis="y", visible=False)
    for lab, col, mk, fc in (("a person finds it", BLUE, "o", BLUE), ("a machine finds it", ORANGE, "o", ORANGE),
                             ("attempted", MUTED, "o", "white"), ("proposed (this paper)", ORANGE, "D", "white"),
                             ("replaced by human labels", BLUE, "X", BLUE)):
        ax.scatter([], [], s=30, marker=mk, color=fc, edgecolor=col, label=lab)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=5, frameon=False, fontsize=6.3, handletextpad=0.2)
    ax.text(0.0, -0.24, "Not placed: " + "; ".join(T["pending"]) + ". Lens calibration is a separate once-per-camera step and is not shown.",
            transform=ax.transAxes, fontsize=5.6, color=INK2, va="top")
    ax.set_title("Laser calibration ran on two tracks: the lab for a machine, the field for a person", loc="left", color=INK2)
    save(fig, "paper_laser_calibration")


def paper_automation():
    A = yaml.safe_load(open(HERE / "automation_attempts.yaml"))
    tasks = ["laser dot", "laser calibration", "head/tail", "species"]
    OUTC = {"deployed": ("deployed", BLUE, "o", BLUE), "reverted": ("reverted to human labels", ORANGE, "X", ORANGE),
            "dropped": ("dropped or replaced", MUTED, "o", "white"), "evaluated": ("evaluated only", AQUA, "D", "white"),
            "unrecorded": ("outcome not recorded", MUTED, "s", GRID)}
    fig, ax = plt.subplots(figsize=(TWO, 2.9))
    ax.axvspan(pd.Timestamp("2023-08-01"), pd.Timestamp("2025-01-17"), color=GRID, alpha=0.55, lw=0, zorder=0)
    ax.text(pd.Timestamp("2023-08-10"), len(tasks) - 0.25, "dives captured", fontsize=6.3, color=INK2, va="top")
    items, seen = [], []
    for e in A:
        y0 = len(tasks) - 1 - tasks.index(e["task"])
        t0 = _ts(e["start"]); t1 = _ts(e["end_event"]) if e.get("end_event") else t0
        near = sum(1 for yy, tt in seen if yy == y0 and abs((tt - t1).days) <= 14)   # keep near-coincident markers visible
        y = y0 + [0, 0.13, -0.13][min(near, 2)]; seen.append((y0, t1))
        lab, col, mk, fc = OUTC[e["outcome"]]
        edge = col if e["outcome"] != "unrecorded" else MUTED
        if t1 > t0:
            ax.plot([t0, t1], [y, y], color=edge, lw=3, alpha=0.5, solid_capstyle="butt", zorder=2)
        ax.scatter([t1], [y], s=36, marker=mk, color=fc, edgecolor=edge, linewidth=1.2, zorder=3)
        items.append((t1, y, e["label"]))
    _place_labels(fig, ax, items, levels=(0.24, -0.24, 0.42, -0.42), size=5.6)
    ax.set_yticks(range(len(tasks)), tasks[::-1]); ax.set_ylim(-0.6, len(tasks) - 0.2)
    ax.set_xlim(pd.Timestamp("2023-06-01"), pd.Timestamp("2026-12-31")); ax.grid(axis="y", visible=False)
    for k, (lab, col, mk, fc) in OUTC.items():
        ax.scatter([], [], s=30, marker=mk, color=fc, edgecolor=col, label=lab)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.1), ncol=5, frameon=False, fontsize=6.3, handletextpad=0.2)
    ax.set_title("Machine labelling: three years of attempts before the first deployment (marker at the outcome)", loc="left", color=INK2)
    save(fig, "paper_automation")


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
              sensys_system, sensys_calibration, sensys_capture, sensys_labelling,
              paper_laser_calibration, paper_automation):
        f()
