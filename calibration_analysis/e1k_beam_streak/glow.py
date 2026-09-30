"""E1k-b: the streak's integrated brightness along the line locates v.

Per pixel of image length the camera sees a beam segment dZ = Z^2/A dx at range ~Z, so the
scattered power it collects is b * dZ / Z^2 = b / A: inverse square cancels exactly. What
is left is attenuation out and back, exp(-2 c Z), with Z = A / (x - v):
    ln I(x) = k - a / (x - v),   a = 2 c A
b is the water's scattering phase function near backscatter (nearly flat over the few
degrees involved). No surface, so no reflectance; no clipping; the beam is the target.

I(x) is the transverse integral of the laser-side excess (Gaussian + linear background, as
in wedge.py), in NBINS bins along the line. Fit k, a, v; bootstrap frames.

Run:  ../../../wuwnet-fishsense2026/.venv/bin/python glow.py 475 [440 ...]
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np
from scipy.optimize import least_squares

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from wedge import bin_widths, M  # noqa: E402

NBINS, F_PX = 12, 2850.0


def fit(W, t_far):
    ok = np.isfinite(W[:, 1]) & (W[:, 2] > 0)
    t, y = W[ok, 0], np.log(W[ok, 2] * W[ok, 1])   # amplitude * sigma  ~ integrated flux
    if ok.sum() < 5:
        return np.nan, np.nan
    best = None
    for tv0 in (t_far - 30, t_far - 150, t_far - 500):
        r = least_squares(lambda q: q[0] - q[1] / (t - q[2]) - y, [y.max(), 50.0, tv0],
                          bounds=([-50, 0, t_far - 5000], [50, 1e5, t_far - 1]))
        if best is None or r.cost < best.cost:
            best = r
    return best.x[2], best.x[1]


def run(dive, n_boot=60):
    z = np.load(HERE / f"streak_{dive}_all.npz"); offs = z["offs"]; ts = z["ts"]
    meta = json.loads(str(z["meta"])); green = bool(meta[0].get("green", False))
    P = z["G"] if green else z["R"]; tdot = np.array([m["t_dot"] for m in meta])
    laser_side = ts[None, :] > tdot[:, None] + M
    have = ts[laser_side.sum(0) >= 10]
    edges = np.linspace(have.min(), have.max(), NBINS + 1)
    W = bin_widths(P, ts, laser_side, offs, edges)
    tv, a = fit(W, tdot.min())
    print(f"dive {dive}: {len(meta)} frames, far dot t={tdot.min():.0f}")
    print("   t, integrated:", [(int(t), round(float(A * s * 1e3), 1)) for t, s, A in W if np.isfinite(s)])
    rng = np.random.default_rng(0); boots = []
    for _ in range(n_boot):
        i = rng.integers(0, len(meta), len(meta))
        boots.append(fit(bin_widths(P[i], ts, laser_side[i], offs, edges), tdot.min())[0])
    b = np.array(boots); b = b[np.isfinite(b)]; se = float(np.std(b))
    print(f"   fit t_v {tv:.0f} ({tdot.min() - tv:.0f} px beyond far dot), a {a:.0f}; bootstrap SE {se:.0f} px = {np.degrees(se / F_PX):.2f} deg; "
          f"5-95% {np.percentile(b, 5):.0f}..{np.percentile(b, 95):.0f}; at bound {np.mean(b >= tdot.min() - 2):.0%}")
    return tv, se


if __name__ == "__main__":
    for d in sys.argv[1:]:
        run(int(d))
