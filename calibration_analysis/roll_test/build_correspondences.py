"""Rebuild LEGO (vertical) and checkerboard (vertical) correspondences from the raw ORFs in ~/data.

Also regression-checks two upright frames against P4's cached `lego_target_raw.npz`.
Outputs land beside this file.
"""
import sys, time
from pathlib import Path
import numpy as np
# Run from P4's environment: ../wuwnet-fishsense2026/.venv/bin/python build_correspondences.py
SP = Path(__file__).resolve().parent; sys.path.insert(0, str(SP))
P4 = Path(__file__).resolve().parents[3] / "wuwnet-fishsense2026"; sys.path.insert(0, str(P4))
from lego_build import build
from fishsense_wuwnet.dataset import load_raw, raw_gray, detect_corners
D = Path("/home/chris/data")
# 1. LEGO vertical, paper settings (subpixel=False)
res = {}
for orf in sorted((D/"Lego Model Vertical").glob("*.ORF")):
    try:
        c, nq, dt, _ = build(orf, subpixel=False)
        res[f"obj/{orf.stem}"] = np.asarray(c.object_points, np.float32); res[f"img/{orf.stem}"] = np.asarray(c.image_points, np.float32)
        print(f"LEGO-V {orf.stem}: {nq} quads, {len(c)} pts, {dt:.1f}s", flush=True)
    except Exception as e:
        print(f"LEGO-V {orf.stem}: FAILED {type(e).__name__}: {e}", flush=True)
np.savez(SP/"lego_V.npz", **res)
# 2. spot-check two more horizontal frames against the paper cache
ref = np.load(P4/"data/lego_target_raw.npz")
for stem in ("P9210011", "P9210021"):
    c, *_ = build(D/"Lego Model Horizontal"/f"{stem}.ORF", subpixel=False)
    ri = ref[f"img/{stem}"]; ni = np.asarray(c.image_points)
    same = len(ri) == len(ni) and np.allclose(np.sort(ri, axis=0), np.sort(ni, axis=0))
    print(f"REGRESSION {stem}: paper {len(ri)} pts, rebuilt {len(ni)} pts, identical={same}", flush=True)
# 3. checkerboard vertical corners (raw, same pipeline as P4's board cache)
cb = {}
for orf in sorted((D/"Checkerboard Vertical").glob("*.ORF")):
    t = time.time(); raw = load_raw(orf); corners = detect_corners(raw_gray(raw))
    if corners is None: print(f"CB-V {orf.stem}: no corners", flush=True); continue
    cb[orf.stem] = np.asarray(corners, np.float32); print(f"CB-V {orf.stem}: {len(corners)} corners, {time.time()-t:.1f}s", flush=True)
np.savez(SP/"cb_V.npz", **cb)
print("DONE", flush=True)
