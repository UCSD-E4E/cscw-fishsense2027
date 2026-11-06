"""Render the dive 436 slate frame for fig_dive436 (slate_handedness.py's frame 121793, the mirrored frame whose recorded
reprojection error is the median of the dive's mirrored frames, 5.6 px).

RectifiedImage(RawImage(raw), intrinsics), fishsense-core's default decode, the frame the labels were drawn on, cut to a
4:3 box centered on the human clicks (data/db_extracts/slate_label_points.psv), 700 px wide, tight enough to
show the slate and not the diver holding it. Only this RAW file is read.
Writes data/dive436/121793.jpg and crop.csv.
Run (NAS, the fishsense-services processor environment, fishsense-core 4.3.2):
  <procenv>/bin/python analysis/codesign/dive436_render.py
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
NAS = Path.home() / "mnt/fishsense_data/REEF/data"
IMAGE, CAMERA, W = 121793, 4, 700
PATH = "2025-02-10 REEF Data Dump SMILE 6/101624_Alligator/101624_Alligator_FSL04/101624_Alligator0_FSL04/PA160035.ORF"
HALF_W = 290                                   # crop half-width in frame px: the slate only, not the diver holding it


def main():
    import cv2
    import numpy as np
    import pandas as pd
    from fishsense_core.camera_intrinsics import CameraIntrinsics
    from fishsense_core.image.raw_image import RawImage
    from fishsense_core.image.rectified_image import RectifiedImage

    I = pd.read_csv(REPO / "laser_detection_analysis/intrinsics.csv").set_index("camera_id")
    cm, dist = (np.array(json.loads(I.loc[CAMERA, k])) for k in ("camera_matrix", "distortion_coefficients"))
    L = pd.read_csv(REPO / "data/db_extracts/slate_label_points.psv", sep="|", header=None, names=["image_id", "dive_id", "camera_id", "pts", "skipped", "upside"])
    c = np.array(json.loads(L[L.image_id == IMAGE].pts.iloc[0]), float).mean(0)
    img = RectifiedImage(RawImage((NAS / PATH).read_bytes()), CameraIntrinsics(cm, dist)).data
    x0, y0 = int(round(c[0] - HALF_W)), int(round(c[1] - HALF_W * 3 / 4))
    x1, y1 = x0 + 2 * HALF_W, y0 + int(round(HALF_W * 3 / 2))
    crop = cv2.resize(img[y0:y1, x0:x1], (W, round(W * (y1 - y0) / (x1 - x0))), interpolation=cv2.INTER_AREA)
    out = REPO / "data/dive436"; out.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out / f"{IMAGE}.jpg"), crop, [cv2.IMWRITE_JPEG_QUALITY, 92])
    pd.DataFrame([dict(image_id=IMAGE, x0=x0, y0=y0, x1=x1, y1=y1, out_w=crop.shape[1], out_h=crop.shape[0])]).to_csv(out / "crop.csv", index=False)
    print(img.shape, (x0, y0, x1, y1))


if __name__ == "__main__":
    main()
