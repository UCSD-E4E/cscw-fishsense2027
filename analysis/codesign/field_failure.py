"""Why size constancy fails in the field: four checks, rebuilt from the frozen 2026-09-25 dump.

These first came from a fishsense-services session on 2026-10-23 (read-only, offline); its scripts and its inputs
(exports of the services database) were not kept. This script redoes each check from this repo's extracts, so
the numbers are its own and may differ from that session's (the comparison is in the report, not adjusted here).

1 offset   For each stored calibration (e2e_measurement/extrinsics.psv), the laser's offset from the camera
           ray perpendicular to the beam, |O_perp|, and A = fx * |O_perp| (px * m): the dot sits A/Z px from
           the vanishing point at range Z, so 1 px of dot error along the line is Z/A of range.
2 predicted  Scale SD that 1 px of dot noise alone gives a size-constancy fit, on each archive slate geometry:
           every dive with a stored calibration and >= 8 complete slate labels with a human dot (frame ranges =
           the stored beam's depth at the human dot). t_k = A/Z_k + noise, s_k proportional to 1/Z_k; t_v fitted
           as in slate_unknown.fit_tv; scale error = range error at the dive's median slate range. 500 draws per
           dive. Also with 1.1 px dot and 0.5% size noise (the services session's noise model).
3 tilt     Each live human slate label's pose by PnP against its template (data/db_extracts/slate_templates.psv,
           reference points at the scan's dpi; skipped points dropped), planar IPPE. tilt = angle between the
           slate's normal and the camera's optical axis; range = depth of the slate centre. Per dive, the OLS
           slope of log cos(tilt) on log range, with a 95% interval resampling frames.
4 handling Pool sessions (the 10 slate sessions with a stored calibration): human dots, SAM 3 text-prompted sizes
           (calibration_analysis/e1j_size_constancy/sizes/sam3_text.csv), t_v fitted, ranges Z = A/(t - t_v)
           with the session's stored A. Referee: each frame's PnP range of the human dot (the dot's ray meeting
           the human-pose plane). Error = median over frames of Z_fit / Z_pnp - 1. Conditions:
             base  as measured
             A     + reef dot noise: along-line residuals (automatic - human) on reef slate frames, resampled
                   onto each frame, 20 trials per session
             B     + the reef's tilt trend on size: log s += 0.5 * slope * log(Z / Z_median) (sqrt(area) goes as
                   sqrt(cos tilt)); slope = the mean of check 3's slopes on dives 347, 349 and 436 where the
                   pose fits well (median reprojection error <= GOOD_POSE_PX), and, as the services session used,
                   -0.07
             A+B   both
           Every fit trims outlier frames as the services fit did (fit_trimmed: 4 sigma of 1.1 px dot and 0.5%
           size noise at the frame's distance from t_v), so rare gross dot misses are dropped, not averaged.

Inputs: data/db_extracts/{slate_dots,slate_label_points,slate_templates,slate_frame_predictions,lines,
annotations}.psv; e2e_measurement/extrinsics.psv; laser_detection_analysis/intrinsics.csv.
Writes analysis/codesign/results/field_failure_{offset,predicted,tilt,handling}.csv.
Run: uv run --with opencv-python-headless python analysis/codesign/field_failure.py
"""
from __future__ import annotations

import json
import sys

import cv2
import numpy as np
import pandas as pd

from fishsense_cscw.paths import REPO

sys.path.insert(0, str(REPO / "calibration_analysis/e1j_size_constancy"))
sys.path.insert(0, str(REPO / "e2e_measurement"))
import score as S  # noqa: E402
import slate_unknown as su  # noqa: E402

DB = REPO / "data/db_extracts"
OUT = REPO / "analysis/codesign/results"
POOL = (62, 63, 65, 71, 77, 80, 83, 87, 94, 114)
REEF_TREND = (347, 349, 436)
RNG = np.random.default_rng(0)
DOT_PX, SIZE_FRAC, TRIM_SIGMA = 1.1, 0.005, 4.0    # the services session's noise model and trim (2026-10-23)
GOOD_POSE_PX = 2.0                                 # dives whose median PnP reprojection error is above this are not used for the trend


def fit_trimmed(t, s):
    """fit_tv with a deleted-residual trim: each kept frame is scored against the fit made without it (its
    residual in log(s / (t - t_v)) over what DOT_PX of dot noise and SIZE_FRAC of size noise explain at its
    distance from that t_v; a frame at or behind that t_v scores infinite), and the worst is dropped while it
    exceeds TRIM_SIGMA, keeping at least MIN_FRAMES. Scoring against the fit without the frame stops one gross
    dot from dragging t_v past every other frame before it can be judged."""
    keep = np.ones(len(t), bool)
    while keep.sum() > su.MIN_FRAMES:
        z = np.full(len(t), -1.0)
        for i in np.flatnonzero(keep):
            k = keep.copy(); k[i] = False
            tv = su.fit_tv(t[k], s[k])
            if t[i] - tv <= 0:
                z[i] = np.inf
                continue
            ref = np.median(np.log(s[k] / (t[k] - tv)))
            z[i] = abs(np.log(s[i] / (t[i] - tv)) - ref) / np.hypot(DOT_PX / (t[i] - tv), SIZE_FRAC)
        if z.max() <= TRIM_SIGMA:
            break
        keep[np.argmax(z)] = False
    return su.fit_tv(t[keep], s[keep]), keep


def stored():
    E = pd.read_csv(REPO / "e2e_measurement/extrinsics.psv", sep="|")
    intr = {int(r.camera_id): np.array(json.loads(r.camera_matrix)) for r in pd.read_csv(REPO / "laser_detection_analysis/intrinsics.csv").itertuples()}
    cal = {}
    for r in E.itertuples():
        O, a = np.array(json.loads(r.laser_position)), np.array(json.loads(r.laser_axis))
        a = a / np.linalg.norm(a)
        K = intr[int(r.camera_id)]
        cal[int(r.dive_id)] = dict(O=O, a=a, K=K, A=K[0, 0] * float(np.linalg.norm(O - (O @ a) * a)))
    return cal


def offset(cal):
    R = pd.DataFrame([dict(dive=d, fx=c["K"][0, 0], o_perp_mm=1000 * c["A"] / c["K"][0, 0], A_px_m=c["A"]) for d, c in cal.items()])
    R["pct_range_per_px_at_1m"] = 100 / R.A_px_m
    R.to_csv(OUT / "field_failure_offset.csv", index=False)
    print(f"1 offset: {len(R)} calibrations; A = fx*|O_perp| median {R.A_px_m.median():.0f} px*m "
          f"({R.A_px_m.min():.0f}-{R.A_px_m.max():.0f}); |O_perp| median {R.o_perp_mm.median():.1f} mm; "
          f"1 px = {R.pct_range_per_px_at_1m.median():.2f}% of range at 1 m, {2 * R.pct_range_per_px_at_1m.median():.2f}% at 2 m")


def slate_frames(cal):
    d, lines, _, _ = su.load()
    d = d[d.dive_id.isin(cal)]
    d["Z"] = [S.depth(cal[r.dive_id]["K"], cal[r.dive_id]["O"], cal[r.dive_id]["a"], r.x, r.y) for r in d.itertuples()]
    return d[d.Z > 0], lines


def predicted(cal, d):
    rows = []
    for dive, g in d.groupby("dive_id"):
        if len(g) < su.MIN_FRAMES:
            continue
        A, Z = cal[dive]["A"], g.Z.to_numpy()
        t0, s0 = A / Z, 1 / Z
        tm = A / np.median(Z)
        out = dict(dive=dive, setting="pool" if dive in POOL else "field", frames=len(g), range_min=Z.min(), range_max=Z.max(),
                   range_spread=Z.max() / Z.min())
        for name, dot_px, size_frac in (("dot1px", 1.0, 0.0), ("dot1.1px_size0.5pct", 1.1, 0.005)):
            err = []
            for _ in range(500):
                t = t0 + RNG.normal(0, dot_px, len(Z))
                s = s0 * np.exp(RNG.normal(0, size_frac, len(Z)))
                tv = su.fit_tv(t, s)
                err.append(tm / (tm - tv) - 1)          # true t_v is 0: the range scale at the median slate range
            out[f"scale_sd_pct_{name}"] = 100 * float(np.std(err))
        rows.append(out)
    R = pd.DataFrame(rows)
    R.to_csv(OUT / "field_failure_predicted.csv", index=False)
    for setting, g in R.groupby("setting"):
        print(f"2 predicted ({setting}): {len(g)} dives, {g.frames.sum()} frames; scale SD from 1 px "
              f"median {g.scale_sd_pct_dot1px.median():.2f}% (range {g.scale_sd_pct_dot1px.min():.2f}-{g.scale_sd_pct_dot1px.max():.2f}%); "
              f"with 1.1 px + 0.5% size {g['scale_sd_pct_dot1.1px_size0.5pct'].median():.2f}% "
              f"({g['scale_sd_pct_dot1.1px_size0.5pct'].min():.2f}-{g['scale_sd_pct_dot1.1px_size0.5pct'].max():.2f}%)")
    return R


def poses(cal):
    """Per live human slate label on a dive with a template: tilt, centre range, the human dot's range on the plane."""
    T = pd.read_csv(DB / "slate_templates.psv", sep="|", header=None, names=["tid", "name", "dpi", "pts"])
    tpl = {r.name: np.array(json.loads(r.pts), float) / r.dpi * 0.0254 for r in T.itertuples()}
    a = pd.read_csv(DB / "annotations.psv", sep="|", header=None, usecols=[0, 3, 12], names=["kind", "dive_id", "slate"])
    name = a[(a.kind == "slate") & a.slate.notna()].drop_duplicates("dive_id").set_index("dive_id").slate
    L = pd.read_csv(DB / "slate_label_points.psv", sep="|", header=None, names=["image_id", "dive_id", "camera_id", "pts", "skipped", "upside"])
    dots = pd.read_csv(DB / "slate_dots.psv", sep="|", header=None, names=["dive_id", "camera_id", "image_id", "pts", "x", "y", "taken"]).drop_duplicates("image_id").set_index("image_id")
    intr = {int(r.camera_id): np.array(json.loads(r.camera_matrix)) for r in pd.read_csv(REPO / "laser_detection_analysis/intrinsics.csv").itertuples()}
    rows = []
    for r in L.itertuples():
        nm = name.get(r.dive_id)
        if nm not in tpl or int(r.camera_id) not in intr or not isinstance(r.pts, str):
            continue
        obj = tpl[nm]
        skip = json.loads(r.skipped) if isinstance(r.skipped, str) and r.skipped not in ("null", "") else []
        keep = [i for i in range(len(obj)) if i not in (skip or [])]
        img = np.array(json.loads(r.pts), float)
        if len(img) != len(keep) or len(keep) < 4:
            continue
        o3 = np.c_[obj[keep], np.zeros(len(keep))]
        K = intr[int(r.camera_id)]
        ok, rv, tv = cv2.solvePnP(o3, img, K, None, flags=cv2.SOLVEPNP_IPPE)
        if not ok:
            continue
        R, _ = cv2.Rodrigues(rv)
        proj, _ = cv2.projectPoints(o3, rv, tv, K, None)
        rms = float(np.sqrt(((proj.reshape(-1, 2) - img) ** 2).sum(1).mean()))
        n = R[:, 2]
        centre = R @ o3.mean(0) + tv.ravel()
        row = dict(image_id=r.image_id, dive=r.dive_id, template=nm, points=len(keep), rms_px=rms,
                   cos_tilt=abs(float(n[2])), range_m=float(centre[2]))
        if r.image_id in dots.index and pd.notna(dots.loc[r.image_id, "x"]):
            ray = np.linalg.solve(K, [dots.loc[r.image_id, "x"], dots.loc[r.image_id, "y"], 1.0])
            row["dot_range_m"] = float((n @ centre) / (n @ ray) * ray[2])
        rows.append(row)
    return pd.DataFrame(rows)


def tilt(P):
    rows = []
    for dive, g in P.groupby("dive"):
        if len(g) < 5:
            continue
        x, y = np.log(g.range_m.to_numpy()), np.log(g.cos_tilt.to_numpy())
        slope = lambda i: np.polyfit(x[i], y[i], 1)[0]
        b = [slope(RNG.integers(0, len(x), len(x))) for _ in range(2000)]
        tl = np.degrees(np.arccos(g.cos_tilt))
        rows.append(dict(dive=dive, setting="pool" if dive in POOL else "field", frames=len(g), template=g.template.iloc[0],
                         rms_px_median=g.rms_px.median(), tilt_median_deg=tl.median(), tilt_p10=np.percentile(tl, 10),
                         tilt_p90=np.percentile(tl, 90), slope=slope(np.arange(len(x))), slope_lo=np.nanpercentile(b, 2.5),
                         slope_hi=np.nanpercentile(b, 97.5)))
    R = pd.DataFrame(rows)
    R.to_csv(OUT / "field_failure_tilt.csv", index=False)
    print("3 tilt: log cos(tilt) on log range, per dive with >= 5 posed labels")
    print(R.round(3).to_string(index=False))
    return R


def handling(cal, d, lines, P, trends):
    sam = pd.read_csv(REPO / "calibration_analysis/e1j_size_constancy/sizes/sam3_text.csv").set_index("image_id")["size"]
    pnp = P.dropna(subset=["dot_range_m"]).set_index("image_id").dot_range_m
    pr = pd.read_csv(DB / "slate_frame_predictions.psv", sep="|", header=None, names=["image_id", "dive_id", "px", "py", "conf", "at"]).set_index("image_id")
    field = d[~d.dive_id.isin(POOL) & d.image_id.isin(pr.index)]
    resid = []
    for dive, g in field.groupby("dive_id"):
        u = su.frame(dive, g, lines)
        auto = pr.loc[g.image_id, ["px", "py"]].to_numpy(float)
        resid += list((auto - g[["x", "y"]].to_numpy(float)) @ u)
    resid = np.array(resid)
    print(f"4 handling: reef along-line residuals (automatic - human) on {len(resid)} field slate frames, "
          f"{field.dive_id.nunique()} dives: median |r| {np.median(np.abs(resid)):.2f} px, p90 {np.percentile(np.abs(resid), 90):.1f}, max {np.abs(resid).max():.0f}; trend slopes {trends}")
    rows = []
    for dive in POOL:
        g = d[(d.dive_id == dive) & d.image_id.isin(sam.index) & d.image_id.isin(pnp.index)]
        if len(g) < su.MIN_FRAMES:
            continue
        u = su.frame(dive, g, lines)
        t0 = g[["x", "y"]].to_numpy(float) @ u
        s0 = sam.loc[g.image_id].to_numpy(float)
        Zp = pnp.loc[g.image_id].to_numpy(float)
        A = cal[dive]["A"]

        def err(t, s):
            tv, keep = fit_trimmed(t, s)
            return float(np.median(A / (t[keep] - tv) / Zp[keep]) - 1)

        rows.append(dict(dive=dive, condition="base", trial=0, frames=len(g), err=err(t0, s0)))
        noisy = [t0 + RNG.choice(resid, len(t0)) for _ in range(20)]
        for k, tn in enumerate(noisy):
            rows.append(dict(dive=dive, condition="A", trial=k, frames=len(g), err=err(tn, s0)))
        for label, slope in trends.items():
            sb = s0 * np.exp(0.5 * slope * np.log(Zp / np.median(Zp)))
            rows.append(dict(dive=dive, condition=f"B {label}", trial=0, frames=len(g), err=err(t0, sb)))
            for k, tn in enumerate(noisy):
                rows.append(dict(dive=dive, condition=f"A+B {label}", trial=k, frames=len(g), err=err(tn, sb)))
    R = pd.DataFrame(rows)
    R.to_csv(OUT / "field_failure_handling.csv", index=False)
    Q = R.groupby("condition", sort=False).err.agg(fits="size", median_abs=lambda e: 100 * e.abs().median(),
                                                   p90_abs=lambda e: 100 * e.abs().quantile(0.9), worst=lambda e: 100 * e.abs().max(),
                                                   signed_median=lambda e: 100 * e.median())
    print(f"   pool sessions {R.dive.nunique()}, frames {R[R.condition == 'base'].frames.sum()}")
    print(Q.round(2).to_string())
    return R


def main():
    cal = stored()
    offset(cal)
    d, lines = slate_frames(cal)
    predicted(cal, d)
    P = poses(cal)
    Tl = tilt(P)
    good = Tl[Tl.dive.isin(REEF_TREND) & (Tl.rms_px_median <= GOOD_POSE_PX)]
    trends = {f"measured {round(good.slope.mean(), 3)} ({'/'.join(map(str, good.dive))})": float(good.slope.mean()), "-0.07": -0.07}
    handling(cal, d, lines, P, trends)


if __name__ == "__main__":
    main()
