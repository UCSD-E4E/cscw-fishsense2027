"""Apparent slate size from the slate project's rigid-board fit to the SAM 3.1 mask.

The slate project (2026-10-03_slate_detector, src/slate_detector/rectfit.py, uncommitted as of
2026-10-06) fits the slate as a rigid rounded rectangle (aspect 0.708, corner radius 3.1% of the
width) seen through the camera's known intrinsics, to the SAM 3.1 "white board" mask. The fit's
pose (rvec, tvec, in units of the board's width) restores the parts a diver's hand hides and
undoes the board's tilt, both of which bias sqrt(mask area).

Two sizes, each 1 / distance in board widths (only ratios within a session matter, so the board's
real size is never used):
  sam3_rect_centre   1 / Z of the board's centre
  sam3_rect_dot_tilt30  as sam3_rect_dot, without frames whose fitted tilt exceeds 30 deg. Diagnostic:
                     above 45 deg the fitted depth disagrees with sqrt(area) by a median 33% (29 pool
                     frames, 5 sessions) - wrong poses, not real tilts; below 20 deg they agree to < 1%
  sam3_rect_dot      1 / Z of the point where the laser dot's ray meets the fitted board plane: the
                     depth size constancy actually assumes, since the dot is rarely at the centre

Input: data/masks/rect.json in the slate project, copied for these frames to rect_poses.json (used
when the slate project is not on disk). For every
frame used here the slate project chose the same SAM candidate a label-free choice would (the
highest-scoring mask under the human dot), checked when this was written, so these sizes use no
slate labels. Frame-cache coordinates are 1600 px wide; K is scaled to match (rectfit.scaled_K).

Writes sizes/sam3_rect_{centre,dot}.csv (pool sessions, picked up by tape_by_session.py) and
reef_sizes/sam3_rect_{centre,dot}.csv (reef dives, reef_labelfree.py).
Run: uv run python calibration_analysis/e1j_size_constancy/rectfit_sizes.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.spatial.transform import Rotation

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SLATE = REPO.parent / "2026-10-03_slate_detector" / "data" / "masks"
CACHE_W, PHOTO_W = 1600, 4014
MAX_TILT = 30.0   # sam3_rect_dot_tilt30 drops fits the fit itself calls more tilted than this


def sizes(frames: pd.DataFrame, rect: dict, intr: dict, cams: dict) -> pd.DataFrame:
    rows = []
    for r in frames.itertuples():
        f = rect.get(str(r.image_id))
        if not f or not f["plausible"]:
            continue
        K = intr[cams[int(r.image_id)]].copy(); K[:2] *= CACHE_W / PHOTO_W
        R = Rotation.from_rotvec(np.array(f["rvec"], float)).as_matrix(); t = np.array(f["tvec"], float)
        n = R[:, 2]
        d = np.linalg.solve(K, [r.dot_x * CACHE_W / PHOTO_W, r.dot_y * CACHE_W / PHOTO_W, 1.0])
        z_dot = float(n @ t / (n @ d)) * d[2]
        z_centre = float((R @ [0.5, 0.354, 0.0] + t)[2])     # board centre: width 1, height 0.708
        rows.append(dict(image_id=int(r.image_id), centre=1.0 / z_centre, dot=1.0 / z_dot,
                         tilt_deg=float(np.degrees(np.arccos(abs(n[2])))), extra=f["extra"]))
    return pd.DataFrame(rows)


POSES = HERE / "rect_poses.json"   # the slate project's fits for the frames used here, copied for reproducibility


def poses(frame_ids) -> dict:
    """Fits for these frames: refreshed from the slate project when it is on disk, else the committed copy."""
    if (SLATE / "rect.json").is_file():
        rect = json.loads((SLATE / "rect.json").read_text())
        keep = {str(i): {k: rect[str(i)][k] for k in ("rvec", "tvec", "plausible", "covered", "extra", "cost")}
                for i in sorted(frame_ids) if rect.get(str(i))}
        POSES.write_text(json.dumps(keep, indent=0))
    return json.loads(POSES.read_text())


def main():
    ids = set(pd.read_csv(HERE / "sizes_frames.csv").image_id) | set(pd.read_csv(HERE / "reef_sizes_frames.csv").image_id)
    rect = poses(ids)
    intr = {int(r.camera_id): np.array(json.loads(r.camera_matrix)) for r in pd.read_csv(REPO / "laser_detection_analysis/intrinsics.csv").itertuples()}
    dive_cam = {int(r.dive_id): int(r.camera_id) for r in pd.read_csv(REPO / "e2e_measurement/extrinsics.psv", sep="|").itertuples()}
    for frames_file, out in (("sizes_frames.csv", "sizes"), ("reef_sizes_frames.csv", "reef_sizes")):
        F = pd.read_csv(HERE / frames_file)
        cams = {int(r.image_id): dive_cam[int(r.dive_id)] for r in F.itertuples()}
        D = sizes(F, rect, intr, cams)
        (HERE / out).mkdir(exist_ok=True)
        for col in ("centre", "dot"):
            D[["image_id", col]].rename(columns={col: "size"}).to_csv(HERE / out / f"sam3_rect_{col}.csv", index=False)
        # diagnostic: the fit's own tilt flags its wrong poses (depth off ~33% vs sqrt(area) above 45 deg)
        ok = D[D.tilt_deg <= MAX_TILT]
        ok[["image_id", "dot"]].rename(columns={"dot": "size"}).to_csv(HERE / out / "sam3_rect_dot_tilt30.csv", index=False)
        print(f"{out}: {len(D)} of {len(F)} frames; tilt median {D.tilt_deg.median():.1f} deg (p90 {D.tilt_deg.quantile(.9):.1f}); "
              f"unseen outline median {D.extra.median():.1%}")


if __name__ == "__main__":
    main()
