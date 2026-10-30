"""Head/tail: the mask rule against the trained SimCC snout/fork model and against the rule's head with the model's fork.

  rule    the SAM 3.1 mask rule (PCA axis of the mask, tail at the narrow end; production's predictor re-run on
          the same frames, "SAM rule (v2)" in the experiment)
  model   both points from the SimCC model (UCSD-E4E/2026-10-22_headtail_keypoints, run simcc_sam, epoch 12); what
          fishsense-services head/tail v5 measures real fish from (cea1ec5; fish models keep the rule)
  hybrid  the rule's head with the model's fork: of the rule's two endpoints, the one farther from the model's
          fork is the head (so the model sets the orientation), and the fork is the model's

All three come from one file, the experiment's results/model_keypoints_simcc_sam.csv (test split; seed "human":
crop at the human dot's SAM box, "auto": at the automatic dot's), so they keypoint the same SAM box per frame.

Pool (fish models, tape truth, stored calibration of the paired slate dive, e2e_measurement/score.py): per-fish
production estimator, p90 over the frames of one model in one dive, error against tape; MAE over fish, overall
and per model. Configurations C (human dot) and E (automatic dot), as score.py's ladder.
Reef (real fish, no tape; e2e_measurement/tail/frames.csv): human-dot crops on the dives with a stored
calibration. Endpoint distance from the human click as a fraction of the human length, each method in its own
orientation; swapped = the method's head is nearer the human tail. d = automatic / human length - 1, same dot
and calibration.

Hold-out by physical dive (physical_dives.py): test dives 94 and 114 each have a duplicate record (91, 106)
in the model's training split, holding a byte-identical copy of one of their images (18457 = 17687,
16882 = 16107; one training click each). "physical" drops both; "record" is the experiment's split.
Only frames where every method measured are scored. 95% intervals resample whole dives (2,000 draws);
paired differences use the same draws.

Writes analysis/codesign/results/headtail_compare_{pool,reef}.csv.
Run: uv run python analysis/codesign/headtail_compare.py
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from fishsense_cscw.paths import REPO

sys.path.insert(0, str(REPO / "e2e_measurement"))
import score as S  # noqa: E402

KP = REPO.parent / "2026-10-22_headtail_keypoints/results/model_keypoints_simcc_sam.csv"
METHODS = ("rule", "model", "hybrid")
LEAKED = (94, 114)
DRAWS, RNG = 2000, np.random.default_rng(0)


def keypoints():
    """Per (image, seed): head and tail of each method."""
    M = pd.read_csv(KP)
    M = M[(M.split == "test") & (M.status == "predicted") & (M.sam_status == "predicted")]
    rh, rt = M[["sam_head_x", "sam_head_y"]].to_numpy(), M[["sam_tail_x", "sam_tail_y"]].to_numpy()
    mh, mt = M[["head_x", "head_y"]].to_numpy(), M[["tail_x", "tail_y"]].to_numpy()
    flip = np.linalg.norm(rh - mt, axis=1) < np.linalg.norm(rt - mt, axis=1)   # the rule's head is the end farther from the fork
    hh = np.where(flip[:, None], rt, rh)
    P = {"rule": (rh, rt), "model": (mh, mt), "hybrid": (hh, mt)}
    out = M[["image_id", "seed", "dot_x", "dot_y"]].copy()
    for m, (h, t) in P.items():
        out[[f"{m}_hx", f"{m}_hy"]], out[[f"{m}_tx", f"{m}_ty"]] = h, t
    return out.set_index(["image_id", "seed"])


def boot(df, stat, by="dive"):
    """Point estimate and 95% interval of stat(df), resampling whole dives."""
    groups = {k: g for k, g in df.groupby(by)}
    keys = np.array(list(groups))
    # a dive drawn twice counts as two dives (its fish twice), so each draw renumbers the dives it holds
    draws = [stat(pd.concat([groups[k].assign(**{by: i}) for i, k in enumerate(RNG.choice(keys, len(keys)))])) for _ in range(DRAWS)]
    return stat(df), np.nanpercentile(draws, 2.5, axis=0), np.nanpercentile(draws, 97.5, axis=0)


def pool(K):
    F = pd.read_csv(REPO / "e2e_measurement/frames.psv", sep="|").drop_duplicates("image_id")
    F = F[F.content.fillna("").str.contains("Fish Model|Ruler")].copy()
    F["target"] = F.content.str.split(", ").str[-1]
    stored, _, intr = S.calibrations()
    rows = []
    for r in F.itertuples():
        cal = stored.get(S.PAIR.get(int(r.dive_id)))
        for config, seed in (("C human dot", "human"), ("E automatic dot", "auto")):
            if cal is None or (r.image_id, seed) not in K.index:
                continue
            k = K.loc[(r.image_id, seed)]
            x, y = (r.laser_x, r.laser_y) if seed == "human" else (k.dot_x, k.dot_y)
            Kc = intr[int(r.camera_id)]
            Z = S.depth(Kc, cal[0], cal[1], x, y)
            if not Z > 0:
                continue
            row = dict(image_id=r.image_id, dive=int(r.dive_id), target=r.target, config=config, L_true=S.KNOWN[r.target])
            for m in METHODS:
                row[m] = S.length(Kc, Z, k[f"{m}_hx"], k[f"{m}_hy"], k[f"{m}_tx"], k[f"{m}_ty"])
            rows.append(row)
    P = pd.DataFrame(rows).dropna()

    # one row per fish (a model in a dive): its p90 error against tape per method
    G = P.groupby(["config", "dive", "target"])
    FT = pd.DataFrame({m: G[m].apply(S.p90) / G.L_true.first() - 1 for m in METHODS}).reset_index()
    FT[[f"abs_{m}" for m in METHODS]] = FT[list(METHODS)].abs().to_numpy()

    out = []
    for hold, drop in (("record", ()), ("physical", LEAKED)):
        for config, f in FT[~FT.dive.isin(drop)].groupby("config"):
            g = P[(P.config == config) & ~P.dive.isin(drop)]
            for target in ["all"] + sorted(f.target.unique()):
                ff = f if target == "all" else f[f.target == target]
                gg = g if target == "all" else g[g.target == target]
                cols = [f"abs_{m}" for m in METHODS]
                stat = lambda d: np.append(d[cols].mean().to_numpy(), d[cols[1:]].mean().to_numpy() - d[cols[0]].mean())
                est, lo, hi = boot(ff, stat)
                row = dict(holdout=hold, config=config, target=target, frames=len(gg), fish=len(ff), dives=ff.dive.nunique())
                for i, m in enumerate(METHODS):
                    row[f"{m}_fish_p90_mae"] = f"{100 * est[i]:.1f} ({100 * lo[i]:.1f}-{100 * hi[i]:.1f})"
                for i, m in enumerate(METHODS[1:], start=3):
                    row[f"{m}_minus_rule"] = f"{100 * est[i]:+.1f} ({100 * lo[i]:+.1f} to {100 * hi[i]:+.1f})"
                for m in METHODS:
                    row[f"{m}_frame_median"] = round(100 * (gg[m] / gg.L_true - 1).median(), 1)
                out.append(row)
    return pd.DataFrame(out)


def reef(K):
    T = pd.read_csv(REPO / "e2e_measurement/tail/frames.csv")
    T = T[T.set == "reef"]
    stored, _, intr = S.calibrations()
    rows = []
    for r in T.itertuples():
        cal = stored.get(int(r.dive_id))
        if cal is None or (r.image_id, "human") not in K.index:
            continue
        k = K.loc[(r.image_id, "human")]
        Kc = intr[int(r.camera_id)]
        Z = S.depth(Kc, cal[0], cal[1], r.laser_x, r.laser_y)
        hh, ht = np.array([r.head_x, r.head_y]), np.array([r.tail_x, r.tail_y])
        Lpx = np.linalg.norm(ht - hh)
        Lh = S.length(Kc, Z, *hh, *ht)
        for m in METHODS:
            h, t = np.array([k[f"{m}_hx"], k[f"{m}_hy"]]), np.array([k[f"{m}_tx"], k[f"{m}_ty"]])
            rows.append(dict(image_id=r.image_id, dive=int(r.dive_id), method=m, snout=np.linalg.norm(h - hh) / Lpx,
                             fork=np.linalg.norm(t - ht) / Lpx, swapped=np.linalg.norm(h - ht) < np.linalg.norm(h - hh),
                             d=S.length(Kc, Z, *h, *t) / Lh - 1))
    R = pd.DataFrame(rows)
    out = []
    for m, g in R.groupby("method", sort=False):
        stat = lambda d: np.array([d.snout.median(), d.fork.median(), d.swapped.mean(), d.d.abs().mean(), d.d.median(), (d.d.abs() <= 0.1).mean()])
        est, lo, hi = boot(g, stat)
        row = dict(method=m, frames=len(g), dives=g.dive.nunique())
        for i, name in enumerate(("snout_median", "fork_median", "swapped", "mean_abs_d", "median_d", "within_10pct")):
            row[name] = f"{100 * est[i]:.1f} ({100 * lo[i]:.1f}-{100 * hi[i]:.1f})"
        if m != "rule":
            W = R.pivot_table(index=["image_id", "dive"], columns="method", values="d").reset_index()
            dd = boot(W, lambda w: np.array([(w[m].abs() - w.rule.abs()).mean()]))
            row["mean_abs_d_minus_rule"] = f"{100 * dd[0][0]:+.1f} ({100 * dd[1][0]:+.1f} to {100 * dd[2][0]:+.1f})"
        out.append(row)
    return pd.DataFrame(out)


def main():
    K = keypoints()
    pd.set_option("display.width", 250, "display.max_columns", 30)
    P = pool(K)
    P.to_csv(REPO / "analysis/codesign/results/headtail_compare_pool.csv", index=False)
    print("POOL (tape), per-fish p90 MAE %, 95% CI over dives\n", P.to_string(index=False))
    R = reef(K)
    R.to_csv(REPO / "analysis/codesign/results/headtail_compare_reef.csv", index=False)
    print("\nREEF (human clicks), %\n", R.to_string(index=False))


if __name__ == "__main__":
    main()
