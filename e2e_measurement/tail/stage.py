"""Tail study, staging (CPU + NAS only; the GPU is hidden): read each raw frame from the NAS once.

Per frame it saves, to scratch:
  <id>.jpg   the rectified frame as production encodes it (cv2.imencode defaults) -- the SAM input
  <id>.ORF   a local copy of the raw, reef frames only (the laser detector needs the raw)
Later GPU passes read these locally and exit quickly (laser.py, masks.py).

Priority order, so results can be scored while it runs:
  1. reef dives with a stored calibration (manual length available)
  2. pool fish-model dives (tape truth)
  3. green-laser reef dives 362 / 366, sampled to 200 each (dot and head/tail vs human clicks)
  4. pool angle tests, sampled to a third

Run from fishsense-lite's venv, with CUDA_VISIBLE_DEVICES= .
"""
from __future__ import annotations

import json, shutil, sys, time
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import run_e2e as E  # noqa: E402

STAGE = Path.home() / ".cache/cscw-fishsense2027/tail_stage"   # 22 GB, ~9 h of NAS reads; outside /tmp, which is wiped at boot
CALIBRATED_REEF = [347, 341, 465, 349, 279, 471, 436, 383]


def frame_list() -> pd.DataFrame:
    reef = pd.read_csv(HERE / "reef_frames.psv", sep="|")
    reef = reef[~reef.content.fillna("").str.startswith("Slate")].assign(set="reef")
    pool = pd.read_csv(HERE.parent / "frames.psv", sep="|").drop_duplicates("image_id")
    pool = pool[pool.content.fillna("").str.contains("Fish Model|Ruler")].assign(set="pool")
    parts = [reef[reef.dive_id.isin(CALIBRATED_REEF)].assign(priority=1),
             pool[pool.dive_id.isin([58, 59, 60, 61, 66, 76, 84])].assign(priority=2),
             reef[reef.dive_id.isin([362, 366])].groupby("dive_id").sample(n=200, random_state=0, replace=False).assign(priority=3),
             pool[pool.dive_id.isin([87, 94, 114])].sample(frac=1 / 3, random_state=0).assign(priority=4)]
    return pd.concat(parts, ignore_index=True).sort_values(["priority", "dive_id", "image_id"])


def main():
    import cv2
    from fishsense_core.image.raw_image import RawImage
    from fishsense_core.image.rectified_image import RectifiedImage
    from fishsense_api_sdk.models.camera_intrinsics import CameraIntrinsics

    STAGE.mkdir(parents=True, exist_ok=True); K = E.intrinsics()
    F = frame_list(); F.to_csv(HERE / "frames.csv", index=False)
    out = HERE / "stage.jsonl"; todo = F[~F.image_id.isin(E.done_ids(out))]
    print(f"stage: {len(todo)} frames to do (of {len(F)})", flush=True)
    with out.open("a") as fh:
        for n, r in enumerate(todo.itertuples(), 1):
            rec = dict(image_id=int(r.image_id), set=r.set); t0 = time.time()
            try:
                raw = (E.NAS / r.path).read_bytes()
                if r.set == "reef":
                    (STAGE / f"{r.image_id}.ORF").write_bytes(raw)
                cm, dist = K[int(r.camera_id)]
                img = RectifiedImage(RawImage(raw), CameraIntrinsics(camera_matrix=cm, distortion_coefficients=dist, camera_id=None)).data
                ok, enc = cv2.imencode(".jpg", img)
                (STAGE / f"{r.image_id}.jpg").write_bytes(enc.tobytes())
            except Exception as e:
                rec["error"] = f"{type(e).__name__}: {e}"
            rec["seconds"] = round(time.time() - t0, 1)
            fh.write(json.dumps(rec) + "\n"); fh.flush()
            if n % 25 == 0:
                print(f"{n}/{len(todo)} ({rec['seconds']}s last)", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
