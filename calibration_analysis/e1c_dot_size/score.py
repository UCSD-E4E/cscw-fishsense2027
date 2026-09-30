"""E1c scoring against the criteria pre-registered in p2-tests.md (before any data).

1. Physics   -- within a dive, width vs 1/Z (Z from the stored calibration) is linear;
                target residual ~0.1 px, kill line 0.3 px. Dots beyond 0.8 m, <=5 clipped px.
2. Constancy -- the intercept c (= f * divergence) agrees across dives of one laser.
                Camera id stands in for the laser unit: the database records no laser serial.
3. Blind     -- with c from the *other* dives of that camera, fit p = v + k (s - c) from the
                dots alone; v is the beam's vanishing point on the dive line. Target: beam
                angle within 0.05 deg of the stored calibration, known-length error in budget.

Known lengths appear only in step 3's check. Run from this repo: `uv run python score.py`.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
IMWUT = REPO.parent / "imwut_2026_fishsense_lite"
sys.path.insert(0, str(IMWUT))
from fishsense_imwut import calibration as cal  # noqa: E402

MIN_Z, MAX_CLIPPED = 0.8, 5
KILL_PX, TARGET_PX, PHI_TARGET_DEG = 0.3, 0.1, 0.05


def load() -> pd.DataFrame:
    latest = {}
    for line in (HERE / "widths.jsonl").open():
        if line.strip():
            r = json.loads(line)
            latest[r["image_id"]] = r
    w = pd.DataFrame(list(latest.values()))
    w = w[w.fit.notna() & w.get("error", pd.Series(index=w.index, dtype=object)).isna()].reset_index(drop=True)
    w = pd.concat([w, pd.json_normalize(w.fit.tolist())], axis=1)
    f = pd.read_csv(HERE / "frames.csv")[["image_id", "camera_id", "calibration_dive_id", "x", "y", "depth_m", "length_m", "model"]]
    w = w.merge(f, on="image_id")
    w["invZ"] = 1 / w.depth_m
    w["good_fit"] = (w.sigma_major < 24) & (w.peak_offset_px < 4) & (w.fit_rmse < 0.25 * w.amp) & (w.snr > 5)
    w["clean"] = (w.depth_m >= MIN_Z) & (w.saturated_px <= MAX_CLIPPED) & w.good_fit
    return w


def mad(r):
    return 1.4826 * np.median(np.abs(r - np.median(r)))


def physics(w: pd.DataFrame, width: str = "sigma_geo") -> pd.DataFrame:
    rows = []
    for d, g in w[w.clean].groupby("dive_id"):
        if len(g) < 5:
            continue
        b, c = np.polyfit(g.invZ, g[width], 1)
        r = g[width] - (c + b * g.invZ)
        rows.append(dict(dive=d, camera=int(g.camera_id.iloc[0]), n=len(g), c=c, b=b,
                         resid_sd=r.std(), resid_robust=mad(r),
                         invZ_span=g.invZ.max() - g.invZ.min(), z_min=g.depth_m.min(), z_max=g.depth_m.max()))
    return pd.DataFrame(rows)


def stored_axes():
    ext = pd.read_csv(REPO / "data" / "e1" / "extrinsics.csv").set_index("dive_id")
    return {int(d): (np.array(json.loads(r.laser_position)), np.array(json.loads(r.laser_axis))) for d, r in ext.iterrows()}


def blind(w: pd.DataFrame, ph: pd.DataFrame, width: str = "sigma_geo") -> pd.DataFrame:
    """Leave-one-dive-out c per camera; v from the dots of this dive alone."""
    axes = stored_axes()
    K = {int(r.camera_id): np.array(json.loads(r.camera_matrix))
         for r in pd.read_csv(REPO / "laser_detection_analysis" / "intrinsics.csv").itertuples()}
    rows = []
    for d, g in w[w.clean].groupby("dive_id"):
        cam = int(g.camera_id.iloc[0])
        cdv = g.calibration_dive_id.iloc[0]
        cd = int(d) if pd.isna(cdv) else int(cdv)  # empty = the dive calibrated itself
        others = ph[(ph.camera == cam) & (ph.dive != d)]
        if len(g) < 5 or others.empty or cd not in axes:
            continue
        c = others.c.median()
        pts = g[["x", "y"]].to_numpy()
        centre = pts.mean(0)
        u = np.linalg.svd(pts - centre)[2][0]
        p = (pts - centre) @ u
        k, v = np.polyfit(g[width] - c, p, 1)  # p = v + k (s - c)
        origin, axis = axes[cd]
        vp = K[cam] @ (axis / axis[2])
        v_true = (vp[:2] - centre) @ u
        dphi = np.degrees((v - v_true) / K[cam][0, 0])
        rows.append(dict(dive=d, camera=cam, n=len(g), c_used=c, v_est=v, v_true=v_true,
                         dv_px=v - v_true, dphi_deg=dphi))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    w = load()
    pd.set_option("display.width", 220)
    print(f"dots {len(w)} over {w.dive_id.nunique()} dives | clean {int(w.clean.sum())} "
          f"| clipped (>{MAX_CLIPPED} px) {(w.saturated_px > MAX_CLIPPED).mean():.0%}")
    print(w.assign(zbin=pd.cut(w.depth_m, [0, .8, 1.5, 2.5, 10])).groupby("zbin", observed=True)
          .apply(lambda g: pd.Series(dict(dots=len(g), clipped=f"{(g.saturated_px > MAX_CLIPPED).mean():.0%}",
                                          clean=int(g.clean.sum()))), include_groups=False).to_string())
    for width in ("sigma_geo", "sigma_minor"):
        ph = physics(w, width)
        print(f"\n=== 1. physics ({width}): {len(ph)} dives with >=5 clean dots ===")
        print(ph.round(3).to_string(index=False))
        print(f"median residual {ph.resid_sd.median():.3f} px (robust {ph.resid_robust.median():.3f}); "
              f"dives under {TARGET_PX} px: {(ph.resid_sd <= TARGET_PX).sum()}, over the {KILL_PX} px kill line: {(ph.resid_sd > KILL_PX).sum()}")
        print(f"\n=== 2. constancy ({width}): c by camera ===")
        print(ph.groupby("camera").c.agg(["size", "median", "std", "min", "max"]).round(3).to_string())
        bl = blind(w, ph, width)
        print(f"\n=== 3. blind ({width}) ===")
        if len(bl):
            print(bl.round(3).to_string(index=False))
            print(f"|dphi| median {bl.dphi_deg.abs().median():.3f} deg; within {PHI_TARGET_DEG} deg: {(bl.dphi_deg.abs() <= PHI_TARGET_DEG).sum()}/{len(bl)}")
        else:
            print("no dive has a same-camera partner to borrow c from")
