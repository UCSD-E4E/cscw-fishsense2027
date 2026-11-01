"""Slate-pose calibrations against human calibrations, dive by dive, on the 2026-10-31 services export.

Dives: physical dives (physical_dives.py) with both an accepted slate-pose-6 calibration for the first laser aim
and an accepted current human calibration (data/fishsense_services/slate_pose_calibrations.csv, the export
stage_comparison.py and calibration_trust.py use). Dive 436 drops out: its human calibration was withdrawn.

Length difference: a calibration sets each frame's range from its laser dot, and length scales with range, so the
two calibrations' length ratio at a dot is their range ratio there. Per dive: the median, over its live human laser
dots (data/db_extracts/dive_laser_dots.psv, sql/extract_dive_laser_dots.sql), of Z_slate_pose / Z_human - 1
(e2e_measurement score.depth, the camera's intrinsics).
Error bar: slate pose's scale_sd_by_range interpolated (linearly in range) at the dive's median dot range.
Within one / two bars: |difference| <= 1x / 2x that bar. Reading high: difference > 0.
95% interval for the median |difference| resamples dives (2,000 draws, seed 0).
Writes analysis/codesign/results/slatepose_vs_human.csv.
Run: uv run python analysis/codesign/slatepose_vs_human.py
"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from fishsense_cscw.paths import REPO

sys.path.insert(0, str(REPO / "e2e_measurement"))
sys.path.insert(0, str(REPO / "analysis/codesign"))
import physical_dives as PD  # noqa: E402
import score as S  # noqa: E402

EXCLUDE = (436,)


def beam(r):
    return (np.array([r.laser_position_x, r.laser_position_y, r.laser_position_z], float),
            np.array([r.laser_axis_x, r.laser_axis_y, r.laser_axis_z], float))


def main():
    K = PD.load().set_index("dive_id")
    C = pd.read_csv(REPO / "data/fishsense_services/slate_pose_calibrations.csv")
    sp = C[(C.method == "slate_pose") & (C.aim == 0) & (C.outcome == "accepted")].set_index("mission_v1_id")
    hu = C[(C.method == "human") & (C.outcome == "accepted")].set_index("mission_v1_id")
    dives = [d for d in sorted(set(sp.index) & set(hu.index)) if d not in EXCLUDE and K.loc[d, "kind"] == "canonical"]
    _, _, intr = S.calibrations()
    D = pd.read_csv(REPO / "data/db_extracts/dive_laser_dots.psv", sep="|", header=None, names=["image_id", "dive_id", "camera_id", "x", "y"])
    rows = []
    for d in dives:
        g = D[D.dive_id == d]
        bs, bh = beam(sp.loc[d]), beam(hu.loc[d])
        z = np.array([(S.depth(intr[int(r.camera_id)], *bs, r.x, r.y), S.depth(intr[int(r.camera_id)], *bh, r.x, r.y)) for r in g.itertuples()])
        z = z[(z > 0).all(1)]
        ratio = z[:, 0] / z[:, 1] - 1
        bars = np.array(json.loads(sp.loc[d, "scale_sd_by_range"]))
        zmed = float(np.median(z[:, 1]))
        bar = float(np.interp(zmed, bars[:, 0], bars[:, 1]))
        diff = float(np.median(ratio))
        rows.append(dict(dive=d, dots=len(z), median_range_m=zmed, diff=diff, bar=bar, bars_off=abs(diff) / bar,
                         within_1=abs(diff) <= bar, within_2=abs(diff) <= 2 * bar, high=diff > 0,
                         slate_pose_frames=int(sp.loc[d, "frames_used"])))
    R = pd.DataFrame(rows)
    rng = np.random.default_rng(0)
    a = R["diff"].abs().to_numpy()
    b = [np.median(rng.choice(a, len(a))) for _ in range(2000)]
    lo, hi = np.percentile(b, [2.5, 97.5])
    R.to_csv(REPO / "analysis/codesign/results/slatepose_vs_human.csv", index=False)
    pd.set_option("display.width", 200)
    print(R.round(4).to_string(index=False))
    print(f"{len(R)} physical dives: median |difference| {100 * np.median(a):.2f}% (95% CI {100 * lo:.2f}-{100 * hi:.2f}); "
          f"within one bar {int(R.within_1.sum())}, within two {int(R.within_2.sum())}; reading high {int(R.high.sum())} "
          f"(median signed {100 * R['diff'].median():+.2f}%)")


if __name__ == "__main__":
    main()
