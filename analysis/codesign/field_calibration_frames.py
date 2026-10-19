"""Why do four of the seven field laser calibrations rest on two or three slate frames?

The seven field deployments of the FishSense Lite IMWUT field cohort (dives 279, 341, 347, 349, 383,
465, 471) each use their own dive's stored laser calibration. For each:

1. Slate frames captured vs used in the fit.
   - captured: any record calls the frame a slate - the slate-frame detector (2026-10-03_slate_detector:
     labelled manifest, its dive-grouped out-of-fold predictions at p >= 0.5, or its scan), a
     slate-corner label, or a labeller's species answer starting "Slate".
   - used: production's own stage-13 steps on the records production reads (non-superseded slate and laser
     labels, as label_controller returns them; none was edited after these fits were made), called here, not re-implemented
     (fishsense-lite perform_laser_calibration_activity.py): a slate-corner label, a laser label with
     coordinates, a point count equal to the template's minus skipped points, a PnP pose and a
     dot-on-plane intersection, and survival of trim_outlying_observations. The refit
     (fishsense_core.laser.calibrate_laser) is compared with the stored calibration to show the frame
     set is the one production used.
2. Why each unused frame was excluded: the FIRST stage-13 step it fails, plus the labeller's recorded
   species answer (e.g. "Slate, Laser not on slate") where one exists. Reasons not in the records
   (occlusion, blur, angle) are not inferred.
3. Size constancy with SAM 3.1 on every slate frame with a laser dot, used or not, twice: live human dots
   only, and live plus superseded dots (a dot labelled and later superseded; flagged, since the record
   does not say why it was superseded): apparent size =
   sqrt(area) of the slate project's "white board" candidate under the dot (label-free choice); fit on
   the dive's laser line (reef_labelfree.calibrate). Reported: frames usable (a mask under the dot),
   size spread, range span of those frames along the stored laser ray against the 0.6 m requirement
   (IMWUT s5.3), and the fitted laser angle against the stored calibration. Stored calibrations are
   not changed.

Data: data/db_extracts/field_calibration_frames.psv (sql/extract_field_calibration_frames.sql), the slate
project's manifest, OOF predictions, scan and SAM masks, laser_detection_analysis/intrinsics.csv,
e2e_measurement/extrinsics.psv.
Writes analysis/codesign/results/field_calibration_frames.csv (per frame) and _summary.csv (per dive).
Run from fishsense-lite's venv (production code):
  ../fishsense-lite/.venv/bin/python analysis/codesign/field_calibration_frames.py
"""
from __future__ import annotations

import json, sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SLATE = REPO.parent / "2026-10-03_slate_detector"
OUT = HERE / "results"
DIVES = (279, 341, 347, 349, 383, 465, 471)
INCH_TO_M, CACHE_W, PHOTO_W, MIN_SPAN_M, MIN_SC_FRAMES = 0.0254, 1600, 4014, 0.6, 8
COLS = ("image_id dive_id taken species slate_label_id slate_completed slate_points slate_skipped slate_upside_down "
        "slate_id template_points slate_dpi laser_x laser_y laser_label laser_superseded slate_updated laser_updated "
        "superseded_x superseded_y").split()


def j(x):
    return json.loads(x) if isinstance(x, str) and x not in ("", "null") else None


def stage13_point(r, K):
    """Production's per-frame lift, step by step; returns (point or None, failing step)."""
    from fishsense_data_processing_workflow_worker.activities.perform_laser_calibration_activity import _drop_skipped
    from fishsense_data_processing_workflow_worker.calibration_geometry import laser_point_on_plane, plane_from_correspondences
    if pd.isna(r.slate_label_id):
        return None, "no slate-corner label"
    if pd.isna(r.laser_x) or pd.isna(r.laser_y):
        if pd.notna(r.superseded_x):
            return None, "laser dot superseded"            # a dot was labelled, then superseded (validator or relabel)
        return None, "no laser dot (no-dot answer)" if isinstance(r.laser_label, str) or pd.notna(r.laser_superseded) else "no laser label"
    src = _drop_skipped(list(j(r.template_points) or []), j(r.slate_skipped) or [])
    img = list(j(r.slate_points) or [])
    if len(img) != len(src):
        return None, "corner count != template minus skipped"
    body = (np.array(src, float) / float(r.slate_dpi)) * INCH_TO_M
    plane = plane_from_correspondences(body, np.array(img, float), K)
    if plane is None:
        return None, "no PnP pose"
    p = laser_point_on_plane(plane, np.array([r.laser_x, r.laser_y], float), K)
    return (None, "dot ray misses the slate plane") if p is None else (np.asarray(p, float), "ok")


def ray_range(K, O, a, x, y):
    """Range (m) of the dot along the stored laser ray: the ray point closest to the camera ray through (x, y)."""
    d = np.linalg.solve(K, [x, y, 1.0]); a = a / np.linalg.norm(a)
    A = np.array([[d @ d, -d @ a], [d @ a, -a @ a]]); b = np.array([d @ O, a @ O])
    s, t = np.linalg.solve(A, b)
    return float(np.linalg.norm(O + t * a))


def sam_size(image_id, x, y):
    p = SLATE / "data/masks/sam3" / f"{int(image_id)}.npz"
    if not p.exists():
        return np.nan, "no SAM masks for this frame"
    z = np.load(p); n, h, w = z["shape"]
    if n == 0:
        return np.nan, "SAM found no board"
    m = np.unpackbits(z["masks"], axis=-1, count=w).astype(bool).reshape(n, h, w)
    xi, yi = int(round(x * CACHE_W / PHOTO_W)), int(round(y * CACHE_W / PHOTO_W))
    hit = [k for k in range(n) if 0 <= xi < w and 0 <= yi < h and m[k, yi, xi]]
    if not hit:
        return np.nan, "dot not on any SAM board mask"
    return float(np.sqrt(m[max(hit, key=lambda k: z["scores"][k])].sum())), "ok"


def main():
    sys.path.insert(0, str(REPO / "calibration_analysis/e1j_size_constancy")); sys.path.insert(0, str(REPO / "e2e_measurement"))
    import reef_labelfree as RL
    import score as S
    from fishsense_core.laser import calibrate_laser
    from fishsense_data_processing_workflow_worker.robust_laser_fit import trim_outlying_observations
    F = pd.read_csv(REPO / "data/db_extracts/field_calibration_frames.psv", sep="|", header=None, names=COLS)
    stored, _, intr = S.calibrations()
    cams = {int(r.dive_id): int(r.camera_id) for r in pd.read_csv(REPO / "e2e_measurement/extrinsics.psv", sep="|").itertuples()}
    man = pd.read_csv(SLATE / "data/manifest.csv"); oof = pd.read_csv(REPO / "data/slate_detector/oof_cv_q1.csv")
    scan = pd.read_csv(SLATE / "runs/scan/predictions.csv")
    det = set(man[man.label == 1].image_id) | set(oof[oof.p_slate >= 0.5].image_id) | set(scan[scan.flag == "likely_slate"].image_id)
    F["detector_slate"] = F.image_id.isin(det)
    F["species_slate"] = F.species.fillna("").str.startswith("Slate")
    F = F[F.detector_slate | F.species_slate | F.slate_label_id.notna()].copy()
    rows, summ, sc_frames = [], [], {}
    for dive, g in F.groupby("dive_id"):
        K = intr[cams[dive]]; O, a = stored[dive]
        pts, ids = [], []
        for r in g.itertuples():
            p, step = stage13_point(r, K)
            rows.append(dict(image_id=r.image_id, dive_id=dive, taken=r.taken, detector_slate=r.detector_slate,
                             species_answer=r.species if isinstance(r.species, str) else "", stage13=step,
                             has_dot=pd.notna(r.laser_x), laser_x=r.laser_x, laser_y=r.laser_y))
            if p is not None:
                pts.append(p); ids.append(r.image_id)
        P = np.array(pts)
        kept = trim_outlying_observations(P) if len(P) else P
        used = [i for i, p in zip(ids, P) if any(np.allclose(p, q) for q in kept)]
        refit_deg = np.nan
        if len(kept) >= 2:
            _, ax = calibrate_laser(kept.astype(np.float32))
            ax = np.asarray(ax, float); refit_deg = float(np.degrees(np.arccos(np.clip(abs(ax @ a / np.linalg.norm(a) / np.linalg.norm(ax)), -1, 1))))
        for rr in rows:
            if rr["dive_id"] == dive and rr["stage13"] == "ok":
                rr["stage13"] = "used in the fit" if rr["image_id"] in used else "trimmed as an outlier"
        span_used = (lambda r: max(r) - min(r) if len(r) > 1 else 0.0)([float(np.linalg.norm(p)) for p in kept])
        # size constancy on every slate frame with a dot: live human dots, then live + superseded dots
        for rr in rows:
            if rr["dive_id"] != dive:
                continue
            src = g.set_index("image_id").loc[rr["image_id"]]
            rr["dot_source"] = "live" if rr["has_dot"] else ("superseded" if pd.notna(src.superseded_x) else "")
            if rr["dot_source"] == "superseded":
                rr["laser_x"], rr["laser_y"] = float(src.superseded_x), float(src.superseded_y)
            if rr["dot_source"]:
                size, why = sam_size(rr["image_id"], rr["laser_x"], rr["laser_y"])
                rr["sam_size"], rr["sam"] = size, why
                rr["range_on_stored_ray_m"] = ray_range(K, O, a, rr["laser_x"], rr["laser_y"])
        rec = dict(dive_id=dive, slate_frames=len(g), detector_slate=int(g.detector_slate.sum()), with_live_dot=int(g.laser_x.notna().sum()),
                   with_superseded_dot=int((g.laser_x.isna() & g.superseded_x.notna()).sum()),
                   used_in_fit=len(used), trimmed=len(pts) - len(used), range_span_used_m=span_used, refit_vs_stored_deg=refit_deg)
        for tag, srcs in (("live", ("live",)), ("all", ("live", "superseded"))):
            sc = pd.DataFrame([dict(image_id=rr["image_id"], dive_id=dive, x=rr["laser_x"], y=rr["laser_y"], size=rr["sam_size"],
                                    rng=rr["range_on_stored_ray_m"]) for rr in rows
                               if rr["dive_id"] == dive and rr.get("dot_source") in srcs and rr.get("sam") == "ok"])
            rec[f"sc_{tag}_usable"] = len(sc)
            if len(sc):
                rec[f"sc_{tag}_size_spread"] = float(sc["size"].max() / sc["size"].min())
                rec[f"sc_{tag}_range_span_m"] = float(sc.rng.max() - sc.rng.min())
                rec[f"sc_{tag}_meets_0_6m"] = bool(sc.rng.max() - sc.rng.min() >= MIN_SPAN_M)
                if len(sc) >= 2:
                    sc_frames.setdefault(tag, []).append(sc)
        summ.append(rec)
    R = pd.DataFrame(rows); Sm = pd.DataFrame(summ).set_index("dive_id")
    for tag in ("live", "all"):
        fr = pd.concat(sc_frames[tag], ignore_index=True)
        cal, C, _ = RL.calibrate(intr, cams, fr[["image_id", "dive_id", "x", "y", "size"]], f"SAM 3.1, {tag} dots")
        C = C.set_index("dive")
        Sm[f"sc_{tag}_angle_vs_stored_deg"] = C.angle_vs_stored_deg; Sm[f"sc_{tag}_vp_vs_stored_px"] = C.tv_err_px
        Sm[f"sc_{tag}_enough_frames"] = Sm[f"sc_{tag}_usable"] >= MIN_SC_FRAMES
    OUT.mkdir(parents=True, exist_ok=True)
    R.to_csv(OUT / "field_calibration_frames.csv", index=False, float_format="%.4f")
    Sm.to_csv(OUT / "field_calibration_summary.csv", float_format="%.4f")
    pd.set_option("display.width", 250)
    print(Sm.round(3).to_string()); print()
    print(R.groupby(["dive_id", "stage13"]).size().unstack(fill_value=0).to_string()); print()
    print(R[R.stage13 != "used in the fit"].groupby(["stage13", "species_answer"]).size().to_string())


if __name__ == "__main__":
    main()
