"""T3: run the production laser detector over sample.csv, two wavelength conditions per frame.

Mirrors fishsense-lite's predict_laser_image exactly: LinearRawImage(raw bytes) ->
LaserDetector.predict(image, wavelength=..., rectify_output=True, K, dist).

  production : wavelength=None   (what prod sends -- the "unknown" 0.5 channel)
  given      : wavelength=<the human label's colour>   (what training/val supplied)

Run from fishsense-lite's venv, with the NixOS driver path for CUDA:
  LD_LIBRARY_PATH=/run/opengl-driver/lib ../../fishsense-lite/.venv/bin/python run_detector.py CHECKPOINT [--limit N]

Appends to predictions.csv as it goes and skips frames already done, so it resumes.
"""
import argparse, csv, hashlib, json, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
PINNED = "bd3ab8f5e273da37a1f2dfc2c6c6a36735b89ae26ff821b71b1f8acce3a74d68"
FIELDS = ["image_id", "condition", "pred_x", "pred_y", "confidence", "seconds", "error"]

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("checkpoint"); ap.add_argument("--limit", type=int)
    ap.add_argument("--out", default=str(HERE / "predictions.csv")); a = ap.parse_args()
    digest = hashlib.sha256(Path(a.checkpoint).read_bytes()).hexdigest()
    assert digest == PINNED, f"checkpoint sha256 {digest} is not the pinned run3 checkpoint"
    import pandas as pd, torch
    from fishsense_core.laser import LaserDetector
    from fishsense_core.image.linear_raw_image import LinearRawImage
    print("cuda:", torch.cuda.is_available(), flush=True)
    det = LaserDetector.from_checkpoint(a.checkpoint)
    S = pd.read_csv(HERE / "sample.csv"); S = S[S.raw_path.notna()]
    # Seeded shuffle: the NAS link runs ~0.7 MB/s, so a full pass takes ~10 h. In random
    # order any prefix is a balanced sample, and interim results are meaningful.
    S = S.sample(frac=1, random_state=0)
    K = {int(r.camera_id): (np.array(json.loads(r.camera_matrix)), np.array(json.loads(r.distortion_coefficients)))
         for r in pd.read_csv(HERE / "intrinsics.csv").itertuples()}
    out = Path(a.out); done = set()
    if out.exists():
        done = {(int(r["image_id"]), r["condition"]) for r in csv.DictReader(out.open()) if not r.get("error")}  # retry errors
    new = not out.exists()
    with out.open("a", newline="") as fh:
        w = csv.DictWriter(fh, FIELDS)
        if new: w.writeheader()
        n = 0
        todo = [r for r in S.itertuples()
                if not all((int(r.image_id), c) in done for c in ("production", "given")[: 2 if r.wavelength in ("red", "green") else 1])]
        if a.limit: todo = todo[: a.limit]
        pool = ThreadPoolExecutor(2)
        futs = {i: pool.submit(lambda p: Path(p).read_bytes(), r.raw_path) for i, r in enumerate(todo[:2])}
        for i, r in enumerate(todo):
            if i + 2 < len(todo): futs[i + 2] = pool.submit(lambda p: Path(p).read_bytes(), todo[i + 2].raw_path)
            conds = [("production", None)] + ([("given", r.wavelength)] if r.wavelength in ("red", "green") else [])
            n += 1
            try:
                t0 = time.time(); img = LinearRawImage(futs.pop(i).result()); t_dec = time.time() - t0
                cm, dist = K[int(r.camera_id)]
            except Exception as e:
                for c, _ in conds: w.writerow(dict(image_id=r.image_id, condition=c, error=f"decode: {type(e).__name__}: {e}"))
                fh.flush(); continue
            for c, wl in conds:
                if (int(r.image_id), c) in done: continue
                t0 = time.time()
                try:
                    p = det.predict(img, wavelength=wl, rectify_output=True, camera_matrix=cm, distortion=dist)
                    w.writerow(dict(image_id=r.image_id, condition=c, pred_x=p.x, pred_y=p.y, confidence=p.confidence,
                                    seconds=round(t_dec + time.time() - t0, 2)))
                except Exception as e:
                    w.writerow(dict(image_id=r.image_id, condition=c, error=f"{type(e).__name__}: {e}"))
                t_dec = 0.0
            fh.flush()
            if n % 25 == 0: print(f"{n} frames", flush=True)
    print("done", n, "frames this run", flush=True)

if __name__ == "__main__":
    main()
