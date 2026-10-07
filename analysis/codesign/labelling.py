"""What labellers do with a pre-fill, and what a label costs them (paper section 8).

Pre-fills (data/db_extracts/seed_moves.psv, sql/extract_seed_moves.sql): every annotation made from
a Label Studio pre-fill, each keypoint matched by label to the seed's keypoint in the same task. Moves
are measured, not taken from Label Studio's "prediction-changed" origin flag, which marks many
annotations whose keypoints did not move (laser model seeds: 56% unchanged by the flag, ~89% by
distance).

  seed source   earlier human label (re-labelling campaigns, 2025-10/11; model_version sql*)
                model (laser-detector, from 2026-07-27; SAM 3.1 head/tail "v2 crop", from 2026-09-07)
  outcome       per keypoint: unchanged (< 0.5 px), nudged (0.5-20 px), replaced (> 20 px)
                per annotation: unchanged = every keypoint unchanged

Time per label (data/db_extracts/annotations.psv): median lead time of unseeded labels, and of
seeded labels by outcome. Lead time includes idle tabs, so medians only.

Writes analysis/codesign/results/labelling_seeds.csv (per keypoint label) and
labelling_seed_annotations.csv (per annotation).
Run: uv run python analysis/codesign/labelling.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from fishsense_cscw.paths import REPO

OUT = REPO / "analysis/codesign/results"
UNCHANGED_PX, NUDGE_PX = 0.5, 20.0
AUTO_ACCEPT = "2026-09-03"


def seed_moves() -> pd.DataFrame:
    d = pd.read_csv(REPO / "data/db_extracts/seed_moves.psv", sep="|", header=None,
                    names="kind ann_id image_id created_at lead_time_s label ax ay sx sy model_version".split())
    d["created_at"] = pd.to_datetime(d.created_at, utc=True, format="ISO8601")
    d["dist"] = np.hypot(d.ax - d.sx, d.ay - d.sy)
    d["seed"] = np.where(d.model_version.fillna("").str.match(r"laser-detector|v2 crop"), "model", "earlier human label")
    d["outcome"] = pd.cut(d.dist, [-1, UNCHANGED_PX, NUDGE_PX, np.inf], labels=["unchanged", "nudged", "replaced"])
    d["period"] = np.where(d.created_at >= pd.Timestamp(AUTO_ACCEPT, tz="UTC"), "after auto-accept", "before auto-accept")
    return d


def main():
    d = seed_moves()
    kp = (d.groupby(["kind", "seed", "label"]).agg(
              keypoints=("dist", "size"), unchanged=("outcome", lambda s: (s == "unchanged").mean()),
              nudged=("outcome", lambda s: (s == "nudged").mean()), replaced=("outcome", lambda s: (s == "replaced").mean()),
              moved_median_px=("dist", lambda s: s[s >= UNCHANGED_PX].median()))
            .reset_index())
    a = d.groupby(["kind", "seed", "period", "ann_id"]).agg(dist=("dist", "max"), lead=("lead_time_s", "first")).reset_index()
    a["outcome"] = pd.cut(a.dist, [-1, UNCHANGED_PX, NUDGE_PX, np.inf], labels=["unchanged", "nudged", "replaced"])
    ann = (a.groupby(["kind", "seed", "period"]).agg(
               annotations=("dist", "size"), unchanged=("outcome", lambda s: (s == "unchanged").mean()),
               within_3px=("dist", lambda s: (s <= 3).mean()), replaced=("outcome", lambda s: (s == "replaced").mean()),
               moved_median_px=("dist", lambda s: s[s >= UNCHANGED_PX].median()),
               seconds_unchanged=("lead", lambda s: s[a.loc[s.index, "outcome"] == "unchanged"].median()),
               seconds_moved=("lead", lambda s: s[a.loc[s.index, "outcome"] != "unchanged"].median()))
             .reset_index())
    C = "kind ann_id image_id dive_id annotator lead_time_s created_at seeded laser_colour ref_points skipped_points upside_down slate origins".split()
    t = pd.read_csv(REPO / "data/db_extracts/annotations.psv", sep="|", header=None, names=C, low_memory=False)
    un = t[(t.seeded != "t") & t.kind.isin(["laser", "headtail"])].groupby("kind").lead_time_s.median()
    ann["seconds_unseeded"] = ann.kind.map(un)
    OUT.mkdir(parents=True, exist_ok=True)
    kp.to_csv(OUT / "labelling_seeds.csv", index=False, float_format="%.4f")
    ann.to_csv(OUT / "labelling_seed_annotations.csv", index=False, float_format="%.4f")
    pd.set_option("display.width", 220)
    print(kp.round(3).to_string(index=False)); print(); print(ann.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
