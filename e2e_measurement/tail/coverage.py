"""Coverage diagnostic, CPU: why SAM misses real reef fish, and which remedy recovers them correctly.

Inputs: coverage/<id>.npz (coverage_gpu.py: every mask >= 0.1 for three prompts on the production
window at the HUMAN dot) and the human dot / head / tail clicks.

1. Cause of each production failure (prompt "fish", score > 0.5, dot on a mask pixel), first
   match wins:
     dot_off_fish      the human dot is > 0.35 L from the human head-tail segment: the dot is not
                       on the clicked fish, so no mask could satisfy both
     fish_off_window   the human head or tail lies outside the 1800x1350 window
     low_score         a "fish" mask with 0.1 < score <= 0.5 contains the dot
     near_miss         a "fish" mask > 0.5 lies within 15 px of the dot but not under it
     other_prompt      "reef fish" or "a fish" > 0.5 contains the dot
     unseen            none of the above
2. Remedies: select a mask by the rule, keypoint it with production's FishHeadTailDetector, and
   score it against the human clicks (length ratio, head/tail error). A remedy that adds masks of
   the wrong fish shows up as a worse ratio, not as coverage.

Run from fishsense-lite's venv (fishsense_core): ../../../fishsense-lite/.venv/bin/python coverage.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
COV = HERE / "coverage"
TOL = 15


def load_masks(z, k):
    if f"p{k}_masks" not in z:
        return np.zeros(0), []
    h, w = z["shape"]; sc = z[f"p{k}_scores"]
    bits = z[f"p{k}_masks"]
    return sc, [np.unpackbits(bits[i])[: h * w].reshape(h, w).astype(bool) for i in range(len(sc))]


def seg_dist(p, a, b):
    ab = b - a; t = np.clip((p - a) @ ab / (ab @ ab), 0, 1)
    return np.linalg.norm(p - (a + t * ab))


def dist_to_mask(m, x, y):
    ys, xs = np.nonzero(m)
    return np.inf if len(xs) == 0 else float(np.min(np.hypot(xs - x, ys - y)))


def select(masks, x, y, thr, tol=0, prompts=(0,)):
    """Highest-scoring mask over the given prompts with score > thr that contains the dot (or lies within tol px)."""
    best = None
    for k in prompts:
        sc, ms = masks[k]
        for s, m in zip(sc, ms):
            if s <= thr:
                continue
            xi, yi = int(round(x)), int(round(y))
            inside = 0 <= yi < m.shape[0] and 0 <= xi < m.shape[1] and m[yi, xi]
            if inside or (tol and dist_to_mask(m, x, y) <= tol):
                if best is None or s > best[0]:
                    best = (s, m)
    return None if best is None else best[1]


REMEDIES = {  # name: (thr, tol, prompts)
    "production (fish > 0.5, on dot)": (0.5, 0, (0,)),
    "threshold 0.3": (0.3, 0, (0,)),
    "threshold 0.2": (0.2, 0, (0,)),
    "threshold 0.1": (0.1, 0, (0,)),
    f"dot tolerance {TOL} px": (0.5, TOL, (0,)),
    "prompt ensemble (> 0.5)": (0.5, 0, (0, 1, 2)),
    f"threshold 0.3 + tolerance {TOL} + ensemble": (0.3, TOL, (0, 1, 2)),
}


def main():
    from fishsense_core.fish import FishHeadTailDetector
    det = FishHeadTailDetector()
    F = pd.read_csv(HERE / "frames.csv"); F = F[F.set == "reef"].set_index("image_id")
    causes, rows = [], []
    for p in sorted(COV.glob("*.npz")):
        iid = int(p.stem); r = F.loc[iid]; z = np.load(p)
        ox, oy = z["origin"]; h, w = z["shape"]
        masks = {k: load_masks(z, k) for k in range(3)}
        x, y = r.laser_x - ox, r.laser_y - oy
        H = np.array([r.head_x - ox, r.head_y - oy]); T = np.array([r.tail_x - ox, r.tail_y - oy]); L = np.linalg.norm(T - H)
        base = select(masks, x, y, 0.5)
        if base is None:
            if seg_dist(np.array([x, y]), H, T) > 0.35 * L:
                c = "dot_off_fish"
            elif not all(0 <= q[0] < w and 0 <= q[1] < h for q in (H, T)):
                c = "fish_off_window"
            elif select(masks, x, y, 0.1) is not None:
                c = "low_score"
            elif select(masks, x, y, 0.5, tol=TOL) is not None:
                c = "near_miss"
            elif select(masks, x, y, 0.5, prompts=(1, 2)) is not None:
                c = "other_prompt"
            else:
                c = "unseen"
        else:
            c = "ok"
        causes.append(dict(image_id=iid, dive=r.dive_id, green=str(r.laser_label).startswith("Green"), cause=c, L_px=L,
                           species=str(r.content).split("(")[-1].rstrip(")") if pd.notna(r.content) else "(unlabelled)"))
        for name, (thr, tol, prompts) in REMEDIES.items():
            m = select(masks, x, y, thr, tol, prompts)
            rec = dict(image_id=iid, remedy=name, covered=m is not None)
            if m is not None:
                try:
                    hh, tt = det.find_head_tail_img(m.astype(np.uint8) * 255)
                    hh, tt = np.asarray(hh, float), np.asarray(tt, float)
                    if np.linalg.norm(hh - T) + np.linalg.norm(tt - H) < np.linalg.norm(hh - H) + np.linalg.norm(tt - T):
                        hh, tt = tt, hh
                    rec.update(ratio=np.linalg.norm(tt - hh) / L, head_err=np.linalg.norm(hh - H) / L, tail_err=np.linalg.norm(tt - T) / L,
                               touches_edge=bool(m[0].any() or m[-1].any() or m[:, 0].any() or m[:, -1].any()))
                except Exception:
                    rec["covered"] = False
            rows.append(rec)
    C = pd.DataFrame(causes); R = pd.DataFrame(rows)
    pd.set_option("display.width", 220)
    print(f"{len(C)} reef frames. Production coverage {np.mean(C.cause == 'ok'):.1%}.\nCauses of the failures:")
    print(C[C.cause != "ok"].cause.value_counts().to_string())
    print("\nfailure causes by laser colour (share of frames):")
    print(pd.crosstab(C.green.map({True: "green", False: "red"}), C.cause, normalize="index").round(3).to_string())
    print("\nfish length in px, ok vs failed (median):", C.groupby(C.cause == "ok").L_px.median().round(0).to_dict())
    print("\nremedies (keypointed with production's detector, scored against human clicks):")
    out = R.groupby("remedy", sort=False).agg(coverage=("covered", "mean"), ratio_med=("ratio", "median"),
                                             ratio_mae=("ratio", lambda s: (s - 1).abs().mean()),
                                             within10=("ratio", lambda s: ((s - 1).abs() <= .1).mean()),
                                             tail_err_med=("tail_err", "median"), touches_window_edge=("touches_edge", "mean"))
    out["good_frames"] = R.assign(g=R.covered & ((R.ratio - 1).abs() <= .1)).groupby("remedy", sort=False).g.mean()
    print(out.round(3).to_string())
    C.to_csv(HERE / "coverage_causes.csv", index=False); R.to_csv(HERE / "coverage_remedies.csv", index=False)


if __name__ == "__main__":
    main()
