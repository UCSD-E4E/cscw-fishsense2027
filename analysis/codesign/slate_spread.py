"""Task 3a: does a field dive's slate footage carry enough near-far spread for size constancy?

Not the full ~60k-image corpus: that scan has not run. This uses the slate frames the slate project has
labelled (2026-10-03_slate_detector data/manifest.csv, label = 1, the one-off cutting-board slate
excluded): 1,403 frames on 168 dives. Apparent size = sqrt(area) of the SAM 3.1 "white board" mask the
project chose per frame (data/masks/sam3/{image_id}.npz; chosen by label outline, then laser dot, then
score). Size constancy only needs ratios within a dive. A fit also needs enough frames: the last measure
keeps only dives with >= 8 slate frames carrying a dot.

Per dive: frames, spread = largest / smallest size (all slate frames, and frames with a current human
laser dot - latest completed, non-superseded label, data/db_extracts/laser_dots.psv - since the fit needs the dot), and a robust spread (90th / 10th percentile) against single bad
masks. Thresholds: 1.5x (the brief) and 2x (task 3c: 98% of fits within 0.05 deg from 2x; the median
is within target from 1.5x).

Field dives: every dive whose setting is not pool (data/db_extracts/dive_environment.psv, T3's keyword
rule). Pool dives are reported separately.

False positives: the slate-presence classifier's dive-grouped out-of-fold predictions
(data/slate_detector/oof_cv_q1.csv) at the operating threshold p >= 0.5, on frames labelled not-slate,
per dive.

Writes analysis/codesign/results/slate_spread_dives.csv and slate_spread_summary.csv.
Run: uv run python analysis/codesign/slate_spread.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from fishsense_cscw.paths import REPO

SLATE = REPO.parent / "2026-10-03_slate_detector"
OUT = REPO / "analysis/codesign/results"
THRESH = 0.5
MIN_FRAMES = 8   # the fewest frames the size-constancy fits here use (slate_unknown.MIN_FRAMES)


def mask_size(image_id: int) -> float:
    z = np.load(SLATE / "data/masks/sam3" / f"{image_id}.npz")
    k = int(z["chosen"])
    if k < 0:
        return np.nan
    n, h, w = z["shape"]
    m = np.unpackbits(z["masks"][k], axis=-1, count=w)
    return float(np.sqrt(m.sum()))


def main():
    oof = pd.read_csv(REPO / "data/slate_detector/oof_cv_q1.csv")
    env = pd.read_csv(REPO / "data/db_extracts/dive_environment.psv", sep="|", header=None, names=["dive_id", "environment"]).set_index("dive_id").environment
    # a current human laser dot (latest completed, non-superseded label with coordinates), as in reef_size_constancy.py
    with_dot = set(pd.read_csv(REPO / "data/db_extracts/laser_dots.psv", sep="|", header=None, names=["image_id", "x", "y", "label"]).image_id)
    pos = oof[(oof.label == 1) & ~oof.cutting_board.astype(bool)].copy()
    pos["size"] = [mask_size(i) for i in pos.image_id]
    pos["has_dot"] = pos.image_id.isin(with_dot)
    pos = pos.dropna(subset=["size"])
    rows = []
    for dive, g in pos.groupby("dive_id"):
        s, sd = g["size"].to_numpy(), g.loc[g.has_dot, "size"].to_numpy()
        rows.append(dict(dive_id=int(dive), environment=env.get(dive, "unknown"), frames=len(g), frames_with_dot=len(sd),
                         spread=s.max() / s.min() if len(s) >= 2 else np.nan,
                         spread_robust=np.percentile(s, 90) / np.percentile(s, 10) if len(s) >= 5 else np.nan,
                         spread_dot=sd.max() / sd.min() if len(sd) >= 2 else np.nan))
    D = pd.DataFrame(rows)
    neg = oof[(oof.label == 0) & ~oof.cutting_board.astype(bool)]
    fp = neg.assign(fp=neg.p_slate >= THRESH).groupby("dive_id").agg(neg_frames=("fp", "size"), false_pos=("fp", "sum"))
    D = D.merge(fp, left_on="dive_id", right_index=True, how="left")
    S = []
    for setting, g in (("field", D[D.environment != "pool"]), ("pool", D[D.environment == "pool"])):
        g = g.assign(spread_dot8=g.spread_dot.where(g.frames_with_dot >= MIN_FRAMES))
        for col, label in (("spread", "all slate frames"), ("spread_robust", "90th/10th percentile"), ("spread_dot", "frames with a laser dot"),
                           ("spread_dot8", f"frames with a laser dot, dives with >= {MIN_FRAMES}")):
            v = g[col]
            S.append(dict(setting=setting, measure=label, dives=len(g), dives_measurable=int(v.notna().sum()),
                          ge_1_5=int((v >= 1.5).sum()), ge_2=int((v >= 2.0).sum()),
                          share_ge_1_5=float((v >= 1.5).sum() / len(g)), share_ge_2=float((v >= 2.0).sum() / len(g)),
                          median_spread=float(v.median())))
    S = pd.DataFrame(S)
    allfp = neg.assign(fp=neg.p_slate >= THRESH).groupby("dive_id").fp.sum()
    OUT.mkdir(parents=True, exist_ok=True)
    D.to_csv(OUT / "slate_spread_dives.csv", index=False, float_format="%.4f")
    S.to_csv(OUT / "slate_spread_summary.csv", index=False, float_format="%.4f")
    pd.set_option("display.width", 200)
    print(S.round(3).to_string(index=False))
    print(f"\nfalse positives at p >= {THRESH}: {int(allfp.sum())} in {len(neg):,} not-slate frames on {neg.dive_id.nunique()} dives; "
          f"dives with any: {int((allfp > 0).sum())}; max per dive {int(allfp.max())}")
    f = D[D.environment != "pool"]
    print(f"field dives: {len(f)}; median slate frames {f.frames.median():.0f}; with a dot on >= 2 slate frames: {int((f.frames_with_dot >= 2).sum())}")


if __name__ == "__main__":
    main()
