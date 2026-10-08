"""Task 3c: reef lengths with a size-constancy laser calibration, on every calibrated reef dive that allows it.

Extends calibration_analysis/e1j_size_constancy/reef_labelfree.py, which used only slate frames with
corner labels (4 dives). Here the slate frames are those the slate project labelled as slate
(2026-10-03_slate_detector data/manifest.csv), so dives without corner labels count too.

  dot    the human laser dot on the slate frame (data/db_extracts/laser_dots.psv). The deployed
         detector made no predictions on these slate frames, so no machine dot is available.
  size   sqrt(area) of the SAM 3.1 "white board" candidate chosen label-free: the highest-scoring
         candidate containing the dot (slate project data/masks/sam3/{id}.npz, 1600-px frame cache)
  fit    size constancy on the dive's laser line (reef_labelfree.calibrate), |O| = 104.0 mm stand-in

A dive is calibrated when it has >= 8 slate frames with a dot whose candidate contains the dot. Each
excluded dive is listed with its reason.

Lengths on the dive's human-measured reef frames, against the manual pipeline (human dot, human
head/tail, stored calibration), as in reef_labelfree.py: calibration only (human dot and head/tail)
and fully automatic (detector dot, SAM head/tail).

Writes analysis/codesign/results/reef_size_constancy_cal.csv, _summary.csv, _dives.csv.
Run: uv run python analysis/codesign/reef_size_constancy.py
"""
from __future__ import annotations

import sys

import numpy as np
import pandas as pd

from fishsense_cscw.paths import REPO

E1J = REPO / "calibration_analysis/e1j_size_constancy"
sys.path.insert(0, str(E1J)); sys.path.insert(0, str(REPO / "e2e_measurement")); sys.path.insert(0, str(REPO / "e2e_measurement/tail"))
import reef_labelfree as RL  # noqa: E402
import score as S  # noqa: E402
import evaluate as EV  # noqa: E402

SLATE = REPO.parent / "2026-10-03_slate_detector"
OUT = REPO / "analysis/codesign/results"
CACHE_W, PHOTO_W, MIN_FRAMES = 1600, 4014, 8


def size_under_dot(image_id: int, x: float, y: float) -> float:
    z = np.load(SLATE / "data/masks/sam3" / f"{image_id}.npz")
    n, h, w = z["shape"]
    if n == 0:
        return np.nan
    masks = np.unpackbits(z["masks"], axis=-1, count=w).astype(bool).reshape(n, h, w)
    xi, yi = int(round(x * CACHE_W / PHOTO_W)), int(round(y * CACHE_W / PHOTO_W))
    if not (0 <= xi < w and 0 <= yi < h):
        return np.nan
    hit = [k for k in range(n) if masks[k, yi, xi]]
    return float(np.sqrt(masks[max(hit, key=lambda k: z["scores"][k])].sum())) if hit else np.nan


def main():
    stored, _, intr = S.calibrations()
    E = pd.read_csv(REPO / "e2e_measurement/extrinsics.psv", sep="|")
    cams = {int(r.dive_id): int(r.camera_id) for r in E.itertuples()}
    F, K, dots = EV.load()
    reef = F[(F.set == "reef") & F.head_x.notna() & F.dive_id.isin(stored)]
    man = pd.read_csv(SLATE / "data/manifest.csv")
    L = pd.read_csv(REPO / "data/db_extracts/laser_dots.psv", sep="|", header=None, names=["image_id", "x", "y", "label"]).set_index("image_id")
    lines = pd.read_csv(REPO / "data/db_extracts/lines.psv", sep="|", header=None, names=["dive_id", "a", "b", "c", "n", "resid"]).set_index("dive_id")
    rows, status = [], []
    for dive in sorted(reef.dive_id.unique()):
        sf = man[(man.dive_id == dive) & (man.label == 1)].image_id
        withdot = [i for i in sf if i in L.index]
        fr = [dict(image_id=int(i), dive_id=int(dive), x=L.loc[i, "x"], y=L.loc[i, "y"], size=size_under_dot(i, L.loc[i, "x"], L.loc[i, "y"]))
              for i in withdot]
        fr = pd.DataFrame(fr).dropna(subset=["size"]) if fr else pd.DataFrame(columns=["image_id", "dive_id", "x", "y", "size"])
        reason = ("no dive laser line" if dive not in lines.index else
                  f"{len(fr)} slate frames with a dot and a mask under it (< {MIN_FRAMES})" if len(fr) < MIN_FRAMES else "calibrated")
        status.append(dict(dive_id=int(dive), reef_frames=int((reef.dive_id == dive).sum()), slate_frames=len(sf),
                           slate_frames_with_dot=len(withdot), usable=len(fr), status=reason))
        if reason == "calibrated":
            rows.append(fr)
    fr = pd.concat(rows, ignore_index=True)
    cal, C, _ = RL.calibrate(intr, cams, fr, "SAM 3.1 under the dot (slate-project frames)")
    Kx = K.set_index(["image_id", "seed"])
    out = []
    for r in reef[reef.dive_id.isin(cal)].itertuples():
        Kc = intr[int(r.camera_id)]; cs, cl = stored[int(r.dive_id)], cal[int(r.dive_id)]
        hh = (r.head_x, r.head_y, r.tail_x, r.tail_y)
        rec = dict(image_id=r.image_id, dive=int(r.dive_id))
        for name, c in (("stored", cs), ("sc", cl)):
            rec[f"L_manual_{name}"] = S.length(Kc, S.depth(Kc, c[0], c[1], r.laser_x, r.laser_y), *hh)
        k = Kx.loc[(r.image_id, "auto")] if (r.image_id, "auto") in Kx.index else None
        if k is not None and r.image_id in dots and not pd.isna(k.get("head_x")):
            ah = (k.head_x, k.head_y, *EV.tail_of(k, "prod"))
            for name, c in (("stored", cs), ("sc", cl)):
                rec[f"L_auto_{name}"] = S.length(Kc, S.depth(Kc, c[0], c[1], *dots[r.image_id]), *ah)
        out.append(rec)
    Ln = pd.DataFrame(out); ref = Ln.L_manual_stored
    summ = []
    for name, rel in (("calibration only: size constancy (human dot + head/tail)", Ln.L_manual_sc / ref - 1),
                      ("fully automatic, stored calibration", Ln.L_auto_stored / ref - 1),
                      ("fully automatic, size-constancy calibration", Ln.L_auto_sc / ref - 1)):
        for dive, r in [("all", rel)] + [(d, rel[Ln.dive == d]) for d in sorted(cal)]:
            r = r.dropna()
            if len(r):
                summ.append(dict(variant=name, dive=dive, frames=len(r), median=r.median(), mae=r.abs().mean(), within10=(r.abs() <= .10).mean()))
    OUT.mkdir(parents=True, exist_ok=True)
    C.to_csv(OUT / "reef_size_constancy_cal.csv", index=False, float_format="%.4f")
    pd.DataFrame(summ).to_csv(OUT / "reef_size_constancy_summary.csv", index=False, float_format="%.4f")
    pd.DataFrame(status).to_csv(OUT / "reef_size_constancy_dives.csv", index=False)
    pd.set_option("display.width", 220)
    print(pd.DataFrame(status).to_string(index=False)); print()
    print(C[["dive", "frames", "size_ratio", "tv_err_px", "angle_vs_stored_deg", "stored_O_mm"]].round(3).to_string(index=False)); print()
    S_ = pd.DataFrame(summ); print(S_[S_.dive == "all"].round(3).to_string(index=False)); print(S_[S_.dive != "all"].round(3).to_string(index=False))


if __name__ == "__main__":
    main()
