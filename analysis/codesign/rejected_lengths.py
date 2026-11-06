"""Reef frames people rejected as unmeasurable that the fully automatic pipeline gave a length, for a person to judge.

Frames: stage_comparison.py's field frames on its 7 reef dives (279, 341, 347, 349, 383, 465, 471) with a head/tail row
but no coordinates (rejected by people) and a configuration-4 length (results/stage_comparison_frames.csv). The points
are configuration 4's, taken as stage_comparison.field() takes them: the run3 dot inside the laser region
(e2e_measurement/tail/reef_dots.jsonl) and v5's SimCC snout and fork (the keypoint experiment's seed "auto" row, else
data/e2e_rejected/headtail.jsonl). Length = configuration 4's (slate-pose-6 calibration, aim 0). Automatic, unreviewed.

Two steps:
  list    this repo's environment: uv run python analysis/codesign/rejected_lengths.py
          writes data/rejected_lengths/frames.csv (points) and review.csv (image_id, dive, length_cm, judgment blank:
          usable / not usable / unsure)
  render  NAS + the fishsense-services processor environment (fishsense-core 4.3.2):
          <procenv>/bin/python analysis/codesign/rejected_lengths.py render
          each frame as RectifiedImage(RawImage(raw)), fishsense-core's default decode, 2000 px wide, with the dot
          (green ring), snout (S) and fork (F) joined by a line, and the length, plus an enlarged inset of the fish
          (bottom right); data/rejected_lengths/{image_id}.jpg
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data/rejected_lengths"
NAS = Path.home() / "mnt/fishsense_data/REEF/data"
FIELD = (279, 341, 347, 349, 383, 465, 471)


def listing():
    import pandas as pd
    sys.path.insert(0, str(REPO / "analysis/codesign"))
    import stage_comparison as SC  # noqa: E402
    F = pd.read_csv(REPO / "analysis/codesign/results/stage_comparison_frames.csv", low_memory=False)
    F = F[(F.set == "field") & F.dive.isin(FIELD) & F.measured.astype(str).eq("False") & F["4 automatic"].notna()]
    T = pd.read_csv(REPO / "e2e_measurement/tail/frames.csv").drop_duplicates("image_id").set_index("image_id")
    kp = pd.read_csv(SC.KP).query("split == 'test' and seed == 'auto' and status == 'predicted'").set_index("image_id")
    rej = {r["image_id"]: r for r in map(json.loads, SC.REJECTED.open())}
    dots = SC.auto_dots()
    rows = []
    for r in F.itertuples():
        i = r.image_id
        if i in kp.index:
            k = kp.loc[i]; h, t, src = (k.head_x, k.head_y), (k.tail_x, k.tail_y), "keypoint experiment"
        else:
            h, t, src = rej[i]["simcc_head"], rej[i]["simcc_tail"], "rejected_headtail.py"
        rows.append(dict(image_id=i, dive=r.dive, camera_id=int(T.loc[i, "camera_id"]), path=T.loc[i, "path"],
                         dot_x=dots[i][0], dot_y=dots[i][1], snout_x=h[0], snout_y=h[1], fork_x=t[0], fork_y=t[1], points_from=src))
    P = pd.DataFrame(rows)
    P["length_cm"] = (100 * F.set_index("image_id").loc[P.image_id, "4 automatic"].to_numpy()).round(1)
    OUT.mkdir(parents=True, exist_ok=True)
    P.to_csv(OUT / "frames.csv", index=False)
    P[["image_id", "dive", "length_cm"]].assign(judgment="").to_csv(OUT / "review.csv", index=False)
    print(P[["image_id", "dive", "length_cm", "points_from"]].to_string(index=False))


def render():
    import cv2
    import numpy as np
    import pandas as pd
    from fishsense_core.camera_intrinsics import CameraIntrinsics
    from fishsense_core.image.raw_image import RawImage
    from fishsense_core.image.rectified_image import RectifiedImage
    I = pd.read_csv(REPO / "laser_detection_analysis/intrinsics.csv").set_index("camera_id")
    P = pd.read_csv(OUT / "frames.csv")
    for r in P.itertuples():
        cm, dist = (np.array(json.loads(I.loc[r.camera_id, k])) for k in ("camera_matrix", "distortion_coefficients"))
        img = RectifiedImage(RawImage((NAS / r.path).read_bytes()), CameraIntrinsics(cm, dist)).data
        img = np.ascontiguousarray(img)                   # already BGR uint8, as cv2 writes it (headtail_examples_render.py)
        s = lambda x, y: (int(round(x)), int(round(y)))  # noqa: E731
        h, f, d = s(r.snout_x, r.snout_y), s(r.fork_x, r.fork_y), s(r.dot_x, r.dot_y)
        cv2.line(img, h, f, (255, 255, 255), 6, cv2.LINE_AA); cv2.line(img, h, f, (0, 159, 230), 3, cv2.LINE_AA)
        for p, lab in ((h, "S"), (f, "F")):
            cv2.circle(img, p, 14, (0, 159, 230), -1, cv2.LINE_AA); cv2.circle(img, p, 14, (255, 255, 255), 3, cv2.LINE_AA)
            cv2.putText(img, lab, (p[0] + 20, p[1] - 20), cv2.FONT_HERSHEY_SIMPLEX, 2.0, (255, 255, 255), 8, cv2.LINE_AA)
            cv2.putText(img, lab, (p[0] + 20, p[1] - 20), cv2.FONT_HERSHEY_SIMPLEX, 2.0, (0, 0, 0), 3, cv2.LINE_AA)
        cv2.circle(img, d, 28, (255, 255, 255), 7, cv2.LINE_AA); cv2.circle(img, d, 28, (0, 200, 0), 4, cv2.LINE_AA)
        txt = f"image {r.image_id}  dive {r.dive}  automatic length {r.length_cm:.1f} cm (unreviewed)"
        cv2.putText(img, txt, (40, 110), cv2.FONT_HERSHEY_SIMPLEX, 2.6, (0, 0, 0), 12, cv2.LINE_AA)
        cv2.putText(img, txt, (40, 110), cv2.FONT_HERSHEY_SIMPLEX, 2.6, (255, 255, 255), 4, cv2.LINE_AA)
        out = cv2.resize(img, (2000, round(2000 * img.shape[0] / img.shape[1])), interpolation=cv2.INTER_AREA)
        # inset: the fish enlarged, from the full-resolution frame, in the bottom-right corner
        pts = np.array([h, f, d], float); L = np.hypot(*np.subtract(h, f))
        pad = max(200.0, 0.8 * L); (x0, y0), (x1, y1) = pts.min(0) - pad, pts.max(0) + pad
        cx, cy, half = (x0 + x1) / 2, (y0 + y1) / 2, max(x1 - x0, (y1 - y0) * 4 / 3) / 2
        x0, x1 = int(max(0, cx - half)), int(min(img.shape[1], cx + half))
        y0, y1 = int(max(0, cy - half * 3 / 4)), int(min(img.shape[0], cy + half * 3 / 4))
        ins = cv2.resize(img[y0:y1, x0:x1], (800, round(800 * (y1 - y0) / (x1 - x0))), interpolation=cv2.INTER_AREA)
        H, W = out.shape[:2]; ih, iw = ins.shape[:2]
        out[H - ih - 20:H - 20, W - iw - 20:W - 20] = ins
        cv2.rectangle(out, (W - iw - 22, H - ih - 22), (W - 18, H - 18), (255, 255, 255), 4)
        cv2.imwrite(str(OUT / f"{r.image_id}.jpg"), out, [cv2.IMWRITE_JPEG_QUALITY, 88])
        print(r.image_id, flush=True)


if __name__ == "__main__":
    render() if sys.argv[1:2] == ["render"] else listing()
