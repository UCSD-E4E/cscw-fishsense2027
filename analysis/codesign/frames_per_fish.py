"""Task 3b: what is each extra frame of a fish worth?

Unit: a fish (same-fish cluster) on the reef dives with a stored calibration, restricted to frames a
human measured (human dot + head/tail). For each frame, the fully automatic pipeline either
produces a length (automatic dot -> SAM mask -> production head/tail rule) or abstains, and a
produced length is "within 10%" when it is within 10% of the manual length (human dot, human
head/tail, same stored calibration), as in e2e_measurement/tail/evaluate.py.

Subsampling is exact, not random: for a fish with n frames of which s succeed, the chance that k
frames drawn without replacement include at least one success is 1 - C(n-s, k) / C(n, k).

  varying set   for each k, every fish with at least k frames (the set shrinks as k grows)
  fixed set     fish with at least 4 frames, k = 1..4 (same fish at every k)

Clusters, two sources:
  predicted   diveframecluster PREDICTION (e2e_measurement/tail/reef_clusters.psv), a clean partition
  labelled    diveframecluster LABEL_STUDIO (data/db_extracts/ls_clusters.psv): repeated syncs
              duplicated clusters, so each image keeps its most recently updated cluster

95% intervals resample whole dives, 2,000 draws.
Writes analysis/codesign/results/frames_per_fish.csv.
Run: uv run python analysis/codesign/frames_per_fish.py
"""
from __future__ import annotations

import sys
from math import comb

import numpy as np
import pandas as pd

from fishsense_cscw.paths import REPO

sys.path.insert(0, str(REPO / "e2e_measurement")); sys.path.insert(0, str(REPO / "e2e_measurement/tail"))
import score as S  # noqa: E402
import evaluate as EV  # noqa: E402

OUT = REPO / "analysis/codesign/results"
K_FIXED, N_BOOT = 4, 2000


def frame_outcomes() -> pd.DataFrame:
    """Per human-measured reef frame on a calibrated dive: produced? within 10% of manual?"""
    F, K, dots = EV.load(); stored, _, intr = S.calibrations()
    Kx = K.set_index(["image_id", "seed"])
    reef = F[(F.set == "reef") & F.head_x.notna() & F.dive_id.isin(stored)]
    rows = []
    for r in reef.itertuples():
        cal = stored[int(r.dive_id)]; Kc = intr[int(r.camera_id)]
        Lm = S.length(Kc, S.depth(Kc, cal[0], cal[1], r.laser_x, r.laser_y), r.head_x, r.head_y, r.tail_x, r.tail_y)
        k = Kx.loc[(r.image_id, "auto")] if (r.image_id, "auto") in Kx.index else None
        produced = k is not None and r.image_id in dots and not pd.isna(k.get("head_x"))
        rel = np.nan
        if produced:
            La = S.length(Kc, S.depth(Kc, cal[0], cal[1], *dots[r.image_id]), k.head_x, k.head_y, *EV.tail_of(k, "prod"))
            rel = La / Lm - 1
        rows.append(dict(image_id=r.image_id, dive=int(r.dive_id), produced=produced,
                         within10=produced and abs(rel) <= 0.10, rel=rel))
    return pd.DataFrame(rows)


def clusters() -> dict[str, pd.Series]:
    p = pd.read_csv(REPO / "e2e_measurement/tail/reef_clusters.psv", sep="|")
    pred = p[p.data_source == "PREDICTION"].drop_duplicates("image_id").set_index("image_id").cid
    ls = pd.read_csv(REPO / "data/db_extracts/ls_clusters.psv", sep="|", header=None,
                     names=["cid", "dive", "updated", "image_id"])
    ls = ls.sort_values(["updated", "cid"]).drop_duplicates("image_id", keep="last").set_index("image_id").cid
    return {"predicted": pred, "labelled": ls}


def p_any(n: int, s: int, k: int) -> float:
    return 1.0 - comb(n - s, k) / comb(n, k)


def curve(fish: pd.DataFrame, ks, min_n=None) -> pd.DataFrame:
    rows = []
    for k in ks:
        f = fish[fish.n >= (min_n or k)]
        rows.append(dict(k=k, fish=len(f),
                         produced=np.mean([p_any(r.n, r.s_prod, k) for r in f.itertuples()]) if len(f) else np.nan,
                         within10=np.mean([p_any(r.n, r.s_w10, k) for r in f.itertuples()]) if len(f) else np.nan))
    return pd.DataFrame(rows)


def main():
    fr = frame_outcomes()
    rows = []
    for src, cid in clusters().items():
        d = fr.assign(cid=fr.image_id.map(cid)).dropna(subset=["cid"])
        fish = d.groupby("cid").agg(dive=("dive", "first"), n=("produced", "size"),
                                    s_prod=("produced", "sum"), s_w10=("within10", "sum")).reset_index()
        kmax = int(fish.n.max())
        for design, ks, min_n in (("varying set", range(1, kmax + 1), None), (f"fixed set (>= {K_FIXED} frames)", range(1, K_FIXED + 1), K_FIXED)):
            c = curve(fish, ks, min_n)
            rng = np.random.default_rng(0); dives = fish.dive.unique(); boot = []
            for _ in range(N_BOOT):
                pick = rng.choice(dives, len(dives))
                b = pd.concat([fish[fish.dive == x] for x in pick])
                boot.append(curve(b, ks, min_n)[["produced", "within10"]].to_numpy())
            lo, hi = np.nanpercentile(np.array(boot), [2.5, 97.5], axis=0)
            c[["produced_lo", "within10_lo"]] = lo; c[["produced_hi", "within10_hi"]] = hi
            c.insert(0, "design", design); c.insert(0, "clusters", src)
            c["frames_in_set"] = [int(fish[fish.n >= (min_n or k)].n.sum()) for k in c.k]
            rows.append(c)
        # all frames of every fish: the per-fish coverage quoted before (p2-tests.md E2)
        rows.append(pd.DataFrame([dict(clusters=src, design="all frames per fish", k=np.nan, fish=len(fish),
                                       produced=(fish.s_prod > 0).mean(), within10=(fish.s_w10 > 0).mean(),
                                       frames_in_set=int(fish.n.sum()))]))
        print(f"{src}: {len(fish)} fish, {int(fish.n.sum())} frames, frames per fish {fish.n.value_counts().sort_index().to_dict()}")
    R = pd.concat(rows, ignore_index=True)
    OUT.mkdir(parents=True, exist_ok=True)
    R.to_csv(OUT / "frames_per_fish.csv", index=False, float_format="%.4f")
    print(f"frames: {len(fr)}, produced {fr.produced.mean():.3f}, within 10% {fr.within10.mean():.3f}")
    pd.set_option("display.width", 220)
    print(R.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
