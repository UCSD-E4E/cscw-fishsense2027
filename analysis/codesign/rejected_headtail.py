"""v5 head/tail on the 32 human-rejected field frames the §6 stage comparison had no SimCC keypoints for.

stage_comparison.py takes SimCC keypoints from the keypoint experiment, which ran only on frames people measured.
These 32 frames (a head/tail row without coordinates, on field dives 279, 341, 347, 349, 471;
data/e2e_rejected/images.psv) had a SAM mask at the automatic dot in the 2026-09-29 run but no SimCC row. This runs
production's automatic head/tail chain on them, as stereo_new_fish.py does:
  dot        the comparison's own run3 dot (e2e_measurement/tail/reef_dots.jsonl), inside the laser region
  render     RectifiedImage(RawImage(raw), intrinsics), fishsense-core's default decode
  fish       find_fish_at_dot(render, [dot], Sam3Segmenter(sam3.1_multiplex), grow_cut_masks=True, score_gate=0.5)
  head/tail  SimCC (simcc-sam-e12) on the kept mask's box, with the mask rule's points for the 15% review check
Writes data/e2e_rejected/headtail.jsonl (resumable); stage_comparison.py reads it.
Run (GPU + NAS, the fishsense-services processor environment, fishsense-core 4.3.2):
  LD_LIBRARY_PATH=<driver, libstdc++, libz> <procenv>/bin/python analysis/codesign/rejected_headtail.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
NAS = Path.home() / "mnt/fishsense_data/REEF/data"
OUT = REPO / "data/e2e_rejected/headtail.jsonl"
SAM3_CKPT = Path.home() / "Downloads/sam3.1_multiplex.pt"
SIMCC_CKPT = Path.home() / ".cache/fishsense-kp/headtail-keypoints/simcc-sam-e12/simcc_sam_best_length.pt"
SCORE_GATE = 0.5


def main():
    import numpy as np
    import pandas as pd
    import torch
    from fishsense_core.camera_intrinsics import CameraIntrinsics
    from fishsense_core.fish.fish_at_dot import Sam3Segmenter, find_fish_at_dot
    from fishsense_core.fish.headtail_keypoints import HeadTailKeypointDetector
    from fishsense_core.fish.sam3 import build_segmenter
    from fishsense_core.image.raw_image import RawImage
    from fishsense_core.image.rectified_image import RectifiedImage

    sys.path.insert(0, str(REPO / "analysis/codesign"))
    from laser_region import in_region  # noqa: E402

    I = pd.read_csv(REPO / "laser_detection_analysis/intrinsics.csv").set_index("camera_id")
    imgs = [l.rstrip("\n").split("|") for l in (REPO / "data/e2e_rejected/images.psv").open()]
    dots = {}
    for l in (REPO / "e2e_measurement/tail/reef_dots.jsonl").open():
        r = json.loads(l)
        if (r.get("dot") or {}).get("x") is not None:
            dots[r["image_id"]] = r["dot"]
    done = {json.loads(l)["image_id"] for l in OUT.open()} if OUT.exists() else set()
    todo = [(int(i), int(c), p) for i, c, p in imgs if int(i) not in done]
    print("cuda", torch.cuda.is_available(), "frames to do", len(todo), flush=True)

    seg = Sam3Segmenter(build_segmenter(str(SAM3_CKPT)))
    found = {}
    for i, cam, path in todo:
        d = dots.get(i)
        ok = d is not None and in_region(d["x"], d["y"])
        f = None
        if ok:
            cm, dist = (np.array(json.loads(I.loc[cam, k])) for k in ("camera_matrix", "distortion_coefficients"))
            frame = RectifiedImage(RawImage((NAS / path).read_bytes()), CameraIntrinsics(cm, dist)).data
            f = find_fish_at_dot(frame, [[d["x"], d["y"]]], seg, grow_cut_masks=True, score_gate=SCORE_GATE)
            found[i] = (frame, f)
        else:
            found[i] = (None, None)
    del seg; torch.cuda.empty_cache()

    kp = HeadTailKeypointDetector.from_checkpoint(str(SIMCC_CKPT))
    with OUT.open("a") as fh:
        for i, _, _ in todo:
            frame, f = found[i]
            rec = dict(image_id=i, dot=dots.get(i), in_region=frame is not None, status=None if f is None else f.status)
            if f is not None and f.head is not None and f.mask_bbox is not None:
                k = kp.predict(frame, list(f.mask_bbox))
                rec.update(rule_head=[float(v) for v in f.head], rule_tail=[float(v) for v in f.tail],
                           mask_bbox=[float(v) for v in f.mask_bbox], simcc_head=[float(v) for v in k.head],
                           simcc_tail=[float(v) for v in k.tail], simcc_confidence=float(k.confidence))
            fh.write(json.dumps(rec) + "\n"); fh.flush()
    print("done", flush=True)


if __name__ == "__main__":
    main()
