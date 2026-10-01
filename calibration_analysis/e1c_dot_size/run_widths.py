"""E1c per-frame pass: how wide is the laser dot, measured on the 16-bit linear raw?

For each frame: map the labelled (rectified) dot back to sensor pixels with production's
`laser_color.rectified_to_sensor_point`, cut a 61x61 patch of `LinearRawImage` (16-bit
linear BGR), form the laser-colour excess (R - (G+B)/2 for red, G - (R+B)/2 for green),
and fit an elliptical Gaussian **to the unsaturated pixels only** -- the wings of a
clipped spot still carry its width, the plateau does not. A second-moment width is kept
as a cross-check; it is biased by clipping and is not the estimator.

Run from P4's environment (OpenCV + fishsense_core):  ../../../wuwnet-fishsense2026/.venv/bin/python run_widths.py
"""
from __future__ import annotations
import importlib.util, json, sys, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import numpy as np, pandas as pd
from scipy.optimize import least_squares
import sys as _sys; _sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2]))
from fishsense_cscw.anon import real_path  # noqa: E402  (pseudonymised paths -> real NAS paths)

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
FISHSENSE = REPO.parent
LC = FISHSENSE / "fishsense-lite/services/fishsense-data-processing-workflow-worker/src/fishsense_data_processing_workflow_worker/laser_color.py"
HALF = 30


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec); sys.modules[name] = mod; spec.loader.exec_module(mod)
    return mod


def gauss(p, x, y):
    amp, x0, y0, sa, sb, th, off = p
    c, s = np.cos(th), np.sin(th)
    u, v = c * (x - x0) + s * (y - y0), -s * (x - x0) + c * (y - y0)
    return off + amp * np.exp(-0.5 * ((u / sa) ** 2 + (v / sb) ** 2))


def measure(patch_bgr, clip, color):
    b, g, r = [patch_bgr[:, :, i].astype(float) for i in range(3)]
    main = r if color == "red" else g
    exc = main - (g + b) / 2 if color == "red" else g - (r + b) / 2
    sat = main >= clip
    yy, xx = np.mgrid[0:exc.shape[0], 0:exc.shape[1]]
    bg = np.median(np.concatenate([exc[:3].ravel(), exc[-3:].ravel(), exc[:, :3].ravel(), exc[:, -3:].ravel()]))
    e = exc - bg
    use = ~sat
    if use.sum() < 30 or e.max() <= 0:
        return None
    y0, x0 = np.unravel_index(np.argmax(np.where(use, e, -np.inf)), e.shape)
    p0 = [e.max(), x0, y0, 2.0, 2.0, 0.0, 0.0]
    lo = [0, 0, 0, 0.3, 0.3, -np.pi, -np.inf]; hi = [np.inf, e.shape[1], e.shape[0], 25, 25, np.pi, np.inf]
    fit = least_squares(lambda p: (gauss(p, xx[use], yy[use]) - e[use]), p0, bounds=(lo, hi))
    amp, fx, fy, sa, sb, th, off = fit.x
    w = np.clip(e, 0, None); w = w / w.sum() if w.sum() > 0 else w
    mx, my = (w * xx).sum(), (w * yy).sum()
    m2 = np.sqrt(((w * ((xx - mx) ** 2 + (yy - my) ** 2)).sum()) / 2)
    return dict(sigma_minor=float(min(sa, sb)), sigma_major=float(max(sa, sb)), sigma_geo=float(np.sqrt(sa * sb)),
                amp=float(amp), fit_rmse=float(np.sqrt(np.mean(fit.fun ** 2))), moment_sigma=float(m2),
                saturated_px=int(sat.sum()), peak_offset_px=float(np.hypot(fx - HALF, fy - HALF)), snr=float(amp / (np.std(e[:3]) + 1e-9)))


def main():
    from fishsense_core.image.linear_raw_image import LinearRawImage
    lc = _load("laser_color", LC)
    intr = {int(r.camera_id): (json.loads(r.camera_matrix), json.loads(r.distortion_coefficients))
            for r in pd.read_csv(REPO / "laser_detection_analysis/intrinsics.csv").itertuples()}
    F = pd.read_csv(HERE / "frames.csv"); F = F[F.raw_path.notna()]
    out = HERE / "widths.jsonl"
    # a frame that errored (e.g. the NAS dropped) is not done: retry it
    done = {r["image_id"] for r in map(json.loads, out.open()) if "error" not in r} if out.exists() else set()
    todo = [r for r in F.itertuples() if int(r.image_id) not in done]
    print(f"{len(todo)} frames to do", flush=True)
    pool = ThreadPoolExecutor(2)
    futs = {i: pool.submit(lambda p: Path(real_path(p)).read_bytes(), r.raw_path) for i, r in enumerate(todo[:2])}
    with out.open("a") as fh:
        for i, r in enumerate(todo):
            if i + 2 < len(todo): futs[i + 2] = pool.submit(lambda p: Path(real_path(p)).read_bytes(), todo[i + 2].raw_path)
            rec = dict(image_id=int(r.image_id), dive_id=int(r.dive_id)); t0 = time.time()
            try:
                data = LinearRawImage(futs.pop(i).result()).data
                K, dist = intr[int(r.camera_id)]
                sx, sy = lc.rectified_to_sensor_point(float(r.x), float(r.y), K, dist)
                xi, yi = int(round(sx)), int(round(sy))
                patch = data[yi - HALF: yi + HALF + 1, xi - HALF: xi + HALF + 1]
                color = "green" if "Green" in str(r.label) else "red"
                ch = 2 if color == "red" else 1
                clip = int(data[:, :, ch].max())
                rec.update(sensor=[sx, sy], color=color, clip=clip, dtype=str(data.dtype),
                           frame_clipped_px=int((data[:, :, ch] >= clip).sum()))
                m = measure(patch, clip, color) if patch.shape[:2] == (2 * HALF + 1, 2 * HALF + 1) else None
                rec["fit"] = m
            except Exception as e:
                rec["error"] = f"{type(e).__name__}: {e}"
            rec["seconds"] = round(time.time() - t0, 1)
            fh.write(json.dumps(rec) + "\n"); fh.flush()
            if (i + 1) % 25 == 0: print(f"{i + 1}/{len(todo)}", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main()
