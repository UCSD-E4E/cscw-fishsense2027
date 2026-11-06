"""Pick three reef frames for the head/tail comparison figure: typical frames, not best cases.

Frames: headtail_compare.py's reef set (human-dot crops on dives with a stored calibration; test split of the
keypoint experiment). Per frame and method (rule = the mask's axis rule, model = SimCC): endpoint error = the mean of
the snout and fork distances from the human clicks, as a fraction of the human length, each method in its own
orientation. A frame's typicality = |percentile of its rule error - 50| + |percentile of its model error - 50|, so a
low score sits near both methods' median error at once. The three lowest-scoring frames from three different dives
are chosen.
Writes analysis/codesign/results/headtail_examples.csv.
Run: uv run python analysis/codesign/headtail_examples_select.py
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from fishsense_cscw.paths import REPO

sys.path.insert(0, str(REPO / "analysis/codesign"))
import headtail_compare as HC  # noqa: E402


def main():
    K = HC.keypoints()
    T = pd.read_csv(REPO / "e2e_measurement/tail/frames.csv")
    T = T[T.set == "reef"]
    stored, _, _ = HC.S.calibrations()
    rows = []
    for r in T.itertuples():
        if stored.get(int(r.dive_id)) is None or (r.image_id, "human") not in K.index:
            continue
        k = K.loc[(r.image_id, "human")]
        hh, ht = np.array([r.head_x, r.head_y]), np.array([r.tail_x, r.tail_y])
        L = np.linalg.norm(ht - hh)
        row = dict(image_id=r.image_id, dive=int(r.dive_id), path=r.path, camera_id=int(r.camera_id), human_px=L)
        for m in ("rule", "model"):
            h, t = np.array([k[f"{m}_hx"], k[f"{m}_hy"]]), np.array([k[f"{m}_tx"], k[f"{m}_ty"]])
            row[f"{m}_err"] = (np.linalg.norm(h - hh) + np.linalg.norm(t - ht)) / 2 / L
        rows.append(row)
    R = pd.DataFrame(rows).dropna(subset=["rule_err", "model_err"])
    R["score"] = (100 * R.rule_err.rank(pct=True) - 50).abs() + (100 * R.model_err.rank(pct=True) - 50).abs()
    pick = R.sort_values("score").drop_duplicates("dive").head(3)
    pick.to_csv(REPO / "analysis/codesign/results/headtail_examples.csv", index=False, float_format="%.4f")
    print(f"{len(R)} frames; median error: rule {100 * R.rule_err.median():.1f}%, model {100 * R.model_err.median():.1f}% of length")
    print(pick[["image_id", "dive", "rule_err", "model_err", "score", "path"]].round(4).to_string(index=False))


if __name__ == "__main__":
    main()
