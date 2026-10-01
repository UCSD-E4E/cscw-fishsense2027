"""E1 per-frame pass: every automatic input a label-free calibration needs, one raw read each.

For each frame in frames.csv:
  * laser dot     -- production LaserDetector, wavelength=None, rectified output (as T3)
  * slate frames  -- fishsense_core.slate.estimate_plane on the rectified frame, twice:
                     board_mask=None (the retired production path) and with the BoardMasker
  * checkerboard  -- production's checkerboard_detection.detect_checkerboard (14x10, 0.04217 m)

Writes one JSON line per frame to frames_out.jsonl and skips frames already there.

Run from P4's environment with torch overlaid (see ../../laser_detection_analysis/README.md):
  LD_LIBRARY_PATH=/run/opengl-driver/lib uv run --project ../../../wuwnet-fishsense2026 --no-sync \\
      --with torch==2.13.0 --with "segmentation-models-pytorch>=0.4" --with "huggingface-hub>=0.26" \\
      python run_frames.py LASER_CHECKPOINT BOARD_UNET_CHECKPOINT
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import sys as _sys; _sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2]))
from fishsense_cscw.anon import real_path  # noqa: E402  (pseudonymised paths -> real NAS paths)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
FISHSENSE = REPO.parent
WORKER = (FISHSENSE / "fishsense-lite/services/fishsense-data-processing-workflow-worker"
          / "src/fishsense_data_processing_workflow_worker")
LASER_SHA = "bd3ab8f5e273da37a1f2dfc2c6c6a36735b89ae26ff821b71b1f8acce3a74d68"
BOARD = dict(max_rows=10, max_cols=14, square_size_m=0.04217)  # calibrationtarget id 1


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # dataclasses resolve annotations through sys.modules
    spec.loader.exec_module(mod)
    return mod


def main(laser_ckpt: str, board_ckpt: str):
    assert hashlib.sha256(Path(laser_ckpt).read_bytes()).hexdigest() == LASER_SHA, "not the pinned laser checkpoint"
    import pymupdf
    import torch
    from fishsense_core.image.decode import rectify
    from fishsense_core.image.linear_raw_image import LinearRawImage
    from fishsense_core.image.raw_image import RawImage
    from fishsense_core.laser import LaserDetector
    from fishsense_core.slate import BoardMasker, estimate_plane
    cb = _load("checkerboard_detection", WORKER / "checkerboard_detection.py")

    print("cuda:", torch.cuda.is_available(), flush=True)
    detector = LaserDetector.from_checkpoint(laser_ckpt)
    masker = BoardMasker.from_checkpoint(board_ckpt)

    data = REPO / "data" / "e1"
    slates = pd.read_csv(data / "slates.csv").set_index("name")
    templates = {}
    for name in ("Tic-Tac-Toe 1", "V-Slate 2"):
        dpi = int(slates.loc[name, "dpi"])
        with pymupdf.open(data / "templates" / f"{name}.pdf") as doc:  # as predict_slate_image._render_template_gray
            pm = doc.load_page(0).get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
        gray = np.frombuffer(pm.samples, dtype=np.uint8).reshape(pm.height, pm.width)
        templates[name] = (gray, json.loads(slates.loc[name, "reference_points"]), dpi)

    intr = {int(r.camera_id): (np.array(json.loads(r.camera_matrix)), np.array(json.loads(r.distortion_coefficients)))
            for r in pd.read_csv(REPO / "laser_detection_analysis" / "intrinsics.csv").itertuples()}
    frames = pd.read_csv(HERE / "frames.csv")
    frames = frames[frames.raw_path.notna()]
    out = HERE / "frames_out.jsonl"
    # a frame that errored (e.g. the NAS dropped) is not done: retry it
    done = {r["image_id"] for r in map(json.loads, out.open()) if "error" not in r} if out.exists() else set()
    todo = [r for r in frames.itertuples() if int(r.image_id) not in done]
    print(f"{len(todo)} frames to do ({len(done)} already done)", flush=True)

    pool = ThreadPoolExecutor(2)
    futs = {i: pool.submit(lambda p: Path(real_path(p)).read_bytes(), r.raw_path) for i, r in enumerate(todo[:2])}
    with out.open("a") as fh:
        for i, r in enumerate(todo):
            if i + 2 < len(todo):
                futs[i + 2] = pool.submit(lambda p: Path(real_path(p)).read_bytes(), todo[i + 2].raw_path)
            rec = dict(image_id=int(r.image_id), dive_id=int(r.dive_id), kind=r.kind)
            t0 = time.time()
            try:
                raw = futs.pop(i).result()
                K, dist = intr[int(r.camera_id)]
                p = detector.predict(LinearRawImage(raw), wavelength=None, rectify_output=True, camera_matrix=K, distortion=dist)
                rec.update(dot=[p.x, p.y], confidence=p.confidence)
                bgr = rectify(RawImage(raw).data, K, dist)
                if r.kind == "slate":
                    gray, pts, dpi = templates[r.slate]
                    for tag, mask in (("classical", None), ("masked", masker.predict(bgr))):
                        est = estimate_plane(bgr, gray, pts, dpi, K, board_mask=mask)
                        rec[tag] = None if est is None else dict(
                            image_points=np.asarray(est.image_points, float).tolist(),
                            ecc=float(est.ecc_score), rms=float(est.reprojection_rms))
                else:
                    det = cb.detect_checkerboard(bgr, **BOARD)
                    rec["board"] = None if det is None else dict(
                        body_points=np.asarray(det.body_points, float).tolist(),
                        image_points=np.asarray(det.image_points, float).tolist(),
                        hull=cb.board_hull(det))
            except Exception as e:  # one bad frame must not stop the pass
                rec["error"] = f"{type(e).__name__}: {e}"
            rec["seconds"] = round(time.time() - t0, 1)
            fh.write(json.dumps(rec) + "\n"); fh.flush()
            if (i + 1) % 25 == 0:
                print(f"{i + 1}/{len(todo)}", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:3])
