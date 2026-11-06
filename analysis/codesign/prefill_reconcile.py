"""Reconcile the two counts of earlier-human-label pre-fills kept unchanged: 626 of 711 (88.0%) and 655 of 726 (90.2%).

  626 / 711  intro_numbers.py item 2a (fishsense_cscw/laser_pairs.py): pairs of laser labels by two labelers on one
             canonical image, lead time <= 300 s, whose later label was seeded from the earlier; kept = Label Studio's
             origin flag "prediction" (vs "prediction-changed")
  655 / 726  intro_numbers.py item 2d / labelling.py (sql/extract_seed_moves.sql): every saved laser keypoint whose
             annotation was pre-filled from an earlier human label, matched by label to the seed's keypoint; kept =
             within 0.5 px of the seed (the definition the detector-seeded 703 / 791 uses)

The two differ in population (pairs vs every seeded keypoint) and in the rule (flag vs distance). This puts both rules
on the images the two populations share, and counts what each population has that the other lacks.
Writes analysis/codesign/results/prefill_reconcile.csv.
Run: uv run python analysis/codesign/prefill_reconcile.py
"""
from __future__ import annotations

import sys

import pandas as pd

from fishsense_cscw import laser_pairs
from fishsense_cscw.paths import REPO

sys.path.insert(0, str(REPO / "analysis/codesign"))
import labelling  # noqa: E402


def main():
    p = laser_pairs.pairs(laser_pairs.load_annotations())
    p = p[p.later_action.isin(["accepted", "moved"])]
    sm = labelling.seed_moves()
    h = sm[(sm.kind == "laser") & (sm.seed == "earlier human label")]
    per_image = h.groupby("image_id").dist.max()           # one image, one annotation; max over its keypoints
    both = p[p.image_id.isin(per_image.index)].assign(dist=lambda x: x.image_id.map(per_image))
    flag, dist = both.later_action.eq("accepted"), both.dist < labelling.UNCHANGED_PX
    only_pairs = p[~p.image_id.isin(per_image.index)]
    only_seed = h[~h.image_id.isin(p.image_id)]
    rows = [
        ("pairs: kept by origin flag (the paper's 626 / 711)", p.later_action.eq("accepted").sum(), len(p)),
        ("seeded keypoints: kept within 0.5 px (the figure's 655 / 726)", (h.dist < labelling.UNCHANGED_PX).sum(), len(h)),
        ("shared images: kept by origin flag", flag.sum(), len(both)),
        ("shared images: kept within 0.5 px", dist.sum(), len(both)),
        ("shared images: flag kept and within 0.5 px", (flag & dist).sum(), len(both)),
        ("shared images: flag moved but within 0.5 px", (~flag & dist).sum(), len(both)),
        ("shared images: flag kept but moved >= 0.5 px", (flag & ~dist).sum(), len(both)),
        ("pairs only (no matched seed keypoint): kept by origin flag", only_pairs.later_action.eq("accepted").sum(), len(only_pairs)),
        ("seeded keypoints only (not in a pair): kept within 0.5 px", (only_seed.dist < labelling.UNCHANGED_PX).sum(), len(only_seed)),
    ]
    R = pd.DataFrame(rows, columns=["quantity", "kept", "of"]); R["share"] = R.kept / R.of
    R.to_csv(REPO / "analysis/codesign/results/prefill_reconcile.csv", index=False, float_format="%.4f")
    print(R.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
