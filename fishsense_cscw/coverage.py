"""How many dives could calibrate their laser from their own dots (E1g's size + brightness fit)?

Each dive is simulated with its *real* dot count and range spread, under the noise E1g
assumes: width noise 0.3 px (E1c's clean dives showed 0.18-0.33), divergence known to
0.05 px, water absorption 30 % off, reflectance scatter x1.35, 1 px dot position noise.
It also assumes dots are unclipped, i.e. a dimmed laser. The existing corpus is clipped,
so everything here is conditional on E1g.

Per-dot ranges are *reconstructed*: the dot's position along the dive's own line, measured
from the camera's fleet-median vanishing point, through the camera's median mount offset.
On the 56 dives with stored depths that reproduces 1/Z exactly in shape (r = 1.000), with
a scale off by -22 % to +9 % (IQR). That spread is the per-dive phi drift itself, which
is fine: the estimator's precision depends on the count and the spread, not the scale.

Pooling: consecutive dives by one camera on one day share their dots when their lines agree
to POOL_TOL_PX. That is only the line-visible part of the laser state; 11-23 % of harmful
shifts are invisible to it, so pooled numbers are an upper bound.
"""
from __future__ import annotations

import zlib

import numpy as np
import pandas as pd
from scipy.optimize import least_squares

from fishsense_cscw.paths import DATA

COV = DATA / "coverage"
F_PX, A_PXM, CS, B = 2850.0, 296.0, 1.0, 4.0
POOL_TOL_PX = 5.0
CLASSES = [-1, 0.05, 0.15, np.inf]
LABELS = ["<=0.05 deg (target)", "0.05-0.15 (usable)", ">0.15 (no)"]


def load():
    depths = pd.read_csv(COV / "reconstructed_depths.csv")
    dots = pd.read_csv(COV / "dot_pixels.csv")
    dives = pd.read_csv(COV / "dives.csv", parse_dates=["dive_datetime"])
    return depths, dots, dives


def estimate_error(z, rng, s_noise=0.3, cs_err=0.05, refl=0.3, c_att=0.35, c_err=0.3) -> float:
    """|phi error| (deg) of one simulated dive whose dots sit at ranges `z`."""
    n = len(z)
    p = A_PXM / z + rng.normal(0, 1.0, n)
    s = CS + B / z + rng.normal(0, s_noise, n)
    y = np.sqrt(np.exp(rng.normal(0, refl, n)) / z ** 2 * np.exp(-2 * c_att * z))

    def res(q):
        d = q[0]
        zz = A_PXM / np.clip(p - d, 1, None)
        return np.concatenate([(s - (CS + cs_err + q[1] / A_PXM * (p - d))) / s_noise,
                               (y - np.exp(q[2]) * (p - d) * np.exp(-c_att * (1 + c_err) * zz)) / (y.mean() * refl)])

    return abs(np.degrees(least_squares(res, [0.0, B, np.log(y.mean() / p.mean())]).x[0] / F_PX))


def predicted_error(z, trials=30, seed=0, recall=1.0) -> float:
    rng = np.random.default_rng(seed)
    errs = []
    for _ in range(trials):
        zz = z[rng.random(len(z)) < recall] if recall < 1 else z
        errs.append(estimate_error(zz, rng) if len(zz) >= 5 else np.inf)
    return float(np.median(errs))


def _line(xy):
    ctr = xy.mean(0)
    u = np.linalg.svd(xy - ctr)[2][0]
    return ctr, np.array([-u[1], u[0]])


def _off_line(xy, line):
    ctr, nrm = line
    return float(np.median(np.abs((xy - ctr) @ nrm)))


def pool_groups(dots: pd.DataFrame, dives: pd.DataFrame, tol=POOL_TOL_PX) -> dict:
    """Map dive_id -> group id. Consecutive dives of one camera on one day join while the
    union line fits every member's dots to `tol` px (median perpendicular distance)."""
    xy = {d: g[["x", "y"]].to_numpy(float) for d, g in dots.groupby("dive_id")}
    group, gid = {}, 0
    dv = dives[dives.dive_id.isin(xy)].sort_values("dive_datetime")
    for (_, _day), g in dv.groupby(["camera_id", dv.dive_datetime.dt.date]):
        members = []
        for d in g.dive_id:
            if members:
                pts = np.vstack([xy[m] for m in members + [d]])
                line = _line(pts)
                if all(_off_line(xy[m], line) <= tol for m in members + [d]):
                    members.append(d)
                    continue
                gid += 1
                for m in members:
                    group[m] = gid
            members = [d]
        gid += 1
        for m in members:
            group[m] = gid
    return group


def coverage(pooled: bool, recall: float = 1.0, trials: int = 30) -> pd.DataFrame:
    """One row per (pooled) unit with its predicted error and class."""
    depths, dots, dives = load()
    z_by = {d: g.z_m.to_numpy() for d, g in depths.groupby("dive_id")}
    kind = dives.set_index("dive_id").kind
    if pooled:
        grp = pool_groups(dots, dives)
        units = {}
        for d in z_by:
            units.setdefault(grp.get(d, f"solo{d}"), []).append(d)
    else:
        units = {d: [d] for d in z_by}
    rows = []
    for u, members in units.items():
        z = np.concatenate([z_by[m] for m in members])
        # crc32, not hash(): Python randomizes str hashes per process, which made reruns disagree
        err = predicted_error(z, trials=trials, recall=recall, seed=zlib.crc32(str(u).encode()))
        for m in members:
            rows.append(dict(dive_id=m, unit=u, unit_dives=len(members), unit_dots=len(z),
                             dive_dots=len(z_by[m]), kind=kind.get(m, "other"), err=err))
    out = pd.DataFrame(rows)
    out["cls"] = pd.cut(out.err, CLASSES, labels=LABELS)
    return out
