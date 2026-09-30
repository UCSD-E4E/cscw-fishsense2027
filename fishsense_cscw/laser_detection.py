"""T3: how often the production laser detector finds the dot a human drew, unseeded.

The detector always returns a point (`fraction_localized = 1.0` in its own metrics).
Whether it thinks a dot is *present* is its presence confidence, thresholded at 0.5 in
its training config. So every frame lands in exactly one outcome:

* dot frames -- ``found``: confident, and within 10 px of the human dot;
  ``missed``: not confident (a lost measurement); ``confident-wrong``: confident but
  more than 10 px away (a *bad* measurement, which is worse than a miss).
* no-dot frames -- ``false-alarm`` (confident) or ``correct-reject``.

The oracle is human labels drawn *without* a pre-annotation. T1/T2 show that seeded
labels are copies of the seed, so scoring against them would be circular.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fishsense_cscw.paths import REPO

HERE = REPO / "laser_detection_analysis"
PRESENCE_THRESHOLD = 0.5  # the checkpoint's cfg["presence_threshold"]
HIT_RADIUS_PX = 10.0  # the auto-accept gate's own perpendicular band


def load(threshold: float = PRESENCE_THRESHOLD, radius: float = HIT_RADIUS_PX) -> pd.DataFrame:
    sample = pd.read_csv(HERE / "sample.csv")
    sample["human_x"] = sample.x_pct / 100 * sample.ow
    sample["human_y"] = sample.y_pct / 100 * sample.oh
    d = pd.read_csv(HERE / "predictions.csv").merge(sample, on="image_id", how="left")
    d["distance_px"] = np.hypot(d.pred_x - d.human_x, d.pred_y - d.human_y)
    d["present"] = d.confidence >= threshold
    d["outcome"] = np.select(
        [d.has_dot & d.present & (d.distance_px <= radius), d.has_dot & ~d.present,
         d.has_dot & d.present & (d.distance_px > radius), ~d.has_dot & d.present],
        ["found", "missed", "confident-wrong", "false-alarm"], "correct-reject")
    return d


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (np.nan, np.nan)
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return centre - half, centre + half


def summarize(d: pd.DataFrame) -> pd.Series:
    dots, neg = d[d.has_dot], d[~d.has_dot]
    out = {}
    if len(dots):
        found = int((dots.outcome == "found").sum())
        out.update(dot_frames=len(dots), dives=dots.dive_id.nunique(), recall=found / len(dots),
                   recall_ci=wilson(found, len(dots)),
                   missed=float((dots.outcome == "missed").mean()),
                   confident_wrong=float((dots.outcome == "confident-wrong").mean()))
    if len(neg):
        fa = int((neg.outcome == "false-alarm").sum())
        out.update(no_dot_frames=len(neg), false_alarm=fa / len(neg), false_alarm_ci=wilson(fa, len(neg)))
    return pd.Series(out)


def dive_bootstrap(d: pd.DataFrame, n: int = 3000, seed: int = 0) -> dict:
    """Resample whole dives: frames within a dive share a rig, a site and a labeller."""
    rng = np.random.default_rng(seed)
    dots = d[d.has_dot]
    ids = dots.dive_id.unique()
    by = {i: dots[dots.dive_id == i] for i in ids}
    recall, gap = [], []
    for _ in range(n):
        s = pd.concat([by[i] for i in rng.choice(ids, len(ids))])
        f = s.outcome == "found"
        recall.append(f.mean())
        gap.append(f[s.wavelength == "red"].mean() - f[s.wavelength == "green"].mean())
    return {"recall_ci": tuple(np.quantile(recall, [0.025, 0.975])),
            "red_minus_green_ci": tuple(np.nanquantile(gap, [0.025, 0.975]))}


# --------------------------------------------------------------------------
# Fixes that need no retraining, tested on the same predictions.
# --------------------------------------------------------------------------

def threshold_sweep(prod: pd.DataFrame, thresholds=(0.5, 0.3, 0.2, 0.1, 0.05), radius: float = HIT_RADIUS_PX) -> pd.DataFrame:
    """What lowering the presence threshold buys. Answer: almost nothing -- the missed
    dots sit at a median confidence of 0.05, so recovering them means admitting most
    no-dot frames as well. The threshold cannot trade missed for wrong."""
    dots, neg = prod[prod.has_dot], prod[~prod.has_dot]
    rows = []
    for t in thresholds:
        present = dots.confidence >= t
        recall = float((present & (dots.distance_px <= radius)).mean())
        wrong = float((present & (dots.distance_px > radius)).mean())
        rows.append(dict(threshold=t, recall=recall, missed=1 - recall - wrong, confident_wrong=wrong,
                         false_alarm=float((neg.confidence >= t).mean())))
    return pd.DataFrame(rows).set_index("threshold")


def leave_one_out_line_distance(frames: pd.DataFrame, min_others: int = 4) -> pd.Series:
    """Perpendicular distance from each prediction to the laser line fitted through the
    dive's *other* human dots. NaN where fewer than `min_others` other dots exist.

    A stand-in for the dive line production could fit from its own accepted frames. The
    sample carries at most 12 frames per dive, so these lines are far looser than a real
    dive's (P1: 71 dots define a line to 0.64 px); the found-but-off-line rate here is an
    upper bound on what the gate would cost."""
    out = pd.Series(np.nan, index=frames.index)
    for _, g in frames.groupby("dive_id"):
        human = g[g.has_dot]
        if len(human) < min_others + 1:
            continue
        for i in g.index:
            others = human.drop(i, errors="ignore")
            if len(others) < min_others:
                continue
            pts = others[["human_x", "human_y"]].to_numpy()
            centre = pts.mean(0)
            direction = np.linalg.svd(pts - centre)[2][0]
            p = np.array([g.at[i, "pred_x"], g.at[i, "pred_y"]]) - centre
            out[i] = abs(p[0] * direction[1] - p[1] * direction[0])
    return out


def line_gate_effect(prod: pd.DataFrame, corridor_px: float = 25.0) -> pd.DataFrame:
    """Share of each outcome that a line corridor would reject, on frames with a usable
    leave-one-out line."""
    frames = prod.assign(line_px=leave_one_out_line_distance(prod))
    frames = frames[frames.line_px.notna()]
    rows = {}
    for name in ("found", "confident-wrong", "false-alarm"):
        s = frames[frames.outcome == name]
        rows[name] = dict(n=len(s), rejected=float((s.line_px > corridor_px).mean()))
    return pd.DataFrame(rows).T
