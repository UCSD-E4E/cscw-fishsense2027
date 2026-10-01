"""E1k probe: is the laser *beam* visible in the water, and does its image widen along the line?

Physics. Scattering makes the beam a faint luminous cylinder of diameter w (a laser constant,
a few mm) running from the laser to the dot. A cylinder's silhouette edges are parallel to
its axis, so in the image they converge at the beam's vanishing point v: the streak is a
wedge with apex at v. At a point along the beam that sits at image coordinate x on the dot
line, the beam is at range t = f*O/(x - v) and its image width is W = f*w/t = (w/O)(x - v).
So the streak's width is linear in distance from v, and extrapolating it to the beam's
far-field width lands on v -- the one laser parameter the dots cannot give. It needs no
brightness model, no reflectance, no dimming: it is a width, measured on light far too
faint to clip. In red-dark water (depth, caves, turbidity) the raw red channel is nearly
black apart from the laser, which is exactly where the dot cues are worst.

This probe only asks whether the streak exists. For each frame it samples the raw Bayer
red (binned 2x2, fraction of full scale) transversely across the dot line at many
positions beyond the dot (away from v), stacks the profiles over frames, and compares the
on-line excess with two control lines 250 px to either side.

Run from P4's environment:  ../../../wuwnet-fishsense2026/.venv/bin/python probe.py DIVE [DIVE ...]
"""
from __future__ import annotations
import json, sys, time
from pathlib import Path
import numpy as np, pandas as pd, rawpy
from scipy.ndimage import map_coordinates

HERE = Path(__file__).resolve().parent
E1C = HERE.parent / "e1c_dot_size"
sys.path.insert(0, str(E1C))
import run_widths as rw  # noqa: E402

NAS = Path.home() / "mnt/fishsense_data/REEF/data"
SCRATCH = Path(__file__).resolve().parents[2] / "data/db_extracts"   # DB extracts (restored backup), kept in the repo
# divelaserline a, b, c (rectified coordinates), from the restored DB
LINES = {526: (0.9284696392645663, -0.3714083049205093, -1333.0422347711647),
         440: (-0.9569151477764191, 0.2903676978522819, 1447.7086566897458),
         475: (-0.9544123900623578, 0.2984911886395608, 1451.4688055029067),
         257: (0.9523858797277137, -0.3048952870991428, -1501.2113721666851),
         318: (-0.9534543256397028, 0.3015374751485123, 1517.8479523369213),
         331: (0.95202507786645, -0.306020017504378, -1499.739152760842)}
for _l in (SCRATCH / "lines.psv").read_text().split():   # every other dive's line from the restored DB
    _d, _a, _b, _c = _l.split("|")[:4]
    LINES.setdefault(int(_d), (float(_a), float(_b), float(_c)))
import os
import sys as _sys; _sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2]))
from fishsense_cscw.anon import real_path  # noqa: E402  (pseudonymised paths -> real NAS paths)
STEP, OFFS, MARGIN, CONTROL, N_FRAMES = 25, np.arange(-60, 61, 2.0), 80, 250, int(os.environ.get("N_FRAMES", 40))


def half_channels(raw):
    """2x2-binned R, G, B as fractions of full scale, black subtracted, no white balance."""
    mos = raw.raw_image_visible.astype(np.float32); pat = raw.raw_pattern
    blk = raw.black_level_per_channel; white = raw.white_level
    h, w = mos.shape[0] // 2 * 2, mos.shape[1] // 2 * 2
    by_color = {}
    for dy in range(2):
        for dx in range(2):
            c = int(pat[dy, dx])
            by_color.setdefault(c, []).append((mos[dy:h:2, dx:w:2] - blk[c]) / (white - blk[c]))
    return by_color[0][0], np.mean(by_color[1] + by_color.get(3, []), axis=0), by_color[2][0]


def line_frame(a, b, c, dots_xy):
    n = np.array([a, b]) / np.hypot(a, b); u = np.array([n[1], -n[0]]); foot = -c / np.hypot(a, b) * n
    t = dots_xy @ u
    # On every FSL mount the dots move up-frame (negative y) as range shrinks, so orienting u
    # to negative y makes t increase away from v. A skew-based guess flipped dive 349, whose
    # dots have no near-range tail; the stored calibrations confirm this orientation.
    if u[1] > 0:
        u, t = -u, -t
    return u, n, foot, t


def sample(img, pts_half, dirs, offs):
    """Transverse profiles: for each sensor point and local direction, sample along the normal."""
    nrm = np.stack([-dirs[:, 1], dirs[:, 0]], 1)
    xy = pts_half[:, None, :] + (offs[None, :, None] / 2.0) * nrm[:, None, :]  # half-size coords
    return map_coordinates(img, [xy[..., 1].ravel(), xy[..., 0].ravel()], order=1, cval=np.nan).reshape(xy.shape[:2])


def main(dives):
    lc = rw._load("laser_color", rw.LC)
    intr = {int(r.camera_id): (json.loads(r.camera_matrix), json.loads(r.distortion_coefficients))
            for r in pd.read_csv(rw.REPO / "laser_detection_analysis/intrinsics.csv").itertuples()}
    D = pd.read_csv(SCRATCH / "field_dots.psv", sep="|", header=None,
                    names=["dive_id", "camera_id", "image_id", "path", "x", "y", "label", "depth_m", "range_m"])
    for dive in dives:
        g = D[(D.dive_id == dive) & D.label.str.contains("Laser")].drop_duplicates("image_id")
        green = bool(g.label.str.contains("Green").iloc[0])  # the streak is the laser's colour; controls use the same channel
        a, b, c = LINES[dive]; K, dist = intr[int(g.camera_id.iloc[0])]
        u, n, foot, t_dots = line_frame(a, b, c, g[["x", "y"]].to_numpy(float))
        g = g.assign(t=t_dots).sort_values("t")
        print(f"dive {dive}: {len(g)} dots; t from {t_dots.min():.0f} to {t_dots.max():.0f}, median {np.median(t_dots):.0f}, "
              f"mean {t_dots.mean():.0f}; away-from-v direction {u.round(3)}", flush=True)
        frames = g.head(N_FRAMES)  # far dots first: they leave the longest streak; N_FRAMES=1000 takes the whole dive
        ts = np.arange(t_dots.min() - 400, t_dots.max() + 1200, STEP)
        rect = foot + ts[:, None] * u
        ok = (rect[:, 0] > 40) & (rect[:, 0] < 3970) & (rect[:, 1] > 40) & (rect[:, 1] < 2980)
        ts, rect = ts[ok], rect[ok]
        rows = {}
        for shift in (0, CONTROL, -CONTROL):
            pts = np.array([lc.rectified_to_sensor_point(float(x), float(y), K, dist) for x, y in rect + shift * n])
            d = np.gradient(pts, axis=0); d /= np.linalg.norm(d, axis=1, keepdims=True)
            rows[shift] = (pts / 2.0, d)
        prof = {k: [] for k in ("R", "G", "B", "Rc+", "Rc-")}  # Rc = laser-channel controls
        valid = []; meta = []
        for i, r in enumerate(frames.itertuples(), 1):
            t0 = time.time()
            try:
                with rawpy.imread(str(NAS / real_path(r.path, NAS))) as raw:
                    R, G, B = half_channels(raw)
                prof["R"].append(sample(R, *rows[0], OFFS)); prof["G"].append(sample(G, *rows[0], OFFS)); prof["B"].append(sample(B, *rows[0], OFFS))
                L = G if green else R
                prof["Rc+"].append(sample(L, *rows[CONTROL], OFFS)); prof["Rc-"].append(sample(L, *rows[-CONTROL], OFFS))
                valid.append(ts > r.t + MARGIN)
                meta.append(dict(image_id=int(r.image_id), t_dot=float(r.t), green=green, red_median=float(np.nanmedian(R)), red_p99=float(np.nanpercentile(R, 99))))
            except Exception as e:
                print(f"  frame {r.image_id}: {type(e).__name__}: {e}", flush=True)
            if i % 6 == 0:
                print(f"  {i}/{len(frames)} ({time.time() - t0:.1f}s last)", flush=True)
        np.savez(HERE / f"streak_{dive}{os.environ.get('TAG', '')}.npz", ts=ts, offs=OFFS, valid=np.array(valid), meta=json.dumps(meta),
                 **{k: np.array(v) for k, v in prof.items()})
        summarize(dive)


def summarize(dive):
    z = np.load(HERE / f"streak_{dive}{os.environ.get('TAG', '')}.npz"); ts, offs, valid = z["ts"], z["offs"], z["valid"]
    meta = json.loads(str(z["meta"]))
    print(f"dive {dive}: red median {np.median([m['red_median'] for m in meta]) * 1e3:.1f}e-3 of full, "
          f"p99 {np.median([m['red_p99'] for m in meta]) * 1e3:.0f}e-3")
    outer = np.abs(offs) >= 40; inner = np.abs(offs) <= 4
    print(f"{'t (px)':>7} {'n':>3} {'R excess':>9} {'R bg':>7} {'ctrl+':>7} {'ctrl-':>7} {'G excess':>9} {'fwhm':>5}")
    for j in range(0, len(ts), 4):
        m = valid[:, j]
        if m.sum() < 3:
            continue
        def ex(k):
            p = np.nanmean(z[k][m, j, :], axis=0)
            return p, np.nanmean(p[inner]) - np.nanmean(p[outer])
        pR, eR = ex("R"); _, eG = ex("G"); _, ec1 = ex("Rc+"); _, ec2 = ex("Rc-")
        prof = pR - np.nanmean(pR[outer]); half = np.nanmax(prof) / 2
        above = np.where(prof >= half)[0]; fwhm = (offs[above[-1]] - offs[above[0]]) if len(above) else np.nan
        print(f"{ts[j]:7.0f} {m.sum():3d} {eR * 1e3:9.2f} {np.nanmean(pR[outer]) * 1e3:7.2f} {ec1 * 1e3:7.2f} {ec2 * 1e3:7.2f} {eG * 1e3:9.2f} {fwhm:5.0f}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[0] == "summarize":
        for d in args[1:]:
            summarize(int(d))
    else:
        main([int(d) for d in args])
