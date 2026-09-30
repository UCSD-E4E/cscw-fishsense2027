"""An upper bound on one labeller's landmark noise, from the P1 corpus, with no new labels.

`HANDOFF.md` section 5 item 1. A rigid target photographed repeatedly at one range must
read one length, so within a (dive, target, narrow range bin) cell the frame-to-frame
spread is landmark noise + ranging noise + pose.

**The estimator, and why not the one the handoff describes.** The handoff proposes the
spread among the *best-presented* frames. Taken literally that is biased *low*, not an
upper bound: keeping the longest frames also keeps the frames whose noise happened to be
positive, and truncating a distribution shrinks its spread. What survives the one-sided
pose argument is the *upper half-width*: pose can only shorten, noise is symmetric, so
deviations above the cell median are noise alone, measured from an anchor that pose has
dragged down. The RMS of those deviations is therefore >= the noise SD -- a bound in the
right direction. The full-cell MAD, which includes pose outright, is reported beside it
as the loosest bound.

Everything is attributed to the two endpoints to get a per-endpoint pixel figure, which
is conservative (ranging noise is in there too).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fishsense_cscw.paths import imwut_on_path


def load_cohort() -> pd.DataFrame:
    """P1's accuracy cohort with clicked endpoints, angle-test sessions excluded
    (one object at deliberately oblique poses is not a repeat-measurement test)."""
    imwut = imwut_on_path()
    from fishsense_imwut import calibration as cal
    from fishsense_imwut.distortion import load_head_tail

    df = pd.DataFrame(load_head_tail(imwut / "fish_model_analysis" / "data" / "head_tail.csv"))
    df = df[~df.dive_id.isin(cal.ANGLE_TEST_DIVES)].copy()
    df["length_px"] = np.hypot(df.head_x - df.tail_x, df.head_y - df.tail_y)
    return df


def noise_cells(df: pd.DataFrame, bin_m: float = 0.25, min_frames: int = 6) -> pd.DataFrame:
    """One row per usable (dive, model, range bin) cell, spreads in % of length."""
    df = df.assign(rbin=(df.depth_m // bin_m).astype(int), x=np.log(df.length_m))
    out = []
    for (dive, model, _), g in df.groupby(["dive_id", "model", "rbin"]):
        if len(g) < min_frames:
            continue
        x = g.x.to_numpy()
        med = np.median(x)
        up = x[x > med]
        if len(up) < 3:
            continue
        bound = 100 * np.sqrt(np.mean((up - med) ** 2))
        out.append(dict(dive_id=dive, model=model, n=len(g), range_m=float(g.depth_m.median()),
                        length_px=float(g.length_px.median()),
                        bound_pct=bound,
                        loose_pct=100 * 1.4826 * np.median(np.abs(x - med)),
                        px_per_endpoint=bound / 100 * g.length_px.median() / np.sqrt(2)))
    return pd.DataFrame(out)
