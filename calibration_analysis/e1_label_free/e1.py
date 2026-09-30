"""E1: can a dive's laser calibration run with nobody labelling anything?

Refits each P1 calibration dive with *production's own* stage-13 code -- imported by
path from fishsense-lite, not reimplemented -- while swapping where the inputs come from:

  stage 0  stored LaserExtrinsics (what production shipped)
  stage 1  human slate corners + human laser dots, refit now   (sanity: must match stage 0)
  stage 2  human slate corners + DETECTOR laser dots           (needs detector output)
  stage 3  PREDICTED slate corners + DETECTOR laser dots       (fully label-free)

Each calibration is judged the way P1 judges one: re-triangulate every P1 corpus frame
that borrowed it, rescale its recorded length by the depth ratio (exact, since snout and
fork are back-projected at the dot's depth -- P1 section 3.3), and compare the per-model
p90 against the known length. Known lengths are only ever the check, never an input.

Run from P4's environment (OpenCV + fishsense_core 4.0.0, production's pin):
    ../../../wuwnet-fishsense2026/.venv/bin/python e1.py
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
FISHSENSE = REPO.parent
DATA = REPO / "data" / "e1"
WORKER = (FISHSENSE / "fishsense-lite/services/fishsense-data-processing-workflow-worker"
          / "src/fishsense_data_processing_workflow_worker")
INCH_TO_M = 0.0254  # perform_laser_calibration_activity.INCH_TO_M


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, WORKER / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # dataclasses resolve annotations through sys.modules
    spec.loader.exec_module(mod)
    return mod


geometry = _load("calibration_geometry")
robust = _load("robust_laser_fit")
from fishsense_core.laser import calibrate_laser  # noqa: E402

sys.path.insert(0, str(FISHSENSE / "imwut_2026_fishsense_lite"))
from fishsense_imwut import calibration as cal  # noqa: E402


def jl(s):
    return None if pd.isna(s) else json.loads(s)


def load_inputs():
    dives = pd.read_csv(DATA / "dives.csv")
    slates = pd.read_csv(DATA / "slates.csv").set_index("dive_slate_id")
    sl = pd.read_csv(DATA / "slate_labels.csv")
    ll = pd.read_csv(DATA / "laser_labels.csv")
    ext = pd.read_csv(DATA / "extrinsics.csv").set_index("dive_id")
    K = {int(r.camera_id): np.array(json.loads(r.camera_matrix))
         for r in pd.read_csv(REPO / "laser_detection_analysis" / "intrinsics.csv").itertuples()}
    for df in (sl, ll):
        df["superseded"] = df.superseded.astype(str).str.lower().isin(["t", "true"])
    return dives, slates, sl, ll, ext, K


def slate_observations(dive, slates, sl, dots):
    """One (body_points_m, image_points, dot) per slate frame that also has a dot.
    `dots` maps image_id -> (x, y); this is the slot stage 2 swaps."""
    slate = slates.loc[int(dive.dive_slate_id)]
    template = np.array(json.loads(slate.reference_points), dtype=float)
    obs = []
    for r in sl[(sl.dive_id == dive.dive_id) & ~sl.superseded].itertuples():
        pts = jl(r.reference_points)
        if not pts or r.image_id not in dots:
            continue
        skipped = set(int(i) for i in (jl(r.skipped_points) or []))
        src = [p for i, p in enumerate(template.tolist()) if i not in skipped]
        if len(src) != len(pts):  # production's pairing guard
            continue
        body = np.array(src) / float(slate.dpi) * INCH_TO_M
        obs.append((body, np.array(pts, dtype=float), np.array(dots[r.image_id], dtype=float)))
    return obs


def fit(obs, K):
    """Production's stage-13 kernel: PnP plane -> dot on plane -> one robust trim -> line."""
    pts = []
    for body, image, dot in obs:
        plane = geometry.plane_from_correspondences(body, image, K)
        if plane is None:
            continue
        p = geometry.laser_point_on_plane(plane, dot, K)
        if p is not None:
            pts.append(p)
    if len(pts) < 2:
        return None, len(pts)
    kept = robust.trim_outlying_observations(np.array(pts))
    origin, axis = calibrate_laser(kept.astype(np.float32))
    LAST_FIT.update(points=kept, dots=np.array([o[2] for o in obs], float))
    return (np.array([origin[0], origin[1], 0.0]), np.asarray(axis, float)), len(pts)


LAST_FIT: dict = {}


def depth(dot, K, origin, axis):
    """Midpoint of closest approach between the dot's camera ray and the laser ray -- z."""
    ray = np.linalg.inv(K) @ np.array([dot[0], dot[1], 1.0])
    ray /= np.linalg.norm(ray)
    a = axis / np.linalg.norm(axis)
    b = ray @ a
    d1, e1 = -(ray @ origin), -(a @ origin)
    den = 1 - b * b
    s, t = (b * e1 - d1) / den, (e1 - b * d1) / den
    return float(0.5 * (s * ray + origin + t * a)[2])


def evaluate(calibrations: dict, K_by_cam=None) -> pd.DataFrame:
    """Per (calibration dive, model): p90 length error against known length, for every
    P1 corpus frame that used that calibration. `calibrations` maps dive_id -> (origin, axis)."""
    rows = cal.load_rows(FISHSENSE / "imwut_2026_fishsense_lite/fish_model_analysis/data/corpus.csv")
    out = []
    for r in rows:
        cd = int(r["calibration_dive_id"])
        if cd not in calibrations or calibrations[cd] is None:
            continue
        K = np.array(json.loads(r["km"]))
        dot = [float(v) for v in r["dot"].split(";")]
        z_new = depth(dot, K, *calibrations[cd])
        length = float(r["length_m"]) * z_new / float(r["depth_m"])
        known = cal.MEASURED_REFERENCES_M.get(r["model"], float(r["known_length_m"]))
        out.append(dict(cal_dive=cd, dive=int(r["dive_id"]), model=r["model"], z=z_new,
                        err_pct=100 * (length / known - 1)))
    df = pd.DataFrame(out)
    if df.empty:
        return pd.DataFrame(columns=["cal_dive", "dive", "model", "n", "p90"])
    return df.groupby(["cal_dive", "dive", "model"]).err_pct.agg(
        n="size", p90=lambda s: np.quantile(s, 0.9)).reset_index()


def stored_calibrations(ext):
    return {int(d): (np.array(json.loads(r.laser_position), float), np.array(json.loads(r.laser_axis), float))
            for d, r in ext.iterrows()}


LASER_REGION = _load_shared = None


def _laser_region():
    global LASER_REGION
    if LASER_REGION is None:
        spec = importlib.util.spec_from_file_location(
            "laser_region", FISHSENSE / "fishsense-lite/libs/fishsense-shared/src/fishsense_shared/laser_region.py")
        LASER_REGION = importlib.util.module_from_spec(spec)
        sys.modules["laser_region"] = LASER_REGION
        spec.loader.exec_module(LASER_REGION)
    return LASER_REGION


def _gates():
    import types
    if "fishsense_shared" not in sys.modules:
        pkg = types.ModuleType("fishsense_shared"); pkg.__path__ = []; sys.modules["fishsense_shared"] = pkg
        spec = importlib.util.spec_from_file_location(
            "fishsense_shared.calibration_bounds",
            FISHSENSE / "fishsense-lite/libs/fishsense-shared/src/fishsense_shared/calibration_bounds.py")
        mod = importlib.util.module_from_spec(spec); sys.modules[spec.name] = mod; spec.loader.exec_module(mod)
    return _load("calibration_consistency")


def production_gates(cal, K, fit_points, fit_dots, dive_dots=None):
    """Production's refusal gates, in production's order. Returns None if accepted, else the
    refusal class name. `dive_dots=None` skips the last gate (it needs dots from the whole dive)."""
    g = _gates()
    origin, axis = cal
    try:
        g.check_observation_geometry(fit_points)
        g.check_fit_self_consistency(origin, axis, K, fit_dots)
        g.check_baseline_plausible(origin)
        if dive_dots is not None:
            g.check_calibration_describes_dive(origin, axis, K, dive_dots)
    except Exception as exc:  # the four Calibration*Error types
        return type(exc).__name__
    return None


PRESENCE = 0.5  # the detector's own presence threshold (T3)
ECC_GATE = 0.80  # the retired slate predictor's acceptance gate


def load_frames_out():
    """Latest record per frame: a retried frame's success replaces its earlier error."""
    latest = {}
    for line in (HERE / "frames_out.jsonl").open():
        if line.strip():
            r = json.loads(line)
            latest[r["image_id"]] = r
    return list(latest.values())


def detector_dots(recs):
    return {r["image_id"]: tuple(r["dot"]) for r in recs
            if "error" not in r and r.get("dot") and r.get("confidence", 0) >= PRESENCE}


def slate_obs_predicted(recs, dive, slates, dots, tag, ecc_min=None):
    """Stage 3 slate observations: the estimator's corners, all template points in order."""
    slate = slates.loc[int(dive.dive_slate_id)]
    body = np.array(json.loads(slate.reference_points), float) / float(slate.dpi) * INCH_TO_M
    obs = []
    for r in recs:
        est = r.get(tag)
        if r["dive_id"] != dive.dive_id or est is None or r["image_id"] not in dots:
            continue
        if ecc_min is not None and est["ecc"] < ecc_min:
            continue
        obs.append((body, np.array(est["image_points"], float), np.array(dots[r["image_id"]], float)))
    return obs


def checkerboard_obs(recs, dive, dots):
    """Production's checkerboard observation: automatic corners, and the dot must be on the board."""
    region = _laser_region()
    obs = []
    for r in recs:
        b = r.get("board")
        if r["dive_id"] != dive.dive_id or b is None or r["image_id"] not in dots:
            continue
        x, y = dots[r["image_id"]]
        if not region.point_in_laser_region(float(x), float(y), b["hull"]):
            continue
        obs.append((np.array(b["body_points"], float), np.array(b["image_points"], float), np.array((x, y), float)))
    return obs


def all_stages(dives, slates, sl, ll, K, recs):
    human = {int(r.image_id): (r.x, r.y) for r in ll[~ll.superseded & ll.x.notna()].itertuples()}
    det = detector_dots(recs)
    stages = {s: {} for s in ("1 human corners + human dots",
                              "2 human corners + detector dots",
                              "3 predicted corners (classical) + detector dots",
                              "3 predicted corners (masked) + detector dots",
                              "3 predicted corners (masked, ECC>=0.8) + detector dots")}
    counts = {s: {} for s in stages}
    for d in dives.itertuples():
        k = K[int(d.camera_id)]
        if pd.notna(d.dive_slate_id):
            plan = {list(stages)[0]: slate_observations(d, slates, sl, human),
                    list(stages)[1]: slate_observations(d, slates, sl, det),
                    list(stages)[2]: slate_obs_predicted(recs, d, slates, det, "classical"),
                    list(stages)[3]: slate_obs_predicted(recs, d, slates, det, "masked"),
                    list(stages)[4]: slate_obs_predicted(recs, d, slates, det, "masked", ECC_GATE)}
        else:  # checkerboard: corners are automatic in every stage
            plan = {list(stages)[0]: checkerboard_obs(recs, d, human),
                    list(stages)[1]: checkerboard_obs(recs, d, det)}
            for s in list(stages)[2:]:
                plan[s] = plan[list(stages)[1]]
        for s, obs in plan.items():
            c, n = fit(obs, k)
            stages[s][int(d.dive_id)], counts[s][int(d.dive_id)] = c, n
    return stages, counts


def report(stored, stages, counts):
    base = evaluate(stored)
    rows = []
    for s, cals in stages.items():
        ok = {k: v for k, v in cals.items() if v is not None and counts[s][k] >= 5}
        ev = evaluate(ok)
        m = base.merge(ev, on=["cal_dive", "dive", "model"], suffixes=("_stored", "_new"))
        baselines = [np.hypot(*v[0][:2]) * 100 for v in ok.values()]
        rows.append(dict(stage=s, dives_calibrated=len(ok), cells=len(m),
                         abs_p90_err_median=m.p90_new.abs().median(),
                         stored_same_cells=m.p90_stored.abs().median(),
                         max_shift_pp=np.max(np.abs(m.p90_new - m.p90_stored)) if len(m) else np.nan,
                         baselines_outside_9p7_14p5cm=int(sum(b < 9.7 or b > 14.5 for b in baselines))))
    return pd.DataFrame(rows).set_index("stage")


if __name__ == "__main__" and len(sys.argv) > 1 and sys.argv[1] == "stages":
    dives, slates, sl, ll, ext, K = load_inputs()
    recs = load_frames_out()
    print(f"{len(recs)} frames processed so far")
    stages, counts = all_stages(dives, slates, sl, ll, K, recs)
    pd.set_option("display.width", 250)
    print(report(stored_calibrations(ext), stages, counts).round(3).to_string())
    sys.exit(0)

if __name__ == "__main__":
    dives, slates, sl, ll, ext, K = load_inputs()
    stored = stored_calibrations(ext)

    # harness check: the stored calibration must reproduce P1's recorded depths
    rows = cal.load_rows(FISHSENSE / "imwut_2026_fishsense_lite/fish_model_analysis/data/corpus.csv")
    diffs = [depth([float(v) for v in r["dot"].split(";")], np.array(json.loads(r["km"])),
                   *stored[int(r["calibration_dive_id"])]) - float(r["depth_m"])
             for r in rows if int(r["calibration_dive_id"]) in stored]
    print(f"harness: stored calibration vs P1 recorded depth, |diff| max {np.max(np.abs(diffs))*1000:.3f} mm over {len(diffs)} frames")

    human_dots = {int(r.image_id): (r.x, r.y) for r in ll[~ll.superseded & ll.x.notna()].itertuples()}
    stage1, npts = {}, {}
    for d in dives[dives.dive_slate_id.notna()].itertuples():
        obs = slate_observations(d, slates, sl, human_dots)
        stage1[int(d.dive_id)], npts[int(d.dive_id)] = fit(obs, K[int(d.camera_id)])

    print(f"\nstage 1 (human inputs, production code) vs stored, slate dives:")
    for dv, c in sorted(stage1.items()):
        if c is None or dv not in stored:
            print(f"  dive {dv}: refit {'failed' if c is None else 'ok'}, stored {'yes' if dv in stored else 'no'}"); continue
        o0, a0 = stored[dv]; o1, a1 = c
        ang = np.degrees(np.arccos(np.clip(abs(a0 @ a1) / np.linalg.norm(a0) / np.linalg.norm(a1), -1, 1)))
        print(f"  dive {dv}: {npts[dv]:2d} obs | axis differs {ang:.4f} deg | baseline stored {np.hypot(*o0[:2])*100:.2f} cm refit {np.hypot(*o1[:2])*100:.2f} cm")

    ev0 = evaluate(stored); ev1 = evaluate({k: v for k, v in stage1.items() if v is not None})
    m = ev0.merge(ev1, on=["cal_dive", "dive", "model"], suffixes=("_stored", "_refit"))
    print(f"\ncorpus cells evaluated: {len(m)};  |p90 error| median stored {m.p90_stored.abs().median():.2f} %  refit {m.p90_refit.abs().median():.2f} %;  max |difference| {np.max(np.abs(m.p90_refit - m.p90_stored)):.3f} pp")
