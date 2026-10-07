"""Task 3c: how much range spread does label-free size constancy need?

The 10 pool slate sessions (calibration_analysis/e1j_size_constancy: sizes_frames.csv, human dot; size
from the SAM 3.1 text-prompted mask, sizes/sam3_text.csv). Each session is subsampled to random
subsets of m frames (m = 3 .. all), and each subset is fitted as in slate_unknown.fit_tv on the
session's own dot line (labelfree_tv.csv). Spread = largest / smallest apparent size in the subset.

Angle error, two references:
  self     the session's fit on all its frames: what spread alone costs, with no outside truth
  stored   the stored known-size calibration's axis (production; not ground truth: it fits |O| per
           dive and assumes the slate matches its template)

The design target is 0.05 deg (about 2.5 px at the vanishing point). Subsets are drawn per session
(400 per m), so sessions weigh equally; spread bins pool all sessions.

Small spreads come mostly from small subsets, so the bins are also reported for m >= 8 frames.
Writes analysis/codesign/results/calibration_spread.csv (per subset) and calibration_spread_bins.csv.
Run: uv run python analysis/codesign/calibration_spread.py
"""
from __future__ import annotations

import json, sys

import numpy as np
import pandas as pd

from fishsense_cscw.paths import REPO

E1J = REPO / "calibration_analysis/e1j_size_constancy"
sys.path.insert(0, str(E1J)); sys.path.insert(0, str(REPO / "e2e_measurement"))
import slate_unknown as su  # noqa: E402
import score as S  # noqa: E402

OUT = REPO / "analysis/codesign/results"
DRAWS, M_MIN, TARGET = 400, 3, 0.05
BINS = [1.0, 1.1, 1.2, 1.3, 1.5, 1.75, 2.0, 2.5, 3.5]


def axis_of(tv, u, offset, K):
    v = tv * u + offset * np.array([-u[1], u[0]])
    a = np.linalg.solve(K, [v[0], v[1], 1.0]); return a / np.linalg.norm(a)


def angle(a, b):
    return float(np.degrees(np.arccos(np.clip(a @ b, -1, 1))))


def main():
    fr = pd.read_csv(E1J / "sizes_frames.csv")
    sz = pd.read_csv(E1J / "sizes/sam3_text.csv").set_index("image_id")["size"]
    fr = fr[fr.image_id.isin(sz.index)].assign(size=lambda t: t.image_id.map(sz))
    L = pd.read_csv(E1J / "labelfree_tv.csv").set_index("dive")
    stored, _, intr = S.calibrations()
    cams = {int(r.dive_id): int(r.camera_id) for r in pd.read_csv(REPO / "e2e_measurement/extrinsics.psv", sep="|").itertuples()}
    rng = np.random.default_rng(0)
    rows = []
    for dive, g in fr.groupby("dive_id"):
        u = np.array([L.loc[dive, "ux"], L.loc[dive, "uy"]]); off = L.loc[dive, "line_offset"]; K = intr[cams[dive]]
        t = g[["dot_x", "dot_y"]].to_numpy(float) @ u; s = g["size"].to_numpy()
        a_self = axis_of(su.fit_tv(t, s), u, off, K)
        a_stored = stored[dive][1] / np.linalg.norm(stored[dive][1])
        for m in range(M_MIN, len(t) + 1):
            for _ in range(DRAWS if m < len(t) else 1):
                i = rng.choice(len(t), m, replace=False)
                a = axis_of(su.fit_tv(t[i], s[i]), u, off, K)
                rows.append(dict(dive=dive, m=m, spread=s[i].max() / s[i].min(),
                                 err_self_deg=angle(a, a_self), err_stored_deg=angle(a, a_stored)))
    R = pd.DataFrame(rows)
    R["bin"] = pd.cut(R.spread, BINS)
    B = pd.concat([bins(R).assign(frames="all m"), bins(R[R.m >= 8]).assign(frames="m >= 8")], ignore_index=True)
    OUT.mkdir(parents=True, exist_ok=True)
    R.drop(columns="bin").to_csv(OUT / "calibration_spread.csv", index=False, float_format="%.5f")
    B.to_csv(OUT / "calibration_spread_bins.csv", index=False, float_format="%.4f")
    pd.set_option("display.width", 200)
    print(f"{len(R):,} subsets over {R.dive.nunique()} sessions")
    print(B.round(3).to_string(index=False))


def bins(R):
    """Per spread bin. Small spreads mostly come from small subsets, so m >= 8 is reported too."""
    B = (R.groupby("bin", observed=True)
           .agg(subsets=("spread", "size"), sessions=("dive", "nunique"),
                self_median=("err_self_deg", "median"), self_p90=("err_self_deg", lambda x: x.quantile(.9)),
                self_within_target=("err_self_deg", lambda x: (x <= TARGET).mean()),
                stored_median=("err_stored_deg", "median"), stored_p90=("err_stored_deg", lambda x: x.quantile(.9)),
                stored_within_target=("err_stored_deg", lambda x: (x <= TARGET).mean()))
           .reset_index())
    B["bin"] = B["bin"].astype(str)
    return B

if __name__ == "__main__":
    main()
