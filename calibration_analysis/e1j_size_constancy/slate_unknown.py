"""E1j in field water: the dive slate as a rigid object of UNKNOWN size.

Size constancy needs a rigid object seen at several ranges with the dot on it. The slate is
one, and in field frames it has human corner labels. Its apparent size s_k (RMS distance of
its 8 labelled reference points from their centroid, px) goes as 1/Z_k, and so does the
dot's offset from the vanishing point, t_k - t_v. So only the true t_v makes
s_k / (t_k - t_v) constant. The slate's physical size is never used; that is the point.

Truth: the stored calibration's laser axis, projected to the vanishing point on the dive
line (as in e1k_beam_streak/truth.py). The known-size slate PnP produced that calibration,
so this compares "slate of unknown size" with "slate of known size" on the same frames.

Run from this repo:  uv run python slate_unknown.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar

REPO = Path(__file__).resolve().parents[2]
SCRATCH = Path(__file__).resolve().parents[2] / "data/db_extracts"   # DB extracts (restored backup), kept in the repo
F_PX, MIN_FRAMES = 2850.0, 8


DESIGN_POINTS = {"H-Slate": 8, "Tic-Tac-Toe": 8, "V-Slate": 6}


def design_points() -> pd.Series:
    """Reference points per dive, from the dive's slate pattern (data/db_extracts/annotations.psv)."""
    a = pd.read_csv(SCRATCH / "annotations.psv", sep="|", header=None, usecols=[0, 3, 12], names=["kind", "dive_id", "slate"])
    a = a[(a.kind == "slate") & a.slate.notna()].drop_duplicates("dive_id")
    return a.set_index("dive_id").slate.str.extract(r"^(H-Slate|Tic-Tac-Toe|V-Slate)")[0].map(DESIGN_POINTS)


def load():
    d = pd.read_csv(SCRATCH / "slate_dots.psv", sep="|", header=None,
                    names=["dive_id", "camera_id", "image_id", "pts", "x", "y", "taken"]).drop_duplicates("image_id")
    d = d[d.pts.notna()]
    # Keep complete labels only, so the size measure is comparable within a dive. A complete label has
    # the slate pattern's own number of reference points: 8 on H and Tic-Tac-Toe, 6 on the V-slate
    # (author, 2026-10-06). A skipped point is left out of the label (it does not come back as null),
    # and which point is missing is not recorded, so a short label cannot be used.
    pts = d.pts.map(lambda s: np.array([q if q is not None else [np.nan, np.nan] for q in json.loads(s)], float))
    need = d.dive_id.map(design_points()).fillna(8)
    full = pd.Series([p.ndim == 2 and p.shape == (n, 2) and np.isfinite(p).all() for p, n in zip(pts, need)], index=d.index)
    d, pts = d[full], pts[full]
    d["size"] = pts.map(lambda p: float(np.sqrt(((p - p.mean(0)) ** 2).sum(1).mean())))
    lines = pd.read_csv(SCRATCH / "lines.psv", sep="|", header=None, names=["dive_id", "a", "b", "c", "n", "resid"]).set_index("dive_id")
    ext = pd.read_csv(SCRATCH / "extrinsics.psv", sep="|", header=None, names=["dive_id", "camera_id", "axis"]).drop_duplicates("dive_id").set_index("dive_id")
    intr = {int(r.camera_id): np.array(json.loads(r.camera_matrix)) for r in pd.read_csv(REPO / "laser_detection_analysis/intrinsics.csv").itertuples()}
    return d, lines, ext, intr


def frame(dive, g, lines):
    """Unit direction u along the dive line, oriented to negative y (t grows away from v on FSL mounts)."""
    if dive in lines.index:
        a, b, c = lines.loc[dive, ["a", "b", "c"]]
        n = np.array([a, b]) / np.hypot(a, b)
        u = np.array([n[1], -n[0]])
    else:
        xy = g[["x", "y"]].to_numpy(float)
        u = np.linalg.svd(xy - xy.mean(0))[2][0]
    return u if u[1] < 0 else -u


def fit_tv(t, s):
    hi = t.min() - 5.0
    obj = lambda tv: np.var(np.log(s / (t - tv)))
    return minimize_scalar(obj, bounds=(hi - 4000.0, hi), method="bounded").x


if __name__ == "__main__":
    d, lines, ext, intr = load()
    rng = np.random.default_rng(0)
    rows = []
    for dive, g in d.groupby("dive_id"):
        if len(g) < MIN_FRAMES:
            continue
        u = frame(dive, g, lines)
        t = g[["x", "y"]].to_numpy(float) @ u; s = g["size"].to_numpy()
        tv = fit_tv(t, s)
        boots = [fit_tv(t[i], s[i]) for i in (rng.integers(0, len(t), len(t)) for _ in range(200))]
        row = dict(dive=dive, frames=len(g), size_ratio=s.max() / s.min(), dot_travel_px=np.ptp(t),
                   tv_fit=tv, se_px=float(np.std(boots)))
        if dive in ext.index:
            ax = np.array(json.loads(ext.loc[dive, "axis"])); K = intr[int(ext.loc[dive, "camera_id"])]
            v = np.array([K[0, 0] * ax[0] / ax[2] + K[0, 2], K[1, 1] * ax[1] / ax[2] + K[1, 2]])
            row.update(tv_true=float(v @ u), err_px=float(tv - v @ u))
        rows.append(row)
    R = pd.DataFrame(rows)
    R["se_deg"] = np.degrees(R.se_px / F_PX)
    if "err_px" in R:
        R["err_deg"] = np.degrees(R.err_px / F_PX)
    pd.set_option("display.width", 200)
    print(R.round(3).sort_values("size_ratio", ascending=False).to_string(index=False))
    T = R.dropna(subset=["err_px"])
    print(f"\n{len(R)} dives; {len(T)} with a stored calibration. |error| median {T.err_deg.abs().median():.3f} deg; "
          f"within 0.05: {(T.err_deg.abs() <= .05).sum()}, within 0.15: {(T.err_deg.abs() <= .15).sum()}, within 2 SE: {(T.err_px.abs() <= 2 * T.se_px).sum()}")
    wide = T[T.size_ratio >= 1.5]
    if len(wide):
        print(f"dives with >= 1.5x size spread: {len(wide)}; |error| median {wide.err_deg.abs().median():.3f} deg; within 0.15: {(wide.err_deg.abs() <= .15).sum()}")
