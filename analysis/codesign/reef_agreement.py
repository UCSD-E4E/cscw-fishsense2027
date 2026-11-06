"""Bland-Altman agreement of the fully automatic pipeline with the human pipeline on the seven reef dives.

Frames: stage_comparison.py's configuration 4 on its field set (results/stage_comparison_frames.csv): human-measured
frames on dives 279, 341, 347, 349, 383, 465, 471 (436 excluded, its human calibration was withdrawn) where the fully
automatic pipeline gives a length (run3 dot inside the laser region, slate-pose-6 calibration at aim 0, head/tail v5).
Reference: configuration 1, the human pipeline. Per frame: mean = (automatic + human) / 2; difference =
(automatic - human) / mean, in %. Bias = mean difference; 95% limits of agreement = bias +/- 1.96 SD of the
differences. 95% intervals for the bias and each limit resample dives (2,000 draws, seed 0); each dive is its own
physical dive. Frames of one fish are not independent; the dive resampling covers that. No tape: agreement, not
accuracy. Automatic lengths are not reviewed by a person.
Writes analysis/codesign/results/reef_agreement.csv (summary) and reef_agreement_frames.csv.
Run: uv run python analysis/codesign/reef_agreement.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from fishsense_cscw.paths import REPO

RES = REPO / "analysis/codesign/results"
FIELD = (279, 341, 347, 349, 383, 465, 471)


def stats(d):
    b, s = d.mean(), d.std(ddof=1)
    return np.array([b, b - 1.96 * s, b + 1.96 * s, s])


def main():
    F = pd.read_csv(RES / "stage_comparison_frames.csv", low_memory=False)
    F = F[(F.set == "field") & F.dive.isin(FIELD) & F.measured.astype(str).eq("True")].dropna(subset=["1 human", "4 automatic"])
    F = F.assign(mean_m=(F["4 automatic"] + F["1 human"]) / 2)
    F["diff_pct"] = 100 * (F["4 automatic"] - F["1 human"]) / F.mean_m
    rng = np.random.default_rng(0)
    g = {k: v.diff_pct.to_numpy() for k, v in F.groupby("dive")}
    keys = list(g)
    draws = np.array([stats(pd.Series(np.concatenate([g[k] for k in rng.choice(keys, len(keys))]))) for _ in range(2000)])
    est = stats(F.diff_pct); lo, hi = np.percentile(draws, [2.5, 97.5], axis=0)
    R = pd.DataFrame(dict(quantity=["bias", "lower limit", "upper limit", "SD"], value_pct=est, ci_lo=lo, ci_hi=hi))
    R["frames"], R["dives"] = len(F), F.dive.nunique()
    F[["image_id", "dive", "1 human", "4 automatic", "mean_m", "diff_pct"]].to_csv(RES / "reef_agreement_frames.csv", index=False, float_format="%.5f")
    R.to_csv(RES / "reef_agreement.csv", index=False, float_format="%.4f")
    print(R.round(2).to_string(index=False))
    print(f"mean length {F.mean_m.min():.3f}-{F.mean_m.max():.3f} m; |diff| > 10%: {(F.diff_pct.abs() > 10).sum()} frames")


if __name__ == "__main__":
    main()
