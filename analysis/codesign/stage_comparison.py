"""The human pipeline to fully automatic, one human step swapped at a time, with the current components.

Configurations (dot, laser calibration, head/tail):
  1 human      human dot,      production (human) calibration,  human head/tail
  2 auto dot   automatic dot,  production calibration,          human head/tail
  3 + auto cal automatic dot,  slate-pose calibration,          human head/tail
  4 automatic  automatic dot,  slate-pose calibration,          automatic head/tail (v5)

Components:
  automatic dot   the deployed RAW detector (run3 epoch_021; e2e_measurement/dots.jsonl, tail/reef_dots.jsonl, from
                  run_e2e.py), kept only inside production's laser region (fishsense-services contracts
                  laser_region.py LASER_REGION_POLYGON at db0b895, rectified px), as laser_predict does.
  calibrations    production: v1 laserextrinsics (e2e_measurement/extrinsics.psv; identical to the services human rows
                  for all 30 shared dives). Slate-pose: fishsense-services' current slate-pose-6 calibrations, exported
                  read-only on 2026-10-31 (data/fishsense_services/slate_pose_calibrations.csv): the mission's own
                  accepted fit at aim 0. Pool dives use the calibration of their paired slate session (score.PAIR).
  head/tail v5    fish models (pool): the SAM 3.1 mask rule at the automatic dot (e2e_measurement/headtail.jsonl
                  ht_auto). Real fish (reef): the SimCC keypoints on the SAM box at the automatic dot
                  (2026-10-22_headtail_keypoints results/model_keypoints_simcc_sam.csv, seed auto); a frame whose
                  SimCC and mask-rule pixel lengths differ by more than 15% of the rule's goes to review and gets
                  no length (fishsense-services KEYPOINT_DISAGREEMENT = 0.15).

Pool (tape): the stage ladder's 10 fish-model dives (score.py: 58, 59, 60, 61, 66, 76, 84, 87, 94, 114, every
IMWUT-corpus measurement). Per fish (one model in one dive): production's p90 over frames; error = p90 / tape - 1;
mean |error| over fish. Field (no tape): the reef dives with a production calibration (279, 341, 347, 349, 383,
465, 471; 436 reported separately, its production calibration came from mirrored labels and was withdrawn); the
reference is configuration 1; d = length / human length - 1 per frame. Coverage: of the human-measured frames (a
head/tail label with coordinates) and the human-rejected frames (a head/tail row without coordinates, reef only),
the share each configuration gives a length. Every dive is its own physical dive (physical_dives.py); 95%
intervals resample dives (2,000 draws, seed 0).
Writes analysis/codesign/results/stage_comparison_{pool,field,coverage}.csv and stage_comparison_frames.csv.
Run: uv run python analysis/codesign/stage_comparison.py
"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from fishsense_cscw.paths import REPO

sys.path.insert(0, str(REPO / "e2e_measurement"))
import score as S  # noqa: E402

OUT = REPO / "analysis/codesign/results"
KP = REPO.parent / "2026-10-22_headtail_keypoints/results/model_keypoints_simcc_sam.csv"
SLATE_POSE = REPO / "data/fishsense_services/slate_pose_calibrations.csv"
REGION = [(1580, 570), (1700, 465), (2335, 395), (2455, 525), (2470, 1610), (2185, 1890), (1920, 1905), (1625, 1365)]
FIELD = (279, 341, 347, 349, 383, 465, 471)
SEPARATE = (436,)
DISAGREE = 0.15
CONFIGS = ["1 human", "2 auto dot", "3 + auto cal", "4 automatic"]
RNG = np.random.default_rng(0)


def in_region(x, y):
    pos = neg = False
    for i, (ax, ay) in enumerate(REGION):
        bx, by = REGION[(i + 1) % len(REGION)]
        c = (bx - ax) * (y - ay) - (by - ay) * (x - ax)
        pos |= c > 0; neg |= c < 0
    return not (pos and neg)


def auto_dots():
    dots = {}
    for f in (REPO / "e2e_measurement/dots.jsonl", REPO / "e2e_measurement/tail/reef_dots.jsonl"):
        for line in f.open():
            r = json.loads(line)
            d = r.get("dot") or {}
            if d.get("x") is not None and in_region(d["x"], d["y"]):
                dots[r["image_id"]] = (d["x"], d["y"])
    return dots


def slate_pose():
    C = pd.read_csv(SLATE_POSE)
    C = C[(C.method == "slate_pose") & (C.aim == 0) & (C.outcome == "accepted")]
    return {int(r.mission_v1_id): (np.array([r.laser_position_x, r.laser_position_y, r.laser_position_z], float),
                                   np.array([r.laser_axis_x, r.laser_axis_y, r.laser_axis_z], float)) for r in C.itertuples()}


def length(K, cal, dot, ht):
    if cal is None or dot is None or ht is None or any(v is None or not np.isfinite(v) for v in (*dot, *ht)):
        return np.nan
    Z = S.depth(K, cal[0], cal[1], *dot)
    return S.length(K, Z, *ht) if Z > 0 else np.nan


def boot(df, stat):
    keys = df.dive.unique()
    g = {k: v for k, v in df.groupby("dive")}
    draws = [stat(pd.concat([g[k].assign(dive=i) for i, k in enumerate(RNG.choice(keys, len(keys)))])) for _ in range(2000)]
    return stat(df), np.nanpercentile(draws, 2.5), np.nanpercentile(draws, 97.5)


def pool(dots, stored, sp, intr):
    F = pd.read_csv(REPO / "e2e_measurement/frames.psv", sep="|").drop_duplicates("image_id")
    F = F[F.content.fillna("").str.contains("Fish Model|Ruler")].copy()
    F["target"] = F.content.str.split(", ").str[-1]
    ht = S.jsonl("headtail.jsonl")
    rows = []
    for r in F.itertuples():
        K, cd = intr[int(r.camera_id)], S.PAIR[int(r.dive_id)]
        e = (ht.get(r.image_id, {}).get("ht_auto") or {})
        aht = (e["head_x"], e["head_y"], e["tail_x"], e["tail_y"]) if e.get("status") == "predicted" else None
        hd, ad, hh = (r.laser_x, r.laser_y), dots.get(r.image_id), (r.head_x, r.head_y, r.tail_x, r.tail_y)
        L = [length(K, stored.get(cd), hd, hh), length(K, stored.get(cd), ad, hh), length(K, sp.get(cd), ad, hh), length(K, sp.get(cd), ad, aht)]
        rows.append(dict(set="pool", image_id=r.image_id, dive=int(r.dive_id), target=r.target, truth=S.KNOWN[r.target], **dict(zip(CONFIGS, L))))
    return pd.DataFrame(rows)


def fish_mae(P, c):
    g = P.dropna(subset=[c]).groupby(["dive", "target"])
    e = (g[c].apply(S.p90) / g.truth.first() - 1).abs()
    return e.mean(), len(e)


def field(dots, stored, sp, intr):
    T = pd.read_csv(REPO / "e2e_measurement/tail/frames.csv")
    T = T[(T.set == "reef") & T.dive_id.isin(FIELD + SEPARATE)]
    kp = pd.read_csv(KP).query("split == 'test' and seed == 'auto' and status == 'predicted'").set_index("image_id")
    rule = pd.read_csv(REPO / "e2e_measurement/tail/keypoints.csv").query("seed == 'auto'").set_index("image_id")
    rows = []
    for r in T.itertuples():
        K, d = intr[int(r.camera_id)], int(r.dive_id)
        measured = pd.notna(r.head_x)
        hh = (r.head_x, r.head_y, r.tail_x, r.tail_y) if measured else None
        ad = dots.get(r.image_id)
        # v5: SimCC where the SAM box exists at the automatic dot, unless it disagrees with the rule by > 15%
        sam_ok = r.image_id in rule.index and pd.notna(rule.loc[r.image_id, "head_x"])
        aht, v5 = None, "no mask" if not sam_ok else "no SimCC row"
        if sam_ok and r.image_id in kp.index:
            k = kp.loc[r.image_id]
            ls = np.hypot(k.head_x - k.tail_x, k.head_y - k.tail_y); lr = np.hypot(k.sam_head_x - k.sam_tail_x, k.sam_head_y - k.sam_tail_y)
            v5 = "review" if abs(ls / lr - 1) > DISAGREE else "measured"
            if v5 == "measured":
                aht = (k.head_x, k.head_y, k.tail_x, k.tail_y)
        L = [length(K, stored.get(d), (r.laser_x, r.laser_y), hh), length(K, stored.get(d), ad, hh),
             length(K, sp.get(d), ad, hh), length(K, sp.get(d), ad, aht)]
        rows.append(dict(set="field", image_id=r.image_id, dive=d, measured=measured, v5=v5, auto_dot=ad is not None, **dict(zip(CONFIGS, L))))
    return pd.DataFrame(rows)


def main():
    stored, _, intr = S.calibrations()
    sp, dots = slate_pose(), auto_dots()
    P, Fd = pool(dots, stored, sp, intr), field(dots, stored, sp, intr)
    pd.concat([P, Fd]).to_csv(OUT / "stage_comparison_frames.csv", index=False)
    pd.set_option("display.width", 250)

    print(f"pool: dives {sorted(P.dive.unique())}; calibration sessions {sorted({S.PAIR[d] for d in P.dive.unique()})}; "
          f"slate-pose for {sorted(d for d in P.dive.unique() if S.PAIR[d] in sp)}")
    rows = []
    common = P.dropna(subset=CONFIGS)
    for c in CONFIGS:
        for name, D in (("own frames", P), ("common frames", common)):
            est, lo, hi = boot(D, lambda x: fish_mae(x, c)[0])
            rows.append(dict(config=c, frames_set=name, frames=int(D[c].notna().sum()), dives=D.dropna(subset=[c]).dive.nunique(),
                             fish=fish_mae(D, c)[1], fish_p90_mae=est, lo=lo, hi=hi))
    R = pd.DataFrame(rows); R.to_csv(OUT / "stage_comparison_pool.csv", index=False)
    print(R.round(4).to_string(index=False))

    rows = []
    for label, dives in (("field (7 dives)", FIELD), ("436 (separate)", SEPARATE)):
        D = Fd[Fd.dive.isin(dives) & Fd.measured]
        for c in CONFIGS[1:]:
            X = D.dropna(subset=["1 human", c]).assign(d=lambda x: x[c] / x["1 human"] - 1)
            if not len(X):
                rows.append(dict(set=label, config=c, frames=0, dives=0)); continue
            out = dict(set=label, config=c, frames=len(X), dives=X.dive.nunique())
            for name, f in (("median_d", lambda x: x.d.median()), ("mean_abs_d", lambda x: x.d.abs().mean()), ("within_10pct", lambda x: (x.d.abs() <= 0.1).mean())):
                est, lo, hi = boot(X, f) if X.dive.nunique() > 1 else (f(X), np.nan, np.nan)
                out.update({name: est, f"{name}_lo": lo, f"{name}_hi": hi})
            rows.append(out)
    R = pd.DataFrame(rows); R.to_csv(OUT / "stage_comparison_field.csv", index=False)
    print(R.round(4).to_string(index=False))

    rows = []
    for label, D in (("pool measured", P.assign(measured=True)), ("field measured", Fd[Fd.dive.isin(FIELD) & Fd.measured]),
                     ("field rejected", Fd[Fd.dive.isin(FIELD) & ~Fd.measured]), ("436 measured", Fd[Fd.dive.isin(SEPARATE) & Fd.measured]),
                     ("436 rejected", Fd[Fd.dive.isin(SEPARATE) & ~Fd.measured])):
        for c in CONFIGS:
            if not len(D):
                continue
            est, lo, hi = boot(D, lambda x: x[c].notna().mean()) if D.dive.nunique() > 1 else (D[c].notna().mean(), np.nan, np.nan)
            rows.append(dict(set=label, config=c, frames=len(D), dives=D.dive.nunique(), share_with_length=est, lo=lo, hi=hi))
    R = pd.DataFrame(rows); R.to_csv(OUT / "stage_comparison_coverage.csv", index=False)
    print(R.round(4).to_string(index=False))
    v = Fd[Fd.dive.isin(FIELD)].groupby("measured").v5.value_counts().unstack(fill_value=0)
    print("v5 head/tail status on field frames (measured True/False):\n", v.to_string())


if __name__ == "__main__":
    main()
