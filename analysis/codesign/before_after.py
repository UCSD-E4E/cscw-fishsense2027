"""Task 3e: before/after for the timeline revisions that the labelling record can test.

Source: one row per Label Studio annotation (data/db_extracts/annotations.psv, sql/extract_annotations.sql).
lead_time_s is Label Studio's time the task was open, so it includes idle tabs; medians are used
throughout. Every comparison is made within annotator first (the labelling analogue of
"within-diver"), then combined:

  per annotator with >= MIN_N labels in both groups: median(B) - median(A), in seconds
  combined: mean of the per-annotator differences weighted by min(n_A, n_B)
  95% interval: resample annotators (whole annotators, 2,000 draws)

Revisions tested (timeline.yaml):
  slate pattern H -> Tic-Tac-Toe -> V (driver: labelability)   seconds per slate frame, and the
      number of reference points labelled per frame, by the dive's slate pattern. Slate labelling
      began in 2025-11, after all three patterns were retired from capture, so pattern is not
      confounded with labelling date - but the patterns come from different dives and sites.
  laser red -> green (driver: diver visibility; red said to be easier to label)   seconds per
      unseeded laser label, by the dive's laser colour (>= 90% of its labels; mixed dives dropped)
  laser model pre-fill (2026-07-27)   unseeded labels before vs pre-filled labels after
  head/tail model pre-fill (2026-09-07)   the same

Not testable from this record (reported in claims.yaml/questions.md): TG-6 -> TG-7 (its 8 dives were
never labelled), mounts (3f), the Temporal migration (data/temporal), auto-accept (task-level
review record not extracted).

Writes analysis/codesign/results/before_after.csv and before_after_annotators.csv.
Run: uv run python analysis/codesign/before_after.py
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from fishsense_cscw.paths import REPO

OUT = REPO / "analysis/codesign/results"
COLS = "kind ann_id image_id dive_id annotator lead_time_s created_at seeded laser_colour ref_points skipped_points upside_down slate".split()
MIN_N, N_BOOT = 10, 2000
LASER_PREFILL, HEADTAIL_PREFILL = "2026-07-27", "2026-09-07"


def load() -> pd.DataFrame:
    d = pd.read_csv(REPO / "data/db_extracts/annotations.psv", sep="|", header=None, names=COLS, low_memory=False)
    d["created_at"] = pd.to_datetime(d.created_at, utc=True, format="ISO8601")
    d["seeded"] = d.seeded == "t"
    d["pattern"] = d.slate.fillna("").str.extract(r"^(H-Slate|Tic-Tac-Toe|V-Slate)")[0]
    col = pd.read_csv(REPO / "data/db_extracts/dive_laser_colour.psv", sep="|", header=None,
                      names=["dive_id", "red", "green"])
    share = col.green / (col.red + col.green)
    d["dive_colour"] = d.dive_id.map(pd.Series(np.select([share >= .9, share <= .1], ["green", "red"], "mixed"),
                                               index=col.dive_id))
    return d


def within(d: pd.DataFrame, group: str, a, b, value="lead_time_s"):
    """Per-annotator median differences B - A, combined; annotator-resampled interval."""
    rows = []
    for ann, g in d.groupby("annotator"):
        ga, gb = g.loc[g[group] == a, value].dropna(), g.loc[g[group] == b, value].dropna()
        if len(ga) >= MIN_N and len(gb) >= MIN_N:
            rows.append(dict(annotator=ann, n_a=len(ga), n_b=len(gb), med_a=ga.median(), med_b=gb.median(),
                             diff=gb.median() - ga.median(), w=min(len(ga), len(gb))))
    P = pd.DataFrame(rows)
    if P.empty:
        return P, np.nan, (np.nan, np.nan)
    est = np.average(P["diff"], weights=P.w)
    rng = np.random.default_rng(0)
    boots = [np.average(P["diff"].to_numpy()[i], weights=P.w.to_numpy()[i])
             for i in (rng.integers(0, len(P), len(P)) for _ in range(N_BOOT))]
    return P, est, tuple(np.percentile(boots, [2.5, 97.5]))


def main():
    d = load()
    slate = d[(d.kind == "slate") & d.pattern.notna()]
    laser = d[(d.kind == "laser") & ~d.seeded & d.laser_colour.isin(["Red Laser", "Green Laser"])]
    laser = laser[laser.laser_colour.str.split().str[0].str.lower() == laser.dive_colour]
    las_pf = d[d.kind == "laser"].assign(phase=lambda t: np.where(
        t.created_at >= LASER_PREFILL, np.where(t.seeded, "after, pre-filled", "after, unseeded"), np.where(t.seeded, "before, seeded", "before, unseeded")))
    ht_pf = d[d.kind == "headtail"].assign(phase=lambda t: np.where(
        t.created_at >= HEADTAIL_PREFILL, np.where(t.seeded, "after, pre-filled", "after, unseeded"), np.where(t.seeded, "before, seeded", "before, unseeded")))
    tests = [
        ("slate pattern", "s per slate frame", slate, "pattern", "H-Slate", "Tic-Tac-Toe", "lead_time_s"),
        ("slate pattern", "s per slate frame", slate, "pattern", "Tic-Tac-Toe", "V-Slate", "lead_time_s"),
        ("slate pattern", "reference points labelled", slate, "pattern", "H-Slate", "Tic-Tac-Toe", "ref_points"),
        ("slate pattern", "reference points labelled", slate, "pattern", "Tic-Tac-Toe", "V-Slate", "ref_points"),
        ("laser red -> green", "s per unseeded laser label", laser, "dive_colour", "red", "green", "lead_time_s"),
        ("laser model pre-fill", "s per laser label", las_pf, "phase", "before, unseeded", "after, pre-filled", "lead_time_s"),
        ("head/tail model pre-fill", "s per head/tail label", ht_pf, "phase", "before, unseeded", "after, pre-filled", "lead_time_s"),
    ]
    rows, per = [], []
    for rev, metric, data, group, a, b, value in tests:
        P, est, (lo, hi) = within(data, group, a, b, value)
        xa, xb = data.loc[data[group] == a, value].dropna(), data.loc[data[group] == b, value].dropna()
        rows.append(dict(revision=rev, metric=metric, a=a, b=b, n_a=len(xa), n_b=len(xb),
                         pooled_median_a=xa.median(), pooled_median_b=xb.median(),
                         pooled_mean_a=xa.mean(), pooled_mean_b=xb.mean(),
                         annotators_both=len(P), annotators_a=data.loc[data[group] == a, "annotator"].nunique(),
                         annotators_b=data.loc[data[group] == b, "annotator"].nunique(),
                         within_annotator_diff=est, ci_lo=lo, ci_hi=hi))
        if len(P):
            per.append(P.assign(revision=rev, metric=metric, a=a, b=b))
    R = pd.DataFrame(rows)
    # descriptive context for the slate patterns: points per frame and skipped/upside-down flags
    ctx = (slate.groupby("pattern").agg(frames=("ann_id", "size"), dives=("dive_id", "nunique"), annotators=("annotator", "nunique"),
                                        median_s=("lead_time_s", "median"), ref_points_median=("ref_points", "median"),
                                        ref_points_lt8=("ref_points", lambda s: (s < 8).mean()),
                                        skipped_flag=("skipped_points", lambda s: s.notna().mean()),
                                        upside_down=("upside_down", lambda s: (s.astype(str) == "t").mean()))
               .reset_index())
    OUT.mkdir(parents=True, exist_ok=True)
    R.to_csv(OUT / "before_after.csv", index=False, float_format="%.4f")
    pd.concat(per).to_csv(OUT / "before_after_annotators.csv", index=False, float_format="%.4f")
    ctx.to_csv(OUT / "before_after_slate_patterns.csv", index=False, float_format="%.4f")
    pd.set_option("display.width", 250)
    print(R.round(2).to_string(index=False)); print(); print(ctx.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
