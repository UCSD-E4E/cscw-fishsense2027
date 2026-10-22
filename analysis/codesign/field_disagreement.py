"""Why automatic and human lengths disagree on field (reef) dives: which component is responsible.

Reference: the human pipeline (human laser dot, human head/tail clicks, the dive's stored laser
calibration from human slate-corner labels). There is no tape on the reef, so every number here is
agreement with the human pipeline, not accuracy.

Frames: human-measured reef frames on the 8 field dives with a stored calibration
(e2e_measurement/tail/frames.csv, set "reef"). The automatic track, as run in e2e_measurement/tail and
analysis/codesign/reef_size_constancy.py:
  dot          deployed laser detector run3 epoch_021 on the RAW (reef_dots.jsonl, dots.jsonl)
  head/tail    SAM 3.1 mask at the dot, production head/tail rule (fishsense-core FishHeadTailDetector)
               (keypoints.csv: seed "auto" = mask at the automatic dot, "human" = mask at the human dot)
  calibration  size constancy with SAM 3.1 sqrt(mask area) under the human dot on the dive's slate
               frames, |O| = 104 mm stand-in (reef_size_constancy.py); only 4 dives (341, 347, 349, 436)
               have >= 8 usable slate frames. The image-registration variant was run on pool sessions
               only, never on field dives, so it is not available here.

Swaps, one component at a time from the human pipeline (stage ladder):
  dot          automatic dot, human head/tail, stored calibration
  calibration  human dot, human head/tail, size-constancy calibration
  head/tail    human dot, SAM head/tail from the mask at the human dot, stored calibration
  dot+ht       automatic dot, SAM head/tail at the automatic dot, stored calibration
  all          automatic dot, SAM head/tail at the automatic dot, size-constancy calibration

Per frame: d = automatic / human - 1. Per fish: production's p90 estimator over each fish's frames
(fish = the Label Studio cluster, e2e_measurement/tail/reef_clusters.psv; an unclustered frame is its
own fish), then the ratio of the two p90 lengths.
Variance of log(automatic/human) is split between dives and within dives with the one-way random-
effects method-of-moments (ANOVA) estimator for unbalanced groups. 95% intervals resample whole dives
(2,000 draws); with 3-8 dives they are wide and the between-dive share is weakly identified.

Writes analysis/codesign/results/field_disagreement_{frames,summary,variance,headtail,species,calibration}.csv.
Run: uv run python analysis/codesign/field_disagreement.py
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from fishsense_cscw.paths import REPO

E1J = REPO / "calibration_analysis/e1j_size_constancy"; TAIL = REPO / "e2e_measurement/tail"
for p in (E1J, REPO / "e2e_measurement", TAIL, REPO / "analysis/codesign"):
    sys.path.insert(0, str(p))
import reef_labelfree as RL  # noqa: E402
import score as S  # noqa: E402
import evaluate as EV  # noqa: E402
import reef_size_constancy as RSC  # noqa: E402

OUT = REPO / "analysis/codesign/results"
N_BOOT = 2000
SWAPS = ["dot", "calibration", "head/tail", "dot+ht", "all"]
rng0 = 0


def sc_calibrations(reef, intr, cams):
    """The size-constancy calibrations of reef_size_constancy.py, rebuilt the same way (not re-stored)."""
    man = pd.read_csv(RSC.SLATE / "data/manifest.csv")
    L = pd.read_csv(REPO / "data/db_extracts/laser_dots.psv", sep="|", header=None, names=["image_id", "x", "y", "label"]).set_index("image_id")
    rows = []
    for dive in sorted(reef.dive_id.unique()):
        ids = [i for i in man[(man.dive_id == dive) & (man.label == 1)].image_id if i in L.index]
        fr = pd.DataFrame([dict(image_id=int(i), dive_id=int(dive), x=L.loc[i, "x"], y=L.loc[i, "y"],
                                size=RSC.size_under_dot(i, L.loc[i, "x"], L.loc[i, "y"])) for i in ids]).dropna(subset=["size"]) if ids else pd.DataFrame()
        if len(fr) >= RSC.MIN_FRAMES:
            rows.append(fr)
    cal, C, _ = RL.calibrate(intr, cams, pd.concat(rows, ignore_index=True), "SAM 3.1 under the dot (slate-project frames)")
    return cal, C


def frames():
    F, K, dots = EV.load(); stored, _, intr = S.calibrations()
    cams = {int(r.dive_id): int(r.camera_id) for r in pd.read_csv(REPO / "e2e_measurement/extrinsics.psv", sep="|").itertuples()}
    reef = F[(F.set == "reef") & F.head_x.notna() & F.dive_id.isin(stored)]
    sc, C = sc_calibrations(reef, intr, cams)
    Kx = K.set_index(["image_id", "seed"])
    cl = pd.read_csv(TAIL / "reef_clusters.psv", sep="|").drop_duplicates("image_id").set_index("image_id").cid
    out = []
    for r in reef.itertuples():
        Kc = intr[int(r.camera_id)]; dive = int(r.dive_id)
        hd = (r.laser_x, r.laser_y); ad = dots.get(r.image_id)
        hh = (r.head_x, r.head_y, r.tail_x, r.tail_y)
        def ht(seed):
            if (r.image_id, seed) not in Kx.index:
                return None
            k = Kx.loc[(r.image_id, seed)]
            return None if pd.isna(k.get("head_x")) else (k.head_x, k.head_y, *EV.tail_of(k, "prod"))
        def L(dot, h, cal):
            if dot is None or h is None or cal is None:
                return np.nan
            Z = S.depth(Kc, cal[0], cal[1], *dot)
            return S.length(Kc, Z, *h) if Z > 0 else np.nan
        cs, cc = stored[dive], sc.get(dive)
        rec = dict(image_id=r.image_id, dive_id=dive, fish=int(cl[r.image_id]) if r.image_id in cl.index else -int(r.image_id),
                   species=(str(r.content).split(", ", 1)[1] if ", " in str(r.content) else "unrecorded"),
                   green=str(r.laser_label).startswith("Green"), human=L(hd, hh, cs),
                   dot_px=np.hypot(ad[0] - hd[0], ad[1] - hd[1]) if ad else np.nan)
        rec.update({"dot": L(ad, hh, cs), "calibration": L(hd, hh, cc), "head/tail": L(hd, ht("human"), cs),
                    "dot+ht": L(ad, ht("auto"), cs), "all": L(ad, ht("auto"), cc)})
        hk = ht("human")
        if hk is not None:   # endpoint distances, human-seeded mask, better of the two head/tail assignments
            H, T = np.array(hh[:2]), np.array(hh[2:]); h, t = np.array(hk[:2], float), np.array(hk[2:], float)
            if np.linalg.norm(h - T) + np.linalg.norm(t - H) < np.linalg.norm(h - H) + np.linalg.norm(t - T):
                h, t = t, h
            Lh = np.linalg.norm(T - H); k = Kx.loc[(r.image_id, "human")]
            rec.update(snout_err=np.linalg.norm(h - H) / Lh, tail_err=np.linalg.norm(t - T) / Lh, fork_notch=bool(k.fork03_moved))
        out.append(rec)
    return pd.DataFrame(out), C, stored, sc


def cboot(d, stat, key="dive_id"):
    rng = np.random.default_rng(rng0); g = [x for _, x in d.groupby(key)]
    v = [stat(pd.concat([g[i] for i in rng.integers(0, len(g), len(g))], ignore_index=True)) for _ in range(N_BOOT)]
    return tuple(np.nanpercentile(v, [2.5, 97.5]))


def describe(d):
    return dict(median=d.median(), mad=d.abs().mean(), within5=(d.abs() <= .05).mean(), within10=(d.abs() <= .10).mean())


def p90(s):
    return S.p90(pd.Series(s))


def fish_level(F, col):
    g = F.dropna(subset=["human", col]).groupby(["dive_id", "fish"])
    return pd.DataFrame(dict(d=g[col].apply(p90) / g.human.apply(p90) - 1, frames=g.size())).reset_index()


def re_split(y, g):
    """One-way random effects, method of moments, unbalanced: (between var, within var, between share)."""
    d = pd.DataFrame(dict(y=y, g=g)).dropna(); k = d.g.nunique(); N = len(d)
    if k < 2 or N <= k:
        return np.nan, np.nan, np.nan
    n = d.groupby("g").size(); m = d.groupby("g").y.transform("mean")
    msw = ((d.y - m) ** 2).sum() / (N - k)
    msb = (n * (d.groupby("g").y.mean() - d.y.mean()) ** 2).sum() / (k - 1)
    n0 = (N - (n ** 2).sum() / N) / (k - 1)
    sb = max((msb - msw) / n0, 0.0)
    return sb, msw, sb / (sb + msw)


def main():
    F, C, stored, sc = frames()
    OUT.mkdir(parents=True, exist_ok=True); F.to_csv(OUT / "field_disagreement_frames.csv", index=False, float_format="%.5f")
    pd.set_option("display.width", 230); pd.set_option("display.max_columns", 30)
    cal_dives = sorted(sc)

    # 1 + 3: each swap, on its own frames and on the common frames (all swaps available)
    common = F.dropna(subset=["human"] + SWAPS)
    rows = []
    for col in SWAPS:
        for scope, X in (("own frames", F.dropna(subset=["human", col])), ("common frames", common)):
            X = X.assign(d=X[col] / X.human - 1)
            for level, Y in (("frame", X), ("fish p90", fish_level(X, col))):
                s = describe(Y.d)
                ci = {k: cboot(Y, lambda z, k=k: describe(z.d)[k]) for k in ("median", "mad", "within10")}
                rows.append(dict(swap=col, scope=scope, level=level, n=len(Y), dives=Y.dive_id.nunique(), **s,
                                 median_ci=ci["median"], mad_ci=ci["mad"], within10_ci=ci["within10"]))
    R = pd.DataFrame(rows); R.to_csv(OUT / "field_disagreement_summary.csv", index=False, float_format="%.4f")
    print("SWAPS (d = automatic / human - 1)"); print(R.round(3).to_string(index=False)); print()

    # 2: variance split of log(automatic / human)
    V = []
    for col, X in (("all", F.dropna(subset=["human", "all"])), ("dot+ht", F.dropna(subset=["human", "dot+ht"])),
                   ("dot+ht, calibrated dives only", F[F.dive_id.isin(cal_dives)].dropna(subset=["human", "dot+ht"])),
                   ("calibration", F.dropna(subset=["human", "calibration"])), ("head/tail", F.dropna(subset=["human", "head/tail"])),
                   ("dot", F.dropna(subset=["human", "dot"]))):
        c = col.split(",")[0]; y = np.log(X[c] / X.human)
        for level, Y in (("frame", X.assign(y=y)), ("fish p90", fish_level(X, c).assign(y=lambda z: np.log1p(z.d)))):
            sb, sw, share = re_split(Y.y, Y.dive_id)
            lo, hi = cboot(Y, lambda z: re_split(z.y, z.dive_id)[2])
            V.append(dict(pipeline=col, level=level, n=len(Y), dives=Y.dive_id.nunique(), sd_between=np.sqrt(sb), sd_within=np.sqrt(sw),
                          between_share=share, share_ci=(lo, hi)))
    V = pd.DataFrame(V); V.to_csv(OUT / "field_disagreement_variance.csv", index=False, float_format="%.4f")
    print("VARIANCE of log(automatic/human): between dives vs within"); print(V.round(3).to_string(index=False)); print()

    # 4: head/tail endpoints (human-seeded masks)
    H = F.dropna(subset=["snout_err"]).copy(); H["d"] = H["head/tail"] / H.human - 1
    q = H.d.abs().quantile(0.9); top = H[H.d.abs() >= q]
    ht = []
    for name, X in (("all frames", H), ("largest 10% |d|", top), ("rest", H[H.d.abs() < q])):
        rec = dict(subset=name, frames=len(X), dives=X.dive_id.nunique())
        for c in ("snout_err", "tail_err"):
            rec[f"{c}_median"] = X[c].median(); rec[f"{c}_ci"] = cboot(X, lambda z, c=c: z[c].median())
        rec["tail_dominates"] = (X.tail_err > X.snout_err).mean(); rec["fork_notch_share"] = X.fork_notch.mean()
        rec["median_d"] = X.d.median(); ht.append(rec)
    HT = pd.DataFrame(ht); HT.to_csv(OUT / "field_disagreement_headtail.csv", index=False, float_format="%.4f")
    print("HEAD/TAIL endpoints (fraction of human length; human-seeded mask, production rule)"); print(HT.round(3).to_string(index=False))
    nf = H.groupby("fork_notch").agg(frames=("d", "size"), tail_err=("tail_err", "median"), snout_err=("snout_err", "median"),
                                    mad=("d", lambda s: s.abs().mean()), median_d=("d", "median"))
    print(nf.round(3).to_string()); print()
    SP = H.groupby("species").agg(frames=("d", "size"), dives=("dive_id", "nunique"), median_d=("d", "median"), mad=("d", lambda s: s.abs().mean()),
                                  snout_err=("snout_err", "median"), tail_err=("tail_err", "median"), fork_notch=("fork_notch", "mean")).sort_values("frames", ascending=False)
    SP.to_csv(OUT / "field_disagreement_species.csv", float_format="%.4f")
    print("HEAD/TAIL by species"); print(SP.round(3).to_string()); print()

    # 5: calibration per dive vs disagreement per dive
    per = F.assign(d_cal=F.calibration / F.human - 1, d_all=F["all"] / F.human - 1, d_dotht=F["dot+ht"] / F.human - 1).groupby("dive_id").agg(
        frames=("human", "size"), cal_median=("d_cal", "median"), all_median=("d_all", "median"), all_mad=("d_all", lambda s: s.abs().mean()),
        dotht_median=("d_dotht", "median"), dotht_mad=("d_dotht", lambda s: s.abs().mean()))
    Cc = C.set_index("dive")[["frames", "size_ratio", "tv_err_px", "angle_vs_stored_deg", "stored_O_mm"]].rename(columns={"frames": "slate_frames"})
    Cc["O_ratio_104"] = 104.0 / Cc.stored_O_mm - 1
    P = per.join(Cc, how="left"); P.to_csv(OUT / "field_disagreement_calibration.csv", float_format="%.4f")
    print("CALIBRATION per dive (size constancy vs stored) and length disagreement per dive"); print(P.round(4).to_string())


if __name__ == "__main__":
    main()
