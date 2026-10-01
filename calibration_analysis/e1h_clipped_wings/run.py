"""E1h: recover a clipped laser dot's width and brightness from its unclipped wings.

No dimming: the laser stays at full power, as deployed. For a Gaussian spot the unclipped
ring around a saturated core obeys log I = log A - r^2 / (2 sigma^2), so the slope gives
the width however hard the core clipped, and 2*pi*A*sigma^2 gives the total brightness
(E1f's quantity) including the part that clipped.

Per dot, on the raw mosaic (no white balance), for the red and the blue photosites:
background from an outer ring; centre from the saturated core's centroid (or the peak if
nothing clipped); keep photosites with 3 % to 90 % of full scale; fit log(I - bg) against
r^2. One JSON line per dot.

Run from P4's environment:  ../../../wuwnet-fishsense2026/.venv/bin/python run.py DIVE [DIVE ...]
"""
from __future__ import annotations
import io, json, sys, time
from pathlib import Path
import numpy as np, pandas as pd, rawpy

HERE = Path(__file__).resolve().parent
E1C = HERE.parent / "e1c_dot_size"
sys.path.insert(0, str(E1C))
import run_widths as rw  # noqa: E402
import sys as _sys; _sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2]))
from fishsense_cscw.anon import real_path  # noqa: E402  (pseudonymised paths -> real NAS paths)

H, RING, LO, HI = 40, 6, 0.03, 0.90


def wing_fit(mos, cols, idx, black, white, y0, x0):
    win = mos[y0 - H:y0 + H + 1, x0 - H:x0 + H + 1]; cw = cols[y0 - H:y0 + H + 1, x0 - H:x0 + H + 1]
    m = np.isin(cw, idx); v = np.where(m, win - black, np.nan)
    ring = np.concatenate([v[:RING].ravel(), v[-RING:].ravel(), v[:, :RING].ravel(), v[:, -RING:].ravel()])
    bg = np.nanmedian(ring); full = white - black
    yy, xx = np.mgrid[-H:H + 1, -H:H + 1]
    sat = m & (win >= white - 2)
    if sat.sum() >= 3:
        cy, cx = yy[sat].mean(), xx[sat].mean()
    else:
        k = np.nanargmax(v); cy, cx = yy.ravel()[k], xx.ravel()[k]
    r2 = (yy - cy) ** 2 + (xx - cx) ** 2
    e = v - bg
    use = m & ~sat & (e > LO * full) & (e < HI * full) & (r2 < (0.8 * H) ** 2)
    out = dict(saturated=int(sat.sum()), wing_px=int(use.sum()))
    if use.sum() < 6:
        return out
    slope, icpt = np.polyfit(r2[use], np.log(e[use]), 1)
    resid = np.log(e[use]) - (icpt + slope * r2[use])
    if slope >= 0:
        return out
    sigma = float(np.sqrt(-1 / (2 * slope))); A = float(np.exp(icpt))
    out.update(sigma=sigma, amp_over_full=A / full, flux=2 * np.pi * A * sigma ** 2,
               fit_rmse_log=float(resid.std()), r_min=float(np.sqrt(r2[use].min())), r_max=float(np.sqrt(r2[use].max())))
    return out


def main(dives):
    lc = rw._load("laser_color", rw.LC)
    intr = {int(r.camera_id): (json.loads(r.camera_matrix), json.loads(r.distortion_coefficients))
            for r in pd.read_csv(rw.REPO / "laser_detection_analysis/intrinsics.csv").itertuples()}
    F = pd.read_csv(E1C / "frames.csv").dropna(subset=["raw_path"])
    F = F[F.label.str.contains("Red") & F.dive_id.isin(dives)]
    out = HERE / "wings.jsonl"
    done = {json.loads(l)["image_id"] for l in out.open() if "error" not in json.loads(l)} if out.exists() else set()
    todo = F[~F.image_id.isin(done)]
    print(f"{len(todo)} dots to do", flush=True)
    with out.open("a") as fh:
        for n, r in enumerate(todo.itertuples(), 1):
            rec = dict(image_id=int(r.image_id), dive_id=int(r.dive_id), model=r.model, depth_m=float(r.depth_m)); t0 = time.time()
            try:
                with rawpy.imread(io.BytesIO(Path(real_path(r.raw_path)).read_bytes())) as raw:
                    mos = raw.raw_image_visible.astype(np.float64); cols = raw.raw_colors_visible
                    white = raw.white_level; black = np.array(raw.black_level_per_channel, float); desc = raw.color_desc.decode()
                K, dist = intr[int(r.camera_id)]
                sx, sy = lc.rectified_to_sensor_point(float(r.x), float(r.y), K, dist)
                y0, x0 = int(round(sy)), int(round(sx))
                for ch in ("R", "B"):
                    idx = [i for i, c in enumerate(desc) if c == ch]
                    rec[ch] = wing_fit(mos, cols, idx, black[idx[0]], white, y0, x0)
            except Exception as e:
                rec["error"] = f"{type(e).__name__}: {e}"
            rec["seconds"] = round(time.time() - t0, 1)
            fh.write(json.dumps(rec) + "\n"); fh.flush()
            if n % 10 == 0:
                print(f"{n}/{len(todo)}", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main([int(d) for d in sys.argv[1:]])
