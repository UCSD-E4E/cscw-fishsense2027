"""Per dive: time underwater vs the time to turn the dive into measurements, by people and by the machine.

Underwater time (LOWER BOUND): last minus first capture time of the dive's canonical images
(data/db_extracts/dive_effort.psv, sql/extract_dive_effort.sql; camera clock). Divers do not photograph
continuously, so the dive was at least this long. Excluded as implausible: span <= 0 (one frame or a
clock fault) and span > 3 h (no single dive lasts that long; clock errors or several dives filed as one).
Field = environment "reef", pool = "pool" (data/db_extracts/dive_environment.psv, T3's keyword
heuristic on the dive path); "other" is reported separately.

Human labelling time, (a) estimated for every dive = frames x per-task median time:
  laser dot      every canonical image (production sends every image to the laser task)
  snout/fork, species
                 images with a valid laser label (completed, not superseded, x and y set), the cohort
                 production sends to both tasks. Counted where the dive's laser labelling is done
                 (>= 95% of images labelled); otherwise images x the fleet median share of valid dots on
                 finished dives of the same environment (flagged imputed).
  slate corners  images any record calls a slate: a slate-corner label, a live species answer "Slate,
                 Laser on slate", or the slate-frame detector (labelled manifest, out-of-fold p >= 0.5, scan
                 "likely_slate"). The detector saw a median 10% of a dive's images, so a count is taken as
                 complete only where it saw >= 90% of them or the dive's species labelling is done;
                 elsewhere the median of complete dives of the same environment (flagged imputed).
  per-task times medians of Label Studio lead_time for annotations drawn without a pre-fill
                 (data/db_extracts/lead_times_by_dive.psv), intervals resampling dives; cross-checked
                 against data/labeling/lead_times.csv.
(b) recorded, for labelled dives: the sum of lead_time over the dive's annotations in all four tasks,
  split by drawn from scratch vs pre-filled. lead_time counts the time a task was open, so idle tabs add
  hours; sums are given capped at 300 s per annotation (the effort study's plausibility cut,
  fishsense_cscw/laser_pairs.py) and uncapped. Only annotations stored in the database count.

Machine time: wall-clock of the per-dive workflow runs on the workflow engine (data/temporal/
workflow_runs.csv, 2026-09-01..10-01; per-dive child runs only to 2026-09-16): preprocessing (laser,
head/tail, species, slate), prediction (laser, head/tail), laser auto-accept, frame clustering, laser
calibration, depths, measurement. Intake (IngestDiveWorkflow) carries a folder name, not a dive id, so its
median run is added to every dive as a constant. A dive counts only when the window holds both its
preprocessing and its prediction runs (others had only re-runs of single stages in the window). Most runs in the window are re-runs that skip finished
work, so per dive and stage the LONGEST completed run is taken as the one that did the work (checked
against the dive's laser-prediction write times). Wall-clock includes queueing and worker start-up, so it
is an upper bound on compute. This is the current pipeline (2026-09), not the 2023-24 one. Label Studio
project population and label sync are not processing and are excluded.

Not included: the time between a dive and its data reaching the lab (organisational delay).
Intervals: 95%, resampling dives (2,000 draws).

Writes analysis/codesign/results/dive_time_{dives,tasks,summary}.csv and figures/dive_time.{pdf,png}.
Run: uv run python analysis/codesign/dive_time.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from fishsense_cscw.paths import REPO

OUT = REPO / "analysis/codesign/results"; FIG = REPO / "analysis/codesign/figures"
SLATE = REPO.parent / "2026-10-03_slate_detector"
N_BOOT, MAX_SPAN_H, CAP_S, DONE = 2000, 3.0, 300.0, 0.95
COLS = ("dive_id camera_id images first last laser_labelled valid_laser species_labelled slate_species preds conf "
        "lp_first lp_last hp_first hp_last dp_first dp_last").split()
STAGES = {"PreprocessLaserImagesWorkflow": "preprocess", "PreprocessHeadtailImagesWorkflow": "preprocess",
          "PreprocessSpeciesImagesWorkflow": "preprocess", "PreprocessSlateImagesWorkflow": "preprocess",
          "PredictLaserImagesWorkflow": "prediction", "PredictHeadtailImagesWorkflow": "prediction",
          "EvaluateLaserAutoAcceptWorkflow": "prediction", "DiveFrameClusteringWorkflow": "preprocess",
          "PerformLaserCalibrationWorkflow": "calibration", "ComputeLaserDepthsWorkflow": "depths + measurement",
          "MeasureFishWorkflow": "depths + measurement"}
TASKS = {"laser": "laser dot", "headtail": "snout/fork", "species": "species", "slate": "slate corners"}


def boot(x: pd.Series | np.ndarray, f=np.median, seed=0):
    x = np.asarray(x, float); x = x[np.isfinite(x)]; rng = np.random.default_rng(seed)
    return tuple(np.percentile([f(x[rng.integers(0, len(x), len(x))]) for _ in range(N_BOOT)], [2.5, 97.5])) if len(x) else (np.nan, np.nan)


def cboot(d: pd.DataFrame, stat, key="dive_id", seed=0):
    rng = np.random.default_rng(seed); g = [x for _, x in d.groupby(key)]
    return tuple(np.nanpercentile([stat(pd.concat([g[i] for i in rng.integers(0, len(g), len(g))])) for _ in range(N_BOOT)], [2.5, 97.5]))


def task_times(A):
    rows = {}
    L = pd.read_csv(REPO / "data/labeling/lead_times.csv"); L = L[L.seeded == "f"]
    ref = {"laser": "laser_dot", "headtail": "head_tail", "species": "species", "slate": "slate_corners"}
    for k, name in TASKS.items():
        s = A[(A.kind == k) & ~A.seeded]
        rows[k] = dict(task=name, annotations=len(s), dives=s.dive_id.nunique(), median_s=s.lead.median(),
                       ci=cboot(s, lambda z: z.lead.median()), lead_times_csv_median_s=L[L.label_type == ref[k]].lead_time_s.median())
    return pd.DataFrame(rows).T


def slate_frames(D):
    man = pd.read_csv(SLATE / "data/manifest.csv"); scan = pd.read_csv(SLATE / "runs/scan/predictions.csv")
    oof = pd.read_csv(REPO / "data/slate_detector/oof_cv_q1.csv")
    pos = pd.concat([man[man.label == 1][["image_id", "dive_id"]], oof[oof.p_slate >= 0.5][["image_id", "dive_id"]],
                     scan[scan.flag == "likely_slate"][["image_id", "dive_id"]]]).drop_duplicates("image_id")
    seen = pd.concat([man[["image_id", "dive_id"]], scan[["image_id", "dive_id"]]]).drop_duplicates("image_id").groupby("dive_id").size()
    return pos.groupby("dive_id").size(), seen


def machine(D):
    W = pd.read_csv(REPO / "data/temporal/workflow_runs.csv", parse_dates=["start_time", "close_time"])
    W = W[W.status == "COMPLETED"].copy(); W["s"] = (W.close_time - W.start_time).dt.total_seconds()
    ingest = W[W.workflow_type == "IngestDiveWorkflow"].s
    W = W[W.workflow_type.isin(STAGES)].copy(); W["dive_id"] = W.workflow_id.str.extract(r"-(\d+)$")[0].astype(int)
    longest = W.sort_values("s").groupby(["dive_id", "workflow_type"]).tail(1)
    # check: the longest predict-laser run is the one that wrote the dive's predictions
    pl = longest[longest.workflow_type == "PredictLaserImagesWorkflow"].merge(D[["dive_id", "lp_first", "lp_last"]], on="dive_id")
    pl = pl.dropna(subset=["lp_first"])
    tol = pd.Timedelta(seconds=5)
    inside = ((pd.to_datetime(pl.lp_first, utc=True) >= pl.start_time - tol) & (pd.to_datetime(pl.lp_last, utc=True) <= pl.close_time + tol))
    per = longest.assign(stage=longest.workflow_type.map(STAGES)).pivot_table(index="dive_id", columns="stage", values="s", aggfunc="sum")
    per["machine_s"] = per.sum(axis=1) + ingest.median()
    return per, dict(ingest_runs=len(ingest), ingest_median_s=ingest.median(), predict_runs_checked=len(pl), predict_runs_matching=int(inside.sum()),
                     window=f"{W.start_time.min():%Y-%m-%d}..{W.close_time.max():%Y-%m-%d}")


def main():
    D = pd.read_csv(REPO / "data/db_extracts/dive_effort.psv", sep="|", header=None, names=COLS)
    D = D.merge(pd.read_csv(REPO / "data/db_extracts/dive_environment.psv", sep="|", header=None, names=["dive_id", "env"]), on="dive_id", how="left")
    D["env"] = D.env.fillna("other")
    D["underwater_h"] = (pd.to_datetime(D["last"]) - pd.to_datetime(D["first"])).dt.total_seconds() / 3600
    D["span_flag"] = np.select([D.underwater_h <= 0, D.underwater_h > MAX_SPAN_H], ["span <= 0", f"span > {MAX_SPAN_H:g} h"], "ok")

    A = pd.read_csv(REPO / "data/db_extracts/lead_times_by_dive.psv", sep="|", header=None, names=["kind", "dive_id", "image_id", "lead", "seeded", "created"])
    A["seeded"] = A.seeded.eq("t")
    T = task_times(A); t = T.median_s.astype(float)

    # (a) estimated human time
    done = D.laser_labelled / D.images >= DONE
    share = (D.valid_laser / D.images)[done].groupby(D.env[done]).median()
    D["fish_frames"] = np.where(done, D.valid_laser, D.images * D.env.map(share).fillna(share.median()))
    D["fish_imputed"] = ~done
    sl, seen = slate_frames(D)
    slate_lab = A[A.kind == "slate"].groupby("dive_id").image_id.nunique()
    obs = pd.concat([sl, slate_lab, D.set_index("dive_id").slate_species], axis=1).max(axis=1)
    # a count is complete only where the detector saw >= 90% of the dive's images or species labelling is done
    D["slate_observed"] = (D.dive_id.map(seen).fillna(0) / D.images >= 0.9) | (D.species_labelled >= DONE * D.valid_laser) & (D.valid_laser > 0)
    D["slate_frames"] = D.dive_id.map(obs).fillna(0)
    med_slate = D[D.slate_observed].groupby("env").slate_frames.median()
    D.loc[~D.slate_observed, "slate_frames"] = D.loc[~D.slate_observed, "env"].map(med_slate).fillna(med_slate.median())
    D["human_est_h"] = (D.images * t["laser"] + D.fish_frames * (t["headtail"] + t["species"]) + D.slate_frames * t["slate"]) / 3600

    # (b) recorded
    A["capped"] = A.lead.clip(upper=CAP_S)
    rec = A.groupby(["dive_id", "seeded"]).agg(capped=("capped", "sum"), raw=("lead", "sum"), n=("lead", "size")).unstack("seeded")
    for col, key in (("scratch", False), ("prefilled", True)):
        for v in ("capped", "raw", "n"):
            D[f"rec_{col}_{v}"] = D.dive_id.map(rec[(v, key)] if (v, key) in rec.columns else pd.Series(dtype=float)).fillna(0)
    D["human_rec_h"] = (D.rec_scratch_capped + D.rec_prefilled_capped) / 3600
    D["human_rec_raw_h"] = (D.rec_scratch_raw + D.rec_prefilled_raw) / 3600
    D["recorded_complete"] = done & (D.rec_scratch_n + D.rec_prefilled_n > 0)

    # machine
    M, info = machine(D)
    D = D.merge(M, left_on="dive_id", right_index=True, how="left")
    # a dive's machine time counts only when the window holds both its preprocessing and its prediction runs
    D["machine_h"] = np.where(D.preprocess.notna() & D.prediction.notna(), D.machine_s / 3600, np.nan)

    OUT.mkdir(parents=True, exist_ok=True)
    D.drop(columns=["first", "last"]).to_csv(OUT / "dive_time_dives.csv", index=False, float_format="%.4f")
    T.to_csv(OUT / "dive_time_tasks.csv")
    ok = D[D.span_flag == "ok"]
    rows = []
    for env, X in [("field (reef)", ok[ok.env == "reef"]), ("pool", ok[ok.env == "pool"]), ("other", ok[ok.env == "other"]), ("all", ok)]:
        def add(q, s, f=np.median, unit=""):
            s = s.replace([np.inf, -np.inf], np.nan).dropna()
            lo, hi = boot(s, f)
            rows.append(dict(set=env, quantity=q, dives=len(s), value=f(s) if len(s) else np.nan, ci_lo=lo, ci_hi=hi))
        add("underwater time, h (lower bound)", X.underwater_h)
        add("estimated human labelling, h", X.human_est_h)
        add("estimated human labelling, h (counts not imputed)", X[~X.fish_imputed & X.slate_observed].human_est_h)
        add("recorded human labelling, h (capped 300 s; laser labelling done)", X[X.recorded_complete].human_rec_h)
        add("machine, h (dives with workflow runs)", X.machine_h)
        add("ratio estimated human / underwater", X.human_est_h / X.underwater_h)
        add("ratio recorded human / underwater", X[X.recorded_complete].human_rec_h / X[X.recorded_complete].underwater_h)
        add("ratio machine / underwater", X.machine_h / X.underwater_h)
        add("share of dives: estimated human > underwater", (X.human_est_h > X.underwater_h).astype(float), np.mean)
    S = pd.DataFrame(rows); S.to_csv(OUT / "dive_time_summary.csv", index=False, float_format="%.4f")

    pd.set_option("display.width", 220)
    print("Per-task median lead time (drawn without a pre-fill):"); print(T.to_string()); print()
    print("Excluded spans:", D.span_flag.value_counts().to_dict(), "by env:", D[D.span_flag != "ok"].groupby("env").size().to_dict())
    print("Imputed: fish frames on", int(D.fish_imputed.sum()), "dives; slate frames on", int((~D.slate_observed).sum()), "dives")
    print("Machine:", info, "; dives with any run:", int(D.machine_h.notna().sum()), "; ok-span dives with runs:", int(ok.machine_h.notna().sum()))
    print("Recorded (capped vs raw, all labelled dives): capped", round(D.human_rec_h.sum(), 1), "h, raw", round(D.human_rec_raw_h.sum(), 1), "h;",
          "pre-filled share of capped time", round((D.rec_prefilled_capped.sum() / (D.rec_scratch_capped + D.rec_prefilled_capped).sum()), 3))
    print(); print(S.round(3).to_string(index=False))

    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(3.4, 3.0))
    for env, m, c in (("reef", "o", "#1f77b4"), ("pool", "s", "#ff7f0e")):
        X = ok[ok.env == env]
        ax.scatter(X.underwater_h * 60, X.human_est_h * 60, s=8, marker=m, color=c, alpha=.7, label=f"people, {'field' if env == 'reef' else env}")
        Y = X.dropna(subset=["machine_h"])
        ax.scatter(Y.underwater_h * 60, Y.machine_h * 60, s=10, marker=m, facecolors="none", edgecolors="0.3", lw=.6,
                   label=f"machine, {'field' if env == 'reef' else env}")
    lim = [0.5, 3000]; ax.plot(lim, lim, color="0.5", lw=.8, ls="--"); ax.set_xscale("log"); ax.set_yscale("log"); ax.set_xlim(lim); ax.set_ylim(lim)
    ax.set_xlabel("time underwater, min (lower bound)"); ax.set_ylabel("processing time, min"); ax.legend(fontsize=6, frameon=False)
    fig.tight_layout(); FIG.mkdir(exist_ok=True)
    for ext in ("pdf", "png"):
        fig.savefig(FIG / f"dive_time.{ext}", dpi=300, metadata={"Author": None, "Creator": None} if ext == "pdf" else None)


if __name__ == "__main__":
    main()
