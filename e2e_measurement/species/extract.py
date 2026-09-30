"""Species stage, pass 1 (GPU + NAS): fish crops for BioCLIP from labelled real-fish frames.

Three crops per frame, all from the rectified image the pipeline sees:
  ht      box around the HUMAN head/tail segment (body depth taken as 0.45 x length), padded
          20 %: isolates the classifier from segmentation
  sam     box of the SAM 3.1 mask that contains the human laser dot (production's crop, prompt
          "fish", mask_at_point gate), padded 20 %  -- the automatic path
  masked  the same crop with non-mask pixels zeroed (the coral-gardeners pipeline classifies
          both and keeps the more confident)
The 20 % padding follows coral-gardeners-fish-detector's cropper.

Run from fishsense-lite's venv (see e2e_measurement/run_e2e.py for the environment):
  extract.py stage     CPU + NAS, slow; holds no GPU
  extract.py segment   GPU, a few minutes
"""
from __future__ import annotations

import json, sys, time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import run_e2e as E  # noqa: E402  (paths, SAM3 checkpoint, intrinsics)

PAD, DEPTH_RATIO = 0.20, 0.45


def pad_box(x0, y0, x1, y1, W, H):
    w, h = x1 - x0, y1 - y0
    return (int(max(0, x0 - PAD * w)), int(max(0, y0 - PAD * h)), int(min(W, x1 + PAD * w)), int(min(H, y1 + PAD * h)))


def ht_box(r):
    h, t = np.array([r.head_x, r.head_y]), np.array([r.tail_x, r.tail_y])
    d = t - h; L = np.linalg.norm(d); n = np.array([-d[1], d[0]]) / L * (DEPTH_RATIO * L / 2)
    pts = np.array([h + n, h - n, t + n, t - n])
    return pts[:, 0].min(), pts[:, 1].min(), pts[:, 0].max(), pts[:, 1].max()


WINDOWS = Path.home() / ".cache/cscw-fishsense2027/sam_windows"   # outside /tmp, which is wiped at boot


def stage():
    """CPU only, NAS-bound: rectify each frame, save the head/tail crop and the 1800x1350 SAM window.

    The window is saved as JPEG (cv2 default quality), as production encodes the rectified frame
    to JPEG before cropping and segmenting. No GPU is held while waiting on the NAS.
    """
    import cv2
    from fishsense_core.image.raw_image import RawImage
    from fishsense_core.image.rectified_image import RectifiedImage
    from fishsense_api_sdk.models.camera_intrinsics import CameraIntrinsics
    from fishsense_data_processing_workflow_worker.headtail_geometry import crop_origin
    from fishsense_shared.headtail_predictor import HEADTAIL_CROP_WIDTH as CW, HEADTAIL_CROP_HEIGHT as CH

    K = E.intrinsics(); WINDOWS.mkdir(parents=True, exist_ok=True)
    F = pd.read_csv(HERE / "frames.psv", sep="|")
    out = HERE / "stage.jsonl"
    skip = E.done_ids(HERE / "crops.jsonl") | E.done_ids(out)          # segmented before the split, or already staged
    todo = F[~F.image_id.isin(skip)]
    print(f"stage: {len(todo)} frames to do", flush=True)
    with out.open("a") as fh:
        for n, r in enumerate(todo.itertuples(), 1):
            rec = dict(image_id=int(r.image_id)); t0 = time.time()
            try:
                cm, dist = K[int(r.camera_id)]
                img = RectifiedImage(RawImage((E.NAS / r.path).read_bytes()),
                                     CameraIntrinsics(camera_matrix=cm, distortion_coefficients=dist, camera_id=None)).data
                H, W = img.shape[:2]
                if pd.notna(r.head_x):
                    x0, y0, x1, y1 = pad_box(*ht_box(r), W, H)
                    cv2.imwrite(str(HERE / "crops" / f"{r.image_id}_ht.jpg"), img[y0:y1, x0:x1]); rec["ht"] = [x0, y0, x1, y1]
                ox, oy = crop_origin(r.laser_x, r.laser_y, W, H, CW, CH)
                cv2.imwrite(str(WINDOWS / f"{r.image_id}.jpg"), img[oy:oy + CH, ox:ox + CW])
                rec.update(origin=[int(ox), int(oy)], frame=[W, H])
            except Exception as e:
                rec["error"] = f"{type(e).__name__}: {e}"
            rec["seconds"] = round(time.time() - t0, 1)
            fh.write(json.dumps(rec) + "\n"); fh.flush()
            if n % 20 == 0:
                print(f"{n}/{len(todo)} ({rec['seconds']}s last)", flush=True)
    print("done", flush=True)


def segment():
    """GPU, short: SAM 3.1 on every staged window, then the sam / masked crops. Frees the GPU on exit."""
    import cv2, torch
    from fishsense_data_processing_workflow_worker.activities.predict_headtail_image import _Sam3Adapter, _load_segmenter
    from fishsense_data_processing_workflow_worker.headtail_geometry import mask_at_point

    staged = {}
    for l in (HERE / "stage.jsonl").open():
        r = json.loads(l)
        if "error" not in r:
            staged[r["image_id"]] = r
    F = pd.read_csv(HERE / "frames.psv", sep="|").set_index("image_id")
    out = HERE / "crops.jsonl"
    todo = [i for i in staged if i not in E.done_ids(out)]
    print(f"segment: {len(todo)} windows; cuda {torch.cuda.is_available()}", flush=True)
    if not todo:
        return
    seg = _Sam3Adapter(_load_segmenter(E.SAM3_CKPT))
    with out.open("a") as fh:
        for n, iid in enumerate(todo, 1):
            st = staged[iid]; r = F.loc[iid]; ox, oy = st["origin"]
            rec = dict(image_id=int(iid), **({"ht": st["ht"]} if "ht" in st else {})); t0 = time.time()
            try:
                win = cv2.imread(str(WINDOWS / f"{iid}.jpg")); h, w = win.shape[:2]
                masks = seg.segment(win)
                m = mask_at_point(masks, [(r.laser_x - ox, r.laser_y - oy)]) if masks else None
                rec["sam_status"] = "no_detections" if not masks else ("laser_off_all_fish" if m is None else "ok")
                if m is not None:
                    mk = np.asarray(m) > 0; ys, xs = np.nonzero(mk)
                    x0, y0, x1, y1 = pad_box(xs.min(), ys.min(), xs.max(), ys.max(), w, h)   # clipped to the window
                    cv2.imwrite(str(HERE / "crops" / f"{iid}_sam.jpg"), win[y0:y1, x0:x1])
                    masked = win[y0:y1, x0:x1].copy(); masked[~mk[y0:y1, x0:x1]] = 0
                    cv2.imwrite(str(HERE / "crops" / f"{iid}_masked.jpg"), masked)
                    rec["sam"] = [x0 + ox, y0 + oy, x1 + ox, y1 + oy]; rec["mask_area_px"] = int(mk.sum())
            except Exception as e:
                rec["error"] = f"{type(e).__name__}: {e}"
            rec["seconds"] = round(time.time() - t0, 1)
            fh.write(json.dumps(rec) + "\n"); fh.flush()
            if n % 50 == 0:
                print(f"{n}/{len(todo)}", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    stage() if sys.argv[1] == "stage" else segment()
