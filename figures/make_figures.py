"""Figures for PAPER.md, built only from result files committed in this repo (no NAS, no GPU).

  fig1_pipeline        the automatic pipeline and the human step each stage replaces
  fig2_stage_time      (a) days REEF data waited to reach the lab; (b) machine time per automated stage (Temporal)
  fig3_size_constancy  (a) apparent size vs dot position for one session, intercept = vanishing point
                       (b) per-session error vs the known-size slate calibration, labelled and label-free
  fig4_stage_ladder    per-fish length error as each human input becomes automatic (pool, tape truth)
  fig5_reef_lengths    fully automatic vs manual length on real reef fish
  fig6_coverage        frames covered vs human-rejected frames measured, as the SAM cutoff moves
  fig7_species         confusion matrix of the trained BioCLIP species head
  fig8_labeling_time   person-seconds per label by type, drawn from scratch (no prediction seed)

Colours: the dataviz skill's validated reference palette (first three categorical slots pass
all-pairs CVD checks on white; aqua is below 3:1 contrast, so it is always direct-labelled) and
its blue sequential ramp. Run from the repo root:  uv run python figures/make_figures.py
"""
from __future__ import annotations

import json, sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "figures"
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "e2e_measurement"))
sys.path.insert(0, str(REPO / "calibration_analysis/e1j_size_constancy"))

BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
INK, INK2, MUTED, GRID = "#0b0b0b", "#52514e", "#8a8984", "#e4e3df"
SEQ = ["#ffffff", "#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
ONE, TWO = 3.33, 7.0     # ACM column widths, inches

plt.rcParams.update({
    "font.size": 8, "axes.titlesize": 8, "axes.labelsize": 8, "xtick.labelsize": 7, "ytick.labelsize": 7,
    "legend.fontsize": 7, "axes.edgecolor": MUTED, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
    "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True, "lines.linewidth": 2,
    "savefig.bbox": "tight", "savefig.dpi": 300, "pdf.fonttype": 42,
})


def save(fig, name):
    for ext in ("pdf", "png"):
        fig.savefig(OUT / f"{name}.{ext}")
    plt.close(fig); print("wrote", name)


def p90(v):
    v = np.sort(np.asarray(v, float)); v = v[np.isfinite(v)]
    return v[min(len(v) - 1, int(np.ceil(0.9 * len(v))) - 1)] if len(v) else np.nan


# ---------------------------------------------------------------- fig 1
def fig1_pipeline():
    fig, ax = plt.subplots(figsize=(TWO, 2.0)); ax.set_axis_off(); ax.set_xlim(0, 10); ax.set_ylim(0, 3.2)
    stages = [("Laser dot", "production\ndetector", "a person clicks\nthe dot"),
              ("Fish mask", "SAM 3.1,\ngated by the dot", "a person finds\nthe fish"),
              ("Head & tail", "mask\ngeometry", "a person clicks\nsnout and fork"),
              ("Length", "dot depth ×\nimage length", "slate corners\nclicked per dive"),
              ("Species", "BioCLIP 2.5 +\ntrained head", "a person names\nthe species")]
    w, gap = 1.62, 0.37
    for i, (name, how, replaces) in enumerate(stages):
        x = 0.1 + i * (w + gap)
        ax.add_patch(FancyBboxPatch((x, 1.35), w, 1.45, boxstyle="round,pad=0.02,rounding_size=0.08",
                                    fc="#eef4fc", ec=BLUE, lw=1.2))
        ax.text(x + w / 2, 2.45, name, ha="center", va="center", fontsize=8.5, weight="bold", color=INK)
        ax.text(x + w / 2, 1.85, how, ha="center", va="center", fontsize=6.5, color=INK2, linespacing=1.2)
        ax.text(x + w / 2, 1.05, "replaces", ha="center", va="center", fontsize=6.5, color=MUTED)
        ax.text(x + w / 2, 0.62, replaces, ha="center", va="center", fontsize=6.5, color=INK2, linespacing=1.2)
        if i < len(stages) - 1:
            ax.annotate("", xy=(x + w + gap - 0.04, 2.07), xytext=(x + w + 0.04, 2.07),
                        arrowprops=dict(arrowstyle="-|>", color=INK2, lw=1))
    ax.text(0.1, 0.05, "Calibration: laser offset from the mount design; laser angle from any rigid object shot near "
            "and far (apparent-size constancy), no labels.", fontsize=6.5, color=INK2)
    save(fig, "fig1_pipeline")


# ---------------------------------------------------------------- fig 2
def fig2_stage_time():
    """(a) calendar days a REEF dive waited before reaching the lab (organisational);
    (b) machine time per dive for each automated stage, completed Temporal runs (last ~30 days)."""
    from fishsense_cscw.turnaround import reef_dives
    wait = reef_dives().to_lab_days.dropna(); wait = wait[wait >= 0]
    R = pd.read_csv(REPO / "data/temporal/workflow_runs.csv", parse_dates=["start_time", "close_time"])
    R = R[R.status == "COMPLETED"]; R["s"] = (R.close_time - R.start_time).dt.total_seconds()
    stages = [("IngestDiveWorkflow", "intake"), ("PreprocessLaserImagesWorkflow", "preprocess: laser"),
              ("PreprocessHeadtailImagesWorkflow", "preprocess: head/tail"), ("PreprocessSpeciesImagesWorkflow", "preprocess: species"),
              ("PredictHeadtailImagesWorkflow", "predict head/tail"), ("PerformLaserCalibrationWorkflow", "laser calibration"),
              ("ComputeLaserDepthsWorkflow", "laser depths"), ("MeasureFishWorkflow", "measure")]
    fig, (a, b) = plt.subplots(1, 2, figsize=(TWO, 2.5), gridspec_kw=dict(width_ratios=[1, 1.25]))
    a.hist(wait, bins=np.arange(0, wait.max() + 30, 30), color=BLUE, edgecolor="white", linewidth=1)
    med = wait.median(); a.axvline(med, color=INK2, lw=1, ls="--")
    a.text(med + 10, a.get_ylim()[1] * 0.92, f"median {med:.0f} days", fontsize=7, color=INK2)
    a.set_xlabel("days from dive to data reaching the lab"); a.set_ylabel("REEF dives")
    a.set_title(f"(a) waiting for data ({len(wait)} dives): organisational", loc="left", color=INK2)
    rows = [(lab, R[R.workflow_type == t].s.to_numpy()) for t, lab in stages]
    rows = [(lab, v) for lab, v in rows if len(v)]
    for i, (lab, v) in enumerate(rows[::-1]):
        p10, q1, med, q3, p90 = np.percentile(v, [10, 25, 50, 75, 90])
        b.plot([p10, p90], [i, i], color=BLUE, lw=1.2, solid_capstyle="round")
        b.add_patch(plt.Rectangle((q1, i - 0.28), q3 - q1, 0.56, fc="#cde2fb", ec=BLUE, lw=1))
        b.plot([med, med], [i - 0.28, i + 0.28], color=INK, lw=1.5)
        b.text(p90 * 1.15, i, (f"{med:.0f} s" if med < 120 else f"{med / 60:.1f} min") + f"  (n={len(v)})",
               va="center", fontsize=6.5, color=INK2)
    b.set_xscale("log"); b.set_xlim(1, 3e4)
    b.set_xticks([1, 10, 60, 600, 3600], ["1 s", "10 s", "1 min", "10 min", "1 h"])
    b.set_yticks(range(len(rows)), [lab for lab, _ in rows[::-1]]); b.grid(axis="y", visible=False)
    b.set_ylim(-0.6, len(rows) - 0.4); b.set_xlabel("machine time per dive (median, IQR, p10–p90)")
    b.set_title("(b) automated stages, Temporal runs Sep 2026: system", loc="left", color=INK2)
    fig.tight_layout(); save(fig, "fig2_stage_time")


# ---------------------------------------------------------------- fig 3
def fig3_size_constancy():
    import slate_unknown as su
    d, lines, ext, intr = su.load()
    F_PX = su.F_PX
    rows = []
    for dive, g in d.groupby("dive_id"):
        if len(g) < su.MIN_FRAMES or dive not in ext.index:
            continue
        u = su.frame(dive, g, lines); t = g[["x", "y"]].to_numpy(float) @ u; s = g["size"].to_numpy()
        if s.max() / s.min() < 1.5:
            continue
        tv = su.fit_tv(t, s)
        ax_ = np.array(json.loads(ext.loc[dive, "axis"])); K = intr[int(ext.loc[dive, "camera_id"])]
        v = np.array([K[0, 0] * ax_[0] / ax_[2] + K[0, 2], K[1, 1] * ax_[1] / ax_[2] + K[1, 2]])
        rows.append(dict(dive=dive, t=t, s=s, tv=tv, tv_true=float(v @ u), err=np.degrees((tv - v @ u) / F_PX)))
    L = pd.read_csv(REPO / "calibration_analysis/e1j_size_constancy/labelfree_tv.csv").set_index("dive")
    fig, (a, b) = plt.subplots(1, 2, figsize=(TWO, 2.4), gridspec_kw=dict(width_ratios=[1.15, 1]))
    ex = next(r for r in rows if r["dive"] == 71)
    t0 = ex["tv_true"]; x = ex["t"] - t0
    k = np.sum(ex["s"] * (ex["t"] - ex["tv"])) / np.sum((ex["t"] - ex["tv"]) ** 2)
    xx = np.linspace(min(ex["tv"] - t0, 0) - 5, x.max() + 10, 50)
    a.plot(xx, k * (xx + t0 - ex["tv"]), color=BLUE, lw=1.5, label="fit: size ∝ distance from vanishing point")
    a.scatter(x, ex["s"], s=16, color=BLUE, edgecolor="white", linewidth=0.5, zorder=3, label="slate frames")
    a.axvline(0, color=ORANGE, lw=1.5, ls="--")
    a.text(3, ex["s"].max() * 0.95, "vanishing point from the\nknown-size slate calibration", color=INK2, fontsize=6.5, va="top")
    a.set_xlim(xx.min(), xx.max()); a.set_ylim(0, ex["s"].max() * 1.08)
    a.set_xlabel("dot position along the laser line, px (0 = vanishing point)"); a.set_ylabel("apparent slate size, px")
    a.set_title("(a) one session: size shrinks to zero at the vanishing point", loc="left", color=INK2)
    a.legend(loc="lower right", frameon=False)
    R = pd.DataFrame([dict(dive=r["dive"], labelled=abs(r["err"])) for r in rows]).set_index("dive")
    R["label-free"] = L.err_deg.abs().reindex(R.index)
    R = R.sort_values("labelled"); y = np.arange(len(R))
    b.axvline(0.05, color=MUTED, lw=1, ls=":")
    b.text(0.051, len(R) - 0.6, "0.05° target", color=INK2, fontsize=6.5)
    b.scatter(R.labelled, y + 0.12, s=22, color=BLUE, edgecolor="white", linewidth=0.5, zorder=3, label="labelled corners")
    b.scatter(R["label-free"], y - 0.12, s=22, color=ORANGE, edgecolor="white", linewidth=0.5, zorder=3, label="label-free registration")
    b.set_yticks(y, [f"session {i}" for i in R.index]); b.set_xlabel("|angle error| vs known-size calibration, degrees")
    b.set_title("(b) every session, unknown object size", loc="left", color=INK2)
    b.legend(loc="lower right", frameon=False); b.grid(axis="y", visible=False)
    fig.tight_layout(); save(fig, "fig3_size_constancy")


# ---------------------------------------------------------------- fig 4
def fig4_stage_ladder():
    D = pd.read_csv(REPO / "e2e_measurement/lengths.csv")
    order = ["A manual (production today)", "B auto dot", "D label-free calibration", "C auto head/tail",
             "E auto dot + head/tail", "F end-to-end automatic"]
    names = {"A manual (production today)": "manual (today)", "B auto dot": "+ automatic dot",
             "D label-free calibration": "+ label-free calibration", "C auto head/tail": "+ automatic head/tail",
             "E auto dot + head/tail": "automatic dot + head/tail", "F end-to-end automatic": "fully automatic"}
    vals = []
    for c in order:
        g = D[D.config == c].dropna(subset=["err"])
        est = [abs(p90(t.L) / t.L_true.iloc[0] - 1) for _, t in g.groupby(["dive", "model"])]
        vals.append(100 * np.mean(est))
    fig, ax = plt.subplots(figsize=(ONE, 2.0))
    y = np.arange(len(order))[::-1]
    ax.barh(y, vals, height=0.62, color=BLUE)
    for yi, v in zip(y, vals):
        ax.text(v + 0.3, yi, f"{v:.1f}%", va="center", fontsize=7, color=INK)
    ax.set_yticks(y, [names[c] for c in order]); ax.grid(axis="y", visible=False)
    ax.set_xlabel("per-fish length error vs tape (mean |p90 error|, %)"); ax.set_xlim(0, max(vals) * 1.2)
    ax.set_title("Pool fish models, 10 dives", loc="left", color=INK2)
    save(fig, "fig4_stage_ladder")


# ---------------------------------------------------------------- fig 5
def fig5_reef_lengths():
    import score as S
    T = REPO / "e2e_measurement/tail"
    F = pd.read_csv(T / "frames.csv"); reef = F[F.set == "reef"]
    K = pd.read_csv(T / "keypoints.csv"); K = K[K.seed == "auto"].set_index("image_id")
    dots = {}
    for l in (T / "reef_dots.jsonl").open():
        r = json.loads(l)
        if "dot" in r and r["dot"]["x"] is not None:
            dots[r["image_id"]] = (r["dot"]["x"], r["dot"]["y"])
    stored, _, intr = S.calibrations(); pts = []
    for r in reef.itertuples():
        cal = stored.get(int(r.dive_id))
        if cal is None or pd.isna(r.head_x) or r.image_id not in dots or r.image_id not in K.index or pd.isna(K.loc[r.image_id, "head_x"]):
            continue
        k = K.loc[r.image_id]; Kc = intr[int(r.camera_id)]
        Lm = S.length(Kc, S.depth(Kc, cal[0], cal[1], r.laser_x, r.laser_y), r.head_x, r.head_y, r.tail_x, r.tail_y)
        La = S.length(Kc, S.depth(Kc, cal[0], cal[1], *dots[r.image_id]), k.head_x, k.head_y, k.prod_tail_x, k.prod_tail_y)
        pts.append((100 * Lm, 100 * La, str(r.laser_label).startswith("Green")))
    P = np.array([(a, b) for a, b, _ in pts]); green = np.array([g for _, _, g in pts])
    rel = P[:, 1] / P[:, 0] - 1
    fig, ax = plt.subplots(figsize=(ONE, 3.0))
    lim = np.array([0, np.percentile(P, 99.5) * 1.05])
    ax.fill_between(lim, lim * 0.9, lim * 1.1, color=GRID, lw=0, label="±10%")
    ax.plot(lim, lim, color=INK2, lw=1)
    ax.scatter(P[~green, 0], P[~green, 1], s=10, color=BLUE, edgecolor="white", linewidth=0.4, label="red-laser dives", zorder=3)
    ax.scatter(P[green, 0], P[green, 1], s=10, color=ORANGE, edgecolor="white", linewidth=0.4, label="green-laser dives", zorder=3)
    ax.set_xlim(lim); ax.set_ylim(lim); ax.set_aspect("equal")
    ax.set_xlabel("manual length, cm (human dot and head/tail)"); ax.set_ylabel("fully automatic length, cm")
    ax.set_title(f"Reef fish, {len(P)} frames: median {100 * np.median(rel):+.1f}%, MAE {100 * np.mean(np.abs(rel)):.1f}%, "
                 f"{np.mean(np.abs(rel) <= .1):.0%} within 10%", loc="left", color=INK2, fontsize=7)
    ax.legend(loc="upper left", frameon=False)
    save(fig, "fig5_reef_lengths")


# ---------------------------------------------------------------- fig 6
def fig6_coverage():
    T = REPO / "e2e_measurement/tail"
    C = pd.read_csv(T / "coverage_causes.csv"); R = pd.read_csv(T / "coverage_remedies.csv"); G = pd.read_csv(T / "gate_features.csv")
    meas = set(C[C.L_px.notna()].image_id); skip = set(C[C.L_px.isna()].image_id)
    cut = {"production (fish > 0.5, on dot)": 0.5, "threshold 0.3": 0.3, "threshold 0.2": 0.2, "threshold 0.1": 0.1}
    xs, ys = [], []
    for name, c in cut.items():
        g = R[R.remedy == name]
        xs.append(100 * g[g.image_id.isin(skip)].covered.mean()); ys.append(100 * g[g.image_id.isin(meas)].covered.mean())
    gx, gy = [], []
    for thr in np.linspace(0.05, 0.95, 37):
        acc = G.p > thr
        gx.append(100 * (acc & ~G.measured).sum() / len(skip)); gy.append(100 * (acc & G.measured).sum() / len(meas))
    fig, ax = plt.subplots(figsize=(ONE, 2.5))
    ax.plot(gx, gy, color=ORANGE, lw=1.5, label="learned measurability gate (held-out dives)")
    ax.plot(xs, ys, color=BLUE, lw=1.5, marker="o", ms=5, mec="white", mew=0.6, label="SAM confidence cutoff", zorder=3)
    for x, y, c in zip(xs, ys, cut.values()):
        ax.annotate(f"{c:g}" + (" (production)" if c == 0.5 else ""), (x, y), xytext=(-4, 7), textcoords="offset points",
                    ha="right" if c == 0.5 else "center", fontsize=6.5, color=INK2)
    ax.set_xlabel("frames humans rejected that get a length, %"); ax.set_ylabel("frames humans measured that get a length, %")
    ax.set_ylim(top=95)
    ax.set_title("Reef frames: coverage costs false measurements", loc="left", color=INK2)
    ax.legend(loc="lower right", frameon=False)
    save(fig, "fig6_coverage")


# ---------------------------------------------------------------- fig 7
def fig7_species():
    P = pd.read_csv(REPO / "e2e_measurement/species/probe_hybrid_predictions.csv")
    common = {"Lachnolaimus maximus": "Hogfish", "Sparisoma viride": "Stoplight parrotfish", "Mycteroperca bonaci": "Black grouper",
              "Scarus coeruleus": "Blue parrotfish", "Epinephelus striatus": "Nassau grouper", "Scarus guacamaia": "Rainbow parrotfish",
              "Scarus coelestinus": "Midnight parrotfish", "Lutjanus griseus": "Grey snapper", "Epinephelus itajara": "Goliath grouper",
              "Ocyurus chrysurus": "Yellowtail snapper", "Lutjanus analis": "Mutton snapper", "OTHER": "Other (non-target)"}
    P = P.dropna(subset=["pred"])
    truth_order = P.truth.value_counts().index.tolist()
    labels = truth_order + [c for c in sorted(P.pred.unique()) if c not in truth_order]
    M = pd.crosstab(P.truth, P.pred).reindex(index=truth_order, columns=labels, fill_value=0)
    N = M.div(M.sum(1), axis=0)
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("blue_seq", SEQ)
    fig, ax = plt.subplots(figsize=(TWO * 0.62, 3.6))
    ax.imshow(N.to_numpy(), cmap=cmap, vmin=0, vmax=1, aspect="auto")
    for i in range(M.shape[0]):
        for j in range(M.shape[1]):
            n = M.iat[i, j]
            if n:
                ax.text(j, i, str(n), ha="center", va="center", fontsize=6, color="white" if N.iat[i, j] > 0.55 else INK)
    ax.set_xticks(range(len(labels)), [common.get(c, c) for c in labels], rotation=60, ha="right")
    ax.tick_params(length=0)
    ax.set_yticks(range(len(truth_order)), [f"{common.get(c, c)} ({M.loc[c].sum()})" for c in truth_order])
    ax.set_xlabel("predicted"); ax.set_ylabel("human label (frames)"); ax.grid(False)
    for s in ax.spines.values():
        s.set_visible(False)
    tgt = P[P.truth != "OTHER"]
    ax.set_title(f"Species, held-out dives: {np.mean(tgt.pred == tgt.truth):.1%} top-1 on target species "
                 f"(shade = row share, number = frames)", loc="left", color=INK2)
    save(fig, "fig7_species")


# ---------------------------------------------------------------- fig 8
def fig8_labeling_time():
    """Person-time per label, drawn from scratch: no prediction or earlier label as a seed."""
    d = pd.read_csv(REPO / "data/labeling/lead_times.csv")
    d = d[d.seeded.astype(str).str.lower().isin(["f", "false"])]
    names = {"laser_dot": "laser dot", "head_tail": "snout + fork", "species": "species", "slate_corners": "slate corners\n(per slate frame)"}
    stats = []
    for k, g in d.groupby("label_type"):
        v = g.lead_time_s.to_numpy()
        stats.append(dict(k=k, n=len(v), p10=np.percentile(v, 10), q1=np.percentile(v, 25), med=np.median(v),
                          q3=np.percentile(v, 75), p90=np.percentile(v, 90)))
    S = pd.DataFrame(stats).sort_values("med")
    fig, ax = plt.subplots(figsize=(ONE, 2.1))
    for i, r in enumerate(S.itertuples()):
        ax.plot([r.p10, r.p90], [i, i], color=BLUE, lw=1.2, solid_capstyle="round")
        ax.add_patch(plt.Rectangle((r.q1, i - 0.28), r.q3 - r.q1, 0.56, fc="#cde2fb", ec=BLUE, lw=1))
        ax.plot([r.med, r.med], [i - 0.28, i + 0.28], color=INK, lw=1.5)
        ax.text(r.p90 + 3, i, f"{r.med:.0f} s  (n={r.n:,})", va="center", fontsize=6.5, color=INK2)
    ax.set_yticks(range(len(S)), [names[k] for k in S.k]); ax.set_ylim(-0.6, len(S) - 0.4)
    ax.grid(axis="y", visible=False); ax.set_xlim(0, S.p90.max() * 1.55)
    ax.set_xlabel("seconds of a person's time per label")
    ax.set_title("Labelling from scratch (no prediction): median, IQR, p10–p90", loc="left", color=INK2)
    save(fig, "fig8_labeling_time")


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for f in (fig1_pipeline, fig2_stage_time, fig3_size_constancy, fig4_stage_ladder, fig5_reef_lengths, fig6_coverage, fig7_species, fig8_labeling_time):
        f()
