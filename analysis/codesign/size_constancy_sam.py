"""Size constancy with SAM 3 segmentation vs labelled corners, on the 10 pool laser-calibration sessions.

Size constancy (this paper's laser-calibration method): a rigid object of unknown size shot near
and far; its apparent size and the laser dot's distance from the vanishing point both go as
1/range, so the vanishing point is where apparent size would reach zero along the dive's laser
line. Two interfaces to the same quantity:

  sam3     machine: sqrt(area) of SAM 3's "white board" mask under the laser dot
           (calibration_analysis/e1j_size_constancy/sizes/sam3_text.csv; SAM 3.1 checkpoint, the one
           production runs)
  corners  human: RMS spread of the labelled slate reference points about their centroid
           (slate_unknown.load: complete labels only)

Both are fitted on the SAME frames (frames with a complete corner label and a SAM size), on the
session's laser line (labelfree_tv.csv: direction and offset), with the human-clicked laser dot.
A third row per session, sam3_all, uses every frame with a SAM size (the label-free variant as it
would run). The estimator is slate_unknown.fit_tv.

Reference: the stored known-size calibration (production: slate template + human corners + |O|
fitted per dive). It is not ground truth; tape-measured lengths are (tape_by_session.py and the
stage ladder in e2e_measurement/score.py).

  err_deg       signed offset of the fitted vanishing point from the stored one along the line,
                in degrees (px / slate_unknown.F_PX), as in earlier E1j tables
  angle_deg     3D angle between the fitted and stored laser axes
  se_deg        bootstrap SE of the vanishing point (resampling frames), in degrees
Target: 0.05 deg.

A fourth row per session, sam3_predline, replaces the human-fitted laser line (direction from the
dive's divelaserline, offset from the human dots) with a line fitted to the deployed detector's own
confident predictions on that dive (T3's sample, laser_detection_analysis/; RANSAC, 10 px, then total
least squares). It still uses the human dot on each slate frame.

Writes analysis/codesign/results/size_constancy_sessions.csv and, for the stage ladder,
calibration_analysis/e1j_size_constancy/labelfree_sam3_tv.csv (same schema as labelfree_tv.csv,
from the sam3_all fit).
Run: uv run python analysis/codesign/size_constancy_sam.py
"""
from __future__ import annotations

import json, sys

import numpy as np
import pandas as pd

from fishsense_cscw.paths import REPO

E1J = REPO / "calibration_analysis/e1j_size_constancy"
sys.path.insert(0, str(E1J)); sys.path.insert(0, str(REPO / "e2e_measurement"))
import slate_unknown as su  # noqa: E402
import score as S  # noqa: E402

OUT = REPO / "analysis/codesign/results"
TARGET, N_BOOT = 0.05, 500
RANSAC_TOL = 10.0


def prediction_lines() -> dict:
    """Per dive: (u, offset) of a line fitted to the deployed detector's confident predictions (T3 sample)."""
    T = pd.read_csv(REPO / "laser_detection_analysis/sample.csv")[["image_id", "dive_id"]]
    P = pd.read_csv(REPO / "laser_detection_analysis/predictions.csv")
    P = P[(P.condition == "production") & (P.confidence >= 0.5)].merge(T, on="image_id")
    rng = np.random.default_rng(0); out = {}
    for dive, g in P.groupby("dive_id"):
        xy = g[["pred_x", "pred_y"]].to_numpy(float)
        if len(xy) < 3:
            continue
        best = None
        for _ in range(500):
            i, j = rng.choice(len(xy), 2, replace=False); d = xy[j] - xy[i]
            if np.hypot(*d) < 1:
                continue
            nn = np.array([-d[1], d[0]]) / np.hypot(*d)
            inl = np.abs(xy @ nn - nn @ xy[i]) <= RANSAC_TOL
            if best is None or inl.sum() > best.sum():
                best = inl
        q = xy[best]; m = q.mean(0); u = np.linalg.svd(q - m)[2][0]
        u = u if u[1] < 0 else -u                      # same orientation convention as slate_unknown.frame
        out[int(dive)] = (u, float(m @ np.array([-u[1], u[0]])), int(best.sum()), len(xy))
    return out


def main():
    L = pd.read_csv(E1J / "labelfree_tv.csv").set_index("dive")
    stored, _, intr = S.calibrations()
    cams = {int(r.dive_id): int(r.camera_id) for r in pd.read_csv(REPO / "e2e_measurement/extrinsics.psv", sep="|").itertuples()}
    sam = pd.read_csv(E1J / "sizes/sam3_text.csv").set_index("image_id")["size"]
    dots = pd.read_csv(E1J / "sizes_frames.csv").set_index("image_id")
    corners, *_ = su.load()
    corners = corners.set_index("image_id")
    rng = np.random.default_rng(0)
    PL = prediction_lines()
    rows, lf, lfp = [], [], []
    for dive in L.index:
        u = np.array([L.loc[dive, "ux"], L.loc[dive, "uy"]]); off = L.loc[dive, "line_offset"]; n = np.array([-u[1], u[0]])
        K = intr[cams[dive]]
        sa = stored[dive][1] / np.linalg.norm(stored[dive][1]); vs = K @ sa; tv_true = float((vs[:2] / vs[2]) @ u)
        f_all = [i for i in dots.index[dots.dive_id == dive] if i in sam.index]
        f_common = [i for i in f_all if i in corners.index]
        variants = [("sam3", f_common, lambda i: sam[i], u, off), ("corners", f_common, lambda i: corners.loc[i, "size"], u, off),
                    ("sam3_all", f_all, lambda i: sam[i], u, off)]
        if dive in PL:
            variants.append(("sam3_predline", f_all, lambda i: sam[i], PL[dive][0], PL[dive][1]))
        for name, ids, size, u, off in variants:
            n = np.array([-u[1], u[0]])
            xy = dots.loc[ids, ["dot_x", "dot_y"]].to_numpy(float)
            t = xy @ u; s = np.array([size(i) for i in ids], float)
            tv = su.fit_tv(t, s)
            boots = [su.fit_tv(t[k], s[k]) for k in (rng.integers(0, len(t), len(t)) for _ in range(N_BOOT))]
            v = tv * u + off * n
            ax = np.linalg.solve(K, [v[0], v[1], 1.0]); ax /= np.linalg.norm(ax)
            tv_true = float((vs[:2] / vs[2]) @ u)
            rows.append(dict(session=int(dive), method=name, frames=len(ids), size_spread=float(s.max() / s.min()),
                             line_points=(f"{PL[dive][2]}/{PL[dive][3]}" if name == "sam3_predline" else ""),
                             err_deg=float(np.degrees((tv - tv_true) / su.F_PX)), angle_deg=float(np.degrees(np.arccos(np.clip(ax @ sa, -1, 1)))),
                             se_deg=float(np.degrees(np.std(boots) / su.F_PX))))
            if name == "sam3_predline":
                lfp.append(dict(dive=int(dive), ux=u[0], uy=u[1], line_offset=off, frames=len(ids), size_ratio=float(s.max() / s.min()),
                                tv_fit=tv, se_px=float(np.std(boots)), err_px=float(tv - tv_true), err_deg=float(np.degrees((tv - tv_true) / su.F_PX))))
            if name == "sam3_all":
                lf.append(dict(dive=int(dive), ux=u[0], uy=u[1], line_offset=off, frames=len(ids), size_ratio=float(s.max() / s.min()),
                               tv_fit=tv, se_px=float(np.std(boots)), err_px=float(tv - tv_true),
                               err_deg=float(np.degrees((tv - tv_true) / su.F_PX))))
    R = pd.DataFrame(rows)
    R["within_target"] = R.err_deg.abs() <= TARGET
    OUT.mkdir(parents=True, exist_ok=True)
    R.to_csv(OUT / "size_constancy_sessions.csv", index=False, float_format="%.5f")
    pd.DataFrame(lf).to_csv(E1J / "labelfree_sam3_tv.csv", index=False)
    pd.DataFrame(lfp).to_csv(E1J / "labelfree_sam3_predline_tv.csv", index=False)
    piv = R.pivot(index="session", columns="method", values="err_deg")
    pd.set_option("display.width", 200)
    print(R.pivot(index="session", columns="method", values=["frames", "size_spread", "err_deg", "se_deg"]).round(3).to_string())
    for m in ("sam3", "corners", "sam3_all", "sam3_predline"):
        e = R[R.method == m].err_deg.abs()
        print(f"{m:9s} |err| median {e.median():.3f} deg, max {e.max():.3f}; within 0.05: {(e <= TARGET).sum()}/{len(e)}")
    d = (piv.sam3 - piv.corners)
    print(f"sam3 - corners (same frames): median |diff| {d.abs().median():.3f} deg, max {d.abs().max():.3f}; "
          f"corr {np.corrcoef(piv.sam3, piv.corners)[0, 1]:.2f}")


if __name__ == "__main__":
    main()
