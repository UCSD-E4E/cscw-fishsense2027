"""Pool size constancy (SAM 3) against the stored calibration, with the along-line offset in each session camera's
own focal length.

size_constancy_sam.py stores err_deg = vanishing-point offset along the line (px) / slate_unknown.F_PX (a fixed
2,850 px). This converts the same offset with the session camera's fx (laser_detection_analysis/intrinsics.csv,
camera from e2e_measurement/extrinsics.psv): err_deg_fx = atan(err_px / fx). It also reports the stored 3D angle
between the fitted and stored laser axes (angle_deg), unchanged.

Per metric: median and max |error| over the 10 pool sessions, sessions within 0.05 deg, and a 95% interval for the
median resampling sessions (each pool session is one physical dive; 2,000 draws, seed 0).
Input: analysis/codesign/results/size_constancy_sessions.csv (method sam3). Writes results/size_constancy_fx.csv.
Run: uv run python analysis/codesign/size_constancy_fx.py
"""
from __future__ import annotations

import json
import sys

import numpy as np
import pandas as pd

from fishsense_cscw.paths import REPO

sys.path.insert(0, str(REPO / "calibration_analysis/e1j_size_constancy"))
import slate_unknown as su  # noqa: E402

TARGET = 0.05


def main():
    R = pd.read_csv(REPO / "analysis/codesign/results/size_constancy_sessions.csv").query("method == 'sam3'").copy()
    cam = pd.read_csv(REPO / "e2e_measurement/extrinsics.psv", sep="|").set_index("dive_id").camera_id
    intr = {int(r.camera_id): np.array(json.loads(r.camera_matrix)) for r in pd.read_csv(REPO / "laser_detection_analysis/intrinsics.csv").itertuples()}
    R["fx"] = R.session.map(lambda s: intr[int(cam[s])][0, 0])
    R["err_px"] = np.radians(R.err_deg) * su.F_PX
    R["err_deg_fx"] = np.degrees(np.arctan(R.err_px / R.fx))
    R[["session", "frames", "fx", "err_px", "err_deg", "err_deg_fx", "angle_deg"]].to_csv(
        REPO / "analysis/codesign/results/size_constancy_fx.csv", index=False)
    rng = np.random.default_rng(0)
    for col, name in (("err_deg", f"along line, fixed {su.F_PX:.0f} px"), ("err_deg_fx", "along line, camera fx"), ("angle_deg", "3D angle between axes")):
        a = R[col].abs().to_numpy()
        b = [np.median(rng.choice(a, len(a))) for _ in range(2000)]
        lo, hi = np.percentile(b, [2.5, 97.5])
        print(f"{name:28s} median {np.median(a):.3f} deg (95% CI {lo:.3f}-{hi:.3f}), max {a.max():.3f}, "
              f"within {TARGET}: {(a <= TARGET).sum()}/{len(a)}"
              + ("" if (a <= TARGET).all() else f" (fails: {', '.join(map(str, R.session[a > TARGET]))})"))
    print(f"fx {R.fx.min():.0f}-{R.fx.max():.0f} px over {len(R)} sessions")


if __name__ == "__main__":
    main()
