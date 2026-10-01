"""E2: end-to-end automatic measurement, pass 1 (GPU + NAS): run the production detectors.

Per frame, exactly as fishsense-lite does each stage, but chained with no human input:
  1. laser dot:  LinearRawImage(raw) -> LaserDetector.predict(wavelength=None, rectify_output=True, K, dist)
                 (predict_laser_image._predict_from_raw)
  2. rectified JPEG: RectifiedImage(RawImage(raw), intrinsics) -> cv2.imencode  (preprocess_headtail_image)
  3. head/tail:  predict_from_jpeg(jpeg, [dot], SAM3 adapter)   (predict_headtail_image)
     run twice: seeded by the AUTOMATIC dot (the e2e path) and by the HUMAN dot (isolates the
     head/tail stage from dot error; this is what production does today).
Calibration and length are pass 2 (score.py), which needs no GPU.

Production seeds head/tail with human laser labels and measures from human labels; nothing in
production chains the detectors. This is the first fully automatic run.

SAM3: sam3.1_multiplex.pt, the checkpoint production runs (a local copy in ~/Downloads).

Run from fishsense-lite's venv:
  PYTHONPATH=<setuptools,einops,psutil,pycocotools --no-deps> LD_LIBRARY_PATH=/run/opengl-driver/lib:<64-bit libxcb> \\
      ../../fishsense-lite/.venv/bin/python run_e2e.py laser|headtail
"""
from __future__ import annotations

import glob, hashlib, json, sys, time
from pathlib import Path

import numpy as np
import pandas as pd
import sys as _sys; _sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[1]))
from fishsense_cscw.anon import real_path  # noqa: E402  (pseudonymised paths -> real NAS paths)

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
LITE = REPO.parent / "fishsense-lite"
sys.path.insert(0, str(LITE / "services/fishsense-data-processing-workflow-worker/src"))
sys.path.insert(0, str(LITE / "libs/fishsense-shared/src"))
NAS = Path.home() / "mnt/fishsense_data/REEF/data"
LASER_CKPT = "/home/chris/.cache/huggingface/hub/models--ucsde4e--fishsense-laser-detector/snapshots/1cd50f16fa92a0b5c9b88645d75b4feb018d5d27/run3_epoch_021.pt"
LASER_SHA = "bd3ab8f5e273da37a1f2dfc2c6c6a36735b89ae26ff821b71b1f8acce3a74d68"
SAM3_CKPT = str(Path.home() / "Downloads/sam3.1_multiplex.pt")   # production's model (config.py: sam3.checkpoint_filename)
ORDER = [58, 59, 60, 61, 66, 76, 84, 87, 94, 114]   # fish-model dives first, then the angle tests


def ht_record(res):
    return {k: getattr(res, k) for k in ("status", "head_x", "head_y", "tail_x", "tail_y", "mask_area_px",
                                         "silhouette_ratio", "crop_x", "crop_y")}


def frames():
    F = pd.read_csv(HERE / "frames.psv", sep="|").drop_duplicates("image_id")
    F = F[F.content.fillna("").str.contains("Fish Model|Ruler")]
    F["o"] = F.dive_id.map({d: i for i, d in enumerate(ORDER)})
    return F.sort_values(["o", "image_id"])


def intrinsics():
    return {int(r.camera_id): (np.array(json.loads(r.camera_matrix)), np.array(json.loads(r.distortion_coefficients)))
            for r in pd.read_csv(REPO / "laser_detection_analysis/intrinsics.csv").itertuples()}


def done_ids(out):
    return {json.loads(l)["image_id"] for l in out.open() if "error" not in json.loads(l)} if out.exists() else set()


def laser_pass():
    """Pass A: the laser detector alone (the 6 GB card is shared with the desktop; it cannot hold SAM3 too)."""
    import torch
    from fishsense_core.laser import LaserDetector
    from fishsense_core.image.linear_raw_image import LinearRawImage
    assert hashlib.sha256(Path(LASER_CKPT).read_bytes()).hexdigest() == LASER_SHA
    print("cuda:", torch.cuda.is_available(), flush=True)
    det = LaserDetector.from_checkpoint(LASER_CKPT); K = intrinsics()
    out = HERE / "dots.jsonl"; F = frames(); todo = F[~F.image_id.isin(done_ids(out))]
    print(f"laser pass: {len(todo)} frames to do", flush=True)
    with out.open("a") as fh:
        for n, r in enumerate(todo.itertuples(), 1):
            rec = dict(image_id=int(r.image_id), dive_id=int(r.dive_id)); t0 = time.time()
            try:
                cm, dist = K[int(r.camera_id)]
                p = det.predict(LinearRawImage((NAS / real_path(r.path, NAS)).read_bytes()), wavelength=None, rectify_output=True,
                                camera_matrix=cm, distortion=dist)
                rec["dot"] = dict(x=p.x, y=p.y, confidence=p.confidence)
            except Exception as e:
                rec["error"] = f"{type(e).__name__}: {e}"
            rec["seconds"] = round(time.time() - t0, 1)
            fh.write(json.dumps(rec, default=float) + "\n"); fh.flush()
            if n % 20 == 0:
                print(f"{n}/{len(todo)} ({rec['seconds']}s last)", flush=True)
    print("done", flush=True)


def headtail_pass():
    """Pass B: SAM3 head/tail, seeded by the automatic dot and, separately, by the human dot."""
    import cv2, torch
    from fishsense_core.image.raw_image import RawImage
    from fishsense_core.image.rectified_image import RectifiedImage
    from fishsense_api_sdk.models.camera_intrinsics import CameraIntrinsics
    from fishsense_data_processing_workflow_worker.activities.predict_headtail_image import (
        _Sam3Adapter, _load_segmenter, predict_from_jpeg, PredictOptions)
    print("cuda:", torch.cuda.is_available(), "sam3:", SAM3_CKPT, flush=True)
    seg = _Sam3Adapter(_load_segmenter(SAM3_CKPT)); opts = PredictOptions(checkpoint="sam3.1_multiplex.pt")
    dots = {}
    for l in (HERE / "dots.jsonl").open():
        r = json.loads(l)
        if "dot" in r:
            dots[r["image_id"]] = r["dot"]
    K = intrinsics(); out = HERE / "headtail.jsonl"; F = frames()
    todo = F[F.image_id.isin(dots) & ~F.image_id.isin(done_ids(out))]
    print(f"head/tail pass: {len(todo)} frames to do", flush=True)
    with out.open("a") as fh:
        for n, r in enumerate(todo.itertuples(), 1):
            rec = dict(image_id=int(r.image_id), dive_id=int(r.dive_id)); t0 = time.time()
            try:
                cm, dist = K[int(r.camera_id)]
                intr = CameraIntrinsics(camera_matrix=cm, distortion_coefficients=dist, camera_id=None)
                ok, enc = cv2.imencode(".jpg", RectifiedImage(RawImage((NAS / real_path(r.path, NAS)).read_bytes()), intr).data)
                jpeg = enc.tobytes(); d = dots[int(r.image_id)]
                auto = [[d["x"], d["y"]]] if d["x"] is not None and np.isfinite(d["x"]) else []
                rec["ht_auto"] = ht_record(predict_from_jpeg(jpeg, auto, seg, int(r.image_id), [1] if auto else None, opts))
                rec["ht_humandot"] = ht_record(predict_from_jpeg(jpeg, [[r.laser_x, r.laser_y]], seg, int(r.image_id), [1], opts))
            except Exception as e:
                rec["error"] = f"{type(e).__name__}: {e}"
            rec["seconds"] = round(time.time() - t0, 1)
            fh.write(json.dumps(rec, default=float) + "\n"); fh.flush()
            if n % 20 == 0:
                print(f"{n}/{len(todo)} ({rec['seconds']}s last)", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    laser_pass() if sys.argv[1] == "laser" else headtail_pass()
