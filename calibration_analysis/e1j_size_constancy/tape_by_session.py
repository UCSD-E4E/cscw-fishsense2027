"""Each calibration scored against tape, per session (Fig 3b).

The stored "known-size" calibration is not ground truth: it assumes the slate matches its scanned
template and fits the laser offset per dive, so it inherits the slate's and the mount's
manufacturing tolerances. The independent truth is a tape-measured length. Each slate session
calibrates a paired dive of rigid fish models (e2e_measurement/score.py PAIR); with the human dot
and human head/tail held fixed, only the calibration varies:

  known size   stored production calibration (slate of known size + template, |O| fitted per dive)
  unknown size slate as an object of unknown size, human corner labels (slate_unknown.py) + |O| from design
  label-free   unknown size, image registration (register.py) + |O| from design

Per session: the per-fish production estimator (p90 over frames of one model in one dive),
signed error vs tape, averaged over the models in that dive. Writes tape_by_session.csv.
Run from this repo:  uv run python calibration_analysis/e1j_size_constancy/tape_by_session.py
"""
from __future__ import annotations

import json, sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "e2e_measurement")); sys.path.insert(0, str(HERE))
import score as S  # noqa: E402
import slate_unknown as su  # noqa: E402


def labelled_unknown(intr, cams):
    """Unknown-size fit from human corner labels, as a laser (origin, axis) per slate session."""
    d, lines, ext, _ = su.load()
    L = pd.read_csv(HERE / "labelfree_tv.csv").set_index("dive")
    out = {}
    for dive, g in d.groupby("dive_id"):
        if dive not in L.index:
            continue
        u = np.array([L.loc[dive, "ux"], L.loc[dive, "uy"]]); n = np.array([-u[1], u[0]])
        t = g[["x", "y"]].to_numpy(float) @ u
        tv = su.fit_tv(t, g["size"].to_numpy())
        K = intr[cams[int(dive)]]; v = tv * u + L.loc[dive, "line_offset"] * n
        axis = np.linalg.solve(K, [v[0], v[1], 1.0])
        o = np.array([u[0] / K[0, 0], u[1] / K[1, 1]]); o /= np.linalg.norm(o)
        out[int(dive)] = (np.append(S.O_DESIGN_M * o, 0.0), axis / np.linalg.norm(axis))
    return out


def main():
    stored, labelfree, intr = S.calibrations()
    E = pd.read_csv(REPO / "e2e_measurement/extrinsics.psv", sep="|")
    cams = {int(r.dive_id): int(r.camera_id) for r in E.itertuples()}
    cal = {"known size": stored, "unknown size (labelled)": labelled_unknown(intr, cams), "label-free": labelfree}
    F = pd.read_csv(REPO / "e2e_measurement/frames.psv", sep="|").drop_duplicates("image_id")
    F = F[F.content.fillna("").str.contains("Fish Model|Ruler")].dropna(subset=["head_x", "laser_x"]).copy()
    F["model"] = F.content.str.split(", ").str[-1]; F["L_true"] = F.model.map(S.KNOWN)
    rows = []
    for name, C in cal.items():
        for r in F.itertuples():
            session = S.PAIR[int(r.dive_id)]
            if session not in C:
                continue
            K = intr[int(r.camera_id)]; O, A = C[session]
            Z = S.depth(K, O, A, r.laser_x, r.laser_y)
            if Z > 0:
                rows.append(dict(cal=name, session=session, dive=int(r.dive_id), model=r.model,
                                 L=S.length(K, Z, r.head_x, r.head_y, r.tail_x, r.tail_y), L_true=r.L_true))
    D = pd.DataFrame(rows)
    fish = (D.groupby(["cal", "session", "dive", "model"])
              .apply(lambda t: S.p90(t.L) / t.L_true.iloc[0] - 1, include_groups=False).rename("err").reset_index())
    out = fish.groupby(["cal", "session"]).err.agg(mean_err="mean", mae=lambda e: e.abs().mean(), fish="size").reset_index()
    out.to_csv(HERE / "tape_by_session.csv", index=False)
    pd.set_option("display.width", 200)
    print(out.pivot(index="session", columns="cal", values="mae").round(4).to_string())
    print("\nmean |error| over sessions:", out.groupby("cal").mae.mean().round(4).to_dict())


if __name__ == "__main__":
    main()
