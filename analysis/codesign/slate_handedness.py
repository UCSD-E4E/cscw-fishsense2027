"""Mirrored human slate labels, and what dive 436's stored calibration says once its labels are un-mirrored.

1 handedness  For every live human slate label in the frozen 2026-09-25 dump (data/db_extracts/slate_label_points.psv,
              skipped points dropped), the 2D affine map from its template's reference points (slate_templates.psv,
              the dive's slate from annotations.psv) to the clicked points. A camera sees a flat board's face
              without mirroring, so the map's determinant is positive; a negative one means the clicks are numbered
              as a mirror image of the template.
2 dive 436    Each slate frame's pose by PnP (planar IPPE) from (a) the clicks as recorded and (b) the clicks re-numbered:
              the assignment of template points to the clicks, over every ordered choice, that keeps the template's
              handedness and has the smallest PnP reprojection error. The human laser dot's ray meets each pose's
              plane at range Z_pose. Against it, the stored v1 calibration's range at the same dot (e2e score.depth):
              ratio = Z_stored / Z_pose - 1. With (a) the ratio says how well the stored beam fits the mirrored poses
              it was built from; with (b), how far it sits from the corrected poses (its scale error).
Writes analysis/codesign/results/slate_handedness.csv and slate_handedness_436.csv.
Run: uv run --with opencv-python-headless python analysis/codesign/slate_handedness.py
"""
from __future__ import annotations

import itertools
import json
import sys

import cv2
import numpy as np
import pandas as pd

from fishsense_cscw.paths import REPO

sys.path.insert(0, str(REPO / "e2e_measurement"))
import score as S  # noqa: E402

DB = REPO / "data/db_extracts"


def inputs():
    T = pd.read_csv(DB / "slate_templates.psv", sep="|", header=None, names=["tid", "name", "dpi", "pts"])
    tpl = {r.name: np.array(json.loads(r.pts), float) / r.dpi * 0.0254 for r in T.itertuples()}
    a = pd.read_csv(DB / "annotations.psv", sep="|", header=None, usecols=[0, 3, 12], names=["kind", "dive_id", "slate"])
    name = a[(a.kind == "slate") & a.slate.notna()].drop_duplicates("dive_id").set_index("dive_id").slate
    L = pd.read_csv(DB / "slate_label_points.psv", sep="|", header=None, names=["image_id", "dive_id", "camera_id", "pts", "skipped", "upside"])
    L = L[L.pts.map(lambda s: isinstance(s, str))]
    return tpl, name, L


def det_sign(src, dst):
    A = np.c_[src, np.ones(len(src))]
    M = np.linalg.lstsq(A, dst, rcond=None)[0][:2].T
    return float(np.linalg.det(M))


def handedness(tpl, name, L):
    rows = []
    for r in L.itertuples():
        nm = name.get(r.dive_id)
        if nm not in tpl:
            continue
        skip = json.loads(r.skipped) if isinstance(r.skipped, str) and r.skipped not in ("null", "") else []
        keep = [i for i in range(len(tpl[nm])) if i not in (skip or [])]
        img = np.array(json.loads(r.pts), float)
        if len(img) != len(keep) or len(keep) < 3:
            continue
        rows.append(dict(image_id=r.image_id, dive=r.dive_id, template=nm, det=det_sign(tpl[nm][keep], img)))
    R = pd.DataFrame(rows)
    R["mirrored"] = R.det < 0
    R.to_csv(REPO / "analysis/codesign/results/slate_handedness.csv", index=False)
    g = R.groupby("dive").mirrored.agg(["sum", "size"])
    print(f"1 handedness: {len(R)} live human slate labels on {R.dive.nunique()} dives; mirrored {int(R.mirrored.sum())}, "
          f"on dives {g[g['sum'] > 0].to_dict('index')}")
    return R


def pnp(obj, img, K):
    o3 = np.c_[obj, np.zeros(len(obj))]
    ok, rv, tv = cv2.solvePnP(o3, img, K, None, flags=cv2.SOLVEPNP_IPPE)
    proj, _ = cv2.projectPoints(o3, rv, tv, K, None)
    R, _ = cv2.Rodrigues(rv)
    return float(np.sqrt(((proj.reshape(-1, 2) - img) ** 2).sum(1).mean())), R, tv.ravel(), o3


def dive436(tpl, name, L):
    E = pd.read_csv(REPO / "e2e_measurement/extrinsics.psv", sep="|").set_index("dive_id")
    O, a = np.array(json.loads(E.loc[436, "laser_position"])), np.array(json.loads(E.loc[436, "laser_axis"]))
    intr = {int(r.camera_id): np.array(json.loads(r.camera_matrix)) for r in pd.read_csv(REPO / "laser_detection_analysis/intrinsics.csv").itertuples()}
    K = intr[int(E.loc[436, "camera_id"])]
    dots = pd.read_csv(DB / "slate_dots.psv", sep="|", header=None, names=["dive_id", "camera_id", "image_id", "pts", "x", "y", "taken"]).drop_duplicates("image_id").set_index("image_id")
    obj = tpl[name[436]]
    rows = []
    for r in L[L.dive_id == 436].itertuples():
        img = np.array(json.loads(r.pts), float)
        skip = json.loads(r.skipped) if isinstance(r.skipped, str) and r.skipped not in ("null", "") else []
        keep = [i for i in range(len(obj)) if i not in (skip or [])]
        if r.image_id not in dots.index or pd.isna(dots.loc[r.image_id, "x"]):
            continue
        x, y = dots.loc[r.image_id, ["x", "y"]].astype(float)
        ray = np.linalg.solve(K, [x, y, 1.0])
        z_stored = S.depth(K, O, a, x, y)

        def range_on(idx):
            rms, Rm, tv, o3 = pnp(obj[list(idx)], img, K)
            n, c = Rm[:, 2], Rm @ o3.mean(0) + tv
            return rms, float((n @ c) / (n @ ray) * ray[2])

        rec_rms, rec_z = range_on(keep)
        best = min((range_on(p) + (p,) for p in itertools.permutations(range(len(obj)), len(img))
                    if det_sign(obj[list(p)], img) > 0), key=lambda v: v[0])
        rows.append(dict(image_id=r.image_id, recorded_det=det_sign(obj[keep], img), recorded_rms_px=rec_rms,
                         recorded_ratio=z_stored / rec_z - 1, corrected_order=" ".join(map(str, best[2])),
                         corrected_rms_px=best[0], corrected_ratio=z_stored / best[1] - 1))
    R = pd.DataFrame(rows)
    R.to_csv(REPO / "analysis/codesign/results/slate_handedness_436.csv", index=False)
    print(f"2 dive 436 ({name[436]}): {len(R)} slate frames with a human dot")
    print(R.round(4).to_string(index=False))
    m = R[R.recorded_det < 0]
    print(f"   mirrored frames ({len(m)}): stored beam vs pose range, recorded clicks median {100 * m.recorded_ratio.median():+.1f}% "
          f"(rms {m.recorded_rms_px.median():.1f} px); re-numbered clicks median {100 * m.corrected_ratio.median():+.1f}% "
          f"(rms {m.corrected_rms_px.median():.1f} px)")


def main():
    tpl, name, L = inputs()
    handedness(tpl, name, L)
    dive436(tpl, name, L)


if __name__ == "__main__":
    main()
