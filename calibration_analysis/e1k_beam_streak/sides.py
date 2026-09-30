"""E1k scoring: is there a streak, and is it a beam?

Two tests on the profiles probe.py saved:
1. One-sidedness. The beam runs from the laser to the dot, so it lies on the laser side of
   every dot (t > t_dot) and not on the v side (t < t_dot), where the beam has already hit
   the surface. Any line-aligned artefact (rectification, flare through the image centre)
   is on both sides. Excess = on-line (|offset| <= 4 px) minus outer (|offset| >= 40 px),
   stacked over frames; the error is the frame-to-frame SE.
2. The wedge. A cylinder's image width grows linearly with distance from its vanishing
   point. Laser-side profiles are stacked in four bins along the line and the transverse
   width of the excess (FWHM and rms of the positive part within 30 px) is reported.

Run from this repo:  ../../../wuwnet-fishsense2026/.venv/bin/python sides.py DIVE [DIVE ...]
"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
M = 80


def score(dive: int):
    z = np.load(HERE / f"streak_{dive}.npz"); offs = z["offs"]; ts = z["ts"]; meta = json.loads(str(z["meta"]))
    tdot = np.array([m["t_dot"] for m in meta]); green = bool(meta[0].get("green", False))
    P = z["G"] if green else z["R"]
    laser_side = ts[None, :] > tdot[:, None] + M
    v_side = ts[None, :] < tdot[:, None] - M
    inner = np.abs(offs) <= 4; outer = np.abs(offs) >= 40
    ex = np.nanmean(P[:, :, inner], axis=2) - np.nanmean(P[:, :, outer], axis=2)
    print(f"dive {dive} ({'green' if green else 'red'} laser, {len(meta)} frames, background {np.median([m['red_median'] for m in meta])*1e3:.0f}e-3 of full)")
    for name, m in (("laser side", laser_side), ("v side", v_side)):
        e = np.where(m, ex, np.nan); pf = np.nanmean(e, axis=1); pf = pf[np.isfinite(pf)]
        print(f"  {name:10s}: excess {np.nanmean(e)*1e3:+.2f} ± {np.std(pf)/np.sqrt(max(len(pf),1))*1e3:.2f}e-3  (pairs {int(np.isfinite(e).sum())})")
    for k in ("Rc+", "Rc-"):
        Q = z[k]; e = np.nanmean(Q[:, :, inner], axis=2) - np.nanmean(Q[:, :, outer], axis=2); e = np.where(laser_side, e, np.nan)
        pf = np.nanmean(e, axis=1); pf = pf[np.isfinite(pf)]
        print(f"  control {k:4s}: excess {np.nanmean(e)*1e3:+.2f} ± {np.std(pf)/np.sqrt(max(len(pf),1))*1e3:.2f}e-3")
    prof_all = np.where(laser_side[:, :, None], P, np.nan)
    have = ts[laser_side.any(0)]
    if len(have) < 8:
        return
    edges = np.quantile(have, [0, .25, .5, .75, 1])
    core = np.abs(offs) <= 30
    print(f"  {'t along line':>16} {'from far dot':>12} {'peak':>8} {'fwhm':>5} {'rms':>5}")
    for lo, hi in zip(edges[:-1], edges[1:]):
        sel = (ts >= lo) & (ts <= hi)
        p = np.nanmean(prof_all[:, sel, :], axis=(0, 1)); p = p - np.nanmean(p[outer])
        half = np.nanmax(p[core]) / 2; above = np.where((p >= half) & core)[0]
        w = offs[above[-1]] - offs[above[0]] if len(above) else np.nan
        q = np.clip(p[core], 0, None); o = offs[core]; rms = np.sqrt((q * o ** 2).sum() / q.sum()) if q.sum() > 0 else np.nan
        print(f"  {lo:7.0f}..{hi:7.0f} {(lo + hi) / 2 - tdot.min():12.0f} {np.nanmax(p[core])*1e3:+8.2f} {w:5.0f} {rms:5.1f}")


if __name__ == "__main__":
    for d in sys.argv[1:]:
        score(int(d))
