"""Automatic-dot gates: drop detections that are probably wrong before measuring.

  confidence  reject a dot whose detector confidence is below T.
              T is chosen on the T3 sample (laser_detection_analysis, 1,571 frames, production
              condition, human dots drawn unseeded), excluding every frame of this study, by a rule
              fixed in advance: the largest T that drops at most 2 % of good dots (<= 20 px).
  line        reject a dot more than 25 px from its dive's laser line, the line being fitted to
              the dive's OTHER automatic dots (total least squares, two rounds of trimming at
              20 px). No human input, so it is usable in the automatic pipeline.
Test: this study's 791 reef frames -- dot misses caught and good dots lost -- and the effect on
fully automatic length vs manual length on the 8 calibrated dives.

Run from this repo:  uv run python dotgate.py
"""
from __future__ import annotations

import json, sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(HERE.parent))
from fishsense_cscw import laser_detection as T3  # noqa: E402
import score as S  # noqa: E402

MISS_PX, LINE_PX, MAX_GOOD_LOSS = 20.0, 25.0, 0.02


def fit_line(xy):
    for _ in range(3):
        c = xy.mean(0); u = np.linalg.svd(xy - c)[2][0]; n = np.array([-u[1], u[0]])
        r = np.abs((xy - c) @ n)
        keep = r <= MISS_PX
        if keep.all() or keep.sum() < 3:
            break
        xy = xy[keep]
    return c, n


def main():
    F = pd.read_csv(HERE / "frames.csv"); reef = F[F.set == "reef"].set_index("image_id")
    # ---- choose T on T3, excluding this study's frames
    d = T3.load(); d = d[(d.condition == "production") & d.has_dot & d.pred_x.notna() & ~d.image_id.isin(F.image_id)]
    d["err"] = np.hypot(d.pred_x - d.human_x, d.pred_y - d.human_y); good = d.err <= MISS_PX
    cands = np.round(np.linspace(0.05, 0.99, 95), 2)
    T = max(t for t in cands if (d[good].confidence < t).mean() <= MAX_GOOD_LOSS)
    print(f"dev (T3, {len(d)} frames, {d.dive_id.nunique()} dives): misses {(~good).mean():.1%}; "
          f"T = {T:.2f} drops {(d[good].confidence < T).mean():.1%} of good dots and {(d[~good].confidence < T).mean():.0%} of misses")
    # ---- test on reef frames
    dots = {}
    for l in (HERE / "reef_dots.jsonl").open():
        r = json.loads(l)
        if "dot" in r and r["dot"]["x"] is not None:
            dots[r["image_id"]] = (r["dot"]["x"], r["dot"]["y"], r["dot"]["confidence"])
    t = pd.DataFrame([dict(image_id=i, dive=int(reef.loc[i, "dive_id"]), green=str(reef.loc[i, "laser_label"]).startswith("Green"),
                           x=v[0], y=v[1], conf=v[2], err=np.hypot(v[0] - reef.loc[i, "laser_x"], v[1] - reef.loc[i, "laser_y"]))
                      for i, v in dots.items() if i in reef.index])
    t["off_line"] = np.nan
    for dive, g in t.groupby("dive"):
        xy = g[["x", "y"]].to_numpy(float)
        for j, idx in enumerate(g.index):
            others = np.delete(xy, j, 0)
            if len(others) >= 5:
                c, n = fit_line(others); t.loc[idx, "off_line"] = abs((xy[j] - c) @ n)
    gates = {"none": pd.Series(True, index=t.index), f"confidence >= {T:.2f}": t.conf >= T,
             f"on line (<= {LINE_PX:.0f} px)": t.off_line.fillna(0) <= LINE_PX}
    gates["both"] = gates[f"confidence >= {T:.2f}"] & gates[f"on line (<= {LINE_PX:.0f} px)"]
    miss = t.err > MISS_PX
    print(f"\ntest (reef, {len(t)} frames; misses {miss.mean():.1%}: green {miss[t.green].mean():.1%}, red {miss[~t.green].mean():.1%})")
    for name, keep in gates.items():
        print(f"  {name:22s} keeps {keep.mean():.1%} | misses left {(miss & keep).sum()} of {miss.sum()} | good dots lost {(~miss & ~keep).sum()} ({(~miss & ~keep).mean() / (~miss).mean():.1%})")
    # ---- end to end on calibrated dives: auto dot + auto-seeded mask (production rule) vs manual
    K = pd.read_csv(HERE / "keypoints.csv"); K = K[K.seed == "auto"].set_index("image_id")
    stored, _, intr = S.calibrations(); rows = []
    for r in t.itertuples():
        cal = stored.get(r.dive); fr = reef.loc[r.image_id]
        if cal is None or pd.isna(fr.head_x):
            continue
        Kc = intr[int(fr.camera_id)]
        Lm = S.length(Kc, S.depth(Kc, cal[0], cal[1], fr.laser_x, fr.laser_y), fr.head_x, fr.head_y, fr.tail_x, fr.tail_y)
        k = K.loc[r.image_id] if r.image_id in K.index else None
        La = np.nan
        if k is not None and pd.notna(k.head_x):
            La = S.length(Kc, S.depth(Kc, cal[0], cal[1], r.x, r.y), k.head_x, k.head_y, k.prod_tail_x, k.prod_tail_y)
        rows.append(dict(idx=r.Index, rel=La / Lm - 1))
    E = pd.DataFrame(rows).set_index("idx")
    print(f"\nend to end, calibrated dives, human-measured frames ({len(E)}):")
    for name, keep in gates.items():
        e = E.rel.where(keep.reindex(E.index))
        ok = e.dropna()
        print(f"  {name:22s} automatic length for {ok.size / len(E):.1%} | MAE {ok.abs().mean():.1%} | > 20% off {(ok.abs() > .2).mean():.1%} | within 10% {(ok.abs() <= .1).mean():.1%}")


if __name__ == "__main__":
    main()
