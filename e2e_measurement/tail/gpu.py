"""Tail study, GPU passes (each loads its model, processes everything staged so far, and exits).

  gpu.py laser   production laser detector on the cached reef raws -> reef_dots.jsonl
                 (pool frames already have automatic dots in ../dots.jsonl)
  gpu.py masks   SAM 3.1 on the production 1800x1350 window at a dot, gated by mask_at_point,
                 for the AUTOMATIC dot and for the HUMAN dot. Saves the chosen mask (cropped to
                 its bounding box, bit-packed) with its frame offset -> masks/<id>_<seed>.npz
The keypoint rules then run on CPU from the saved masks (keypoints.py).

Run from fishsense-lite's venv (see ../run_e2e.py for the environment).
"""
from __future__ import annotations

import json, sys, time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent)); sys.path.insert(0, str(HERE))
import run_e2e as E  # noqa: E402
from stage import STAGE  # noqa: E402

MASKS = HERE / "masks"


def staged():
    ok = {}
    for l in (HERE / "stage.jsonl").open():
        r = json.loads(l)
        if "error" not in r:
            ok[r["image_id"]] = r["set"]
    F = pd.read_csv(HERE / "frames.csv")
    return F[F.image_id.isin(ok)]


def auto_dots():
    d = {}
    for name in (HERE.parent / "dots.jsonl", HERE / "reef_dots.jsonl"):
        if name.exists():
            for l in name.open():
                r = json.loads(l)
                if "dot" in r and r["dot"]["x"] is not None:
                    d[r["image_id"]] = (r["dot"]["x"], r["dot"]["y"])
    return d


def laser():
    import hashlib, torch
    from fishsense_core.laser import LaserDetector
    from fishsense_core.image.linear_raw_image import LinearRawImage
    assert hashlib.sha256(Path(E.LASER_CKPT).read_bytes()).hexdigest() == E.LASER_SHA
    F = staged(); F = F[F.set == "reef"]
    out = HERE / "reef_dots.jsonl"; todo = F[~F.image_id.isin(E.done_ids(out))]
    print(f"laser: {len(todo)} reef frames; cuda {torch.cuda.is_available()}", flush=True)
    if todo.empty:
        return
    det = LaserDetector.from_checkpoint(E.LASER_CKPT); K = E.intrinsics()
    with out.open("a") as fh:
        for r in todo.itertuples():
            rec = dict(image_id=int(r.image_id))
            try:
                cm, dist = K[int(r.camera_id)]
                p = det.predict(LinearRawImage((STAGE / f"{r.image_id}.ORF").read_bytes()), wavelength=None,
                                rectify_output=True, camera_matrix=cm, distortion=dist)
                rec["dot"] = dict(x=p.x, y=p.y, confidence=p.confidence)
            except Exception as e:
                rec["error"] = f"{type(e).__name__}: {e}"
            fh.write(json.dumps(rec, default=float) + "\n"); fh.flush()
    print("done", flush=True)


def masks():
    import cv2, torch
    from fishsense_data_processing_workflow_worker.activities.predict_headtail_image import _Sam3Adapter, _load_segmenter
    from fishsense_data_processing_workflow_worker.headtail_geometry import crop_origin, mask_at_point
    from fishsense_shared.headtail_predictor import HEADTAIL_CROP_WIDTH as CW, HEADTAIL_CROP_HEIGHT as CH
    MASKS.mkdir(exist_ok=True)
    F = staged(); dots = auto_dots()
    jobs = []
    for r in F.itertuples():
        for seed, pt in (("human", (r.laser_x, r.laser_y)), ("auto", dots.get(int(r.image_id)))):
            if pt is not None and not (MASKS / f"{r.image_id}_{seed}.npz").exists():
                jobs.append((int(r.image_id), seed, pt))
    print(f"masks: {len(jobs)} (frame, seed) jobs; cuda {torch.cuda.is_available()}", flush=True)
    if not jobs:
        return
    seg = _Sam3Adapter(_load_segmenter(E.SAM3_CKPT)); frame_cache = {}
    for n, (iid, seed, (x, y)) in enumerate(jobs, 1):
        try:
            if iid not in frame_cache:
                frame_cache.clear(); frame_cache[iid] = cv2.imread(str(STAGE / f"{iid}.jpg"))
            img = frame_cache[iid]; H, W = img.shape[:2]
            ox, oy = crop_origin(x, y, W, H, CW, CH)
            ms = seg.segment(np.ascontiguousarray(img[oy:oy + CH, ox:ox + CW]))
            m = mask_at_point(ms, [(x - ox, y - oy)]) if ms else None
            status = "no_detections" if not ms else ("laser_off_all_fish" if m is None else "ok")
            if m is None:
                np.savez_compressed(MASKS / f"{iid}_{seed}.npz", status=status); continue
            mk = np.asarray(m) > 0; ys, xs = np.nonzero(mk)
            y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
            np.savez_compressed(MASKS / f"{iid}_{seed}.npz", status=status, bits=np.packbits(mk[y0:y1, x0:x1]),
                                shape=np.array([y1 - y0, x1 - x0]), offset=np.array([ox + x0, oy + y0]), n_masks=len(ms))
        except Exception as e:
            np.savez_compressed(MASKS / f"{iid}_{seed}.npz", status=f"error: {type(e).__name__}: {e}")
        if n % 100 == 0:
            print(f"{n}/{len(jobs)}", flush=True)
    print("done", flush=True)


def load_mask(iid, seed):
    """-> (status, bool mask cropped to its box, (x, y) frame offset of the box) ."""
    z = np.load(MASKS / f"{iid}_{seed}.npz")
    if "bits" not in z:
        return str(z["status"]), None, None
    h, w = z["shape"]
    return "ok", np.unpackbits(z["bits"])[: h * w].reshape(h, w).astype(bool), tuple(z["offset"])


if __name__ == "__main__":
    laser() if sys.argv[1] == "laser" else masks()
