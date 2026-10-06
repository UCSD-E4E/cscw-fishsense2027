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
  fig9_slate_detector  slate-frame detector: precision-recall; per-dive recall
  fig10_size_measures  apparent-size measures for size-constancy calibration, scored against tape
  fig11_laser_recall   laser detector: found / wrong spot / missed by colour and setting
  fig12_laser_position laser detector: distance of confident detections from the human dot
  fig13_headtail_examples automatic vs human head/tail: typical reef fish and pool failure modes
  fig14_headtail_error automatic head and tail distance from the human clicks on reef fish

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
    # no timestamps in the files, so a rebuild from the same data is byte-identical
    fig.savefig(OUT / f"{name}.pdf", metadata={"CreationDate": None, "ModDate": None})
    fig.savefig(OUT / f"{name}.png", metadata={"Software": None})
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
    fig, (a, b) = plt.subplots(1, 2, figsize=(TWO, 3.0), gridspec_kw=dict(width_ratios=[1.15, 1]))
    ex = next(r for r in rows if r["dive"] == 71)
    t0 = ex["tv_true"]; x = ex["t"] - t0
    k = np.sum(ex["s"] * (ex["t"] - ex["tv"])) / np.sum((ex["t"] - ex["tv"]) ** 2)
    xx = np.linspace(min(ex["tv"] - t0, 0) - 5, x.max() + 10, 50)
    pred = k * (ex["t"] - ex["tv"])
    r2 = 1 - np.sum((ex["s"] - pred) ** 2) / np.sum((ex["s"] - ex["s"].mean()) ** 2)
    a.plot(xx, k * (xx + t0 - ex["tv"]), color=BLUE, lw=1.5)
    a.scatter(x, ex["s"], s=16, color=BLUE, edgecolor="white", linewidth=0.5, zorder=3)
    a.text(0.04, 0.92, f"each dot: one slate frame\nline: size \u221d distance from vanishing point\nR\u00b2 = {r2:.3f}",
           transform=a.transAxes, va="top", fontsize=6.5, color=INK2, linespacing=1.4)
    a.set_xlim(xx.min(), xx.max()); a.set_ylim(0, ex["s"].max() * 1.08)
    a.set_xlabel("dot position along the laser line, px (0 = vanishing point)"); a.set_ylabel("apparent slate size, px")
    a.set_title("(a) one session: size shrinks to zero at the vanishing point", loc="left", color=INK2)
    # (b) every session against TAPE: the stored calibration is not ground truth (it trusts the slate template and
    # the mount), so each calibration is scored by the length it gives tape-measured fish models in the paired dive
    T = pd.read_csv(REPO / "calibration_analysis/e1j_size_constancy/tape_by_session.csv")
    M = T.pivot(index="session", columns="cal", values="mae") * 100
    order = M["known size"].sort_values().index; y = np.arange(len(order))
    series = [("known size", "known size + template (production)", MUTED, 0.22),
              ("unknown size (labelled)", "unknown size, human corners", BLUE, 0.0),
              ("label-free", "unknown size, no labels", ORANGE, -0.22)]
    for key, lab, col, dy in series:
        b.scatter(M.loc[order, key], y + dy, s=20, color=col, edgecolor="white", linewidth=0.5, zorder=3,
                  label=f"{lab}: {M[key].mean():.1f}%")
    b.set_yticks(y, [f"session {i}" for i in order]); b.grid(axis="y", visible=False)
    b.set_xlim(0, M.max().max() * 1.12)
    b.set_xlabel("length error vs tape, % (fish models, paired dive)")
    b.set_title("(b) every session, scored against tape", loc="left", color=INK2)
    b.legend(loc="upper center", bbox_to_anchor=(0.45, -0.25), frameon=False, fontsize=6.5, ncol=1,
             title="calibration (mean over sessions)", title_fontsize=6.5, scatterpoints=1, handletextpad=0.3)
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
    ax.scatter(P[:, 0], P[:, 1], s=10, color=BLUE, edgecolor="white", linewidth=0.4, label="one frame", zorder=3)
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


# ---------------------------------------------------------------- fig 9
def fig9_slate_detector():
    """Slate-frame detector (2026-10-03_slate_detector), dive-grouped cross-validation.
    (a) precision-recall over all frames except the one-off cutting-board test slate;
    (b) q1 model, per dive with slate frames: share of its slate frames found at p >= 0.5."""
    fig, (a, b) = plt.subplots(1, 2, figsize=(TWO, 2.4), gridspec_kw=dict(width_ratios=[1, 1.15]))
    # the one-off cutting-board test slate ("Slate not in list") is not a deployed duct-tape slate
    d = pd.read_csv(REPO / "data/slate_detector/oof_cv_q1.csv")
    d = d[d.cutting_board == 0].sort_values("p_slate", ascending=False)
    tp = d.label.cumsum().to_numpy(); k = np.arange(1, len(d) + 1)
    prec, rec = tp / k, tp / d.label.sum()
    ap = np.sum(np.diff(np.r_[0, rec]) * prec)
    a.plot(rec, prec, color=BLUE, lw=1.6)
    at = d.p_slate >= 0.5; tp5 = int((at & (d.label == 1)).sum())
    a.scatter([tp5 / d.label.sum()], [tp5 / at.sum()], s=22, color=BLUE, edgecolor="white", linewidth=0.6, zorder=3)
    a.annotate(f"p \u2265 0.5: precision {tp5 / at.sum():.1%}, recall {tp5 / d.label.sum():.1%}",
               (tp5 / d.label.sum(), tp5 / at.sum()), xytext=(-8, -14), textcoords="offset points", ha="right", fontsize=6.5, color=INK2)
    a.text(0.902, 0.55, f"AP {ap:.3f}; {int(d.label.sum()):,} slate of {len(d):,} frames", fontsize=6.5, color=INK2)
    a.set_xlim(0.9, 1.003); a.set_ylim(0.5, 1.02); a.set_xlabel("recall (slate frames found)"); a.set_ylabel("precision")
    a.set_title("(a) slate frames, held-out dives", loc="left", color=INK2)
    g = d[d.label == 1].groupby("dive_id").p_slate.agg(n="size", found=lambda v: (v >= 0.5).mean())
    bins = [("all", g.found == 1), ("50–99%", (g.found >= .5) & (g.found < 1)), ("1–49%", (g.found > 0) & (g.found < .5)),
            ("none", g.found == 0)]
    y = np.arange(len(bins))[::-1]; counts = [int(m.sum()) for _, m in bins]
    b.barh(y, counts, height=0.6, color=BLUE)
    for yi, c in zip(y, counts):
        b.text(c + 2, yi, str(c), va="center", fontsize=7, color=INK)
    b.set_yticks(y, [lab for lab, _ in bins]); b.grid(axis="y", visible=False); b.set_xlim(0, max(counts) * 1.15)
    b.set_ylabel("slate frames found"); b.set_xlabel("dives")
    b.set_title(f"(b) per dive: {len(g) - counts[-1]} of {len(g)} dives have \u2265 1 slate frame found", loc="left", color=INK2)
    fig.tight_layout(); save(fig, "fig9_slate_detector")


# ---------------------------------------------------------------- fig 10
def fig10_size_measures():
    """How the slate's apparent size is measured, scored against tape (tape_by_session.py).
    One row per size measure; dots are the 10 calibration sessions, the bar their mean."""
    T = pd.read_csv(REPO / "calibration_analysis/e1j_size_constancy/tape_by_session.csv")
    M = T.pivot(index="session", columns="cal", values="mae") * 100
    methods = [("known size", "known size + template (production)", True),
               ("unknown size (labelled)", "human corner spread", True),
               ("sam3_box", "SAM 3.1 mask from human box", True),
               ("label-free", "image registration", False),
               ("sam3_text", "SAM 3.1 mask, text prompt", False)]
    methods = [m for m in methods if m[0] in M]
    order = sorted(methods, key=lambda m: -M[m[0]].mean())
    fig, ax = plt.subplots(figsize=(ONE, 2.4))
    rng = np.random.default_rng(0)
    for i, (key, lab, labelled) in enumerate(order):
        col = MUTED if labelled else BLUE
        v = M[key].to_numpy(); jit = rng.uniform(-0.12, 0.12, len(v))
        ax.scatter(v, i + jit, s=12, color=col, alpha=0.55, edgecolor="none", zorder=2)
        ax.plot([v.mean()] * 2, [i - 0.3, i + 0.3], color=col, lw=2.2, zorder=3)
        ax.text(1.02, i, f"{v.mean():.1f}%", va="center", fontsize=7, color=INK, transform=ax.get_yaxis_transform())
    ax.set_yticks(range(len(order)), [lab for _, lab, _ in order]); ax.grid(axis="y", visible=False)
    ax.set_xlim(0, M.max().max() * 1.05); ax.set_ylim(-0.6, len(order) - 0.4)
    ax.set_xlabel("length error vs tape, % (dots: 10 sessions; bar: mean)")
    ax.set_title("Measuring the slate's apparent size", loc="left", color=INK2, pad=14)
    ax.text(1.0, 1.02, "grey: needs human labels · blue: no labels", transform=ax.transAxes, ha="right", va="bottom",
            fontsize=6.5, color=INK2)
    save(fig, "fig10_size_measures")


# ---------------------------------------------------------------- fig 11, 12
def _t3_dots():
    """Production laser detector against human dots drawn with no pre-fill (T3; frames with a dot)."""
    from fishsense_cscw import laser_detection as T3
    d = T3.load()
    return T3, d[(d.condition == "production") & d.has_dot]


def fig11_laser_recall():
    """Does the detector find the dot? Outcome per laser colour and setting."""
    T3, d = _t3_dots()
    groups = [("all", d), ("red, reef", d[(d.wavelength == "red") & (d.environment == "reef")]),
              ("red, pool", d[(d.wavelength == "red") & (d.environment == "pool")]),
              ("green, reef", d[(d.wavelength == "green") & (d.environment == "reef")]),
              ("green, pool", d[(d.wavelength == "green") & (d.environment == "pool")])]
    parts = [("found", "found", BLUE), ("confident-wrong", "confident, wrong spot", ORANGE), ("missed", "missed", "#c3c2b7")]
    fig, a = plt.subplots(figsize=(ONE, 2.3))
    y = np.arange(len(groups))[::-1]
    for yi, (name, g) in zip(y, groups):
        left = 0.0
        for key, lab, col in parts:
            w = (g.outcome == key).mean() * 100
            a.barh(yi, w, left=left, height=0.62, color=col, edgecolor="white", linewidth=1, label=lab if name == "all" else None)
            if key == "found":
                a.text(w - 1.5, yi, f"{w:.0f}%", ha="right", va="center", fontsize=6.5, color="white")
            left += w
        a.text(101.5, yi, f"n={len(g):,}", va="center", fontsize=6.5, color=INK2)
    a.set_yticks(y, [n for n, _ in groups]); a.set_xlim(0, 100); a.grid(axis="y", visible=False)
    a.set_xlabel("share of frames with a laser dot, %")
    a.set_title("Does the laser detector find the dot?", loc="left", color=INK2)
    a.legend(loc="upper center", bbox_to_anchor=(0.45, -0.25), ncol=3, frameon=False, fontsize=6.5, handlelength=1.0)
    save(fig, "fig11_laser_recall")


def fig12_laser_position():
    """Where confident detections land relative to the human dot (cumulative, log distance)."""
    T3, d = _t3_dots()
    v = np.clip(np.sort(d[d.present].distance_px.to_numpy()), 0.05, None)
    fig, b = plt.subplots(figsize=(ONE, 2.3))
    b.step(v, np.arange(1, len(v) + 1) / len(v) * 100, where="post", color=BLUE, lw=1.6)
    b.axvline(T3.HIT_RADIUS_PX, color=MUTED, lw=1, ls=":")
    within = (v <= T3.HIT_RADIUS_PX).mean() * 100
    b.text(T3.HIT_RADIUS_PX * 1.15, 40, f"{within:.0f}% within\n{T3.HIT_RADIUS_PX:.0f} px", fontsize=6.5, color=INK2)
    b.text(0.12, 92, f"median {np.median(v):.1f} px\n(n={len(v):,})", fontsize=6.5, color=INK2, va="top")
    b.set_xscale("log"); b.set_xlim(0.1, 3000); b.set_ylim(0, 101)
    b.set_xticks([0.1, 1, 10, 100, 1000], ["0.1", "1", "10", "100", "1000"])
    b.set_xlabel("distance from the human dot, px"); b.set_ylabel("confident detections, cumulative %")
    b.set_title("Where the laser detector puts the dot", loc="left", color=INK2)
    save(fig, "fig12_laser_position")


# ---------------------------------------------------------------- fig 13, 14
def fig13_headtail_examples():
    """Automatic head/tail vs the human clicks: three typical reef fish, three pool failure modes.
    Crops and crop-local points from e2e_measurement/tail/headtail_examples.py."""
    import matplotlib.patheffects as pe
    from PIL import Image
    E = pd.read_csv(REPO / "data/headtail_examples/examples.csv")
    E = pd.concat([E[E.kind == "typical"], E[E.kind == "failure"]])
    fig, axes = plt.subplots(2, 3, figsize=(TWO, 3.5))
    halo = [pe.withStroke(linewidth=2.6, foreground="black")]
    for ax, r in zip(axes.ravel(), E.itertuples()):
        ax.imshow(Image.open(REPO / f"data/headtail_examples/{r.image_id}.jpg")); ax.set_axis_off()
        ax.plot([r.human_head_x, r.human_tail_x], [r.human_head_y, r.human_tail_y], color="white", lw=1.6, path_effects=halo)
        ax.scatter([r.human_head_x, r.human_tail_x], [r.human_head_y, r.human_tail_y], s=36, facecolor="none",
                   edgecolor="white", linewidth=1.6, zorder=3, path_effects=halo)
        ax.plot([r.auto_head_x, r.auto_tail_x], [r.auto_head_y, r.auto_tail_y], color=ORANGE, lw=1.4, ls="--")
        ax.scatter([r.auto_head_x, r.auto_tail_x], [r.auto_head_y, r.auto_tail_y], s=16, color=ORANGE, zorder=4,
                   edgecolor="black", linewidth=0.4)
        ax.set_title(f"{r.label}\nautomatic / human length {r.ratio:.2f}", fontsize=7, color=INK2, loc="left")
    fig.text(0.01, 0.005, "white: human clicks   orange: automatic (SAM 3.1 mask at the dot + keypointer)",
             fontsize=6.5, color=INK2)
    fig.tight_layout(rect=(0, 0.035, 1, 1), h_pad=0.6); save(fig, "fig13_headtail_examples")


def fig14_headtail_error():
    """Reef fish: how far the automatic head and tail land from the human clicks, % of body length
    (mask seeded at the human dot, so only the head/tail stage differs)."""
    F = pd.read_csv(REPO / "e2e_measurement/tail/frames.csv").set_index("image_id")
    K = pd.read_csv(REPO / "e2e_measurement/tail/keypoints.csv")
    K = K[(K.seed == "human") & K.head_x.notna()].set_index("image_id")
    J = K.join(F[["head_x", "head_y", "tail_x", "tail_y", "set"]], rsuffix="_h", how="inner")
    J = J[(J.set == "reef") & J.head_x_h.notna()]
    H = J[["head_x_h", "head_y_h"]].to_numpy(); T = J[["tail_x", "tail_y"]].to_numpy()
    h = J[["head_x", "head_y"]].to_numpy(); t = J[["prod_tail_x", "prod_tail_y"]].to_numpy()
    L = np.linalg.norm(T - H, axis=1)
    swap = np.linalg.norm(h - T, axis=1) + np.linalg.norm(t - H, axis=1) < np.linalg.norm(h - H, axis=1) + np.linalg.norm(t - T, axis=1)
    h2 = np.where(swap[:, None], t, h); t2 = np.where(swap[:, None], h, t)
    eh = np.linalg.norm(h2 - H, axis=1) / L * 100; et = np.linalg.norm(t2 - T, axis=1) / L * 100
    fig, ax = plt.subplots(figsize=(ONE, 2.3))
    for v, lab, col in ((eh, "head", BLUE), (et, "tail", ORANGE)):
        v = np.sort(v)
        ax.step(v, np.arange(1, len(v) + 1) / len(v) * 100, where="post", color=col, lw=1.6, label=f"{lab}: median {np.median(v):.1f}%")
    ax.set_xlim(0, 30); ax.set_ylim(0, 101)
    ax.set_xlabel("distance from the human click, % of body length"); ax.set_ylabel("reef frames, cumulative %")
    ax.set_title(f"Automatic head and tail on reef fish (n={len(eh)})", loc="left", color=INK2)
    ax.legend(loc="lower right", frameon=False, fontsize=6.5)
    save(fig, "fig14_headtail_error")


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for f in (fig1_pipeline, fig2_stage_time, fig3_size_constancy, fig4_stage_ladder, fig5_reef_lengths, fig6_coverage, fig7_species, fig8_labeling_time, fig9_slate_detector, fig10_size_measures, fig11_laser_recall, fig12_laser_position, fig13_headtail_examples, fig14_headtail_error):
        f()
