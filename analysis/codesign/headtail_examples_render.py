"""Render the three head/tail example crops (results/headtail_examples.csv, headtail_examples_select.py).

Each frame as the keypoints saw it: RectifiedImage(RawImage(raw), intrinsics), fishsense-core's default decode,
cut to the stored crop box. Only these three RAW files are read from the NAS.
Writes data/headtail_examples/{image_id}.jpg (crop) and crops.csv (the box actually cut, clipped to the frame).
Run (NAS, the fishsense-services processor environment, fishsense-core 4.3.2):
  <procenv>/bin/python analysis/codesign/headtail_examples_render.py
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
NAS = Path.home() / "mnt/fishsense_data/REEF/data"
OUT = REPO / "data/headtail_examples"


def main():
    import cv2
    import numpy as np
    import pandas as pd
    from fishsense_core.camera_intrinsics import CameraIntrinsics
    from fishsense_core.image.raw_image import RawImage
    from fishsense_core.image.rectified_image import RectifiedImage

    I = pd.read_csv(REPO / "laser_detection_analysis/intrinsics.csv").set_index("camera_id")
    E = pd.read_csv(REPO / "analysis/codesign/results/headtail_examples.csv")
    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    for r in E.itertuples():
        cm, dist = (np.array(json.loads(I.loc[r.camera_id, k])) for k in ("camera_matrix", "distortion_coefficients"))
        img = RectifiedImage(RawImage((NAS / r.path).read_bytes()), CameraIntrinsics(cm, dist)).data
        h, w = img.shape[:2]
        x0, y0 = max(0, int(round(r.crop_x0))), max(0, int(round(r.crop_y0)))
        x1, y1 = min(w, int(round(r.crop_x1))), min(h, int(round(r.crop_y1)))
        crop = img[y0:y1, x0:x1]
        crop = cv2.resize(crop, (900, round(900 * (y1 - y0) / (x1 - x0))), interpolation=cv2.INTER_AREA)
        cv2.imwrite(str(OUT / f"{r.image_id}.jpg"), crop, [cv2.IMWRITE_JPEG_QUALITY, 92])   # data is BGR, as cv2 writes it
        rows.append(dict(image_id=r.image_id, x0=x0, y0=y0, x1=x1, y1=y1, frame_w=w, frame_h=h, out_w=crop.shape[1], out_h=crop.shape[0]))
        print(r.image_id, img.shape, (x0, y0, x1, y1), flush=True)
    pd.DataFrame(rows).to_csv(OUT / "crops.csv", index=False)


if __name__ == "__main__":
    main()
