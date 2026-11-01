"""Fully automatic lengths for the stereo-measured fish that are not among the IMWUT paper's seven.

Fish: the collaborators' stereo archive (imwut_2026_fishsense_lite fish_model_analysis/data/stereo_archive.csv,
SV1 rows of 2023-08-03) matched to the single-fish Lite dives of that day by site, species and number, the
convention of the IMWUT pairs (stereo_pairs.csv / stereo_reference.csv: dives 5, 16, 20, 25, 28, 35, 39). Three
are not among the seven, all at Conch Reef, FSL-01, inside physical dive 15 (physical_dives.py):

  Hogfish1        331.0 mm   records 13/14  canonical images 2049-2053
  Black Grouper   300.2 mm   records 12/43  canonical images 2077-2086
  Nassau Grouper  441.5 mm   records 17/37  canonical images 2059-2067

(BlueParrot02_MolPeLe_1037, record 40, holds byte-identical copies of dive 39's photos, IMWUT's Blue Parrotfish1,
so it is not a new fish; BlueParrot01_MolPeLe_1029, record 33, may be the same fish as dive 39 and is left out.
The match rests on dive names, not on the images.)

Pipeline, production's automatic chain with the current components, frame by frame:
  dot        run3 epoch_021 on the linear RAW (fishsense-core LaserDetector, rectified output), kept only inside
             production's laser region (laser_region.py)
  render     RectifiedImage(RawImage(raw), intrinsics), fishsense-core's default decode
  fish       find_fish_at_dot(render, [dot], Sam3Segmenter(sam3.1_multiplex), grow_cut_masks=True, score_gate=0.5),
             as the services automatic chain calls it (automatic_results/frames.py)
  head/tail  v5: SimCC (HeadTailKeypointDetector, simcc-sam-e12) on the kept mask's box; no length when SimCC's and
             the mask rule's pixel lengths differ by more than 15% of the rule's (review)
  length     depth at the dot from dive 32's slate-pose-6 calibration (aim 0; same camera and day; production's own
             automatic calibration for physical dive 15 is borrowed from 32 or 23 with a ~13% bar)
Per fish: production's p90 over its measured frames; difference from stereo. Automatic lengths are not reviewed.
Control: the human pipeline on the same frames where human labels exist (human dot, human head/tail, dive 32's
human calibration; data/stereo/new_fish_human_labels.psv, sql/extract_stereo_new_fish_human.sql), so a gap to stereo
that both pipelines share is not blamed on automation.

Two modes:
  run    GPU + NAS, in the fishsense-services processor environment (fishsense-core 4.3.2, sam3, timm):
           LD_LIBRARY_PATH=<driver, libstdc++, libz> <procenv>/bin/python analysis/codesign/stereo_new_fish.py run
         writes data/stereo/new_fish_frames.jsonl (resumable)
  score  this repo's environment: uv run python analysis/codesign/stereo_new_fish.py
         writes analysis/codesign/results/stereo_new_fish.csv
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
NAS = Path.home() / "mnt/fishsense_data/REEF/data"
OUT = REPO / "data/stereo/new_fish_frames.jsonl"
LASER_CKPT = Path.home() / ".cache/huggingface/hub/models--ucsde4e--fishsense-laser-detector/snapshots/1cd50f16fa92a0b5c9b88645d75b4feb018d5d27/run3_epoch_021.pt"
SAM3_CKPT = Path.home() / "Downloads/sam3.1_multiplex.pt"
SIMCC_CKPT = Path.home() / ".cache/fishsense-kp/headtail-keypoints/simcc-sam-e12/simcc_sam_best_length.pt"
FISH = {"Hogfish1": (331.0, range(2049, 2054)), "Black Grouper": (300.2, range(2077, 2087)), "Nassau Grouper": (441.5, range(2059, 2068))}
CAL_DIVE, CAMERA, DISAGREE, SCORE_GATE = 32, 1, 0.15, 0.5


def frames():
    """image_id -> NAS-relative path and fish, from the frozen dump's extract (data/stereo/new_fish_images.psv)."""
    rows = [l.rstrip("\n").split("|") for l in (REPO / "data/stereo/new_fish_images.psv").open()]
    return {int(i): p for i, p in rows}


def run():
    import cv2
    import numpy as np
    import pandas as pd
    import torch
    from fishsense_core.camera_intrinsics import CameraIntrinsics
    from fishsense_core.fish.fish_at_dot import Sam3Segmenter, find_fish_at_dot
    from fishsense_core.fish.headtail_keypoints import HeadTailKeypointDetector
    from fishsense_core.fish.sam3 import build_segmenter
    from fishsense_core.image.linear_raw_image import LinearRawImage
    from fishsense_core.image.raw_image import RawImage
    from fishsense_core.image.rectified_image import RectifiedImage
    from fishsense_core.laser import LaserDetector

    sys.path.insert(0, str(REPO / "analysis/codesign"))
    from laser_region import in_region  # noqa: E402

    r = pd.read_csv(REPO / "laser_detection_analysis/intrinsics.csv").set_index("camera_id").loc[CAMERA]
    cm, dist = np.array(json.loads(r.camera_matrix)), np.array(json.loads(r.distortion_coefficients))
    paths = frames()
    done = {json.loads(l)["image_id"] for l in OUT.open()} if OUT.exists() else set()
    todo = [i for i in sorted(paths) if i not in done]
    print("cuda", torch.cuda.is_available(), "frames to do", len(todo), flush=True)

    dots, raws = {}, {}
    det = LaserDetector.from_checkpoint(str(LASER_CKPT))
    for i in todo:
        raws[i] = (NAS / paths[i]).read_bytes()
        p = det.predict(LinearRawImage(raws[i]), wavelength=None, rectify_output=True, camera_matrix=cm, distortion=dist)
        dots[i] = dict(x=p.x, y=p.y, confidence=p.confidence)
    del det; torch.cuda.empty_cache()

    seg = Sam3Segmenter(build_segmenter(str(SAM3_CKPT)))
    found = {}
    for i in todo:
        t0 = time.time()
        frame = RectifiedImage(RawImage(raws[i]), CameraIntrinsics(cm, dist)).data
        d = dots[i]
        ok = d["x"] is not None and np.isfinite(d["x"]) and in_region(d["x"], d["y"])
        f = find_fish_at_dot(frame, [[d["x"], d["y"]]], seg, grow_cut_masks=True, score_gate=SCORE_GATE) if ok else None
        found[i] = (frame, f, ok, time.time() - t0)
    del seg; torch.cuda.empty_cache()

    kp = HeadTailKeypointDetector.from_checkpoint(str(SIMCC_CKPT))
    with OUT.open("a") as fh:
        for i in todo:
            frame, f, ok, secs = found[i]
            rec = dict(image_id=i, dot=dots[i], in_region=ok, status=None if f is None else f.status)
            if f is not None and f.head is not None and f.mask_bbox is not None:
                k = kp.predict(frame, list(f.mask_bbox))
                rec.update(rule_head=[float(v) for v in f.head], rule_tail=[float(v) for v in f.tail],
                           mask_bbox=[float(v) for v in f.mask_bbox], simcc_head=[float(v) for v in k.head],
                           simcc_tail=[float(v) for v in k.tail], simcc_confidence=float(k.confidence))
            rec["seconds"] = round(secs, 1)
            fh.write(json.dumps(rec) + "\n"); fh.flush()
    print("done", flush=True)


def score():
    import numpy as np
    import pandas as pd
    sys.path.insert(0, str(REPO / "e2e_measurement"))
    import score as S  # noqa: E402

    C = pd.read_csv(REPO / "data/fishsense_services/slate_pose_calibrations.csv")
    c = C[(C.mission_v1_id == CAL_DIVE) & (C.method == "slate_pose") & (C.aim == 0)].iloc[0]
    O = np.array([c.laser_position_x, c.laser_position_y, c.laser_position_z], float)
    a = np.array([c.laser_axis_x, c.laser_axis_y, c.laser_axis_z], float)
    stored, _, intr = S.calibrations()
    K = intr[CAMERA]
    H = pd.read_csv(REPO / "data/stereo/new_fish_human_labels.psv", sep="|", header=None, names="i x y hx hy tx ty".split())
    human = {int(r.i): (r.x, r.y, r.hx, r.hy, r.tx, r.ty) for r in H.astype({"x": float, "hx": float}).itertuples()}
    fish_of = {i: name for name, (_, ids) in FISH.items() for i in ids}
    rows = []
    for l in OUT.open():
        r = json.loads(l)
        row = dict(image_id=r["image_id"], fish=fish_of[r["image_id"]], dot=r["dot"]["x"] is not None, in_region=r["in_region"],
                   status=r["status"], outcome="no fish at dot")
        if "simcc_head" in r:
            ls = np.hypot(*np.subtract(r["simcc_head"], r["simcc_tail"])); lr = np.hypot(*np.subtract(r["rule_head"], r["rule_tail"]))
            row["disagreement"] = ls / lr - 1
            if abs(ls / lr - 1) > DISAGREE:
                row["outcome"] = "review"
            else:
                Z = S.depth(K, O, a, r["dot"]["x"], r["dot"]["y"])
                row.update(outcome="measured", range_m=Z, length_m=S.length(K, Z, *r["simcc_head"], *r["simcc_tail"]))
        h = human.get(r["image_id"])
        if h is not None and np.isfinite(h[0]) and np.isfinite(h[2]):
            Zh = S.depth(K, *stored[CAL_DIVE], h[0], h[1])
            row.update(human_range_m=Zh, human_length_m=S.length(K, Zh, *h[2:]))
            if "simcc_head" in r:
                Za = S.depth(K, *stored[CAL_DIVE], r["dot"]["x"], r["dot"]["y"])
                row["auto_length_human_cal_m"] = S.length(K, Za, *r["simcc_head"], *r["simcc_tail"])
        rows.append(row)
    F = pd.DataFrame(rows)
    F.to_csv(REPO / "analysis/codesign/results/stereo_new_fish_frames.csv", index=False)
    out = []
    for name, (stereo_mm, ids) in FISH.items():
        g = F[(F.fish == name) & (F.outcome == "measured")]
        p90 = S.p90(g.length_m) if len(g) else np.nan
        out.append(dict(fish=name, stereo_mm=stereo_mm, frames=len(ids), measured=len(g),
                        outcomes=F[F.fish == name].outcome.value_counts().to_dict(), p90_mm=1000 * p90,
                        diff_pct=100 * (1000 * p90 / stereo_mm - 1) if len(g) else np.nan,
                        median_mm=1000 * g.length_m.median() if len(g) else np.nan,
                        human_frames=int(F[F.fish == name].human_length_m.notna().sum()),
                        human_p90_mm=1000 * S.p90(F[F.fish == name].human_length_m),
                        auto_vs_human_same_frames_pct=100 * float(np.median(
                            (F[F.fish == name].length_m / F[F.fish == name].human_length_m - 1).dropna()))
                        if F[(F.fish == name)][["length_m", "human_length_m"]].dropna().size else np.nan))
    R = pd.DataFrame(out)
    R.to_csv(REPO / "analysis/codesign/results/stereo_new_fish.csv", index=False)
    print(R.round(1).to_string(index=False))


if __name__ == "__main__":
    run() if sys.argv[1:2] == ["run"] else score()
