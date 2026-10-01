"""E1j label-free: the object's size ratio between frames from image registration.

No corner labels, no template, no known size. For each frame with the dot on an object:
SIFT features within ROI px of the dot (the dot is on the object, so the object dominates
the neighbourhood). Each frame is matched to every other frame of the dive; a RANSAC
similarity transform gives the relative scale s_j/s_i. A least-squares solve over all
pairs gives log s_k per frame (up to one constant, which size constancy does not need).
Then t_v is fitted exactly as in slate_unknown.py and compared with the stored calibration.

Pass 1 (NAS, slow):   ../../../wuwnet-fishsense2026/.venv/bin/python register.py extract
Pass 2 (fast):        ../../../wuwnet-fishsense2026/.venv/bin/python register.py score
"""
from __future__ import annotations

import sys, time
from itertools import combinations
from pathlib import Path

import os
import cv2
import numpy as np
import pandas as pd
import rawpy

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import slate_unknown as su  # noqa: E402
import sys as _sys; _sys.path.insert(0, str(__import__('pathlib').Path(__file__).resolve().parents[2]))
from fishsense_cscw.anon import real_path  # noqa: E402  (pseudonymised paths -> real NAS paths)

NAS = Path.home() / "mnt/fishsense_data/REEF/data"
DIVES = [62, 63, 65, 71, 77, 80, 83, 87, 94, 114]
ROI = 700          # full-resolution px around the dot
MIN_INLIERS = int(os.environ.get("MIN_INLIERS", 8))
MODEL = os.environ.get('MODEL', 'sim')      # sim: similarity; homog: plane homography, scale at the dot
SELECT = os.environ.get('SELECT', 'near')   # hull: inliers surround the dot; near: most inliers within NEAR px of it
NEAR = int(os.environ.get("NEAR", 80))   # full-res px; must be on the scale of the object, not the scene


def gray_half(path):
    with rawpy.imread(str(path)) as raw:
        rgb = raw.postprocess(half_size=True, output_bps=8, no_auto_bright=False, use_camera_wb=True)
    g = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    return cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(g)


def extract():
    d, *_ = su.load()
    paths = pd.read_csv(su.SCRATCH / "slate_paths.psv", sep="|", header=None, names=["image_id", "path"]).set_index("image_id").path
    d = d[d.dive_id.isin(DIVES) & d.image_id.isin(paths.index)]
    out = HERE / "features"; out.mkdir(exist_ok=True)
    sift = cv2.SIFT_create(nfeatures=4000)
    todo = [r for r in d.itertuples() if not (out / f"{r.image_id}.npz").exists()]
    print(f"{len(todo)} frames to do", flush=True)
    for n, r in enumerate(todo, 1):
        t0 = time.time()
        try:
            g = gray_half(NAS / real_path(paths[r.image_id], NAS))
            cx, cy, R = r.x / 2, r.y / 2, ROI / 2
            mask = np.zeros_like(g); cv2.circle(mask, (int(cx), int(cy)), int(R), 255, -1)
            kp, desc = sift.detectAndCompute(g, mask)
            np.savez(out / f"{r.image_id}.npz", xy=np.array([k.pt for k in kp], np.float32) * 2, desc=desc)
        except Exception as e:
            print(f"  {r.image_id}: {type(e).__name__}: {e}", flush=True)
        if n % 10 == 0:
            print(f"{n}/{len(todo)} ({time.time() - t0:.1f}s last)", flush=True)
    print("done", flush=True)


def pair_scale(a, b, matcher, dot_a):
    """Scale between two frames of the object the dot is on.

    Scenes hold several rigid layers (the object, the pool floor or reef behind it). Sequential
    RANSAC peels off up to three similarity motions; the object's is the one whose inliers
    surround the dot (dot inside their convex hull) -- the dot is on the object by construction.
    """
    if a["desc"] is None or b["desc"] is None or len(a["desc"]) < 10 or len(b["desc"]) < 10:
        return None
    m = matcher.knnMatch(a["desc"], b["desc"], k=2)
    good = [p[0] for p in m if len(p) == 2 and p[0].distance < 0.75 * p[1].distance]
    if len(good) < MIN_INLIERS:
        return None
    pa = a["xy"][[g.queryIdx for g in good]]; pb = b["xy"][[g.trainIdx for g in good]]
    best = None
    for _ in range(3):
        if len(pa) < MIN_INLIERS:
            break
        # a plane's motion is a homography even when it tilts (the angle-test sessions tilt the slate on purpose);
        # its local scale at the dot, sqrt|det J|, is the range ratio there
        if MODEL == "sim":
            M, inl = cv2.estimateAffinePartial2D(pa, pb, method=cv2.RANSAC, ransacReprojThreshold=6.0)
            H = None if M is None else np.vstack([M, [0, 0, 1]])
        else:
            H, inl = cv2.findHomography(pa, pb, cv2.RANSAC, 6.0)
        if H is None or inl.sum() < MIN_INLIERS:
            break
        inl = inl.ravel().astype(bool)
        hull = cv2.convexHull(pa[inl].astype(np.float32))
        inside = cv2.pointPolygonTest(hull, (float(dot_a[0]), float(dot_a[1])), True)  # >0 inside, px from edge
        x, y = dot_a; w = H[2, 0] * x + H[2, 1] * y + H[2, 2]
        u = (H[0, 0] * x + H[0, 1] * y + H[0, 2]) / w; v = (H[1, 0] * x + H[1, 1] * y + H[1, 2]) / w
        J = np.array([[H[0, 0] - u * H[2, 0], H[0, 1] - u * H[2, 1]], [H[1, 0] - v * H[2, 0], H[1, 1] - v * H[2, 1]]]) / w
        det = np.linalg.det(J)
        near = int((np.hypot(*(pa[inl] - dot_a).T) < NEAR).sum())
        score = near if SELECT == "near" else int(inl.sum())
        cand = (inside if SELECT == "hull" else near, score, float(0.5 * np.log(abs(det))) if det > 0 else np.nan)
        if not np.isfinite(cand[2]):
            pa, pb = pa[~inl], pb[~inl]; continue
        if inside > 0 and (best is None or cand[1] > best[1]):
            best = cand
        pa, pb = pa[~inl], pb[~inl]
    return (best[2], best[1]) if best else None


def score():
    d, lines, ext, intr = su.load()
    feats = HERE / "features"
    matcher = cv2.BFMatcher(cv2.NORM_L2)
    rng = np.random.default_rng(0); rows = []
    for dive in DIVES:
        g = d[(d.dive_id == dive)]
        g = g[[(feats / f"{i}.npz").exists() for i in g.image_id]].reset_index(drop=True)
        F = [dict(np.load(feats / f"{i}.npz", allow_pickle=True)) for i in g.image_id]
        eq, w = [], []
        for i, j in combinations(range(len(g)), 2):
            r = pair_scale(F[i], F[j], matcher, g.loc[i, ['x', 'y']].to_numpy(float))
            if r and r[1] >= 3:   # a pair needs matches near the dot, or its weight is zero and its residual undefined
                row = np.zeros(len(g)); row[j], row[i] = 1, -1
                eq.append((row, r[0])); w.append(np.sqrt(r[1]))
        if len(eq) < len(g):
            print(f"dive {dive}: only {len(eq)} matched pairs for {len(g)} frames"); continue
        A = np.array([e[0] for e in eq]) * np.array(w)[:, None]; b = np.array([e[1] for e in eq]) * np.array(w)
        A = np.vstack([A, np.ones(len(g))]); b = np.append(b, 0.0)           # gauge: mean log s = 0
        logs = np.linalg.lstsq(A, b, rcond=None)[0]
        # a wrong pair match (another layer that passed the selection) disagrees with the loop of
        # other pairs through the same frames: drop pairs beyond 4 robust SDs and re-solve
        # (one pass; the robust SD is floored at 1 % of scale, the typical pair noise, so an
        # almost-perfect majority cannot shrink the tolerance until everything is rejected)
        r = (A[:-1] @ logs - b[:-1]) / np.array(w)
        mad = max(1.4826 * np.median(np.abs(r - np.median(r))), 0.01)
        keep = np.append(np.abs(r) <= 4 * mad, True)
        logs = np.linalg.lstsq(A[keep], b[keep], rcond=None)[0]
        resid = (A[:-1] @ logs - b[:-1]) / np.array(w)
        connected = np.abs(A[:-1]).sum(0) > 0
        g, logs = g[connected].reset_index(drop=True), logs[connected]
        u = su.frame(dive, g, lines)
        t = g[["x", "y"]].to_numpy(float) @ u
        s_reg = np.exp(logs); s_lab = g["size"].to_numpy()
        tv = su.fit_tv(t, s_reg)
        boots = [su.fit_tv(t[i], s_reg[i]) for i in (rng.integers(0, len(t), len(t)) for _ in range(200))]
        ax = np.array(su.json.loads(ext.loc[dive, "axis"])); K = intr[int(ext.loc[dive, "camera_id"])]
        v = np.array([K[0, 0] * ax[0] / ax[2] + K[0, 2], K[1, 1] * ax[1] / ax[2] + K[1, 2]])
        xy = g[["x", "y"]].to_numpy(float); nrm = np.array([-u[1], u[0]])
        rows.append(dict(dive=dive, ux=float(u[0]), uy=float(u[1]), line_offset=float(np.median(xy @ nrm)),
                         frames=len(g), pairs=len(eq), pair_resid_sd=float(resid.std()),
                         corr_with_labels=float(np.corrcoef(np.log(s_reg), np.log(s_lab))[0, 1]),
                         size_ratio=float(s_reg.max() / s_reg.min()), tv_fit=tv, se_px=float(np.std(boots)),
                         err_px=float(tv - v @ u)))
    R = pd.DataFrame(rows); R["err_deg"] = np.degrees(R.err_px / su.F_PX); R["se_deg"] = np.degrees(R.se_px / su.F_PX)
    pd.set_option("display.width", 200)
    R.to_csv(HERE / "labelfree_tv.csv", index=False)   # consumed by e2e_measurement/score.py
    print(R.drop(columns=["ux", "uy", "line_offset"]).round(3).to_string(index=False))
    print(f"\nlabel-free: |error| median {R.err_deg.abs().median():.3f} deg; within 0.05: {(R.err_deg.abs() <= .05).sum()}, "
          f"within 0.15: {(R.err_deg.abs() <= .15).sum()} of {len(R)}")


if __name__ == "__main__":
    extract() if sys.argv[1] == "extract" else score()
