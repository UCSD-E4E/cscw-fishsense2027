"""Rebuild LEGO-target correspondences from raw ORFs (the lost roll2.py / lego_v.py).

Pipeline, per P4's own library: load_raw -> raw_colour -> detect_quads(photo settings)
-> match(quads, K guess) -> (object_points, image_points).
"""
import sys, time, json
from pathlib import Path
import numpy as np
P4 = Path(__file__).resolve().parents[3] / "wuwnet-fishsense2026"
sys.path.insert(0, str(P4))
from fishsense_wuwnet.dataset import load_raw, raw_colour
from fishsense_wuwnet.target_detect import detect_quads, match

SENSOR = (4014, 3016)
GUESS = np.array([[2900.0, 0, SENSOR[0]/2], [0, 2900.0, SENSOR[1]/2], [0, 0, 1.0]])

def build(orf, subpixel=True):
    t = time.time()
    raw = load_raw(orf)
    img = raw_colour(raw)
    quads = detect_quads(img, chroma_blur=2.0, open_px=5, subpixel=subpixel)
    corr = match(quads, GUESS)
    return corr, len(quads), time.time() - t, img.shape

if __name__ == "__main__":
    folder, out = Path(sys.argv[1]), Path(sys.argv[2])
    only = sys.argv[3:] or None
    res = {}
    for orf in sorted(folder.glob("*.ORF")):
        if only and orf.stem not in only: continue
        try:
            corr, nq, dt, shp = build(orf)
            res[f"obj/{orf.stem}"] = np.asarray(corr.object_points, np.float32)
            res[f"img/{orf.stem}"] = np.asarray(corr.image_points, np.float32)
            print(f"{orf.stem}: {nq} quads, {len(corr)} matched points, {dt:.1f}s, shape {shp}", flush=True)
        except Exception as e:
            print(f"{orf.stem}: FAILED {type(e).__name__}: {e}", flush=True)
    np.savez(out, **res)
    print("saved", out, len([k for k in res if k.startswith('obj/')]), "views")
