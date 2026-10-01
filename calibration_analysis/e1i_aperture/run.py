"""E1i: the undimmed dot's total returned light, as a wide-aperture sum on the raw mosaic.

E1h fitted a Gaussian profile to the wings and failed because the wings are scatter halo.
The halo is still laser light, though, so a sum over an aperture that holds the halo should
keep the dot's total brightness (light loss with range), whatever shape the scatter gives it.
It only works where a channel's photosites are unclipped; the blue ones see the red laser
weakly and clip only at close range.

Per dot, for the R, G and B photosites: background is the median of a ring at 50-60 px;
sums of (I - bg) inside radii 10/20/30/45 px, scaled by 1/(fraction of photosites of that
colour), plus the saturated-photosite count. Exposure (t, ISO, N) is joined later with
exiftool. One JSON line per dot.

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

H, BG_IN, RADII = 60, 50, (10, 20, 30, 45)


def aperture(mos, cols, idx, black, white, y0, x0):
    win = mos[y0 - H:y0 + H + 1, x0 - H:x0 + H + 1]; cw = cols[y0 - H:y0 + H + 1, x0 - H:x0 + H + 1]
    m = np.isin(cw, idx); v = win - black
    yy, xx = np.mgrid[-H:H + 1, -H:H + 1]; r = np.hypot(yy, xx)
    bg = float(np.median(v[m & (r >= BG_IN)]))
    frac = m.mean()
    out = dict(saturated=int((m & (win >= white - 2) & (r <= RADII[-1])).sum()), bg=bg, full=float(white - black))
    for R in RADII:
        k = m & (r <= R)
        out[f"sum{R}"] = float((v[k] - bg).sum() / frac)
    return out


def main(dives):
    lc = rw._load("laser_color", rw.LC)
    intr = {int(r.camera_id): (json.loads(r.camera_matrix), json.loads(r.distortion_coefficients))
            for r in pd.read_csv(rw.REPO / "laser_detection_analysis/intrinsics.csv").itertuples()}
    F = pd.read_csv(E1C / "frames.csv").dropna(subset=["raw_path"])
    F = F[F.label.str.contains("Red") & F.dive_id.isin(dives)]
    out = HERE / "aperture.jsonl"
    done = {json.loads(l)["image_id"] for l in out.open() if "error" not in json.loads(l)} if out.exists() else set()
    todo = F[~F.image_id.isin(done)]
    print(f"{len(todo)} dots to do", flush=True)
    with out.open("a") as fh:
        for n, r in enumerate(todo.itertuples(), 1):
            rec = dict(image_id=int(r.image_id), dive_id=int(r.dive_id), model=r.model, depth_m=float(r.depth_m),
                       raw_path=r.raw_path); t0 = time.time()
            try:
                with rawpy.imread(io.BytesIO(Path(real_path(r.raw_path)).read_bytes())) as raw:
                    mos = raw.raw_image_visible.astype(np.float64); cols = raw.raw_colors_visible
                    white = raw.white_level; black = np.array(raw.black_level_per_channel, float); desc = raw.color_desc.decode()
                K, dist = intr[int(r.camera_id)]
                sx, sy = lc.rectified_to_sensor_point(float(r.x), float(r.y), K, dist)
                y0, x0 = int(round(sy)), int(round(sx))
                for ch in ("R", "G", "B"):
                    idx = [i for i, c in enumerate(desc) if c == ch]
                    rec[ch] = aperture(mos, cols, idx, black[idx[0]], white, y0, x0)
            except Exception as e:
                rec["error"] = f"{type(e).__name__}: {e}"
            rec["seconds"] = round(time.time() - t0, 1)
            fh.write(json.dumps(rec) + "\n"); fh.flush()
            if n % 10 == 0:
                print(f"{n}/{len(todo)}", flush=True)
    print("done", flush=True)


if __name__ == "__main__":
    main([int(d) for d in sys.argv[1:]])
