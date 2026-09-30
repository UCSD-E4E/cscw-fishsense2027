"""The 755 "doubly-labelled" laser images, and why they are not an inter-annotator study.

`2026-09-01_underwater-correction` found 755 canonical images carrying usable laser
annotations from two distinct labellers, and used them for a *timing* correlation. The
P2 inventory took them for a ready-made spatial agreement study. They are not one:

* 751 of 755 pairs come from two *different* Label Studio projects, a median ~260 days
  apart -- re-labelling campaigns, not two people on one task.
* The later project was **pre-annotated with the earlier human label**. Where the later
  labeller accepted the seed, the two labels agree to 0.00 px (mixed canvases) or
  ~0.4 px (same canvas). That is a copy, not agreement.

What the pairs *do* measure is how labellers treat a pre-annotation, which is the more
useful question for P2 anyway (T22): see `anchoring`.

Labels are compared in each annotation's own pixel frame (`pct / 100 * original_width`).
Two canvases occur -- 3987 x 3016 on the oldest manual labels, 4014 x 3016 elsewhere --
and the exact 0.00 px agreement across them is the evidence that they share a frame.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from fishsense_cscw.paths import DATA

PAIRS = DATA / "laser_pairs"
LEAD_TIME_MAX_S = 300.0  # the effort study's own cut, kept so its 755 reproduces


def _tobool(s: pd.Series) -> pd.Series:
    if s.dtype == bool:
        return s
    return s.astype(str).str.lower().map({"t": True, "true": True, "f": False, "false": False}).astype(bool)


def load_annotations() -> pd.DataFrame:
    a = pd.read_csv(PAIRS / "annotations.csv")
    for col in ("is_canonical", "superseded", "completed", "cancelled"):
        a[col] = _tobool(a[col])
    a["created_at"] = pd.to_datetime(a.created_at, format="ISO8601")
    a["x"] = a.x_pct / 100 * a.ow
    a["y"] = a.y_pct / 100 * a.oh
    a["seed"] = np.select([a.origin.eq("prediction"), a.origin.eq("prediction-changed")],
                          ["accepted", "moved"], "none")
    return a


def usable(a: pd.DataFrame) -> pd.DataFrame:
    """The effort study's filter: canonical, not a skip, plausible lead time."""
    return a[a.is_canonical & ~a.cancelled & (a.lead_time > 0) & (a.lead_time <= LEAD_TIME_MAX_S)]


def pair_images(a: pd.DataFrame) -> pd.Index:
    n = usable(a).groupby("image_id").labeler.nunique()
    return n[n >= 2].index


def pairs(a: pd.DataFrame) -> pd.DataFrame:
    """One pair per image: earliest vs latest usable annotation by distinct labellers,
    both carrying a dot. `later_action` is what the second labeller did with their seed."""
    u = usable(a)
    u = u[u.image_id.isin(pair_images(a)) & (u.n_kp >= 1)].sort_values("created_at")
    rows = []
    for img, g in u.groupby("image_id"):
        g = g.drop_duplicates("labeler")
        if len(g) < 2:
            continue
        first, later = g.iloc[0], g.iloc[-1]
        rows.append(dict(image_id=img, dive_id=first.dive_id, later_action=later.seed,
                         canvas=f"{int(first.ow)}->{int(later.ow)}",
                         first_x=first.x, first_y=first.y, later_x=later.x, later_y=later.y,
                         first_superseded=first.superseded, later_superseded=later.superseded,
                         gap_days=(later.created_at - first.created_at).total_seconds() / 86400,
                         same_project=first.label_studio_project_id == later.label_studio_project_id))
    p = pd.DataFrame(rows)
    p["distance_px"] = np.hypot(p.later_x - p.first_x, p.later_y - p.first_y)
    return p


def live_label_distance(p: pd.DataFrame) -> pd.Series:
    """Distance from the later label to the nearest *live* label on the image now; NaN if
    the image has none. Separates a routine replacement (a live label at the same spot)
    from a discarded position (nothing live left)."""
    rows = pd.read_csv(PAIRS / "laserlabel_rows.csv")
    rows["superseded"] = _tobool(rows.superseded)
    live = rows[~rows.superseded & rows.x.notna()].groupby("image_id")[["x", "y"]].agg(list)

    def nearest(r):
        if r.image_id not in live.index:
            return np.nan
        xs, ys = live.loc[r.image_id, "x"], live.loc[r.image_id, "y"]
        return float(np.min(np.hypot(np.array(xs) - r.later_x, np.array(ys) - r.later_y)))

    return p.apply(nearest, axis=1)


def anchoring(p: pd.DataFrame) -> pd.DataFrame:
    """How labellers treated a seed, split by whether that seed's source label is now
    superseded. "Superseded" is not ground truth -- the flag carries no reason and is set
    both by the line-fit validator and by routine replacement -- so this is read together
    with `live_label_distance`, which says whether anything live replaced it."""
    seeded = p[p.later_action.isin(["accepted", "moved"])]
    t = seeded.groupby(["first_superseded", "later_action"]).size().unstack(fill_value=0)
    t["accept_rate"] = t.accepted / t.sum(axis=1)
    t.index = t.index.map({True: "seed's source now superseded", False: "seed's source live"})
    return t
