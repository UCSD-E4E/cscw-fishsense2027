"""What the field corpus shows divers actually did, against what the estimator needs.

Scope note that governs every sentence written from this module: P1 *derives* "about ten
frames per animal" (its Figure 8) and "work beyond 1 m" (section 4.2.3) from its own
analysis. Nothing on disk shows divers were told either at collection time. So these are
**shortfalls against the estimator's requirements**, not non-compliance with an
instruction. The only instruction P1 says divers were given is to frame within 15 degrees
of broadside, and that needs a pose measurement this module does not have (T7c).
"""

from __future__ import annotations

import pandas as pd

from fishsense_cscw.paths import IMWUT

FIELD_CSV = IMWUT / "fish_model_analysis" / "data" / "field.csv"
FRAMES_FOR_STABLE_P90 = 10  # P1 Figure 8
MIN_RECOMMENDED_RANGE_M = 1.0  # P1 section 4.2.3
TABLE1_RANGE_M = (2.0, 5.0)  # P1 Table 1, "Triangulation Rangefinding"


def load_field() -> pd.DataFrame:
    """The seven reef deployments: one row per Measurement of a wild fish.

    `fish_id` is bound per animal per dive by stage 14, so repeat frames of one animal
    share it -- which is what makes frames-per-animal meaningful. These are *measured*
    frames: a frame the laser missed, or that never got labelled, is not here.
    """
    df = pd.read_csv(FIELD_CSV, sep="|")
    df = df[pd.to_numeric(df.dive_id, errors="coerce").notna()].copy()
    for col in ("length_m", "range_m", "depth_m"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["animal"] = df.dive_id.astype(str) + ":" + df.fish_id.astype(str)
    return df


def frames_per_animal(df: pd.DataFrame) -> pd.Series:
    return df.groupby("animal").size()


def range_bands(df: pd.DataFrame) -> dict:
    r = df.range_m.dropna()
    lo, hi = TABLE1_RANGE_M
    return {
        "n": len(r),
        "p10": float(r.quantile(0.1)), "p50": float(r.median()), "p90": float(r.quantile(0.9)),
        "below_1m": int((r < MIN_RECOMMENDED_RANGE_M).sum()),
        "below_1m_pct": 100 * float((r < MIN_RECOMMENDED_RANGE_M).mean()),
        "in_table1_range": int(((r >= lo) & (r <= hi)).sum()),
        "in_table1_range_pct": 100 * float(((r >= lo) & (r <= hi)).mean()),
        "below_2m_pct": 100 * float((r < lo).mean()),
    }
