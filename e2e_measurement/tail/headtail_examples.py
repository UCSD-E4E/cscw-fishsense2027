"""Crops and keypoints for the head/tail example figure (Fig 13), saved into the repo so the figure
rebuilds without the local frame cache.

Picks three typical reef fish (head and tail errors closest to the reef medians, one each of
Hogfish, Stoplight Parrotfish and Black Grouper) and the three pool failure modes found earlier
(Shark tail lobe 4168, Purple Angel fin corner 4175, Grouper occluded by the pole 4874). The
automatic keypoints are from the mask seeded at the human dot, so only the head/tail stage differs
from the human. Each crop is the human and automatic points' bounding box plus 18% margin,
saved at most 640 px wide.

Writes data/headtail_examples/{image_id}.jpg and examples.csv (crop-local coordinates).
Run from this repo:  uv run --no-project --with pillow python e2e_measurement/tail/headtail_examples.py
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
STAGE = Path.home() / ".cache/cscw-fishsense2027/tail_stage"
OUT = REPO / "data/headtail_examples"
FAILURES = [(4168, "Shark model: tail on the upper lobe"), (4175, "Angelfish model: tail on a fin corner"),
            (4874, "Grouper model: mask cut by the pole")]
REEF = [("Hogfish", "Hogfish"), ("Stoplight Parrotfish", "Stoplight parrotfish"), ("Black Grouper", "Black grouper")]


def main():
    F = pd.read_csv(HERE / "frames.csv").set_index("image_id")
    K = pd.read_csv(HERE / "keypoints.csv"); K = K[(K.seed == "human") & K.head_x.notna()].set_index("image_id")
    rows = []
    ok = K.index.intersection(F.index)
    J = K.loc[ok].join(F.loc[ok, ["head_x", "head_y", "tail_x", "tail_y", "content", "set"]], rsuffix="_h").dropna(subset=["head_x_h"])
    Lh = np.hypot(J.head_x_h - J.tail_x, J.head_y_h - J.tail_y)
    J["ratio"] = np.hypot(J.head_x - J.prod_tail_x, J.head_y - J.prod_tail_y) / Lh
    # endpoint errors as a share of length, with head/tail possibly swapped (score the better assignment)
    d_dir = np.hypot(J.head_x - J.head_x_h, J.head_y - J.head_y_h) + np.hypot(J.prod_tail_x - J.tail_x, J.prod_tail_y - J.tail_y)
    d_sw = np.hypot(J.head_x - J.tail_x, J.head_y - J.tail_y) + np.hypot(J.prod_tail_x - J.head_x_h, J.prod_tail_y - J.head_y_h)
    sw = d_sw < d_dir
    J["head_err"] = np.where(sw, np.hypot(J.prod_tail_x - J.head_x_h, J.prod_tail_y - J.head_y_h),
                             np.hypot(J.head_x - J.head_x_h, J.head_y - J.head_y_h)) / Lh
    J["tail_err"] = np.where(sw, np.hypot(J.head_x - J.tail_x, J.head_y - J.tail_y),
                             np.hypot(J.prod_tail_x - J.tail_x, J.prod_tail_y - J.tail_y)) / Lh
    J = J[[(STAGE / f"{i}.jpg").exists() for i in J.index]]
    picks = []
    for key, label in REEF:
        g = J[(J.set == "reef") & J.content.fillna("").str.contains(key)]
        if len(g):
            # typical = endpoint errors closest to the reef-wide medians (a length ratio near 1 can hide bad endpoints)
            reef = J[J.set == "reef"]; mh, mt = reef.head_err.median(), reef.tail_err.median()
            picks.append((int(((g.head_err - mh) ** 2 + (g.tail_err - mt) ** 2).idxmin()), f"{label}: typical", "typical"))
    picks += [(i, lab, "failure") for i, lab in FAILURES if i in J.index]
    OUT.mkdir(parents=True, exist_ok=True)
    for iid, label, kind in picks:
        r = J.loc[iid]
        pts = np.array([[r.head_x_h, r.head_y_h], [r.tail_x, r.tail_y], [r.head_x, r.head_y], [r.prod_tail_x, r.prod_tail_y]])
        x0, y0 = pts.min(0); x1, y1 = pts.max(0); m = 0.18 * max(x1 - x0, y1 - y0)
        img = Image.open(STAGE / f"{iid}.jpg").convert("RGB")
        box = (int(max(0, x0 - m)), int(max(0, y0 - m)), int(min(img.width, x1 + m)), int(min(img.height, y1 + m)))
        crop = img.crop(box); s = min(1.0, 640 / crop.width)
        crop.resize((int(crop.width * s), int(crop.height * s))).save(OUT / f"{iid}.jpg", quality=85)
        q = (pts - [box[0], box[1]]) * s
        rows.append(dict(image_id=iid, label=label, kind=kind, ratio=float(r.ratio),
                         human_head_x=q[0, 0], human_head_y=q[0, 1], human_tail_x=q[1, 0], human_tail_y=q[1, 1],
                         auto_head_x=q[2, 0], auto_head_y=q[2, 1], auto_tail_x=q[3, 0], auto_tail_y=q[3, 1]))
    pd.DataFrame(rows).to_csv(OUT / "examples.csv", index=False)
    print(pd.DataFrame(rows)[["image_id", "label", "ratio"]].to_string(index=False))


if __name__ == "__main__":
    main()
