"""Known issue 1: reef lengths with the label-free calibration instead of the stored one.

The reef comparison (e2e_measurement/tail/evaluate.py, Fig 5) used each dive's stored calibration,
which came from human slate-corner labels on a slate of known size. Here the four reef dives with
at least 8 slate frames carrying a human dot (341, 347, 349, 436) are calibrated label-free:

  size     SAM 3.1 text-prompted mask under the dot, sqrt(area) (sam_sizes.py, reef_sizes/sam3_text.csv;
           every frame used the "white board" prompt)
  angle    size constancy on the dive's own line (slate_unknown.fit_tv): the vanishing point is where
           apparent size would reach zero along the line
  offset   |O| = 0.104 m stand-in for the mount design, oriented along the line (as score.calibrations)

For comparison, the same fit with the human corner labels as the size (an object of unknown size,
slate_unknown.load: complete labels only, 6 points on the V-slate) on the dives with >= 8 such frames.

The dot is still the human click on the slate frames (as in the pool test, tape_by_session.py), so
the slate's corners are the only labels removed.

Outputs, against the manual pipeline (human dot, human head/tail, stored calibration):
  calibration only   human dot + human head/tail, label-free calibration
  angle only         as "calibration only", but with the dive's stored |O| magnitude: separates the
                     label-free angle from the |O| stand-in
  fully automatic    automatic dot + automatic head/tail (production rule), stored and label-free
There is no tape on the reef, so this measures agreement with the manual pipeline, not truth; the
stored calibration was itself fit to these slate frames with their corner labels.

Writes reef_labelfree_cal.csv (per dive) and reef_labelfree_lengths.csv (per frame).
Run from this repo:  uv run python calibration_analysis/e1j_size_constancy/reef_labelfree.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "e2e_measurement")); sys.path.insert(0, str(REPO / "e2e_measurement/tail")); sys.path.insert(0, str(HERE))
import score as S  # noqa: E402
import evaluate as EV  # noqa: E402
import slate_unknown as su  # noqa: E402

DIVES = (341, 347, 349, 436)
N_BOOT = 500


def sam_frames():
    fr = pd.read_csv(HERE / "reef_sizes_frames.csv").rename(columns={"dot_x": "x", "dot_y": "y"})
    sz = pd.read_csv(HERE / "reef_sizes/sam3_text.csv").set_index("image_id")["size"]
    return fr[fr.image_id.isin(sz.index)].assign(size=lambda t: t.image_id.map(sz))


def corner_frames():
    """Human corner labels as an object of unknown size (slate_unknown.load: complete labels only)."""
    d, *_ = su.load()
    d = d[d.dive_id.isin(DIVES)][["image_id", "dive_id", "x", "y", "size"]]
    return d[d.groupby("dive_id").image_id.transform("size") >= su.MIN_FRAMES]


def calibrate(intr, cams, fr, source):
    lines = pd.read_csv(REPO / "data/db_extracts/lines.psv", sep="|", header=None,
                        names=["dive_id", "a", "b", "c", "n", "resid"]).set_index("dive_id")
    stored, _, _ = S.calibrations()
    rng = np.random.default_rng(0)
    cal, rows = {}, []
    for dive in sorted(fr.dive_id.unique()):
        g = fr[fr.dive_id == dive]
        u = su.frame(dive, g, lines); n = np.array([-u[1], u[0]])
        a, b, c = lines.loc[dive, ["a", "b", "c"]]
        offset = float(np.array([a, b]) * -c / (a * a + b * b) @ n)          # the dive line, in (u, n) coordinates
        t = g[["x", "y"]].to_numpy(float) @ u; s = g["size"].to_numpy()
        tv = su.fit_tv(t, s)
        boots = [su.fit_tv(t[i], s[i]) for i in (rng.integers(0, len(t), len(t)) for _ in range(N_BOOT))]
        K = intr[cams[dive]]
        v = tv * u + offset * n
        axis = np.linalg.solve(K, [v[0], v[1], 1.0]); axis /= np.linalg.norm(axis)
        o = np.array([u[0] / K[0, 0], u[1] / K[1, 1]]); o /= np.linalg.norm(o)
        cal[dive] = (np.append(S.O_DESIGN_M * o, 0.0), axis)
        sa = stored[dive][1] / np.linalg.norm(stored[dive][1])
        vs = K @ sa; vs = vs[:2] / vs[2]
        deg = lambda tt: float(np.degrees(np.arccos(np.clip(
            (lambda ax: ax / np.linalg.norm(ax))(np.linalg.solve(K, [*(tt * u + offset * n), 1.0])) @ sa, -1, 1))))
        rows.append(dict(source=source, dive=dive, camera=cams[dive], frames=len(g), size_ratio=float(s.max() / s.min()),
                         tv_fit=tv, tv_stored=float(vs @ u), tv_err_px=float(tv - vs @ u), tv_se_px=float(np.std(boots)),
                         angle_vs_stored_deg=deg(tv),
                         angle_ci_deg=tuple(np.round(np.percentile([deg(x) for x in boots], [2.5, 97.5]), 3)),
                         stored_O_mm=float(np.linalg.norm(stored[dive][0]) * 1000)))
    return cal, pd.DataFrame(rows), stored


def main():
    stored_all, _, intr = S.calibrations()
    E = pd.read_csv(REPO / "e2e_measurement/extrinsics.psv", sep="|")
    cams = {int(r.dive_id): int(r.camera_id) for r in E.itertuples()}
    cal, C1, stored = calibrate(intr, cams, sam_frames(), "SAM 3.1 mask")
    calh, C2, _ = calibrate(intr, cams, corner_frames(), "human corners")
    C = pd.concat([C1, C2], ignore_index=True)
    F, K, dots = EV.load()
    Kx = K.set_index(["image_id", "seed"])
    reef = F[(F.set == "reef") & F.dive_id.isin(DIVES)]
    rows = []
    for r in reef.itertuples():
        Kc = intr[int(r.camera_id)]
        rec = dict(image_id=r.image_id, dive=r.dive_id, green=str(r.laser_label).startswith("Green"))
        hh = (r.head_x, r.head_y, r.tail_x, r.tail_y)
        auto = Kx.loc[(r.image_id, "auto")] if (r.image_id, "auto") in Kx.index else None
        ah = None if auto is None or pd.isna(auto.get("head_x")) else (auto.head_x, auto.head_y, *EV.tail_of(auto, "prod"))
        cs, cl = stored[int(r.dive_id)], cal[int(r.dive_id)]
        angle_only = (cl[0] / np.linalg.norm(cl[0]) * np.linalg.norm(cs[0]), cl[1])
        Ca = S.depth(Kc, angle_only[0], angle_only[1], r.laser_x, r.laser_y)
        rec["L_manual_angleonly"] = S.length(Kc, Ca, *hh)
        for name, c in (("stored", cs), ("labelfree", cl)):
            rec[f"L_manual_{name}"] = S.length(Kc, S.depth(Kc, c[0], c[1], r.laser_x, r.laser_y), *hh)
            if ah is not None and r.image_id in dots:
                rec[f"L_auto_{name}"] = S.length(Kc, S.depth(Kc, c[0], c[1], *dots[r.image_id]), *ah)
        if int(r.dive_id) in calh:
            ch = calh[int(r.dive_id)]
            rec["L_manual_corners"] = S.length(Kc, S.depth(Kc, ch[0], ch[1], r.laser_x, r.laser_y), *hh)
        rows.append(rec)
    L = pd.DataFrame(rows)
    ref = L.L_manual_stored
    variants = {"angle only (label-free angle, stored |O|)": L.L_manual_angleonly / ref - 1,
                "calibration only (human dot + head/tail, label-free cal)": L.L_manual_labelfree / ref - 1,
                "calibration only, human corners (unknown size; dives with >= 8 complete labels)": L.get("L_manual_corners") / ref - 1,
                "fully automatic, stored cal (Fig 5)": L.get("L_auto_stored") / ref - 1,
                "fully automatic, label-free cal": L.get("L_auto_labelfree") / ref - 1}
    S_ = []
    for name, rel in variants.items():
        for dive, r in [("all", rel)] + [(d, rel[L.dive == d]) for d in DIVES]:
            r = r.dropna()
            if len(r):
                S_.append(dict(variant=name, dive=dive, frames=len(r), median=r.median(), mae=r.abs().mean(),
                               within10=(r.abs() <= .10).mean()))
    S_ = pd.DataFrame(S_)
    C.to_csv(HERE / "reef_labelfree_cal.csv", index=False, float_format="%.4f")
    L.to_csv(HERE / "reef_labelfree_lengths.csv", index=False, float_format="%.5f")
    S_.to_csv(HERE / "reef_labelfree_summary.csv", index=False, float_format="%.4f")
    pd.set_option("display.width", 220)
    print(C.round(3).to_string(index=False)); print(); print(S_.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
