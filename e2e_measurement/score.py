"""E2 pass 2: lengths from every combination of human/automatic inputs, scored against tape.

Stages, each either human or automatic:
  dot         human LaserLabel            | laser detector (dots.jsonl)
  head/tail   human HeadTailLabel         | SAM3 + keypointer seeded by the human dot (ht_humandot)
                                          | ... seeded by the automatic dot (ht_auto; the e2e path)
  calibration stored slate calibration    | label-free unknown-size fit (E1j) + |O| from the mount
              (production's own pairing:    design (fleet median 104.0 mm stands in until the CAD
               fish dive <- slate session)  value arrives); the size measure is image registration
                                            (D, F) or SAM 3 mask area (D2, F2)

Geometry is production's (laser_geometry.py): the dot's depth is the closest point between
the camera ray and the laser ray; head and tail are back-projected onto the plane at that
depth. Truth: fishmodelreference.known_length_m (tape). Per frame: signed error L/L_true - 1.
Per (dive, model): production's p90 estimator (fish_length_estimate).

Run from this repo:  uv run python score.py
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
O_DESIGN_M = 0.104   # stand-in for the mount CAD value (fleet median of 31 stored calibrations)
PAIR = {58: 71, 59: 77, 60: 65, 61: 80, 66: 83, 76: 63, 84: 62, 87: 87, 94: 94, 114: 114}
KNOWN = {"Snook": 0.455, "Grouper": 0.36, "Shark": 0.605, "Purple Angel": 0.192, "Ruler": 0.3429}


def jsonl(name):
    latest = {}
    p = HERE / name
    if p.exists():
        for l in p.open():
            r = json.loads(l)
            if "error" not in r:
                latest[r["image_id"]] = r
    return latest


def depth(K, O, a, x, y):
    """Depth (Z) of the laser point closest to the camera ray through pixel (x, y)."""
    d = np.linalg.solve(K, [x, y, 1.0]); a = a / np.linalg.norm(a)
    # minimise |s d - (O + t a)|: 2x2 normal equations
    A = np.array([[d @ d, -d @ a], [d @ a, -a @ a]]); b = np.array([d @ O, a @ O])
    s, t = np.linalg.solve(A, b)
    return float((O + t * a)[2])


def length(K, Z, hx, hy, tx, ty):
    Ki = np.linalg.inv(K)
    return float(np.linalg.norm(Ki @ [hx, hy, 1.0] * Z - Ki @ [tx, ty, 1.0] * Z))


def calibrations(labelfree_file: str = "labelfree_tv.csv"):
    """(stored, label-free, intrinsics). labelfree_file picks the label-free fit: labelfree_tv.csv
    (image registration, register.py) or labelfree_sam3_tv.csv (SAM 3 mask area,
    analysis/codesign/size_constancy_sam.py)."""
    E = pd.read_csv(HERE / "extrinsics.psv", sep="|")
    stored = {int(r.dive_id): (np.array(json.loads(r.laser_position)), np.array(json.loads(r.laser_axis))) for r in E.itertuples()}
    intr = {int(r.camera_id): np.array(json.loads(r.camera_matrix)) for r in pd.read_csv(REPO / "laser_detection_analysis/intrinsics.csv").itertuples()}
    cams = {int(r.dive_id): int(r.camera_id) for r in E.itertuples()}
    L = pd.read_csv(REPO / "calibration_analysis/e1j_size_constancy" / labelfree_file)
    labelfree = {}
    for r in L.itertuples():
        K = intr[cams[int(r.dive)]]; u = np.array([r.ux, r.uy]); n = np.array([-u[1], u[0]])
        v = r.tv_fit * u + r.line_offset * n
        axis = np.linalg.solve(K, [v[0], v[1], 1.0])
        o = np.array([u[0] / K[0, 0], u[1] / K[1, 1]]); o = o / np.linalg.norm(o)
        labelfree[int(r.dive)] = (np.append(O_DESIGN_M * o, 0.0), axis / np.linalg.norm(axis))
    return stored, labelfree, intr


def build():
    F = pd.read_csv(HERE / "frames.psv", sep="|").drop_duplicates("image_id")
    F = F[F.content.fillna("").str.contains("Fish Model|Ruler")].copy()
    F["model"] = F.content.str.split(", ").str[-1]
    F["L_true"] = F.model.map(KNOWN)
    dots, ht = jsonl("dots.jsonl"), jsonl("headtail.jsonl")
    stored, labelfree, intr = calibrations()
    _, sam3, _ = calibrations("labelfree_sam3_tv.csv")
    rows = []
    for r in F.itertuples():
        K = intr[int(r.camera_id)]; cal_dive = PAIR[int(r.dive_id)]
        dot_auto = dots.get(r.image_id, {}).get("dot") or {}
        h = ht.get(r.image_id, {})
        DOT = {"human": (r.laser_x, r.laser_y), "auto": (dot_auto.get("x"), dot_auto.get("y"))}
        HT = {"human": (r.head_x, r.head_y, r.tail_x, r.tail_y)}
        for k, key in (("auto_humandot", "ht_humandot"), ("auto", "ht_auto")):
            e = h.get(key) or {}
            HT[k] = (e.get("head_x"), e.get("head_y"), e.get("tail_x"), e.get("tail_y")) if e.get("status") == "predicted" else (None,) * 4
        CAL = {"stored": stored.get(cal_dive), "labelfree": labelfree.get(cal_dive), "sam3": sam3.get(cal_dive)}
        for name, dk, hk, ck in LADDER:
            x, y = DOT[dk]; hh = HT[hk]; cal = CAL[ck]
            L = np.nan
            if cal is not None and x is not None and np.isfinite(x) and all(q is not None and np.isfinite(q) for q in hh):
                Z = depth(K, cal[0], cal[1], x, y)
                if Z > 0:
                    L = length(K, Z, *hh)
            rows.append(dict(image_id=r.image_id, dive=int(r.dive_id), model=r.model, L_true=r.L_true, config=name,
                             dot_err_px=float(np.hypot(DOT["auto"][0] - r.laser_x, DOT["auto"][1] - r.laser_y)) if DOT["auto"][0] is not None else np.nan,
                             L=L, err=L / r.L_true - 1 if np.isfinite(L) else np.nan))
    return pd.DataFrame(rows)


LADDER = [  # name, dot, head/tail, calibration
    ("A manual (production today)", "human", "human", "stored"),
    ("B auto dot", "auto", "human", "stored"),
    ("C auto head/tail", "human", "auto_humandot", "stored"),
    ("D label-free calibration", "human", "human", "labelfree"),
    ("E auto dot + head/tail", "auto", "auto", "stored"),
    ("F end-to-end automatic", "auto", "auto", "labelfree"),
    # the label-free laser calibration from SAM 3 mask area (the machine path); D and F above use image registration
    ("D2 label-free laser calibration (SAM 3)", "human", "human", "sam3"),
    ("F2 end-to-end automatic (SAM 3)", "auto", "auto", "sam3"),
]


def p90(s):
    s = np.sort(s.dropna().to_numpy())
    return s[min(len(s) - 1, int(np.ceil(0.9 * len(s))) - 1)] if len(s) else np.nan


if __name__ == "__main__":
    D = build()
    pd.set_option("display.width", 220)
    n_frames = D.image_id.nunique()
    print(f"{n_frames} frames, {D.dive.nunique()} dives; dots for {D[D.config.str.startswith('B')].dot_err_px.notna().sum()}")
    out = []
    for name, g in D.groupby("config", sort=False):
        ok = g.dropna(subset=["err"])
        if ok.empty:
            out.append(dict(config=name, coverage=0.0, n=0)); continue
        est = pd.Series({k: p90(t.L) / t.L_true.iloc[0] - 1 for k, t in ok.groupby(["dive", "model"])})
        out.append(dict(config=name, coverage=len(ok) / len(g), n=len(ok), median_err=ok.err.median(), mae=ok.err.abs().mean(),
                        p90_abs=ok.err.abs().quantile(.9), fish_p90_mae=est.abs().mean(), fish_p90_median=est.median(), fish_n=len(est)))
    R = pd.DataFrame(out)
    print(R.round(4).to_string(index=False))
    D.to_csv(HERE / "lengths.csv", index=False)
