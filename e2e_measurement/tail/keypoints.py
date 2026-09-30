"""Tail study, CPU: head/tail keypoints from the saved SAM masks under two tail rules.

  prod   fishsense-core's FishHeadTailDetector (production): PCA endpoints plus its peduncle /
         hull-area head-vs-tail decision. Its tail is the far end of the mask along the body axis.
  fork   production's head; the tail becomes the caudal FORK when the mask has one: the deepest
         convexity defect of the outline that
           - lies in the tail portion (projection on head->tail beyond FORK_FROM of the length),
           - has both hull-chord endpoints (the lobe tips) further toward the tail than itself,
           - opens across the body (chord within 45 deg of perpendicular to the axis),
           - lies near the axis (lateral offset < 0.25 L),
           - is at least DELTA * L deep.
         With no such notch (rounded or truncate tails) the tip stays -- which is also where a
         person clicks on a rounded tail. DELTA is fixed in advance at 0.03; 0.02 and 0.05 are
         reported as sensitivity only.

Run from fishsense-lite's venv (fishsense_core):  ../../../fishsense-lite/.venv/bin/python keypoints.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from gpu import MASKS, load_mask  # noqa: E402

FORK_FROM, PAD = 0.6, 5
DELTAS = (0.03, 0.02, 0.05)


def fork_tail(mask, head, tail, delta):
    import cv2
    H, T = np.asarray(head, float), np.asarray(tail, float)
    L = np.linalg.norm(T - H)
    if L < 10:
        return None
    a = (T - H) / L; perp = np.array([-a[1], a[0]])
    cnts, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not cnts:
        return None
    c = max(cnts, key=cv2.contourArea)
    try:
        hull = cv2.convexHull(c, returnPoints=False)
        defects = cv2.convexityDefects(c, hull)
    except cv2.error:
        return None
    if defects is None:
        return None
    pts = c[:, 0, :].astype(float)
    best = None
    for s, e, f, d in defects.reshape(-1, 4):   # OpenCV returns (N,1,4), or (N,4) in some builds
        S, E_, Fp = pts[s], pts[e], pts[f]; depth = d / 256.0
        sF, sS, sE = [(q - H) @ a / L for q in (Fp, S, E_)]
        chord = E_ - S; nc = np.linalg.norm(chord)
        if (sF > FORK_FROM and sS > sF and sE > sF and depth >= delta * L and nc > 0
                and abs(chord @ a) / nc < np.cos(np.radians(45)) and abs((Fp - H) @ perp) < 0.25 * L):
            if best is None or depth > best[0]:
                best = (depth, Fp)
    return None if best is None else best[1]


def main():
    from fishsense_core.fish import FishHeadTailDetector
    det = FishHeadTailDetector(); rows = []
    for p in sorted(MASKS.glob("*.npz")):
        iid, seed = p.stem.split("_"); iid = int(iid)
        status, m, off = load_mask(iid, seed)
        rec = dict(image_id=iid, seed=seed, mask_status=status)
        if m is None:
            rows.append(rec); continue
        mp = np.pad(m, PAD); ox, oy = off[0] - PAD, off[1] - PAD
        rec["mask_area_px"] = int(m.sum())
        try:
            h, t = det.find_head_tail_img(mp.astype(np.uint8) * 255)
        except Exception as e:
            rec["mask_status"] = f"headtail_failed: {e}"; rows.append(rec); continue
        h, t = np.asarray(h, float), np.asarray(t, float)
        rec.update(head_x=h[0] + ox, head_y=h[1] + oy, prod_tail_x=t[0] + ox, prod_tail_y=t[1] + oy)
        for delta in DELTAS:
            f = fork_tail(mp, h, t, delta)
            tag = f"fork{int(round(delta * 100)):02d}"
            ft = t if f is None else f
            rec.update({f"{tag}_tail_x": ft[0] + ox, f"{tag}_tail_y": ft[1] + oy, f"{tag}_moved": f is not None})
        rows.append(rec)
    K = pd.DataFrame(rows); K.to_csv(HERE / "keypoints.csv", index=False)
    if "head_x" not in K:
        print(f"{len(K)} masks; none keypointed"); return
    ok = K.dropna(subset=["head_x"])
    print(f"{len(K)} masks; keypointed {len(ok)}; fork03 moved the tail on {ok.fork03_moved.mean():.0%}")


if __name__ == "__main__":
    main()
