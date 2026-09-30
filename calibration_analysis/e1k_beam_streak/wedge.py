"""E1k: how precisely does the streak's widening locate the beam's vanishing point?

The beam's image width grows linearly with distance from its vanishing point, from both its
physical width (w/O) and defocus (also ~1/Z). With a PSF floor s0:
    sigma(t)^2 = s0^2 + k^2 (t - t_v)^2
Laser-side profiles (probe.py, whole dive) are stacked in bins along the line; each bin's
transverse profile is fitted with Gaussian + constant; then sigma(t) gives t_v. Frames are
bootstrapped for the SE. 0.05 deg of phi is 2.5 px of t_v; the dot line's far end sits
tv_gap px from t_v.

Run:  ../../../wuwnet-fishsense2026/.venv/bin/python wedge.py 257 318
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares

HERE = Path(__file__).resolve().parent
M, NBINS = 80, 8


def bin_widths(P, ts, laser_side, offs, edges):
    out = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        sel = (ts >= lo) & (ts < hi)
        m = laser_side[:, sel]
        if m.sum() < 20:
            out.append((np.nan, np.nan, np.nan)); continue
        p = np.nanmean(np.where(m[:, :, None], P[:, sel, :], np.nan), axis=(0, 1))
        ok = np.isfinite(p)
        f = lambda q: q[0] * np.exp(-0.5 * ((offs[ok] - q[1]) / q[2]) ** 2) + q[3] + q[4] * offs[ok] - p[ok]
        r = least_squares(f, [max(p[ok].max() - np.median(p[ok]), 1e-5), 0, 8, np.median(p[ok]), 0],
                          bounds=([0, -15, 1, -1, -1], [1, 15, 40, 1, 1]))
        out.append(((lo + hi) / 2, r.x[2], r.x[0]))
    return np.array(out)


def fit_tv(W, t_far):
    ok = np.isfinite(W[:, 1])
    t, s = W[ok, 0], W[ok, 1]
    if ok.sum() < 4:
        return np.nan, np.nan, np.nan
    f = lambda q: np.sqrt(q[0] ** 2 + (q[1] * (t - q[2])) ** 2) - s
    r = least_squares(f, [2.0, 0.01, t_far - 200], bounds=([0, 1e-5, t_far - 5000], [30, 1, t_far - 1]))
    return r.x[2], r.x[1], r.x[0]


def run(dive, n_boot=100, quiet=False):
    z = np.load(HERE / f"streak_{dive}_all.npz"); offs = z["offs"]; ts = z["ts"]
    meta = json.loads(str(z["meta"])); green = bool(meta[0].get("green", False))
    P = z["G"] if green else z["R"]; tdot = np.array([m["t_dot"] for m in meta])
    laser_side = ts[None, :] > tdot[:, None] + M
    have = ts[laser_side.sum(0) >= 10]
    edges = np.linspace(have.min(), have.max(), NBINS + 1)
    W = bin_widths(P, ts, laser_side, offs, edges)
    tv, k, s0 = fit_tv(W, tdot.min())
    if not quiet:
        print(f"dive {dive}: {len(meta)} frames; far dot at t={tdot.min():.0f}")
        for t, s, a in W:
            print(f"   t {t:7.0f}  sigma {s:5.1f} px  amp {a * 1e3:5.2f}e-3")
    print(f"   dive {dive} fit: t_v {tv:.0f} ({tdot.min() - tv:.0f} px beyond the far dot), slope {k:.4f}, floor {s0:.1f} px")
    rng = np.random.default_rng(0); boots = []
    for _ in range(n_boot):
        i = rng.integers(0, len(meta), len(meta))
        boots.append(fit_tv(bin_widths(P[i], ts, laser_side[i], offs, edges), tdot.min())[0])
    boots = np.array(boots); boots = boots[np.isfinite(boots)]
    se = np.std(boots)
    print(f"   bootstrap ({len(boots)}): t_v SE {se:.0f} px = {np.degrees(se / 2850):.2f} deg (target 2.5 px = 0.05 deg); "
          f"5-95% {np.percentile(boots, 5):.0f}..{np.percentile(boots, 95):.0f}")
    return tv, se


if __name__ == "__main__":
    for d in sys.argv[1:]:
        run(int(d))
