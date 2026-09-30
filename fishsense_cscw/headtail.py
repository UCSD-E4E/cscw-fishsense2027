"""Head/tail keypoint error across the two domains, and what the fork error is made of.

The detector is `FishHeadTailDetector.find_head_tail_img`: classical, untrained, the
same function in both domains. What differs is upstream: Lite picks the instance under
the laser dot; Mobile, having no laser, picks by area (or score x area after the fix).
Errors are scored exactly as both producers score them -- orientation resolved by
taking the better of the direct and swapped assignment, because nothing downstream
reads which end is the snout.

Everything is reported as a percentage of the human snout-fork length, per frame. Raw
pixels are not comparable across the domains: a Mobile fish spans a median ~960 px of
a 1920 px frame, a Lite fish ~540 px of a 4014 px one.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
from PIL import Image

from fishsense_cscw.paths import DATA

MOBILE = DATA / "mobile_headtail"
LITE = DATA / "lite_headtail_field"

#: Long side each segmenter is fed. Fishial's `MAX_SIZE_TEST`; SAM3's encoder is 1008.
FISHIAL_INPUT_PX = 1058
MOBILE_FRAME_PX = 1920
LITE_FRAME_PX = 4014


def _orient(head, tail, snout, fork):
    """Assign predicted endpoints to human ones, whichever pairing is closer in total."""
    direct = np.linalg.norm(head - snout) + np.linalg.norm(tail - fork)
    swapped = np.linalg.norm(tail - snout) + np.linalg.norm(head - fork)
    return (tail, head) if swapped < direct else (head, tail)


def load_mobile(tag: str = "v2_1_5_fix") -> pd.DataFrame:
    """One row per labelled frame; prediction columns are NaN where nothing was detected."""
    rows = []
    for r in json.loads((MOBILE / f"{tag}.json").read_text())["results"]:
        w, h, g = r["W"], r["H"], r["gt"]
        snout = np.array([g["snout"][0] / 100 * w, g["snout"][1] / 100 * h])
        fork = np.array([g["fork"][0] / 100 * w, g["fork"][1] / 100 * h])
        row = dict(image=r["image"], length_px=float(np.linalg.norm(fork - snout)),
                   predicted=bool(r.get("detected") and "head" in r),
                   snout_x=snout[0], snout_y=snout[1], fork_x=fork[0], fork_y=fork[1])
        if row["predicted"]:
            head, tail = _orient(np.array(r["head"]), np.array(r["tail"]), snout, fork)
            row.update(head_x=head[0], head_y=head[1], tail_x=tail[0], tail_y=tail[1],
                       snout_px=float(np.linalg.norm(head - snout)),
                       fork_px=float(np.linalg.norm(tail - fork)),
                       pred_length_px=float(np.linalg.norm(head - tail)))
        rows.append(row)
    df = pd.DataFrame(rows)
    df["model_input_px"] = df.length_px * FISHIAL_INPUT_PX / MOBILE_FRAME_PX
    return _derive(df)


def load_lite(model: str = "fishial") -> pd.DataFrame:
    """The `baseline` arm of the frozen Lite field run, one row per labelled frame.

    Human length comes from the manifest rather than the result file, whose
    `human_len_px` is blank on frames where nothing was predicted -- and those are
    exactly the frames a coverage-by-size analysis needs.
    """
    res = pd.read_csv(LITE / f"{model}.csv")
    res = res[res.arm == "baseline"]
    man = pd.read_csv(LITE / "manifest_field.csv")
    man["length_px"] = np.hypot(man.head_x - man.tail_x, man.head_y - man.tail_y)
    df = res.merge(man[["image_id", "length_px"]], on="image_id", how="left")
    df["predicted"] = df.status == "predicted"
    df = df.rename(columns={"err_head_px": "snout_px", "err_tail_px": "fork_px"})
    df["pred_length_px"] = df.pred_len_px
    df["model_input_px"] = df.length_px * FISHIAL_INPUT_PX / LITE_FRAME_PX
    return _derive(df)


def _derive(df: pd.DataFrame) -> pd.DataFrame:
    df["snout_pct"] = 100 * df.snout_px / df.length_px
    df["fork_pct"] = 100 * df.fork_px / df.length_px
    df["length_err_pct"] = 100 * (df.pred_length_px - df.length_px) / df.length_px
    return df


def _bootstrap_median(values, groups=None, n=4000, seed=0):
    """95 % interval on the median; resamples whole groups when given (frames within a
    dive are not independent, and the Lite set is only six dives)."""
    rng = np.random.default_rng(seed)
    values = np.asarray(values, float)
    if groups is None:
        draws = [np.median(rng.choice(values, len(values))) for _ in range(n)]
    else:
        groups = np.asarray(groups)
        ids = np.unique(groups)
        by = {g: values[groups == g] for g in ids}
        draws = [np.median(np.concatenate([by[g] for g in rng.choice(ids, len(ids))])) for _ in range(n)]
    return tuple(np.quantile(draws, [0.025, 0.975]))


def summarize(df: pd.DataFrame, cluster: str | None = None) -> dict:
    """The cross-domain row. `usable` is the product metric from the Lite plan:
    within 5 % of the labeller's own length, as a share of *labelled* frames."""
    p = df[df.predicted]
    groups = p[cluster] if cluster else None
    return {
        "labelled": len(df),
        "predicted": len(p),
        "coverage_pct": 100 * len(p) / len(df),
        "fish_at_model_input_px_p50": float(df.model_input_px.median()),
        "snout_pct_p50": float(p.snout_pct.median()),
        "snout_pct_p50_ci": _bootstrap_median(p.snout_pct, groups),
        "snout_pct_p90": float(p.snout_pct.quantile(0.9)),
        "fork_pct_p50": float(p.fork_pct.median()),
        "fork_pct_p50_ci": _bootstrap_median(p.fork_pct, groups),
        "fork_pct_p90": float(p.fork_pct.quantile(0.9)),
        "fork_over_snout": float(p.fork_pct.median() / p.snout_pct.median()),
        "abs_length_err_pct_p50": float(p.length_err_pct.abs().median()),
        "abs_length_err_pct_p90": float(p.length_err_pct.abs().quantile(0.9)),
        "signed_length_err_pct_p50": float(p.length_err_pct.median()),
        "usable_pct_of_labelled": 100 * float((p.length_err_pct.abs() <= 5).sum()) / len(df),
    }


def fork_decomposition(df: pd.DataFrame, masks: str | None = "masks_v2_1_5_fix") -> pd.DataFrame:
    """Split each endpoint error into components along and across the human body axis.

    `headtail-prediction.md` section 9.2 asks whether the fork error is a *convention*
    problem (labellers click the notch, the detector returns a mask extremity: a tight,
    signed, along-axis offset a constant would remove) or a *model* problem (scattered).
    Needs predicted coordinates, so it runs on Mobile only until the Lite run is redone.

    Sign convention: positive `*_along` is *beyond* the human point, away from the body.
    With `masks`, also measures how far the segmentation itself reaches past the fork and
    how wide it is there -- i.e. whether the caudal lobes are in the mask at all.
    """
    p = df[df.predicted].copy()
    snout = p[["snout_x", "snout_y"]].to_numpy()
    fork = p[["fork_x", "fork_y"]].to_numpy()
    head = p[["head_x", "head_y"]].to_numpy()
    tail = p[["tail_x", "tail_y"]].to_numpy()
    length = p.length_px.to_numpy()
    u = (fork - snout) / length[:, None]
    n = np.column_stack([-u[:, 1], u[:, 0]])
    p["fork_along_pct"] = 100 * np.einsum("ij,ij->i", tail - fork, u) / length
    p["fork_across_pct"] = 100 * np.abs(np.einsum("ij,ij->i", tail - fork, n)) / length
    p["snout_along_pct"] = 100 * np.einsum("ij,ij->i", head - snout, -u) / length
    p["snout_across_pct"] = 100 * np.abs(np.einsum("ij,ij->i", head - snout, n)) / length
    if masks:
        reach, width = [], []
        for img, f, uu, nn, L in zip(p.image, fork, u, n, length):
            path = MOBILE / masks / (img.rsplit(".", 1)[0] + ".png")
            ys, xs = np.nonzero(np.asarray(Image.open(path)) > 0)
            rel = np.column_stack([xs, ys]) - f
            along = rel @ uu
            reach.append(100 * along.max() / L)
            beyond = along > 0
            width.append(100 * np.ptp(rel[beyond] @ nn) / L if beyond.sum() > 10 else 0.0)
        p["mask_past_fork_pct"] = reach
        p["mask_width_past_fork_pct"] = width
    return p
