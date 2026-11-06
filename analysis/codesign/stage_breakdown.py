"""Field disagreement with the human pipeline when one step at a time is automatic, with the current components.

Frames: the human-measured frames on stage_comparison.py's 7 field dives (279, 341, 347, 349, 383, 465, 471; 436
left out, its human calibration came from mirrored labels and was withdrawn). Each dive is its own physical dive.
Reference: the human pipeline (human dot, the dive's production calibration from human slate labels, human snout
and fork clicks). d = length / human length - 1 per frame; mean |d| over the frames each swap measures; 95%
intervals resample dives (stage_comparison.boot, 2,000 draws, seed 0). No tape: agreement, not accuracy.

  only dot          automatic dot (run3 epoch_021, inside the laser region); stage_comparison configuration 2
  only calibration  slate-pose-6 calibration (2026-10-31 services export, aim 0, accepted) at the human dot
  only head/tail    at the human dot's SAM 3.1 mask:
                      axis rule   production's mask rule (PCA axis, tail at the narrow end; e2e_measurement/tail/
                                  keypoints.csv, seed "human", head + prod_tail)
                      trained     v5: SimCC snout/fork on the mask box (2026-10-22_headtail_keypoints, test split,
                                  seed "human"), no length when SimCC and the rule differ by > 15% (review)
  all automatic     automatic dot, slate-pose calibration, head/tail at the automatic dot's mask:
                      axis rule   the mask rule (keypoints.csv seed "auto")
                      trained     v5, stage_comparison configuration 4
Automatic lengths are not reviewed by a person.
Writes analysis/codesign/results/stage_breakdown.csv.
Run: uv run python analysis/codesign/stage_breakdown.py
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from fishsense_cscw.paths import REPO

sys.path.insert(0, str(REPO / "analysis/codesign"))
import stage_comparison as SC  # noqa: E402

S = SC.S


def main():
    stored, _, intr = S.calibrations()
    sp, dots = SC.slate_pose(), SC.auto_dots()
    T = pd.read_csv(REPO / "e2e_measurement/tail/frames.csv")
    T = T[(T.set == "reef") & T.dive_id.isin(SC.FIELD) & T.head_x.notna()]
    rule = pd.read_csv(REPO / "e2e_measurement/tail/keypoints.csv")
    rule = {s: g.set_index("image_id") for s, g in rule[rule.head_x.notna()].groupby("seed")}
    kp = pd.read_csv(SC.KP).query("split == 'test' and status == 'predicted'")
    kp = {s: g.set_index("image_id") for s, g in kp.groupby("seed")}

    def rule_ht(i, seed):
        if i not in rule[seed].index:
            return None
        k = rule[seed].loc[i]
        return (k.head_x, k.head_y, k.prod_tail_x, k.prod_tail_y)

    def v5_ht(i, seed):
        if i not in kp[seed].index or rule_ht(i, seed) is None:
            return None, "no keypoints"
        k = kp[seed].loc[i]
        ls, lr = np.hypot(k.head_x - k.tail_x, k.head_y - k.tail_y), np.hypot(k.sam_head_x - k.sam_tail_x, k.sam_head_y - k.sam_tail_y)
        return (None, "review") if abs(ls / lr - 1) > SC.DISAGREE else ((k.head_x, k.head_y, k.tail_x, k.tail_y), "measured")

    rows = []
    for r in T.itertuples():
        K, d, i = intr[int(r.camera_id)], int(r.dive_id), r.image_id
        hd, ad, hh = (r.laser_x, r.laser_y), dots.get(i), (r.head_x, r.head_y, r.tail_x, r.tail_y)
        (vh, vh_s), (va, va_s) = v5_ht(i, "human"), v5_ht(i, "auto")
        L = SC.length
        rows.append(dict(image_id=i, dive=d, human=L(K, stored.get(d), hd, hh), v5_human_status=vh_s, v5_auto_status=va_s, **{
            "only dot": L(K, stored.get(d), ad, hh),
            "only calibration": L(K, sp.get(d), hd, hh),
            "only head/tail, axis rule": L(K, stored.get(d), hd, rule_ht(i, "human")),
            "only head/tail, trained": L(K, stored.get(d), hd, vh),
            "all automatic, axis rule": L(K, sp.get(d), ad, rule_ht(i, "auto")),
            "all automatic, trained": L(K, sp.get(d), ad, va)}))
    F = pd.DataFrame(rows)
    out = []
    for c in F.columns[5:]:
        X = F.dropna(subset=["human", c]).assign(dd=lambda x: x[c] / x.human - 1)
        est, lo, hi = SC.boot(X, lambda x: x.dd.abs().mean())
        out.append(dict(swap=c, frames=len(X), of=len(F), dives=X.dive.nunique(), mean_abs_d=est, lo=lo, hi=hi,
                        median_d=X.dd.median(), within_10pct=(X.dd.abs() <= 0.1).mean()))
    R = pd.DataFrame(out)
    R.to_csv(REPO / "analysis/codesign/results/stage_breakdown.csv", index=False, float_format="%.5f")
    pd.set_option("display.width", 200)
    print(R.round(4).to_string(index=False))
    print("v5 at the human dot:", F.v5_human_status.value_counts().to_dict(), "; at the automatic dot:", F.v5_auto_status.value_counts().to_dict())


if __name__ == "__main__":
    main()
