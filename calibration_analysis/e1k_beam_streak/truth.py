"""E1k accuracy: streak apex vs the slate calibration's vanishing point.

The stored laser axis a (camera frame) projects to the rectified vanishing point
v = (fx*ax/az + cx, fy*ay/az + cy). Its coordinate along the dive line (probe.py's
orientation, recomputed from the same dots) is the true t_v; its distance off the line is
a consistency check on the stored line. The streak's t_v comes from wedge.py.

Run:  ../../../wuwnet-fishsense2026/.venv/bin/python truth.py 347 349 436 465 471
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np, pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import probe  # noqa: E402
import wedge  # noqa: E402
import glow  # noqa: E402

F_PX = 2850.0


def true_tv(dive):
    T = pd.read_csv(probe.SCRATCH / "green_truth.psv", sep="|", header=None, names=["dive", "camera", "pos", "axis"]).set_index("dive")
    intr = {int(r.camera_id): json.loads(r.camera_matrix) for r in pd.read_csv(probe.rw.REPO / "laser_detection_analysis/intrinsics.csv").itertuples()}
    ax = np.array(json.loads(T.loc[dive, "axis"])); K = np.array(intr[int(T.loc[dive, "camera"])])
    v = np.array([K[0, 0] * ax[0] / ax[2] + K[0, 2], K[1, 1] * ax[1] / ax[2] + K[1, 2]])
    D = pd.read_csv(probe.SCRATCH / "field_dots.psv", sep="|", header=None,
                    names=["dive_id", "camera_id", "image_id", "path", "x", "y", "label", "depth_m", "range_m"])
    g = D[(D.dive_id == dive) & D.label.str.contains("Laser")].drop_duplicates("image_id")
    a, b, c = probe.LINES[dive]
    u, n, foot, _ = probe.line_frame(a, b, c, g[["x", "y"]].to_numpy(float))
    return float((v - foot) @ u), float((v - foot) @ n)


if __name__ == "__main__":
    rows = []
    for d in map(int, sys.argv[1:]):
        tv_true, off = true_tv(d)
        for cue, fn in (("width", lambda: wedge.run(d, n_boot=60, quiet=True)), ("brightness", lambda: glow.run(d, n_boot=60))):
            tv_streak, se = fn()
            err = tv_streak - tv_true
            rows.append(dict(dive=d, cue=cue, tv_true=tv_true, true_off_line_px=off, tv_streak=tv_streak, se_px=se,
                             err_px=err, err_deg=np.degrees(err / F_PX), se_deg=np.degrees(se / F_PX)))
    R = pd.DataFrame(rows)
    print(R.round(2).to_string(index=False))
    for cue, g in R.groupby("cue"):
        print(f"{cue}: |error| median {g.err_deg.abs().median():.2f} deg; within 1 deg: {(g.err_deg.abs() <= 1).sum()} of {len(g)}; "
              f"errors within 2 SE: {(g.err_px.abs() <= 2 * g.se_px).sum()}")
